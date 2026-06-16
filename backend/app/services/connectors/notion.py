import tempfile
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app.services.connectors.base import DocumentConnector, SourceACL, SourceFile

_NOTION_API = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"
_PAGE_SIZE = 100


class NotionConnector(DocumentConnector):
    """Connecteur Notion via l'API officielle (Integration Token).

    Champs requis dans connector.config :
      - notion_token : str  (token depuis notion.so/my-integrations)

    Champs optionnels :
      - database_id : str  (indexe les pages d'une base de données Notion)
      - page_id     : str  (indexe les sous-pages d'une page racine)
      Si aucun n'est fourni, toutes les pages accessibles sont indexées.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        token = config.get("notion_token")
        if not token:
            raise ValueError("Notion connector requires 'notion_token' in config.")
        self._notion_headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }
        self._database_id: str | None = config.get("database_id")
        self._page_id: str | None = config.get("page_id")

    # ── list_files ────────────────────────────────────────────────────────────

    async def list_files(self) -> AsyncIterator[SourceFile]:  # type: ignore[override]
        async with httpx.AsyncClient(timeout=30, headers=self._notion_headers) as client:
            if self._database_id:
                async for page in self._iter_database_pages(client, self._database_id):
                    yield page
            elif self._page_id:
                async for page in self._iter_child_pages(client, self._page_id):
                    yield page
            else:
                async for page in self._iter_search_pages(client):
                    yield page

    async def _iter_search_pages(
        self, client: httpx.AsyncClient
    ) -> AsyncIterator[SourceFile]:
        cursor: str | None = None
        while True:
            body: dict[str, Any] = {
                "filter": {"value": "page", "property": "object"},
                "page_size": _PAGE_SIZE,
            }
            if cursor:
                body["start_cursor"] = cursor
            resp = await client.post(f"{_NOTION_API}/search", json=body)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("results", []):
                if sf := self._page_to_source_file(item):
                    yield sf
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

    async def _iter_database_pages(
        self, client: httpx.AsyncClient, database_id: str
    ) -> AsyncIterator[SourceFile]:
        cursor: str | None = None
        while True:
            body: dict[str, Any] = {"page_size": _PAGE_SIZE}
            if cursor:
                body["start_cursor"] = cursor
            resp = await client.post(
                f"{_NOTION_API}/databases/{database_id}/query", json=body
            )
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("results", []):
                if sf := self._page_to_source_file(item):
                    yield sf
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

    async def _iter_child_pages(
        self, client: httpx.AsyncClient, page_id: str
    ) -> AsyncIterator[SourceFile]:
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": _PAGE_SIZE}
            if cursor:
                params["start_cursor"] = cursor
            resp = await client.get(
                f"{_NOTION_API}/blocks/{page_id}/children", params=params
            )
            resp.raise_for_status()
            data = resp.json()
            for block in data.get("results", []):
                if block.get("type") == "child_page":
                    child_resp = await client.get(
                        f"{_NOTION_API}/pages/{block['id']}"
                    )
                    if child_resp.status_code == 200:
                        if sf := self._page_to_source_file(child_resp.json()):
                            yield sf
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

    def _page_to_source_file(self, page: dict[str, Any]) -> SourceFile | None:
        page_id = page.get("id", "").replace("-", "")
        if not page_id:
            return None

        title = "Sans titre"
        for prop in page.get("properties", {}).values():
            if prop.get("type") == "title":
                parts = prop.get("title", [])
                title = "".join(t.get("plain_text", "") for t in parts) or "Sans titre"
                break

        modified_str: str | None = page.get("last_edited_time")
        return SourceFile(
            external_id=page_id,
            title=title,
            path=title,
            source_url=page.get("url"),
            mime_type="text/plain",
            modified_at=(
                datetime.fromisoformat(modified_str.replace("Z", "+00:00"))
                if modified_str
                else None
            ),
            acl=[SourceACL(principal_type="group", principal_id="everyone", permission="read")],
        )

    # ── download_file ─────────────────────────────────────────────────────────

    async def download_file(self, source_file: SourceFile) -> Path:
        async with httpx.AsyncClient(timeout=60, headers=self._notion_headers) as client:
            text = await self._extract_page_text(client, source_file.external_id)

        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt", mode="w", encoding="utf-8"
        )
        try:
            tmp.write(f"# {source_file.title}\n\n{text}")
        finally:
            tmp.close()
        return Path(tmp.name)

    async def _extract_page_text(
        self, client: httpx.AsyncClient, page_id: str, depth: int = 0
    ) -> str:
        if depth > 3:
            return ""

        parts: list[str] = []
        cursor: str | None = None

        while True:
            params: dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            resp = await client.get(
                f"{_NOTION_API}/blocks/{page_id}/children", params=params
            )
            if resp.status_code != 200:
                break
            data = resp.json()

            for block in data.get("results", []):
                text = self._extract_block_text(block)
                if text:
                    parts.append(text)
                if block.get("has_children") and block.get("type") not in (
                    "child_database",
                    "child_page",
                ):
                    child_text = await self._extract_page_text(
                        client, block["id"], depth + 1
                    )
                    if child_text:
                        parts.append(child_text)

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

        return "\n".join(parts)

    def _extract_block_text(self, block: dict[str, Any]) -> str:
        block_type = block.get("type", "")
        content = block.get(block_type, {})
        rich_text = content.get("rich_text", [])
        text = "".join(t.get("plain_text", "") for t in rich_text)

        if block_type in ("heading_1", "heading_2", "heading_3"):
            return f"\n## {text}\n"
        if block_type == "bulleted_list_item":
            return f"• {text}"
        if block_type == "numbered_list_item":
            return f"  {text}"
        if block_type == "code":
            return f"```\n{text}\n```"
        if block_type == "divider":
            return "\n---\n"
        return text

import asyncio
import tempfile
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app.services.connectors.base import DocumentConnector, SourceACL, SourceFile
from app.services.ingestion.extractor import TextExtractor

SUPPORTED_EXTENSIONS = TextExtractor.supported_extensions
_GRAPH = "https://graph.microsoft.com/v1.0"
_GRAPH_SCOPE = "https://graph.microsoft.com/.default"
_PAGE_SIZE = 100


class SharePointConnector(DocumentConnector):
    """Connecteur Microsoft SharePoint / OneDrive via Microsoft Graph API.

    Champs requis dans connector.config :
      - tenant_id     : str  (ID du tenant Azure AD)
      - client_id     : str  (ID de l'application Azure AD)
      - client_secret : str  (secret de l'application)

    Champs optionnels :
      - site_id   : str  (ID du site SharePoint ; défaut = drive OneDrive de l'app)
      - drive_id  : str  (ID du drive spécifique ; priorité sur site_id)
      - folder_id : str  (ID du dossier racine dans le drive ; défaut = root)
    """

    def __init__(self, config: dict[str, Any]) -> None:
        tenant_id = config.get("tenant_id")
        client_id = config.get("client_id")
        client_secret = config.get("client_secret")
        if not all([tenant_id, client_id, client_secret]):
            raise ValueError(
                "SharePoint connector requires 'tenant_id', 'client_id' and "
                "'client_secret' in config."
            )
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._site_id: str | None = config.get("site_id")
        self._drive_id: str | None = config.get("drive_id")
        self._folder_id: str = config.get("folder_id") or "root"
        self._token: str | None = None

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _fetch_token(self) -> str:
        import msal  # type: ignore[import-untyped]

        app = msal.ConfidentialClientApplication(
            self._client_id,
            authority=f"https://login.microsoftonline.com/{self._tenant_id}",
            client_credential=self._client_secret,
        )
        result = app.acquire_token_for_client(scopes=[_GRAPH_SCOPE])
        if "access_token" not in result:
            raise RuntimeError(
                f"SharePoint auth failed: {result.get('error_description', 'unknown error')}"
            )
        return result["access_token"]  # type: ignore[return-value]

    async def _get_token(self) -> str:
        if not self._token:
            self._token = await asyncio.to_thread(self._fetch_token)
        return self._token

    async def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self._get_token()}"}

    # ── Drive root URL ────────────────────────────────────────────────────────

    def _items_url(self) -> str:
        if self._drive_id:
            return f"{_GRAPH}/drives/{self._drive_id}/items/{self._folder_id}/children"
        if self._site_id:
            return f"{_GRAPH}/sites/{self._site_id}/drive/items/{self._folder_id}/children"
        return f"{_GRAPH}/me/drive/items/{self._folder_id}/children"

    def _content_url(self, item_id: str) -> str:
        if self._drive_id:
            return f"{_GRAPH}/drives/{self._drive_id}/items/{item_id}/content"
        if self._site_id:
            return f"{_GRAPH}/sites/{self._site_id}/drive/items/{item_id}/content"
        return f"{_GRAPH}/me/drive/items/{item_id}/content"

    # ── list_files ────────────────────────────────────────────────────────────

    async def list_files(self) -> AsyncIterator[SourceFile]:  # type: ignore[override]
        headers = await self._headers()
        url: str | None = (
            f"{self._items_url()}"
            f"?$top={_PAGE_SIZE}"
            "&$select=id,name,file,size,lastModifiedDateTime,webUrl,eTag"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            while url:
                response = await client.get(url, headers=headers)
                if response.status_code == 401:
                    self._token = None
                    headers = await self._headers()
                    response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                for item in data.get("value", []):
                    if "file" not in item:
                        continue
                    name: str = item.get("name", "")
                    if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
                        continue
                    modified_str: str | None = item.get("lastModifiedDateTime")
                    yield SourceFile(
                        external_id=item["id"],
                        title=name,
                        path=item.get("webUrl", name),
                        source_url=item.get("webUrl"),
                        mime_type=item.get("file", {}).get("mimeType"),
                        checksum=item.get("file", {}).get("hashes", {}).get("sha256Hash"),
                        version=item.get("eTag"),
                        size_bytes=item.get("size"),
                        modified_at=(
                            datetime.fromisoformat(modified_str.replace("Z", "+00:00"))
                            if modified_str
                            else None
                        ),
                        acl=[SourceACL(principal_type="group", principal_id="everyone", permission="read")],
                    )

                url = data.get("@odata.nextLink")

    # ── download_file ─────────────────────────────────────────────────────────

    async def download_file(self, source_file: SourceFile) -> Path:
        headers = await self._headers()
        content_url = self._content_url(source_file.external_id)
        suffix = Path(source_file.title).suffix or ".bin"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                async with client.stream("GET", content_url, headers=headers) as response:
                    if response.status_code == 401:
                        self._token = None
                        new_headers = await self._headers()
                        async with client.stream("GET", content_url, headers=new_headers) as r2:
                            r2.raise_for_status()
                            async for chunk in r2.aiter_bytes(1024 * 1024):
                                tmp.write(chunk)
                    else:
                        response.raise_for_status()
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            tmp.write(chunk)
        finally:
            tmp.close()
        return Path(tmp.name)

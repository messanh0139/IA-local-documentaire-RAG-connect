import asyncio
import mimetypes
import tempfile
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.connectors.base import DocumentConnector, SourceACL, SourceFile
from app.services.ingestion.extractor import TextExtractor

SUPPORTED_EXTENSIONS = TextExtractor.supported_extensions

# Google Docs native formats → export targets
_EXPORT_MAP: dict[str, tuple[str, str]] = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
}

_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

_FIELDS = (
    "nextPageToken,"
    "files(id,name,mimeType,size,modifiedTime,webViewLink,md5Checksum,parents)"
)


class GoogleDriveConnector(DocumentConnector):
    """Connecteur Google Drive via compte de service (Service Account).

    Champs requis dans connector.config :
      - service_account_info : dict  (contenu du fichier JSON du compte de service)
      - folder_id             : str   (optionnel, ID du dossier racine ; défaut = "root")
      - impersonate_user      : str   (optionnel, email à usurper via domain-wide delegation)
      - shared_drive_id       : str   (optionnel, ID d'un Shared Drive)
    """

    def __init__(self, config: dict[str, Any]) -> None:
        sa_info = config.get("service_account_info")
        if not sa_info:
            raise ValueError(
                "Google Drive connector requires 'service_account_info' in config. "
                "Paste the content of your Service Account JSON key."
            )

        # Lazy import so the package is only required when the connector is used.
        from google.oauth2.service_account import Credentials  # type: ignore[import-untyped]
        from googleapiclient.discovery import build  # type: ignore[import-untyped]

        creds: Any = Credentials.from_service_account_info(sa_info, scopes=_DRIVE_SCOPES)
        if subject := config.get("impersonate_user"):
            creds = creds.with_subject(subject)

        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        self._folder_id: str = config.get("folder_id") or "root"
        self._shared_drive_id: str | None = config.get("shared_drive_id")

    def _list_page(self, page_token: str | None) -> dict:
        kwargs: dict[str, Any] = {
            "q": f"'{self._folder_id}' in parents and trashed = false",
            "pageSize": 100,
            "fields": _FIELDS,
        }
        if self._shared_drive_id:
            kwargs.update(
                corpora="drive",
                driveId=self._shared_drive_id,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
        if page_token:
            kwargs["pageToken"] = page_token
        return self._service.files().list(**kwargs).execute()  # type: ignore[no-any-return]

    def _get_media_request(self, file_id: str, native_mime: str) -> Any:
        export_mime, _ = _EXPORT_MAP.get(native_mime, (None, None))
        if export_mime:
            return self._service.files().export_media(fileId=file_id, mimeType=export_mime)
        return self._service.files().get_media(
            fileId=file_id, supportsAllDrives=True
        )

    async def list_files(self) -> AsyncIterator[SourceFile]:  # type: ignore[override]
        page_token: str | None = None
        while True:
            result = await asyncio.to_thread(self._list_page, page_token)
            for f in result.get("files", []):
                mime: str = f.get("mimeType", "")
                _, export_ext = _EXPORT_MAP.get(mime, (None, None))
                effective_ext = export_ext or (mimetypes.guess_extension(mime) or "")
                if effective_ext not in SUPPORTED_EXTENSIONS:
                    continue
                modified_str: str | None = f.get("modifiedTime")
                yield SourceFile(
                    external_id=f["id"],
                    title=f["name"],
                    path=f["name"],
                    source_url=f.get("webViewLink"),
                    mime_type=_EXPORT_MAP.get(mime, (mime,))[0],
                    checksum=f.get("md5Checksum"),
                    version=f.get("md5Checksum"),
                    size_bytes=int(f["size"]) if f.get("size") else None,
                    modified_at=(
                        datetime.fromisoformat(modified_str.replace("Z", "+00:00"))
                        if modified_str
                        else None
                    ),
                    acl=[SourceACL(principal_type="group", principal_id="everyone", permission="read")],
                )
            page_token = result.get("nextPageToken")
            if not page_token:
                break

    async def download_file(self, source_file: SourceFile) -> Path:
        from googleapiclient.http import MediaIoBaseDownload  # type: ignore[import-untyped]

        file_meta = await asyncio.to_thread(
            lambda: self._service.files()
            .get(fileId=source_file.external_id, fields="mimeType", supportsAllDrives=True)
            .execute()
        )
        native_mime: str = file_meta.get("mimeType", "")
        _, export_ext = _EXPORT_MAP.get(native_mime, (None, None))
        suffix = export_ext or (mimetypes.guess_extension(native_mime) or ".bin")

        request = self._get_media_request(source_file.external_id, native_mime)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            def _download() -> None:
                downloader = MediaIoBaseDownload(tmp, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()

            await asyncio.to_thread(_download)
        finally:
            tmp.close()

        return Path(tmp.name)

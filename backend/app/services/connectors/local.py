import hashlib
import mimetypes
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings
from app.services.connectors.base import DocumentConnector, SourceACL, SourceFile
from app.services.ingestion.extractor import TextExtractor


SUPPORTED_EXTENSIONS = TextExtractor.supported_extensions
MAX_LOCAL_FILE_SIZE_BYTES = 50 * 1024 * 1024


class LocalConnector(DocumentConnector):
    def __init__(self, root_path: str) -> None:
        configured_root = Path(settings.local_connector_root).expanduser().resolve()
        requested_root = Path(root_path).expanduser().resolve()
        if configured_root not in requested_root.parents and requested_root != configured_root:
            raise ValueError(
                "Local connector root_path must stay inside LOCAL_CONNECTOR_ROOT. "
                "Use LOCAL_CONNECTOR_ROOT to change the allowed base folder."
            )
        self.root_path = requested_root

    async def list_files(self) -> AsyncIterator[SourceFile]:
        if not self.root_path.exists():
            raise FileNotFoundError(f"Local connector path does not exist: {self.root_path}")
        if not self.root_path.is_dir():
            raise NotADirectoryError(f"Local connector path is not a directory: {self.root_path}")

        for path in sorted(self.root_path.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            stat = path.stat()
            if stat.st_size > MAX_LOCAL_FILE_SIZE_BYTES:
                continue
            checksum = _sha256_file(path)
            relative = path.relative_to(self.root_path).as_posix()
            yield SourceFile(
                external_id=relative,
                title=path.name,
                path=relative,
                source_url=path.as_uri(),
                mime_type=mimetypes.guess_type(path.name)[0],
                checksum=checksum,
                version=checksum,
                size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                acl=[SourceACL(principal_type="group", principal_id="everyone", permission="read")],
            )

    async def download_file(self, source_file: SourceFile) -> Path:
        path = (self.root_path / source_file.external_id).resolve()
        if self.root_path not in path.parents and path != self.root_path:
            raise ValueError("Invalid local connector path traversal attempt")
        if not path.is_file():
            raise FileNotFoundError(f"Source file not found: {source_file.external_id}")
        return path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

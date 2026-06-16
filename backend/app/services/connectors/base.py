from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class SourceACL:
    principal_type: str
    principal_id: str
    permission: str = "read"
    inherited: bool = False
    source_acl_id: str | None = None


@dataclass(frozen=True)
class SourceFile:
    external_id: str
    title: str
    path: str
    source_url: str | None
    mime_type: str | None
    checksum: str | None
    version: str | None
    size_bytes: int | None
    modified_at: datetime | None
    acl: list[SourceACL] = field(default_factory=list)


class DocumentConnector(ABC):
    @abstractmethod
    def list_files(self) -> AsyncIterator[SourceFile]:
        ...

    @abstractmethod
    async def download_file(self, source_file: SourceFile) -> Path:
        ...

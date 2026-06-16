from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentRead(BaseModel):
    id: UUID
    tenant_id: str
    connector_id: UUID
    external_id: str
    title: str
    path: str
    source_url: str | None
    mime_type: str | None
    checksum: str | None
    version: str | None
    size_bytes: int | None
    source_modified_at: datetime | None
    deleted_at: datetime | None

    model_config = {"from_attributes": True}

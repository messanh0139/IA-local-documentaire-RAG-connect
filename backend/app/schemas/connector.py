from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


ConnectorType = Literal["local", "sharepoint", "google_drive"]


class ConnectorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: ConnectorType
    config: dict[str, Any] = Field(default_factory=dict)


class ConnectorRead(BaseModel):
    id: UUID
    tenant_id: str
    name: str
    type: str
    status: str
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SyncRequest(BaseModel):
    mode: Literal["foreground", "rq", "background"] = "background"


class SyncRunRead(BaseModel):
    id: UUID
    tenant_id: str
    connector_id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    files_seen: int
    files_indexed: int
    files_deleted: int
    error_message: str | None
    stats: dict[str, Any]

    model_config = {"from_attributes": True}


class ConnectorDetail(ConnectorRead):
    last_sync: SyncRunRead | None = None

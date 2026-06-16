from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.search import SourceCitation


class ConversationRead(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageRead(BaseModel):
    id: UUID
    role: str
    content: str
    citations: list[SourceCitation]
    created_at: datetime

    model_config = {"from_attributes": True}

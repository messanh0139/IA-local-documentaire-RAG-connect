from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, get_current_principal
from app.db.session import get_db_session
from app.models.chat_message import ChatMessage
from app.models.conversation import Conversation
from app.schemas.conversation import ChatMessageRead, ConversationRead
from app.schemas.search import SourceCitation

router = APIRouter()


@router.get("", response_model=list[ConversationRead])
async def list_conversations(
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> list[Conversation]:
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.tenant_id == principal.tenant_id,
            Conversation.user_id == principal.user_id,
        )
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> None:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    await db.delete(conversation)
    await db.commit()


@router.get("/{conversation_id}/messages", response_model=list[ChatMessageRead])
async def list_messages(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> list[ChatMessageRead]:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = list(result.scalars().all())

    return [
        ChatMessageRead(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            citations=[SourceCitation(**c) for c in (msg.citations_json or [])],
            created_at=msg.created_at,
        )
        for msg in messages
    ]

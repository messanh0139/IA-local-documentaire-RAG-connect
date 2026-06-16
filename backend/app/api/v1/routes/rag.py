from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, get_current_principal
from app.db.session import get_db_session
from app.models.chat_message import ChatMessage
from app.models.conversation import Conversation
from app.schemas.search import ChatRequest, ChatResponse, SearchRequest, SearchResponse
from app.services.rag.service import RagService

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> SearchResponse:
    return await RagService(db).search(payload, principal)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> ChatResponse:
    rag_response = await RagService(db).answer(payload, principal)

    # Retrieve or create conversation
    conversation: Conversation | None = None
    if payload.conversation_id:
        conversation = await db.get(Conversation, payload.conversation_id)
        if conversation is None or conversation.tenant_id != principal.tenant_id:
            conversation = None

    if conversation is None:
        title = payload.question[:60] + ("…" if len(payload.question) > 60 else "")
        conversation = Conversation(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            title=title,
        )
        db.add(conversation)
        await db.flush()
    else:
        conversation.updated_at = datetime.now(UTC)

    conversation_id = conversation.id

    db.add(ChatMessage(
        conversation_id=conversation_id,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        role="user",
        content=payload.question,
    ))
    db.add(ChatMessage(
        conversation_id=conversation_id,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        role="assistant",
        content=rag_response.answer,
        citations_json=[c.model_dump(mode="json") for c in rag_response.citations],
    ))

    return ChatResponse(
        answer=rag_response.answer,
        citations=rag_response.citations,
        conversation_id=conversation_id,
    )

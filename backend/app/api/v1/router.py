from fastapi import APIRouter

from app.api.v1.routes import auth, connectors, conversations, documents, rag, system

api_router = APIRouter()
api_router.include_router(system.router, tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(connectors.router, prefix="/connectors", tags=["connectors"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(rag.router, tags=["rag"])

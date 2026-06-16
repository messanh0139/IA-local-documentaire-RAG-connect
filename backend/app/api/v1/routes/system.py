from fastapi import APIRouter, Depends
from qdrant_client import QdrantClient
from redis import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import Principal, get_current_principal
from app.db.session import get_db_session
from app.models.connector import Connector
from app.models.document import Chunk, Document
from app.models.sync_run import SyncRun
from app.schemas.system import ComponentHealth, DashboardStats, ReadinessResponse

router = APIRouter()


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", response_model=ReadinessResponse)
async def ready(db: AsyncSession = Depends(get_db_session)) -> ReadinessResponse:
    components: dict[str, ComponentHealth] = {}

    try:
        await db.execute(text("select 1"))
        components["postgres"] = ComponentHealth(status="ok")
    except Exception as exc:
        components["postgres"] = ComponentHealth(status="error", detail=str(exc))

    try:
        QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None).get_collections()
        components["qdrant"] = ComponentHealth(status="ok")
    except Exception as exc:
        components["qdrant"] = ComponentHealth(status="error", detail=str(exc))

    try:
        Redis.from_url(settings.redis_url).ping()
        components["redis"] = ComponentHealth(status="ok")
    except Exception as exc:
        components["redis"] = ComponentHealth(status="error", detail=str(exc))

    status = "ok" if all(item.status == "ok" for item in components.values()) else "degraded"
    return ReadinessResponse(status=status, components=components)


@router.get("/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats(
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> DashboardStats:
    connectors = await db.scalar(
        select(func.count()).select_from(Connector).where(Connector.tenant_id == principal.tenant_id)
    )
    active_documents = await db.scalar(
        select(func.count())
        .select_from(Document)
        .where(Document.tenant_id == principal.tenant_id, Document.deleted_at.is_(None))
    )
    deleted_documents = await db.scalar(
        select(func.count())
        .select_from(Document)
        .where(Document.tenant_id == principal.tenant_id, Document.deleted_at.is_not(None))
    )
    chunks = await db.scalar(
        select(func.count()).select_from(Chunk).where(Chunk.tenant_id == principal.tenant_id)
    )
    sync_runs = await db.scalar(
        select(func.count()).select_from(SyncRun).where(SyncRun.tenant_id == principal.tenant_id)
    )
    last_sync = await db.scalar(
        select(SyncRun.status)
        .where(SyncRun.tenant_id == principal.tenant_id)
        .order_by(SyncRun.started_at.desc())
        .limit(1)
    )

    return DashboardStats(
        connectors=connectors or 0,
        active_documents=active_documents or 0,
        deleted_documents=deleted_documents or 0,
        chunks=chunks or 0,
        sync_runs=sync_runs or 0,
        last_sync_status=last_sync,
    )

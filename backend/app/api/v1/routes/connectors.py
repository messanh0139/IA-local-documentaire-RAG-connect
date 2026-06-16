from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, get_current_principal
from app.db.session import get_db_session
from app.models.connector import Connector
from app.models.document import Chunk, Document, DocumentACL
from app.models.sync_run import SyncRun
from app.models.tenant import Tenant
from app.schemas.connector import ConnectorCreate, ConnectorDetail, ConnectorRead, SyncRequest, SyncRunRead
from app.services.ingestion.pipeline import IngestionPipeline
from app.services.vector.qdrant_store import QdrantVectorStore
from app.workers.queue import enqueue_sync

router = APIRouter()


@router.post("", response_model=ConnectorRead, status_code=status.HTTP_201_CREATED)
async def create_connector(
    payload: ConnectorCreate,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> Connector:
    tenant = await db.get(Tenant, principal.tenant_id)
    if tenant is None:
        tenant = Tenant(id=principal.tenant_id, name=principal.tenant_id)
        db.add(tenant)

    connector = Connector(
        tenant_id=principal.tenant_id,
        name=payload.name,
        type=payload.type,
        config=payload.config,
    )
    db.add(connector)
    await db.commit()
    await db.refresh(connector)
    return connector


@router.get("", response_model=list[ConnectorRead])
async def list_connectors(
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> list[Connector]:
    result = await db.execute(
        select(Connector)
        .where(Connector.tenant_id == principal.tenant_id)
        .order_by(Connector.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{connector_id}", response_model=ConnectorDetail)
async def get_connector(
    connector_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> ConnectorDetail:
    connector = await db.get(Connector, connector_id)
    if connector is None or connector.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    last_sync = await db.scalar(
        select(SyncRun)
        .where(SyncRun.connector_id == connector.id, SyncRun.tenant_id == principal.tenant_id)
        .order_by(SyncRun.started_at.desc())
        .limit(1)
    )
    detail = ConnectorDetail.model_validate(connector)
    detail.last_sync = SyncRunRead.model_validate(last_sync) if last_sync else None
    return detail


@router.get("/{connector_id}/sync-runs", response_model=list[SyncRunRead])
async def list_connector_sync_runs(
    connector_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> list[SyncRun]:
    connector = await db.get(Connector, connector_id)
    if connector is None or connector.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    result = await db.execute(
        select(SyncRun)
        .where(SyncRun.connector_id == connector_id, SyncRun.tenant_id == principal.tenant_id)
        .order_by(SyncRun.started_at.desc())
        .limit(20)
    )
    return list(result.scalars().all())


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(
    connector_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> None:
    connector = await db.get(Connector, connector_id)
    if connector is None or connector.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    # Nettoyer les documents, chunks et vecteurs avant de supprimer le connecteur
    docs_result = await db.execute(
        select(Document).where(
            Document.connector_id == connector_id,
            Document.tenant_id == principal.tenant_id,
        )
    )
    vector_store = QdrantVectorStore()
    for doc in docs_result.scalars().all():
        vector_store.delete_document(doc.tenant_id, doc.id)
        await db.execute(delete(DocumentACL).where(DocumentACL.document_id == doc.id))
        await db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    await db.execute(
        delete(Document).where(
            Document.connector_id == connector_id,
            Document.tenant_id == principal.tenant_id,
        )
    )
    await db.execute(delete(SyncRun).where(SyncRun.connector_id == connector_id))
    await db.delete(connector)
    await db.commit()


@router.post("/{connector_id}/sync", response_model=SyncRunRead)
async def sync_connector(
    connector_id: UUID,
    payload: SyncRequest,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> SyncRunRead:
    connector = await db.get(Connector, connector_id)
    if connector is None or connector.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    if payload.mode == "rq":
        sync_run = await IngestionPipeline(db).create_sync_run(connector)
        await db.commit()
        enqueue_sync(str(sync_run.id), str(connector.id))
        return SyncRunRead.model_validate(sync_run)

    sync_run = await IngestionPipeline(db).sync_connector(connector)
    return SyncRunRead.model_validate(sync_run)

import asyncio
from uuid import UUID

from app.db.session import AsyncSessionLocal
from app.models.connector import Connector
from app.models.sync_run import SyncRun
from app.services.ingestion.pipeline import IngestionPipeline


def sync_connector_task(sync_run_id: str, connector_id: str) -> None:
    asyncio.run(_sync_connector_task(sync_run_id, connector_id))


async def _sync_connector_task(sync_run_id: str, connector_id: str) -> None:
    async with AsyncSessionLocal() as db:
        connector = await db.get(Connector, UUID(connector_id))
        sync_run = await db.get(SyncRun, UUID(sync_run_id))
        if connector is None or sync_run is None:
            return
        await IngestionPipeline(db).sync_connector(connector, sync_run=sync_run)

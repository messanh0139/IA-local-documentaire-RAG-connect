import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connector import Connector
from app.models.document import Chunk, Document, DocumentACL
from app.models.sync_run import SyncRun
from app.models.tenant import Tenant
from app.services.connectors.base import SourceACL, SourceFile
from app.services.connectors.factory import build_connector
from app.services.embeddings.factory import build_embedding_provider
from app.services.ingestion.chunker import SimpleTextChunker
from app.services.ingestion.extractor import TextExtractionError, TextExtractor, UnsupportedDocumentTypeError
from app.services.vector.qdrant_store import QdrantVectorStore, VectorPoint

UPLOAD_CONNECTOR_NAME = "Fichiers uploadés"
UPLOAD_DIR = Path("/data/uploads")


class IngestionPipeline:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.extractor = TextExtractor()
        self.chunker = SimpleTextChunker()
        self.embeddings = build_embedding_provider()
        self.vector_store = QdrantVectorStore()

    async def ingest_upload(self, file_path: Path, filename: str, tenant_id: str, user_id: str) -> Document:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        connector = await self._get_or_create_upload_connector(tenant_id)
        checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()
        source_file = SourceFile(
            external_id=f"upload:{filename}:{checksum}",
            title=filename,
            path=str(file_path),
            source_url=None,
            mime_type=None,
            checksum=checksum,
            version=checksum,
            size_bytes=file_path.stat().st_size,
            modified_at=datetime.now(UTC),
            acl=[SourceACL(principal_type="public", principal_id="everyone", permission="read")],
        )
        document = await self._get_document(connector, source_file.external_id)
        document = await self._upsert_document(connector, source_file, document)
        pages = self.extractor.extract(file_path)
        chunks = self.chunker.split_pages(pages)
        await self._replace_chunks(document, source_file, chunks)
        await self.db.commit()
        return document

    async def _get_or_create_upload_connector(self, tenant_id: str) -> Connector:
        result = await self.db.execute(
            select(Connector).where(
                Connector.tenant_id == tenant_id,
                Connector.type == "local",
                Connector.name == UPLOAD_CONNECTOR_NAME,
            )
        )
        connector = result.scalar_one_or_none()
        if connector is None:
            tenant = await self.db.get(Tenant, tenant_id)
            if tenant is None:
                tenant = Tenant(id=tenant_id, name=tenant_id)
                self.db.add(tenant)
            connector = Connector(
                tenant_id=tenant_id,
                name=UPLOAD_CONNECTOR_NAME,
                type="local",
                config={"root_path": str(UPLOAD_DIR)},
            )
            self.db.add(connector)
            await self.db.flush()
        return connector

    async def create_sync_run(self, connector: Connector) -> SyncRun:
        sync_run = SyncRun(
            tenant_id=connector.tenant_id,
            connector_id=connector.id,
            status="running",
            started_at=datetime.now(UTC),
        )
        self.db.add(sync_run)
        await self.db.flush()
        return sync_run

    async def sync_connector(self, connector: Connector, sync_run: SyncRun | None = None) -> SyncRun:
        sync_run = sync_run or await self.create_sync_run(connector)
        connector_impl = build_connector(connector)
        seen_external_ids: set[str] = set()

        try:
            async for source_file in connector_impl.list_files():
                seen_external_ids.add(source_file.external_id)
                sync_run.files_seen += 1
                document = await self._get_document(connector, source_file.external_id)
                if self._needs_reindex(document, source_file):
                    try:
                        document = await self._upsert_document(connector, source_file, document)
                        path = await connector_impl.download_file(source_file)
                        pages = self.extractor.extract(path)
                        chunks = self.chunker.split_pages(pages)
                        await self._replace_chunks(document, source_file, chunks)
                        sync_run.files_indexed += 1
                    except (UnsupportedDocumentTypeError, TextExtractionError, OSError, ValueError) as exc:
                        sync_run.stats = self._append_file_error(
                            sync_run.stats,
                            source_file.path,
                            str(exc),
                        )

            sync_run.files_deleted = await self._mark_deleted_missing(connector, seen_external_ids)
            sync_run.status = "succeeded"
        except Exception as exc:
            sync_run.status = "failed"
            sync_run.error_message = str(exc)
            raise
        finally:
            sync_run.finished_at = datetime.now(UTC)
            await self.db.commit()

        return sync_run

    async def _get_document(self, connector: Connector, external_id: str) -> Document | None:
        result = await self.db.execute(
            select(Document).where(
                Document.tenant_id == connector.tenant_id,
                Document.connector_id == connector.id,
                Document.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    def _needs_reindex(self, document: Document | None, source_file: SourceFile) -> bool:
        if document is None:
            return True
        if document.deleted_at is not None:
            return True
        if document.acl_hash != self._acl_hash(source_file.acl):
            return True
        if document.checksum and source_file.checksum:
            return document.checksum != source_file.checksum
        return document.version != source_file.version

    async def _upsert_document(
        self,
        connector: Connector,
        source_file: SourceFile,
        document: Document | None,
    ) -> Document:
        if document is None:
            document = Document(
                tenant_id=connector.tenant_id,
                connector_id=connector.id,
                external_id=source_file.external_id,
                title=source_file.title,
                path=source_file.path,
            )
            self.db.add(document)

        document.title = source_file.title
        document.path = source_file.path
        document.source_url = source_file.source_url
        document.mime_type = source_file.mime_type
        document.checksum = source_file.checksum
        document.version = source_file.version
        document.size_bytes = source_file.size_bytes
        document.source_modified_at = source_file.modified_at
        document.deleted_at = None
        document.acl_hash = self._acl_hash(source_file.acl)
        document.metadata_ = {"source": connector.type}
        await self.db.flush()

        await self.db.execute(delete(DocumentACL).where(DocumentACL.document_id == document.id))
        for acl in source_file.acl:
            self.db.add(
                DocumentACL(
                    document_id=document.id,
                    tenant_id=connector.tenant_id,
                    principal_type=acl.principal_type,
                    principal_id=acl.principal_id,
                    permission=acl.permission,
                    inherited=acl.inherited,
                    source_acl_id=acl.source_acl_id,
                )
            )
        await self.db.flush()
        return document

    async def _replace_chunks(self, document: Document, source_file: SourceFile, chunks) -> None:
        self.vector_store.delete_document(document.tenant_id, document.id)
        await self.db.execute(delete(Chunk).where(Chunk.document_id == document.id))
        await self.db.flush()

        texts = [chunk.text for chunk in chunks]
        vectors = await self.embeddings.embed_texts(texts) if texts else []
        acl_payload = self._acl_payload(source_file.acl)

        points: list[VectorPoint] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk_id = uuid4()
            point_id = str(uuid4())
            db_chunk = Chunk(
                id=chunk_id,
                tenant_id=document.tenant_id,
                document_id=document.id,
                ordinal=chunk.ordinal,
                page=chunk.page,
                text_hash=hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
                token_count=len(chunk.text.split()),
                qdrant_point_id=point_id,
            )
            self.db.add(db_chunk)
            points.append(
                VectorPoint(
                    point_id=point_id,
                    vector=vector,
                    payload={
                        "tenant_id": document.tenant_id,
                        "document_id": str(document.id),
                        "chunk_id": str(chunk_id),
                        "connector_id": str(document.connector_id),
                        "title": document.title,
                        "path": document.path,
                        "source_url": document.source_url,
                        "page": chunk.page,
                        "chunk_text": chunk.text,
                        "checksum": document.checksum,
                        **acl_payload,
                    },
                )
            )

        self.vector_store.upsert(points)
        await self.db.flush()

    async def _mark_deleted_missing(self, connector: Connector, seen_external_ids: set[str]) -> int:
        stmt = select(Document).where(
            Document.tenant_id == connector.tenant_id,
            Document.connector_id == connector.id,
            Document.deleted_at.is_(None),
        )
        if seen_external_ids:
            stmt = stmt.where(Document.external_id.not_in(seen_external_ids))
        result = await self.db.execute(stmt)
        deleted_count = 0
        for document in result.scalars().all():
            document.deleted_at = datetime.now(UTC)
            self.vector_store.delete_document(document.tenant_id, document.id)
            await self.db.execute(delete(Chunk).where(Chunk.document_id == document.id))
            deleted_count += 1
        return deleted_count

    def _acl_payload(self, acl_entries: list[SourceACL]) -> dict:
        return {
            "is_public": any(entry.principal_type == "public" for entry in acl_entries),
            "allowed_user_ids": [
                entry.principal_id for entry in acl_entries if entry.principal_type == "user"
            ],
            "allowed_group_ids": [
                entry.principal_id for entry in acl_entries if entry.principal_type == "group"
            ],
        }

    def _acl_hash(self, acl_entries: list[SourceACL]) -> str:
        serialized = "|".join(
            sorted(
                f"{entry.principal_type}:{entry.principal_id}:{entry.permission}"
                for entry in acl_entries
            )
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _append_file_error(self, stats: dict | None, path: str, error: str) -> dict:
        next_stats = dict(stats or {})
        errors = list(next_stats.get("file_errors") or [])
        errors.append({"path": path, "error": error[:1000]})
        next_stats["file_errors"] = errors[-50:]
        next_stats["files_failed"] = len(errors)
        return next_stats

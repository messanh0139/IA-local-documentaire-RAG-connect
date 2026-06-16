from dataclasses import dataclass
from uuid import UUID

from qdrant_client import QdrantClient, models
import structlog

from app.core.config import settings
from app.core.security import Principal

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class VectorPoint:
    point_id: str
    vector: list[float]
    payload: dict


@dataclass(frozen=True)
class VectorSearchHit:
    point_id: str
    score: float
    payload: dict


class QdrantVectorStore:
    _ready_collections: set[str] = set()

    def __init__(self) -> None:
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
        self.collection_name = settings.qdrant_collection

    def ensure_collection(self) -> None:
        if self.collection_name in QdrantVectorStore._ready_collections:
            return

        existing = self.client.get_collections().collections
        collection_exists = any(collection.name == self.collection_name for collection in existing)
        if not collection_exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=settings.embedding_dimensions,
                    distance=models.Distance.COSINE,
                ),
            )
        self._create_payload_indexes()
        QdrantVectorStore._ready_collections.add(self.collection_name)

    def _create_payload_indexes(self) -> None:
        indexed_fields = {
            "tenant_id": models.PayloadSchemaType.KEYWORD,
            "document_id": models.PayloadSchemaType.KEYWORD,
            "allowed_user_ids": models.PayloadSchemaType.KEYWORD,
            "allowed_group_ids": models.PayloadSchemaType.KEYWORD,
            "is_public": models.PayloadSchemaType.BOOL,
        }
        for field_name, schema in indexed_fields.items():
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema,
                )
            except Exception as exc:
                logger.debug(
                    "qdrant_payload_index_skipped",
                    field_name=field_name,
                    error=str(exc),
                )

    def upsert(self, points: list[VectorPoint]) -> None:
        if not points:
            return
        self.ensure_collection()
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(id=point.point_id, vector=point.vector, payload=point.payload)
                for point in points
            ],
        )

    def delete_document(self, tenant_id: str, document_id: UUID) -> None:
        self.ensure_collection()
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="tenant_id",
                            match=models.MatchValue(value=tenant_id),
                        ),
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=str(document_id)),
                        ),
                    ]
                )
            ),
        )

    def search(
        self,
        query_vector: list[float],
        principal: Principal,
        limit: int,
    ) -> list[VectorSearchHit]:
        self.ensure_collection()
        acl_conditions: list[models.Condition] = [
            models.FieldCondition(key="is_public", match=models.MatchValue(value=True)),
            models.FieldCondition(
                key="allowed_user_ids",
                match=models.MatchAny(any=[principal.user_id]),
            ),
        ]
        if principal.group_ids:
            acl_conditions.append(
                models.FieldCondition(
                    key="allowed_group_ids",
                    match=models.MatchAny(any=list(principal.group_ids)),
                )
            )

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="tenant_id",
                        match=models.MatchValue(value=principal.tenant_id),
                    )
                ],
                should=acl_conditions,
            ),
            limit=limit,
            with_payload=True,
        )
        return [
            VectorSearchHit(
                point_id=str(hit.id),
                score=float(hit.score),
                payload=dict(hit.payload or {}),
            )
            for hit in response.points
        ]

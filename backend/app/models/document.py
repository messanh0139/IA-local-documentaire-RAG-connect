from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "connector_id", "external_id", name="uq_document_source"),
    )

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    connector_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("connectors.id", ondelete="CASCADE"),
        index=True,
    )
    external_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    checksum: Mapped[str | None] = mapped_column(String(128))
    version: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    source_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    acl_hash: Mapped[str | None] = mapped_column(String(128))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)

    tenant = relationship("Tenant", back_populates="documents")
    connector = relationship("Connector", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    acls = relationship("DocumentACL", back_populates="document", cascade="all, delete-orphan")


class DocumentACL(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "document_acls"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "principal_type",
            "principal_id",
            "permission",
            name="uq_document_acl_principal",
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    principal_type: Mapped[str] = mapped_column(String(40), nullable=False)
    principal_id: Mapped[str] = mapped_column(String(255), nullable=False)
    permission: Mapped[str] = mapped_column(String(40), default="read", nullable=False)
    inherited: Mapped[bool] = mapped_column(default=False, nullable=False)
    source_acl_id: Mapped[str | None] = mapped_column(String(512))

    document = relationship("Document", back_populates="acls")


class Chunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("document_id", "ordinal", name="uq_chunk_document_ordinal"),)

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer)
    text_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    qdrant_point_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    document = relationship("Document", back_populates="chunks")

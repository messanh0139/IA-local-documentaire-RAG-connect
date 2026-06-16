from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Connector(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "connectors"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    secret_ref: Mapped[str | None] = mapped_column(String(255))

    tenant = relationship("Tenant", back_populates="connectors")
    documents = relationship("Document", back_populates="connector")

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Group(Base, TimestampMixin):
    __tablename__ = "groups"
    __table_args__ = (UniqueConstraint("tenant_id", "external_id", name="uq_group_tenant_external"),)

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))

    users = relationship("UserGroup", back_populates="group", cascade="all, delete-orphan")


class UserGroup(Base, TimestampMixin):
    __tablename__ = "user_groups"
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_user_group"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)

    user = relationship("User", back_populates="groups")
    group = relationship("Group", back_populates="users")

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.models.audit_log import AuditLog


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record(
        self,
        principal: Principal,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.db.add(
            AuditLog(
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata_=metadata or {},
            )
        )
        await self.db.flush()

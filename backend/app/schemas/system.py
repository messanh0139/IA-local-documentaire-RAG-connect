from pydantic import BaseModel


class ComponentHealth(BaseModel):
    status: str
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: str
    components: dict[str, ComponentHealth]


class DashboardStats(BaseModel):
    connectors: int
    active_documents: int
    deleted_documents: int
    chunks: int
    sync_runs: int
    last_sync_status: str | None

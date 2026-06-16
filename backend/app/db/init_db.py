import asyncio

from app.db.base import Base
from app.db.session import engine
from app.models import audit_log, chat_message, connector, conversation, document, group, sync_run, tenant, user  # noqa: F401


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    try:
        asyncio.run(init_db())
    except OSError as exc:
        raise SystemExit(
            "Database connection failed. Start PostgreSQL first with "
            "`docker compose up -d`, or run `scripts\\start-dev.ps1`. "
            f"Cause: {exc}"
        ) from exc

from redis import Redis
from rq import Queue

from app.core.config import settings

_redis: Redis | None = None
_queue: Queue | None = None


def get_queue() -> Queue:
    global _redis, _queue
    if _queue is None:
        _redis = Redis.from_url(settings.redis_url)
        _queue = Queue("docmind", connection=_redis)
    return _queue


def enqueue_sync(sync_run_id: str, connector_id: str) -> None:
    get_queue().enqueue(
        "app.workers.tasks.sync_connector_task",
        sync_run_id,
        connector_id,
        job_timeout="30m",
    )

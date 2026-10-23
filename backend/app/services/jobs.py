"""Enqueue background jobs on the arq worker, with an in-process fallback.

In production the `worker` container processes jobs. In local development, if
Redis/worker isn't running (or INLINE_JOBS=true), jobs run inside the API process.
"""
import asyncio
import logging
import os

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings

log = logging.getLogger(__name__)
_pool: ArqRedis | None = None
_background: set[asyncio.Task] = set()
INLINE = os.getenv("INLINE_JOBS", "false").lower() == "true"


async def _get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    return _pool


async def _run_inline(name: str, *args) -> None:
    from app.services import ingestion

    func = {"ingest_document": ingestion.ingest_document, "embed_faq": ingestion.embed_faq}[name]
    task = asyncio.create_task(func(*args))
    _background.add(task)
    task.add_done_callback(_background.discard)


async def enqueue(name: str, *args) -> None:
    if INLINE:
        await _run_inline(name, *args)
        return
    try:
        pool = await _get_pool()
        await pool.enqueue_job(name, *args)
    except Exception as exc:
        log.warning("Queue unavailable (%s); running %s in-process", exc, name)
        await _run_inline(name, *args)

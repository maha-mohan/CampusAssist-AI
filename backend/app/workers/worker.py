"""arq background worker.

Run with:  arq app.workers.worker.WorkerSettings
"""
import logging
from datetime import datetime, timedelta, timezone

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import delete

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import setup_logging
from app.models import ChatSession
from app.services import ingestion

setup_logging()
log = logging.getLogger("worker")


async def ingest_document(ctx, document_id: int):
    await ingestion.ingest_document(document_id)


async def embed_faq(ctx, faq_id: int):
    await ingestion.embed_faq(faq_id)


async def purge_old_chats(ctx):
    """Data retention (DPDP-friendly): delete chat sessions older than CHAT_RETENTION_DAYS."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.CHAT_RETENTION_DAYS)
    async with SessionLocal() as db:
        res = await db.execute(delete(ChatSession).where(ChatSession.last_active_at < cutoff))
        await db.commit()
    log.info("Purged %s old chat sessions", res.rowcount)


class WorkerSettings:
    functions = [ingest_document, embed_faq]
    cron_jobs = [cron(purge_old_chats, hour={21}, minute={30})]  # 03:00 IST daily
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 4
    job_timeout = 900

"""Public misc endpoints: health, widget config, document download."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import QUICK_REPLIES
from app.core.database import get_db
from app.core.redis import get_redis
from app.models import Document
from app.services import storage

router = APIRouter(tags=["public"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    status = {"api": "ok", "llm": "mock" if settings.is_mock_llm else "openai"}
    try:
        await db.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception:
        status["database"] = "error"
    try:
        await get_redis().ping()
        status["redis"] = "ok"
    except Exception:
        status["redis"] = "unavailable"
    return status


@router.get("/config")
async def widget_config():
    return {
        "college_name": settings.COLLEGE_NAME,
        "academic_year": settings.CURRENT_ACADEMIC_YEAR,
        "quick_replies": QUICK_REPLIES,
        "max_message_chars": settings.MAX_MESSAGE_CHARS,
    }


@router.get("/documents/{document_id}/file")
async def document_file(document_id: int, db: AsyncSession = Depends(get_db)):
    """Lets the widget link to the source document an answer came from. Only active documents."""
    doc = await db.get(Document, document_id)
    if not doc or doc.status != "active":
        raise HTTPException(404, "Document not available")
    if doc.source_url and not doc.file_path:
        return RedirectResponse(doc.source_url)
    if storage.is_s3_path(doc.file_path):
        data = await storage.read(doc.file_path)
        if data is None:
            raise HTTPException(404, "File missing")
        name = (doc.filename or "document").replace('"', "")
        return Response(data, media_type=doc.mime_type or "application/octet-stream",
                        headers={"Content-Disposition": f'inline; filename="{name}"'})
    path = Path(doc.file_path or "")
    if not path.is_file():
        raise HTTPException(404, "File missing")
    return FileResponse(path, filename=doc.filename or path.name, media_type=doc.mime_type or None,
                        content_disposition_type="inline")

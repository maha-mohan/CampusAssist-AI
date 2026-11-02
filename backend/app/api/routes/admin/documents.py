"""Knowledge base management: documents (upload / URL), chunks preview, FAQs."""
import re
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import audit, get_current_user, require_content_admin
from app.core.config import settings
from app.core.constants import DOC_TYPES
from app.core.database import get_db
from app.core.redis import cache_clear_prefix
from app.models import FAQ, Chunk, Document, User
from app.schemas.schemas import ChunkOut, DocumentOut, DocumentUpdate, FAQIn, FAQOut, Page, UrlIngestIn
from app.services.ingestion import ALLOWED_EXTENSIONS
from app.services import storage
from app.services.jobs import enqueue

router = APIRouter(tags=["admin-knowledge"])

MIME = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown", ".html": "text/html",
        ".htm": "text/html", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
MAGIC = {".pdf": b"%PDF", ".docx": b"PK"}


def _scope_check(user: User, department_id: int | None):
    """Department admins may only manage content for their own department."""
    if user.role == "dept_admin" and department_id not in (None, user.department_id):
        raise HTTPException(403, "You can only manage your department's content")


@router.get("/meta/doc-types")
async def doc_types(_: User = Depends(get_current_user)):
    return DOC_TYPES


# ---- Documents -------------------------------------------------------------
@router.get("/documents", response_model=Page)
async def list_documents(
    q: str | None = None, status: str | None = None, doc_type: str | None = None,
    department_id: int | None = None, academic_year: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    stmt = select(Document)
    if q:
        stmt = stmt.where(or_(Document.title.ilike(f"%{q}%"), Document.filename.ilike(f"%{q}%")))
    if status:
        stmt = stmt.where(Document.status == status)
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    if department_id:
        stmt = stmt.where(Document.department_id == department_id)
    if academic_year:
        stmt = stmt.where(Document.academic_year == academic_year)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.execute(stmt.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return Page(items=[DocumentOut.model_validate(r) for r in rows], total=total or 0, page=page, page_size=page_size)


@router.post("/documents/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(""),
    doc_type: str = Form("general"),
    department_id: int | None = Form(None),
    academic_year: str | None = Form(None),
    valid_from: date | None = Form(None),
    valid_to: date | None = Form(None),
    replaces_document_id: int | None = Form(None),
    user: User = Depends(require_content_admin),
    db: AsyncSession = Depends(get_db),
):
    _scope_check(user, department_id)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {settings.MAX_UPLOAD_MB} MB)")
    if ext in MAGIC and not data.startswith(MAGIC[ext]):
        raise HTTPException(400, "File content doesn't match its extension")

    safe = re.sub(r"[^\w.\-]", "_", file.filename or f"file{ext}")[:120]
    stored = await storage.save(f"{uuid.uuid4().hex[:12]}_{safe}", data, MIME.get(ext))

    doc = Document(
        title=title.strip() or Path(file.filename).stem.replace("_", " "), filename=file.filename,
        file_path=stored, mime_type=MIME.get(ext), doc_type=doc_type if doc_type in DOC_TYPES else "general",
        department_id=department_id, academic_year=academic_year or None, valid_from=valid_from, valid_to=valid_to,
        status="pending", uploaded_by=user.id,
    )
    db.add(doc)
    if replaces_document_id:  # new version of a circular / fee sheet → archive the old one
        old = await db.get(Document, replaces_document_id)
        if old:
            old.status = "archived"
    await db.flush()
    await audit(db, user, "upload", "document", doc.id, {"title": doc.title})
    await db.commit()
    await db.refresh(doc)
    await enqueue("ingest_document", doc.id)
    return doc


@router.post("/documents/url", response_model=DocumentOut, status_code=201)
async def ingest_url(body: UrlIngestIn, user: User = Depends(require_content_admin), db: AsyncSession = Depends(get_db)):
    _scope_check(user, body.department_id)
    doc = Document(title=body.title or body.url, source_url=body.url, doc_type=body.doc_type,
                   department_id=body.department_id, academic_year=body.academic_year, status="pending",
                   uploaded_by=user.id)
    db.add(doc)
    await db.flush()
    await audit(db, user, "add_url", "document", doc.id, {"url": body.url})
    await db.commit()
    await db.refresh(doc)
    await enqueue("ingest_document", doc.id)
    return doc


@router.get("/documents/{doc_id}", response_model=DocumentOut)
async def get_document(doc_id: int, _: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/documents/{doc_id}/chunks", response_model=list[ChunkOut])
async def document_chunks(doc_id: int, _: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.chunk_index))).scalars().all()


@router.patch("/documents/{doc_id}", response_model=DocumentOut)
async def update_document(doc_id: int, body: DocumentUpdate, user: User = Depends(require_content_admin),
                          db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    _scope_check(user, doc.department_id)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(doc, k, v)
    await audit(db, user, "update", "document", doc.id, {k: str(v) for k, v in data.items()})
    await db.commit()
    await db.refresh(doc)
    await cache_clear_prefix("ans")
    return doc


@router.post("/documents/{doc_id}/reprocess", response_model=DocumentOut)
async def reprocess_document(doc_id: int, user: User = Depends(require_content_admin), db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    _scope_check(user, doc.department_id)
    doc.status = "pending"
    await db.commit()
    await db.refresh(doc)
    await enqueue("ingest_document", doc.id)
    return doc


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: int, user: User = Depends(require_content_admin), db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    _scope_check(user, doc.department_id)
    if doc.file_path:
        await storage.delete(doc.file_path)
    await db.delete(doc)
    await audit(db, user, "delete", "document", doc_id, {"title": doc.title})
    await db.commit()
    await cache_clear_prefix("ans")


# ---- FAQs ------------------------------------------------------------------
@router.get("/faqs", response_model=list[FAQOut])
async def list_faqs(q: str | None = None, _: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(FAQ).order_by(FAQ.updated_at.desc())
    if q:
        stmt = stmt.where(or_(FAQ.question.ilike(f"%{q}%"), FAQ.answer.ilike(f"%{q}%")))
    return (await db.execute(stmt)).scalars().all()


@router.post("/faqs", response_model=FAQOut, status_code=201)
async def create_faq(body: FAQIn, user: User = Depends(require_content_admin), db: AsyncSession = Depends(get_db)):
    _scope_check(user, body.department_id)
    faq = FAQ(**body.model_dump())
    db.add(faq)
    await db.flush()
    await audit(db, user, "create", "faq", faq.id)
    await db.commit()
    await db.refresh(faq)
    await enqueue("embed_faq", faq.id)
    return faq


@router.put("/faqs/{faq_id}", response_model=FAQOut)
async def update_faq(faq_id: int, body: FAQIn, user: User = Depends(require_content_admin), db: AsyncSession = Depends(get_db)):
    faq = await db.get(FAQ, faq_id)
    if not faq:
        raise HTTPException(404, "FAQ not found")
    _scope_check(user, faq.department_id)
    question_changed = faq.question != body.question
    for k, v in body.model_dump().items():
        setattr(faq, k, v)
    await audit(db, user, "update", "faq", faq.id)
    await db.commit()
    await db.refresh(faq)
    if question_changed:
        await enqueue("embed_faq", faq.id)
    await cache_clear_prefix("ans")
    return faq


@router.delete("/faqs/{faq_id}", status_code=204)
async def delete_faq(faq_id: int, user: User = Depends(require_content_admin), db: AsyncSession = Depends(get_db)):
    faq = await db.get(FAQ, faq_id)
    if not faq:
        raise HTTPException(404, "FAQ not found")
    _scope_check(user, faq.department_id)
    await db.delete(faq)
    await audit(db, user, "delete", "faq", faq_id)
    await db.commit()
    await cache_clear_prefix("ans")

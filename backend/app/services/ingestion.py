"""Document ingestion: extract → clean → chunk → embed → store.

Supports PDF (with OCR fallback for scanned pages), DOCX, TXT/MD, HTML files
and web pages (URL). Runs inside the background worker.
"""
from __future__ import annotations

import io
import logging
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.redis import cache_clear_prefix
from app.models import Chunk, Document
from app.services.llm_client import get_llm

log = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".html", ".htm"}


@dataclass
class Page:
    number: int | None
    text: str


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def extract_pdf(path: Path) -> list[Page]:
    import fitz  # PyMuPDF

    pages: list[Page] = []
    with fitz.open(path) as pdf:
        for i, page in enumerate(pdf, start=1):
            text = _pdf_page_text(page)
            if len(text.strip()) < 40:  # likely scanned → OCR
                text = _ocr_page(page) or text
            pages.append(Page(i, text))
    return pages


def _pdf_page_text(page) -> str:
    """Text plus tables rendered as markdown (fee tables matter!)."""
    parts = []
    try:
        tables = page.find_tables()
        table_rects = [t.bbox for t in tables.tables]
        for t in tables.tables:
            md = t.to_markdown()
            if md:
                parts.append(md)
    except Exception:
        table_rects = []
    blocks = page.get_text("blocks")
    body = []
    for b in blocks:
        x0, y0, x1, y1, txt = b[0], b[1], b[2], b[3], b[4]
        inside = any(x0 >= r[0] - 1 and y0 >= r[1] - 1 and x1 <= r[2] + 1 and y1 <= r[3] + 1 for r in table_rects)
        if not inside:
            body.append(txt)
    return "\n".join(body + parts)


def _ocr_page(page) -> str:
    try:
        import pytesseract
        from PIL import Image

        pix = page.get_pixmap(dpi=250)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img, lang=_ocr_langs())
    except Exception as exc:
        log.warning("OCR failed: %s", exc)
        return ""


def _ocr_langs() -> str:
    try:
        import pytesseract

        available = set(pytesseract.get_languages(config=""))
        return "+".join(l for l in ("eng", "tam") if l in available) or "eng"
    except Exception:
        return "eng"


def extract_docx(path: Path) -> list[Page]:
    import docx

    d = docx.Document(str(path))
    parts = [p.text for p in d.paragraphs if p.text.strip()]
    for table in d.tables:
        rows = [[c.text.strip().replace("\n", " ") for c in row.cells] for row in table.rows]
        if rows:
            header = "| " + " | ".join(rows[0]) + " |"
            sep = "|" + "---|" * len(rows[0])
            body = ["| " + " | ".join(r) + " |" for r in rows[1:]]
            parts.append("\n".join([header, sep, *body]))
    return [Page(None, "\n".join(parts))]


def html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form", "iframe", "svg"]):
        tag.decompose()
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if cells:
                rows.append("| " + " | ".join(cells) + " |")
        table.replace_with("\n" + "\n".join(rows) + "\n")
    main = soup.find("main") or soup.find("article") or soup.body or soup
    return main.get_text("\n", strip=True)


def extract_file(path: Path) -> list[Page]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf(path)
    if ext == ".docx":
        return extract_docx(path)
    if ext in (".html", ".htm"):
        return [Page(None, html_to_text(path.read_text(encoding="utf-8", errors="ignore")))]
    return [Page(None, path.read_text(encoding="utf-8", errors="ignore"))]


async def fetch_url(url: str) -> tuple[str, list[Page]]:
    import httpx

    async with httpx.AsyncClient(timeout=30, follow_redirects=True,
                                 headers={"User-Agent": "CollegeHelpDeskBot/1.0"}) as client:
        r = await client.get(url)
        r.raise_for_status()
    ctype = r.headers.get("content-type", "")
    if "pdf" in ctype:
        tmp = settings.UPLOAD_DIR / "tmp_url.pdf"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(r.content)
        try:
            return "application/pdf", extract_pdf(tmp)
        finally:
            tmp.unlink(missing_ok=True)
    return "text/html", [Page(None, html_to_text(r.text))]


# ---------------------------------------------------------------------------
# Cleaning & chunking
# ---------------------------------------------------------------------------
PAGE_NO_RE = re.compile(r"^\s*(page\s*)?\d+\s*(of\s*\d+)?\s*$", re.I)


def clean_pages(pages: list[Page]) -> list[Page]:
    """Remove repeated headers/footers, page numbers and extra whitespace."""
    if len(pages) >= 3:
        counts = Counter()
        for p in pages:
            lines = {l.strip() for l in p.text.splitlines() if l.strip()}
            counts.update(lines)
        repeated = {l for l, c in counts.items() if c >= max(3, int(len(pages) * 0.6)) and len(l) < 120}
    else:
        repeated = set()
    out = []
    for p in pages:
        lines = []
        for line in p.text.splitlines():
            s = line.strip()
            if not s or s in repeated or PAGE_NO_RE.match(s):
                if not s and lines and lines[-1] != "":
                    lines.append("")
                continue
            lines.append(re.sub(r"[ \t]+", " ", s))
        text = "\n".join(lines).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        if text:
            out.append(Page(p.number, text))
    return out


def _splitter():
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    seps = ["\n\n", "\n| ", "\n", ". ", "। ", " ", ""]
    try:
        return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base", chunk_size=settings.CHUNK_SIZE_TOKENS,
            chunk_overlap=settings.CHUNK_OVERLAP_TOKENS, separators=seps)
    except Exception:  # tiktoken data not downloadable (offline) → ~4 chars per token
        return RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE_TOKENS * 4, chunk_overlap=settings.CHUNK_OVERLAP_TOKENS * 4, separators=seps)


TABLE_SEP_RE = re.compile(r"^:?-+:?$")


def contextualize_tables(text: str) -> str:
    """Rewrite markdown table rows as self-describing lines.

    A bare row like '| B.E. CSE | 1,20,000 |' is useless to search because its column
    names sit on another line. Each data row becomes 'Heading: Header: value; Header: value'
    so the row carries its own context.
    """
    out: list[str] = []
    heading = ""
    header: list[str] | None = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            heading = s.lstrip("#").strip()
        if not s.startswith("|"):
            header = None
            out.append(line)
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header is None:
            header = cells
        elif all(TABLE_SEP_RE.match(c) for c in cells):
            continue
        else:
            pairs = [f"{h}: {v}" for h, v in zip(header, cells) if h and v]
            row = "; ".join(pairs)
            out.append(f"{heading}: {row}" if heading else row)
    return "\n".join(out)


def chunk_pages(pages: list[Page]) -> list[tuple[int | None, str]]:
    splitter = _splitter()
    chunks: list[tuple[int | None, str]] = []
    for p in pages:
        for piece in splitter.split_text(contextualize_tables(p.text)):
            piece = piece.strip()
            if len(piece) >= 30:
                chunks.append((p.number, piece))
    return chunks


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
async def ingest_document(document_id: int) -> None:
    async with SessionLocal() as db:
        doc = await db.get(Document, document_id)
        if not doc:
            log.warning("Document %s not found", document_id)
            return
        doc.status, doc.error = "processing", None
        await db.commit()

        try:
            if doc.file_path:
                pages = extract_file(Path(doc.file_path))
            elif doc.source_url:
                mime, pages = await fetch_url(doc.source_url)
                doc.mime_type = mime
            else:
                raise ValueError("Document has neither a file nor a URL")

            pages = clean_pages(pages)
            pieces = chunk_pages(pages)
            if not pieces:
                raise ValueError("No readable text found. If this is a scanned file, check OCR is installed.")

            # Embed with the title prepended: improves retrieval for short chunks.
            year = f" ({doc.academic_year})" if doc.academic_year else ""
            texts = [f"{doc.title}{year}\n{content}" for _, content in pieces]
            vectors = await get_llm().embed(texts)

            await db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
            for i, ((page_no, content), vec) in enumerate(zip(pieces, vectors)):
                db.add(Chunk(document_id=doc.id, chunk_index=i, content=content, page_no=page_no,
                             embedding=vec, meta={"doc_type": doc.doc_type}))
            doc.num_pages = len([p for p in pages if p.number]) or 1
            doc.num_chunks = len(pieces)
            doc.status = "active"
            await db.commit()
            await cache_clear_prefix("ans")
            log.info("Ingested document %s: %s chunks", doc.id, len(pieces))
        except Exception as exc:
            await db.rollback()
            doc = await db.get(Document, document_id)
            doc.status, doc.error = "failed", str(exc)[:1000]
            await db.commit()
            log.exception("Ingestion failed for document %s", document_id)


async def embed_faq(faq_id: int) -> None:
    from app.models import FAQ

    async with SessionLocal() as db:
        faq = await db.get(FAQ, faq_id)
        if not faq:
            return
        faq.embedding = (await get_llm().embed([faq.question]))[0]
        await db.commit()
        await cache_clear_prefix("ans")


async def reembed_all() -> int:
    """Re-embed everything (use after changing the embedding model)."""
    async with SessionLocal() as db:
        ids = (await db.execute(select(Document.id).where(Document.status.in_(["active", "failed"])))).scalars().all()
    for i in ids:
        await ingest_document(i)
    return len(ids)

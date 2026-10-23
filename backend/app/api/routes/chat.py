"""Public chat endpoints used by the website widget."""
import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import client_ip
from app.core.config import settings
from app.core.constants import QUICK_REPLIES
from app.core.database import get_db
from app.core.redis import hit_rate_limit
from app.models import ChatSession, Feedback, Message
from app.schemas.schemas import ChatIn, ChatOut, FeedbackIn, SessionIn, SessionOut
from app.services import prompts
from app.services.chat_service import handle_message

router = APIRouter(prefix="/chat", tags=["chat"])


async def _check_limits(request: Request, body: ChatIn) -> None:
    if len(body.message) > settings.MAX_MESSAGE_CHARS:
        raise HTTPException(413, f"Message too long (max {settings.MAX_MESSAGE_CHARS} characters)")
    ip = client_ip(request)
    if await hit_rate_limit(f"ip:{ip}", settings.RATE_LIMIT_PER_MINUTE) or \
            await hit_rate_limit(f"s:{body.session_id}", settings.RATE_LIMIT_PER_MINUTE):
        raise HTTPException(429, "You're sending messages too quickly. Please wait a moment.")


@router.post("/session", response_model=SessionOut)
async def create_session(body: SessionIn, request: Request, db: AsyncSession = Depends(get_db)):
    if await hit_rate_limit(f"sess:{client_ip(request)}", 30):
        raise HTTPException(429, "Too many sessions. Please wait a moment.")
    sid = str(uuid.uuid4())
    ip_hash = hashlib.sha256(f"{client_ip(request)}{settings.SECRET_KEY}".encode()).hexdigest()  # no raw IPs stored
    lang = body.language if body.language in prompts.LANG_NAMES else "en"
    db.add(ChatSession(id=sid, visitor_id=body.visitor_id, page_url=body.page_url, language=lang,
                       user_agent=(request.headers.get("user-agent") or "")[:500], ip_hash=ip_hash))
    await db.commit()
    return SessionOut(session_id=sid, greeting=prompts.reply("greeting", lang), quick_replies=QUICK_REPLIES)


@router.post("/stream")
async def chat_stream(body: ChatIn, request: Request):
    """Server-Sent Events stream: meta → token* → done."""
    await _check_limits(request, body)

    async def events():
        async for ev in handle_message(body.session_id, body.message):
            if await request.is_disconnected():
                break
            yield {"event": ev["type"], "data": json.dumps(ev, ensure_ascii=False, default=str)}

    return EventSourceResponse(events(), ping=15)


@router.post("/message", response_model=ChatOut)
async def chat_message(body: ChatIn, request: Request):
    """Non-streaming variant (used by evals, integrations and simple clients)."""
    await _check_limits(request, body)
    done = None
    async for ev in handle_message(body.session_id, body.message):
        if ev["type"] == "error":
            raise HTTPException(404, ev["message"])
        if ev["type"] == "done":
            done = ev
    return ChatOut(message_id=done["message_id"], answer=done["answer"], sources=done["sources"],
                   intent=done["intent"], answered=done["answered"], confidence=done["confidence"],
                   suggest_ticket=done["suggest_ticket"], ticket_prefill=done["ticket_prefill"])


@router.get("/session/{session_id}/messages")
async def session_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    """Restores chat history in the widget after a page reload."""
    if not await db.get(ChatSession, session_id):
        raise HTTPException(404, "Session not found")
    rows = (await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.id).limit(100))).scalars().all()
    return [{"id": m.id, "role": m.role, "content": m.content, "sources": m.sources,
             "rating": m.feedback.rating if m.feedback else None} for m in rows]


@router.post("/feedback")
async def feedback(body: FeedbackIn, db: AsyncSession = Depends(get_db)):
    msg = await db.get(Message, body.message_id)
    if not msg or msg.session_id != body.session_id or msg.role != "assistant":
        raise HTTPException(404, "Message not found")
    existing = await db.scalar(select(Feedback).where(Feedback.message_id == msg.id))
    if existing:
        existing.rating, existing.comment = body.rating, body.comment
    else:
        db.add(Feedback(message_id=msg.id, rating=body.rating, comment=body.comment))
    await db.commit()
    return {"ok": True}

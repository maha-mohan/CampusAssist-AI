"""Chat logs, unanswered questions, negative feedback and analytics."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_staff
from app.core.database import get_db
from app.models import FAQ, ChatSession, Document, Feedback, Message, Ticket, User
from app.schemas.schemas import MessageOut, Page

router = APIRouter(tags=["admin-chats"])

# Rough USD prices per 1M tokens for cost estimates; update to current pricing.
PRICE_PER_M = {"gpt-4o-mini": (0.15, 0.60), "gpt-4o": (2.50, 10.00)}


def _msg_out(m: Message) -> MessageOut:
    out = MessageOut.model_validate(m)
    out.rating = m.feedback.rating if m.feedback else None
    return out


@router.get("/chats", response_model=Page)
async def list_sessions(q: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                        _: User = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    stmt = select(ChatSession).where(ChatSession.message_count > 0)
    if q:
        sub = select(Message.session_id).where(Message.content.ilike(f"%{q}%"))
        stmt = stmt.where(ChatSession.id.in_(sub))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.execute(stmt.order_by(ChatSession.last_active_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    items = []
    for s in rows:
        first = await db.scalar(select(Message.content).where(Message.session_id == s.id, Message.role == "user").order_by(Message.id).limit(1))
        unanswered = await db.scalar(select(func.count()).where(Message.session_id == s.id, Message.role == "assistant", Message.answered.is_(False)))
        items.append({"id": s.id, "language": s.language, "page_url": s.page_url, "message_count": s.message_count,
                      "started_at": s.started_at, "last_active_at": s.last_active_at, "first_message": first,
                      "unanswered": unanswered})
    return Page(items=items, total=total or 0, page=page, page_size=page_size)


@router.get("/chats/{session_id}")
async def session_detail(session_id: str, _: User = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    s = await db.get(ChatSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    msgs = (await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.id))).scalars().all()
    tickets = (await db.execute(select(Ticket.ticket_code, Ticket.status).where(Ticket.session_id == session_id))).all()
    return {"session": {"id": s.id, "language": s.language, "page_url": s.page_url, "started_at": s.started_at,
                        "user_agent": s.user_agent},
            "messages": [_msg_out(m) for m in msgs],
            "tickets": [{"ticket_code": t.ticket_code, "status": t.status} for t in tickets]}


@router.get("/insights/unanswered", response_model=Page)
async def unanswered_questions(days: int = Query(30, ge=1, le=365), page: int = Query(1, ge=1),
                               page_size: int = Query(50, ge=1, le=200),
                               _: User = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    """The most useful list for content admins: questions the bot couldn't answer → add FAQs/documents."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    # Pair each unanswered assistant message with the user question just before it,
    # then group identical questions so staff see "asked 5 times" instead of 5 rows.
    a = Message.__table__.alias("a")
    u = Message.__table__.alias("u")
    question = (select(u.c.content).where(u.c.session_id == a.c.session_id, u.c.role == "user", u.c.id < a.c.id)
                .order_by(u.c.id.desc()).limit(1).correlate(a).scalar_subquery())
    rows = (await db.execute(
        select(a.c.id, a.c.session_id, a.c.created_at, question.label("question"))
        .where(a.c.role == "assistant", a.c.answered.is_(False), a.c.intent == "question", a.c.created_at >= since)
        .order_by(a.c.id.desc()).limit(2000))).all()
    groups: dict[str, dict] = {}
    for r in rows:
        key = " ".join((r.question or "").lower().split()).rstrip("?.! ")
        g = groups.get(key)
        if g:
            g["count"] += 1
        else:
            groups[key] = {"message_id": r.id, "session_id": r.session_id, "question": r.question,
                           "count": 1, "created_at": r.created_at}
    ordered = sorted(groups.values(), key=lambda g: (-g["count"], -g["created_at"].timestamp()))
    start = (page - 1) * page_size
    return Page(items=ordered[start:start + page_size], total=len(ordered), page=page, page_size=page_size)


@router.get("/insights/negative-feedback", response_model=Page)
async def negative_feedback(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                            _: User = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    stmt = select(Message, Feedback).join(Feedback, Feedback.message_id == Message.id).where(Feedback.rating < 0)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.execute(stmt.order_by(Feedback.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).all()
    items = []
    for m, f in rows:
        q = await db.scalar(select(Message.content).where(Message.session_id == m.session_id, Message.role == "user",
                                                          Message.id < m.id).order_by(Message.id.desc()).limit(1))
        items.append({"message_id": m.id, "session_id": m.session_id, "question": q, "answer": m.content,
                      "sources": m.sources, "comment": f.comment, "created_at": f.created_at})
    return Page(items=items, total=total or 0, page=page, page_size=page_size)


@router.get("/analytics/overview")
async def overview(days: int = Query(14, ge=1, le=180), _: User = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    async def count(stmt):
        return await db.scalar(stmt) or 0

    sessions_total = await count(select(func.count()).select_from(ChatSession).where(ChatSession.started_at >= since, ChatSession.message_count > 0))
    sessions_today = await count(select(func.count()).select_from(ChatSession).where(ChatSession.started_at >= today, ChatSession.message_count > 0))
    questions = await count(select(func.count()).select_from(Message).where(Message.role == "assistant", Message.intent == "question", Message.created_at >= since))
    answered = await count(select(func.count()).select_from(Message).where(Message.role == "assistant", Message.intent == "question", Message.answered.is_(True), Message.created_at >= since))
    fb_pos = await count(select(func.count()).select_from(Feedback).where(Feedback.rating > 0, Feedback.created_at >= since))
    fb_neg = await count(select(func.count()).select_from(Feedback).where(Feedback.rating < 0, Feedback.created_at >= since))
    avg_latency = await db.scalar(select(func.avg(Message.latency_ms)).where(Message.role == "assistant", Message.created_at >= since)) or 0

    tickets_by_status = dict((await db.execute(select(Ticket.status, func.count()).group_by(Ticket.status))).all())
    tickets_by_cat = [{"category": c, "count": n} for c, n in (await db.execute(
        select(Ticket.category, func.count()).where(Ticket.created_at >= since).group_by(Ticket.category).order_by(func.count().desc()))).all()]

    day = cast(func.timezone("Asia/Kolkata", Message.created_at), Date)
    daily_rows = (await db.execute(
        select(day.label("d"), func.count().label("n"),
               func.count().filter(Message.answered.is_(False)).label("unanswered"))
        .where(Message.role == "assistant", Message.created_at >= since).group_by("d").order_by("d"))).all()
    daily = [{"date": str(d), "messages": n, "unanswered": u} for d, n, u in daily_rows]

    source_rows = dict((await db.execute(select(Message.answer_source, func.count()).where(
        Message.role == "assistant", Message.intent == "question", Message.created_at >= since).group_by(Message.answer_source))).all())

    token_rows = (await db.execute(select(Message.model, func.sum(Message.prompt_tokens), func.sum(Message.completion_tokens))
                                   .where(Message.created_at >= since, Message.model.is_not(None)).group_by(Message.model))).all()
    cost = 0.0
    tokens = 0
    for model, pt, ct in token_rows:
        pin, pout = PRICE_PER_M.get(model or "", (0, 0))
        cost += (pt or 0) / 1e6 * pin + (ct or 0) / 1e6 * pout
        tokens += (pt or 0) + (ct or 0)

    top_q = (await db.execute(select(func.lower(Message.content).label("q"), func.count().label("n")).where(
        Message.role == "user", Message.intent == "question", Message.created_at >= since)
        .group_by("q").order_by(func.count().desc()).limit(10))).all()

    docs_active = await count(select(func.count()).select_from(Document).where(Document.status == "active"))
    docs_failed = await count(select(func.count()).select_from(Document).where(Document.status == "failed"))
    faqs_active = await count(select(func.count()).select_from(FAQ).where(FAQ.is_active.is_(True)))

    return {
        "period_days": days,
        "sessions": sessions_total, "sessions_today": sessions_today,
        "questions": questions, "answered": answered,
        "answer_rate": round(answered / questions, 3) if questions else None,
        "feedback": {"positive": fb_pos, "negative": fb_neg},
        "avg_latency_ms": int(avg_latency),
        "tickets_by_status": tickets_by_status, "tickets_by_category": tickets_by_cat,
        "open_tickets": tickets_by_status.get("open", 0) + tickets_by_status.get("in_progress", 0),
        "daily": daily,
        "answer_sources": source_rows,
        "tokens": tokens, "estimated_cost_usd": round(cost, 4),
        "top_questions": [{"question": q, "count": n} for q, n in top_q],
        "knowledge": {"documents_active": docs_active, "documents_failed": docs_failed, "faqs_active": faqs_active},
    }

"""Chat orchestration: intent → (FAQ | RAG | fixed reply | ticket flow) → streamed answer.

`handle_message` is an async generator of events so the same logic powers the
SSE streaming endpoint and the plain JSON endpoint (used by evals and tests):

    {"type": "meta",  "intent": ..., "language": ...}
    {"type": "token", "text": "..."}            (many)
    {"type": "done",  "message_id": ..., "sources": [...], "answered": bool, ...}
"""
from __future__ import annotations

import logging
import re
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.redis import cache_get, cache_key, cache_set
from app.models import FAQ, ChatSession, Message
from app.services import nlu, prompts
from app.services.llm_client import StreamResult, get_llm
from app.services.retrieval import RetrievedChunk, match_faq, relevance, search_chunks
from app.services.ticket_service import find_ticket_for_public

log = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?91[\s-]?)?[6-9]\d{9}")
CITE_RE = re.compile(r"\[(\d{1,2})\]")
ANSWER_CACHE = "ans"


def _sources_from(chunks: list[RetrievedChunk], answer: str) -> list[dict]:
    cited = {int(n) for n in CITE_RE.findall(answer)}
    picked = [chunks[i - 1] for i in sorted(cited) if 0 < i <= len(chunks)] or chunks[:2]
    seen, out = set(), []
    for c in picked:
        if c.document_id in seen:
            continue
        seen.add(c.document_id)
        url = c.source_url or f"{settings.API_PREFIX}/documents/{c.document_id}/file"
        out.append({"title": c.title, "url": url, "page": c.page_no, "document_id": c.document_id})
    return out


def _chunk_words(text: str, size: int = 4):
    words = re.split(r"(\s+)", text)
    for i in range(0, len(words), size):
        yield "".join(words[i:i + size])


async def _history(db, session_id: str, limit: int) -> list[Message]:
    rows = (await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.id.desc()).limit(limit)
    )).scalars().all()
    return list(reversed(rows))


async def _standalone_query(text: str, history: list[Message]) -> str:
    if not history or not nlu.is_follow_up(text):
        return text
    convo = "\n".join(f"{'User' if m.role == 'user' else 'Assistant'}: {m.content[:400]}" for m in history[-4:])
    try:
        rewritten, _ = await get_llm().complete(
            [{"role": "system", "content": prompts.REWRITE_PROMPT},
             {"role": "user", "content": f"Conversation:\n{convo}\n\nFollow-up: {text}"}],
            max_tokens=80,
        )
        return rewritten.strip().strip('"') or text
    except Exception as exc:
        log.warning("Query rewrite failed: %s", exc)
        return text


async def handle_message(session_id: str, text: str) -> AsyncIterator[dict]:
    started = time.perf_counter()
    text = text[: settings.MAX_MESSAGE_CHARS]

    async with SessionLocal() as db:
        chat = await db.get(ChatSession, session_id)
        if not chat:
            yield {"type": "error", "message": "Session not found. Please refresh the chat."}
            return

        history = await _history(db, session_id, settings.HISTORY_TURNS * 2)
        language = nlu.detect_language(text)
        if language == "en" and chat.language in ("ta", "ta-en", "hi") and len(text.split()) <= 3:
            language = chat.language  # keep language for very short replies like "ok", "CSE"
        intent = nlu.detect_intent(text)

        db.add(Message(session_id=session_id, role="user", content=text, intent=intent))
        await db.flush()
        yield {"type": "meta", "intent": intent, "language": language}

        answer, sources, answered, confidence = "", [], True, None
        answer_source, model, suggest_ticket, prefill = "system", None, False, None
        p_tokens = c_tokens = 0
        streamed = False  # True when the answer tokens were already yielded

        try:
            if intent in ("greeting", "thanks"):
                answer = prompts.reply(intent, language)

            elif intent == "create_ticket":
                answer = prompts.reply("create_ticket", language)
                context_text = " ".join([m.content for m in history if m.role == "user"][-3:] + [text])
                suggest_ticket = True
                prefill = {"category": nlu.guess_category(context_text), "subject": text[:120], "description": text}

            elif intent == "ticket_status":
                answer = await _ticket_status_reply(db, text, history, language)

            else:  # question → FAQ / RAG
                async for ev in _answer_question(db, text, history, language):
                    if ev["type"] == "token":
                        streamed = True
                        yield ev
                    elif ev["type"] == "result":
                        answer = ev["answer"]
                        sources, answered, confidence = ev["sources"], ev["answered"], ev["confidence"]
                        answer_source, model = ev["answer_source"], ev["model"]
                        p_tokens, c_tokens = ev["prompt_tokens"], ev["completion_tokens"]
                        if not answered:
                            suggest_ticket = True
                            prefill = {"category": nlu.guess_category(text), "subject": text[:120], "description": text}
        except Exception as exc:
            log.exception("Chat failed: %s", exc)
            await db.rollback()
            db.add(Message(session_id=session_id, role="user", content=text, intent=intent))
            answer, answered, answer_source, suggest_ticket = prompts.reply("error", language), False, "fallback", True
            sources, confidence, streamed = [], None, False
            yield {"type": "reset"}  # tell the client to discard any partial text

        if not streamed:
            for piece in _chunk_words(answer):
                yield {"type": "token", "text": piece}

        latency = int((time.perf_counter() - started) * 1000)
        msg = Message(session_id=session_id, role="assistant", content=answer, sources=sources, intent=intent,
                      confidence=confidence, answered=answered, answer_source=answer_source, model=model,
                      prompt_tokens=p_tokens, completion_tokens=c_tokens, latency_ms=latency)
        db.add(msg)
        await db.execute(update(ChatSession).where(ChatSession.id == session_id).values(
            message_count=ChatSession.message_count + 2, last_active_at=datetime.now(timezone.utc), language=language))
        await db.commit()

        yield {"type": "done", "message_id": msg.id, "answer": answer, "sources": sources, "intent": intent,
               "answered": answered, "confidence": confidence, "suggest_ticket": suggest_ticket,
               "ticket_prefill": prefill, "latency_ms": latency}


async def _answer_question(db, text: str, history: list[Message], language: str) -> AsyncIterator[dict]:
    llm = get_llm()
    query = await _standalone_query(text, history)

    def result(answer, sources=None, answered=True, confidence=None, answer_source="rag",
               model=None, pt=0, ct=0):
        return {"type": "result", "answer": answer, "sources": sources or [], "answered": answered,
                "confidence": confidence, "answer_source": answer_source, "model": model,
                "prompt_tokens": pt, "completion_tokens": ct}

    # 1) Answer cache (only for self-contained questions)
    ckey = cache_key(ANSWER_CACHE, query.lower().strip(), language)
    cached = await cache_get(ckey) if query == text else None
    if cached:
        for piece in _chunk_words(cached["answer"]):
            yield {"type": "token", "text": piece}
        yield result(cached["answer"], cached["sources"], True, cached.get("confidence"), "cache")
        return

    query_vec = (await llm.embed([query]))[0]

    # 2) Curated FAQ match → direct, verified answer (English) or as top context (other languages)
    faq = await match_faq(db, query_vec)
    if faq and language == "en":
        await db.execute(update(FAQ).where(FAQ.id == faq.id).values(hits=FAQ.hits + 1))
        for piece in _chunk_words(faq.answer):
            yield {"type": "token", "text": piece}
        src = [{"title": "College FAQ", "url": None, "page": None, "document_id": None}]
        await cache_set(ckey, {"answer": faq.answer, "sources": src, "confidence": faq.score}, ttl=3600)
        yield result(faq.answer, src, True, round(faq.score, 3), "faq")
        return

    # 3) Hybrid retrieval over documents
    chunks = await search_chunks(db, query, query_vec)
    if faq:
        await db.execute(update(FAQ).where(FAQ.id == faq.id).values(hits=FAQ.hits + 1))
        chunks.insert(0, RetrievedChunk(0, 0, "College FAQ", f"Q: {faq.question}\nA: {faq.answer}", None,
                                        None, settings.CURRENT_ACADEMIC_YEAR, "faq", faq.score))
    conf = relevance(chunks)
    if conf < settings.MIN_RELEVANCE_SCORE:
        ans = prompts.reply("no_answer", language)
        for piece in _chunk_words(ans):
            yield {"type": "token", "text": piece}
        yield result(ans, [], False, round(conf, 3), "fallback")
        return

    # 4) Generate grounded answer (streamed). Hold back the first characters to catch NO_ANSWER.
    messages = [
        {"role": "system", "content": prompts.system_prompt(language)},
        *[{"role": m.role, "content": m.content[:800]} for m in history[-4:] if m.role in ("user", "assistant")],
        {"role": "user", "content": prompts.user_prompt(prompts.build_context_block(chunks), text if query == text else f"{text}\n(Interpreted as: {query})")},
    ]
    sr = StreamResult()
    buffer, full, released = "", "", False
    async for token in llm.stream(messages, sr):
        full += token
        if released:
            yield {"type": "token", "text": token}
            continue
        buffer += token
        if len(buffer) >= 12 or not "NO_ANSWER".startswith(buffer.strip()[:9]):
            if buffer.strip().startswith("NO_ANSWER"):
                break
            released = True
            yield {"type": "token", "text": buffer}

    if full.strip().startswith("NO_ANSWER") or not full.strip():
        ans = prompts.reply("no_answer", language)
        for piece in _chunk_words(ans):
            yield {"type": "token", "text": piece}
        yield result(ans, [], False, round(conf, 3), "fallback", sr.usage.model,
                     sr.usage.prompt_tokens, sr.usage.completion_tokens)
        return
    if not released:
        yield {"type": "token", "text": buffer}

    sources = [s for s in _sources_from(chunks, full) if s["document_id"] != 0]
    if any(c.document_id == 0 for c in chunks) and not sources:
        sources = [{"title": "College FAQ", "url": None, "page": None, "document_id": None}]
    if query == text:
        await cache_set(ckey, {"answer": full, "sources": sources, "confidence": round(conf, 3)}, ttl=3600)
    yield result(full, sources, True, round(conf, 3), "rag", sr.usage.model,
                 sr.usage.prompt_tokens, sr.usage.completion_tokens)


async def _ticket_status_reply(db, text: str, history: list[Message], language: str) -> str:
    # Look for the code and contact in this message and the last few user turns.
    recent = " ".join([m.content for m in history if m.role == "user"][-3:] + [text])
    code = nlu.extract_ticket_code(text) or nlu.extract_ticket_code(recent)
    contact_m = EMAIL_RE.search(text) or PHONE_RE.search(text) or EMAIL_RE.search(recent) or PHONE_RE.search(recent)
    if not code or not contact_m:
        return prompts.reply("ticket_status_ask", language)
    ticket = await find_ticket_for_public(db, code, contact_m.group(0))
    if not ticket:
        return (f"I couldn't find a ticket {code} with that email/phone. Please check the details, "
                "or raise a new ticket if needed.")
    status = ticket.status.replace("_", " ").title()
    lines = [f"**Ticket {ticket.ticket_code}**", f"- Subject: {ticket.subject}",
             f"- Department: {ticket.department.name if ticket.department else 'College Office'}",
             f"- Status: **{status}**"]
    public = [u for u in ticket.updates if u.is_public and u.note and u.note != "Ticket created"]
    if public:
        lines.append(f"- Latest update: {public[-1].note}")
    return "\n".join(lines)

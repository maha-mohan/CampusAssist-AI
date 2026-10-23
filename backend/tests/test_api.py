"""End-to-end API tests against a real PostgreSQL + pgvector database (mock LLM)."""
import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client():
    from app.core.database import Base, engine
    import app.models  # noqa: F401

    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Test database not available: {exc}")

    from app.scripts.seed import seed
    await seed(with_samples=True)

    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_headers(client):
    r = await client.post("/api/admin/auth/login", json={"email": "admin@test.edu", "password": "Admin@12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def new_session(client) -> str:
    r = await client.post("/api/chat/session", json={"page_url": "https://college.edu"})
    assert r.status_code == 200
    assert "Help Desk" in r.json()["greeting"]
    return r.json()["session_id"]


async def ask(client, sid, message):
    r = await client.post("/api/chat/message", json={"session_id": sid, "message": message})
    assert r.status_code == 200, r.text
    return r.json()


async def test_health(client):
    r = await client.get("/api/health")
    assert r.json()["database"] == "ok"


async def test_rag_answer_with_sources(client):
    sid = await new_session(client)
    d = await ask(client, sid, "What is the annual fee for CSE?")
    assert d["answered"] is True
    assert "1,20,000" in d["answer"]
    assert any(s["title"] == "Fee Structure 2026-27" for s in d["sources"])


async def test_unknown_question_offers_ticket(client):
    sid = await new_session(client)
    d = await ask(client, sid, "Who won the IPL final?")
    assert d["answered"] is False
    assert d["suggest_ticket"] is True


async def test_faq_direct_answer(client):
    sid = await new_session(client)
    d = await ask(client, sid, "Is there college bus facility?")
    assert "25 routes" in d["answer"]


async def test_streaming_endpoint(client):
    sid = await new_session(client)
    async with client.stream("POST", "/api/chat/stream", json={"session_id": sid, "message": "highest placement package?"}) as r:
        body = "".join([chunk async for chunk in r.aiter_text()])
    assert "event: token" in body and "event: done" in body and "24 LPA" in body


async def test_ticket_flow(client, admin_headers):
    sid = await new_session(client)
    d = await ask(client, sid, "I have an issue with my exam hall ticket")
    assert d["intent"] == "create_ticket" and d["ticket_prefill"]["category"] == "Examination"

    r = await client.post("/api/tickets", json={
        "session_id": sid, "name": "Priya", "email": "priya@example.com", "category": "Examination",
        "subject": "Hall ticket not generated", "description": "My hall ticket is not available on the portal."})
    assert r.status_code == 201, r.text
    code = r.json()["ticket_code"]
    assert r.json()["department"] == "Examination Cell"

    # Public status needs the matching contact
    assert (await client.get(f"/api/tickets/{code}", params={"contact": "someone@else.com"})).status_code == 404
    pub = await client.get(f"/api/tickets/{code}", params={"contact": "PRIYA@example.com"})
    assert pub.status_code == 200 and pub.json()["status"] == "open"

    # Staff resolves it with a public note
    lst = await client.get("/api/admin/tickets", headers=admin_headers, params={"q": code})
    tid = lst.json()["items"][0]["id"]
    upd = await client.patch(f"/api/admin/tickets/{tid}", headers=admin_headers,
                             json={"status": "resolved", "note": "Hall ticket regenerated. Please download again.", "is_public": True})
    assert upd.status_code == 200 and upd.json()["status"] == "resolved"

    # Status via chat
    d = await ask(client, sid, f"status of ticket {code} priya@example.com")
    assert "Resolved" in d["answer"] and "regenerated" in d["answer"]


async def test_upload_document_then_answer(client, admin_headers):
    content = b"Library Timings (SAMPLE)\n\nThe central library is open from 8:00 AM to 8:00 PM on all working days. Students can borrow up to 4 books for 14 days."
    r = await client.post("/api/admin/documents/upload", headers=admin_headers,
                          files={"file": ("library.txt", content, "text/plain")},
                          data={"title": "Library Rules", "doc_type": "policy"})
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    for _ in range(50):
        doc = (await client.get(f"/api/admin/documents/{doc_id}", headers=admin_headers)).json()
        if doc["status"] in ("active", "failed"):
            break
        await asyncio.sleep(0.1)
    assert doc["status"] == "active", doc
    sid = await new_session(client)
    d = await ask(client, sid, "What are the central library timings?")
    assert "8:00 AM" in d["answer"]


async def test_feedback_and_analytics(client, admin_headers):
    sid = await new_session(client)
    d = await ask(client, sid, "What is the last date for B.E. admission?")
    r = await client.post("/api/chat/feedback", json={"message_id": d["message_id"], "session_id": sid, "rating": -1, "comment": "too long"})
    assert r.status_code == 200
    ov = (await client.get("/api/admin/analytics/overview", headers=admin_headers)).json()
    assert ov["questions"] >= 1 and ov["feedback"]["negative"] >= 1
    un = (await client.get("/api/admin/insights/unanswered", headers=admin_headers)).json()
    assert un["total"] >= 1
    neg = (await client.get("/api/admin/insights/negative-feedback", headers=admin_headers)).json()
    assert neg["items"][0]["comment"] == "too long"


async def test_rbac(client, admin_headers):
    depts = (await client.get("/api/admin/departments", headers=admin_headers)).json()
    hostel = next(d for d in depts if d["slug"] == "hostel")
    r = await client.post("/api/admin/users", headers=admin_headers, json={
        "name": "Hostel Staff", "email": "warden@test.edu", "password": "Warden@123", "role": "staff",
        "department_id": hostel["id"]})
    assert r.status_code == 201
    login = await client.post("/api/admin/auth/login", json={"email": "warden@test.edu", "password": "Warden@123"})
    staff = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.get("/api/admin/users", headers=staff)).status_code == 403
    assert (await client.post("/api/admin/faqs", headers=staff, json={"question": "Test question?", "answer": "x"})).status_code == 403
    # Staff only see their department's tickets
    tickets = (await client.get("/api/admin/tickets", headers=staff)).json()
    assert all(t["department_id"] == hostel["id"] for t in tickets["items"])
    assert (await client.get("/api/admin/tickets")).status_code == 401

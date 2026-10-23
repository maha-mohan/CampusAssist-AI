"""Add realistic DUMMY data to every table so the admin dashboard has something to show.

Run after `app.scripts.seed`:
    python -m app.scripts.seed_dummy

Adds: staff accounts, extra FAQs, chat sessions with answers and feedback, tickets with
updates, and audit log entries. Safe to run again: rows that already exist are skipped.
All dummy staff use the password DUMMY_PASSWORD below. Do not use this in production.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    FAQ, AuditLog, ChatSession, Department, Document, Feedback, Message, Ticket, TicketUpdate, User,
)
from app.services.ingestion import embed_faq

DUMMY_PASSWORD = "Dummy@2026"
NOW = datetime.now(timezone.utc)
NAMESPACE = uuid.UUID("6f1c2a52-8c1e-4a53-9d0a-7b1f0c3d2e11")

STAFF = [
    # (name, email, role, department slug)
    ("Meena Iyer", "admissions.admin@college.edu", "dept_admin", "admissions"),
    ("Suresh Babu", "exam.admin@college.edu", "dept_admin", "exam-cell"),
    ("Lakshmi Narayanan", "accounts.admin@college.edu", "dept_admin", "accounts"),
    ("Rajesh Kumar", "hostel.admin@college.edu", "dept_admin", "hostel"),
    ("Anand Mohan", "transport.admin@college.edu", "dept_admin", "transport"),
    ("Divya Shankar", "placements.admin@college.edu", "dept_admin", "placements"),
    ("Prakash Raj", "academics.admin@college.edu", "dept_admin", "academics"),
    ("Kavitha Devi", "library.admin@college.edu", "dept_admin", "library"),
    ("Vijay Anand", "office.admin@college.edu", "dept_admin", "office"),
    ("Ramesh Pillai", "it.admin@college.edu", "dept_admin", "it-support"),
    ("Sneha Krishnan", "sneha.staff@college.edu", "staff", "accounts"),
    ("Hari Prasad", "hari.staff@college.edu", "staff", "exam-cell"),
]

EXTRA_FAQS = [
    ("When is the last date to pay semester fees?",
     "Semester fees are due on the date printed on the fee circular. Pay at the Accounts & Fees counter or online. A late fee of Rs. 50 per day applies after the due date.", "accounts"),
    ("When are hall tickets released for semester exams?",
     "Hall tickets are released on the student portal about 10 days before the exam. Students with pending fees will not get a hall ticket until the dues are cleared.", "exam-cell"),
    ("How do I get a bonafide certificate?",
     "Submit a request at the College Office with your student ID card. Certificates are usually issued within 2 working days.", "office"),
    ("Can first-year students apply for hostel?",
     "Yes. Hostel seats are allotted on merit and distance from home. Apply through the Hostel Office during the admission period.", "hostel"),
    ("I forgot my student portal password. What do I do?",
     "Use 'Forgot password' on the student portal. If it still fails, raise a ticket under the Technical category so the IT Support team can help.", "it-support"),
    ("What are the library timings?",
     "The central library is open Monday to Saturday, 8:30 AM to 6:00 PM. Digital journals can be accessed 24x7 from the campus network.", "library"),
]

# Each exchange: (question, answer, source document title or None, answer_source, answered, rating)
SESSIONS = [
    ("en", "/admissions.html", 1, [
        ("What is the B.E. admission process this year?",
         "Applications for B.E. 2026-27 open through the Admissions Office. Apply online, upload your marksheets and pay the application fee. Seats are allotted on merit. [1]",
         "Admission Notification 2026-27", "rag", True, 1),
        ("Is there a last date to apply?",
         "The application window closes on the date mentioned in the admission notification. Check the notice for the exact date. [1]",
         "Admission Notification 2026-27", "rag", True, None),
    ]),
    ("en", "/fees.html", 2, [
        ("What is the fee structure for 2026-27?",
         "The fees below apply to students admitted in 2026-27 under the management quota. Admission fee (one-time): Rs. 5,000. [1]",
         "Fee Structure 2026-27", "rag", True, 1),
    ]),
    ("ta", "/hostel.html", 3, [
        ("Hostel fees evlo?",
         "Hostel fees depend on the room type. Please see the hostel fee table for details. [1]",
         "Hostel Information", "rag", True, -1),
        ("Hostel la wifi irukka?",
         "Yes, Wi-Fi is available in the hostel blocks. [1]",
         "Hostel Information", "rag", True, None),
    ]),
    ("en", "/exams.html", 4, [
        ("When are the semester exams?",
         "Semester exam dates are published in the examination timetable each term. [1]",
         "Examination Guidelines", "rag", True, 1),
    ]),
    ("en", "/placements.html", 5, [
        ("Which companies recruited last year?",
         "The Placement Report 2025-26 lists the recruiters and package ranges for the last placement season. [1]",
         "Placement Report 2025-26", "rag", True, 1),
    ]),
    ("en", "/", 6, [
        ("Is there a bus from Tiruppur?",
         "College buses run on routes across Coimbatore, Tiruppur and Pollachi. Contact the Transport Office for the route and fee details.",
         None, "faq", True, None),
        ("What is the fee for the bus?",
         "I could not find a confident answer in the college documents. Would you like to raise a ticket with the Transport Office?",
         None, "fallback", False, -1),
    ]),
    ("en", "/scholarships.html", 7, [
        ("What scholarships are available?",
         "Merit and need-based scholarships are listed in the Scholarships document. [1]",
         "Scholarships", "rag", True, 1),
    ]),
    ("en", "/", 8, [
        ("Where is the college located?",
         "ABC Engineering College is located on Avinashi Road, Coimbatore, Tamil Nadu.",
         None, "faq", True, None),
    ]),
]

# (category, subject, description, name, email, phone, priority, status, days_ago, assignee slug, notes)
TICKETS = [
    ("Fees", "Fee receipt not received", "I paid my semester fee online last week but did not get a receipt.",
     "Arjun Selvam", "arjun.s@example.com", "9876500001", "high", "resolved", 6, "accounts",
     [("Receipt reissued from the portal.", "in_progress", "resolved", True)]),
    ("Examination", "Hall ticket not showing", "My hall ticket is missing from the portal. Exam is next week.",
     "Nithya Raman", "nithya.r@example.com", "9876500002", "urgent", "in_progress", 2, "exam-cell",
     [("Checking fee clearance status.", "open", "in_progress", True)]),
    ("Hostel", "Room allotment query", "I want to know when hostel room allotment results will be announced.",
     "Mohamed Irfan", "irfan.m@example.com", "9876500003", "normal", "open", 1, "hostel", []),
    ("Transport", "Bus pass renewal", "My bus pass expired. How do I renew it for this semester?",
     "Keerthana S", "keerthana.s@example.com", "9876500004", "normal", "closed", 12, "transport",
     [("Renewed at the Transport Office.", "in_progress", "resolved", True),
      ("Ticket closed after confirmation.", "resolved", "closed", True)]),
    ("Placements", "Resume review session", "Is there a resume review session before the placement drive?",
     "Gokul Vasan", "gokul.v@example.com", "9876500005", "low", "open", 4, "placements", []),
    ("Technical", "Cannot log in to student portal", "The portal says my password is wrong even after reset.",
     "Priyanka Das", "priyanka.d@example.com", "9876500006", "high", "in_progress", 3, "it-support",
     [("Account unlocked. Asked student to try again.", "open", "in_progress", True)]),
    ("Library", "Book renewal", "How do I renew a book that is due tomorrow?",
     "Tamilselvan R", "tamil.r@example.com", None, "normal", "resolved", 5, "library",
     [("Renewed for 14 days.", "open", "resolved", True)]),
    ("Certificates", "Bonafide certificate for bank loan", "I need a bonafide certificate urgently for a bank loan.",
     "Aswin Kumar", "aswin.k@example.com", "9876500008", "urgent", "open", 0, "office", []),
]

AUDIT = [
    ("login", "user", None, {"note": "Dummy sign-in"}, 0),
    ("ticket.update", "ticket", "1", {"status_to": "resolved"}, 6),
    ("document.upload", "document", "1", {"filename": "fee_structure_2026_27.md"}, 9),
    ("faq.create", "faq", "1", {"category": "accounts"}, 10),
    ("user.create", "user", None, {"role": "dept_admin"}, 11),
]


def _ticket_code(day: datetime, seq: int) -> str:
    return f"C{day.strftime('%Y%m%d')}-{seq:03d}"


async def seed_dummy() -> None:
    async with SessionLocal() as db:
        depts = {d.slug: d for d in (await db.scalars(select(Department))).all()}
        if not depts:
            raise SystemExit("No departments found. Run `python -m app.scripts.seed` first.")

        # --- staff -------------------------------------------------------
        users: dict[str, User] = {}
        pw_hash = hash_password(DUMMY_PASSWORD)
        for name, email, role, slug in STAFF:
            user = await db.scalar(select(User).where(User.email == email))
            if not user:
                user = User(name=name, email=email, password_hash=pw_hash, role=role,
                            department_id=depts[slug].id, is_active=True, last_login_at=NOW - timedelta(days=1))
                db.add(user)
                await db.flush()
            if role == "dept_admin":
                users[slug] = user
        await db.commit()
        print(f"✓ {len(STAFF)} staff accounts (password: {DUMMY_PASSWORD})")

        # --- FAQs --------------------------------------------------------
        new_faqs = []
        for q, a, slug in EXTRA_FAQS:
            if not await db.scalar(select(FAQ).where(FAQ.question == q)):
                faq = FAQ(question=q, answer=a, category=slug, department_id=depts[slug].id,
                          hits=0, is_active=True)
                db.add(faq)
                new_faqs.append(faq)
        await db.commit()
        for f in new_faqs:
            await embed_faq(f.id)
        print(f"✓ {len(new_faqs)} new FAQs")

        # --- chat sessions ----------------------------------------------
        docs = {d.title: d for d in (await db.scalars(select(Document))).all()}
        session_count = 0
        for i, (lang, page, n, exchanges) in enumerate(SESSIONS, start=1):
            sid = str(uuid.uuid5(NAMESPACE, f"dummy-session-{i}"))
            if await db.get(ChatSession, sid):
                continue
            started = NOW - timedelta(days=i, hours=2)
            session = ChatSession(id=sid, visitor_id=f"dummy-visitor-{i:02d}", language=lang, page_url=page,
                                  user_agent="Mozilla/5.0 (dummy)", ip_hash=f"{i:064x}",
                                  message_count=len(exchanges) * 2, started_at=started,
                                  last_active_at=started + timedelta(minutes=5 * len(exchanges)))
            db.add(session)
            await db.flush()
            for j, (question, answer, doc_title, source, answered, rating) in enumerate(exchanges):
                t = started + timedelta(minutes=5 * j)
                db.add(Message(session_id=sid, role="user", content=question, intent="question", created_at=t))
                sources = []
                doc = docs.get(doc_title) if doc_title else None
                if doc:
                    sources = [{"title": doc.title, "url": f"/api/documents/{doc.id}/file",
                                "page": None, "document_id": doc.id}]
                msg = Message(session_id=sid, role="assistant", content=answer, sources=sources, intent="question",
                              confidence=0.78 if answered else 0.31, answered=answered, answer_source=source,
                              model="mock", prompt_tokens=420, completion_tokens=90, latency_ms=850 + 40 * j,
                              created_at=t + timedelta(seconds=3))
                db.add(msg)
                await db.flush()
                if rating is not None:
                    db.add(Feedback(message_id=msg.id, rating=rating,
                                    comment="Not what I needed." if rating < 0 else None))
            session_count += 1
        await db.commit()
        print(f"✓ {session_count} chat sessions")

        # --- tickets -----------------------------------------------------
        ticket_count = 0
        seq_by_day: dict[str, int] = {}
        for category, subject, desc, name, email, phone, priority, status, days_ago, slug, notes in TICKETS:
            created = NOW - timedelta(days=days_ago, hours=3)
            day_key = created.strftime("%Y%m%d")
            seq_by_day[day_key] = seq_by_day.get(day_key, 0) + 1
            code = _ticket_code(created, seq_by_day[day_key])
            if await db.scalar(select(Ticket).where(Ticket.ticket_code == code)):
                continue
            assignee = users.get(slug)
            resolved_at = created + timedelta(days=1) if status in ("resolved", "closed") else None
            ticket = Ticket(ticket_code=code, name=name, email=email, phone=phone, category=category,
                            department_id=depts[slug].id, subject=subject, description=desc,
                            status=status, priority=priority, assigned_to=assignee.id if assignee else None,
                            created_at=created, updated_at=created, resolved_at=resolved_at)
            db.add(ticket)
            await db.flush()
            db.add(TicketUpdate(ticket_id=ticket.id, note="Ticket created", status_to="open", is_public=True,
                                created_at=created))
            for k, (note, s_from, s_to, public) in enumerate(notes, start=1):
                db.add(TicketUpdate(ticket_id=ticket.id, user_id=assignee.id if assignee else None, note=note,
                                    status_from=s_from, status_to=s_to, is_public=public,
                                    created_at=created + timedelta(hours=6 * k)))
            ticket_count += 1
        await db.commit()
        print(f"✓ {ticket_count} tickets")

        # --- audit log ---------------------------------------------------
        audit_count = 0
        already = await db.scalar(select(AuditLog).where(AuditLog.details["dummy"].as_string() == "true").limit(1))
        super_admin = await db.scalar(select(User).where(User.role == "super_admin"))
        if not already:
            for action, entity, entity_id, details, days_ago in AUDIT:
                actor = super_admin.id if super_admin else None
                db.add(AuditLog(user_id=actor, action=action, entity=entity, entity_id=entity_id,
                                details={**details, "dummy": True},
                                created_at=NOW - timedelta(days=days_ago)))
                audit_count += 1
        await db.commit()
        print(f"✓ {audit_count} audit log entries")


if __name__ == "__main__":
    asyncio.run(seed_dummy())

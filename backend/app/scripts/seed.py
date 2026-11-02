"""Seed departments, the first super admin, sample FAQs and (optionally) sample documents.

Usage:
    python -m app.scripts.seed              # departments + admin + FAQs
    python -m app.scripts.seed --samples    # also ingest the demo documents in sample_data/
"""
import argparse
import asyncio
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.constants import DEFAULT_DEPARTMENTS
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import FAQ, Department, Document, User
from app.services import storage
from app.services.ingestion import embed_faq, ingest_document

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_data"

SAMPLE_FAQS = [
    ("What are the college working hours?", "The college office works Monday to Saturday, 9:00 AM to 4:30 PM. It is closed on Sundays and government holidays.", "office"),
    ("Where is the college located?", "ABC Engineering College is located on Avinashi Road, Coimbatore, Tamil Nadu. The campus is about 8 km from Coimbatore Junction railway station.", "office"),
    ("How can I contact the admissions office?", "You can reach the Admissions Office at admissions@college.edu or +91 422 000 0000 (9:00 AM to 4:30 PM, Monday to Saturday).", "admissions"),
    ("Is there college bus facility?", "Yes. College buses run on 25 routes across Coimbatore, Tiruppur and Pollachi. Contact the Transport Office for route and fee details.", "transport"),
    ("Which programmes does the college offer?", "The college offers B.E. Computer Science and Engineering, B.Tech Artificial Intelligence and Data Science, B.Tech Information Technology, B.E. Electronics and Communication Engineering, B.E. Electrical and Electronics Engineering, B.E. Mechanical Engineering and B.E. Civil Engineering. M.E. Computer Science and Engineering and MBA are offered at postgraduate level.", "academics"),
    ("Does the college help with placements?", "Yes. The Training and Placement Cell offers aptitude and technical training, mock interviews and campus drives. Students need a CGPA of 6.5 or above and no standing arrears to register on the placement portal before 30 June of the final year.", "placements"),
]

SAMPLE_DOCS = [
    ("admission_notification_2026_27.md", "Admission Notification 2026-27", "admission", "admissions"),
    ("fee_structure_2026_27.md", "Fee Structure 2026-27", "fees", "accounts"),
    ("hostel_information.md", "Hostel Information", "hostel", "hostel"),
    ("examination_guidelines.md", "Examination Guidelines", "exam", "exam-cell"),
    ("placements_2025_26.md", "Placement Report 2025-26", "placement", "placements"),
    ("courses_offered.md", "Courses and Departments", "department", "academics"),
    ("scholarships.md", "Scholarships", "fees", "accounts"),
    ("transport_information.md", "Transport Information 2026-27", "general", "transport"),
    ("library_information.md", "Library Rules and Services", "policy", "library"),
    ("college_office_information.md", "College Office Services and Certificates", "general", "office"),
    ("it_support_information.md", "IT Support and Campus Network Policy", "policy", "it-support"),
    ("academic_calendar_2026_27.md", "Academic Calendar 2026-27", "circular", "academics"),
    ("college_and_class_timings.md", "College and Class Timings", "general", "academics"),
    ("hostel_mess_menu_and_rooms.md", "Hostel Room Types, Mess Menu and Timings", "hostel", "hostel"),
    ("department_profiles.md", "Department Profiles", "department", "academics"),
    ("contact_directory.md", "Contact Directory", "general", "office"),
    ("attendance_and_leave_policy.md", "Attendance and Leave Policy", "policy", "academics"),
    ("code_of_conduct_and_anti_ragging.md", "Code of Conduct and Anti-Ragging Policy", "policy", "office"),
    ("campus_facilities.md", "Campus Facilities", "general", "office"),
    ("clubs_and_events.md", "Clubs, Events and Annual Fest", "general", "office"),
    ("syllabus_overview.md", "Syllabus Overview", "syllabus", "academics"),
]


async def seed(with_samples: bool) -> None:
    async with SessionLocal() as db:
        depts = {}
        for d in DEFAULT_DEPARTMENTS:
            dept = await db.scalar(select(Department).where(Department.slug == d["slug"]))
            if not dept:
                dept = Department(**d)
                db.add(dept)
                await db.flush()
            depts[d["slug"]] = dept
        print(f"✓ {len(depts)} departments")

        email = settings.FIRST_ADMIN_EMAIL.lower()
        if not await db.scalar(select(User).where(User.email == email)):
            db.add(User(name="Super Admin", email=email, password_hash=hash_password(settings.FIRST_ADMIN_PASSWORD),
                        role="super_admin"))
            print(f"✓ Super admin created: {email} (change the password after first login!)")
        else:
            print(f"• Super admin already exists: {email}")

        new_faqs = []
        for q, a, slug in SAMPLE_FAQS:
            if not await db.scalar(select(FAQ).where(FAQ.question == q)):
                faq = FAQ(question=q, answer=a, department_id=depts[slug].id, category=slug)
                db.add(faq)
                new_faqs.append(faq)
        await db.commit()
        for f in new_faqs:
            await embed_faq(f.id)
        print(f"✓ {len(new_faqs)} FAQs added")

        if not with_samples:
            return
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        ids = []
        for filename, title, doc_type, slug in SAMPLE_DOCS:
            if await db.scalar(select(Document).where(Document.title == title)):
                continue
            stored = await storage.save(f"sample_{filename}", (SAMPLE_DIR / filename).read_bytes(), "text/markdown")
            year = settings.CURRENT_ACADEMIC_YEAR if "2026_27" in filename else None
            doc = Document(title=title, filename=filename, file_path=stored, mime_type="text/markdown",
                           doc_type=doc_type, department_id=depts[slug].id, academic_year=year, status="pending")
            db.add(doc)
            await db.flush()
            ids.append(doc.id)
        await db.commit()
    for i in ids:
        await ingest_document(i)
    print(f"✓ {len(ids)} sample documents ingested")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", action="store_true", help="Also load demo documents from sample_data/")
    asyncio.run(seed(parser.parse_args().samples))

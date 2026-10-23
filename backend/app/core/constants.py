"""Shared enumerations used by the API, services and seed data."""

ROLES = ("super_admin", "dept_admin", "staff")

DOC_TYPES = (
    "admission", "fees", "circular", "syllabus", "exam", "policy",
    "hostel", "placement", "department", "faq", "website", "general",
)

DOC_STATUSES = ("pending", "processing", "active", "failed", "archived")

TICKET_STATUSES = ("open", "in_progress", "resolved", "closed")
TICKET_PRIORITIES = ("low", "normal", "high", "urgent")

# Ticket category -> department slug used for automatic routing.
TICKET_CATEGORIES: dict[str, str] = {
    "Admission": "admissions",
    "Examination": "exam-cell",
    "Fees": "accounts",
    "Scholarship": "accounts",
    "Hostel": "hostel",
    "Transport": "transport",
    "Placements": "placements",
    "Academics": "academics",
    "Library": "library",
    "Certificates": "office",
    "Technical": "it-support",
    "Other": "office",
}

DEFAULT_DEPARTMENTS = [
    {"name": "Admissions Office", "slug": "admissions", "email": "admissions@college.edu"},
    {"name": "Examination Cell", "slug": "exam-cell", "email": "coe@college.edu"},
    {"name": "Accounts & Fees", "slug": "accounts", "email": "accounts@college.edu"},
    {"name": "Hostel Office", "slug": "hostel", "email": "hostel@college.edu"},
    {"name": "Transport", "slug": "transport", "email": "transport@college.edu"},
    {"name": "Training & Placement", "slug": "placements", "email": "placements@college.edu"},
    {"name": "Academics", "slug": "academics", "email": "academics@college.edu"},
    {"name": "Library", "slug": "library", "email": "library@college.edu"},
    {"name": "College Office", "slug": "office", "email": "office@college.edu"},
    {"name": "IT Support", "slug": "it-support", "email": "it@college.edu"},
]

QUICK_REPLIES = [
    {"label": "Admission", "query": "How do I apply for B.E. admission this year?"},
    {"label": "Courses", "query": "What courses and departments are offered?"},
    {"label": "Fees", "query": "What is the fee structure for this academic year?"},
    {"label": "Exam", "query": "When are the semester exams and how do I get my hall ticket?"},
    {"label": "Hostel", "query": "What are the hostel facilities and fees?"},
    {"label": "Placements", "query": "What are the placement statistics and recruiters?"},
    {"label": "Scholarship", "query": "What scholarships are available?"},
    {"label": "Raise a ticket", "query": "I want to raise a support ticket"},
]

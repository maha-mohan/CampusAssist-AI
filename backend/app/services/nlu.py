"""Lightweight, rule-based language and intent detection (fast and free).

These run before any LLM call so greetings, ticket requests and status checks
never cost tokens.
"""
import re

from app.core.constants import TICKET_CATEGORIES

TICKET_CODE_RE = re.compile(r"\b#?(C\d{8}-\d{3,})\b", re.I)

TAMIL_RE = re.compile(r"[஀-௿]")
HINDI_RE = re.compile(r"[ऀ-ॿ]")
TANGLISH_WORDS = {
    "enna", "epdi", "eppadi", "evlo", "evvalavu", "eppo", "eppothu", "enga", "irukku", "iruka", "irukka",
    "venum", "vendum", "sollunga", "solla", "kudunga", "kudukanum", "panna", "pannanum", "theriyuma",
    "theriyala", "aagum", "aaguma", "illa", "illai", "seri", "romba", "konjam", "vanakkam", "nandri",
    "yaaru", "edhu", "ethana", "kitta", "pathi", "kaasu", "panam",
}

GREETINGS = {"hi", "hii", "hello", "hey", "hai", "vanakkam", "namaste", "good morning", "good afternoon",
             "good evening", "hlo", "helo", "வணக்கம்"}
THANKS = {"thanks", "thank you", "thankyou", "thx", "nandri", "நன்றி", "ok thanks", "great thanks", "tq"}

TICKET_PATTERNS = [
    r"\b(raise|create|open|file|submit|log)\b.{0,20}\b(ticket|complaint|request|issue)\b",
    r"\bticket\b",
    r"\bcomplain(t)?\b",
    r"\b(talk|speak|connect|chat)\b.{0,20}\b(human|person|staff|someone|agent|officer)\b",
    r"\bescalate\b",
    r"\b(not|never)\s+(received|got|getting|issued|working|updated|credited|refunded)\b",
    r"\b(have|having|facing)\s+(an?\s+)?(issue|problem)\b",
    r"\bissue with\b",
    r"\bproblem with\b",
]
STATUS_PATTERNS = [r"\b(status|update|progress)\b.{0,25}\b(ticket|complaint|request)\b", r"\btrack\b.{0,15}\bticket\b"]

CATEGORY_KEYWORDS = {
    "Admission": ["admission", "apply", "application", "counselling", "cutoff", "seat", "eligibility", "tnea"],
    "Examination": ["exam", "hall ticket", "result", "revaluation", "arrear", "marksheet", "grade", "semester exam", "coe"],
    "Fees": ["fee", "fees", "payment", "refund", "receipt", "challan", "tuition", "due"],
    "Scholarship": ["scholarship", "first graduate", "bc/mbc", "sc/st", "post matric", "stipend"],
    "Hostel": ["hostel", "mess", "room", "warden"],
    "Transport": ["bus", "transport", "route", "pass"],
    "Placements": ["placement", "internship", "recruit", "company", "job", "offer letter"],
    "Academics": ["timetable", "attendance", "syllabus", "faculty", "class", "lab", "course"],
    "Library": ["library", "book", "journal"],
    "Certificates": ["bonafide", "certificate", "transfer certificate", "tc", "conduct", "id card"],
    "Technical": ["login", "portal", "password", "website", "wifi", "erp", "email id"],
}


def detect_language(text: str) -> str:
    """Return 'ta' (Tamil script), 'hi' (Hindi), 'ta-en' (Tanglish) or 'en'."""
    if TAMIL_RE.search(text):
        return "ta"
    if HINDI_RE.search(text):
        return "hi"
    words = set(re.findall(r"[a-z]+", text.lower()))
    if len(words & TANGLISH_WORDS) >= 1 and len(words) <= 40:
        return "ta-en"
    return "en"


def detect_intent(text: str) -> str:
    """Return one of: greeting, thanks, ticket_status, create_ticket, question."""
    t = text.lower().strip().rstrip("!.? ")
    if TICKET_CODE_RE.search(text) or any(re.search(p, t) for p in STATUS_PATTERNS):
        return "ticket_status"
    if t in GREETINGS or (len(t.split()) <= 3 and t.split()[0] in GREETINGS if t else False):
        return "greeting"
    if t in THANKS or (len(t.split()) <= 4 and any(w in t for w in ("thank", "nandri", "நன்றி"))):
        return "thanks"
    # "hall ticket" is an exam document, not a help desk ticket.
    t_clean = re.sub(r"\bhall\s*ticket", "hallticket", t)
    if any(re.search(p, t_clean) for p in TICKET_PATTERNS):
        return "create_ticket"
    return "question"


def extract_ticket_code(text: str) -> str | None:
    m = TICKET_CODE_RE.search(text)
    return m.group(1).upper() if m else None


def guess_category(text: str) -> str:
    t = text.lower()
    best, score = "Other", 0
    for cat, kws in CATEGORY_KEYWORDS.items():
        s = sum(1 for k in kws if k in t)
        if s > score:
            best, score = cat, s
    return best if best in TICKET_CATEGORIES else "Other"


def is_follow_up(text: str) -> bool:
    """Heuristic: short messages or ones with pronouns/connectors need the history to be understood."""
    words = text.lower().split()
    if len(words) <= 6:
        return True
    return bool(re.match(r"^(and|also|what about|how about|then|ok|so|but|for)\b", text.lower())) or any(
        w in {"it", "its", "that", "this", "those", "them", "same", "there"} for w in words
    )

"""Pydantic request / response schemas."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.constants import TICKET_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Auth & users
# ---------------------------------------------------------------------------
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class DepartmentOut(ORM):
    id: int
    name: str
    slug: str
    email: str | None = None
    description: str | None = None


class DepartmentIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9-]+$")
    email: EmailStr | None = None
    description: str | None = None


class UserOut(ORM):
    id: int
    name: str
    email: str
    role: str
    department_id: int | None = None
    department: DepartmentOut | None = None
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["super_admin", "dept_admin", "staff"] = "staff"
    department_id: int | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    role: Literal["super_admin", "dept_admin", "staff"] | None = None
    department_id: int | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
class SessionIn(BaseModel):
    visitor_id: str | None = Field(default=None, max_length=64)
    page_url: str | None = Field(default=None, max_length=1000)
    language: str = "en"


class SessionOut(BaseModel):
    session_id: str
    greeting: str
    quick_replies: list[dict]


class ChatIn(BaseModel):
    session_id: str
    message: str = Field(min_length=1)

    @field_validator("message")
    @classmethod
    def strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        return v


class SourceOut(BaseModel):
    title: str
    url: str | None = None
    page: int | None = None
    document_id: int | None = None


class ChatOut(BaseModel):
    message_id: int
    answer: str
    sources: list[SourceOut] = []
    intent: str
    answered: bool
    confidence: float | None = None
    suggest_ticket: bool = False
    ticket_prefill: dict | None = None


class FeedbackIn(BaseModel):
    message_id: int
    session_id: str
    rating: Literal[1, -1]
    comment: str | None = Field(default=None, max_length=1000)


class MessageOut(ORM):
    id: int
    role: str
    content: str
    sources: list = []
    intent: str | None = None
    confidence: float | None = None
    answered: bool
    answer_source: str | None = None
    latency_ms: int = 0
    created_at: datetime
    rating: int | None = None


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------
class TicketCreate(BaseModel):
    session_id: str | None = None
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9 \-]{8,15}$")
    category: str = "Other"
    subject: str = Field(min_length=3, max_length=300)
    description: str = Field(min_length=5, max_length=5000)

    @field_validator("category")
    @classmethod
    def valid_category(cls, v: str) -> str:
        return v if v in TICKET_CATEGORIES else "Other"

    @model_validator(mode="after")
    def need_contact(self):
        if not self.email and not self.phone:
            raise ValueError("Please provide an email or phone number so we can contact you")
        return self


class TicketPublicUpdate(BaseModel):
    note: str | None
    status_to: str | None
    created_at: datetime


class TicketPublicOut(BaseModel):
    ticket_code: str
    subject: str
    category: str
    department: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    updates: list[TicketPublicUpdate] = []


class TicketUpdateOut(ORM):
    id: int
    note: str | None
    status_from: str | None
    status_to: str | None
    is_public: bool
    created_at: datetime
    user: UserOut | None = None


class TicketOut(ORM):
    id: int
    ticket_code: str
    session_id: str | None
    name: str
    email: str | None
    phone: str | None
    category: str
    department_id: int | None
    department: DepartmentOut | None = None
    subject: str
    description: str
    status: str
    priority: str
    assigned_to: int | None
    assignee: UserOut | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    updates: list[TicketUpdateOut] = []


class TicketAdminUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    assigned_to: int | None = None
    department_id: int | None = None
    note: str | None = Field(default=None, max_length=5000)
    is_public: bool = False  # whether the note is visible to the student

    @field_validator("status")
    @classmethod
    def v_status(cls, v):
        if v is not None and v not in TICKET_STATUSES:
            raise ValueError(f"status must be one of {TICKET_STATUSES}")
        return v

    @field_validator("priority")
    @classmethod
    def v_priority(cls, v):
        if v is not None and v not in TICKET_PRIORITIES:
            raise ValueError(f"priority must be one of {TICKET_PRIORITIES}")
        return v


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------
class DocumentOut(ORM):
    id: int
    title: str
    filename: str | None
    source_url: str | None
    mime_type: str | None
    doc_type: str
    department_id: int | None
    department: DepartmentOut | None = None
    academic_year: str | None
    valid_from: date | None
    valid_to: date | None
    status: str
    error: str | None
    num_pages: int
    num_chunks: int
    created_at: datetime
    updated_at: datetime


class DocumentUpdate(BaseModel):
    title: str | None = None
    doc_type: str | None = None
    department_id: int | None = None
    academic_year: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    status: Literal["active", "archived"] | None = None


class UrlIngestIn(BaseModel):
    url: str = Field(pattern=r"^https?://")
    title: str | None = None
    doc_type: str = "website"
    department_id: int | None = None
    academic_year: str | None = None


class ChunkOut(ORM):
    id: int
    chunk_index: int
    content: str
    page_no: int | None


class FAQIn(BaseModel):
    question: str = Field(min_length=5, max_length=1000)
    answer: str = Field(min_length=2, max_length=5000)
    category: str | None = None
    department_id: int | None = None
    is_active: bool = True


class FAQOut(ORM):
    id: int
    question: str
    answer: str
    category: str | None
    department_id: int | None
    is_active: bool
    hits: int
    created_at: datetime
    updated_at: datetime


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int

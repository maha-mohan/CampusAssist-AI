"""SQLAlchemy ORM models for the help desk."""
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base

EMBED_DIM = settings.EMBEDDING_DIM


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Organisation
# ---------------------------------------------------------------------------
class Department(TimestampMixin, Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)


class User(TimestampMixin, Base):
    """Admin / staff accounts. Website visitors are anonymous (see ChatSession)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="staff")  # super_admin | dept_admin | staff
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    department: Mapped[Department | None] = relationship(lazy="joined")


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------
class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str | None] = mapped_column(String(300))
    file_path: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    doc_type: Mapped[str] = mapped_column(String(40), default="general")
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    academic_year: Mapped[str | None] = mapped_column(String(20), index=True)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    error: Mapped[str | None] = mapped_column(Text)
    num_pages: Mapped[int] = mapped_column(Integer, default=0)
    num_chunks: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    department: Mapped[Department | None] = relationship(lazy="joined")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan", passive_deletes=True)


class Chunk(TimestampMixin, Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    page_no: Mapped[int | None] = mapped_column(Integer)
    embedding = mapped_column(Vector(EMBED_DIM))
    # 'simple' config works for English and Tamil (no language-specific stemming).
    tsv = mapped_column(TSVECTOR, Computed("to_tsvector('simple', content)", persisted=True))
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_embedding_hnsw", "embedding", postgresql_using="hnsw",
              postgresql_with={"m": 16, "ef_construction": 64},
              postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
    )


class FAQ(TimestampMixin, Base):
    __tablename__ = "faqs"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(60))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    embedding = mapped_column(Vector(EMBED_DIM))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    department: Mapped[Department | None] = relationship(lazy="joined")


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    visitor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    page_url: Mapped[str | None] = mapped_column(String(1000))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(back_populates="session", cascade="all, delete-orphan",
                                                      order_by="Message.id", passive_deletes=True)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    intent: Mapped[str | None] = mapped_column(String(30))
    confidence: Mapped[float | None] = mapped_column(Float)
    answered: Mapped[bool] = mapped_column(Boolean, default=True)
    answer_source: Mapped[str | None] = mapped_column(String(20))  # faq | rag | fallback | system
    model: Mapped[str | None] = mapped_column(String(60))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    session: Mapped[ChatSession] = relationship(back_populates="messages")
    feedback: Mapped["Feedback | None"] = relationship(back_populates="message", uselist=False, lazy="selectin")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), unique=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1 = helpful, -1 = not helpful
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    message: Mapped[Message] = relationship(back_populates="feedback")


# ---------------------------------------------------------------------------
# Help desk tickets
# ---------------------------------------------------------------------------
class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("chat_sessions.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(40), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True)
    subject: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open|in_progress|resolved|closed
    priority: Mapped[str] = mapped_column(String(20), default="normal")  # low|normal|high|urgent
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    department: Mapped[Department | None] = relationship(lazy="joined")
    assignee: Mapped[User | None] = relationship(lazy="joined")
    updates: Mapped[list["TicketUpdate"]] = relationship(back_populates="ticket", cascade="all, delete-orphan",
                                                          order_by="TicketUpdate.id", lazy="selectin")


class TicketUpdate(Base):
    __tablename__ = "ticket_updates"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(Text)
    status_from: Mapped[str | None] = mapped_column(String(20))
    status_to: Mapped[str | None] = mapped_column(String(20))
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)  # visible to the student when checking status
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticket: Mapped[Ticket] = relationship(back_populates="updates")
    user: Mapped[User | None] = relationship(lazy="joined")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(60))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

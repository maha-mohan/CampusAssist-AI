"""Help desk ticket creation, routing, status lookup and notifications."""
import logging
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import TICKET_CATEGORIES
from app.models import Department, Ticket, TicketUpdate
from app.schemas.schemas import TicketCreate
from app.services.email_service import send_email

log = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


async def _next_code(db: AsyncSession) -> str:
    today = datetime.now(IST).strftime("%Y%m%d")
    prefix = f"C{today}-"
    count = await db.scalar(select(func.count()).select_from(Ticket).where(Ticket.ticket_code.like(f"{prefix}%")))
    return f"{prefix}{(count or 0) + 1:03d}"


async def route_department(db: AsyncSession, category: str) -> Department | None:
    slug = TICKET_CATEGORIES.get(category, "office")
    return await db.scalar(select(Department).where(Department.slug == slug))


def _priority(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(urgent|emergency|immediately|today|deadline|tomorrow|asap)\b", t):
        return "high"
    return "normal"


async def create_ticket(db: AsyncSession, data: TicketCreate) -> Ticket:
    dept = await route_department(db, data.category)
    for _ in range(5):  # retry on the rare code collision
        ticket = Ticket(
            ticket_code=await _next_code(db),
            session_id=data.session_id,
            name=data.name.strip(),
            email=str(data.email) if data.email else None,
            phone=data.phone,
            category=data.category,
            department_id=dept.id if dept else None,
            subject=data.subject.strip(),
            description=data.description.strip(),
            priority=_priority(f"{data.subject} {data.description}"),
        )
        db.add(ticket)
        try:
            await db.flush()
            break
        except IntegrityError:
            await db.rollback()
    db.add(TicketUpdate(ticket_id=ticket.id, note="Ticket created", status_to="open", is_public=True))
    await db.commit()
    await db.refresh(ticket)
    return ticket


async def notify_ticket_created(ticket_id: int) -> None:
    """Runs after the response is sent: alerts the department and confirms to the student."""
    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        ticket = await db.get(Ticket, ticket_id)
        if not ticket:
            return
        dept_email = ticket.department.email if ticket.department else None
        await send_email(
            dept_email or settings.SMTP_FROM,
            f"[New Ticket {ticket.ticket_code}] {ticket.category}: {ticket.subject}",
            f"A new help desk ticket was raised.\n\nTicket: {ticket.ticket_code}\nPriority: {ticket.priority}\n"
            f"Name: {ticket.name}\nEmail: {ticket.email or '-'}\nPhone: {ticket.phone or '-'}\n\n"
            f"{ticket.description}\n\nOpen the admin dashboard to respond.",
        )
        if ticket.email:
            await send_email(
                ticket.email,
                f"Your ticket {ticket.ticket_code} has been received",
                f"Dear {ticket.name},\n\nWe have received your request \"{ticket.subject}\".\n"
                f"Ticket ID: {ticket.ticket_code}\nDepartment: {ticket.department.name if ticket.department else 'College Office'}\n\n"
                f"You can check the status anytime in the chat assistant using your ticket ID.\n\n"
                f"Regards,\n{settings.COLLEGE_NAME} Help Desk",
            )


async def notify_ticket_updated(ticket_id: int, note: str | None) -> None:
    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        ticket = await db.get(Ticket, ticket_id)
        if not ticket or not ticket.email:
            return
        await send_email(
            ticket.email,
            f"Update on your ticket {ticket.ticket_code}: {ticket.status.replace('_', ' ').title()}",
            f"Dear {ticket.name},\n\nYour ticket \"{ticket.subject}\" is now: {ticket.status.replace('_', ' ')}.\n"
            + (f"\nMessage from the team:\n{note}\n" if note else "")
            + f"\nRegards,\n{settings.COLLEGE_NAME} Help Desk",
        )


def _norm_phone(p: str | None) -> str:
    return re.sub(r"\D", "", p or "")[-10:]


async def find_ticket_for_public(db: AsyncSession, code: str, contact: str) -> Ticket | None:
    """Requires the email or phone used on the ticket, so ticket IDs can't be enumerated."""
    ticket = await db.scalar(select(Ticket).where(Ticket.ticket_code == code.upper().lstrip("#")))
    if not ticket:
        return None
    contact = contact.strip().lower()
    if ticket.email and contact == ticket.email.lower():
        return ticket
    if ticket.phone and _norm_phone(contact) and _norm_phone(contact) == _norm_phone(ticket.phone):
        return ticket
    return None


def set_status(ticket: Ticket, status: str) -> None:
    ticket.status = status
    if status in ("resolved", "closed") and not ticket.resolved_at:
        ticket.resolved_at = datetime.now(timezone.utc)
    if status in ("open", "in_progress"):
        ticket.resolved_at = None

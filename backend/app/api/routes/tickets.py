"""Public ticket endpoints (create + status check) used by the widget."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import client_ip
from app.core.constants import TICKET_CATEGORIES
from app.core.database import get_db
from app.core.redis import hit_rate_limit
from app.models import ChatSession
from app.schemas.schemas import TicketCreate, TicketPublicOut, TicketPublicUpdate
from app.services import ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/categories")
async def categories():
    return list(TICKET_CATEGORIES.keys())


@router.post("", status_code=201)
async def create_ticket(body: TicketCreate, request: Request, background: BackgroundTasks,
                        db: AsyncSession = Depends(get_db)):
    if await hit_rate_limit(f"ticket:{client_ip(request)}", 5, 600):
        raise HTTPException(429, "Too many tickets from this device. Please try again later.")
    if body.session_id and not await db.get(ChatSession, body.session_id):
        body.session_id = None
    ticket = await ticket_service.create_ticket(db, body)
    background.add_task(ticket_service.notify_ticket_created, ticket.id)
    return {
        "ticket_code": ticket.ticket_code,
        "category": ticket.category,
        "department": ticket.department.name if ticket.department else None,
        "status": ticket.status,
        "message": "Ticket created successfully. Our team will contact you soon.",
    }


@router.get("/{code}", response_model=TicketPublicOut)
async def ticket_status(code: str, request: Request, contact: str = Query(..., min_length=5, description="Email or phone used on the ticket"),
                        db: AsyncSession = Depends(get_db)):
    if await hit_rate_limit(f"tstatus:{client_ip(request)}", 15):
        raise HTTPException(429, "Too many lookups. Please wait a moment.")
    ticket = await ticket_service.find_ticket_for_public(db, code, contact)
    if not ticket:
        raise HTTPException(404, "No ticket found with that ID and contact detail")
    return TicketPublicOut(
        ticket_code=ticket.ticket_code, subject=ticket.subject, category=ticket.category,
        department=ticket.department.name if ticket.department else None, status=ticket.status,
        created_at=ticket.created_at, updated_at=ticket.updated_at,
        updates=[TicketPublicUpdate(note=u.note, status_to=u.status_to, created_at=u.created_at)
                 for u in ticket.updates if u.is_public],
    )

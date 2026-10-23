"""Help desk ticket management for staff."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import audit, require_staff
from app.core.database import get_db
from app.models import Message, Ticket, TicketUpdate, User
from app.schemas.schemas import Page, TicketAdminUpdate, TicketOut
from app.services import ticket_service

router = APIRouter(prefix="/tickets", tags=["admin-tickets"])


def _scoped(stmt, user: User):
    """Department admins and staff see their own department's tickets (plus ones assigned to them)."""
    if user.role == "super_admin":
        return stmt
    return stmt.where(or_(Ticket.department_id == user.department_id, Ticket.assigned_to == user.id))


async def _get_scoped(db: AsyncSession, ticket_id: int, user: User) -> Ticket:
    ticket = await db.scalar(_scoped(select(Ticket).where(Ticket.id == ticket_id), user))
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    return ticket


@router.get("", response_model=Page)
async def list_tickets(
    status: str | None = None, department_id: int | None = None, category: str | None = None,
    priority: str | None = None, assigned_to_me: bool = False, q: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(require_staff), db: AsyncSession = Depends(get_db),
):
    stmt = _scoped(select(Ticket), user)
    if status:
        stmt = stmt.where(Ticket.status.in_(status.split(",")))
    if department_id:
        stmt = stmt.where(Ticket.department_id == department_id)
    if category:
        stmt = stmt.where(Ticket.category == category)
    if priority:
        stmt = stmt.where(Ticket.priority == priority)
    if assigned_to_me:
        stmt = stmt.where(Ticket.assigned_to == user.id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Ticket.ticket_code.ilike(like), Ticket.subject.ilike(like), Ticket.name.ilike(like),
                              Ticket.email.ilike(like), Ticket.phone.ilike(like)))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.execute(stmt.order_by(Ticket.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).unique().scalars().all()
    return Page(items=[TicketOut.model_validate(t) for t in rows], total=total or 0, page=page, page_size=page_size)


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: int, user: User = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    ticket = await _get_scoped(db, ticket_id, user)
    transcript = []
    if ticket.session_id:
        msgs = (await db.execute(select(Message).where(Message.session_id == ticket.session_id).order_by(Message.id).limit(60))).scalars().all()
        transcript = [{"role": m.role, "content": m.content, "created_at": m.created_at} for m in msgs]
    return {"ticket": TicketOut.model_validate(ticket), "transcript": transcript}


@router.patch("/{ticket_id}", response_model=TicketOut)
async def update_ticket(ticket_id: int, body: TicketAdminUpdate, background: BackgroundTasks,
                        user: User = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    ticket = await _get_scoped(db, ticket_id, user)
    old_status = ticket.status
    changes = body.model_dump(exclude_unset=True, exclude={"note", "is_public"})
    if "department_id" in changes and user.role == "staff":
        raise HTTPException(403, "Only admins can move tickets between departments")
    for k, v in changes.items():
        if k == "status":
            ticket_service.set_status(ticket, v)
        else:
            setattr(ticket, k, v)
    if body.note or ticket.status != old_status:
        db.add(TicketUpdate(ticket_id=ticket.id, user_id=user.id, note=body.note,
                            status_from=old_status if ticket.status != old_status else None,
                            status_to=ticket.status if ticket.status != old_status else None,
                            is_public=body.is_public or ticket.status != old_status))
    await audit(db, user, "update", "ticket", ticket.id, {k: str(v) for k, v in changes.items()})
    await db.commit()
    db.expire(ticket)
    ticket = await _get_scoped(db, ticket_id, user)
    if ticket.status != old_status or (body.note and body.is_public):
        background.add_task(ticket_service.notify_ticket_updated, ticket.id, body.note if body.is_public else None)
    return ticket

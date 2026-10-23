from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import audit, client_ip, get_current_user
from app.core.database import get_db
from app.core.redis import hit_rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.schemas import LoginIn, PasswordChange, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["admin-auth"])


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    if await hit_rate_limit(f"login:{client_ip(request)}", 10, 300):
        raise HTTPException(429, "Too many login attempts. Try again in a few minutes.")
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(403, "Account is disabled")
    user.last_login_at = datetime.now(timezone.utc)
    await audit(db, user, "login", "user", user.id)
    await db.commit()
    await db.refresh(user)
    return TokenOut(access_token=create_access_token(str(user.id), user.role), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password")
async def change_password(body: PasswordChange, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    await audit(db, user, "change_password", "user", user.id)
    await db.commit()
    return {"ok": True}

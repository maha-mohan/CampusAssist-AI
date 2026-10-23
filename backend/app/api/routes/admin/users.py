"""User and department management (super admin only for writes)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import audit, get_current_user, require_super_admin
from app.core.database import get_db
from app.core.security import hash_password
from app.models import Department, User
from app.schemas.schemas import DepartmentIn, DepartmentOut, UserCreate, UserOut, UserUpdate

router = APIRouter(tags=["admin-users"])


# ---- Users -----------------------------------------------------------------
@router.get("/users", response_model=list[UserOut])
async def list_users(_: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(User).order_by(User.name))).scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(body: UserCreate, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "A user with this email already exists")
    user = User(name=body.name, email=body.email.lower(), password_hash=hash_password(body.password),
                role=body.role, department_id=body.department_id)
    db.add(user)
    await db.flush()
    await audit(db, admin, "create", "user", user.id, {"email": user.email, "role": user.role})
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, body: UserUpdate, admin: User = Depends(require_super_admin),
                      db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    data = body.model_dump(exclude_unset=True)
    if user.id == admin.id and (data.get("is_active") is False or data.get("role", "super_admin") != "super_admin"):
        raise HTTPException(400, "You can't disable or demote your own account")
    if "password" in data:
        pw = data.pop("password")
        if pw:
            user.password_hash = hash_password(pw)
    for k, v in data.items():
        setattr(user, k, v)
    await audit(db, admin, "update", "user", user.id, {k: v for k, v in data.items()})
    await db.commit()
    await db.refresh(user)
    return user


# ---- Departments -----------------------------------------------------------
@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(_: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Department).order_by(Department.name))).scalars().all()


@router.post("/departments", response_model=DepartmentOut, status_code=201)
async def create_department(body: DepartmentIn, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    dept = Department(**body.model_dump())
    db.add(dept)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(409, "Department name or slug already exists")
    await audit(db, admin, "create", "department", dept.id, {"name": dept.name})
    await db.commit()
    return dept


@router.put("/departments/{dept_id}", response_model=DepartmentOut)
async def update_department(dept_id: int, body: DepartmentIn, admin: User = Depends(require_super_admin),
                            db: AsyncSession = Depends(get_db)):
    dept = await db.get(Department, dept_id)
    if not dept:
        raise HTTPException(404, "Department not found")
    for k, v in body.model_dump().items():
        setattr(dept, k, v)
    await audit(db, admin, "update", "department", dept.id)
    await db.commit()
    return dept


@router.delete("/departments/{dept_id}", status_code=204)
async def delete_department(dept_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    dept = await db.get(Department, dept_id)
    if not dept:
        raise HTTPException(404, "Department not found")
    await db.delete(dept)
    await audit(db, admin, "delete", "department", dept_id)
    await db.commit()

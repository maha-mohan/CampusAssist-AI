from fastapi import APIRouter

from app.api.routes import chat, public, tickets
from app.api.routes.admin import auth as admin_auth
from app.api.routes.admin import chats as admin_chats
from app.api.routes.admin import documents as admin_documents
from app.api.routes.admin import tickets as admin_tickets
from app.api.routes.admin import users as admin_users

api_router = APIRouter()

# Public (website widget)
api_router.include_router(public.router)
api_router.include_router(chat.router)
api_router.include_router(tickets.router)

# Admin dashboard (JWT protected inside each router)
admin = APIRouter(prefix="/admin")
admin.include_router(admin_auth.router)
admin.include_router(admin_users.router)
admin.include_router(admin_documents.router)
admin.include_router(admin_tickets.router)
admin.include_router(admin_chats.router)
api_router.include_router(admin)

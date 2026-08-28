from fastapi import APIRouter

from app.api.v1.routes import auth, catalogs, health, roles, tickets, users


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(users.admin_router)
api_router.include_router(roles.router)
api_router.include_router(tickets.router)
api_router.include_router(catalogs.router)
api_router.include_router(catalogs.admin_router)

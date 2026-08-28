from fastapi import APIRouter

from app.api.v1.routes import (
    attachments,
    audit_logs,
    auth,
    catalogs,
    comments,
    health,
    roles,
    tickets,
    users,
    workflow,
)


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(users.admin_router)
api_router.include_router(roles.router)
api_router.include_router(tickets.router)
api_router.include_router(comments.router)
api_router.include_router(workflow.router)
api_router.include_router(attachments.router)
api_router.include_router(catalogs.router)
api_router.include_router(catalogs.admin_router)
api_router.include_router(audit_logs.router)

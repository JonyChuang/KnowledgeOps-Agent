"""Router exports registered by the FastAPI application factory."""

from .agents import agent_router
from .auth import auth_router
from .dashboard import dashboard_router
from .engagement import engagement_router
from .knowledge_bases import documents_router, knowledge_bases_router
from .notifications import notifications_router
from .service_desk import service_desk_router
from .tickets import tickets_router

__all__ = [
    "agent_router",
    "auth_router",
    "dashboard_router",
    "documents_router",
    "engagement_router",
    "knowledge_bases_router",
    "notifications_router",
    "service_desk_router",
    "tickets_router",
]

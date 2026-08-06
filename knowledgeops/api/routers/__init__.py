"""Router exports registered by the FastAPI application factory."""

from .knowledge_bases import documents_router, knowledge_bases_router

__all__ = ["documents_router", "knowledge_bases_router"]
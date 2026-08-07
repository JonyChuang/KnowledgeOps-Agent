"""FastAPI application factory and application lifecycle management."""

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import Settings, get_settings
from ..db import create_database
from .routers import documents_router, knowledge_bases_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an application instance with isolated runtime dependencies."""
    settings = settings or get_settings()
    database = create_database(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # SQLite tests and local development need tables without manual setup.
        # Production will set AUTO_CREATE_SCHEMA=false and use Alembic.
        if settings.auto_create_schema:
            await database.create_schema()

        yield

        # Always close the pool so tests and reload processes release connections.
        await database.dispose()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.database = database
    # The indexing endpoint reads Qdrant and Embedding configuration from here.
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    router = APIRouter(prefix=settings.api_prefix)

    @router.get("/health", tags=["system"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "knowledgeops-api"}

    app.include_router(router)

    # Business routers reuse the version prefix defined in Settings.
    app.include_router(knowledge_bases_router, prefix=settings.api_prefix)
    app.include_router(documents_router, prefix=settings.api_prefix)
    return app


app = create_app()
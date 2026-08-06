"""REST endpoints for knowledge bases and text documents."""

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...schemas import (
    DocumentRead,
    KnowledgeBaseCreate,
    KnowledgeBaseRead,
    TextDocumentCreate,
)
from ...services import (
    KnowledgeService,
    ResourceConflictError,
    ResourceNotFoundError,
)
from ..dependencies import get_session


knowledge_bases_router = APIRouter(
    prefix="/knowledge-bases",
    tags=["knowledge-bases"],
)
documents_router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


def get_actor(x_actor: str = Header(default="anonymous")) -> str:
    """Read the temporary actor header before authentication is introduced."""
    return x_actor


@knowledge_bases_router.post(
    "",
    response_model=KnowledgeBaseRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> KnowledgeBaseRead:
    """Create a knowledge base and append its audit event."""
    service = KnowledgeService(session)

    try:
        return await service.create_knowledge_base(payload, actor=actor)
    except ResourceConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@knowledge_bases_router.get("", response_model=list[KnowledgeBaseRead])
async def list_knowledge_bases(
    session: AsyncSession = Depends(get_session),
) -> list[KnowledgeBaseRead]:
    """List all knowledge bases for the future management page."""
    return await KnowledgeService(session).list_knowledge_bases()


@knowledge_bases_router.post(
    "/{knowledge_base_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_text_document(
    knowledge_base_id: str,
    payload: TextDocumentCreate,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> DocumentRead:
    """Store a text document and leave it ready for later indexing."""
    service = KnowledgeService(session)

    try:
        return await service.upload_text_document(
            knowledge_base_id,
            payload,
            actor=actor,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ResourceConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@knowledge_bases_router.get(
    "/{knowledge_base_id}/documents",
    response_model=list[DocumentRead],
)
async def list_documents(
    knowledge_base_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[DocumentRead]:
    """Return document metadata without exposing original document content."""
    try:
        return await KnowledgeService(session).list_documents(knowledge_base_id)
    except ResourceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@documents_router.get("/{document_id}", response_model=DocumentRead)
async def get_document_status(
    document_id: str,
    session: AsyncSession = Depends(get_session),
) -> DocumentRead:
    """Return one document's current indexing lifecycle state."""
    try:
        return await KnowledgeService(session).get_document(document_id)
    except ResourceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
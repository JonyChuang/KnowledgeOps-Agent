"""REST endpoints for knowledge bases and text documents."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...graphrag import GraphRetriever, RuleBasedEntityExtractor
from ...rag import parse_uploaded_document
from ...schemas import (
    DocumentIndexTaskRead,
    DocumentRead,
    KnowledgeBaseCreate,
    KnowledgeBaseRead,
    SearchRequest,
    SearchResultRead,
    TextDocumentCreate,
    WebPageImportCreate,
)
from ...schemas.knowledge import GraphSearchResultRead
from ...services import (
    KnowledgeService,
    ResourceConflictError,
    ResourceNotFoundError,
)
from ...services.web_import import WebImportError, import_web_page
from ...tasks import build_hybrid_retriever, enqueue_document_index
from ...tasks.indexing import build_neo4j_graph_store
from ..dependencies import get_actor, get_session

SUPPORTED_UPLOAD_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".pdf",
    ".docx",
    ".html",
    ".htm",
}


def _normalize_upload_name(source_name: str) -> str:
    normalized = source_name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not normalized:
        raise ValueError("Uploaded file must have a name.")
    if Path(normalized).suffix.lower() not in SUPPORTED_UPLOAD_SUFFIXES:
        raise ValueError("Supported file types are PDF, DOCX, Markdown, TXT, and HTML.")
    return normalized


async def _read_limited_request_body(request: Request, max_bytes: int) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="File exceeds the import size limit.",
                )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header.")

    chunks: list[bytes] = []
    total_size = 0
    async for chunk in request.stream():
        total_size += len(chunk)
        if total_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File exceeds the import size limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)

knowledge_bases_router = APIRouter(
    prefix="/knowledge-bases",
    tags=["knowledge-bases"],
)
documents_router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)

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
    "/{knowledge_base_id}/documents/upload",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_local_file_document(
    knowledge_base_id: str,
    request: Request,
    source_name: str = Query(min_length=1, max_length=255),
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> DocumentRead:
    """Extract a supported local file and persist its text for indexing."""
    settings = request.app.state.settings
    try:
        normalized_name = _normalize_upload_name(source_name)
        content = await _read_limited_request_body(
            request,
            settings.document_upload_max_bytes,
        )
        parsed = parse_uploaded_document(content, normalized_name)
        payload = TextDocumentCreate(
            source_name=parsed.source_name,
            source_type=parsed.source_type,
            content=parsed.text,
        )
        return await KnowledgeService(session).upload_text_document(
            knowledge_base_id,
            payload,
            actor=actor,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ResourceConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@knowledge_bases_router.post(
    "/{knowledge_base_id}/documents/web-import",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def import_webpage_document(
    knowledge_base_id: str,
    payload: WebPageImportCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> DocumentRead:
    """Fetch a safe public webpage and persist its readable text for indexing."""
    settings = request.app.state.settings
    try:
        parsed = await import_web_page(
            payload.url,
            max_bytes=settings.web_import_max_bytes,
            timeout_seconds=settings.web_import_timeout_seconds,
        )
        document_payload = TextDocumentCreate(
            source_name=payload.source_name or parsed.source_name,
            source_type=parsed.source_type,
            content=parsed.text,
        )
        return await KnowledgeService(session).upload_text_document(
            knowledge_base_id,
            document_payload,
            actor=actor,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except WebImportError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ResourceConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

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


@knowledge_bases_router.post(
    "/{knowledge_base_id}/search",
    response_model=list[SearchResultRead],
)
async def search_knowledge_base(
    knowledge_base_id: str,
    payload: SearchRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> list[SearchResultRead]:
    """Search indexed chunks within one existing knowledge base."""
    try:
        # Validate the scope before creating authenticated external clients.
        await KnowledgeService(session).list_documents(knowledge_base_id)

        # The retriever owns an OpenAI and Qdrant client for this request.
        retriever = build_hybrid_retriever(request.app.state.settings)
        try:
            return await retriever.retrieve(
                payload.query,
                knowledge_base_id=knowledge_base_id,
                limit=payload.limit,
            )
        finally:
            await retriever.close()
    except ResourceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    

@knowledge_bases_router.post(
    "/{knowledge_base_id}/graph/search",
    response_model=list[GraphSearchResultRead],
)
async def search_knowledge_base_graph(
    knowledge_base_id: str,
    payload: SearchRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> list[GraphSearchResultRead]:
    """Find document chunks related through recognized graph entities."""
    try:
        await KnowledgeService(session).list_documents(knowledge_base_id)

        graph_store = build_neo4j_graph_store(request.app.state.settings)
        try:
            retriever = GraphRetriever(
                graph_store=graph_store,
                entity_extractor=RuleBasedEntityExtractor(),
            )
            chunks = await retriever.retrieve(
                payload.query,
                knowledge_base_id=knowledge_base_id,
                limit=payload.limit,
            )
            return [
                GraphSearchResultRead(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    knowledge_base_id=chunk.knowledge_base_id,
                    source_name=chunk.source_name,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                )
                for chunk in chunks
            ]
        finally:
            await graph_store.close()
    except ResourceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
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


@documents_router.post(
    "/{document_id}/index",
    response_model=DocumentIndexTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_document_index(
    document_id: str,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> DocumentIndexTaskRead:
    """Validate a document, then queue its indexing work for Celery."""
    try:
        await KnowledgeService(session).get_document(document_id)
        task_id = enqueue_document_index(
            document_id,
            actor=actor,
        )
        return DocumentIndexTaskRead(
            document_id=document_id,
            task_id=task_id,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
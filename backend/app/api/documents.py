from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.schemas.document import DocumentImport, Question
from app.services import documents
from app.services.document_ai import WorkflowError
from app.services.document_workflow import answer_question


def create_document_router(sessions, settings):
    router = APIRouter(prefix="/api")

    @router.get("/ai/providers")
    def providers():
        return {
            "providers": [
                {
                    "id": "openai",
                    "online": True,
                    "configured": bool(settings.openai_api_key),
                    "models": list(settings.openai_models),
                    "default_model": settings.openai_model,
                    "status": "configured_unverified"
                    if settings.openai_api_key
                    else "missing_api_key",
                }
            ],
            "local_status": "Development mock only; no local document model installed",
        }

    @router.get("/documents")
    def library():
        return documents.list_documents(sessions)

    @router.post("/documents", status_code=201)
    async def import_file(request: Request):
        body = bytearray()
        async for part in request.stream():
            body.extend(part)
            if len(body) > 14_100_000:
                raise WorkflowError(
                    "document_too_large", "Import request is too large.", 413
                )
        try:
            payload = DocumentImport.model_validate_json(body)
        except ValidationError:
            # Input validation errors can contain the entire uploaded document.
            raise WorkflowError(
                "invalid_document",
                "Provide title, format (text/pdf) and valid content within import limits.",
                422,
            ) from None
        return await run_in_threadpool(documents.import_document, sessions, payload)

    @router.post("/documents/{document_id}/questions")
    def question(document_id: UUID, payload: Question, request: Request):
        return answer_question(
            sessions,
            str(document_id),
            payload,
            request.app.state.document_providers.get(payload.provider),
        )

    return router

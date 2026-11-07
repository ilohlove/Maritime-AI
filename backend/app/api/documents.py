from uuid import UUID

from fastapi import APIRouter, Request
from starlette.responses import Response
from app.services.auth import rate_limit
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.core.disposable import SYNTHETIC_DOCUMENT
from app.schemas.document import DocumentImport, Question
from app.services import documents
from app.services.document_ai import WorkflowError
from app.services.document_workflow import answer_question


def create_document_router(sessions, settings):
    router = APIRouter(prefix="/api")

    @router.get("/ai/providers")
    def providers():
        return {
            "mode": settings.mode,
            "upload_max_bytes": settings.upload_bytes,
            "upload_max_pages": 50 if settings.online_mvp_mode else 300,
            "disposable_test_mode": settings.disposable_test_mode,
            "synthetic_document": SYNTHETIC_DOCUMENT
            if settings.disposable_test_mode
            else None,
            "providers": [
                {
                    "id": "openai",
                    "online": True,
                    "configured": bool(settings.openai_api_key)
                    and not settings.disposable_test_mode
                    and (not settings.online_mvp_mode or settings.ai_enabled),
                    "models": list(settings.openai_models),
                    "default_model": settings.openai_model,
                    "status": "disabled_disposable"
                    if settings.disposable_test_mode
                    else "disabled_online"
                    if settings.online_mvp_mode and not settings.ai_enabled
                    else "configured_unverified"
                    if settings.openai_api_key
                    else "missing_api_key",
                }
            ],
            "local_status": "Development mock only; no local document model installed",
        }

    @router.get("/documents")
    def library(request: Request):
        return documents.list_documents(
            sessions, request.state.user, not settings.online_mvp_mode
        )

    @router.post("/documents", status_code=201)
    async def import_file(request: Request):
        body = bytearray()
        async for part in request.stream():
            body.extend(part)
            if len(body) > settings.upload_request_bytes:
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
        if settings.disposable_test_mode and payload.model_dump() != SYNTHETIC_DOCUMENT:
            raise WorkflowError(
                "synthetic_fixture_required",
                "Disposable mode accepts only the exact bundled synthetic sample.",
                422,
            )
        if settings.online_mvp_mode:
            await run_in_threadpool(
                rate_limit,
                request.app.state.engine,
                "upload:" + request.state.user,
                settings.upload_rate_limit,
            )
        slot = request.app.state.upload_slot
        if not slot.acquire(blocking=False):
            raise WorkflowError(
                "upload_busy",
                "Another document is being processed. Retry shortly.",
                429,
            )
        try:
            return await run_in_threadpool(
                documents.import_document,
                sessions,
                payload,
                owner=request.state.user,
                storage=request.app.state.storage,
                settings=settings,
            )
        finally:
            slot.release()

    @router.delete("/documents/{document_id}")
    def delete_file(document_id: UUID, request: Request):
        # A second tab must not remove a pending row while its PUT is in flight.
        slot = request.app.state.upload_slot
        if not slot.acquire(blocking=False):
            raise WorkflowError(
                "upload_busy", "Document processing is in progress. Retry shortly.", 429
            )
        try:
            return documents.delete_document(
                sessions,
                str(document_id),
                request.state.user,
                request.app.state.storage,
                not settings.online_mvp_mode,
            )
        finally:
            slot.release()

    @router.get("/documents/{document_id}/original")
    def original(document_id: UUID, request: Request):
        content = documents.read_original(
            sessions,
            str(document_id),
            request.state.user,
            request.app.state.storage,
            not settings.online_mvp_mode,
        )
        return Response(
            content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{document_id}.bin"',
                "Content-Security-Policy": "sandbox; default-src 'none'",
            },
        )

    @router.get("/documents/{document_id}/excerpts/{excerpt_id}")
    def excerpt(document_id: UUID, excerpt_id: int, request: Request):
        return documents.inspect_excerpt(
            sessions,
            str(document_id),
            excerpt_id,
            request.state.user,
            not settings.online_mvp_mode,
        )

    @router.get("/documents/{document_id}/search")
    def search(document_id: UUID, request: Request, q: str = ""):
        if not 1 <= len(q.strip()) <= 2000:
            raise WorkflowError(
                "invalid_query", "Provide a search query of 1–2000 characters.", 422
            )
        documents.get_document(
            sessions, str(document_id), request.state.user, not settings.online_mvp_mode
        )
        return [
            {"excerpt_id": e.id, "page": e.page, "text": e.text}
            for e in documents.retrieve(sessions, str(document_id), [q])
        ]

    @router.get("/ai/usage")
    def usage(request: Request):
        return request.app.state.ai_guard.usage(request.state.user)

    @router.post("/documents/{document_id}/questions")
    def question(document_id: UUID, payload: Question, request: Request):
        if payload.provider == "openai" and payload.model not in settings.openai_models:
            raise WorkflowError("invalid_model", "Select a configured model.", 422)
        return answer_question(
            sessions,
            str(document_id),
            payload,
            request.app.state.document_providers.get(payload.provider),
            lambda: request.app.state.ai_guard.request(request.state.user),
            owner=request.state.user,
            allow_legacy=not settings.online_mvp_mode,
            usage_recorder=lambda model, usage: request.app.state.ai_guard.record_usage(
                request.state.user, model, usage
            ),
        )

    return router

import asyncio
import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.services.ai import ProviderError
from app.services.documents import MAX_UPLOAD, extract_pdf, retrieve, store_document


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    document_id: UUID
    question: str = Field(min_length=3, max_length=500)
    mode: str = "local_only"


def create_workspace_router(engine, directory: Path, provider):
    router = APIRouter(prefix="/api")
    running = {}

    def get_document(document_id: UUID):
        with engine.connect() as connection:
            result = connection.execute(text("SELECT * FROM documents WHERE id=:id"), {"id": str(document_id)}).mappings().first()
            if not result:
                raise HTTPException(404, "Document not found")
            return dict(result)

    @router.get("/ai/status")
    def status():
        ready, detail = provider.availability()
        return {"mode": "local_only", "provider": provider.name, "configured": ready, "detail": detail,
                "unavailable_modes": ["online", "auto"]}

    @router.get("/documents")
    def documents():
        with engine.connect() as connection:
            return [dict(row) for row in connection.execute(text("SELECT * FROM documents ORDER BY created_at DESC")).mappings()]

    @router.post("/documents", status_code=201)
    async def upload(request: Request, filename: str = Query(min_length=1, max_length=200)):
        if not filename.lower().endswith(".pdf") or request.headers.get("content-type", "").split(";")[0] != "application/pdf":
            raise HTTPException(415, "Import a PDF file with application/pdf content type.")
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_UPLOAD:
                raise HTTPException(413, "PDF exceeds the 10 MiB size limit.")
        if not data.startswith(b"%PDF-"):
            raise HTTPException(422, "Invalid PDF signature.")
        document_id = str(uuid4())
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{document_id}.pdf"
        try:
            with path.open("xb") as file:
                file.write(data)
            pages = await extract_pdf(path)
            # User filenames are labels only and never used as storage paths.
            name = filename.replace("\\", "/").split("/")[-1]
            name = re.sub(r"[\x00-\x1f\x7f]", "", name) or "document.pdf"
            record = store_document(engine, document_id, name, bytes(data), pages)
            return record
        except ValueError as error:
            path.unlink(missing_ok=True)
            raise HTTPException(422, str(error)) from None
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    @router.get("/documents/{document_id}/pages/{page_number}")
    def page(document_id: UUID, page_number: int):
        document = get_document(document_id)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT text FROM document_pages WHERE document_id=:id AND page_number=:page"),
                                        {"id": str(document_id), "page": page_number}).scalar_one_or_none()
        if result is None:
            raise HTTPException(404, "Page not found")
        return {"document_id": str(document_id), "document_name": document["name"], "page_number": page_number, "text": result}

    @router.get("/documents/{document_id}/file")
    def file(document_id: UUID):
        document = get_document(document_id)
        path = directory / f"{document_id}.pdf"
        if not path.is_file():
            raise HTTPException(404, "Stored PDF is missing. Reimport the source.")
        return FileResponse(path, media_type="application/pdf", filename=document["name"],
                            headers={"X-Content-Type-Options": "nosniff"})

    @router.post("/questions/{request_id}/cancel")
    async def cancel(request_id: UUID):
        task = running.get(str(request_id))
        if task:
            task.cancel()
        return {"cancelled": task is not None}

    @router.post("/questions")
    async def ask(payload: Question, request: Request):
        if payload.mode != "local_only":
            raise HTTPException(422, "Only Local Only mode is available. No cloud fallback.")
        get_document(payload.document_id)
        evidence = retrieve(engine, str(payload.document_id), payload.question)
        insufficient = {"status": "insufficient_evidence", "answer": "Insufficient document evidence / Không đủ bằng chứng trong tài liệu.", "citations": [], "provider": provider.name}
        if not evidence:
            return insufficient
        key = str(payload.request_id)
        if key in running:
            raise HTTPException(409, "Request ID is already running")
        task = asyncio.create_task(provider.answer(payload.question, evidence))
        running[key] = task
        try:
            while not task.done():
                if await request.is_disconnected():
                    task.cancel()
                    raise asyncio.CancelledError
                await asyncio.wait({task}, timeout=0.2)
            result = await task
            if not result.supported:
                return insufficient
            sources = {item["id"]: item for item in evidence}
            if not result.answer.strip() or not result.citations:
                raise ProviderError("The model supplied no supporting citations. No answer was accepted.")
            citations = []
            for citation in result.citations:
                source = sources.get(citation.id)
                if source is None or len(citation.quote.strip()) < 8 or citation.quote not in source["excerpt"]:
                    raise ProviderError("Citation integrity check failed. No answer was accepted.")
                citations.append({**source, "quote": citation.quote})
            return {"status": "answered", "answer": result.answer, "citations": citations,
                    "provider": provider.name, "notice": "AI interpretation grounded in document excerpts. Verify claims against the source; this is not navigational advice."}
        except ProviderError as error:
            raise HTTPException(503, str(error)) from None
        except asyncio.CancelledError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise HTTPException(499, "Inference cancelled") from None
        finally:
            running.pop(key, None)

    return router

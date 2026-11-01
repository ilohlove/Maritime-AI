import asyncio
import hashlib
import json
import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.services.ai import ProviderError
from app.schemas.extraction import DocumentMetadata, ExtractionFile, initial_revision_id
from app.services.documents import MAX_UPLOAD, extract_document, store_document


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    document_id: UUID
    question: str = Field(min_length=3, max_length=500)
    mode: str = "local_only"


def create_workspace_router(engine, directory: Path, provider, retrieval):
    router = APIRouter(prefix="/api")
    running = {}

    def get_document(document_id: UUID):
        with engine.connect() as connection:
            result = connection.execute(text("""SELECT d.*, r.id AS revision_id,r.source_format,r.business_version,r.effective_date,
                r.extraction_status,r.extraction_errors,r.media_type,r.storage_name FROM documents d
                JOIN document_revisions r ON r.document_id=d.id WHERE d.id=:id"""), {"id": str(document_id)}).mappings().first()
            if not result:
                raise HTTPException(404, "Document not found")
            return {**dict(result), "extraction_errors": json.loads(result["extraction_errors"])}

    @router.get("/ai/status")
    def status():
        ready, detail = provider.availability()
        return {"mode": "local_only", "provider": provider.name, "configured": ready, "detail": detail,
                "unavailable_modes": ["online", "auto"]}

    @router.get("/retrieval/status")
    def retrieval_status():
        return dict(retrieval.last_status)

    @router.post("/documents/{document_id}/index")
    async def index(document_id: UUID):
        get_document(document_id)
        return await retrieval.index_document(str(document_id))

    @router.get("/documents")
    def documents():
        with engine.connect() as connection:
            rows = connection.execute(text("""SELECT d.*,r.id AS revision_id,r.source_format,
                r.business_version,r.effective_date,r.extraction_status,r.extraction_errors FROM documents d
                JOIN document_revisions r ON r.document_id=d.id ORDER BY d.created_at DESC""")).mappings()
            return [{**dict(row), "extraction_errors": json.loads(row["extraction_errors"])} for row in rows]

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
            # User filenames are labels only and never used as storage paths.
            name = filename.replace("\\", "/").split("/")[-1]
            name = re.sub(r"[\x00-\x1f\x7f]", "", name) or "document.pdf"
            metadata = DocumentMetadata(document_id=document_id, revision_id=initial_revision_id(document_id),
                name=name, source_format='pdf', media_type='application/pdf',
                sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))
            result = await extract_document(ExtractionFile(path=path, metadata=metadata))
            if result.status == 'failed':
                raise ValueError(result.errors[0].message)
            record = store_document(engine, result)
            # Indexing failure cannot remove an already committed source document.
        except ValueError as error:
            path.unlink(missing_ok=True)
            raise HTTPException(422, str(error)) from None
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        record['semantic_index'] = await retrieval.index_document(document_id)
        return record

    @router.get("/documents/{document_id}/pages/{page_number}")
    def page(document_id: UUID, page_number: int):
        document = get_document(document_id)
        with engine.connect() as connection:
            row = connection.execute(text("""SELECT id,text,locator FROM content_units
                WHERE revision_id=:rid AND json_extract(locator,'$.kind')='page'
                AND json_extract(locator,'$.page_number')=:page"""),
                {"rid": document['revision_id'], "page": page_number}).mappings().first()
        if row is None:
            raise HTTPException(404, "Page not found")
        return {"document_id": str(document_id), "document_name": document['name'],
                "page_number": page_number, "text": row['text'], "revision_id": document['revision_id'],
                "unit_id": row['id'], "locator": json.loads(row['locator'])}

    @router.get("/documents/{document_id}/revisions/{revision_id}/units/{unit_id}")
    def unit(document_id: UUID, revision_id: UUID, unit_id: UUID):
        with engine.connect() as connection:
            row = connection.execute(text("""SELECT u.*,d.name AS document_name,r.document_id,r.source_format
                FROM content_units u JOIN document_revisions r ON r.id=u.revision_id
                JOIN documents d ON d.id=r.document_id
                WHERE d.id=:did AND r.id=:rid AND u.id=:uid"""),
                {"did": str(document_id), "rid": str(revision_id), "uid": str(unit_id)}).mappings().first()
        if row is None:
            raise HTTPException(404, "Source unit not found for this document revision")
        return {"document_id": str(document_id), "revision_id": str(revision_id), "unit_id": str(unit_id),
                "document_name": row['document_name'], "source_format": row['source_format'],
                "kind": row['kind'], "locator": json.loads(row['locator']), "text": row['text'],
                "table": json.loads(row['table_content']) if row['table_content'] else None}

    @router.get("/documents/{document_id}/file")
    def file(document_id: UUID):
        document = get_document(document_id)
        path = directory / document["storage_name"]
        if not path.is_file():
            raise HTTPException(404, "Stored PDF is missing. Reimport the source.")
        return FileResponse(path, media_type=document["media_type"], filename=document["name"],
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
        async def generate():
            evidence, retrieval_info = await retrieval.search(str(payload.document_id), payload.question)
            insufficient = {"status": "insufficient_evidence", "answer": "Insufficient document evidence / Không đủ bằng chứng trong tài liệu.",
                            "citations": [], "provider": provider.name, "retrieval": retrieval_info,
                            "notice": retrieval_info.get("notice", "")}
            if not evidence:
                return insufficient
            result = await provider.answer(payload.question, evidence)
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
                    "retrieval": retrieval_info, "provider": provider.name, "notice": retrieval_info.get("notice", "") + " AI interpretation grounded in document excerpts. Verify claims against the source; this is not navigational advice."}

        key = str(payload.request_id)
        if key in running:
            raise HTTPException(409, "Request ID is already running")
        task = asyncio.create_task(generate())
        running[key] = task
        try:
            while not task.done():
                if await request.is_disconnected():
                    task.cancel()
                    raise asyncio.CancelledError
                await asyncio.wait({task}, timeout=0.2)
            return await task
        except ProviderError as error:
            raise HTTPException(503, str(error)) from None
        except asyncio.CancelledError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise HTTPException(499, "Inference cancelled") from None
        finally:
            running.pop(key, None)

    return router

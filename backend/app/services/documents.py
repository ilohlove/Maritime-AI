import asyncio
import json
import re
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from app.schemas.extraction import ExtractionFile, ExtractionResult, ExtractionError, PageLocator

MAX_UPLOAD = 10 * 1024 * 1024
STOP_WORDS = set("a an the is are what when where how which of to in on for and or does do this document please tell me about la gi nao cua cac nhung cho toi ve trong va hay bao nhieu duoc phai can mot tai lieu".split())


def normalize(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", value.lower().replace("đ", "d")) if not unicodedata.combining(c))


async def extract_document(file: ExtractionFile) -> ExtractionResult:
    if file.metadata.source_format != 'pdf':
        return ExtractionResult(metadata=file.metadata, status='failed', errors=[
            ExtractionError(code='unsupported_format', message='Only PDF extraction is supported.')])
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "app.services.pdf_worker",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(file.model_dump_json().encode()), timeout=30)
        result = ExtractionResult.model_validate_json(stdout)
        if result.metadata != file.metadata:
            raise ValueError('Extractor changed source identity')
        return result
    except (TimeoutError, ValueError):
        return ExtractionResult(metadata=file.metadata, status='failed', errors=[ExtractionError(
            code='extraction_failed', message='PDF extraction failed or exceeded 30 seconds. Use a smaller text-based PDF.')])
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


def store_document(engine, result: ExtractionResult):
    if result.status == 'failed':
        raise ValueError('Failed extraction cannot be indexed')
    meta = result.metadata
    # Legacy counter counts PDF page units only; generic units do not acquire fake pages.
    page_count = sum(isinstance(unit.locator, PageLocator) for unit in result.units)
    record = {"id": str(meta.document_id), "name": meta.name, "page_count": page_count,
              "size_bytes": meta.size_bytes, "sha256": meta.sha256,
              "created_at": datetime.now(UTC).isoformat()}
    revision = {"rid": str(meta.revision_id), "did": str(meta.document_id),
                "format": meta.source_format, "mime": meta.media_type, "sha": meta.sha256,
                "size": meta.size_bytes, "file": f"{meta.document_id}.{meta.source_format}",
                "version": meta.business_version, "effective": meta.effective_date.isoformat() if meta.effective_date else None,
                "status": result.status, "errors": json.dumps([error.model_dump(mode='json') for error in result.errors]),
                "extractor": result.extractor}
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO documents
            (id,name,page_count,size_bytes,sha256,created_at)
            VALUES (:id,:name,:page_count,:size_bytes,:sha256,:created_at)"""), record)
        connection.execute(text("""INSERT INTO document_revisions
            (id,document_id,source_format,media_type,sha256,size_bytes,storage_name,
            business_version,effective_date,extraction_status,extraction_errors,extractor)
            VALUES (:rid,:did,:format,:mime,:sha,:size,:file,:version,:effective,:status,:errors,:extractor)"""), revision)
        for position, unit in enumerate(result.units, 1):
            connection.execute(text("""INSERT INTO content_units
                (id,revision_id,position,kind,locator,text,table_content)
                VALUES (:uid,:rid,:position,:kind,:locator,:text,:table)"""),
                {"uid": str(unit.id), "rid": str(meta.revision_id), "position": position,
                 "kind": unit.kind, "locator": unit.locator.model_dump_json(), "text": unit.text,
                 "table": unit.table.model_dump_json() if unit.table else None})
            number = unit.locator.page_number if isinstance(unit.locator, PageLocator) else None
            if number is not None:
                connection.execute(text("INSERT INTO document_pages VALUES (:id,:page,:text)"),
                                   {"id": str(meta.document_id), "page": number, "text": unit.text})
            for start in range(0, len(unit.text), 500):
                excerpt = unit.text[start:start + 700]
                chunk = connection.execute(text("""INSERT INTO document_chunks
                    (document_id,revision_id,unit_id,page_number,excerpt)
                    VALUES (:id,:rid,:uid,:page,:excerpt)"""),
                    {"id": str(meta.document_id), "rid": str(meta.revision_id), "uid": str(unit.id), "page": number, "excerpt": excerpt})
                connection.execute(text("INSERT INTO document_search(chunk_id,normalized) VALUES (:id,:value)"),
                                   {"id": chunk.lastrowid, "value": normalize(excerpt)})
    return {**record, "revision_id": str(meta.revision_id), "source_format": meta.source_format,
            "business_version": meta.business_version, "effective_date": revision['effective'],
            "extraction_status": result.status, "extraction_errors": [error.model_dump(mode='json') for error in result.errors]}


def retrieve(engine, document_id: str, question: str, limit: int = 3) -> list[dict]:
    words = list(dict.fromkeys(word for word in re.findall(r"\w+", normalize(question))
                              if word not in STOP_WORDS and len(word) > 1))[:16]
    if not words:
        return []
    query = " OR ".join('"' + word + '"' for word in words)
    with engine.connect() as connection:
        rows = connection.execute(text("""SELECT c.id,c.page_number,c.excerpt,d.name,c.revision_id,c.unit_id,u.locator,r.source_format
            FROM document_search s JOIN document_chunks c ON c.id=s.chunk_id
            JOIN documents d ON d.id=c.document_id
            JOIN content_units u ON u.id=c.unit_id AND u.revision_id=c.revision_id
            JOIN document_revisions r ON r.id=c.revision_id AND r.document_id=d.id
            WHERE document_search MATCH :query AND c.document_id=:id
            ORDER BY bm25(document_search), c.id LIMIT :limit"""), {"query": query, "id": document_id, "limit": limit}).mappings()
        return [{"id": f"E{row['id']}", "document_id": document_id, "document_name": row["name"],
                 "page_number": row["page_number"], "excerpt": row["excerpt"],
                 "revision_id": row["revision_id"], "unit_id": row["unit_id"],
                 "source_format": row["source_format"], "locator": json.loads(row["locator"])} for row in rows]

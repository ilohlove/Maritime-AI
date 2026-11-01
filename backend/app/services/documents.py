import asyncio
import hashlib
import json
import re
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

MAX_UPLOAD = 10 * 1024 * 1024
STOP_WORDS = set("a an the is are what when where how which of to in on for and or does do this document please tell me about la gi nao cua cac nhung cho toi ve trong va hay bao nhieu duoc phai can mot tai lieu".split())


def normalize(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", value.lower().replace("đ", "d")) if not unicodedata.combining(c))


async def extract_pdf(path: Path) -> list[str]:
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "app.services.pdf_worker", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
        result = json.loads(stdout)
        if "error" in result:
            raise ValueError(result["error"])
        return result["pages"]
    except (TimeoutError, json.JSONDecodeError):
        raise ValueError("PDF extraction failed or exceeded 30 seconds. Use a smaller text-based PDF.") from None
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


def store_document(engine, document_id: str, name: str, data: bytes, pages: list[str]):
    record = {"id": document_id, "name": name, "page_count": len(pages),
              "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
              "created_at": datetime.now(UTC).isoformat()}
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO documents
            (id,name,page_count,size_bytes,sha256,created_at)
            VALUES (:id,:name,:page_count,:size_bytes,:sha256,:created_at)"""), record)
        for number, value in enumerate(pages, 1):
            connection.execute(text("INSERT INTO document_pages VALUES (:id,:page,:text)"),
                               {"id": document_id, "page": number, "text": value})
            # Fixed overlapping windows retain exact source text; at most 3 are retrieved.
            for start in range(0, len(value), 500):
                excerpt = value[start:start + 700]
                result = connection.execute(text("""INSERT INTO document_chunks
                    (document_id,page_number,excerpt) VALUES (:id,:page,:excerpt)"""),
                    {"id": document_id, "page": number, "excerpt": excerpt})
                connection.execute(text("INSERT INTO document_search(chunk_id,normalized) VALUES (:id,:value)"),
                                   {"id": result.lastrowid, "value": normalize(excerpt)})
    return record


def retrieve(engine, document_id: str, question: str) -> list[dict]:
    words = list(dict.fromkeys(word for word in re.findall(r"\w+", normalize(question))
                              if word not in STOP_WORDS and len(word) > 1))[:16]
    if not words:
        return []
    query = " OR ".join('"' + word + '"' for word in words)
    with engine.connect() as connection:
        rows = connection.execute(text("""SELECT c.id,c.page_number,c.excerpt,d.name
            FROM document_search s JOIN document_chunks c ON c.id=s.chunk_id
            JOIN documents d ON d.id=c.document_id
            WHERE document_search MATCH :query AND c.document_id=:id
            ORDER BY bm25(document_search), c.id LIMIT 3"""), {"query": query, "id": document_id}).mappings()
        return [{"id": f"E{row['id']}", "document_id": document_id, "document_name": row["name"],
                 "page_number": row["page_number"], "excerpt": row["excerpt"]} for row in rows]

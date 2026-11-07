"""Local extraction, bounded lexical retrieval and citation integrity checks."""

import base64
import binascii
import os
import hashlib
import json
import subprocess
import sys
import re
from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4

from pypdf import PdfReader
from sqlalchemy import select, text, delete, func, or_
from sqlalchemy.exc import SQLAlchemyError

from app.models.document import Document, DocumentChunk
from app.schemas.document import DocumentImport
from app.services.document_ai import Excerpt, WorkflowError

MAX_ORIGINAL_BYTES = 10_000_000
MAX_EXTRACTED_CHARS = 1_000_000
CHUNK_CHARS = 1600
MAX_CONTEXT_CHARS = 9600
STOP_WORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "how",
        "of",
        "for",
        "to",
        "in",
        "on",
        "and",
        "or",
        "does",
        "do",
        "this",
        "that",
        "document",
        "please",
        "tell",
        "me",
        "i",
        "about",
        "it",
        "can",
        "be",
        "co",
        "la",
        "gi",
        "va",
        "cua",
        "toi",
        "trong",
        "cho",
        "nao",
        "hay",
        "nhu",
        "mot",
        "nhung",
        "duoc",
        "voi",
    ]
)


def extract(
    payload: DocumentImport,
    max_bytes=MAX_ORIGINAL_BYTES,
    max_pages=300,
    max_chars=MAX_EXTRACTED_CHARS,
) -> tuple[bytes, list[tuple[int, str]]]:
    try:
        original = (
            base64.b64decode(payload.content, validate=True)
            if payload.format == "pdf"
            else payload.content.encode("utf-8")
        )
    except (ValueError, binascii.Error):
        raise WorkflowError(
            "invalid_document", "PDF content must be valid base64.", 422
        ) from None
    if len(original) > max_bytes:
        raise WorkflowError(
            "document_too_large",
            f"Original file must be at most {max_bytes} bytes.",
            413,
        )
    pages = []
    total = 0
    try:
        if payload.format == "pdf":
            if not original.startswith(b"%PDF-"):
                raise ValueError("Not a PDF")
            reader = PdfReader(BytesIO(original))
            if reader.is_encrypted or len(reader.pages) > max_pages:
                raise WorkflowError(
                    "invalid_document",
                    f"Use an unencrypted PDF of at most {max_pages} pages.",
                    422,
                )
            source = (
                (index + 1, page.extract_text() or "")
                for index, page in enumerate(reader.pages)
            )
        else:
            # Form feeds can represent pages in imported plain text.
            source = enumerate(payload.content.split("\f"), 1)
        for page, value in source:
            if page > max_pages:
                raise WorkflowError(
                    "invalid_document",
                    f"Document must have at most {max_pages} pages.",
                    422,
                )
            value = value.replace("\x00", "").strip()
            total += len(value)
            if total > max_chars:
                raise WorkflowError(
                    "document_too_large",
                    f"Extracted text must be at most {max_chars} characters.",
                    413,
                )
            pages.append((page, value))
    except WorkflowError:
        raise
    except Exception:  # noqa: BLE001 - sanitize parser-specific errors on untrusted PDFs
        raise WorkflowError(
            "invalid_document",
            "Cannot extract this PDF. Use a valid text-based PDF.",
            422,
        ) from None
    if not any(value for _, value in pages):
        raise WorkflowError(
            "no_extractable_text",
            "No readable text found. Scanned PDFs need OCR before import.",
            422,
        )
    return original, pages


def owner_filter(model, owner, allow_legacy=False):
    condition = model.owner_id == owner
    return or_(condition, model.owner_id.is_(None)) if allow_legacy else condition


def isolated_extract(payload):
    # Decoding is bounded before spawning; child stdout contains extracted text
    # and is consumed privately, never logged. No cloud credentials in child env.
    original = decode_original(payload, 3_000_000)
    child_env = {
        key: value
        for key, value in os.environ.items()
        if key
        in {"PATH", "SYSTEMROOT", "WINDIR", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP"}
    }
    try:
        result = subprocess.run(
            [sys.executable, "-m", "app.services.pdf_worker"],
            input=payload.model_dump_json().encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=20,
            env=child_env,
            check=False,
        )
        if result.returncode != 0:
            raise WorkflowError(
                "pdf_processing_limit", "PDF parser exceeded its resource limits.", 422
            )
        data = json.loads(result.stdout)
        if "error" in data:
            raise WorkflowError(*data["error"])
        return original, data["pages"]
    except subprocess.TimeoutExpired:
        raise WorkflowError(
            "pdf_processing_timeout", "PDF processing exceeded 20 seconds.", 422
        ) from None
    except (OSError, ValueError, KeyError):
        raise WorkflowError(
            "pdf_processing_failed", "PDF processing could not complete.", 422
        ) from None


def decode_original(payload, limit):
    try:
        original = (
            base64.b64decode(payload.content, validate=True)
            if payload.format == "pdf"
            else payload.content.encode()
        )
    except (ValueError, binascii.Error):
        raise WorkflowError(
            "invalid_document", "PDF content must be valid base64.", 422
        ) from None
    if len(original) > limit:
        raise WorkflowError(
            "document_too_large", f"Original must be at most {limit} bytes.", 413
        )
    return original


def metadata(document):
    return {
        key: getattr(document, key)
        for key in (
            "id",
            "title",
            "format",
            "created_at",
            "state",
            "byte_size",
            "page_count",
            "sha256",
        )
    }


def import_document(
    sessions,
    payload: DocumentImport,
    storage_dir=None,
    owner=None,
    storage=None,
    settings=None,
):
    from app.core.object_storage import LocalStorage

    storage = storage or LocalStorage(storage_dir)
    original, pages = (
        isolated_extract(payload)
        if settings and settings.online_mvp_mode
        else extract(payload)
    )
    document = Document(
        id=str(uuid4()),
        title=payload.title.strip(),
        format=payload.format,
        original=b"",
        owner_id=owner,
        state="pending",
        byte_size=len(original),
        page_count=max(p[0] for p in pages),
        sha256=hashlib.sha256(original).hexdigest(),
        created_at=datetime.now(UTC).isoformat(),
    )
    document.original_path = document.id + ".bin"
    try:
        # Persist the generated key BEFORE touching storage. An interrupted or
        # ambiguous PUT remains tracked, invisible to retrieval, and deletable.
        with sessions.begin() as session:
            if settings and settings.online_mvp_mode:
                count = session.scalar(
                    select(func.count())
                    .select_from(Document)
                    .where(Document.owner_id == owner)
                )
                total = session.scalar(select(func.count()).select_from(Document))
                if count >= settings.max_documents or total >= 100:
                    raise WorkflowError(
                        "document_quota",
                        "Document allowance reached. Delete old documents first.",
                        429,
                    )
            session.add(document)
        storage.put(document.original_path, original)
        with sessions.begin() as session:
            current = session.get(Document, document.id)
            for page, value in pages:
                for start in range(0, len(value), CHUNK_CHARS - 200):
                    session.add(
                        DocumentChunk(
                            document_id=document.id,
                            page=page,
                            text=value[start : start + CHUNK_CHARS],
                        )
                    )
            current.state = "ready"
        document.state = "ready"
    except (SQLAlchemyError, OSError):
        raise WorkflowError(
            "storage_unavailable",
            "Upload incomplete. Reload the library and delete the pending item before retrying.",
        ) from None
    return metadata(document)


def list_documents(sessions, owner=None, allow_legacy=False):
    try:
        with sessions() as session:
            query = select(Document).order_by(Document.created_at.desc())
            if owner is not None:
                query = query.where(owner_filter(Document, owner, allow_legacy))
            return [metadata(document) for document in session.scalars(query)]
    except SQLAlchemyError:
        raise WorkflowError(
            "storage_unavailable", "Cannot read the private library."
        ) from None


def load_owned(session, document_id, owner=None, allow_legacy=False, ready=True):
    query = select(Document).where(Document.id == document_id)
    if owner is not None:
        query = query.where(owner_filter(Document, owner, allow_legacy))
    document = session.scalar(query)
    if document is None:
        raise WorkflowError("document_not_found", "Document not found.", 404)
    if ready and document.state != "ready":
        raise WorkflowError(
            "document_not_ready",
            "Upload or deletion is incomplete. Delete the item and retry.",
            409,
        )
    return document


def get_document(sessions, document_id: str, owner=None, allow_legacy=False):
    try:
        with sessions() as session:
            document = load_owned(session, document_id, owner, allow_legacy)
            # Check index availability before contacting a paid provider.
            session.execute(
                text(
                    "SELECT rowid FROM document_fts LIMIT 1"
                    if session.bind.dialect.name == "sqlite"
                    else "SELECT search_vector FROM document_chunks LIMIT 1"
                )
            )
            return metadata(document)
    except SQLAlchemyError:
        raise WorkflowError(
            "retrieval_unavailable",
            "Document retrieval is unavailable. Check migrations and search index.",
        ) from None


def delete_document(sessions, document_id, owner, storage, allow_legacy=False):
    try:
        with sessions.begin() as session:
            document = load_owned(
                session, document_id, owner, allow_legacy, ready=False
            )
            key = document.original_path
            document.state = "deleting"
        if key:
            storage.delete(key)  # idempotent: retry also succeeds if object is gone
        with sessions.begin() as session:
            document = load_owned(
                session, document_id, owner, allow_legacy, ready=False
            )
            session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )
            session.delete(document)
    except SQLAlchemyError:
        raise WorkflowError(
            "storage_unavailable", "Deletion incomplete. Retry after storage recovery."
        ) from None
    return {"deleted": True}


def read_original(sessions, document_id, owner, storage, allow_legacy=False):
    with sessions() as session:
        document = load_owned(session, document_id, owner, allow_legacy)
        value = (
            storage.get(document.original_path)
            if document.original_path
            else document.original
        )
        if document.sha256 and hashlib.sha256(value).hexdigest() != document.sha256:
            raise WorkflowError(
                "storage_integrity_failed",
                "The original does not match its saved checksum.",
            )
        return value


def inspect_excerpt(sessions, document_id, excerpt_id, owner, allow_legacy=False):
    with sessions() as session:
        document = load_owned(session, document_id, owner, allow_legacy)
        chunk = session.scalar(
            select(DocumentChunk).where(
                DocumentChunk.id == excerpt_id, DocumentChunk.document_id == document_id
            )
        )
        if chunk is None:
            raise WorkflowError("excerpt_not_found", "Excerpt not found.", 404)
        return {
            "document_id": document.id,
            "title": document.title,
            "page": chunk.page,
            "excerpt_id": chunk.id,
            "text": chunk.text,
        }


def retrieve(sessions, document_id: str, queries: list[str]) -> list[Excerpt]:
    tokens = list(
        dict.fromkeys(
            token.lower()
            for token in re.findall(r"[^\W_]+", " ".join(queries), re.UNICODE)
            if len(token) > 1 and token.lower() not in STOP_WORDS
        )
    )[:80]
    if not tokens:
        return []
    match = " OR ".join('"' + token + '"' for token in tokens)
    try:
        with sessions() as session:
            sql = (
                "SELECT c.id,c.page,c.text FROM document_fts "
                "JOIN document_chunks c ON c.id=document_fts.rowid "
                "WHERE document_fts MATCH :query AND c.document_id=:document "
                "ORDER BY bm25(document_fts),c.id LIMIT 6"
            )
            if session.bind.dialect.name == "postgresql":
                # Each term is parsed as plain text by PostgreSQL; no tsquery syntax injection.
                sql = (
                    "SELECT c.id,c.page,c.text FROM document_chunks c, (SELECT "
                    + " || ".join(
                        f"plainto_tsquery('simple', :term{i})"
                        for i in range(len(tokens))
                    )
                    + " AS q) s WHERE c.document_id=:document AND c.search_vector @@ s.q ORDER BY ts_rank(c.search_vector,s.q) DESC,c.id LIMIT 6"
                )
            parameters = {"query": match, "document": document_id} | {
                f"term{i}": token for i, token in enumerate(tokens)
            }
            rows = session.execute(text(sql), parameters)
            excerpts = [
                Excerpt(row.id, row.page, row.text[:CHUNK_CHARS]) for row in rows
            ]
    except SQLAlchemyError:
        raise WorkflowError(
            "retrieval_unavailable",
            "Local retrieval failed. Check the FTS5 index and retry.",
        ) from None
    if sum(len(e.text) for e in excerpts) > MAX_CONTEXT_CHARS:
        raise WorkflowError(
            "retrieval_unavailable", "Retrieved context exceeded the allowed limit."
        )
    return excerpts

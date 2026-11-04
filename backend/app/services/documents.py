"""Local extraction, bounded lexical retrieval and citation integrity checks."""

import base64
import binascii
import os
import re
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader
from sqlalchemy import select, text
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


def extract(payload: DocumentImport) -> tuple[bytes, list[tuple[int, str]]]:
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
    if len(original) > MAX_ORIGINAL_BYTES:
        raise WorkflowError(
            "document_too_large", "Original file must be at most 10 MB.", 413
        )
    pages = []
    total = 0
    try:
        if payload.format == "pdf":
            if not original.startswith(b"%PDF-"):
                raise ValueError("Not a PDF")
            reader = PdfReader(BytesIO(original))
            if reader.is_encrypted or len(reader.pages) > 300:
                raise WorkflowError(
                    "invalid_document",
                    "Use an unencrypted PDF of at most 300 pages.",
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
            value = value.replace("\x00", "").strip()
            total += len(value)
            if total > MAX_EXTRACTED_CHARS:
                raise WorkflowError(
                    "document_too_large",
                    "Extracted text must be at most 1 million characters.",
                    413,
                )
            if value:
                pages.append((page, value))
    except WorkflowError:
        raise
    except Exception:  # noqa: BLE001 - sanitize parser-specific errors on untrusted PDFs
        raise WorkflowError(
            "invalid_document",
            "Cannot extract this PDF. Use a valid text-based PDF.",
            422,
        ) from None
    if not pages:
        raise WorkflowError(
            "no_extractable_text",
            "No readable text found. Scanned PDFs need OCR before import.",
            422,
        )
    return original, pages


def import_document(sessions, payload: DocumentImport, storage_dir: Path):
    original, pages = extract(payload)
    document = Document(
        id=str(uuid4()),
        title=payload.title.strip(),
        format=payload.format,
        original=b"",
        created_at=datetime.now(UTC).isoformat(),
    )
    filename = document.id + ".bin"
    destination = storage_dir / filename
    created = False
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, "wb") as file:
            file.write(original)
            file.flush()
            os.fsync(file.fileno())
        document.original_path = filename
        with sessions.begin() as session:
            session.add(document)
            session.flush()
            for page, value in pages:
                for start in range(0, len(value), CHUNK_CHARS - 200):
                    session.add(
                        DocumentChunk(
                            document_id=document.id,
                            page=page,
                            text=value[start : start + CHUNK_CHARS],
                        )
                    )
    except (SQLAlchemyError, OSError):
        try:
            if created:
                destination.unlink(missing_ok=True)
        except OSError:
            pass  # An orphan can be reconciled from the DB after storage recovery.
        raise WorkflowError(
            "storage_unavailable",
            "Cannot save the document. Check migrations and local storage.",
        ) from None
    return {
        "id": document.id,
        "title": document.title,
        "format": document.format,
        "created_at": document.created_at,
    }


def list_documents(sessions):
    try:
        with sessions() as session:
            return [
                dict(row)
                for row in session.execute(
                    select(
                        Document.id,
                        Document.title,
                        Document.format,
                        Document.created_at,
                    ).order_by(Document.created_at.desc())
                ).mappings()
            ]
    except SQLAlchemyError:
        raise WorkflowError(
            "storage_unavailable",
            "Cannot read the library. Check local storage and migrations.",
        ) from None


def get_document(sessions, document_id: str):
    try:
        with sessions() as session:
            row = (
                session.execute(
                    select(Document.id, Document.title).where(
                        Document.id == document_id
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise WorkflowError(
                    "document_not_found", "Select an imported document.", 404
                )
            # Check FTS before contacting the external provider.
            session.execute(text("SELECT rowid FROM document_fts LIMIT 1"))
            return dict(row)
    except SQLAlchemyError:
        raise WorkflowError(
            "retrieval_unavailable",
            "Local retrieval is unavailable. Check migrations and the FTS5 index.",
        ) from None


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
            rows = session.execute(
                text(
                    "SELECT c.id,c.page,c.text FROM document_fts "
                    "JOIN document_chunks c ON c.id=document_fts.rowid "
                    "WHERE document_fts MATCH :query AND c.document_id=:document "
                    "ORDER BY bm25(document_fts),c.id LIMIT 6"
                ),
                {"query": match, "document": document_id},
            )
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

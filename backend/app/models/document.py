from sqlalchemy import ForeignKey, Index, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    format: Mapped[str] = mapped_column(String(10))
    original: Mapped[bytes] = mapped_column(LargeBinary)
    original_path: Mapped[str | None] = mapped_column(String(80), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[str] = mapped_column(
        String(16), default="ready", server_default="ready"
    )
    byte_size: Mapped[int | None] = mapped_column(nullable=True)
    page_count: Mapped[int | None] = mapped_column(nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (Index("ix_chunks_document", "document_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    page: Mapped[int]
    text: Mapped[str] = mapped_column(Text)

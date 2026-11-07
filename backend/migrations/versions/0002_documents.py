"""Local document library and FTS5 index; vessel schema is unchanged."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("original", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False
        ),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
    )
    op.create_index("ix_chunks_document", "document_chunks", ["document_id"])
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            "CREATE VIRTUAL TABLE document_fts USING fts5(text, content='document_chunks', content_rowid='id', tokenize='unicode61 remove_diacritics 2')"
        )
        op.execute(
            "CREATE TRIGGER chunks_insert AFTER INSERT ON document_chunks BEGIN INSERT INTO document_fts(rowid,text) VALUES(new.id,new.text); END"
        )
        op.execute(
            "CREATE TRIGGER chunks_delete AFTER DELETE ON document_chunks BEGIN INSERT INTO document_fts(document_fts,rowid,text) VALUES('delete',old.id,old.text); END"
        )
        op.execute(
            "CREATE TRIGGER chunks_update AFTER UPDATE ON document_chunks BEGIN INSERT INTO document_fts(document_fts,rowid,text) VALUES('delete',old.id,old.text); INSERT INTO document_fts(rowid,text) VALUES(new.id,new.text); END"
        )


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        for name in ("chunks_insert", "chunks_delete", "chunks_update"):
            op.execute(f"DROP TRIGGER {name}")
        op.execute("DROP TABLE document_fts")
    op.drop_table("document_chunks")
    op.drop_table("documents")

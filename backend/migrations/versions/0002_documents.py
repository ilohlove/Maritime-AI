"""Local PDF evidence and FTS5 search; vessel storage is unchanged."""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE documents (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, page_count INTEGER NOT NULL,
        size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL)""")
    op.execute("""CREATE TABLE document_pages (
        document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        page_number INTEGER NOT NULL, text TEXT NOT NULL,
        PRIMARY KEY(document_id, page_number))""")
    op.execute("""CREATE TABLE document_chunks (
        id INTEGER PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        page_number INTEGER NOT NULL, excerpt TEXT NOT NULL)""")
    op.execute("CREATE INDEX chunks_document ON document_chunks(document_id)")
    op.execute("CREATE VIRTUAL TABLE document_search USING fts5(chunk_id UNINDEXED, normalized)")


def downgrade():
    op.execute("DROP TABLE document_search")
    op.execute("DROP TABLE document_chunks")
    op.execute("DROP TABLE document_pages")
    op.execute("DROP TABLE documents")

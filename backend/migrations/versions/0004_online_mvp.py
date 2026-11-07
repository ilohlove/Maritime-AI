"""Add ownership, recoverable object lifecycle, usage accounting and PG search."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("vessels", "documents"):
        # Never guess ownership of existing data. Offline mode retains legacy access.
        op.add_column(table, sa.Column("owner_id", sa.String(100), nullable=True))
        op.create_index(f"ix_{table}_owner_id", table, ["owner_id"])
    for column in (
        sa.Column("state", sa.String(16), nullable=False, server_default="ready"),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
    ):
        op.add_column("documents", column)
    for name in ("input_tokens", "output_tokens", "requests"):
        op.add_column(
            "ai_daily_usage",
            sa.Column(name, sa.BigInteger(), nullable=False, server_default="0"),
        )
    if op.get_bind().dialect.name == "postgresql":
        # Supabase may expose public-schema tables through its Data API. Deny
        # browser/database roles independently of backend HTTP authorization.
        tables = (
            "vessels",
            "documents",
            "document_chunks",
            "auth_sessions",
            "rate_windows",
            "ai_daily_usage",
            "alembic_version",
        )
        for table in tables:
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            op.execute(f'REVOKE ALL ON TABLE "{table}" FROM PUBLIC')
            for role in ("anon", "authenticated"):
                # Also renders with Alembic --sql; no catalog query during generation.
                op.execute(f"""DO $$ BEGIN
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN
                        EXECUTE 'REVOKE ALL ON TABLE "{table}" FROM "{role}"';
                    END IF;
                END $$""")
        op.add_column(
            "document_chunks",
            sa.Column(
                "search_vector",
                TSVECTOR(),
                sa.Computed("to_tsvector('simple'::regconfig, text)", persisted=True),
            ),
        )
        op.create_index(
            "ix_chunks_search",
            "document_chunks",
            ["search_vector"],
            postgresql_using="gin",
        )


def downgrade():
    # Empty disposable databases can exercise a full reversible migration chain.
    # Never discard live ownership, originals or accounting on rollback.
    connection = op.get_bind()
    if any(
        connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar()
        for table in ("vessels", "documents", "ai_daily_usage")
    ):
        raise RuntimeError(
            "Back up and restore a matching database and originals before downgrading online ownership/accounting"
        )
    if connection.dialect.name == "postgresql":
        op.drop_index("ix_chunks_search", table_name="document_chunks")
        op.drop_column("document_chunks", "search_vector")
    for table, columns in (
        ("ai_daily_usage", ("input_tokens", "output_tokens", "requests")),
        ("documents", ("state", "byte_size", "page_count", "sha256")),
    ):
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.drop_column(column)
    for table in ("vessels", "documents"):
        op.drop_index(f"ix_{table}_owner_id", table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_column("owner_id")

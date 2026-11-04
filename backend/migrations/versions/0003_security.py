"""Durable revocable sessions, rate windows, usage ledger and external originals."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("original_path", sa.String(80), nullable=True))
    op.create_table(
        "auth_sessions",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=False),
        sa.Column("csrf_digest", sa.String(64), nullable=False),
        sa.Column("credential_version", sa.String(64), nullable=False),
    )
    op.create_table(
        "rate_windows",
        sa.Column("key", sa.String(160), primary_key=True),
        sa.Column("window", sa.Integer(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
    )
    op.create_table(
        "ai_daily_usage",
        sa.Column("user_id", sa.String(100), primary_key=True),
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False),
    )


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text("SELECT count(*) FROM documents WHERE original_path IS NOT NULL")
        )
        .scalar()
    ):
        raise RuntimeError(
            "Back up and restore file-backed originals to SQLite before downgrading 0003"
        )
    op.drop_table("ai_daily_usage")
    op.drop_table("rate_windows")
    op.drop_table("auth_sessions")
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("original_path")

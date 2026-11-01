"""Persistent optional vectors, scoped to model identity and immutable chunks."""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('chunk_embeddings',
        sa.Column('chunk_id',sa.Integer(),sa.ForeignKey('document_chunks.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('model_id',sa.Text(),primary_key=True),
        sa.Column('content_sha256',sa.Text(),nullable=False),
        sa.Column('dimensions',sa.Integer(),nullable=False),
        sa.Column('vector',sa.LargeBinary(),nullable=False))


def downgrade():
    op.drop_table('chunk_embeddings')

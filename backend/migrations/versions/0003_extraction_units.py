"""Add immutable source revisions/units; retain original pages, chunk IDs and FTS."""
import json
from uuid import NAMESPACE_URL, uuid5

from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('document_revisions',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('document_id', sa.Text(), sa.ForeignKey('documents.id'), nullable=False, unique=True),
        sa.Column('source_format', sa.Text(), nullable=False),
        sa.Column('media_type', sa.Text(), nullable=False),
        sa.Column('sha256', sa.Text(), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('storage_name', sa.Text(), nullable=False),
        sa.Column('business_version', sa.Text(), nullable=True),
        sa.Column('effective_date', sa.Text(), nullable=True),
        sa.Column('extraction_status', sa.Text(), nullable=False),
        sa.Column('extraction_errors', sa.Text(), nullable=False),
        sa.Column('extractor', sa.Text(), nullable=True))
    op.create_table('content_units',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('revision_id', sa.Text(), sa.ForeignKey('document_revisions.id'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('locator', sa.Text(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('table_content', sa.Text(), nullable=True),
        sa.UniqueConstraint('revision_id', 'position'))
    connection = op.get_bind()
    for doc in connection.execute(sa.text('SELECT * FROM documents')).mappings().all():
        rid = str(uuid5(NAMESPACE_URL, f"maritime:{doc['id']}:revision:1"))
        connection.execute(sa.text('''INSERT INTO document_revisions
            (id,document_id,source_format,media_type,sha256,size_bytes,storage_name,
             business_version,effective_date,extraction_status,extraction_errors,extractor)
            VALUES (:rid,:did,'pdf','application/pdf',:sha,:size,:file,NULL,NULL,'ready','[]',NULL)'''),
            {'rid': rid, 'did': doc['id'], 'sha': doc['sha256'], 'size': doc['size_bytes'], 'file': doc['id']+'.pdf'})
        for page in connection.execute(sa.text('SELECT * FROM document_pages WHERE document_id=:id ORDER BY page_number'), {'id': doc['id']}).mappings():
            uid = str(uuid5(NAMESPACE_URL, f"maritime:{rid}:page:{page['page_number']}"))
            connection.execute(sa.text('''INSERT INTO content_units
                (id,revision_id,position,kind,locator,text,table_content)
                VALUES (:uid,:rid,:position,'text',:locator,:text,NULL)'''),
                {'uid': uid, 'rid': rid, 'position': page['page_number'], 'locator': json.dumps({'kind': 'page', 'page_number': page['page_number']}), 'text': page['text']})
    with op.batch_alter_table('document_chunks') as batch:
        batch.alter_column('page_number', existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column('revision_id', sa.Text(), nullable=True))
        batch.add_column(sa.Column('unit_id', sa.Text(), nullable=True))
        batch.create_foreign_key('fk_chunk_revision', 'document_revisions', ['revision_id'], ['id'])
        batch.create_foreign_key('fk_chunk_unit', 'content_units', ['unit_id'], ['id'])
    for row in connection.execute(sa.text('SELECT id,document_id,page_number FROM document_chunks')).mappings().all():
        rid = str(uuid5(NAMESPACE_URL, f"maritime:{row['document_id']}:revision:1"))
        uid = str(uuid5(NAMESPACE_URL, f"maritime:{rid}:page:{row['page_number']}"))
        connection.execute(sa.text('UPDATE document_chunks SET revision_id=:rid,unit_id=:uid WHERE id=:id'), {'rid':rid,'uid':uid,'id':row['id']})
    # No chunk, page, FTS entry, file or source text is deleted or rewritten.


def downgrade():
    # A legacy schema cannot represent non-page units. Refuse lossy conversion.
    connection = op.get_bind()
    if (connection.execute(sa.text('SELECT count(*) FROM document_chunks WHERE page_number IS NULL')).scalar()
        or connection.execute(sa.text("""SELECT count(*) FROM document_revisions
            WHERE source_format!='pdf' OR business_version IS NOT NULL OR effective_date IS NOT NULL
            OR extractor IS NOT NULL OR extraction_errors!='[]'""")).scalar()
        or connection.execute(sa.text("""SELECT count(*) FROM content_units
            WHERE kind!='text' OR json_extract(locator,'$.kind')!='page'""")).scalar()):
        raise RuntimeError('Cannot downgrade source metadata or non-page units without data loss')
    with op.batch_alter_table('document_chunks') as batch:
        batch.drop_constraint('fk_chunk_unit', type_='foreignkey')
        batch.drop_constraint('fk_chunk_revision', type_='foreignkey')
        batch.drop_column('unit_id')
        batch.drop_column('revision_id')
        batch.alter_column('page_number', existing_type=sa.Integer(), nullable=False)
    op.drop_table('content_units')
    op.drop_table('document_revisions')

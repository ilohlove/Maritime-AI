"""Synthetic contracts and legacy migration. No new file-format extractor."""
import hashlib
import json
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text

from app.core.config import Settings
from app.main import create_app
from app.schemas.extraction import (
    ContentUnit, DocumentMetadata, ExtractionError, ExtractionFile, ExtractionResult,
    PageLocator, RowsLocator, SectionLocator, SheetLocator, TableContent, initial_revision_id, pdf_unit_id,
)
from app.services.documents import extract_document, retrieve, store_document
from app.services.pdf_worker import PDFExtractor
from test_workspace import synthetic_pdf, upload, question, workspace  # fixture and synthetic helpers


def test_pdf_contract_status_and_identity(tmp_path):
    path = tmp_path / 'synthetic.pdf'
    data = synthetic_pdf(['', 'SYNTHETIC lifejacket inspections Friday.'])
    path.write_bytes(data)
    did = uuid4(); rid = initial_revision_id(did)
    meta = DocumentMetadata(document_id=did, revision_id=rid, name=path.name, source_format='pdf',
                            media_type='application/pdf', sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))
    file = ExtractionFile(path=path, metadata=meta)
    result = PDFExtractor().extract(file)
    assert result.status == 'partial'
    assert result.errors[0].code == 'page_without_text'
    assert result.units[0].text == ''
    assert result.units[1].locator == PageLocator(page_number=2)
    assert result.metadata.business_version is result.metadata.effective_date is None
    assert result.units[1].id == pdf_unit_id(rid, 2)
    assert PDFExtractor().extract(file) == result
    assert ExtractionResult.model_validate_json(result.model_dump_json()) == result
    path.write_bytes(b'not a PDF')
    failed = PDFExtractor().extract(file)
    assert failed.status == 'failed' and failed.errors and not failed.units


def test_revision_unit_resolution_and_quote_validation(workspace):
    client, provider, _ = workspace
    doc = upload(client).json()
    first = question(client, doc['id']).json()['citations'][0]
    assert first['revision_id'] == doc['revision_id']
    assert first['unit_id'] == str(pdf_unit_id(doc['revision_id'], 1))
    assert first['locator'] == {'kind': 'page', 'page_number': 1}
    url = f"/api/documents/{doc['id']}/revisions/{first['revision_id']}/units/{first['unit_id']}"
    unit = client.get(url).json()
    assert first['quote'] in unit['text']
    assert unit['revision_id'] == first['revision_id'] and unit['unit_id'] == first['unit_id']
    assert question(client, doc['id']).json()['citations'][0] == first
    other = upload(client).json()
    assert other['id'] != doc['id'] and other['revision_id'] != doc['revision_id']
    assert client.get(url.replace(doc['id'], other['id'])).status_code == 404
    assert client.get(url.replace(first['revision_id'], other['revision_id'])).status_code == 404
    assert client.get(url.replace(first['unit_id'], str(uuid4()))).status_code == 404
    provider.result = 'bad_quote'
    assert question(client, doc['id']).status_code == 503


@pytest.mark.parametrize('extension', ['docx','doc','xlsx','xls','txt','csv','md','png'])
def test_non_pdf_import_still_unsupported(workspace, extension):
    client, _, _ = workspace
    assert upload(client, filename='synthetic.'+extension).status_code == 415
    assert client.get('/api/documents').json() == []


def test_generic_units_and_tables_are_indexable_without_fake_pages(workspace):
    # Construct common content directly; this is NOT a CSV/XLSX extractor or import feature.
    client, _, app = workspace
    did = uuid4(); rid = uuid4(); uid = uuid4()
    table = TableContent(columns=['Item','Interval'], rows=[['Synthetic lifejacket','Friday']])
    meta = DocumentMetadata(document_id=did, revision_id=rid, name='synthetic-contract.csv', source_format='csv',
        media_type='text/csv', sha256='0'*64, size_bytes=0, business_version='TEST-REV-B', effective_date='2026-01-01')
    unit = ContentUnit(id=uid, kind='table', locator=RowsLocator(start=2,end=2),
                       text='Item | Interval\nSynthetic lifejacket | Friday', table=table)
    result = ExtractionResult(metadata=meta, status='ready', units=[unit])
    store_document(app.state.engine, result)
    evidence = retrieve(app.state.engine, str(did), 'lifejacket')[0]
    assert evidence['page_number'] is None and evidence['locator'] == {'kind':'rows','start':2,'end':2}
    assert evidence['unit_id'] == str(uid) and evidence['revision_id'] == str(rid)
    source = client.get(f'/api/documents/{did}/revisions/{rid}/units/{uid}').json()
    assert source['table'] == table.model_dump()
    assert client.get(f'/api/documents/{did}/pages/1').status_code == 404
    doc = client.get('/api/documents').json()[0]
    assert doc['business_version'] == 'TEST-REV-B' and doc['effective_date'] == '2026-01-01'
    with pytest.raises(ValidationError):
        TableContent(columns=['A'],rows=[['one','two']])
    with pytest.raises(ValidationError):
        RowsLocator(start=4,end=2)
    with pytest.raises(ValidationError):
        PageLocator(page_number=0)
    assert SectionLocator(heading='Safety',paragraph=3).kind == 'section'
    assert SheetLocator(sheet_name='Safety',cell_range='B2:C3').kind == 'sheet'


def test_unsupported_extractor_contract(tmp_path):
    import asyncio
    meta = DocumentMetadata(document_id=uuid4(),revision_id=uuid4(),name='synthetic.txt',source_format='txt',
                            media_type='text/plain',sha256='0'*64,size_bytes=0)
    result = asyncio.run(extract_document(ExtractionFile(path=tmp_path/'unused.txt',metadata=meta)))
    assert result.status == 'failed' and result.errors[0].code == 'unsupported_format'


def test_legacy_pdf_migration_preserves_files_pages_chunks_fts(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path/'legacy.db'}")
    app = create_app(settings)
    config = Config('alembic.ini')
    did = str(uuid4()); quote = 'SYNTHETIC lifejacket inspections Friday.'
    second = 'SYNTHETIC fire drill attendance.'
    data = synthetic_pdf([quote, second])
    directory = tmp_path/'documents'; directory.mkdir(); source = directory/f'{did}.pdf'; source.write_bytes(data)
    with app.state.engine.begin() as conn:
        config.attributes['connection'] = conn
        command.upgrade(config,'0002')
        conn.execute(text('INSERT INTO documents VALUES (:id,:name,2,:size,:sha,:created)'),
            {'id':did,'name':'synthetic-legacy.pdf','size':len(data),'sha':hashlib.sha256(data).hexdigest(),'created':'2026-01-01T00:00:00Z'})
        conn.execute(text('INSERT INTO document_pages VALUES (:id,1,:text)'),{'id':did,'text':quote})
        conn.execute(text('INSERT INTO document_pages VALUES (:id,2,:text)'),{'id':did,'text':second})
        conn.execute(text('INSERT INTO document_chunks VALUES (77,:id,2,:quote)'),{'id':did,'quote':second})
        conn.execute(text("INSERT INTO document_search VALUES (77,'synthetic fire drill attendance.')"))
        conn.execute(text('INSERT INTO document_chunks VALUES (42,:id,1,:quote)'),{'id':did,'quote':quote})
        conn.execute(text("INSERT INTO document_search VALUES (42,'synthetic lifejacket inspections friday.')"))
        old_pages = conn.execute(text('SELECT * FROM document_pages')).all()
        old_fts = conn.execute(text('SELECT rowid,* FROM document_search')).all()
        command.upgrade(config,'head')
        assert conn.execute(text('SELECT * FROM document_pages')).all() == old_pages
        assert conn.execute(text('SELECT rowid,* FROM document_search')).all() == old_fts
        chunk = conn.execute(text('SELECT * FROM document_chunks WHERE id=42')).mappings().one()
        assert chunk['excerpt'] == quote
        assert chunk['revision_id'] == str(initial_revision_id(did))
        assert chunk['unit_id'] == str(pdf_unit_id(chunk['revision_id'],1))
        assert conn.execute(text('PRAGMA foreign_key_check')).all() == []
    assert source.read_bytes() == data
    with TestClient(app) as client:
        doc = client.get('/api/documents').json()[0]
        assert doc['business_version'] is doc['effective_date'] is None
        page = client.get(f'/api/documents/{did}/pages/1').json()
        assert page['text'] == quote and page['page_number'] == 1
        evidence = retrieve(app.state.engine,did,'lifejacket')[0]
        assert evidence['id'] == 'E42' and evidence['excerpt'] == quote
        assert client.get(f"/api/documents/{did}/revisions/{evidence['revision_id']}/units/{evidence['unit_id']}").json()['text'] == quote
        assert client.get(f'/api/documents/{did}/file').content == data
    # Reversible for legacy PDFs: stable IDs on upgrade again, no source deletion.
    with app.state.engine.begin() as conn:
        config.attributes['connection'] = conn
        command.downgrade(config,'0002')
        assert conn.execute(text('SELECT id,excerpt FROM document_chunks ORDER BY id')).all() == [(42,quote),(77,second)]
        command.upgrade(config,'head')
        assert conn.execute(text('SELECT unit_id FROM document_chunks WHERE id=42')).scalar_one() == page['unit_id']
    assert source.read_bytes() == data


def test_downgrade_refuses_to_discard_new_extraction_metadata(workspace):
    client, _, app = workspace
    doc = upload(client).json()
    config = Config('alembic.ini')
    with app.state.engine.begin() as connection:
        config.attributes['connection'] = connection
        with pytest.raises(RuntimeError, match='without data loss'):
            command.downgrade(config,'0002')
        assert connection.execute(text('SELECT count(*) FROM content_units')).scalar() == 2
    assert client.get(f"/api/documents/{doc['id']}/pages/1").status_code == 200

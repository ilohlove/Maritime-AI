"""Deterministic vector fixtures test plumbing, never real multilingual quality."""
import asyncio
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import Settings
from app.main import create_app
from app.services.embeddings import EmbeddingError, LocalEmbeddingProvider, QUERY_INSTRUCTION
from app.services.hybrid_retrieval import HybridRetrieval, fuse
from conftest import migrate
from test_workspace import synthetic_pdf, upload, question, EvidenceProvider


class VectorFixture:
    def __init__(self, identity='fixture-v1'):
        self.model_id = identity
        self.calls = []
        self.fail = False

    def identity(self):
        if self.fail: raise EmbeddingError('Fixture unavailable')
        return self.model_id

    async def embed(self, texts, purpose):
        self.calls.append((purpose,list(texts)))
        if self.fail: raise EmbeddingError('Fixture failed')
        vectors = []
        for value in texts:
            lower = value.lower()
            # Explicit hand-coded oracle: NOT an embedding model or language evaluation.
            if 'lifejacket' in lower or 'áo phao' in lower: vectors.append([1.,0.,0.])
            elif 'drill' in lower: vectors.append([0.,1.,0.])
            else: vectors.append([0.,0.,1.])
        return vectors

    async def close(self): pass


@pytest.fixture
def hybrid(tmp_path):
    model = VectorFixture()
    settings = Settings(database_url=f"sqlite:///{tmp_path/'hybrid.db'}")
    app = create_app(settings, provider=EvidenceProvider(), embedding_provider=model)
    migrate(app)
    with TestClient(app) as client: yield client,app,model,settings


def test_incremental_persistent_index_and_model_identity(hybrid):
    client,app,model,settings = hybrid
    doc = upload(client).json()
    assert doc['semantic_index']['newly_indexed'] == 2
    count = len(model.calls)
    assert client.post(f"/api/documents/{doc['id']}/index",json={}).json()['newly_indexed'] == 0
    assert len(model.calls) == count
    with app.state.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM chunk_embeddings')).scalar() == 2
    # New app/provider reuses persisted vectors; only question embeddings are requested.
    fresh = VectorFixture()
    with TestClient(create_app(settings,provider=EvidenceProvider(),embedding_provider=fresh)) as restarted:
        result = question(restarted,doc['id'],'Áo phao được kiểm tra khi nào?').json()
        assert result['status'] == 'answered'
        assert [purpose for purpose,_ in fresh.calls] == ['query']
        citation = result['citations'][0]
        source = restarted.get(f"/api/documents/{doc['id']}/revisions/{citation['revision_id']}/units/{citation['unit_id']}").json()
        assert citation['quote'] in source['text']
        assert citation['locator'] == source['locator']
        assert citation['revision_id'] == doc['revision_id']
    # New model space never mixes old vectors.
    model.model_id = 'fixture-v2'
    state = client.post(f"/api/documents/{doc['id']}/index",json={}).json()
    assert state['newly_indexed'] == 2
    with app.state.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM chunk_embeddings')).scalar() == 4


def test_semantic_scope_threshold_and_lexical_fallback(hybrid):
    client,app,model,_ = hybrid
    doc = upload(client).json()
    other = upload(client,synthetic_pdf(['SYNTHETIC Fire drill records only.'])).json()
    result = question(client,doc['id'],'Áo phao được kiểm tra khi nào?').json()
    assert result['retrieval']['mode'] == 'hybrid'
    assert all(c['document_id'] == doc['id'] for c in result['citations'])
    assert question(client,other['id'],'Áo phao được kiểm tra khi nào?').json()['status'] == 'insufficient_evidence'
    # Missing vectors/model keeps the exact legacy FTS5 evidence path.
    model.fail = True
    english = question(client,doc['id'],'lifejacket inspections').json()
    assert english['status'] == 'answered' and english['retrieval']['mode'] == 'fts5'
    assert client.get('/api/vessels').json() == []
    assert client.get('/api/retrieval/status').json()['semantic'] == 'unavailable'


def test_failed_index_preserves_pdf_and_retries(hybrid):
    client,app,model,_ = hybrid
    model.fail = True
    doc = upload(client).json()
    assert doc['semantic_index']['mode'] == 'fts5'
    assert client.get(f"/api/documents/{doc['id']}/file").content.startswith(b'%PDF-')
    model.fail = False
    assert client.post(f"/api/documents/{doc['id']}/index",json={}).json()['newly_indexed'] == 2
    assert client.post(f'/api/documents/{uuid4()}/index',json={}).status_code == 404


def test_invalid_embeddings_do_not_break_fts(hybrid):
    client,app,model,_ = hybrid
    doc = upload(client).json()
    async def invalid(texts,purpose): return [[float('nan')]*3 for _ in texts]
    model.embed = invalid
    result = question(client,doc['id'],'lifejacket inspections').json()
    assert result['retrieval']['mode'] == 'fts5' and result['status'] == 'answered'


def test_rrf_dedup_and_tie_break():
    a,b,c = ({'id':f'E{i}'} for i in (1,2,3))
    assert [item['id'] for item in fuse([a,b],[b,c])] == ['E2','E1','E3']
    assert fuse([a],[a]) == [a]


def test_embedding_http_recipe(monkeypatch):
    real_client = httpx.AsyncClient
    seen = []
    def handler(request):
        import json
        seen.append(json.loads(request.content))
        return httpx.Response(200,json={'data':[{'index':0,'embedding':[3.,4.]}]})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs: real_client(**kwargs,transport=httpx.MockTransport(handler)))
    async def run():
        provider = LocalEmbeddingProvider(Settings(database_url='sqlite://'))
        async def started(client): pass
        monkeypatch.setattr(provider,'_start',started)
        assert await provider.embed(['Áo phao?'],'query') == [[.6,.8]]
        assert seen[0]['input'] == [QUERY_INSTRUCTION+'Áo phao?']
        assert await provider.embed(['English document'],'document') == [[.6,.8]]
        assert seen[1]['input'] == ['English document']
    asyncio.run(run())


def test_stale_content_and_partial_resume(hybrid):
    client,app,model,_ = hybrid
    doc = upload(client).json()
    with app.state.engine.begin() as conn:
        # Simulates a future re-extraction; old vectors must not remain valid.
        conn.execute(text("UPDATE chunk_embeddings SET content_sha256='stale' WHERE chunk_id=(SELECT min(id) FROM document_chunks)"))
    state = client.post(f"/api/documents/{doc['id']}/index",json={}).json()
    assert state['newly_indexed'] == 1
    calls = len(model.calls)
    assert client.post(f"/api/documents/{doc['id']}/index",json={}).json()['newly_indexed'] == 0
    assert len(model.calls) == calls


def test_partial_batch_failure_resumes_without_reembedding(hybrid):
    client,app,model,_ = hybrid
    original = model.embed
    calls = 0
    async def fail_second(texts,purpose):
        nonlocal calls
        if purpose == 'document':
            calls += 1
            if calls == 2: raise EmbeddingError('Interrupted second batch')
        return await original(texts,purpose)
    model.embed = fail_second
    doc = upload(client,synthetic_pdf(['SYNTHETIC lifejacket inspections Friday.']*16)).json()
    assert doc['semantic_index']['mode'] == 'fts5'
    with app.state.engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM chunk_embeddings')).scalar() == 8
    model.embed = original
    result = client.post(f"/api/documents/{doc['id']}/index",json={}).json()
    assert result['newly_indexed'] == 8
    assert client.get(f"/api/documents/{doc['id']}/file").status_code == 200


def test_queued_index_cancellation_does_not_close_owner(hybrid):
    _,app,model,_ = hybrid
    closed = []
    async def close(): closed.append(True)
    model.close = close
    async def run():
        service = app.state.retrieval
        await service.lock.acquire()
        queued = asyncio.create_task(service.index_document(str(uuid4())))
        await asyncio.sleep(.01); queued.cancel()
        with pytest.raises(asyncio.CancelledError): await queued
        assert not closed
        service.lock.release()
    asyncio.run(run())


def test_embedding_timeout_falls_back_and_cancel_during_query(hybrid):
    import time
    from concurrent.futures import ThreadPoolExecutor
    client,app,model,_ = hybrid
    doc = upload(client).json()
    async def slow(texts,purpose):
        await asyncio.sleep(20)
    model.embed = slow
    key = str(uuid4())
    with ThreadPoolExecutor() as pool:
        pending = pool.submit(question,client,doc['id'],'lifejacket inspections',key)
        for _ in range(100):
            if client.post(f'/api/questions/{key}/cancel',json={}).json()['cancelled']: break
            time.sleep(.01)
        assert pending.result(timeout=3).status_code == 499


def test_search_timeout_preserves_lexical_results(hybrid):
    client,app,model,_ = hybrid
    doc = upload(client).json()
    async def slow(texts,purpose): await asyncio.sleep(10)
    model.embed = slow
    service = HybridRetrieval(app.state.engine,model,Settings(database_url='sqlite://',embedding_timeout=.02))
    rows,state = asyncio.run(service.search(doc['id'],'lifejacket inspections'))
    assert rows and state['mode'] == 'fts5'


def test_owned_embedding_runtime_protocol(tmp_path,monkeypatch):
    """Fake runtime only: CPU/offline flags, process/HTTP and cleanup, not semantics."""
    import socket,sys
    model=tmp_path/'fixture.gguf';model.write_bytes(b'protocol fixture, not weights')
    server=tmp_path/'runtime.py'
    server.write_text('''import http.server,json,sys
args=sys.argv
assert '--embedding' in args and '--offline' in args
assert args[args.index('--pooling')+1]=='last'
assert args[args.index('--n-gpu-layers')+1]=='0'
port=int(args[args.index('--port')+1])
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_GET(self):
  self.send_response(200);self.end_headers();self.wfile.write(b'{}')
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  self.send_response(200);self.end_headers()
  self.wfile.write(json.dumps({'data':[{'index':i,'embedding':[3.,4.]} for i,_ in enumerate(body['input'])]}).encode())
http.server.HTTPServer(('127.0.0.1',port),Handler).serve_forever()
''')
    with socket.socket() as probe: probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    real_spawn=asyncio.create_subprocess_exec
    async def spawn(executable,*args,**kwargs): return await real_spawn(executable,str(server),*args,**kwargs)
    monkeypatch.setattr(asyncio,'create_subprocess_exec',spawn)
    async def run():
        provider=LocalEmbeddingProvider(Settings(database_url='sqlite://',embedding_model_path=str(model),llama_server=sys.executable,embedding_port=port))
        try:
            assert len(provider.identity())==64
            assert await provider.embed(['SYNTHETIC document','SYNTHETIC second document'],'document')==[[.6,.8],[.6,.8]]
            process=provider.process
        finally: await provider.close()
        assert process.returncode is not None
    asyncio.run(run())

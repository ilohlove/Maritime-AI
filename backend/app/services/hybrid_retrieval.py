"""SQLite-backed local cosine search plus deterministic reciprocal-rank fusion."""
import asyncio
import hashlib
import heapq
import json
import struct
from contextlib import suppress

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.services.documents import retrieve
from app.services.embeddings import EmbeddingError, normalized


def content_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def fuse(lexical: list[dict], semantic: list[dict], limit=3) -> list[dict]:
    scores, items = {}, {}
    for ranking in (lexical, semantic):
        for rank, item in enumerate(ranking, 1):
            key = item['id']
            items[key] = item
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
    lexical_rank = {item['id']: i for i, item in enumerate(lexical)}
    return [items[key] for key in sorted(scores, key=lambda key: (
        -scores[key], lexical_rank.get(key, 10**9), int(key[1:])))[:limit]]


class HybridRetrieval:
    def __init__(self, engine, provider, settings):
        self.engine, self.provider, self.settings = engine, provider, settings
        self.lock = asyncio.Lock()
        self.last_status = {'mode': 'fts5', 'semantic': 'not_checked'}

    async def close(self):
        await self.provider.close()

    async def _index(self, document_id, model_id):
        with self.engine.connect() as connection:
            chunks = [dict(row) for row in connection.execute(text('''SELECT c.id,c.excerpt,
                e.content_sha256 FROM document_chunks c LEFT JOIN chunk_embeddings e
                ON e.chunk_id=c.id AND e.model_id=:model
                WHERE c.document_id=:document ORDER BY c.id'''),
                {'model':model_id,'document':document_id}).mappings()]
        pending = [c for c in chunks if c['content_sha256'] != content_hash(c['excerpt'])]
        indexed = 0
        for offset in range(0, len(pending), 8):
            batch = pending[offset:offset+8]
            vectors = await self.provider.embed([c['excerpt'] for c in batch], 'document')
            if len(vectors) != len(batch):
                raise EmbeddingError('Wrong embedding batch length')
            vectors = [normalized(v) for v in vectors]
            if len({len(v) for v in vectors}) != 1:
                raise EmbeddingError('Inconsistent embedding dimensions')
            dimensions = len(vectors[0])
            with self.engine.begin() as connection:
                existing = connection.execute(text('SELECT dimensions FROM chunk_embeddings WHERE model_id=:model LIMIT 1'), {'model':model_id}).scalar()
                if existing is not None and existing != dimensions:
                    raise EmbeddingError('Model dimensions changed; refusing mixed embeddings')
                for chunk, vector in zip(batch, vectors):
                    current = connection.execute(text('SELECT excerpt FROM document_chunks WHERE id=:id'), {'id':chunk['id']}).scalar_one_or_none()
                    if current != chunk['excerpt']:
                        raise EmbeddingError('Source chunk changed during indexing')
                    connection.execute(text('''INSERT INTO chunk_embeddings
                        (chunk_id,model_id,content_sha256,dimensions,vector) VALUES (:chunk,:model,:sha,:dim,:vector)
                        ON CONFLICT(chunk_id,model_id) DO UPDATE SET content_sha256=excluded.content_sha256,
                        dimensions=excluded.dimensions,vector=excluded.vector'''),
                        {'chunk':chunk['id'],'model':model_id,'sha':content_hash(current),'dim':dimensions,
                         'vector':struct.pack(f'<{dimensions}f', *vector)})
            indexed += len(batch)
        return {'total_chunks':len(chunks), 'newly_indexed':indexed, 'model_id':model_id}

    async def index_document(self, document_id):
        owned = False
        try:
            async with asyncio.timeout(self.settings.embedding_timeout):
                async with self.lock:
                    owned = True
                    model_id = await asyncio.to_thread(self.provider.identity)
                    progress = await self._index(document_id, model_id)
                    self.last_status = {'mode':'hybrid','semantic':'indexed', **progress}
        except asyncio.CancelledError:
            if owned: await self.provider.close()
            raise
        except (EmbeddingError, TimeoutError, OSError, ValueError, TypeError, struct.error, SQLAlchemyError):
            if owned:
                with suppress(OSError): await self.provider.close()
            self.last_status = {'mode':'fts5','semantic':'unavailable',
                'notice':'Semantic indexing unavailable/incomplete. PDF and FTS5 remain available; retry indexing after model setup.'}
        return dict(self.last_status)

    def _semantic(self, document_id, model_id, query):
        best = []
        with self.engine.connect() as connection:
            rows = connection.execute(text('''SELECT c.id,c.excerpt,c.revision_id,c.unit_id,c.page_number,
                d.name,u.locator,r.source_format,e.vector,e.dimensions,e.content_sha256
                FROM document_chunks c JOIN chunk_embeddings e ON e.chunk_id=c.id
                JOIN content_units u ON u.id=c.unit_id AND u.revision_id=c.revision_id
                JOIN document_revisions r ON r.id=c.revision_id AND r.document_id=c.document_id
                JOIN documents d ON d.id=c.document_id
                WHERE c.document_id=:document AND e.model_id=:model'''),
                {'document':document_id,'model':model_id}).mappings()
            for row in rows:
                if row['content_sha256'] != content_hash(row['excerpt']): continue
                if row['dimensions'] != len(query):
                    raise EmbeddingError('Query/document dimensions differ')
                vector = struct.unpack(f"<{row['dimensions']}f", row['vector'])
                vector = normalized(list(vector))
                score = sum(a*b for a,b in zip(query,vector))
                if score < self.settings.semantic_min_score: continue
                entry = (score, -row['id'], dict(row))
                if len(best) < 20: heapq.heappush(best, entry)
                elif entry[:2] > best[0][:2]: heapq.heapreplace(best, entry)
        return [{'id':f"E{row['id']}",'document_id':document_id,'document_name':row['name'],
                 'revision_id':row['revision_id'],'unit_id':row['unit_id'], 'page_number':row['page_number'],
                 'locator':json.loads(row['locator']),'source_format':row['source_format'],'excerpt':row['excerpt']}
                for _,_,row in sorted(best, key=lambda x:(-x[0],-x[1]))]

    async def search(self, document_id, question):
        lexical = retrieve(self.engine, document_id, question, limit=20)
        owned = False
        try:
            async with asyncio.timeout(self.settings.embedding_timeout):
                async with self.lock:
                    owned = True
                    model_id = await asyncio.to_thread(self.provider.identity)
                    progress = await self._index(document_id, model_id)
                    vectors = await self.provider.embed([question], 'query')
                    if len(vectors) != 1: raise EmbeddingError('Expected one query embedding')
                    semantic = self._semantic(document_id, model_id, normalized(vectors[0]))
                    result = fuse(lexical, semantic)
                    self.last_status = {'mode':'hybrid','semantic':'ready', 'semantic_candidates':len(semantic), **progress}
                    return result, dict(self.last_status)
        except asyncio.CancelledError:
            # A queued caller must not terminate another caller's active inference.
            if owned: await self.provider.close()
            raise
        except (EmbeddingError, TimeoutError, OSError, ValueError, TypeError, struct.error, SQLAlchemyError):
            # A lock timeout never terminates another caller's owned runtime.
            if owned:
                with suppress(OSError): await self.provider.close()
            self.last_status = {'mode':'fts5','semantic':'unavailable',
                'notice':'Semantic search unavailable/incomplete; using FTS5 only. Missing results do not prove absence of evidence.'}
            return lexical[:3], dict(self.last_status)

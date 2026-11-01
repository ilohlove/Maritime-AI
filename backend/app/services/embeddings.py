"""Optional local embeddings; never uses an external endpoint or downloads weights."""
import asyncio
import hashlib
import math
import shutil
import socket
from pathlib import Path
from typing import Literal, Protocol

import httpx

QUERY_INSTRUCTION = 'Instruct: Given a maritime question, retrieve relevant passages that answer the question\nQuery: '


class EmbeddingError(Exception):
    pass


class EmbeddingProvider(Protocol):
    def identity(self) -> str: ...
    async def embed(self, texts: list[str], purpose: Literal['document', 'query']) -> list[list[float]]: ...
    async def close(self) -> None: ...


def normalized(vector: list[float]) -> list[float]:
    if not 1 <= len(vector) <= 4096 or not all(math.isfinite(v) for v in vector):
        raise EmbeddingError('Invalid embedding dimensions or non-finite values')
    norm = math.hypot(*vector)
    if not math.isfinite(norm) or norm <= 1e-12:
        raise EmbeddingError('Zero embedding vector')
    return [v/norm for v in vector]


class LocalEmbeddingProvider:
    """Qwen3-Embedding GGUF with llama-server last-token pooling, CPU only."""
    def __init__(self, settings):
        self.settings = settings
        self.process = None
        self._signature = None
        self._identity = None

    def identity(self) -> str:
        path = Path(self.settings.embedding_model_path)
        if not self.settings.embedding_model_path or not path.is_file() or path.suffix.lower() != '.gguf':
            raise EmbeddingError('Embedding model unavailable; FTS5 remains available')
        if not shutil.which(self.settings.llama_server):
            raise EmbeddingError('llama-server unavailable for embeddings; FTS5 remains available')
        stat = path.stat()
        executable = Path(shutil.which(self.settings.llama_server))
        executable_stat = executable.stat()
        signature = (str(path.resolve()), stat.st_size, stat.st_mtime_ns,
                     str(executable.resolve()), executable_stat.st_size, executable_stat.st_mtime_ns)
        if self._signature is not None and signature != self._signature:
            raise EmbeddingError('Embedding model changed; restart the app before indexing')
        if self._identity is None:
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                while block := stream.read(1024*1024): digest.update(block)
            # Include pooling/query recipe and executable hash to avoid mixing incompatible spaces.
            with executable.open('rb') as binary:
                runtime = hashlib.file_digest(binary, 'sha256').hexdigest()
            recipe = f'{digest.hexdigest()}:{runtime}:last:l2:v1:{QUERY_INSTRUCTION}'
            self._identity = hashlib.sha256(recipe.encode()).hexdigest()
            self._signature = signature
        return self._identity

    async def close(self):
        process, self.process = self.process, None
        if process is not None and process.returncode is None:
            try: process.terminate()
            except ProcessLookupError: pass
            try: await asyncio.wait_for(process.wait(), 5)
            except TimeoutError:
                try: process.kill()
                except ProcessLookupError: pass
                await process.wait()

    async def _start(self, client):
        if self.process is None or self.process.returncode is not None:
            try:
                with socket.socket() as probe: probe.bind(('127.0.0.1', self.settings.embedding_port))
            except OSError:
                raise EmbeddingError('Embedding port is occupied; refusing an unowned service') from None
            self.process = await asyncio.create_subprocess_exec(
                self.settings.llama_server, '--model', str(Path(self.settings.embedding_model_path).resolve()),
                '--host', '127.0.0.1', '--port', str(self.settings.embedding_port),
                '--embedding', '--pooling', 'last', '--ctx-size', '4096', '--batch-size', '2048',
                '--ubatch-size', '2048', '--parallel', '1', '--threads', '2', '--n-gpu-layers', '0',
                '--offline', '--no-webui', '--cache-ram', '0',
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        while True:
            if self.process.returncode is not None:
                raise EmbeddingError('Embedding runtime exited; check GGUF/runtime compatibility')
            try:
                response = await client.get('/health')
                if response.status_code == 200: return
            except httpx.TransportError: pass
            await asyncio.sleep(.2)

    async def embed(self, texts, purpose):
        try:
            async with asyncio.timeout(self.settings.embedding_timeout):
                async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{self.settings.embedding_port}', trust_env=False, timeout=5) as client:
                    await self._start(client)
                    inputs = [QUERY_INSTRUCTION+t if purpose == 'query' else t for t in texts]
                    response = await client.post('/v1/embeddings', json={'input': inputs, 'encoding_format': 'float'}, timeout=None)
                    response.raise_for_status()
                    rows = sorted(response.json()['data'], key=lambda row: row['index'])
                    if [r['index'] for r in rows] != list(range(len(texts))):
                        raise EmbeddingError('Embedding response indices do not match inputs')
                    return [normalized(row['embedding']) for row in rows]
        except asyncio.CancelledError:
            await self.close(); raise
        except (TimeoutError, OSError, httpx.HTTPError, ValueError, KeyError, TypeError, EmbeddingError) as error:
            await self.close()
            raise EmbeddingError('Local embedding inference unavailable or invalid; using FTS5') from error

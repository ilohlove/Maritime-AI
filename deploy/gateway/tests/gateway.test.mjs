import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { handleRequest, signRequest } from '../dist/index.js';

const env = {
  MARITIME_BACKEND_ORIGIN: 'https://backend.example.onrender.com',
  MARITIME_PUBLIC_ORIGIN: 'https://maritime.example.workers.dev',
  MARITIME_GATEWAY_SECRET: '00'.repeat(32), // Synthetic test vector only.
  ASSETS: { fetch: async () => new Response('<html>synthetic</html>') },
};

function edgeRequest(url, init) {
  const request = new Request(url, init);
  Object.defineProperty(request, 'cf', { value: { tlsVersion: 'TLSv1.3' } });
  return request;
}

test('matches independent Python/JavaScript wire-protocol vector', async () => {
  const v = JSON.parse(await readFile(new URL('../protocol-v1.test-vector.json', import.meta.url)));
  assert.equal(await signRequest(v.secret, new URL(v.url), v.method, new Headers(v.headers),
    new TextEncoder().encode(v.body), v.timestamp, v.nonce), v.signature);
});

test('rejects HTTP API even when the client claims HTTPS', async () => {
  let calls = 0;
  const response = await handleRequest(edgeRequest('http://maritime.example.workers.dev/api/health',
    { headers: { 'X-Forwarded-Proto': 'https' } }), env, async () => { calls++; });
  assert.equal(response.status, 400);
  assert.equal(calls, 0);
});

test('strips supplied proofs/proxy headers, binds credentials and uses only HTTPS origin', async () => {
  const response = await handleRequest(edgeRequest(env.MARITIME_PUBLIC_ORIGIN + '/api/health?x=1', {
    headers: { 'x-maritime-gateway-signature': 'forged', 'x-forwarded-proto': 'http',
      'x-forwarded-for': '192.0.2.1', 'authorization': 'Bearer synthetic-session', 'cookie': 'untrusted' }
  }), env, async (url, options) => {
    assert.equal(url, env.MARITIME_BACKEND_ORIGIN + '/api/health?x=1');
    assert.equal(options.redirect, 'manual');
    const h = options.headers;
    assert.equal(h.get('x-forwarded-proto'), null);
    assert.equal(h.get('x-forwarded-for'), null);
    assert.equal(h.get('cookie'), null);
    assert.equal(h.get('authorization'), 'Bearer synthetic-session');
    assert.equal(h.get('x-maritime-gateway-signature'), await signRequest(env.MARITIME_GATEWAY_SECRET,
      new URL(url), options.method, h, new Uint8Array(), h.get('x-maritime-gateway-time'), h.get('x-maritime-gateway-nonce')));
    return Response.json({ status: 'ok' });
  });
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('cache-control'), 'no-store');
});

test('never sends a request to an unconfigured host or plaintext backend', async () => {
  for (const bad of [env.MARITIME_PUBLIC_ORIGIN.replace('maritime.', 'other.'), env.MARITIME_PUBLIC_ORIGIN]) {
    const response = await handleRequest(edgeRequest(bad + '/api/health'),
      { ...env, MARITIME_BACKEND_ORIGIN: 'http://backend.example.onrender.com' },
      async () => { throw new Error('Must not fetch'); });
    assert.equal(response.status, 502);
  }
  assert.equal((await handleRequest(edgeRequest('https://other.example.workers.dev/api/health'), env)).status, 400);
});

test('bounds streamed bodies and refuses redirects rather than following credentials', async () => {
  const large = edgeRequest(env.MARITIME_PUBLIC_ORIGIN + '/api/documents', { method: 'POST', body: 'x'.repeat(65537) });
  assert.equal((await handleRequest(large, env, async () => { throw Error('Must not fetch'); })).status, 413);
  const redirect = await handleRequest(edgeRequest(env.MARITIME_PUBLIC_ORIGIN + '/api/health'), env,
    async () => Response.redirect('https://untrusted.invalid', 307));
  assert.equal(redirect.status, 502);
});

test('serves same-origin assets with HSTS; redirects HTTP assets', async () => {
  const asset = await handleRequest(edgeRequest(env.MARITIME_PUBLIC_ORIGIN), env);
  assert.match(await asset.text(), /synthetic/);
  assert.equal(asset.headers.get('strict-transport-security'), 'max-age=31536000');
  assert.equal((await handleRequest(edgeRequest('http://maritime.example.workers.dev/'), env)).status, 308);
});

test('requires platform TLS connection metadata; URL/proxy header claims are insufficient', async () => {
  for (const version of [undefined, '', 'TLSv1', 'TLSv1.1']) {
    const request = new Request(env.MARITIME_PUBLIC_ORIGIN + '/api/health', {
      headers: { 'x-forwarded-proto': 'https', 'cf-tls-version': 'TLSv1.3' }
    });
    if (version !== undefined) Object.defineProperty(request, 'cf', { value: { tlsVersion: version } });
    const result = await handleRequest(request, env, async () => { throw Error('Must not sign/fetch'); });
    assert.equal(result.status, 400);
    assert.equal((await result.json()).detail.code, 'verified_tls_required');
  }
});

test('online uploads have a separate bounded opt-in; other routes retain 64 KiB', async () => {
  const online = { ...env, MARITIME_ONLINE_MVP_MODE: 'true' };
  let forwarded = false;
  const upload = edgeRequest(env.MARITIME_PUBLIC_ORIGIN + '/api/documents', { method: 'POST', headers: { 'content-type': 'application/json' }, body: 'x'.repeat(100_000) });
  const response = await handleRequest(upload, online, async (url, options) => {
    forwarded = true;
    assert.equal(options.body.length, 100_000);
    assert.equal(options.headers.get('x-maritime-gateway-signature'), await signRequest(env.MARITIME_GATEWAY_SECRET,
      new URL(url), options.method, options.headers, options.body,
      options.headers.get('x-maritime-gateway-time'), options.headers.get('x-maritime-gateway-nonce')));
    return Response.json({ status: 'synthetic' });
  });
  assert.equal(response.status, 200);
  assert.equal(forwarded, true);
  for (const [path, size] of [['/api/documents', 4_100_001], ['/api/vessels', 65537]]) {
    const request = edgeRequest(env.MARITIME_PUBLIC_ORIGIN + path, { method: 'POST', body: 'x'.repeat(size) });
    assert.equal((await handleRequest(request, online, async () => { throw Error('Must not fetch'); })).status, 413);
  }
  const invalid = await handleRequest(edgeRequest(env.MARITIME_PUBLIC_ORIGIN + '/api/health'), { ...env, MARITIME_ONLINE_MVP_MODE: 'typo' });
  assert.equal(invalid.status, 503);
});

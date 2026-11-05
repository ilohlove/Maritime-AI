// Invoked only by pytest against its ephemeral, certificate-verified TLS server.
import assert from 'node:assert/strict';
import { request as tlsRequest } from 'node:https';
import { handleRequest } from '../dist/index.js';
const env = {
  MARITIME_BACKEND_ORIGIN: 'https://backend.example.onrender.com',
  MARITIME_PUBLIC_ORIGIN: 'https://maritime.example.workers.dev',
  MARITIME_GATEWAY_SECRET: '00'.repeat(32),
  ASSETS: { fetch: async () => new Response('synthetic static UI') },
};
const upstream = async (target, options) => {
  const url = new URL(target);
  const local = new URL(process.env.MARITIME_TEST_TLS_ORIGIN);
  local.pathname = url.pathname;
  local.search = url.search;
  const headers = new Headers(options.headers);
  headers.set('host', url.host);
  // Node's Fetch controls Host itself. This local test transport preserves the
  // real origin Host while routing to loopback; certificate validation stays on.
  return new Promise((resolve, reject) => {
    const req = tlsRequest(local, { method: options.method, headers: Object.fromEntries(headers) }, res => {
      const chunks = [];
      res.on('data', chunk => chunks.push(chunk));
      res.on('end', () => resolve(new Response(Buffer.concat(chunks), {
        status: res.statusCode, headers: res.headers,
      })));
    });
    req.on('error', failure => { console.error(failure.message); reject(failure); });
    if (options.body) req.write(options.body);
    req.end();
  });
};
const call = (path, init) => {
  const request = new Request(env.MARITIME_PUBLIC_ORIGIN + path, init);
  // Model the documented Cloudflare runtime connection metadata in this local test.
  Object.defineProperty(request, 'cf', { value: { tlsVersion: 'TLSv1.3' } });
  return handleRequest(request, env, upstream);
};
assert.equal((await call('/api/health', { headers: { 'x-forwarded-proto': 'http' } })).status, 200);
assert.equal((await call('/api/documents')).status, 401);
const login = await call('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json',
  Origin: env.MARITIME_PUBLIC_ORIGIN }, body: JSON.stringify({ username: 'admin', password: 'synthetic-private-test-password' }) });
assert.equal(login.status, 200, await login.clone().text());
const token = (await login.json()).access_token;
const documents = await call('/api/documents', { headers: { authorization: 'Bearer ' + token } });
assert.equal(documents.status, 200);
assert.deepEqual(await documents.json(), []);
console.log('PASS: actual Worker signer → verified local TLS → Uvicorn → gateway MAC/replay checks → owner login');

/** Cloudflare Free: HTTPS entry point + HMAC-attested HTTPS hop to Render. */
interface Env {
  MARITIME_BACKEND_ORIGIN: string;
  MARITIME_PUBLIC_ORIGIN: string;
  MARITIME_GATEWAY_SECRET: string;
  MARITIME_ONLINE_MVP_MODE?: string;
  ASSETS: { fetch(request: Request): Promise<Response> };
}

const LIMIT = 65536; // Preserved default for the existing disposable deployment.
const ONLINE_UPLOAD_LIMIT = 4_100_000; // 3 MB PDF plus bounded JSON/base64 envelope.
const signedHeaders = ["authorization", "content-type", "origin", "x-csrf-token"];
const encoder = new TextEncoder();
const hex = (value: ArrayBuffer) => Array.from(new Uint8Array(value), b => b.toString(16).padStart(2, "0")).join("");

function origin(value: string, suffix: string): URL {
  const url = new URL(value);
  if (url.protocol !== "https:" || !url.hostname.endsWith(suffix) ||
      url.port || url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
    throw new Error("Invalid configured origin");
  }
  return url;
}

function error(status: number, code: string): Response {
  return Response.json({ detail: { code, message: "The secure gateway could not accept this request." } }, {
    status, headers: { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" }
  });
}

async function boundedBody(request: Request, limit: number): Promise<Uint8Array> {
  const chunks: Uint8Array[] = [];
  let length = 0;
  const reader = request.body?.getReader();
  if (!reader) return new Uint8Array();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    length += value.length;
    if (length > limit) {
      await reader.cancel();
      throw new RangeError("Body limit");
    }
    chunks.push(value);
  }
  const result = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.length; }
  return result;
}

export async function signRequest(
  secret: string, target: URL, method: string, headers: Headers, body: Uint8Array,
  stamp: string, nonce: string,
): Promise<string> {
  if (!/^[0-9a-f]{64}$/.test(secret)) throw new Error("Invalid gateway credential");
  const key = await crypto.subtle.importKey("raw", Uint8Array.from(secret.match(/../g)!, v => parseInt(v, 16)),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const bodyHash = hex(await crypto.subtle.digest("SHA-256", body as BufferSource));
  const fields = ["maritime-gateway-v1-https", stamp, nonce, method, target.host,
    target.pathname, target.search.slice(1), ...signedHeaders.map(name => headers.get(name) ?? ""), bodyHash];
  if (fields.some(value => /[\r\n]/.test(value))) throw new Error("Ambiguous gateway field");
  return hex(await crypto.subtle.sign("HMAC", key, encoder.encode(fields.join("\n"))));
}

export async function handleRequest(request: Request, env: Env, upstream: typeof fetch = fetch): Promise<Response> {
  try {
    const backend = origin(env.MARITIME_BACKEND_ORIGIN, ".onrender.com");
    const publicOrigin = origin(env.MARITIME_PUBLIC_ORIGIN, ".workers.dev");
    if (!/^[0-9a-f]{64}$/.test(env.MARITIME_GATEWAY_SECRET)) return error(503, "gateway_not_configured");
    const incoming = new URL(request.url);
    if (incoming.host !== publicOrigin.host) return error(400, "host_not_permitted");
    // URL comes from the platform Request, never from X-Forwarded-Proto.
    if (incoming.protocol !== "https:") {
      if (incoming.pathname.startsWith("/api")) return error(400, "https_required");
      incoming.protocol = "https:";
      return Response.redirect(incoming.href, 308);
    }
    // Connection metadata is supplied by Cloudflare, not by HTTP headers or URL text.
    const tlsVersion = (request as Request & { readonly cf?: { readonly tlsVersion?: string } }).cf?.tlsVersion;
    if (tlsVersion !== "TLSv1.2" && tlsVersion !== "TLSv1.3") {
      return error(400, "verified_tls_required");
    }
    if (!incoming.pathname.startsWith("/api/")) {
      const response = await env.ASSETS.fetch(request);
      const asset = new Response(response.body, response);
      asset.headers.set("Strict-Transport-Security", "max-age=31536000");
      return asset;
    }
    if (!["GET", "HEAD", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"].includes(request.method)) {
      return error(405, "method_not_permitted");
    }
    if (env.MARITIME_ONLINE_MVP_MODE !== undefined && !["true", "false"].includes(env.MARITIME_ONLINE_MVP_MODE)) {
      return error(503, "gateway_not_configured");
    }
    const limit = env.MARITIME_ONLINE_MVP_MODE === "true" && incoming.pathname === "/api/documents" && request.method === "POST" ? ONLINE_UPLOAD_LIMIT : LIMIT;
    const body = await boundedBody(request, limit);
    // Set URL components separately: a path beginning // cannot change origin.
    const target = new URL(backend);
    target.pathname = incoming.pathname;
    target.search = incoming.search;
    const headers = new Headers();
    for (const name of signedHeaders) {
      const value = request.headers.get(name);
      if (value !== null) headers.set(name, value);
    }
    const stamp = Math.floor(Date.now() / 1000).toString();
    const nonce = hex(crypto.getRandomValues(new Uint8Array(16)).buffer);
    headers.set("x-maritime-gateway-time", stamp);
    headers.set("x-maritime-gateway-nonce", nonce);
    headers.set("x-maritime-gateway-signature", await signRequest(env.MARITIME_GATEWAY_SECRET, target, request.method, headers, body, stamp, nonce));
    // Fixed HTTPS destination, platform certificate validation, no redirect following.
    const response = await upstream(target.href, {
      method: request.method, headers, redirect: "manual",
      body: ["GET", "HEAD"].includes(request.method) ? undefined : body as BodyInit,
    });
    // Keep redirects within the authenticated public gateway, never expose origin URLs.
    if (response.status >= 300 && response.status < 400 && response.headers.has("location")) {
      return error(502, "unexpected_origin_redirect");
    }
    const result = new Response(response.body, response);
    result.headers.set("Cache-Control", "no-store");
    result.headers.set("Strict-Transport-Security", "max-age=31536000");
    return result;
  } catch (failure) {
    return error(failure instanceof RangeError ? 413 : 502, "gateway_unavailable");
  }
}

export default {
  fetch(request: Request, env: Env) { return handleRequest(request, env); }
};

# Online MVP V1 security assessment

2026-11-07. This documents implemented controls and remaining validation; it is
not an independent penetration test or a production-readiness approval.

| Threat | Implemented control | Validation / limit |
| --- | --- | --- |
| Forged gateway identity/HTTPS | Original HMAC v1 protocol, constant-time comparison, bound method/host/raw path/query/auth/content type/origin/CSRF/body, timestamp expiry and atomic durable nonce | Existing signature, tamper, replay, concurrent nonce, TLS and proxy-spoof tests retained; new PG tests |
| Direct Render access | Signed-gateway outer middleware required for all requests, including health and preflight; Uvicorn header trust disabled | Anonymous/spoofed requests rejected before application auth; no new unsigned health exception |
| Account takeover/session forgery | Existing scrypt hash, opaque random token digests, absolute expiry, credential-version revocation, durable login throttle | Existing login/expiry/logout/password-rotation/CSRF tests retained |
| Cross-origin or Host abuse | Explicit trusted hosts and HTTPS frontend origins; JSON-only bounded writes; signed auth headers | Existing tests retained; no wildcard or origin bypass introduced |
| Unauthorized documents/profiles | Owner ID derived only from authenticated session; route-level owner filtering, same 404 for unknown/foreign IDs | Tests cover list/read/patch/search/inspect/original/questions/delete; single configured administrator remains the account model |
| Supabase REST bypass | PG RLS enabled and PUBLIC/anon/authenticated table grants revoked, including sessions/quota/Alembic tables | Local PG checks; provider deployment must verify actual anon/authenticated API denial and restricted backend-role policy |
| Public PDFs/object traversal | Backend-only private S3 client, UUID keys, strict key grammar, no public ACL or presigned URLs, private download through authenticated backend | Traversal, symlink, collision, S3 SDK request stubs and ownership tests; remote bucket privacy still an operator verification gate |
| PDF decompression/parser abuse | 3 MB originals, 50 pages, 200000 text characters, one parser, killable 20-second subprocess; Linux 256 MiB/15 CPU-second caps | Valid real synthetic PDF, encrypted/page/size/timeout rejection tested; no OCR or malware scanner |
| Storage interruption | Durable pending/deleting records, generated key committed before PUT, idempotent retry deletion, shared upload/delete slot | Interrupted PUT and DELETE, non-ready retrieval rejection, overlap rejection and cleanup tests |
| Uncontrolled growth | Upload throttle, 20 records/owner, 100 total, bounded chunk/context sizes; two DB connections and no overflow | Quota/config tests; pending items count toward quota; no multi-replica guarantee |
| Database transport/exhaustion | PostgreSQL verify-full TLS, pre-ping, bounded pool/connect/statement/lock timeouts | Real local TLS PG tests with trusted self-signed test CA; provider pooler and network path untested |
| API key exposure | Backend-only SDK, secret fields excluded from Settings repr, SQL parameters hidden, no frontend secret config | API status/redaction tests and code review; operators must restrict provider roles/log access |
| Sensitive logs | Existing sanitized HTTP/workflow errors; production SDK/SQL logging reduced; pypdf diagnostics suppressed; parser stderr discarded | Existing secret-marker tests retained; no document payloads or credentials intentionally logged |
| Prompt injection | Questions/passages are user-role JSON data, system explicitly treats them as untrusted; no tools; structured output; only server-validated exact quotes/IDs render sources | Mocked malicious-document prompt test retained; citation validity cannot establish semantic truth |
| Unsupported maritime answers | Bounded retrieved evidence; unknown IDs/invented quotes rejected; no-evidence/decline behavior; source/interpretation shown separately; conflict instruction | Existing citation tests, new real PDF/browser evidence tests; no real maritime benchmark or authority ranking |
| Excess AI spending | Online activation defaults off independently of API key; fresh request consent; one-model allowlist; durable atomic conservative quota, rate/concurrency controls, no refunds, zero retries | Concurrent PG/SQLite quota tests, disabled factory checks, mocked SDK usage tests; account billing limits remain essential |
| Quota/usage storage failure | Fail closed before inference if reservation unavailable; withhold answer on post-call usage failure; unknown usage covered by reserved budget | Failure tests; a charged request can still fail after inference, so billing reconciliation is required |
| Mode confusion/data loss | Strict new boolean flags; online requires persistent PG/private S3 and security; no ephemeral fallback; no automatic ownership claim/migrations | Invalid startup configuration, missing originals, unowned data, disposable restrictions and legacy upgrade tests |

## Operational requirements and findings

- **Single owner:** no public signup, invitations, password reset or multi-user
  identity provider was implemented. Owner checks prepare the storage boundary;
  they do not turn this into a multi-tenant SaaS. Keep the administrator username
  stable. Renaming it changes ownership/quota identity and requires an audited
  migration; changing the password revokes old sessions.
- **Supabase privacy:** acknowledgement of a private bucket is configuration, not
  remote proof. Verify anonymous object GET denial and direct Data API denial
  using synthetic objects before real data. Use a restricted backend role with
  explicit RLS policies and a separate migration owner. Supabase S3 credentials
  may carry broad storage authority; use a dedicated project and restrict them
  to the required bucket wherever the provider permits.
- **Boundaries:** one backend process/replica is mandatory. Per-process parser/
  inference semaphores cannot protect a scaled deployment. Horizontal scaling,
  shared processing locks, robust billing reconciliation and automated backup
  recovery require additional work.
- **Document safety:** PDFs are untrusted active containers. Original download
  uses attachment/octet-stream, no-store, nosniff and a sandbox CSP; the browser
  never embeds an original PDF. An externally opened downloaded PDF remains an
  operator decision. Parser isolation reduces resource abuse but is not a
  full OS security sandbox or malware-disarm service.
- **Accuracy:** exact quotes prove traceability, not entailment, completeness,
  current regulatory authority or operational safety. Conflicting evidence is
  requested as separately cited positions. Cross-document conflict detection,
  version authority and independent maritime review remain outstanding.
- **Quotas:** failures retain full reservations; restore/reset/renaming identity
  can undermine spending controls. Keep inference off after any old-ledger
  restore until reconciliation or UTC reset. Set provider-side spending controls
  and review billing even when application estimates are small.
- **Availability:** free services can sleep, pause or exceed quotas. Startup
  deliberately refuses missing persistence. No availability/SLA claim is made.

## Dependency review

`pip-audit` against the pinned backend dependency lock and `npm audit` against the
frontend lock were executed and reported no known vulnerabilities on 2026-11-07.
The scan is limited to advisories available at execution; pinning is not a future
security guarantee. TLS and npm integrity validation stayed enabled. No paid AI
requests, private uploads, external accounts or production settings were used.

# Render Free disposable backend: configuration and unresolved ingress gate

Assessment date: 2026-11-06. Based on
`feature/free-cloud-deployment-assessment` at
`202240d96a446ce8b64d8a6971bccfbd03ea6c45`.

**Deployment readiness is not verified.** The operator reports an available Free
Python service in Singapore. The build works locally, but the production launcher
requires a verified trusted ingress configuration that is not yet available.
Do not deploy with guessed proxy addresses, all-address trust, disabled HTTPS,
development mode, or disabled authentication/host validation.

## Verified implementation and official-source evidence

Task 02B.2 update: the operator independently retrieved the official Render
sources below and supplied these verified facts. They are accepted as evidence
for this continuation; this environment has not independently re-fetched them.

| Official source | Operator-verified facts |
| --- | --- |
| [Web services](https://render.com/docs/web-services) and [web services tutorial](https://render.com/tutorials/web-service-vs-static-site/web-services) | Render terminates inbound HTTPS at its load balancer, forwards HTTP to the app, redirects public HTTP to HTTPS, documents `X-Forwarded-Proto` for the original scheme, and requires `0.0.0.0` plus the supplied `PORT` |
| [Private network](https://render.com/docs/private-network) and [Free services](https://render.com/docs/free) | Free Web Services can initiate private-network requests but cannot receive inbound private-network traffic |

These sources, as verified by the operator, do not supply verified inbound proxy
IP ranges or sufficient guarantees about sanitizing client-supplied forwarded
headers. The remaining blocker is that trust boundary, not inability to retrieve
the already-verified platform facts.

- `scripts/start_disposable_test.py` requires the production/disposable/data-loss
  flags below, creates a fresh system temporary directory, overrides inherited
  database/document paths, migrates that database, then calls `start_backend.py`.
  It intentionally loses documents, sessions and rate state on every launch.
- `Settings` requires a valid password hash, explicit HTTPS frontend origins,
  explicit backend hostnames and the disabled API-key placeholder. Disposable
  mode rejects real API keys, persistent-storage claims and cookie sessions.
- `start_backend.py` runs one Uvicorn worker. Its default loopback bind must be
  changed for Render. It requires `MARITIME_TRUSTED_PROXY_IPS` in production,
  accepts only IPs/CIDRs and rejects either IPv4 or IPv6 prefix length zero.
  `*`, hostnames and placeholder strings are not valid proxy values.
- Uvicorn 0.38.0 interprets `X-Forwarded-Proto` and `X-Forwarded-For` only when
  the connecting peer matches that allowlist. The FastAPI app itself does not
  interpret forwarded headers. It rejects non-HTTPS request schemes, including
  health checks. Private routes still require a session; Host and Origin checks
  remain enforced.
- Render's official [FastAPI example README][render-example] and
  [Blueprint][render-yaml] were retrieved successfully from GitHub. They specify
  Python/FastAPI, binding to `0.0.0.0`, and using the platform's `$PORT`.
  The old Blueprint contains `plan: free` and `autoDeploy: false`; it does not
  establish current pricing, header sanitization or proxy topology.

**Still unverified:** which forwarded headers Render overwrites versus appends,
including duplicate headers, and actual immediate ingress peer addresses/ranges.
Free's inbound private-network restriction reduces possible access paths; it
does not by itself authenticate a forwarded-header value. A public client can
send that header through the load balancer unless the ingress sanitizes it.

**Decision:** a secure configuration without proxy IP ranges has not been
established from the available evidence. A platform-specific scheme adapter could
potentially use a documented exclusive ingress boundary with a guaranteed
canonical scheme header that clients cannot influence. Both the exclusive path
and sanitization guarantee would need verification before implementing it. A
`RENDER=true` process variable, a matching Host, the application's password or the
HTTP-to-HTTPS redirect does not authenticate each forwarded header. Authentication
also cannot protect the public login endpoint's transport check.

For the existing Uvicorn implementation, an IP allowlist additionally needs the
trusted ingress to supply safe scheme and client-IP headers: peer identity alone
does not sanitize malicious input relayed by that peer. No automatic Render mode,
unconditional HTTPS scheme, wildcard trust or broad private range was added.
Production remains fail-closed. This does not prove that Render is inherently
incompatible; it identifies the evidence needed for a secure compatibility fix.

## Generate the password hash locally

Run these commands in a local interactive terminal at the repository root, using
Python 3.11+ (validation here used Python 3.12):

```sh
python -m venv .venv
# Activate .venv: POSIX: source .venv/bin/activate
# PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps -e backend
python scripts/hash_password.py
```

Enter a unique password of 12–256 characters twice at the hidden prompts. Do not
put it in a command argument, pipe, environment variable, online hash generator,
Git file, or chat. The script now stops if hidden input is unavailable, rather
than allowing `getpass` to fall back to visible input.

Copy the single output line into Render's secret environment field named
`MARITIME_PASSWORD_HASH`. Paste it literally, without quotes, spaces or newlines.
Its format is `scrypt$16384$8$5$<32 hex salt characters>$<128 hex digest characters>`.
Keep every `$`; do not paste the hash into an unquoted shell command, where dollar
signs can expand. It is not a bcrypt, Argon2, SHA-256 or plaintext password field.
Treat the hash as a secret too. The password remains your login password; it is
not the value stored in Render.

The implementation uses a random 16-byte salt, scrypt N=16384/r=8/p=5, a 64-byte
digest and constant-time comparison. Each generation produces a different hash.
No real password/hash was generated for or committed to this repository.

## Environment values required for this profile

These fixed values are verified against the repository, not inferred Render
network properties. Set them through Render's Environment settings:

| Name | Value | Status |
| --- | --- | --- |
| `MARITIME_ENV` | `production` | Required |
| `MARITIME_DISPOSABLE_TEST_MODE` | `true` | Required |
| `MARITIME_DISPOSABLE_ACK` | `SYNTHETIC_ONLY_DATA_LOSS_NO_PAID_AI` | Required, exact literal |
| `MARITIME_STORAGE_PERSISTENT` | `false` | Required, exact literal |
| `OPENAI_API_KEY` | `DISABLED-DISPOSABLE-TEST` | Required noncredential; never use a live key |
| `MARITIME_BIND_HOST` | `0.0.0.0` | Required for Render's external port binding; this is a bind address, not a proxy trust range |
| `MARITIME_AUTH_TRANSPORT` | `bearer` | Required mode; also the default |
| `WEB_CONCURRENCY` | `1` | Required worker count; also the default |

Values that require your input or further evidence:

| Name | Exact procedure | Status |
| --- | --- | --- |
| `MARITIME_PASSWORD_HASH` | Paste the locally generated complete scrypt line | Secret, owner-specific |
| `MARITIME_TRUSTED_HOSTS` | Copy the hostname from the actual Render service URL; omit `https://`, port, path and trailing slash | Service-URL dependent; never infer it from the service name or use `*.onrender.com` |
| `MARITIME_ALLOWED_ORIGINS` | Set the actual HTTPS frontend origin, without path or trailing slash | Frontend dependent; `https://ilohlove.github.io` only if that is the frontend being used, regardless of its `/Maritime-AI/` path |
| `MARITIME_TRUSTED_PROXY_IPS` | A comma-separated list of verified immediate TLS ingress IPs/CIDRs with safe forwarded-header handling | **Unresolved startup blocker. No value can currently be supplied securely. Leaving it unset intentionally fails startup.** |

For example, if the dashboard actually displays
`https://maritime-ai-EXAMPLE.onrender.com`, use
`MARITIME_TRUSTED_HOSTS=maritime-ai-EXAMPLE.onrender.com`. This is an illustration,
not a verified hostname for this service.

Leave `PORT` platform-managed: the launcher reads Render's supplied `PORT`.
Do not replace it with the local default 8000. Do not set
`MARITIME_DISPOSABLE_ROOT`, `MARITIME_DATABASE_URL`, `MARITIME_DOCUMENTS_DIR` or
`MARITIME_DATA_DIR`; this launcher creates/sets its isolated paths. No disk,
database subscription, paid AI provider or other paid resource is needed.

All remaining settings may be omitted, using these validated defaults:

| Name | Default |
| --- | --- |
| `MARITIME_ADMIN_USERNAME` | `admin` (set explicitly if a different owner username is wanted) |
| `MARITIME_SESSION_SECONDS` | `3600` |
| `MARITIME_LOGIN_LIMIT` | `5` per peer/minute, with a separate global limit |
| `OPENAI_MODEL`, `OPENAI_MODELS` | `gpt-4.1-mini` (metadata only; inference remains disabled) |
| `OPENAI_TIMEOUT_SECONDS`, `OPENAI_MAX_RETRIES` | `30`, `0` (retries must remain zero) |
| `MARITIME_AI_RATE_LIMIT`, `MARITIME_AI_CONCURRENCY` | `5`, `1` |
| `MARITIME_AI_DAILY_TOKEN_BUDGET`, `MARITIME_AI_MAX_INPUT_TOKENS` | `100000`, `20000` |
| `MARITIME_AI_OUTPUT_TOKENS`, `MARITIME_AI_TRANSLATION_TOKENS` | `2000`, `512` |

The Render-specific [environment template](../deploy/render-free.env.example)
sets `MARITIME_BIND_HOST=0.0.0.0` and deliberately omits `PORT`, using Render's
inherited value. The shared launcher's loopback default remains appropriate for
local use. The template deliberately leaves proxy trust unset and cannot start
production until the ingress gate is resolved.

Existing tighter AI limits from `deploy/disposable-test.env.example` are valid
but not required; they do not enable inference. That generic example's loopback
bind and ingress placeholders are not ready-to-use Render values.

## Remaining Render settings and deployment gate

1. Keep the service as Python 3, Singapore, Free, with repository root as Root
   Directory. Do not add a persistent disk or paid database.
2. Disable automatic deployments before changing branch/configuration. Select
   `feature/render-free-proxy-compatibility` for reviewing this change.
3. Keep Build Command:
   `python -m pip install -r backend/requirements-dev.lock && python -m pip install --no-deps -e backend`.
   This exact installation sequence succeeded locally.
4. Keep Start Command: `python scripts/start_disposable_test.py`. Do not replace
   it with bare Uvicorn: the script creates isolated storage, validates production
   guards and runs migrations without a paid release-command feature.
5. Enter the environment values above. Health Check Path is `/api/health`;
   its scheme and Host must also pass the existing security controls.
6. **Before any manual deployment**, obtain official documentation or an official
   Render support statement establishing the trust boundary below. If Render
   cannot supply a suitable stable IP allowlist, a separately validated platform
   adapter may be needed. Do not select an arbitrary range just to pass startup.
7. Only after that gate is resolved, manually deploy and verify HTTPS health,
   anonymous rejection, owner login, Host/Origin rejection, synthetic import,
   disabled inference and expected data/session loss on restart. These Render
   checks have not been run; local simulation is not live ingress verification.

Specific official documentation needed:

- [Web services](https://render.com/docs/web-services): the
  exact `X-Forwarded-Proto`/`X-Forwarded-For` replacement or append behavior,
  including client-supplied and duplicate values; port exposure and health probes.
- The verified inbound private-network restriction is accepted. An alternative
  without IP ranges still needs a complete exclusive-ingress guarantee, including
  any internal platform/health-probe paths to this Free service's listening port.
- Official inbound proxy address/range guarantees or an explicit documented
  alternative trust boundary. Render outbound/egress IP lists and DNS addresses
  of the public service are not evidence of immediate inbound proxy addresses.

No deployment, live AI request, provider account change or paid resource was made.

## Local validation

| Check | Result |
| --- | --- |
| Exact Render Build Command, using the local virtual environment | Passed, including editable installation |
| Backend `python -m pytest -q` | 130 passed; one existing Starlette/httpx deprecation warning |
| Frontend `npm test` | 25 passed |
| Frontend `npm run build` | Passed |
| Chromium Playwright with isolated synthetic SDK backend | 5 passed, no paid calls |
| Actual `start_disposable_test.py` processes with simulated trusted loopback ingress | Passed: migrations, health, auth, HTTPS scheme, Host/Origin, fixture import and inference denial |
| Same process with an untrusted peer; missing/wildcard/IPv4-zero/IPv6-zero allowlists | HTTPS scheme spoofing rejected; invalid startup configurations did not listen |
| Restart and path preservation | Old sessions invalid, new database empty, unrelated existing paths untouched |
| `python -m pip check`; `git diff --check` | Passed |

The password CLI regressions verify hash output, confirmation mismatch and refusal
of visible-input fallback on either prompt. The normal persistence tests remain
passing; disposable startup intentionally has different restart semantics.

Task 02B.2 adds launcher regressions for `0.0.0.0` binding, a platform-supplied
nondefault `PORT`, rejection of missing/wildcard/zero-prefix/hostname proxy
settings even when `RENDER=true`, and disabled forwarded-header trust in local
defaults. Integration tests run the real Uvicorn proxy middleware with the
production disposable app, proving an untrusted peer cannot forge HTTPS (even
by claiming a trusted IP in `X-Forwarded-For`), while auth, Host and Origin guards
remain effective for a simulated trusted peer. No simulated address is asserted
to belong to Render.

To reproduce the repository checks, use the installed virtual environment and
run `python -m pytest -q` from `backend`, then `npm test` and `npm run build` from
`frontend`. The README's synthetic browser harness reproduces the five browser
checks with `MARITIME_E2E_SYNTHETIC=1`, `MARITIME_E2E_DISPOSABLE_UI=1` and an
installed Chromium executable. The local process simulation is not evidence of
Render ingress behavior, live TLS, Windows CI or physical Android compatibility.

[render-example]: https://github.com/render-examples/fastapi/blob/f829276c68503f7afae195c3e3f778f085242cb0/README.md
[render-yaml]: https://github.com/render-examples/fastapi/blob/f829276c68503f7afae195c3e3f778f085242cb0/render.yaml

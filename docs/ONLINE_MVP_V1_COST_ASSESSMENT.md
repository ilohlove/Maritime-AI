# Online MVP V1 cost assessment

Assessment date: 2026-11-07. **Planning estimates, not verified quotes.**
No account was created, billing enabled, free plan accepted or paid API called.

## Verification status

Direct requests to Supabase pricing, Render Free documentation, Cloudflare Worker
pricing and OpenAI API pricing were attempted. Each was blocked by this session's
outbound network policy (HTTP CONNECT 403). Therefore current free availability,
account/card eligibility, S3 feature eligibility, region quotas and prices remain
unverified. Existing documentation describes past assessments; it does not prove
current eligibility. These exact provider checks require a user/operator browser:

- https://supabase.com/pricing
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/docs/guides/storage/s3/compatibility
- https://supabase.com/docs/guides/storage/buckets/fundamentals
- https://render.com/docs/free
- https://developers.cloudflare.com/workers/platform/pricing/
- https://openai.com/api/pricing/

## Monthly scenarios (USD, excluding taxes)

| Component | Evaluation assumption | Planning cost / caveat |
| --- | --- | --- |
| Separate Render backend | Free plan actually available and measured resource use fits | $0 conditional; sleep/cold starts, no durable disk/SLA; a second service can affect account allowances |
| Separate Worker/assets | Free tier supports measured body-hashing CPU and request traffic | $0 conditional; no purchased domain required; quota/CPU overages may require an authorized paid plan |
| Supabase PostgreSQL | Free project/region and sufficient database/connection quota | $0 conditional; no guarantee of ongoing availability, backups or inactivity policy |
| Supabase private storage | Free S3 access/storage/egress actually available | $0 conditional; 20 × 3 MB originals is at most 60 MB for the single owner, plus transfer/backup overhead |
| Lexical extraction/index | In-process pypdf, PostgreSQL GIN or SQLite FTS | No separate embedding/vector/OCR service bill |
| OpenAI disabled | Default example configuration | $0 inference; no key required |
| Backup destination | Operator-selected encrypted backup storage | Unpriced; cannot claim durable backup at $0 without provider verification |

The infrastructure planning target is **$0/month if every relevant free tier and
account allowance is confirmed**. This is not a promise that the stack can be
provisioned for $0. A paid hosting/database fallback must be quoted and separately
authorized; no subscription is selected automatically.

## Controlled inference examples

The template uses illustrative `gpt-4.1-mini` prices of $0.40 per million input
and $1.60 per million output tokens. They were **not verified in this session**.
Set the two backend price variables to current verified rates for the single
allowed model before activation. Cached-token discounts are ignored.

`estimated cost = (reported input × input rate + reported output × output rate) / 1,000,000`.

For example, a combined 3000 input / 500 output tokens across translation and
answering would cost approximately **$0.002** at those assumed rates; 1000 such
questions would be approximately **$2**, but the default application quota does
not permit that request volume.

Defaults reserve `2 × 20000 + 2000 + 512 = 42512` tokens per question. A daily
100000-token allowance admits only **two** questions/attempts, even if actual
usage is much smaller. No reservation is refunded after failure. At the assumed
input/output limits, both maximum inputs and outputs would cost $0.0200192 per
question; two questions/day for 30 days is approximately **$1.21/month** rounded
up. The UI deliberately uses a looser conservative bound (all reserved tokens
priced at the larger rate): the 100000/day allowance corresponds to at most
**$4.80 over 30 days** at $1.60/million. This bound applies only while identity,
quotas, model and prices are stable and correctly configured.

Actual provider charges are authoritative. Timeouts, disconnects and failed
parsing can charge tokens without reporting usage; full reservations remain in
the ledger and the UI flags that reported costs can be incomplete. Zero retries
prevents automatic duplicate requests. Restoring an earlier quota ledger can
permit additional spending and must keep inference disabled until reconciled.

## Capacity and connection evaluation

One backend worker uses at most two pooled PostgreSQL connections, plus temporary
operator/migration connections. A session pooler is the initial candidate for
IPv4-friendly access and connection accounting; no separate external paid pooler
is technically required for this load. Verify Supabase's actual direct/session/
transaction limits and all other clients against account-wide allowances.

The app permits one parser and one inference request concurrently by default.
Each online PDF is limited to 3 MB / 50 pages / 200000 extracted characters.
The parser's Linux address-space cap is 256 MiB; actual combined application RSS
and Worker HMAC CPU must still be measured on the proposed free services. A hard
quota is preferable to silently selecting a paid service or increasing spend.

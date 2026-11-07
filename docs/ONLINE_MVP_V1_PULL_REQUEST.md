# Add persistent Online MVP mode with private PDFs and controlled document AI

Base: `feature/signed-cloud-gateway` at `19ad79830595fd1ab13f4a0135f847e240e714f9`
Head: `feature/online-mvp-v1`

The disposable deployment cannot retain its SQLite database or PDF originals on
Render Free. This adds a separate, fail-closed online profile using certificate-
verified PostgreSQL and private S3-compatible storage, while preserving the
existing signed gateway protocol and synthetic/no-paid-AI restrictions.

Includes explicit Alembic schema evolution, owner-scoped profile/document APIs,
PostgreSQL RLS and lexical search, bounded isolated PDF extraction, recoverable
upload/deletion states, private evidence inspection, durable usage/cost reporting
and default-off inference activation. React exposes the mode, limits, source
inspection, document deletion and usage. Separate configuration examples avoid
changing the live Worker/Render settings.

See the architecture, deployment, security, cost and executed test reports in
`docs/ONLINE_MVP_V1_*.md`. No production rollout, cloud account creation, secret
change, private upload or paid inference was performed. Supabase S3/pooler
integration, provider eligibility and staging performance remain deployment gates.

This is a prepared PR body. Publishing the remote PR requires valid repository
credentials; `gh auth status` reports the session token invalid. No merge or
production deployment is requested or authorized.

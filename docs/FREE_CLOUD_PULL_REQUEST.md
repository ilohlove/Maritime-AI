# Assess zero-cost testing and add a secured disposable profile

The production MVP correctly rejects ephemeral storage, while free testing hosts
may discard SQLite, originals and quota state. This change adds an explicit,
production-secured synthetic-only test profile: a fresh isolated temp database,
exact bundled fixture import, disabled vessel writes, persistent UI/log data-loss
warning, rejection of real API keys and defense-in-depth inference denial.
Restarted quota state cannot permit paid calls; normal durable behavior is retained.

The official-source assessment compares Render/Koyeb and alternatives. Fly's
eligible no-card $1/7-day trial is a bounded initial-test option, not lasting free
hosting; HF Docker creation requires a paid plan in the current official source.
Render/Koyeb current terms remain blocked by the documentation allowlist, and
Pages password/SaaS guidance is an explicit rollout gate. No provider deployment
or live API verification is claimed. The network-only draft still needs user
Review/Save and Publish; no API-call domain/secret was added.

Validation: 117 backend, 25 frontend and five Chromium cases passed; regular/Pages
builds, advisory checks and a real loopback disposable-launcher/restart smoke
passed. Browser inference/UI are mocked and no real API key/call is used. No
resources were provisioned, no Hybrid merge occurred and Task 02B.2 is unstarted.
See docs/FREE_CLOUD_DEPLOYMENT_PLAN.md and docs/FREE_CLOUD_VERIFICATION.md.

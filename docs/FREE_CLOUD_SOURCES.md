# Task 02B.1 — official-source verification ledger

Checked 2026-11-05. Published provider sites are blocked by this environment's
restricted outbound policy (HTTP client reported ProxyError). Official source
repositories on github.com are reachable. This ledger distinguishes read source
from an unvisited published URL, and does not certify account eligibility or
that a source commit has already been published on the website.

## Sources actually read

| ID | Official source and immutable revision | Findings supported by the source |
| --- | --- | --- |
| R1 | [Render FastAPI example README](https://github.com/render-examples/fastapi/blob/f829276c68503f7afae195c3e3f778f085242cb0/README.md) and [render.yaml](https://github.com/render-examples/fastapi/blob/f829276c68503f7afae195c3e3f778f085242cb0/render.yaml), last example commit 2023-12-04 | Python/FastAPI deployment, Git repository deployment, PORT start command, template `plan: free`. **Old template is not verification of current billing/free-tier terms.** |
| K1 | [Koyeb FastAPI example](https://github.com/koyeb/example-fastapi/blob/f85072a17ed3c9b602ccb334eb28cf9bd19f4457/README.md), source commit 2026-11-01 | FastAPI support and GitHub deployment. Free **account signup** is described; this does not prove a free backend instance. |
| H1 | [Hugging Face Spaces overview](https://github.com/huggingface/hub-docs/blob/fe239b96beb76ea1c7aadaf42a4baa3c6e2ab522/docs/hub/spaces-overview.md), source commit 2026-11-05 | Static Spaces free; creating Docker/Gradio compute Spaces requires a paid plan. CPU Basic has no hourly charge but is not subscription-free. Default 2 CPU, 16 GB RAM, 50 GB nonpersistent disk; variables/secrets and outbound ports 80/443/8080. |
| H2 | [Docker Spaces](https://github.com/huggingface/hub-docs/blob/fe239b96beb76ea1c7aadaf42a4baa3c6e2ab522/docs/hub/spaces-sdks-docker.md), [storage](https://github.com/huggingface/hub-docs/blob/fe239b96beb76ea1c7aadaf42a4baa3c6e2ab522/docs/hub/spaces-storage.md), [billing](https://github.com/huggingface/hub-docs/blob/fe239b96beb76ea1c7aadaf42a4baa3c6e2ab522/docs/hub/billing.md) | FastAPI container support, runtime secrets, nonpersistent default storage, billed services/payment methods. No free durable SQLite volume is established. |
| F1 | [Fly.io trial](https://github.com/superfly/docs/blob/941ab703541804f90768d8fcf9b560c273ef11f0/about/free-trial.mdx), source commit 2026-11-04 | $1 trial credit, 7 days or exhaustion, no card initially; trial machines auto-stop after 5 minutes. Not a recurring free hosting tier. |
| F2 | [Fly.io pricing](https://github.com/superfly/docs/blob/941ab703541804f90768d8fcf9b560c273ef11f0/about/pricing.mdx) | Pay-as-you-go machines, volumes and outbound data. Example 512 MB machine $3.69/30 days, volumes $0.15/GB/month, region-dependent egress. |
| F3 | [Fly FastAPI guide](https://github.com/superfly/docs/blob/941ab703541804f90768d8fcf9b560c273ef11f0/python/frameworks/fastapi.mdx), [TLS](https://github.com/superfly/docs/blob/941ab703541804f90768d8fcf9b560c273ef11f0/networking/tls.mdx), [runtime secrets](https://github.com/superfly/docs/blob/941ab703541804f90768d8fcf9b560c273ef11f0/apps/secrets.mdx), [GitHub Actions guide](https://github.com/superfly/docs/blob/941ab703541804f90768d8fcf9b560c273ef11f0/launch/continuous-deployment-with-github-actions.mdx) | Official FastAPI deployment guide, TLS 1.2/1.3, encrypted secret vault with runtime env injection. The Actions guide was read for GitHub deployment support; no workflow or deployment was triggered. |
| G1 | [Pages limits](https://github.com/github/docs/blob/58b7b56aa507ad1269b9f8e9e89a172f0976c7ce/content/pages/getting-started-with-github-pages/github-pages-limits.md), [password/sensitive-transaction guidance](https://github.com/github/docs/blob/58b7b56aa507ad1269b9f8e9e89a172f0976c7ce/data/reusables/pages/no_sensitive_data_pages.md), [plan eligibility](https://github.com/github/docs/blob/58b7b56aa507ad1269b9f8e9e89a172f0976c7ce/data/reusables/gated-features/pages.md), source commit 2026-11-04 | Free plans cover public-repo Pages; commercial SaaS hosting restrictions; Pages should not send passwords/credit cards. 1 GB site, soft 100 GB/month bandwidth and build restrictions. |
| G2 | [Codespaces billing](https://github.com/github/docs/blob/58b7b56aa507ad1269b9f8e9e89a172f0976c7ce/content/billing/concepts/product-billing/github-codespaces.md), [lifecycle](https://github.com/github/docs/blob/58b7b56aa507ad1269b9f8e9e89a172f0976c7ce/content/codespaces/about-codespaces/understanding-the-codespace-lifecycle.md) | Personal Free accounts: 120 included compute units (2-core multiplier 2, about 60 running hours) and 15 GB-month storage. No valid payment method: usage blocked on exhaustion. Idle default 30 minutes; max session lifetime 12 hours. This is development compute, not managed always-on hosting. |
| G3 | [Codespaces port forwarding](https://github.com/github/docs/blob/58b7b56aa507ad1269b9f8e9e89a172f0976c7ce/content/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace.md) | Testing/debugging forwarded ports, visibility controls. Changing a public port to HTTPS forwarding makes it private; do not assume an arbitrary public Codespaces port supports the required Pages integration/security behavior. |

## Published pages still requiring direct verification

- Render: https://render.com/docs/free ; https://render.com/pricing ; https://render.com/docs/deploy-fastapi
- Koyeb: https://www.koyeb.com/docs/reference/instances ; https://www.koyeb.com/docs/faqs/pricing ; https://www.koyeb.com/pricing
- HF: https://huggingface.co/docs/hub/spaces-overview ; https://huggingface.co/pricing
- Fly: https://fly.io/docs/about/free-trial/ ; https://fly.io/docs/about/pricing/
- GitHub: https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
- OpenAI unit prices/minimum funding: https://openai.com/api/pricing/ and current official model/billing documentation. **No exact current OpenAI price or required minimum top-up is asserted.**

A network-only environment draft was saved for these documentation domains:
render.com, www.koyeb.com, koyeb.com, fly.io, huggingface.co, docs.github.com,
openai.com, developers.openai.com. It preserves the existing network presets and
adds no secrets, provider account or API-call permission. Saving the draft does
not apply it: Environment settings Review/Save and Publish are still required.
`api.openai.com` was deliberately not added. Direct Render/Koyeb current plan
verification remains blocked until this supported review workflow is completed.

Do not treat a button named Free, a free signup account, an old example YAML,
trial credit, or free hourly hardware inside a paid subscription as proof of a
recurring zero-cost backend. Recheck at checkout without creating paid resources.

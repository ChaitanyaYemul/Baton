# Deployment and judge access

## Verified local installation path

`npm ci && npm run build`, then install `requirements.txt` in Python 3.12+ and start one Uvicorn worker. The FastAPI process serves `dist/` plus `/api`. Local demo mode binds to `127.0.0.1:8000`. `GET /api/health` is a readiness endpoint. Docker Compose provides the same installable experience, with persistent data and localhost binding.

## Cloud deployment checklist

The application is designed for a Docker-capable service with a persistent disk, such as the API host proposed in Round 1. There is no active deployed URL in this document until a deployment has actually succeeded.

1. Build the repository Dockerfile on the selected host.
2. Attach a persistent disk at `/app/data`; run one replica and one Uvicorn worker. SQLite is not suitable for independent ephemeral replicas.
3. Expose container port 8000 through the host's HTTPS reverse proxy. Set `BATON_SECURE_COOKIE=1`.
4. For a public **synthetic-only** judge demo, explicitly set `BATON_DEMO=1` and clearly disclose the shared demonstration accounts. All demo users can alter the shared reviewer workspace; do not add confidential information.
5. For permissioned data, set `BATON_DEMO=0`, configure distinct `BATON_*_PASSWORD` values and share credentials only with the intended judge. Do not put secrets in a README, URL, frontend bundle or git commit.
6. Set `LLM_PROVIDER=groq`, `GROQ_API_KEY` and an available strict-output `GROQ_MODEL` (default `openai/gpt-oss-20b`). Gemini remains optional. Default `LLM_FALLBACK_PROVIDER=offline` avoids silently sending data to another cloud. Validate the provider with `scripts/check_llm.py` and review the mode label; an offline fallback is not a successful live model check. Backend secrets may be configured in the host environment or a local Git-ignored `.env` and require a restart.
7. Run the README walkthrough against the deployed origin. Verify cookie security, login, reconnect persistence, import error handling, role restrictions, receipt inspection and PDF/Markdown downloads.

Separate frontend hosting (for example Vercel) would require an authenticated same-origin `/api` reverse proxy and matching cookie settings. It is deliberately not configured as a static-only deployment: a static page cannot replace the Python evidence and access-control backend.

## Known limitations

One workspace/four role accounts; no invitations, password recovery, Supabase RLS or SSO. Regex PII detection has gaps. Imports and extraction are bounded and synchronous. Generic chat normalization, simple lexical categories and explicit conflict tuples in offline mode have limited recall. Ownership is a signal rather than an authorship model. Plan groups suggest confirmation steps rather than inferring new organisational facts. Downloads cannot be recalled. The database/activity log is not tamper proof against server administrators. Public GitHub/Gemini availability and free-tier limits may change. Docker and hosted model/network journeys require verification on the actual target environment.

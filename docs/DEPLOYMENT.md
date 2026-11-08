# Deployment and private judge access

Production: **a-7c4f/baton** at **https://baton-ruddy.vercel.app**. Vercel serves Vite assets and routes `/api/*` to the Python ASGI entrypoint `api/index.py`, pinned to Mumbai (`bom1`) near the database. Supabase Postgres provides persistent storage through its IPv4 transaction pooler. `/api/health` checks database connectivity and returns 503 when unavailable.

## Access and secrets

The participant chose private accounts. `BATON_DEMO=0` disables shared demonstration sign-in, including previously seeded demo password hashes. The initial reviewer password is generated in local `.env` as `BATON_REVIEWER_PASSWORD` and uploaded as a production Secret. It is never committed, put in a URL, or printed in tool output. The owner signs in as Kabir / Reviewer, then can create named invitations in **Team access**. Sharing invitations with judges is left to the participant; no email or message is sent automatically.

Invitations are unguessable, hashed at rest, valid for 24 hours and usable once. Recipients choose passwords of at least 12 characters. A role is assigned by the reviewer and cannot be changed through login parameters. Revocation disables the account and deletes sessions; current account state is checked on every request.

The production Secrets are `DATABASE_URL`, `GROQ_API_KEY` and `BATON_REVIEWER_PASSWORD`. Config variables select Groq, model, timeout, offline fallback, disabled shared demos and secure cookies. `scripts/configure_vercel.py` validates the linked team/project and uploads an explicit allowlist via stdin. `--only DATABASE_URL` changes only that Secret. It never places secret values in shell arguments.

The database login is `baton_runtime`, confined to the separate Baton project. It has no superuser, database/role-creation or RLS-bypass privileges. Enabling this credential and uploading the production payload were explicitly approved by the participant. Direct IPv6 connectivity worked locally but not from Vercel; the participant supplied the project's transaction-pooler hostname. Prepared statements are disabled for pooler compatibility.

## Releases

The local `.vercel/project.json` links the intended project and is Git-ignored. After build/tests, deploy with the explicit scope:

```sh
vercel deploy --prod --scope team_NgKr6jpZj9NVdACMjyWeqX3X --yes
```

The connector's scope error persisted after its consent flow. The participant completed the official CLI device login, allowing a correctly scoped deployment. No unscoped project was created. Git auto-deployment is not assumed connected until verified.

Python 3.12 and a flat pinned `requirements.txt` support reproducible cloud installs. The same versions are recorded in `requirements.lock.txt`. A nested requirements include failed in Vercel's parser and was replaced by a flat file. `.env`, `.env.local`, `.vercel`, local data and test artifacts are excluded from uploads. Vercel startup refuses to use ephemeral SQLite if `DATABASE_URL` is missing.

The three SQL migrations describe normalized data, invitations and consolidated RLS policies. The first two local filenames match Supabase's applied journal versions. After an MCP migration error, the policy-hardening SQL was applied in a transaction, verified through `pg_policies`, and recorded in migration history. Runtime credentials are separate from migration files.

## Local fallback and limits

README contains the local Uvicorn installation. Without `DATABASE_URL`, SQLite persists in `data/` and requires one worker. Docker Compose remains a localhost synthetic-demo fallback with a named volume; Docker runtime has not been tested here.

The product has one workspace and app-managed sessions, not Supabase Auth, SSO, password recovery or organisation-wide multi-tenancy. Redaction is heuristic. Import/extraction is synchronous and bounded. Chat normalization and offline conflict rules are limited. Ownership is a signal rather than a validated authorship score. Downloads cannot be revoked. Database administrators retain administrative access. Gemini validation was explicitly skipped; Groq remains the selected provider. No interview feedback, onboarding-time reduction or model accuracy benchmark is invented.

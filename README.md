# Baton

**A handover that shows its receipts.** Built for the Knowledge Handover Challenge, Round 2, by Chaitanya Shrikant Yemul.

Baton turns authorised notes, task exports, git history and conversations into an evidence-linked claim ledger. A reviewer resolves uncertainty and publishes a numbered snapshot. Successors receive approved knowledge filtered by their access to **all** its underlying evidence.

Production address: **https://baton-ruddy.vercel.app**. The participant has intentionally made the shared **Kabir / Reviewer** password visible beside the sign-in field for hackathon judges. Anyone visiting the site can use this reviewer account, including its editing and team-management permissions. Use synthetic or public demonstration data only. The older seeded demo passwords remain disabled in production. See [deployment details](docs/DEPLOYMENT.md) and [observed testing](docs/TESTING.md) for the earlier private-account setup and validation history.

Judges can select **Kabir / Reviewer** and use the password displayed on the sign-in page. The credential is intentionally public; this hosted workspace must not hold confidential data. Use **More tools → Team access** to create one-time invitations for named users. Recipients choose **Join with invitation**, set their own password, then sign in with **My named account**. Invitations expire in 24 hours; revocation terminates existing sessions. Model keys and database credentials remain backend-only and must never be published.

## Run locally

Requirements: Node.js 22+ and Python 3.12+. From the repository directory:

```sh
python -m venv .venv
# Windows:
.venv\Scripts\python -m pip install -r requirements.txt
npm ci
npm run build
# PowerShell:
$env:BATON_DEMO='1'
.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Alternatively, after installing dependencies, run `powershell -File scripts/start.ps1`.

macOS/Linux: use `.venv/bin/python`; start with `BATON_DEMO=1 .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`.

Docker alternative: `docker compose up --build`. It binds to localhost and persists SQLite in a named volume. This is also an installation package judges can run without a hosted account.

For frontend development, run the API and `npm run dev` in separate terminals. Vite proxies `/api` to port 8000. Build again before using the single-process production preview.

## Judge walkthrough

1. Sign in as **Kabir / Reviewer**, password **`baton-demo-2026`** (only enabled by `BATON_DEMO=1`).
2. Click **Load demo project** on Overview, or **Load synthetic demo** on Sources. This adds five synthetic sources: notes, chat, task CSV, git history and leads-only provider notes. Demo import only works in an empty workspace.
3. On Sources, click **Reconstruct project**. Inspect the model mode label. With no model key, extraction uses deterministic rules and verbatim lines.
4. Open **Claim ledger** and a receipt. Inspect the exact quote and locator. Two planted disagreements affect API deployment and SMS ownership. Both sides remain conflicting.
5. Resolve a conflict by rejecting the outdated card, opening the selected card and saving a named attestation; then approve it. Alternatively reject both if they cannot be resolved. Answer the cron ownership gap in **Ask the leaver**. Aarav can also answer in planned-exit mode, but Kabir must approve.
6. **Approve supported** handles only pending quote-verified/attested cards. Resolve or reject all remaining cards. The publication gate blocks pending uncertainty.
7. Open **Handover**, publish version 1, then sign out and sign in as **Meera / Technical successor** with the same demo password. Leads-only claims appear as content-free stubs; quotes, history, export and evidence search enforce the same restriction.
8. Read the continuation plan, acknowledge sections and download Markdown or PDF. Sign in as **Riya / Coordinator** to verify git-only knowledge is additionally restricted.
9. As reviewer, change a source to Leads only. On the reader's next load/API request, dependent facts disappear from current and historical views. Prior acknowledgements are invalidated for source permission changes. Downloaded files cannot be revoked.

## Configuration

Copy `.env.example` to `.env` and set your backend key there. `.env` is ignored by Git and excluded from Docker images. The backend loads it on startup; host-provided environment variables take precedence. Restart after changing configuration. Docker Compose passes the model settings to the container.

For Groq, set `LLM_PROVIDER=groq` and `GROQ_API_KEY` locally. The default model is `openai/gpt-oss-20b`, using strict structured output. Check the connection with `.venv\Scripts\python scripts/check_llm.py`; this sends one synthetic example and prints only the provider result and validated claim count. A successful result starts with `Groq`; offline fallback is not a live validation success. Never paste keys into the frontend or commit them.

| Variable | Purpose |
| --- | --- |
| `BATON_DEMO` | Explicit `1` enables public synthetic demo credentials. Defaults to off. |
| `BATON_DB` | SQLite file path; default `data/baton.sqlite3`. |
| `DATABASE_URL` | Restricted Supabase Postgres connection. Hosted Baton uses its IPv4 transaction pooler with RLS; SQLite remains a local fallback. Backend-only secret. |
| `BATON_REVIEWER_PASSWORD` | Unique reviewer password for hosted use. |
| `BATON_SUCCESSOR_PASSWORD` | Unique technical successor password. |
| `BATON_COORDINATOR_PASSWORD` | Unique coordinator password. |
| `BATON_LEAVER_PASSWORD` | Unique departing-member password. |
| `BATON_SECURE_COOKIE` | Set `1` behind HTTPS. |
| `LLM_PROVIDER` | `groq`, `gemini`, `offline`, or `auto` (default: prefer configured Groq, then Gemini, otherwise offline). |
| `GROQ_API_KEY` | Backend-only Groq credential. |
| `GROQ_MODEL` | Default `openai/gpt-oss-20b`; choose a Groq model supporting strict structured output. |
| `LLM_TIMEOUT_SECONDS` | Read/write timeout per attempt, default 15 seconds; clamped to 5–30. Connect timeout is 5 seconds. |
| `LLM_FALLBACK_PROVIDER` | Default `offline`. Set `gemini` explicitly to opt in to sending redacted text to Google after a Groq failure. |
| `GEMINI_API_KEY` | Optional Google model credential, backend only. |
| `GEMINI_MODEL` | Configurable model ID; default `gemini-2.5-flash`. Check availability with your provider. |

Never enable demo credentials for confidential data. Production uses `BATON_DEMO=0`, a unique reviewer password, HTTPS and secure cookies. Other users join through reviewer-issued invitations. Named memberships have four permission roles in one workspace. Authentication is application-managed; Supabase Auth, SSO, password recovery and organisation-wide multi-tenancy remain future work.

In **Handover**, create actions linked to approved evidence, set owners/deadlines, and schedule Day 1/Week 1/Day 30 work. Assigned owners can update status; reassignment requires the reviewer. Changes invalidate receipts. **Ask the leaver** adds priority, due dates and reviewer/departing-member routing with sudden-exit fallback. Version diffs cover owner/status/type/attestation as well as text; historical receipts use their original version.

## Validation

```sh
npm run build
.venv\Scripts\python -m pytest -q
```

The API tests use isolated temporary databases and remove real model credentials from their environment. They cover the complete journey, approval gating, forged citations, paraphrase uncertainty, invalid input, redaction, role restrictions, version immutability, permission revocation, evidence/search/export leakage, sudden exit, structured Groq requests, bounded retries, error sanitisation and explicit cloud fallback. Model tests use mocked HTTP responses, not paid calls.

With `DATABASE_URL` configured, `python scripts/check_rls.py` runs rollback-only canary tests under the restricted runtime role. `python scripts/verify_supabase.py` imports/reconstructs only the known synthetic fixture and checks API visibility; it refuses to modify a workspace containing other source hashes.

## Submission material

- [Round 2 submission and feature matrix](docs/ROUND2.md)
- [Architecture, evidence contract and privacy](docs/ARCHITECTURE.md)
- [External tools and AI disclosure](docs/DISCLOSURES.md)
- [Deployment and limitations](docs/DEPLOYMENT.md)

No user interviews, recall percentage, transition-time reduction, cloud deployment, or live model evaluation are claimed without evidence. The original PDFs' demonstration numbers and impact targets are plans, not measured results.

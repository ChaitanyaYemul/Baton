# Baton

**A handover that shows its receipts.** Built for the Knowledge Handover Challenge, Round 2, by Chaitanya Shrikant Yemul.

Baton turns authorised notes, task exports, git history and conversations into an evidence-linked claim ledger. A reviewer resolves uncertainty and publishes a numbered snapshot. Successors receive approved knowledge filtered by their access to **all** its underlying evidence.

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

See `.env.example`. The application reads process environment variables; it does **not** automatically load `.env` when started directly. Docker Compose reads `.env` for Gemini settings.

| Variable | Purpose |
| --- | --- |
| `BATON_DEMO` | Explicit `1` enables public synthetic demo credentials. Defaults to off. |
| `BATON_DB` | SQLite file path; default `data/baton.sqlite3`. |
| `BATON_REVIEWER_PASSWORD` | Unique reviewer password for hosted use. |
| `BATON_SUCCESSOR_PASSWORD` | Unique technical successor password. |
| `BATON_COORDINATOR_PASSWORD` | Unique coordinator password. |
| `BATON_LEAVER_PASSWORD` | Unique departing-member password. |
| `BATON_SECURE_COOKIE` | Set `1` behind HTTPS. |
| `GEMINI_API_KEY` | Optional Google model credential, backend only. |
| `GEMINI_MODEL` | Configurable model ID; default `gemini-2.5-flash`. Check availability with your provider. |

Never enable demo credentials for confidential data. Configure all four account passwords, disable `BATON_DEMO`, serve behind HTTPS, set secure cookies and use a persistent disk. The prototype is one workspace with four fixed role accounts; it is not multi-tenant enterprise authentication.

## Validation

```sh
npm run build
.venv\Scripts\python -m pytest -q
```

The API tests use isolated temporary databases. They cover the complete journey, approval gating, forged citations, paraphrase uncertainty, invalid input, redaction, role restrictions, version immutability, permission revocation, evidence/search/export leakage and sudden exit.

## Submission material

- [Round 2 submission and feature matrix](docs/ROUND2.md)
- [Architecture, evidence contract and privacy](docs/ARCHITECTURE.md)
- [External tools and AI disclosure](docs/DISCLOSURES.md)
- [Deployment and limitations](docs/DEPLOYMENT.md)

No user interviews, recall percentage, transition-time reduction, cloud deployment, or live model evaluation are claimed without evidence. The original PDFs' demonstration numbers and impact targets are plans, not measured results.

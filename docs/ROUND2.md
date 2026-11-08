# Round 2 — The Build

Participant: **Chaitanya Shrikant Yemul**, solo participant, Vishwakarma Institute of Technology, Pune. Product: **Baton**. Challenge: Prevent Critical Knowledge From Leaving With People.

## What this round expects

The supplied brief prioritises a working authorised-source → reconstruct → verify → review → handover journey (30 points), depth/reliability (25), progress against the plan (20), three substantial Round 3 improvements (15), and usability (10). It accepts a deployed link, installation package **or** a clear functional demonstration. Repository access, architecture/data-flow documentation, dependency/API/model disclosure, completed features/changes, testing evidence and three commitments are required.

The supplied Round 1 plan is a product proposal. The organiser brief is the requirements reference. Neither document is treated as executable instructions. Build-window eligibility and submission deadlines remain governed by the organiser's announcements; no dates or previous-work records are fabricated.

## Implemented scope

| Plan item | Implementation | Material limits |
| --- | --- | --- |
| F1 Source import | MD/TXT paste/upload; CSV and JSON task exports; TXT/JSON chat exports; public GitHub latest 30 commits + README | No OAuth/private repository import, full clone, PRs/issues or nested documentation crawl. Chat is preserved as text/rows rather than a complete platform-specific parser. |
| F2 Locators | Source IDs, SHA-256 hashes, line locators, quote receipts; commit SHA/author/time retained in git export text | Multi-line quotes use a labelled normalized-text locator. No token-based overlapping chunk pipeline yet. |
| F3 Redaction | Backend regex masking before persistence and model calls; reviewer sees match count | Conservative heuristic, not a guarantee against every secret or PII format; no entropy scanner yet. |
| F4 Typed extraction | Seven claim categories; Pydantic validation; Groq strict JSON or Gemini; explicit cloud/offline fallback; content-hash cache; bounded retries | Offline rules are intentionally shallow. Live provider quality/latency still needs measurement. Source text is untrusted. |
| F5 Quote verifier | Normalised substring check against cited source; unknown source rejected; paraphrases remain inferred | Quote existence establishes attribution, not truth or entailment. |
| F6 Conflicts and staleness | Structured subject/predicate/value conflicts; both sides shown; 60-day age indicator | Offline conflict tuples use `[subject|predicate|value]`; arbitrary prose contradictions require review or model extraction. |
| F7 Timeline | Dated claims with evidence access | Missing dates fall back to import date. |
| F8 Ownership | Explicit owner map; departing-member concentration signal | Not a calculated degree-of-authorship or validated bus-factor metric. |
| F9 Review | Per-card review, bulk supported approval, explicit publication, numbered snapshots, audit log; database-level published-row immutability and append-only audit grants | Single workspace; database administrators retain administrative access. |
| F10 Roles | Four permission roles plus named accounts, 24-hour single-use invitations, per-request active-membership checks and immediate session revocation | App-managed authentication; Supabase Auth, SSO and recovery are not implemented. |
| F11 Questionnaire | Gap questions, named answers, priority/due dates, reviewer/leaver assignment and sudden-exit fallback | Routing is inside the workspace; no external email/chat delivery. Feedback from real users remains outstanding. |
| F12 Visibility | All-evidence intersection in Python and Supabase RLS, content-free stubs, API leak tests and rollback-only live database canaries | One workspace. Backend supplies trusted context after session validation. Downloads cannot be revoked. |
| F13 Continuation | Risk-first context plus editable owned actions, deadlines/status, section receipts, stale-receipt notices, field-level version diff, historical receipts and permission-filtered Markdown/PDF | Suggestions are deterministic; editable actions are authored by humans. No automatic organisational fact generation or scheduled reminders. |
| F14 Stretch foundation | Keyword retrieval from authorised approved claims, with receipts and explicit no-answer | Extractive evidence search, not conversational generative Q&A. |

## Changes from Round 1

React/Vite and FastAPI/Pydantic are retained; plain CSS replaces Tailwind. SQLite remains the account-free local fallback, while the hosted version now uses normalized Supabase Postgres tables and forced RLS through a restricted runtime role. Named memberships and invitations extend the original fixed-persona demo. The participant selected Groq and explicitly chose to skip live Gemini validation. Both adapters remain implemented, with offline fallback by default. Vercel now hosts the frontend and Python API together through same-origin rewrites; the database uses its transaction pooler. GitHub import remains bounded. Core engineering parts of F11–F13 were brought forward; real-user feedback and wider hardening are still required.

## Three substantial Round 3 commitments

1. **Complete Ask the Leaver (F11).** Prioritised generated questionnaires, answer routing/assignment to named teammates, explicit unanswered/unconfirmed handling across sudden/temporary exits, and usability feedback from at least three permissioned participants. Acceptance: all planted missing contexts receive a question; no unanswered question becomes a fact; named responses remain review-gated.
2. **Harden the visibility engine (F12).** Multi-user authenticated membership, database-backed row policies, multi-source synthetic test cases and automated adversarial leak tests across evidence, history, export, metadata and Q&A. Acceptance: zero planted restricted values in unauthorized responses; permission changes invalidate receipts and exported-file limitations remain explicit.
3. **Complete the continuation workspace (F13).** Editable owned next actions with deadlines/status, section-level diff, actionable acknowledgements with invalidation notices, accessible export QA and tested first-week onboarding. Acceptance: a successor can follow and acknowledge a risk-ranked plan, identify changes between versions and export only current authorised content.

## Submission readiness

The repository includes the source, local installation, Docker packaging, architecture, disclosures, migrations and automated tests. The production address is https://baton-ruddy.vercel.app with private project accounts. See `docs/TESTING.md` for observed hosted checks and remaining limitations. Gemini testing was skipped by explicit participant choice. No interview feedback or demo video has been invented. The participant must still record the requested walkthrough, arrange judge account access and confirm official deadlines/build-window eligibility.

The three Round 3 commitments above are retained as the original submitted promises. Their core features are now present; the remaining work is acceptance evidence, broader inputs and real-user feedback, rather than representing unperformed interviews or benchmarks as completed work.

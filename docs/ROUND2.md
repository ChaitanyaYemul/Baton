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
| F9 Review | Per-card approve/reject/edit/attest, bulk supported approval, explicit publication, immutable numbered snapshots, activity log | Single workspace; local DB admins can alter records. Audit is application append-only, not tamper-proof storage. |
| F10 Roles | Reviewer, technical successor, coordinator, departing member; server sessions and current source labels | Fixed accounts; no invitation flow or Supabase Auth/RLS yet. |
| F11 Early foundation | Gap questions, named answers, planned/sudden exit routing | Reviewer workflow rather than external question delivery. |
| F12 Early foundation | All-evidence visibility, neutral restricted stubs, server API leak tests | Browser cannot revoke downloaded copies; no enterprise policy framework. |
| F13 Early foundation | Risk-first Day 1/Week 1/Day 30 groups, section receipt, version diff, Markdown/PDF | Plan is a deterministic grouping of claims with a suggested confirmation step, not a model-generated schedule. Diff tracks added/changed and removed count, not a rich field-level comparison. |
| F14 Stretch foundation | Keyword retrieval from authorised approved claims, with receipts and explicit no-answer | Extractive evidence search, not conversational generative Q&A. |

## Changes from Round 1

React/Vite and FastAPI/Pydantic are retained. Plain CSS replaces planned Tailwind. SQLite replaces Supabase for a zero-account runnable installation; server-side authorization is mandatory, but the planned database RLS second lock is still pending. The participant selected Groq as the preferred cloud provider after reporting Gemini errors/latency. Both adapters are implemented with an offline fallback; a second cloud provider requires explicit configuration. GitHub REST import is deliberately bounded. Early foundations for F11–F13 were implemented without claiming the later-round hardening is complete.

## Three substantial Round 3 commitments

1. **Complete Ask the Leaver (F11).** Prioritised generated questionnaires, answer routing/assignment to named teammates, explicit unanswered/unconfirmed handling across sudden/temporary exits, and usability feedback from at least three permissioned participants. Acceptance: all planted missing contexts receive a question; no unanswered question becomes a fact; named responses remain review-gated.
2. **Harden the visibility engine (F12).** Multi-user authenticated membership, database-backed row policies, multi-source synthetic test cases and automated adversarial leak tests across evidence, history, export, metadata and Q&A. Acceptance: zero planted restricted values in unauthorized responses; permission changes invalidate receipts and exported-file limitations remain explicit.
3. **Complete the continuation workspace (F13).** Editable owned next actions with deadlines/status, section-level diff, actionable acknowledgements with invalidation notices, accessible export QA and tested first-week onboarding. Acceptance: a successor can follow and acknowledge a risk-ranked plan, identify changes between versions and export only current authorised content.

## Submission readiness

The repository includes source, local installation, Docker packaging, architecture, disclosures and automated tests. See `docs/TESTING.md` for observed results. Hosting and live Gemini integration must be verified in the chosen environment. No interview feedback or demo video has been invented. Record a short walkthrough using the README journey and attach it if the organiser requests one. Confirm official deadlines and build-window eligibility before submission.

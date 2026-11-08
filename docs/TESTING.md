# Observed validation — 8 November 2026

## Automated checks

- `npm run build`: TypeScript validation and Vite production build passed.
- `.venv/Scripts/python.exe -m pytest -q`: **30 passed** after adding Groq support. One upstream Starlette warning reports that HTTPX test transport is deprecated in favour of HTTPX2; tests still pass.
- `git diff --check`: passed before initial commit.

The suite checks the judge's import → reconstruction → review → publish → successor journey, publication blocking, source quote existence, forged citations, paraphrase demotion, immutable published content, all-role leak checks, direct evidence authorization, historical/export/search restrictions, source-label revocation, deleted evidence, malformed/empty/duplicate input, unauthorised import, SSRF URL rejection, redaction, chat timestamps, leaver attestation, sudden-exit restrictions, session requirements, mutation header protection, multi-source intersection, acknowledgement invalidation, model-outage fallback, duplicate source lines and malformed dates.

Seeded fixture observations: five source types/files, 16 extractive claims, four conflicting cards representing two disagreements (API deployment and SMS ownership), one explicit missing-context question. Demo values and commit identifiers are synthetic. Tests do not establish recall on real project data or a measured reduction in onboarding time.

Groq integration tests use synthetic keys and mocked HTTP responses. They cover strict-schema formatting, successful extraction through the quote verifier, no retries for permanent HTTP errors, short/long rate limits, bounded timeout retries, truncated/empty/malformed output, named provider errors without upstream secret leakage, opt-in Gemini fallback, missing-key/offline behaviour, provider/model cache invalidation, Groq-key source redaction and retrying fallback results rather than caching an outage. Autouse fixtures remove developer credentials before every test; no live provider calls are made by the suite.

## Browser observations

Using the local production frontend and real FastAPI server in the in-app browser, verified reviewer sign-in, loading the five synthetic sources, reconstruction, claim-ledger display, evidence drawer with source/line/exact quote, individual approval, navigation and overview. Inspected the desktop layout and a 390 × 844 mobile layout. The browser check found an overly broad phone redaction pattern matching chat dates; this was corrected and a regression test added. Offline classification was also corrected so ordinary task-board Todo states do not become gap questions.

The complete publication and successor flow was exercised through the API test client. It has not yet been recorded as an uninterrupted browser demo. PDF responses are checked for valid PDF signature; detailed visual export QA and accessibility assistive-technology testing remain Round 3 tasks.

## Not yet verified

Live Groq/Gemini calls, public GitHub network import against a real target, Docker build/runtime, Linux CI execution and hosted deployment. A Groq key has been created by the participant but is not yet configured locally; a live evaluation is not claimed. `scripts/check_llm.py` is available for a synthetic-only live check once it is saved in the local `.env` and the backend is restarted. Deterministic extraction is a fully labelled runnable fallback. GitHub rate-limit/network errors return a recoverable explanation. Hosting readiness is documented rather than falsely reported as deployed.

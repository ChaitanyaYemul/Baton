# Observed validation — 8 November 2026

## Automated checks

- `npm run build`: TypeScript validation and Vite production build passed.
- `.venv/Scripts/python.exe -m pytest -q`: **35 passed** after Supabase/advanced features. One upstream Starlette warning reports that HTTPX test transport is deprecated in favour of HTTPX2; tests still pass. Each run uses a separate workspace-local temporary directory so concurrent runs cannot overwrite the same fixture databases.
- `git diff --check`: passed before initial commit.
- GitHub Actions also passed on Linux for the implementation release: [Baton checks](https://github.com/ChaitanyaYemul/Baton/actions/runs/42457051731).

The suite checks the judge's import → reconstruction → review → publish → successor journey, publication blocking, source quote existence, forged citations, paraphrase demotion, immutable published content, all-role leak checks, direct evidence authorization, historical/export/search restrictions, source-label revocation, deleted evidence, malformed/empty/duplicate input, unauthorised import, SSRF URL rejection, redaction, chat timestamps, leaver attestation, sudden-exit restrictions, session requirements, mutation header protection, multi-source intersection, acknowledgement invalidation, model-outage fallback, duplicate source lines and malformed dates.

Seeded fixture observations: five source types/files, 16 extractive claims, four conflicting cards representing two disagreements (API deployment and SMS ownership), one explicit missing-context question. Demo values and commit identifiers are synthetic. Tests do not establish recall on real project data or a measured reduction in onboarding time.

Groq integration tests use synthetic keys and mocked HTTP responses. They cover strict-schema formatting, successful extraction through the quote verifier, no retries for permanent HTTP errors, short/long rate limits, bounded timeout retries, truncated/empty/malformed output, named provider errors without upstream secret leakage, opt-in Gemini fallback, missing-key/offline behaviour, provider/model cache invalidation, Groq-key source redaction and retrying fallback results rather than caching an outage. Autouse fixtures remove developer credentials before every test; no live provider calls are made by the suite.

Advanced tests cover named-account role spoofing, invitation/password validation, single-use invitation reuse, immediate member revocation, disabling old seeded demo passwords, action ownership and source-access revocation, acknowledgement invalidation after action changes, question routing in sudden exits, owner/status/attestation version changes and historical receipt access.

## Live Supabase and hosted checks

The separate Baton Supabase project was created in the participant-approved organisation. A live restricted-account connection confirmed `rolbypassrls=false`. `scripts/verify_supabase.py` persisted five synthetic sources and 16 draft claims and checked role views. `scripts/check_rls.py` independently tested default-deny context, private credential-table protection, multi-source visibility intersection, changed source labels and published-row immutability. All synthetic canaries were rolled back. Supabase's security advisor reports no findings; consolidated policies removed its RLS performance warnings. Two unused-index informational notices are expected on this new small dataset; no sensitive access is granted to address them.

Production is https://baton-ruddy.vercel.app. The page and database health endpoint return 200; unauthenticated `/api/workspace` returns 401. Direct IPv6 connectivity failed from Vercel, so the participant supplied the IPv4 transaction-pooler hostname. The first requirements-include build also failed; a flat pinned dependency list resolved it.

The hosted fixture test verifies private reviewer sign-in, one-time invitations and named registration, a named departing-member gap answer, review/approval/publication, successor/coordinator/lead-only restrictions, owned continuation actions, receipt invalidation, Markdown and PDF responses. Temporary QA accounts are revoked before the probe exits. These are automated operations on an explicitly synthetic project, not participant interviews or real organisational attestations.

The full-project Groq check initially hit its output limit: the default reasoning effort consumed 6,639 of 8,192 completion tokens, and the adapter rejected the incomplete JSON and used offline extraction. GPT-OSS extraction now explicitly uses low reasoning effort. One subsequent synthetic request stopped normally, returned 15 schema-valid claims and reported about 2.7 seconds of provider processing. The final hosted reconstruction also returned `Groq · openai/gpt-oss-20b` with 15 draft claims. This is one fixture observation, not an accuracy/latency benchmark. Hosting is pinned to Mumbai near the database. Private production login works, shared demo login is rejected, and all temporary QA memberships remain revoked.

## Browser observations

Using the local production frontend and real FastAPI server in the in-app browser, verified reviewer sign-in, loading the five synthetic sources, reconstruction, claim-ledger display, evidence drawer with source/line/exact quote, individual approval, navigation and overview. Inspected the desktop layout and a 390 × 844 mobile layout. The browser check found an overly broad phone redaction pattern matching chat dates; this was corrected and a regression test added. Offline classification was also corrected so ordinary task-board Todo states do not become gap questions.

An isolated localhost SQLite fixture was also exercised in the browser through source loading, reconstruction, questionnaire priority/assignment, named attestation, conflict rejection, bulk approval, publication and continuation-action creation/status updates. The final continuation screen was inspected at tablet (980 pixels) and mobile (390 pixels) widths; DOM measurements confirmed no horizontal overflow. A screenshot of this synthetic QA workspace is stored in `docs/assets/handover-preview.jpg`.

The hosted successor PDF was parsed and did not contain planted lead-only values. All three pages of a revised authorized synthetic export were rendered and visually inspected. Receipts are grouped with their claim sections and page footers are present. Automated PDF checks also verify a valid signature. A recorded demonstration and assistive-technology testing remain outstanding.

## Not yet verified

Public GitHub import against a real target, Docker runtime, wider model-quality/latency benchmarks, assistive-technology checks and real-user feedback remain outstanding. Gemini validation was explicitly skipped; Groq is the selected provider. Live Groq extraction now passes on the complete synthetic fixture as described above. This does not establish a recall percentage or onboarding-time reduction. GitHub/provider network errors remain recoverable, with labelled offline extraction as the fallback.

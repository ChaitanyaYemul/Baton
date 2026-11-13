# Baton Round 3 · The Finish

**CodeFrontier · Challenge 01 · Chaitanya Shrikant Yemul · Team chaitanyayemul39**

Baton helps a successor take over work when decisions, risks and dependencies live in different project sources. A reviewer imports authorised files, reconstructs statements, checks their evidence, resolves uncertainty and publishes a numbered handover. Readers receive content according to their project membership and access to each supporting source.

## Three commitments from the Round 2 report

| Commitment | Round 3 behaviour | How to verify it |
| --- | --- | --- |
| Adaptive Ask the Leaver questionnaire | Generate questions from unresolved gaps. Route a question to a named project teammate with source access. Short or uncertain replies produce a suggested follow-up. A reviewer confirms a complete reply and then approves the claim. | Generate the cron-ownership question, open its evidence, assign it, answer “Not sure,” submit a fuller answer, confirm it and publish. |
| Independent project workspaces | Named accounts can create projects and use the project selector. Memberships, invitations and roles are project-specific. Existing accounts can accept invitations to additional projects using their existing password. | Join two projects with different roles. Compare sources and version history, and export each project separately. Revoke a membership and confirm the other remains available. |
| Personal catch-up | Handover compares the latest approved version with the reader’s most recent acknowledgement. It lists changed owners, newly approved risks and overdue or blocked actions. Each row opens evidence for its version. | Acknowledge version 1 as one successor, then acknowledge version 2 as another. Open both catch-up views and compare the results. Restrict a supporting source and reload. |

The questionnaire uses deterministic, context-sensitive prompts and completeness hints. A human still checks the substance of each reply. In sudden-exit mode, the reviewer can route questions to an available teammate.

## Technology and responsible design

The React and TypeScript interface uses the existing FastAPI backend. SQLite supports local use. The hosted adapter uses PostgreSQL with forced row-level security. The server resolves each request against the signed-in account’s membership and role for the selected project. PostgreSQL adds restrictive project policies to source and role policies. The migration maps Round 2 data and invitations into project 1.

Groq remains the selected live extraction provider. The local demo and automated acceptance cases use deterministic extraction from synthetic files. Python checks quote attribution. Review and publication remain separate decisions. Evidence, historical snapshots, catch-up and exports check current source permissions.

The public reviewer login is scoped to the existing synthetic demonstration project. Use named accounts for independent projects. Use authorised sources only. Pattern-based masking has limits, and downloaded files remain with their recipients after access changes.

Project switching uses a labelled native selector. The questionnaire and catch-up controls support keyboard interaction, retain visible labels, and display status in text. The existing reduced-motion styles apply. Formal assistive-technology testing and external participant feedback remain to be collected.

## Verification

- The production frontend build and all 38 Python tests passed locally. Run `npm run build` and `python -m pytest -q` to reproduce.
- All three Round 3 API acceptance journeys also passed through the PostgreSQL adapter with the restricted runtime role against disposable PGlite databases. They cover named routing, follow-ups, reviewer confirmation, two project roles for one identity, revocation, cross-project evidence, history and exports, and distinct acknowledgement baselines.
- The standalone SQL checks passed locally and on a native PostgreSQL 16 service in GitHub Actions. The checks apply every migration and verify project-specific reads and writes, repeated identifiers in separate projects, assigned answers and source revocation.
- A recorded Chromium walkthrough exercised the questionnaire, review and publication, catch-up evidence and project switching using synthetic data. The 390 px mobile catch-up screen fit without horizontal scrolling.
- Demo inputs are synthetic. Production provider quality, onboarding time saved and participant feedback require separate measurement.

## Judge walkthrough

1. Sign in as a reviewer and load the synthetic project in local demo mode. On Sources, select **Reconstruct project**.
2. In **More tools → Team access**, invite a named successor. Use **Join with invitation** in a second session to register the successor. Sign in using **My named account**.
3. In **Questions**, generate questions and assign the cron gap to the successor. In the successor session, view evidence and submit “Not sure,” then answer the suggested follow-up with a name and a reference to the relevant instructions.
4. Confirm the reply as reviewer. Resolve or reject remaining uncertain claims, approve the supported claims and publish version 1. In the successor session, acknowledge a section in **Handover**.
5. As reviewer, update an owner on a draft statement and import a new synthetic risk. Reconstruct, approve and publish version 2. Create a blocked continuation action. As successor, open **Your catch-up** and inspect a versioned receipt.
6. As the named successor, select **New project**. Create a project and inspect its empty sources and history. Switch back to the first project. The selector shows the different role for each project.

## Limitations and roadmap

The deployed provider, Docker runtime, assistive-technology compatibility and real-world onboarding outcomes need further validation. The GitHub importer covers public README content and recent commits. Questionnaire hints use rules and need reviewer judgement. Future work includes scoped private connectors, assignment reminders and broader usability studies.

Chaitanya Shrikant Yemul is the solo participant from Vishwakarma Institute of Technology, Pune. He set the requirements and directed the interface decisions. OpenAI Codex assisted substantially with implementation, testing and documentation. The application uses React, TypeScript, Vite, FastAPI, Pydantic, Psycopg, SQLite, Supabase, Groq, ReportLab, pytest and GitHub Actions. Website imagery and logo credits are documented separately.

# Tools, datasets and contribution disclosure

All application source in this repository was created with significant assistance from **OpenAI Codex** in the user's Round 2 build session. Codex generated the backend, frontend, test suite, synthetic fixtures, packaging and documentation. The participant must review, understand, validate and accurately describe personal contributions before submission. Do not represent generated code as unaided work.

No starter application, commercial template, copied handover implementation, real workplace export or participant interview dataset was used. Synthetic names/events/commits/provider details in `backend/engine.py` are invented; the demo commit hashes are not real repository evidence. The visual baton is CSS rather than stock/generated imagery.

| Dependency/service | Use | License / condition |
| --- | --- | --- |
| React / React DOM | Interface | MIT |
| Vite / TypeScript / React Vite plugin | Build tooling | MIT / Apache-2.0 / MIT |
| Lucide React | Icons | ISC |
| FastAPI / Starlette / Uvicorn | HTTP server | MIT / BSD-3-Clause / BSD-3-Clause |
| Pydantic | Schema validation | MIT |
| HTTPX | GitHub/Gemini HTTP calls | BSD-3-Clause |
| pytest | Automated API tests | MIT |
| ReportLab | Runtime PDF export | BSD-style; review installed package license |
| Python SQLite / crypto standard library | Persistence / password and session handling | Python standard-library terms; SQLite public domain |
| Google Fonts DM Sans and Manrope | Optional remote typography | SIL Open Font License; local system fallbacks work offline |
| Google Gemini API | Optional JSON extraction | Provider terms; requires user's backend key; not needed in offline mode |
| GitHub REST API | Public README + recent commits | GitHub API terms; unauthenticated rate limits apply |
| Docker official Node/Python images | Optional packaging | Upstream image and included component licences |

Refer to lockfiles and installed dependency licence files for exact resolved versions and transitive dependencies. No runtime AI calls are made when `GEMINI_API_KEY` is absent. A configured key sends redacted imported text to Google; regex redaction cannot certify complete anonymisation.

Official technical references consulted: [Gemini generateContent](https://ai.google.dev/api/generate-content), [GitHub repository API](https://docs.github.com/en/rest/repos/repos), [GitHub contents API](https://docs.github.com/en/rest/repos/contents). Product requirements come from the two PDFs supplied by the participant; no external numerical impact claims are reused as measured results.

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
| HTTPX | GitHub/Groq/Gemini HTTP calls | BSD-3-Clause |
| python-dotenv | Backend-only local environment loading | BSD-3-Clause |
| Psycopg / psycopg-binary | Restricted Postgres connections and JSONB adaptation | LGPL-3.0; bundled binary components retain their upstream licences |
| pytest | Automated API tests | MIT |
| ReportLab | Runtime PDF export | BSD-style; review installed package license |
| Python SQLite / crypto standard library | Persistence / password and session handling | Python standard-library terms; SQLite public domain |
| Google Fonts DM Sans and Manrope | Optional remote typography | SIL Open Font License; local system fallbacks work offline |
| Google Gemini API | Optional JSON extraction | Provider terms; requires user's backend key; not needed in offline mode |
| Groq API | Optional strict JSON extraction | Provider terms; requires user's backend key; no Groq SDK dependency |
| GitHub REST API | Public README + recent commits | GitHub API terms; unauthenticated rate limits apply |
| Supabase Postgres | Persistent data and database-enforced RLS | Supabase terms; database credentials remain backend-only |
| Vercel | Vite CDN and Python/FastAPI hosting | Vercel terms; production Secrets remain backend-only |
| Docker official Node/Python images | Optional packaging | Upstream image and included component licences |

Refer to lockfiles and installed dependency licence files for exact resolved versions and transitive dependencies. No runtime AI calls are made when offline mode is selected or no selected provider key exists. A configured provider sends redacted imported text to Groq or Google according to backend configuration; a second cloud fallback requires explicit opt-in. Regex redaction cannot certify complete anonymisation.

Groq integration references: [API compatibility](https://console.groq.com/docs/openai), [structured outputs](https://console.groq.com/docs/structured-outputs), [error handling](https://console.groq.com/docs/errors). Mocked integration tests establish request/response behaviour; live speed and extraction quality require validation with an actual key.

Official technical references consulted: [Gemini generateContent](https://ai.google.dev/api/generate-content), [GitHub repository API](https://docs.github.com/en/rest/repos/repos), [GitHub contents API](https://docs.github.com/en/rest/repos/contents). Product requirements come from the two PDFs supplied by the participant; no external numerical impact claims are reused as measured results.

# Architecture and trust contract

```mermaid
flowchart TD
  A[Authorised notes / tasks / chat / public git] --> B[Validate and normalise exports]
  B --> C[Redact, hash, persist source and access label]
  C --> D[Gemini JSON adapter or explicit offline extractor]
  D --> E[Pydantic candidate validation]
  E --> F[Deterministic quote attribution verifier]
  F --> G[Conflicts / gaps / dates / explicit owners]
  G --> H[Draft claim ledger]
  H --> I[Named human corrections and review]
  I --> J[Explicit publish gate]
  J --> K[Immutable approved snapshots]
  K --> L[Current all-evidence source permission check]
  L --> M[Role handover / evidence / search / history / exports]
```

## Storage and deployment

React uses same-origin JSON endpoints. Vite proxies to FastAPI in development; the production Python process serves built frontend assets. SQLite stores workspace JSON transactionally and separate password/session tables. A process-local lock serializes writes; deploy a **single worker/replica** with a persistent volume. This implementation is sized for a small hackathon project, not high-concurrency organisations. Snapshot content is deep-copied; source permission labels remain live.

## Evidence contract

Candidates contain text, category, owner, source ID, exact quote and optional subject/predicate/value. Code alone sets statuses:

- **Verified** means an extractive statement exactly matches a quote found in the cited redacted source. It proves attribution, not the truth of the source.
- **Inferred** covers failed quote matches and model paraphrases even when a quote exists. A human must attest or reject them.
- **Conflicting** means different explicit values share a subject/predicate. Neither wins automatically.
- **Gap** means context requires an answer.
- **Attested** means a named authenticated human supplied/corrected the statement, with a server timestamp. Original source receipts are retained; they need not literally contain the human correction.

Only verified and attested items can be approved. Publication requires every draft item to have a review decision; approved items become the handover, rejected items stay outside the snapshot. Human attestation and reviewer approval are separate actions.

## Access and privacy

Reviewer: core + technical + leads. Successor/leaver: core + technical. Coordinator: core. Every claim requires every evidence source to exist and be accessible. Restricted stubs disclose only existence, an opaque ID and the reviewer contact; titles, quotes, categories, conflict edges and dates are removed. All relevant read endpoints reapply access checks, including historical snapshots, search, export and evidence inspection. Non-reviewers do not receive the activity log. Successor/coordinator see only published snapshots. Leaver sees accessible draft gaps to answer them.

Sessions are cryptographically random, hashed in SQLite, time-limited (8 hours) and sent as HttpOnly SameSite Strict cookies. Passwords use PBKDF2-HMAC-SHA256 (200,000 rounds); login is rate limited per direct client IP. Mutation requests require a custom same-origin header and no CORS is enabled. Hosted use requires secure cookies and TLS. Account credentials are provided through environment variables, not checked into source. Fixed role accounts and no MFA/password-reset/invite flow remain explicit limitations.

Regex masking runs before source persistence/model calls and on named human corrections. Unredacted source content is not retained. Redaction is heuristic; use synthetic data for judging. GitHub import accepts only strict public github.com repository URLs and sends requests only to fixed api.github.com endpoints with redirects disabled. Imports are capped at 250k characters each and 40 sources. No live monitoring is implemented.

Permission/source changes invalidate current acknowledgement records. They cannot revoke previously downloaded files, screenshots or already-rendered browser content. A reader must make a new request/reload. Removed evidence makes historical dependent claims inaccessible and draft claims require review. Audit events are appended by application code but are not cryptographically sealed.

## AI and outages

The backend only sends redacted sources to Gemini when its key is configured. Model responses are validated and cached against source identity/content/model settings. On network errors, rate limits or invalid model output, reconstruction falls back to labelled deterministic extraction. The offline path quotes source lines directly and uses narrow category heuristics, retaining uncertainty instead of fabricating missing facts. Model calls run synchronously with a timeout; a durable background queue is deferred. Source instructions are treated as data in the extraction prompt. Quote verification and human approval remain independent controls even if prompt injection affects extraction.

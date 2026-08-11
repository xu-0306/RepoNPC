# RepoNPC v1 Technical Specification

| Field | Value |
| --- | --- |
| Status | **Approved** |
| Version | 0.1.0 |
| Product | RepoNPC v1 |
| Audience | Implementation Agents, reviewers, maintainers |
| Last updated | 2026-08-10 |
| Approval date | 2026-08-10 |

Application implementation is authorized under this approved specification. The words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY, and OPTIONAL are normative as described by RFC 2119.

## 1. System boundary

RepoNPC is a single-owner, open-source, self-hosted application that:

1. builds a searchable evidence index from owner-selected public GitHub repositories and owner-authored configuration;
2. presents a bilingual pixel-RPG portfolio on an external web page;
3. answers visitor questions using a configured OpenAI-compatible or Ollama model;
4. attaches server-validated immutable GitHub citations;
5. supplies a script-free GitHub Profile README card;
6. lets the owner edit public configuration and approved character assets through an authenticated admin UI.

The production deployment is one application image plus persistent storage. Index building runs separately in GitHub Actions using the same Python package.

## 2. Requirement catalogue

### 2.1 Functional requirements

| ID | Requirement |
| --- | --- |
| FR-001 | The system MUST load and validate a versioned `reponpc.yml` without source-code edits and MUST reject unknown keys by default. |
| FR-002 | The indexer MUST resolve and record an exact commit SHA for every enabled public repository and the configuration repository. |
| FR-003 | The indexer MUST enforce path, file type, symlink, secret, generated-content, and size exclusions before text enters the index. |
| FR-004 | The indexer MUST create stable line-addressable evidence records using Tree-sitter for Python, JavaScript/TypeScript, Go, and Rust, with a bounded text fallback. |
| FR-005 | The system MUST provide lexical retrieval through SQLite FTS5/BM25 for words, symbols, paths, and multilingual text. |
| FR-006 | The system MUST provide semantic retrieval with a configurable multilingual embedding provider whose identity and dimension are recorded in the bundle. |
| FR-007 | The retriever MUST fuse independently ranked lexical and vector candidates using Reciprocal Rank Fusion (RRF) and apply only documented metadata policies. |
| FR-008 | Every evidence record and answer claim MUST preserve the distinction between `OWNER_ASSERTION`, `REPOSITORY_FACT`, and `MODEL_INFERENCE`. |
| FR-009 | The chat service MUST answer only from retrieved evidence and MUST treat all repository/configuration text as delimited untrusted data. |
| FR-010 | The model MUST emit evidence IDs rather than URLs; the backend MUST validate them and construct immutable GitHub permalinks. |
| FR-011 | The service MUST abstain or qualify the response when available evidence is insufficient, especially for person-level claims without owner assertions. |
| FR-012 | The provider layer MUST support OpenAI-compatible chat/embedding APIs, Ollama chat/embedding APIs, and the default local sentence-transformers embedding adapter through declared capability contracts. |
| FR-013 | The public chat API MUST deliver validated answers, citations, completion data, and failures using the SSE contract in this document. |
| FR-014 | The public site MUST show profile/project content, suggested questions, evidence-linked chat, index/model status, and responsive bilingual controls. |
| FR-015 | The character system MUST support built-in customization, the specified custom sprite-sheet format, required animation states, accessibility, and reduced motion. |
| FR-016 | The card service MUST provide sanitized, self-contained SVG, GIF fallback, and static preview outputs with light/dark and `zh-TW`/`en` variants. |
| FR-017 | The admin surface MUST use the single-admin session, password, CSRF, backoff, expiration, and revocation controls defined here. |
| FR-018 | The admin UI/API MUST read, validate, preview, and edit configuration and character assets without exposing secrets. |
| FR-019 | Admin writeback MUST use blob-SHA conflict detection and MUST modify only `reponpc.yml` or `assets/character/` in the configured repository. |
| FR-020 | GitHub Actions MUST validate sources, build a reproducible immutable bundle, publish it to a GitHub Release, and update the stable manifest last. |
| FR-021 | The runtime MUST poll, verify, atomically activate, retain, and roll back bundles according to this document. |
| FR-022 | All visitor/admin workflows and equivalent answers MUST support Traditional Chinese (`zh-TW`) and English (`en`). |
| FR-023 | The system MUST expose public status plus process/readiness health endpoints without revealing secrets or sensitive diagnostics. |
| FR-024 | The admin UI MUST generate ready-to-copy GitHub README snippets for SVG, GIF, light/dark, and locale selections. |

### 2.2 Non-functional requirements

| ID | Requirement |
| --- | --- |
| NFR-001 | Security: untrusted inputs MUST NOT change system policy, execute code/tools, create arbitrary network requests, traverse paths, or inject active HTML/SVG. |
| NFR-002 | Privacy: raw conversations MUST NOT be persisted by default; logs MUST omit secrets, full prompts, full answers, and raw IP addresses. |
| NFR-003 | Availability: an invalid update MUST NOT replace the last known-good bundle; first boot without a bundle MUST present an actionable setup state. |
| NFR-004 | Performance: with the reference corpus (up to 50,000 chunks), warm retrieval p95 MUST be <= 750 ms on the reference 4-core/8-GB CPU host, excluding model time. |
| NFR-005 | Streaming: after the validated model response is available, the first SSE event MUST be emitted within 250 ms; the overall public request timeout defaults to 45 seconds. |
| NFR-006 | Retrieval quality: the committed evaluation set MUST achieve Recall@8 >= 85%. |
| NFR-007 | Answer quality: >= 95% of emitted citations MUST resolve correctly, >= 90% of factual answer claims MUST be entailed, and >= 90% of deliberately unsupported questions MUST produce a correct abstention. |
| NFR-008 | Language parity: equivalent `zh-TW` and `en` evaluation questions MUST retrieve materially equivalent evidence at least 90% of the time. |
| NFR-009 | Accessibility: visitor and admin UIs MUST meet WCAG 2.2 AA for implemented flows, including keyboard use, focus, labels, contrast, and reduced motion. |
| NFR-010 | Portability: the documented Docker Compose installation MUST work on current Docker Engine for x86_64 Linux without external database/vector services. |
| NFR-011 | Reproducibility: identical configuration, source commits, schema, and model inputs MUST produce equivalent evidence IDs and bundle contents except declared build metadata. |
| NFR-012 | Observability: health, update, retrieval, latency, usage, and error data MUST be diagnosable by request ID without logging sensitive bodies. |
| NFR-013 | Maintainability: Python and TypeScript public module boundaries MUST be typed, tested, and covered by locked dependency graphs. |
| NFR-014 | Cost control: per-IP/global concurrency, request limits, output limits, and daily generation budgets MUST be enforced before paid provider work is accepted. |

## 3. Normative repository structure

Implementation MUST start with this structure. New directories are allowed when they preserve the module boundaries; moving or merging these boundaries requires an ADR update.

```text
RepoNPC/
├─ AGENTS.md
├─ README.md
├─ LICENSE
├─ pyproject.toml
├─ uv.lock
├─ package.json
├─ pnpm-lock.yaml
├─ pnpm-workspace.yaml
├─ reponpc.example.yml
├─ .env.example
├─ compose.yml
├─ Dockerfile
├─ apps/
│  └─ web/
│     ├─ index.html
│     ├─ package.json
│     ├─ vite.config.ts
│     └─ src/
│        ├─ app/
│        ├─ api/
│        ├─ features/admin/
│        ├─ features/card/
│        ├─ features/chat/
│        ├─ features/character/
│        ├─ features/profile/
│        ├─ i18n/
│        └─ test/
├─ src/reponpc/
│  ├─ api/                 # FastAPI routes, dependencies, headers, error mapping
│  ├─ admin/               # auth, sessions, CSRF, GitHub writeback
│  ├─ bundles/             # manifest polling, validation, atomic activation
│  ├─ cards/               # SVG/GIF/PNG generation and sanitization
│  ├─ chat/                # prompt assembly, policy validation, SSE orchestration
│  ├─ config/              # YAML and environment schemas
│  ├─ domain/              # evidence, citation, profile, common contracts
│  ├─ indexing/            # GitHub input, parsing, chunking, bundle builder CLI
│  ├─ providers/           # chat and embedding interfaces/adapters
│  ├─ retrieval/           # FTS, vectors, filters, RRF, context packing
│  ├─ runtime/             # runtime SQLite, budgets, rate limits, audit
│  ├─ observability/       # structured safe logging and metrics
│  └─ main.py
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ security/
│  ├─ contract/
│  └─ fixtures/repos/
├─ evals/
│  ├─ questions.yml
│  ├─ expected_evidence.yml
│  └─ README.md
├─ docs/
│  ├─ PROJECT_CONTEXT.md
│  ├─ TECHNICAL_SPEC.md
│  ├─ ACCEPTANCE_CRITERIA.md
│  ├─ DECISIONS.md
│  ├─ IMPLEMENTATION_PLAN.md
│  ├─ OPERATIONS.md
│  ├─ SECURITY.md
│  └─ SPRITE_FORMAT.md
└─ .github/workflows/
   ├─ ci.yml
   ├─ build-index.yml
   └─ release.yml
```

`OPERATIONS.md`, `SECURITY.md`, and `SPRITE_FORMAT.md` are implementation deliverables and MUST be complete before the relevant release gate. Their required content is defined in sections 15 and 16.

## 4. Configuration contract

### 4.1 Sources and precedence

- Public portfolio/index settings come from UTF-8 `reponpc.yml` in `REPONPC_CONFIG_REPOSITORY` at `REPONPC_CONFIG_BRANCH`.
- Runtime secrets and deployment-specific values come from environment variables or mounted secret files.
- Secrets MUST NOT be accepted in YAML.
- Environment variables MUST NOT override public semantic fields in ways that make the built bundle disagree with its manifest.
- Unknown YAML keys MUST fail validation unless a future schema version explicitly defines an extension namespace.

### 4.2 Root YAML shape

`schema_version` MUST equal integer `1`. The exact public structure is:

```yaml
schema_version: 1
locales:
  default: zh-TW
  supported: [zh-TW, en]
profile: {}
repositories: []
character: {}
card: {}
retrieval: {}
```

The normative populated example is `reponpc.example.yml`. Rules:

- Localized text is a mapping whose keys exactly match `locales.supported`.
- Missing localized required text is a validation error; fallback is allowed only for optional fields.
- Repository `slug` is `owner/name`; duplicates are invalid.
- Repository `ref` is optional. If omitted, the GitHub default branch is resolved at build time. A branch, tag, or SHA may be supplied, but the bundle always records the resolved full commit SHA.
- `include` and `exclude` use repository-relative gitignore-style patterns. Absolute paths and `..` are invalid.
- Owner claim IDs match `^[a-z][a-z0-9_-]{2,63}$` and are globally unique.
- Claim `kind` is `role`, `responsibility`, `achievement`, or `context`.
- Owner claims, localized profile headline/bio, and repository role/summary fields become `OWNER_ASSERTION` evidence sourced to the exact configuration commit and line range. Suggested questions and visual copy do not become evidence.
- A repository `role` is presentation shorthand; person-level answers SHOULD cite an explicit item in that repository's `claims` list rather than rely only on the shorthand.
- URLs MUST be absolute HTTPS, except `http://localhost` and private-network Ollama URLs are environment-only and never part of this YAML.
- `character.mode` is exactly `builtin` or `custom`.
- A custom sprite path MUST be below `assets/character/`, must be a `.png`, and must satisfy section 12.
- `card.revision` is a non-negative integer used for cache-busting snippets.
- Retrieval weights are non-negative finite numbers and at least one source weight must be positive.
- `embedding.model`, `embedding.dimension`, and `embedding.query_prefix` become part of the bundle compatibility contract.

### 4.3 Default limits

| Setting | Default | Hard maximum |
| --- | ---: | ---: |
| Configuration file | 256 KiB | 1 MiB |
| Source file | 512 KiB | 2 MiB |
| Indexed text per repository | 25 MiB | 100 MiB |
| Indexed text across corpus | 100 MiB | 250 MiB |
| Evidence records/chunks | 50,000 | 100,000 |
| Chunk characters | 6,000 | 12,000 |
| Chunk lines | 200 | 400 |
| Fallback overlap | 12 lines | 40 lines |
| Public message | 2,000 Unicode scalar values | 4,000 |
| Supplied history | 6 messages / 6,000 chars | 10 / 12,000 |
| Retrieval candidates | 30 per channel | 100 |
| Final context records | 8 | 20 |
| Context token budget | 24,000 or provider limit | provider limit |
| Model output | 1,000 tokens | 2,000 |
| Character upload | 1 MiB | 2 MiB |
| Downloaded bundle | 512 MiB | 1 GiB |

Configuration can lower defaults. Raising a value above a hard maximum requires source changes, an ADR, and new resource/security tests.

## 5. Indexing contract

### 5.1 Allowed inputs

The indexer MUST access only:

- `reponpc.yml` and allowlisted character assets in the configuration repository;
- enabled public GitHub repositories named in the validated configuration;
- GitHub metadata required for repository name, description, topics, default branch, and resolved commit.

Every GitHub redirect and final host MUST remain on the configured GitHub host allowlist. The indexer MUST NOT fetch URLs found inside repository content.

### 5.2 Mandatory exclusions

The indexer MUST skip:

- Git submodules and symlinks;
- binary or undecodable files;
- `.env*`, credential/key/certificate files, `.git/`, dependency/vendor directories, build output, coverage, caches, generated documentation, minified assets, maps, archives, media, database files, and lock files;
- paths excluded by global rules or repository configuration;
- files that exceed configured limits;
- content matching a high-confidence secret detector.

A skipped-file summary records path, reason code, and size but MUST NOT record secret-like content. Secret scanning is defense in depth; owners remain responsible for public repository content.

### 5.3 Parsing and stable identifiers

- Supported Tree-sitter languages are Python, JavaScript, TypeScript/TSX, Go, and Rust.
- Complete named functions, methods, classes, structs, interfaces, traits, modules, and exported declarations SHOULD form chunks when within limits.
- Oversized syntax nodes are split on child boundaries, then bounded line windows.
- Unsupported text uses heading-aware sections for Markdown and line windows for other text.
- Every record stores exact one-based inclusive `start_line` and `end_line`.
- Evidence ID is `E_` plus the first 24 lowercase hexadecimal characters of SHA-256 over: `schema_version`, evidence class, repository slug, commit SHA, normalized POSIX path, line range, and normalized content hash.
- Explicit owner claims retain their stable YAML claim ID in `owner_claim_id`; they use the same content-addressed `E_...` evidence-ID format as every other indexed record.
- Line endings normalize to LF for hashing; displayed excerpts preserve safe text, not control characters.

### 5.4 Embeddings

The default local embedding contract is:

- adapter: `local_sentence_transformers` through the common embedding-provider abstraction;
- model: `intfloat/multilingual-e5-small`;
- dimension: `384`;
- normalized float32 output;
- query prefix: `query: `;
- evidence prefix: `passage: `.

An owner MAY select another supported OpenAI-compatible or Ollama embedding provider. Index and runtime query embeddings MUST have identical provider semantics, model identifier, dimension, prefixes, and normalization. A mismatch prevents readiness. Embedding API keys remain GitHub Action/runtime secrets and never enter bundles.

## 6. Index database schema

`index.sqlite` is built once, integrity-checked, then opened read-only by the application. Schema version `1` contains at least these logical tables (additional indexes are allowed):

```sql
CREATE TABLE bundle_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE repositories (
  repo_id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  commit_sha TEXT NOT NULL CHECK(length(commit_sha) = 40),
  default_branch TEXT,
  github_html_url TEXT NOT NULL,
  summary_zh_tw TEXT,
  summary_en TEXT
);

CREATE TABLE sources (
  source_id INTEGER PRIMARY KEY,
  repo_id INTEGER NOT NULL REFERENCES repositories(repo_id),
  path TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  language TEXT,
  source_type TEXT NOT NULL,
  UNIQUE(repo_id, path, content_sha256)
);

CREATE TABLE evidence (
  evidence_id TEXT PRIMARY KEY,
  evidence_class TEXT NOT NULL CHECK(evidence_class IN
    ('OWNER_ASSERTION','REPOSITORY_FACT','MODEL_INFERENCE')),
  source_id INTEGER NOT NULL REFERENCES sources(source_id),
  owner_claim_id TEXT,
  title TEXT,
  symbol TEXT,
  content TEXT NOT NULL,
  start_line INTEGER NOT NULL CHECK(start_line >= 1),
  end_line INTEGER NOT NULL CHECK(end_line >= start_line),
  language TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE VIRTUAL TABLE evidence_fts_terms USING fts5(
  evidence_id UNINDEXED, title, symbol, path, content,
  tokenize='unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE evidence_fts_trigram USING fts5(
  evidence_id UNINDEXED, title, symbol, path, content,
  tokenize='trigram'
);

CREATE TABLE embeddings (
  evidence_id TEXT PRIMARY KEY REFERENCES evidence(evidence_id),
  model_id TEXT NOT NULL,
  dimension INTEGER NOT NULL,
  normalized INTEGER NOT NULL CHECK(normalized = 1),
  vector_f32_le BLOB NOT NULL
);
```

`MODEL_INFERENCE` rows are optional derived portfolio summaries created during indexing. They MUST list supporting immutable evidence IDs in `metadata_json`. Runtime answer inferences are ephemeral and follow the same dependency rule but are not written into the immutable database.

The lexical search channel combines ranks from the term and trigram tables. Queries shorter than three characters MAY use a bounded exact `instr` fallback. It MUST treat user text as values and generate only allowlisted FTS syntax; raw user query syntax is forbidden.

## 7. Retrieval and context contract

1. Normalize the question for locale without translating code symbols, paths, or product names.
2. Apply explicit filters only when confidently extracted (repository, language, evidence class, source type).
3. Retrieve the configured candidate count independently from lexical and vector channels.
4. Within the lexical channel, fuse term and trigram ranks. Across lexical and vector channels, use RRF score `sum(weight_c / (k + rank_c))`, with default `k=60`, lexical weight `1.0`, vector weight `1.0`.
5. Add configured source/evidence weights after ranking as documented multipliers. Owner assertions do not receive an unconditional global relevance boost.
6. Deduplicate identical/overlapping ranges and cap any one repository at six of the final eight records unless the question names that repository.
7. Pack records in rank order within the smaller of the configured and provider context budget.
8. Delimit each record with an assigned request-local source ID (`S1`, `S2`, ...) plus evidence class and metadata. Clearly state that record text is data, not instruction.

Search results and logs use persistent evidence IDs. The model sees only request-local IDs.

## 8. Answer and citation policy

### 8.1 Model output contract

The provider is instructed to produce an answer envelope equivalent to:

```json
{
  "answer_markdown": "... [S1] ...",
  "used_source_ids": ["S1"],
  "inferences": [
    {"statement": "...", "source_ids": ["S1", "S2"]}
  ],
  "insufficient_evidence": false
}
```

Native structured output is used when supported; otherwise RepoNPC parses a constrained text envelope and MAY perform one repair attempt. The model MUST NOT output source URLs. Markdown is sanitized and only a conservative display subset is rendered.

### 8.2 Validation before public delivery

The backend MUST buffer the complete provider result before releasing answer text to the public stream. It then:

- rejects unknown or unselected source IDs;
- removes model-authored links presented as citations;
- requires every material factual claim to carry one or more known source markers;
- requires person-level role, authorship, responsibility, employment, seniority, achievement, or impact claims to cite at least one matching `OWNER_ASSERTION`;
- requires every inference to cite supporting non-inference evidence;
- converts selected IDs into immutable citation objects;
- returns an abstention response if parsing or policy validation cannot safely recover.

After validation, the service emits answer text in SSE `token` chunks. This preserves the streaming UI contract without exposing unvalidated partial claims.

### 8.3 Immutable GitHub permalink

For GitHub.com, the server constructs:

```text
https://github.com/{owner}/{repo}/blob/{40-char-commit}/{percent-encoded-path}#L{start}-L{end}
```

Owner assertion citations point to `reponpc.yml` in the configuration repository at its indexed commit. Repository slug, host, commit, path, and lines come only from validated index records. A single-line citation uses `#L{start}`.

## 9. Public HTTP API

All JSON is UTF-8. `/api/public/*` responses set `Cache-Control: no-store` except card/profile resources with explicit validators. Every response carries `X-Request-ID`. Clients MAY send an opaque UUID in `X-Request-ID`; invalid values are replaced.

### 9.1 `GET /api/public/profile`

Query: optional `locale=zh-TW|en`; default is configured locale.

Success `200`:

```json
{
  "schema_version": 1,
  "locale": "zh-TW",
  "profile": {
    "display_name": "Example Developer",
    "headline": "...",
    "bio": "...",
    "location": null,
    "avatar_url": null,
    "links": [{"label": "GitHub", "url": "https://github.com/example"}]
  },
  "repositories": [{
    "slug": "example/project",
    "summary": "...",
    "role": "...",
    "tags": ["Python"],
    "demo_url": null
  }],
  "suggested_questions": ["這個專案解決什麼問題？"],
  "character": {"mode": "builtin", "asset_url": "/api/public/character.png", "revision": 1},
  "index": {"version": "...", "built_at": "...", "repository_count": 1}
}
```

The endpoint returns `503 INDEX_UNAVAILABLE` before first bundle activation. It uses an ETag derived from bundle version and locale.

### 9.2 `POST /api/public/chat/stream`

Request content type is `application/json`:

```json
{
  "message": "請介紹你最有代表性的專案",
  "locale": "zh-TW",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

`history` is optional, must alternate roles starting with `user`, and is treated as untrusted conversational context. The client sends it on each request; the server does not persist it by default.

If validation/rate/readiness fails before streaming, the endpoint returns a normal JSON error. Once accepted, it returns `200 text/event-stream`, `Cache-Control: no-store`, `Connection: keep-alive`, and `X-Accel-Buffering: no`.

Events, in required order:

```text
event: metadata
data: {"request_id":"...","index_version":"...","locale":"zh-TW","evidence_count":8}

event: token
data: {"delta":"..."}

event: citations
data: {"items":[{"id":"S1","evidence_id":"E_...","evidence_class":"REPOSITORY_FACT","repository":"owner/repo","commit_sha":"...","path":"src/app.py","start_line":10,"end_line":24,"title":"...","excerpt":"...","url":"https://github.com/..."}]}

event: complete
data: {"finish_reason":"stop","usage":{"input_tokens":1234,"output_tokens":321},"insufficient_evidence":false}
```

- There is exactly one `metadata`, zero or more `token`, at most one `citations`, and exactly one terminal `complete` on success.
- A failure after SSE starts emits exactly one terminal `error` event with the common error body and closes the stream; it does not emit `complete`.
- Keepalive comments (`: keepalive`) MAY occur at least every 15 seconds and carry no semantics.
- `usage` fields are nullable when the provider does not report them.

### 9.3 Card and character endpoints

- `GET /api/public/card.svg?theme=light|dark&locale=zh-TW|en&rev=N`
- `GET /api/public/card.gif?theme=light|dark&locale=zh-TW|en&rev=N`
- `GET /api/public/card.png?theme=light|dark&locale=zh-TW|en&rev=N`
- `GET /api/public/character.png?rev=N`

Unsupported query values return `400 VALIDATION_ERROR`. Outputs use an ETag including bundle version, variant, and revision. SVG response headers include `Content-Type: image/svg+xml`, `X-Content-Type-Options: nosniff`, and a restrictive `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src data:`. SVG contains no scripts, event handlers, foreign objects, or external URLs.

### 9.4 Status and health

`GET /api/public/status` returns `200` even when degraded:

```json
{
  "status": "ready|setup_required|degraded|offline",
  "index": {"ready": true, "version": "...", "last_checked_at": "...", "update_error": null},
  "model": {"ready": true, "provider": "ollama", "last_checked_at": "..."},
  "chat_available": true
}
```

Sensitive provider URLs, model credentials, stack traces, filesystem paths, and admin state are excluded.

- `GET /healthz` returns `200` when the process event loop responds.
- `GET /readyz` returns `200` only when a valid index is active, runtime storage is usable, and the configured chat/embedding contracts are compatible; otherwise `503`.

## 10. Common error contract

JSON failures use:

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Localized safe message",
    "request_id": "...",
    "details": {},
    "retry_after_seconds": 30
  }
}
```

`details` contains field-level validation data only and never internal exceptions. Required stable codes:

| HTTP | Code | Meaning |
| ---: | --- | --- |
| 400 | `VALIDATION_ERROR` | Body/query/config value invalid. |
| 401 | `AUTHENTICATION_REQUIRED` / `INVALID_CREDENTIALS` | Admin authentication failed or missing. |
| 403 | `CSRF_FAILED` / `WRITE_NOT_ALLOWED` | Security policy rejected the operation. |
| 404 | `NOT_FOUND` | Allowlisted resource does not exist. |
| 409 | `CONFIG_CONFLICT` | Expected Git blob SHA no longer matches. |
| 413 | `PAYLOAD_TOO_LARGE` | Config, question, or asset limit exceeded. |
| 422 | `CONFIG_INVALID` / `ASSET_INVALID` | Structurally valid request fails domain validation. |
| 429 | `RATE_LIMITED` / `DAILY_BUDGET_EXHAUSTED` / `CONCURRENCY_LIMIT` | Cost/abuse limit reached. |
| 502 | `PROVIDER_ERROR` / `GITHUB_ERROR` | Upstream failed safely. |
| 503 | `INDEX_UNAVAILABLE` / `MODEL_UNAVAILABLE` / `SERVICE_NOT_READY` | Required capability unavailable. |
| 504 | `PROVIDER_TIMEOUT` | Configured model exceeded timeout. |

## 11. Admin contract

### 11.1 Authentication

- One admin username is configured by `REPONPC_ADMIN_USERNAME`.
- `REPONPC_ADMIN_PASSWORD_HASH` is a PHC-format Argon2id hash generated by `reponpc admin hash-password`; plaintext passwords are never configured or logged.
- Login uses a generic failure message and exponential per-IP/account backoff.
- Successful login creates a random 256-bit server-side session and sets `__Host-reponpc_session` with `Secure`, `HttpOnly`, `Path=/`, and `SameSite=Strict`.
- Idle expiration defaults to 30 minutes; absolute expiration defaults to 12 hours. Refresh rotates the session ID.
- A random CSRF token is returned in the login/refresh JSON body, stored only in browser memory, hashed in the session row, and required as `X-CSRF-Token` on every state-changing authenticated request.
- Logout revokes the current session. Logout-all requires the current password and increments the admin session epoch.

### 11.2 Endpoints

| Method and path | Contract |
| --- | --- |
| `POST /api/admin/session` | `{username,password}` -> `{csrf_token,expires_at,absolute_expires_at}` and cookie. |
| `POST /api/admin/session/refresh` | Auth + CSRF -> rotated session and CSRF token. |
| `DELETE /api/admin/session` | Auth + CSRF -> `204`, revoke current session. |
| `DELETE /api/admin/sessions` | Auth + CSRF + `{password}` -> `204`, revoke all sessions. |
| `GET /api/admin/config` | Return `{content,blob_sha,commit_sha,updated_at}` for `reponpc.yml`. |
| `POST /api/admin/config/validate` | `{content}` -> normalized errors/warnings and parsed preview; no write. |
| `POST /api/admin/config/preview` | `{content}` -> localized profile/card/character preview; no write or model call. |
| `PUT /api/admin/config` | `{content,expected_blob_sha,commit_message}` -> commit result or `CONFIG_CONFLICT`. |
| `POST /api/admin/assets/character/validate` | Multipart PNG -> validation result and ephemeral preview; no write. |
| `PUT /api/admin/assets/character/{filename}` | PNG + `expected_blob_sha` + commit message -> allowlisted GitHub commit. |
| `GET /api/admin/readme-snippet` | Query variant -> `{markdown,asset_url,target_url}`. |
| `POST /api/admin/index/dispatch` | Trigger allowlisted `build-index.yml`; return dispatch acknowledgement. |
| `GET /api/admin/index/status` | Return last publication/activation detail and safe error diagnostics. |

Admin APIs set `Cache-Control: no-store`. Login and state-changing requests require same-origin `Origin`/`Referer` validation in addition to CSRF. Admin responses never return environment values, password hashes, GitHub tokens, provider keys, or private provider URLs.

### 11.3 GitHub writeback

- The token MUST be a fine-grained token limited to contents/actions permissions on `REPONPC_CONFIG_REPOSITORY`.
- The target branch is `REPONPC_CONFIG_BRANCH`; it is never supplied by the browser.
- Allowed target paths are exactly `reponpc.yml` and normalized paths matching `assets/character/*.png`. Nested paths, deletion, renames, and arbitrary filenames are rejected in v1.
- `expected_blob_sha` is mandatory for replacement. Creation uses explicit `null` and fails if the file exists.
- Configuration is fully validated before commit. Assets are decoded and validated, not trusted by MIME/extension alone.
- Commit messages are length-limited plain text with a safe default.
- Every write creates a safe audit record with time, path, resulting commit SHA, request ID, and outcome, but not file bodies or credentials.

## 12. Character and card asset contract

### 12.1 Custom sprite sheet

The v1 custom sheet is a transparent, non-animated PNG:

- exact size: `128 x 224` pixels;
- grid: 4 columns x 7 rows;
- frame: `32 x 32` pixels;
- rows in order: `idle`, `walk`, `listen`, `think`, `talk`, `success`, `offline`;
- four frames per state from left to right;
- RGBA or indexed color with transparency; decoded pixel count and file size are enforced;
- no ancillary text/profile chunks are retained after server re-encoding;
- horizontal direction MAY be rendered by flipping frames; the sheet contains one facing direction.

Built-in characters are composed into the same canonical sheet, so frontend state logic is identical. Animation timing is configuration-bounded from 80–1000 ms. Reduced motion uses the first frame of each state with no movement/transitions.

### 12.2 README card

- canonical view box/output size: `600 x 180` CSS pixels;
- first frame includes character, display name, headline, call to action, and visible RepoNPC identity;
- SVG animation uses allowlisted CSS only and remains understandable when animation is stripped;
- GIF is generated from the canonical frames at build time and loops at a bounded rate;
- PNG is the exact static first-frame rendering;
- user text is length-bounded and XML-escaped; remote fonts/images are forbidden;
- card links are provided by Markdown around the image, never embedded executable behavior.

## 13. Provider interfaces

### 13.1 Chat provider

Every adapter exposes:

```text
capabilities() -> {
  streaming, system_role, structured_output, usage_reporting,
  health_check, max_context_tokens, max_output_tokens
}
generate(messages, response_schema, max_output_tokens, timeout) -> ProviderResult
health() -> ProviderHealth
```

`ProviderResult` contains raw structured/text content, finish reason, nullable usage, provider request ID, and timing. Provider exceptions map to stable internal categories: authentication, rate limit, timeout, unavailable, invalid response, and context overflow.

### 13.2 Embedding provider

```text
identity() -> {adapter, model_id, dimension, normalized, query_prefix, passage_prefix}
embed_query(texts) -> float32 matrices
embed_passages(texts) -> float32 matrices
health() -> ProviderHealth
```

The application validates output shape, finite values, and normalization. Indexing batches may retry transient failures with bounded exponential backoff; runtime queries default to at most two transient attempts within the overall timeout.

### 13.3 Required adapters and fallback rule

- `openai_compatible`: configurable base URL, key secret, chat model, embedding model, timeout, and optional headers from server-only secrets.
- `ollama`: private base URL, chat model, embedding model, explicit context/output caps, and health endpoint.
- A local sentence-transformers embedding adapter MUST be shipped to implement the default embedding contract without an external API.

The selected chat and embedding adapters are explicit. RepoNPC MUST NOT silently try another provider, model, or cloud endpoint after failure.

## 14. Bundle publication and activation

### 14.1 Immutable bundle layout

Release asset name: `reponpc-index-{bundle_id}.tar.zst`.

```text
manifest.json
checksums.sha256
index.sqlite
public/profile.json
public/character.png
public/card-light-zh-TW.svg
public/card-dark-zh-TW.svg
public/card-light-en.svg
public/card-dark-en.svg
public/card-*.gif
public/card-*.png
```

Archives MUST contain only regular files at normalized relative paths, no symlinks/hardlinks/devices, and no path traversal. Unknown required files or duplicate paths fail validation.

### 14.2 Internal manifest

`manifest.json` canonical JSON fields:

```json
{
  "manifest_schema_version": 1,
  "index_schema_version": 1,
  "bundle_id": "20260810T120000Z-0123456789ab",
  "built_at": "2026-08-10T12:00:00Z",
  "application_compatibility": {"minimum": "1.0.0", "maximum_exclusive": "2.0.0"},
  "config": {"repository": "owner/profile", "commit_sha": "40hex", "path": "reponpc.yml", "sha256": "64hex"},
  "repositories": [{"slug": "owner/repo", "commit_sha": "40hex"}],
  "embedding": {"adapter": "local_sentence_transformers", "model_id": "intfloat/multilingual-e5-small", "dimension": 384, "normalized": true, "query_prefix": "query: ", "passage_prefix": "passage: "},
  "statistics": {"repositories": 1, "sources": 100, "evidence_records": 500},
  "files": [{"path": "index.sqlite", "size": 123, "sha256": "64hex"}]
}
```

`bundle_id` is UTC build timestamp plus the first 12 hex characters of a deterministic hash over schema, normalized configuration, source commits, parser/chunker version, and embedding identity. Rebuilding identical inputs retains the hash suffix; timestamps are declared non-deterministic metadata.

### 14.3 Stable manifest

The `reponpc-index` branch contains `stable-manifest.json`:

```json
{
  "stable_manifest_schema_version": 1,
  "bundle_id": "...",
  "release_tag": "index-...",
  "asset_url": "https://github.com/owner/repo/releases/download/.../...tar.zst",
  "asset_size": 123,
  "asset_sha256": "64hex",
  "published_at": "2026-08-10T12:01:00Z"
}
```

The Action uploads the immutable asset, verifies its availability, then updates this document in the final publication step. The URL host/repository must match configured allowlists.

### 14.4 Runtime activation

1. On startup and every 300 seconds by default, fetch stable manifest with `If-None-Match`.
2. If the bundle is already active, update check time only.
3. Download to a unique staging directory with byte/time limits while hashing.
4. Verify outer SHA-256, safe archive structure, all internal checksums, manifest schema/application compatibility, embedding compatibility, required files, and SQLite `PRAGMA quick_check`.
5. Open the candidate database read-only and run a retrieval/card smoke check.
6. Atomically replace an `active` pointer/file only after all checks pass.
7. Keep the current and previous validated bundles; clean older bundles only after the new bundle serves successfully.
8. On failure, delete/quarantine only the candidate, retain current active state, record a safe diagnostic, and retry with bounded backoff.

An admin MAY pin a previously downloaded compatible bundle by ID. Automatic polling then reports a newer version but does not activate it until unpinned.

## 15. Runtime storage, security, and operations

### 15.1 Mutable runtime database

`REPONPC_DATA_DIR/runtime.sqlite` is separate from bundles and contains logical tables:

- `admin_sessions`: token hash, CSRF hash, created/seen/idle/absolute expiry, session epoch, revoked time;
- `rate_buckets`: HMAC-derived IP key, window/bucket counters and expiry;
- `daily_usage`: UTC date, accepted requests, reported input/output tokens and estimated cost where configured;
- `bundle_state`: active/previous/pinned IDs, ETags, checks and safe update error;
- `admin_audit`: timestamp, action, target path, result commit, request ID, outcome.

Raw session/CSRF tokens and raw IPs are never stored. IP keys use HMAC-SHA-256 with `REPONPC_IP_HASH_KEY`. Expired rows are periodically removed.

### 15.2 Default public controls

- per-IP token bucket: capacity 10, refill 10 requests/minute;
- global concurrent model generations: 2;
- global accepted chat requests per UTC day: 200;
- public request timeout: 45 seconds;
- provider connect/read timeouts are bounded inside that deadline;
- response and history limits follow section 4.3.

Rate and budget checks occur before retrieval/provider work. Operators can lower or raise defaults within documented hard limits through environment variables.

### 15.3 Safe logging

Structured logs contain timestamp, severity, event name, request ID, route template, status, latency, index version, provider adapter/model alias, retrieval counts/ranks, token usage, rate outcome, and sanitized error category. They exclude credentials, cookies, CSRF values, raw IPs, full questions, history, prompts, evidence bodies, full answers, uploaded files, and stack traces in public responses.

`docs/SECURITY.md` MUST document the threat model, trust boundaries, secret handling, injection defenses, SSRF/redirect controls, HTML/Markdown/SVG escaping, admin controls, dependency/secret scanning, disclosure process, and operator checklist.

`docs/OPERATIONS.md` MUST document prerequisites, password/token creation, GitHub Action permissions, installation, HTTPS/reverse proxy, backup, update, pin/rollback, logs/health, provider setup, cost limits, key rotation, upgrade compatibility, and disaster recovery.

## 16. Frontend behavior

- The visitor route defaults to `/`; admin routes are below `/admin` and are not advertised publicly.
- The UI renders profile and chat as semantic DOM. Canvas MAY render decorative scene elements but MUST NOT contain the only accessible content.
- Character states map to lifecycle: idle before input, listen while input is active, think during retrieval/provider wait, talk while validated tokens render, success on completion, offline on unavailable/error.
- Suggested questions are keyboard-operable buttons and remain editable before submission.
- Citation markers focus/scroll to a citation panel and links open immutable GitHub pages with safe `rel` attributes.
- Locale switching changes UI/profile fields and sends the selected locale with chat. It does not discard the visible conversation.
- Offline/setup/model unavailable states explain what visitors can still view and do not expose admin diagnostics.
- The admin UI is code-split from the visitor application and clears in-memory CSRF/config drafts on logout.
- `docs/SPRITE_FORMAT.md` MUST provide the exact grid diagram, state table, frame timing guidance, examples, validation errors, reduced-motion behavior, and an MIT-compatible template asset.

## 17. Edge cases and required behavior

| Condition | Required behavior |
| --- | --- |
| No active bundle on first boot | Public setup state; profile/chat `503 INDEX_UNAVAILABLE`; health alive, readiness false. |
| Active index but chat model down | Profile/card remain available; status degraded; chat `503 MODEL_UNAVAILABLE`; no provider fallback. |
| Embedding query service down | Exact/lexical-only fallback is allowed only if explicitly enabled and visibly reported; default is chat unavailable to preserve retrieval contract. |
| Repository renamed/deleted/private | Index build fails that configured repository; stable manifest is not advanced. Existing bundle remains valid. |
| Empty repository/no eligible text | Build emits a warning; repository metadata/owner assertions may remain; zero total evidence fails publication. |
| Invalid custom sprite | Admin/build returns row/dimension/format errors; previous asset/bundle remains. |
| GitHub write conflict | Return `409 CONFIG_CONFLICT` with current blob SHA; never overwrite or auto-merge. |
| Unknown model source ID | Discard output and use a safe abstention or one bounded repair; never publish invented citation. |
| Provider stops mid-generation | Terminal SSE error; no partial unvalidated answer is sent because public output is buffered. |
| Daily budget exhausted | Reject before model call with localized `429`; profile/card remain usable. |
| Malicious repository prompt | It remains delimited evidence; no tool/network capability; evaluation security case must pass. |
| File lines changed after indexing | Citation still points to recorded commit SHA and remains stable. |
| Browser blocks SVG animation | Static first frame remains complete; generated snippet can use GIF/PNG. |
| Concurrent bundle read/activation | In-flight requests retain their opened bundle handle; new requests use new active bundle. |
| Locale field missing | Required localized field fails configuration validation; optional field follows configured fallback policy. |

## 18. Explicit v1 exclusions

Private repositories, multi-owner/multi-tenant operation, billing, visitor authentication, GitHub OAuth onboarding, model fine-tuning, autonomous tools, live repository mutation by the model, arbitrary URL ingestion, multiple NPCs, navigable worlds, keyboard gameplay, mobile-native apps, externally hosted frontend origins by default, distributed replicas, and a separate vector/database service are outside v1.

## 19. Implementation and release gates

Work follows `IMPLEMENTATION_PLAN.md`, but a milestone is complete only when its mapped acceptance criteria pass. Before v1 release:

- every FR and NFR has at least one automated or documented acceptance result;
- retrieval and bilingual evaluation thresholds pass on a committed, non-secret fixture corpus;
- security tests cover all named trust boundaries;
- current Chrome, Firefox, and Safari plus a real GitHub Profile render are manually verified where automation is insufficient;
- Compose installation succeeds from clean documented prerequisites;
- operations, security, sprite, upgrade, and rollback documentation is complete;
- the owner approves any change to this specification and all ADR statuses are consistent.

## 20. Owner approval record

To approve, the project owner should explicitly state that RepoNPC v1 Technical Specification version `0.1.0` is approved. The approving change must update:

- this document's status to `Approved` and record approval date;
- all `Proposed` ADRs adopted by the approval to `Accepted`;
- any owner-requested exceptions before application implementation starts.

**Approved by:** project owner  
**Approved on:** 2026-08-10  
**Approval scope:** Technical Specification 0.1.0 and OR-001 through OR-007. The owner requested an MVP delivery phase; this is a sequencing decision and does not reduce the complete v1 scope.

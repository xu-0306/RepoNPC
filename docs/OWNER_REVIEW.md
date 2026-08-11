# RepoNPC v1 Owner Review Checklist

**Status:** Closed — approved by the project owner on 2026-08-10  
**Purpose:** isolate the new high-impact defaults introduced while turning the agreed product plan into an implementation-complete contract.

**Decision record:** The project owner approved Technical Specification 0.1.0 and OR-001 through OR-007 in the 2026-08-10 implementation conversation. The requested MVP is an initial delivery phase of the complete v1; it does not remove, postpone, or weaken any v1 requirement.

## 1. Already established and not being re-opened

Unless the owner says otherwise, the following earlier product decisions remain fixed:

- project name `RepoNPC` and tagline “Meet the NPC who knows your code.”;
- complete v1 delivery rather than a reduced MVP;
- open-source MIT, self-hosted, single owner;
- owner-selected public GitHub repositories only;
- script-free README card linking to an external interactive RPG chat page;
- React/Vite/TypeScript frontend and FastAPI/Python backend;
- SQLite FTS5 + multilingual vector retrieval + RRF;
- Tree-sitter support for Python, JavaScript/TypeScript, Go, and Rust;
- OpenAI-compatible and private/internal Ollama model support;
- Traditional Chinese and English;
- admin UI, GitHub writeback, character builder, and custom sprites in v1;
- GitHub Actions immutable index bundles, SVG static-safe first frame, and GIF fallback;
- the three evidence classes and backend-owned immutable citations;
- repository content is untrusted and the LLM has no tools/code execution.

## 2. New decisions requiring confirmation

### OR-001 — Default embedding profile

**Proposal:** Ship `local_sentence_transformers` with `intfloat/multilingual-e5-small`, 384-dimensional normalized vectors, `query: ` / `passage: ` prefixes. Keep OpenAI-compatible/Ollama embeddings configurable, but require an exact manifest/runtime match.

**Why proposed:** It gives a compact no-API default for Chinese/English semantic retrieval while lexical search covers exact code terms. The committed evaluation target decides whether it is good enough.

**Impact if changed:** Model download size, memory, index dimensions, build/runtime provider configuration, and retrieval benchmarks.

**Owner response:** Approved on 2026-08-10.

### OR-002 — Canonical sprite-sheet dimensions

**Proposal:** One transparent `128x224` PNG: four `32x32` frames across seven rows (`idle`, `walk`, `listen`, `think`, `talk`, `success`, `offline`). Built-in and custom characters share the same output.

**Why proposed:** It is large enough for a recognizable pixel character but small and deterministic enough for validation, animation, README card generation, and community templates.

**Impact if changed:** Character assets, builder/composer, upload validation, animation controller, GIF/SVG rendering, and documentation.

**Owner response:** Approved on 2026-08-10.

### OR-003 — Validate before streaming

**Proposal:** Buffer the complete model response, validate citations/person claims/sanitization, then send the approved answer as SSE token chunks. The UI shows `think` while the provider generates and `talk` while validated chunks render.

**Why proposed:** Pass-through token streaming could expose a fabricated citation or unsupported personal claim before the server can validate and cannot retract it.

**Impact if changed:** Time-to-first-visible-token versus trust guarantees and response architecture.

**Owner response:** Approved on 2026-08-10.

### OR-004 — Single-admin credential and writeback model

**Proposal:** One configured username plus Argon2id password hash; server-side rotating secure-cookie sessions with CSRF; a server-only fine-grained GitHub token; exact write allowlist `reponpc.yml` and `assets/character/*.png`; stale blob SHA returns conflict with no auto-merge.

**Why proposed:** It avoids GitHub OAuth/multi-user complexity while retaining revocation, conflict safety, and least privilege.

**Impact if changed:** Admin onboarding, secret management, API/session design, GitHub permissions, and security tests.

**Owner response:** Approved on 2026-08-10.

### OR-005 — Bundle publication/discovery

**Proposal:** GitHub Actions uploads immutable `tar.zst` assets to GitHub Releases; a small `stable-manifest.json` on a dedicated `reponpc-index` branch is updated last and fetched with ETag. Runtime retains active and previous bundles and supports pin/unpin.

**Why proposed:** Releases provide immutable large artifacts while a branch supplies one stable discovery URL without overwriting bundle contents.

**Impact if changed:** Action permissions, hosting cost, updater, cache behavior, backup, and rollback.

**Owner response:** Approved on 2026-08-10.

### OR-006 — Default public capacity limits

**Proposal:** 2,000-character question, six history messages/6,000 history characters, 1,000 output tokens, 45-second timeout, 10 chats/minute/IP, two global concurrent generations, and 200 accepted chats per UTC day. Operators may adjust within hard limits.

**Why proposed:** Safe initial settings for a publicly exposed personal portfolio; they bound abuse and provider cost while remaining configurable.

**Impact if changed:** UX, cost, rate-limit storage, load tests, and operator documentation.

**Owner response:** Approved on 2026-08-10.

### OR-007 — Reference performance and quality gates

**Proposal:** On a documented 4-core/8-GB reference host and corpus up to 50,000 chunks: retrieval p95 <=750 ms, Recall@8 >=85%, citation resolution >=95%, factual entailment >=90%, unsupported abstention >=90%, and paired-language evidence parity >=90%.

**Why proposed:** A complete product needs measurable release gates; these are ambitious but realistic starting targets and may be revised with benchmark evidence before approval.

**Impact if changed:** Release gate, model selection, tuning effort, and hardware guidance.

**Owner response:** Approved on 2026-08-10.

## 3. How to respond

The owner may reply either:

- “OR-001 到 OR-007 全部同意，批准 Technical Specification 0.1.0”；or
- list only the OR IDs to change and the preferred direction.

Approval was recorded on 2026-08-10. Technical Specification 0.1.0 and the adopted ADRs were updated before application implementation began.

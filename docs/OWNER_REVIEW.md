# RepoNPC v1 Owner Review Checklist

**Status:** OR-001 through OR-013 closed; ENGD-001, ENGD-002, ENGD-003, and ENGD-006 approved/closed; UXD-001 through UXD-007 plus ENGD-004, ENGD-005, and ENGD-007 remain open
**Purpose:** record owner decisions that close the high-impact embedding, authentication, recovery, and operations contradictions found during specification review.

**Decision record:** The project owner approved Technical Specification 0.1.0 and OR-001 through OR-007 in the 2026-08-10 implementation conversation. OR-008, OR-009, and OR-010 were approved on 2026-08-14. OR-011 was approved by the owner's explicit vLLM/Ollama/OpenAI-compatible implementation request on 2026-08-15. OR-013 was approved by the owner's 2026-08-30 request to make unconfigured GitHub OAuth entry points actionable with a safe host-side setup guide. ENGD-001, ENGD-002, ENGD-003, and ENGD-006 were approved by the owner's follow-up decisions on 2026-08-30 and are recorded below. The requested MVP is an initial delivery phase of the complete v1; it does not remove, postpone, or weaken any v1 requirement.

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
- generic OpenAI-compatible plus private/internal vLLM and Ollama model support;
- Traditional Chinese and English;
- admin UI, GitHub writeback, character builder, and custom sprites in v1;
- GitHub Actions immutable index bundles, SVG static-safe first frame, and GIF fallback;
- the three evidence classes and backend-owned immutable citations;
- repository content is untrusted and the LLM has no tools/code execution.

## 2. New decisions requiring confirmation

### OR-001 — Default embedding profile (superseded)

**Status:** Superseded by ENGD-001 / ADR-023 on 2026-08-30.

**Proposal:** Ship `local_sentence_transformers` with `intfloat/multilingual-e5-small`, 384-dimensional normalized vectors, `query: ` / `passage: ` prefixes. Keep OpenAI-compatible/Ollama embeddings configurable, but require an exact manifest/runtime match.

**Why proposed:** It gives a compact no-API default for Chinese/English semantic retrieval while lexical search covers exact code terms. The committed evaluation target decides whether it is good enough.

**Impact if changed:** Model download size, memory, index dimensions, build/runtime provider configuration, and retrieval benchmarks.

**Owner response:** Historical approval on 2026-08-10; the local default is no longer normative.

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

### OR-008 — First-owner onboarding without product default credentials

**Proposal:** A new deployment has no product username or password. The host operator runs `reponpc admin setup-code` to create a 256-bit, 15-minute, one-time code whose SHA-256 digest is stored in runtime SQLite. `/admin` accepts that code with a chosen username and password, stores only an Argon2id hash, creates a session atomically, and permanently closes setup once the owner exists. The prior environment username/hash mode remains an optional pre-provisioned compatibility mode. GitHub credentials are not required to create or use an admin session; they gate only GitHub-backed operations.

**Why proposed:** A self-hosted owner must be able to obtain credentials without a hidden/default account or manually producing a password hash before the configuration UI can be reached. Host-issued proof prevents the first remote visitor from claiming the deployment.

**Impact if changed:** Admin onboarding, runtime schema, CLI, authentication API/UI, deployment examples, backup requirements, and security tests.

**Owner response:** Approved on 2026-08-14.

### OR-009 — Personal local-deployment convenience defaults (partially superseded)

**Status:** The loopback launcher/port portion remains accepted; the four-character rule for production is superseded by ENGD-002 / ADR-024.

**Proposal:** First-owner passwords use a 4-character minimum with no uppercase, lowercase, number, symbol, or mixed-character rule. Existing setup-code proof, Argon2id hashing, backoff, and session controls remain. The Windows one-click launcher defaults to loopback port 8090, while explicit `.env`/`-Port` overrides and the production container port remain unchanged.

**Why proposed:** RepoNPC is normally operated by one owner on their own computer. The previous 12-character minimum and common local development port created unnecessary onboarding friction for that threat model.

**Impact if changed:** Admin setup UI/API/service validation, security tests, launcher contract/tests, local documentation, and examples.

**Owner response:** Approved on 2026-08-14 for loopback evaluation only; production password scope was revised on 2026-08-30.

### OR-010 — Guided repository onboarding and explicit analysis

**Status:** Approved on 2026-08-14; implementation authorized.

**Proposal:** Adopt all of the following as one compatible 0.1.4 amendment:

1. Guided onboarding becomes the default authenticated post-login experience; raw `reponpc.yml` remains available as an advanced mode.
2. Repository discovery uses read-only, unauthenticated public GitHub metadata without OAuth. The default is a checkbox picker after entering a username/profile URL; manual `owner/name` or `https://github.com/owner/name` entry remains available.
3. Metadata discovery never downloads source or calls a model. Under the original 0.1.4 route, source analysis began only after explicit confirmation and accepted one confirmed public repository per request.
4. **Historical 0.1.4 lifecycle, superseded by ADR-021:** analysis was synchronous and ephemeral, with one active request per admin session, a 120-second overall request limit, the existing 45-second provider sub-limit, existing repository/file/text/chunk/context caps, no automatic retry, no partial durable result, and unconditional temporary-file cleanup after success, failure, cancellation, or disconnect. The provider/no-fallback and resource-boundary portions remain in force; the current execution lifecycle is the durable batch plus one-item compatibility adapter.
5. Repository facts and model inferences remain distinct. Model-generated personal-role/result text is an unconfirmed proposal and becomes `OWNER_ASSERTION` only after explicit owner acceptance/editing.
6. The schema remains version 1: localized repository `role` and `summary` stay required and, once confirmed into configuration, retain the current `OWNER_ASSERTION` semantics. This avoids a migration while keeping the confirmation boundary visible.
7. Without a GitHub writeback token, an authenticated owner may copy or download the generated YAML. These local operations make no GitHub mutation and do not dispatch publication.

**Additional contract details:** Discovery returns at most 50 repositories per page and at most five pages per owner request sequence. Public metadata requests do not use or broaden the configured fine-grained writeback token. Unsaved selection, owner-entered public statements, and confirmed suggestions may use browser `sessionStorage` for same-tab/session resume but must be cleared on logout or successful save; raw repository bodies, raw provider prompts/outputs, credentials, CSRF/session tokens, and private provider URLs must never be stored there.

**Why proposed:** A new owner should understand the product and select what to present without writing a schema by hand. RepoNPC should perform repository understanding while the owner supplies and confirms personal attribution that source code cannot prove.

**Impact if approved:** New authenticated read-only discovery/resolve endpoints, explicit provider-consuming analysis and contribution-suggestion endpoints, an in-memory YAML draft endpoint, a guided frontend state machine, public GitHub rate-limit handling, temporary-data cleanup, new acceptance/security tests, and updated operations guidance. No new dependency, OAuth flow, private-repository support, database migration, environment variable, or token permission is introduced.

**Owner response:** Approved on 2026-08-14. The owner's explicit instruction to proceed with implementation records approval of OR-010 and Technical Specification 0.1.4.

**Historical lifecycle note:** OR-010's one-repository synchronous/ephemeral execution design was superseded by the owner-approved ADR-021 durable batch lifecycle. OR-010 remains authoritative for explicit selection, optional/manual continuation, owner-confirmed personal claims, local export, and the no-fallback/privacy boundaries.

### OR-011 — Name vLLM without adding another wire protocol

**Status:** Approved on 2026-08-15; implementation authorized.

**Proposal:** Accept `vllm` as a server-side chat and embedding provider preset. It uses the existing OpenAI-compatible `/v1/models`, `/v1/chat/completions`, and `/v1/embeddings` transports, permits an explicitly configured private HTTP origin, and normalizes embedding compatibility plus the existing public status provider value to `openai_compatible`. Chat and embedding retain separate server-only URL/model/key settings. Health must verify that each selected model appears in that server's model catalog. No raw key or private URL enters public configuration, browser requests, API responses, logs, fixtures, or snapshots.

**Why proposed:** vLLM exposes an OpenAI-compatible server rather than a distinct RepoNPC protocol, but self-hosted operators need a clear, private-network-safe deployment choice. A named preset avoids duplicating adapters while keeping origin policy and operations guidance explicit.

**Impact:** Environment validation, provider assembly, model preflight, examples, provider tests, and operations/security documentation. Bundle schema version 1, browser contracts, public provider enum, secret storage, fallback policy, and hosted dependencies do not change.

**Owner response:** Approved on 2026-08-15 by the explicit request to implement vLLM, Ollama, and generic OpenAI-compatible API support.

### OR-012 — GitHub identity, encrypted public-read credentials, and dual sign-in (partially superseded)

**Status:** OAuth identity, encryption, public-read purpose, and dual sign-in remain accepted. The GitHub-only first-owner and host-recovery prerequisite are superseded by ENGD-003 / ADR-025.

**Decision:** Keep local password sign-in and add GitHub OAuth Web Application Flow with PKCE as an alternative for the same sole owner. The host-issued setup proof is followed by local username/password creation; GitHub is linked only from that authenticated local owner session. OAuth identities are linked by immutable GitHub numeric user ID; OAuth requests no repository scope and may serve only public read. An explicitly entered fine-grained PAT is a public-read connection fallback, never a sign-in method. OAuth/PAT credential records use a dedicated encryption key and writeback keeps its independent credential/purpose. The local password remains the break-glass method and unlinking cannot remove it. GitHub-only first-owner setup is not supported. Milestones A–C are authorized; GraphQL/archive optimization and durable batch analysis remain later milestones.

**Owner response:** Approved by the owner's explicit 2026-08-16 instruction to implement Milestones A–C with complete OAuth Web Flow plus PKCE, migration, bilingual UI, security, and accessibility tests.

### OR-013 — Actionable GitHub OAuth setup guidance

**Status:** Approved on 2026-08-30; implementation authorized.

**Decision:** When GitHub OAuth is not configured, setup, sign-in, link, and reauthentication buttons remain operable and open a bilingual host-side setup guide dialog instead of redirecting or accepting secrets. The guide shows the backend-provided canonical callback URL, links the official GitHub OAuth-App documentation, explains host-secret configuration plus restart/recheck, and warns against pasting secrets, keys, or tokens into the browser. Configured OAuth keeps the existing top-level Authorization Code Flow with PKCE S256 and intent separation. The public setup-guide API returns only non-sensitive guidance data and uses `Cache-Control: no-store`.

**Owner response:** Approved by the owner's explicit 2026-08-30 request to modify the specification and implement the UX correction.

## 2. Approved engineering decisions (2026-08-30)

### ENGD-001 — External embedding profiles and provider-aware model management

**Status:** Approved on 2026-08-30; implementation authorized.

**Decision:** RepoNPC MUST NOT require or default to an in-process/local embedding runtime. A deployment MUST connect at least one external embedding interface: `ollama`, `vllm`, or `openai_compatible` (including another service that implements the same embeddings contract). Chat and embedding profiles are independent. The authenticated Web Admin MUST provide profile create/read/update/delete operations, connection/model capability probing, and an explicit active-profile switch; at most one profile may be active, and readiness requires one valid active profile whose identity matches the index bundle. A profile change is pending until reindexing and bundle validation complete; the last-known-good bundle remains active on failure.

Ollama receives provider-native model management in the Web Admin (curated catalog, installed-model list, pull, and delete). vLLM and generic OpenAI-compatible services expose connect/list/probe/select only; model installation remains on the provider host. RepoNPC MUST NOT offer an arbitrary URL or local-path downloader. Catalog entries are recommendations, not a hidden fallback, and licenses/capabilities must be shown before use.

The recommended first catalog entry for a Traditional-Chinese/English personal deployment is Ollama `qwen3-embedding:0.6b`; `BAAI/bge-m3` and `embeddinggemma:300m` are optional alternatives, while larger Qwen3-Embedding variants are for hosts with more memory. The actual returned dimension, normalization, prefixes, and model identity are probed and recorded rather than assumed from a label.

**Impact:** Adds a deployment-local embedding-profile registry, provider-specific model-center UI, probe/reindex state, bundle identity checks, and safe cleanup/error states. It removes the local sentence-transformers runtime from the supported production default; index builders must receive an explicit frozen external profile snapshot.

**Owner response:** Approved by the owner's instruction that at least one Ollama/vLLM/API embedding interface be connected, profiles support CRUD, and only one model be active at a time.

### ENGD-002 — Deployment-aware password policy and private administration

**Status:** Approved on 2026-08-30; implementation authorized.

**Decision:** The four-character convenience is allowed only in an explicitly configured loopback evaluation profile. Any production or non-loopback admin surface requires at least 15 Unicode code points (15 is a minimum, not a maximum) and accepts passphrases up to 128 code points; no upper/lowercase/number/symbol composition rule is imposed. New passwords are checked against a common/compromised-password blocklist. Argon2id, backoff, secure sessions, CSRF, origin checks, and revocation remain mandatory. Existing hashes remain usable during migration; a password change applies the policy for the selected deployment profile.

The admin surface MUST NOT be made safe by choosing an unusual port. The supported headless path is loopback binding plus an SSH local-port tunnel; persistent remote access uses a private LAN/VPN (for example Tailscale/WireGuard) with firewall allowlisting. A reverse proxy may publish visitor routes while denying `/admin` and `/api/admin` from the public Internet. A public `0.0.0.0` admin listener is not a supported default.

**Impact:** Adds an explicit deployment-profile policy, private-admin topology guidance, password blocklist tests, and SSH/VPN/reverse-proxy acceptance evidence.

**Owner response:** Approved by the owner's acceptance of the layered policy and preference for SSH/private access rather than an Internet-exposed admin port.

### ENGD-003 — Local-first owner setup with optional GitHub binding

**Status:** Approved on 2026-08-30; implementation authorized.

**Decision:** First-owner setup always creates a local username/password after the host-issued setup code. GitHub OAuth is an optional alternative sign-in and public-read connection that can be linked only from an authenticated local owner session. The local password MUST remain usable as break-glass recovery and the last local method cannot be disabled or unlinked. A GitHub-only owner is not supported in v1, so recovery readiness is a product-owned capability (`reponpc admin set-password --data-dir <dir>`) rather than a non-empty environment command string. Recovery changes only the local password, never reopens setup, changes GitHub identity, or exposes secrets.

**Impact:** Supersedes the GitHub-only portion of ADR-020, removes `REPONPC_GITHUB_OWNER_RECOVERY_COMMAND` as a readiness switch, adds local-recovery/backup tests, and clarifies the first-login/linking UX.

**Owner response:** Approved by the owner's instruction to set account/password on first login and then allow GitHub binding.

### ENGD-006 — Web Admin plus bounded operations CLI

**Status:** Approved on 2026-08-30; implementation authorized.

**Decision:** Web Admin is the normal daily configuration surface, including embedding profile CRUD, provider probes, and connection status. The CLI is intentionally small and host-oriented: bootstrap/recovery (`admin setup-code`, `admin set-password`), health/backup (`runtime check`, `runtime backup <path>`), and bundle lifecycle (`bundle status`, `verify <id>`, `pin <id>`, `unpin`). Linux/headless operators reach the same Web Admin through an SSH tunnel; RepoNPC does not add a second public management protocol or a public setup port. Every command must have stable help/error output, explicit paths/IDs, and tests for failure, restore, and last-known-good behavior.

**Impact:** Adds the remaining `runtime` and `bundle` command groups and clean-host recovery evidence without duplicating the complete admin UI in a CLI.

**Owner response:** Approved by the owner's instruction to follow the bounded Web Admin/CLI split.

## 2.1 Open decisions from the 2026-08-30 UX/complexity audit

The owner clarified that predesigned specifications are hypotheses and must be corrected when actual use shows an unreasonable workflow. The compatible no-dead-end corrections are recorded in FR-025/FR-027/FR-028/NFR-003 and AC-019/AC-025/AC-032/AC-040: optional analysis has an immediate manual path, guided navigation is reversible with selective invalidation, and unavailable integrations cannot disable unrelated local work without a reason/recovery/alternative.

The audit also identified higher-impact choices that are **not approved or changed yet** because they affect security, API/state, persistence, schema/validation, asset compatibility, or hosting topology. `docs/UX_SPEC_REVIEW.md` records the evidence, alternatives, and recommendations for UXD-001 through UXD-007: anonymous small-batch public analysis, batch/scheduler simplification, optional local publication transport, primary-locale preview gating, password recovery/durable drafts, returning-owner guided editing, and the unused `walk` asset state. The owner may approve/change these independently by ID.

The full-stack audit adds the following independent decisions. ENGD-001, ENGD-002, ENGD-003, and ENGD-006 are now closed above; only the remaining items below require a later owner decision. Their evidence, exit gates, and sequencing are in `docs/SPEC_AND_ENGINEERING_REMEDIATION_PLAN.md`.

| ID | Decision required | Recommendation | Contract/implementation impact |
| --- | --- | --- | --- |
| ENGD-004 | For `profile.greeting`, `avatar_url`, character animation timing/movement, and `walk`, should v1 wire each field to a visible consumer or remove/deprecate it? | Do not require configuration that has no observable effect. Wire only fields with a committed user outcome; deprecate the rest through a compatible schema plan. | Public config/profile/bundle, CSP, visitor/admin UI, sprite compatibility, examples. |
| ENGD-005 | Should release evidence move to one machine-readable acceptance ledger? | Yes; make one AC/FR ledger authoritative for current evidence and have narrative documents link to it instead of copying pass totals. | Release governance and documentation; no runtime behavior change. |
| ENGD-007 | What capacity baseline governs scheduler/cache complexity and release SLOs? | Record deployment cadence, year-one p50/p99 traffic, monthly cloud/SaaS ceiling, and availability target before adding or deleting scheduler/cache behavior. | Performance plan, capacity tests, possible FR-033 simplification; no silent API change. |

## 3. How to respond

OR-010 was approved on 2026-08-14, OR-011 on 2026-08-15, OR-013 and ENGD-001/002/003/006 on 2026-08-30. Any later incompatible change requires an explicit owner decision and matching updates to the normative specification, acceptance criteria, and relevant ADR.

For the historical closed decisions, the owner may reply either:

- “OR-001 到 OR-007 全部同意，批准 Technical Specification 0.1.0”；or
- list only the OR IDs to change and the preferred direction.

Approval was recorded on 2026-08-10. Technical Specification 0.1.0 and the adopted ADRs were updated before application implementation began.

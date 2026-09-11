# RepoNPC v1 Technical Specification

| Field | Value |
| --- | --- |
| Status | **Approved** |
| Version | 0.2.3 |
| Product | RepoNPC v1 |
| Audience | Implementation Agents, reviewers, maintainers |
| Last updated | 2026-09-10 |
| Approval date | 2026-08-10; Phase 2 closure amendment approved 2026-08-11; first-owner onboarding, personal-deployment convenience, and guided-onboarding amendments approved 2026-08-14; vLLM provider-preset amendment approved 2026-08-15; GitHub identity and connection amendment approved 2026-08-16; OAuth setup-guidance UX and ENGD-001/002/003/006 amendments approved 2026-08-30; passwordless loopback launch and connection-only GitHub amendment approved 2026-09-04; GitHub OAuth/public-read PAT retirement approved 2026-09-08; provider-neutral setup approved 2026-09-09; model-first guided workflow approved 2026-09-10 |

Application implementation is authorized under this approved specification. The words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY, and OPTIONAL are normative as described by RFC 2119.

**0.2.3 approval:** On 2026-09-10 the owner approved the reviewed six-step model-first AI journey, an immediate manual route, and separate analysis-model readiness from published-index activation (ENGD-011 / ADR-030). This work package updates documents only. Existing 0.2.2 connection/profile implementation is present, but guided integration and clean-bootstrap lifecycle gaps remain; see `ONBOARDING_FLOW_IMPLEMENTATION_HANDOFF.md`. Figma and RepoNPC-managed GGUF/Hugging Face execution remain outside scope.

**0.2.2 historical approval:** On 2026-09-09 the owner accepted the provider-neutral onboarding analysis and requested specification, memory, and implementation-handoff updates under ENGD-010 / ADR-029. That documentation delivery did not establish application acceptance. The 2026-09-10 source review supersedes its then-current “not implemented” inventory without claiming complete release verification.

Version 0.2.3 puts model setup before project analysis on the AI route, adds an explicit four-step manual route, and separates the model pair selected for owner analysis from the publicly active bundle/model state. It requires the clean no-model/no-bundle runtime to become analysis-capable after explicit model setup without restart, while keeping publication and public chat behind their stricter bundle lifecycle.

Version 0.2.2 adds independent chat/embedding setup through authenticated Web Admin: explicit service selection, API base URL, write-only API key, manually entered model ID, optional model discovery, and capability testing. There is no automatically selected provider/model on a clean deployment. Section 11.5 supersedes the environment-only/browser-input prohibition in older sections only for this protected model-connection form. Stored keys and private endpoints are still never returned to browsers, exported, logged, or sent directly from the browser to providers. ADR-029 also supersedes a mandatory model-list gate when a gateway does not support listing; actual capability testing remains required.

Version 0.1.1 records the owner-approved Phase 2 closure boundary as historical context: Phase 2 shipped a build-time local embedding adapter and executable index CLI, while concrete chat adapters and runtime query-provider integration remained Phase 3 work. The local adapter is retained only for isolated reproducibility fixtures; version 0.1.9 is normative for production embedding deployment and requires an external profile.

Version 0.1.2 records the owner-approved first-owner onboarding amendment. A new deployment has no product default credential: a host-issued, short-lived, one-time setup code authorizes creation of the sole durable owner through `/admin`. The environment username/Argon2id-hash mode remains available for explicit pre-provisioning, and GitHub credentials gate GitHub operations rather than admin authentication.

Version 0.1.3 records the owner-approved personal-deployment convenience amendment as historical context. The four-character convenience now applies only to the explicit loopback evaluation profile; version 0.1.9/ADR-024 is normative for production and non-loopback administration. The Windows one-click launcher still defaults to local port 8090 without changing the production container port contract.

Version 0.1.4 records the owner-approved guided-onboarding amendment. It adds guided public-repository discovery, explicit selected-only analysis, owner-confirmed contribution suggestions, advanced raw-YAML mode, and no-token YAML export without changing schema version 1, writeback permissions, or provider fallback behavior.

Version 0.1.5 records the owner-approved vLLM provider-preset amendment. `vllm` is a named server-side deployment preset over the existing OpenAI-compatible transport, not a third wire protocol or bundle adapter. It permits explicitly configured private HTTP origins, keeps chat and embedding server/model/key settings independent, validates selected-model availability, and does not expose keys/private URLs or add fallback behavior.

Version 0.1.6 records the owner-approved GitHub identity and public-read connection amendment. GitHub OAuth Web Application Flow with PKCE is an alternative authentication method for the same sole owner, never open registration or a visitor account system. The host-issued setup proof remains mandatory for first-owner creation. OAuth and explicit public-read PAT credentials are separately encrypted in mutable runtime state; writeback remains a separate least-privilege credential.

Version 0.1.7 records the owner's 2026-08-16 authorization for the bounded GitHub resolver and durable analysis-batch extension. It replaces per-blob guided analysis with server-owned GraphQL metadata plus immutable-commit archives, and replaces browser-driven serial work with one durable, bounded-parallel batch for the sole owner. It does not add private-repository support, another owner, a hosted dependency, model tools, or credential/provider fallback.

Version 0.1.8 records the owner's 2026-08-30 authorization for the GitHub OAuth setup-guidance UX amendment. GitHub entry points remain actionable when OAuth is not configured: they open a host-side setup guide instead of redirecting to GitHub. Configured OAuth continues to use the existing top-level Authorization Code Flow with PKCE S256. The guide endpoint exposes only a canonical callback URL, fixed GitHub documentation URL, configuration state, and a next-step label; it never exposes secrets, tokens, secret-file paths, or owner identity.

Version 0.1.9 records the owner's 2026-08-30 engineering decisions: production embeddings are external provider profiles with CRUD and one active profile; Ollama may manage models through provider-native pull/delete while vLLM and generic OpenAI-compatible services are connect/probe-only; administration uses an explicit loopback/production password policy and private access topology; first-owner setup is local-password-first with optional GitHub binding and local break-glass recovery; and daily Web Admin work is complemented by a bounded host operations CLI. Where the historical 0.1.1/0.1.3 paragraphs above describe a local production embedding default or an unrestricted four-character production password, this 0.1.9 amendment is normative.

Version 0.2.0 records the owner's 2026-09-04 correction after observing the implemented first-run flow. The `loopback_evaluation` launcher now uses a short-lived one-use local-launch capability and presents no registration, password-login, or GitHub-login screen. Production and every non-loopback administration path retain the setup-code, local password, and host recovery controls. GitHub OAuth is connection-only and begins from authenticated settings; it never creates or authenticates the RepoNPC owner. ADR-027 is normative where the historical 0.1.2/0.1.3/0.1.6/0.1.8/0.1.9 text describes loopback password setup, GitHub sign-in, or a public OAuth setup guide.

Version 0.2.1 records the owner's 2026-09-08 decision to retire GitHub OAuth and browser-entered public-read PATs entirely. Public discovery and selected-repository analysis move to bounded unauthenticated GitHub REST resolution followed by an archive addressed by a validated full commit SHA. Anonymous rate exhaustion is a recoverable capacity state and never blocks manual authoring/export. The independent least-privilege writeback credential remains server-only and MUST NOT be sent to discovery or analysis. ADR-028 is normative where historical 0.1.6 through 0.2.0 text requires OAuth, public-read PATs, GraphQL, connection UI, or public-read credential storage. The current OAuth/PAT implementation is legacy until the ordered removal plan is complete; it is not a release target.

The local Windows launcher is also required to reconcile its own runtime state at startup: when the recorded process is stale, it MUST verify the recorded PID and configured Python executable before stopping it, MAY fall back from process-tree termination to a direct stop of that same verified PID when Windows reports an elevation-context error, and MUST never terminate an unknown process occupying the port.

## 1. System boundary

RepoNPC is a single-owner, open-source, self-hosted application that:

1. builds a searchable evidence index from owner-selected public GitHub repositories and owner-authored configuration;
2. presents a bilingual pixel-RPG portfolio on an external web page;
3. answers visitor questions using a configured OpenAI-compatible (including vLLM) or Ollama model;
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
| FR-006 | The system MUST provide semantic retrieval with a configured external multilingual embedding profile whose identity and dimension are recorded in the bundle. |
| FR-007 | The retriever MUST fuse independently ranked lexical and vector candidates using Reciprocal Rank Fusion (RRF) and apply only documented metadata policies. |
| FR-008 | Every evidence record and answer claim MUST preserve the distinction between `OWNER_ASSERTION`, `REPOSITORY_FACT`, and `MODEL_INFERENCE`. |
| FR-009 | The chat service MUST answer only from retrieved evidence and MUST treat all repository/configuration text as delimited untrusted data. |
| FR-010 | The model MUST emit evidence IDs rather than URLs; the backend MUST validate them and construct immutable GitHub permalinks. |
| FR-011 | The service MUST abstain or qualify the response when available evidence is insufficient, especially for person-level claims without owner assertions. |
| FR-012 | The provider layer MUST support generic OpenAI-compatible chat/embedding APIs, the vLLM named OpenAI-compatible preset, and Ollama chat/embedding APIs through declared capability contracts. The local sentence-transformers adapter MAY remain only for isolated build/benchmark fixtures and MUST NOT be the production default or a runtime requirement. |
| FR-013 | The public chat API MUST deliver validated answers, citations, completion data, and failures using the SSE contract in this document. |
| FR-014 | The public site MUST show profile/project content, suggested questions, evidence-linked chat, index/model status, and responsive bilingual controls. |
| FR-015 | The character system MUST support built-in customization, the specified custom sprite-sheet format, required animation states, accessibility, and reduced motion. |
| FR-016 | The card service MUST provide sanitized, self-contained SVG, GIF fallback, and static preview outputs with light/dark and `zh-TW`/`en` variants. |
| FR-017 | The admin surface MUST use the single-admin session, CSRF, origin/host validation, expiration, rotation, and revocation controls defined here. `loopback_evaluation` MUST bootstrap that session only from a host-minted one-use local-launch grant and MUST expose no registration/password-login UI; production or any non-loopback administration MUST use the deployment-aware password, setup proof, and backoff controls. |
| FR-018 | The admin UI/API MUST read, validate, preview, and edit configuration and character assets without exposing secrets. |
| FR-019 | Admin writeback MUST use blob-SHA conflict detection and MUST modify only `reponpc.yml` or `assets/character/` in the configured repository. |
| FR-020 | GitHub Actions MUST validate sources, build a reproducible immutable bundle, publish it to a GitHub Release, and update the stable manifest last. |
| FR-021 | The runtime MUST poll, verify, atomically activate, retain, and roll back bundles according to this document. |
| FR-022 | All visitor/admin workflows and equivalent answers MUST support Traditional Chinese (`zh-TW`) and English (`en`). |
| FR-023 | The system MUST expose public status plus process/readiness health endpoints without revealing secrets or sensitive diagnostics. |
| FR-024 | The admin UI MUST generate ready-to-copy GitHub README snippets for SVG, GIF, light/dark, and locale selections. |
| FR-029 | RepoNPC MUST support exactly one owner through profile-specific local authentication: one-use launcher grants for `loopback_evaluation`, and host-issued setup proof plus local password sign-in/recovery for production or non-loopback administration. GitHub OAuth MUST NOT authenticate or register the owner. |
| FR-030 | **Legacy in 0.2.1; superseded by FR-037.** OAuth and browser-entered public-read PAT storage is not a release requirement. Writeback credential isolation remains normative under FR-019 and FR-037. |
| FR-031 | The admin UI MUST expose the access state appropriate to the deployment profile with bilingual, keyboard-accessible, no-secret behavior. It MUST NOT expose GitHub OAuth setup/connection controls, public-read PAT inputs, or missing-public-read-credential warnings. |
| FR-034 | **Legacy in 0.2.1; superseded by FR-037.** The OAuth setup-guide, recheck, and Continue-to-GitHub contract is retained only as historical migration context. |
| FR-035 | The deployment MUST provide an authenticated embedding-profile registry with create/read/update/delete, provider/model probing, at most one active profile (exactly one when ready), explicit reindex status, and atomic last-known-good switching. |
| FR-036 | The deployment MUST provide the bounded host operations CLI and private-admin access topology defined in sections 5.5, 11.1, and 15.5; it MUST NOT add a separate public management protocol or treat a non-standard port as access control. |
| FR-037 | RepoNPC MUST retire GitHub OAuth and browser-entered public-read PATs, resolve selected public repositories through bounded unauthenticated GitHub REST requests, and fetch source only by a validated immutable full commit SHA. Rate exhaustion MUST provide a safe retry state and preserve manual continuation. Discovery and analysis MUST NOT receive or fall back to the independent writeback credential. |

### 2.2 Non-functional requirements

| ID | Requirement |
| --- | --- |
| NFR-001 | Security: untrusted inputs MUST NOT change system policy, execute code/tools, create arbitrary network requests, traverse paths, or inject active HTML/SVG. |
| NFR-002 | Privacy: raw conversations MUST NOT be persisted by default; logs MUST omit secrets, full prompts, full answers, and raw IP addresses. |
| NFR-003 | Availability and capability degradation: an invalid update MUST NOT replace the last known-good bundle; first boot without a bundle MUST present an actionable setup state; and an unavailable optional integration MUST NOT disable unrelated local or public functions. Every unavailable primary action MUST identify the specific cause, a next recovery action, and a safe alternative when one exists. |
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

### 2.3 Version 0.1.4 functional requirements

| ID | Requirement |
| --- | --- |
| FR-025 | The authenticated admin UI MUST default to a guided onboarding flow that explains the product outcome, preserves raw YAML as an advanced mode, resumes saved configuration, and exposes the next valid action with a reason when blocked. Every non-terminal guided stage MUST support backward navigation or an equivalent Edit action without requiring a full reset; only selection-bound results and data for removed or materially changed repositories may be invalidated. |
| FR-026 | RepoNPC MUST discover and resolve public GitHub repositories from an owner-supplied username/profile URL or manual repository slug without OAuth, private-repository access, source download, model calls, or broadened writeback-token permissions before explicit repository selection. |
| FR-027 | RepoNPC MUST analyze only explicitly confirmed public repositories, reuse the production indexing/trust boundaries, invoke only the configured provider/model, clean temporary data, and return separately labeled repository facts and model inferences. Analysis is an optional enhancement: before preflight and on every blocked or failed analysis state, the owner MUST be able to skip it and continue with owner-authored contribution fields without first triggering a failed request. |
| FR-028 | Model-generated role, responsibility, achievement, context, summary, or translation suggestions MUST remain unconfirmed proposals until the owner accepts or edits them; only confirmed configuration text becomes `OWNER_ASSERTION`. The owner MUST be able to author contributions manually and validate, preview, copy, or download a complete YAML draft without model availability, a GitHub public-read connection, or GitHub writeback. |

### 2.4 Legacy version 0.1.6 identity and connection requirements (superseded by 0.2.1)

The following bullets document the implemented migration source only. They are not 0.2.1 release requirements and MUST NOT be used to justify retaining a reachable OAuth/PAT product flow after ADR-028 is implemented.

- GitHub OAuth uses the Authorization Code Web Application Flow with a cryptographically random one-use `state`, PKCE S256 verifier/challenge, server-side token exchange, fixed configured callback URL, and a short-lived `HttpOnly` OAuth transaction cookie with `SameSite=Lax`. It is initiated only from an existing authenticated RepoNPC session and returns a public-read connection to that same owner; it never issues an owner session.
- OAuth has one connection intent. Legacy setup/login intents must return a safe removal error and must never create an owner, consume setup/local-launch proof, or redirect to GitHub. Expired, replaced, replayed, wrong-intent, and cross-browser transactions fail closed.
- The GitHub numeric user ID is stable connection metadata. The GitHub login is display metadata only and has no RepoNPC authentication meaning.
- OAuth requests no repository scope. RepoNPC rejects a broader reported scope, including `public_repo`. A selected OAuth token may be used only as `identity_public_read`; it can read public metadata/source after a bounded server-side readiness probe, but cannot write. A `401` makes that connection unavailable and MUST NOT select a PAT or writeback credential automatically.
- A manually submitted fine-grained PAT is never an authentication method. Its input is cleared immediately after submission and its persisted form is `public_read` only. It is never shown, echoed, masked, fingerprinted, logged, or returned to the browser.
- GitHub-only ownership is not supported in v1. Removing an OAuth connection affects only GitHub-backed public-read work and cannot revoke or create a RepoNPC session.

### 2.5 Version 0.1.7 bounded resolver and batch requirements

| ID | Requirement |
| --- | --- |
| FR-032 | GitHub-backed guided analysis MUST use a centralized unauthenticated public-read resolver that obtains public repository eligibility and immutable commit OIDs through bounded fixed-origin REST metadata, and downloads only an archive addressed by that full commit SHA. It MUST reject unconfirmed, private, inaccessible, or policy-disallowed archived repositories before source access; it MUST never send or fall back to the writeback credential. Anonymous primary/secondary rate exhaustion MUST produce a safe bounded retry state without busy looping. |
| FR-033 | Guided analysis MUST run as a durable, owner-scoped, idempotent batch with safe snapshots/events, bounded stage-specific concurrency, pause/resume/cancel/retry/restart recovery, isolated staging and terminal cleanup. Cache reuse MUST be integrity-checked and keyed by immutable commit plus policy, parser, embedding, chat model, prompt, and output-schema identities. A dispatched generation interrupted by cancellation or restart MUST require explicit retry confirmation. |

### 2.6 Legacy version 0.1.8 OAuth setup-guidance requirements (superseded by 0.2.1)

This section is historical migration context. The 0.2.1 target removes the setup guide and every OAuth/PAT entry point; FR-037 and ADR-028 are normative.

- When OAuth is not configured, the authenticated GitHub connection button MUST remain keyboard-operable and MUST open a setup guide dialog. It MUST NOT submit an OAuth start request or redirect to GitHub in that state.
- Recheck reports configuration state and does not implicitly navigate. When OAuth is configured, the dialog exposes a distinct **Continue to GitHub** action that performs the top-level redirect and preserves Authorization Code Flow, PKCE S256, one-use state, fixed callback, server-side token exchange, and connection intent.
- The setup guide MUST identify host-side deployment configuration, show the authoritative callback URL, link only to the fixed GitHub official OAuth-App documentation URL, explain host-secret configuration and service restart/recheck steps, and warn that secrets, encryption keys, and tokens MUST NOT be pasted into the browser.
- GET /api/admin/github/oauth/setup-guide MUST require an authenticated session and return only configured, callback_url, documentation_url, and next_step. It MUST set Cache-Control: no-store and MUST NOT return environment values, secret-file paths, secret material, token material, or owner identity.
- Dialog behavior MUST meet NFR-009: semantic dialog labeling, focus trap, Escape close, focus return to the invoking button, visible status/error announcements, Traditional Chinese/English parity, responsive layouts at 375/768/1024/1440 pixels, and reduced-motion compatibility.
- GitHub expiring-token refresh, refresh-token rotation, and revoke-error recovery are explicitly deferred from 0.1.8. Until a separately approved lifecycle amendment is implemented, a selected credential that receives `401` is marked `connection_required` and requires explicit reconnection; RepoNPC MUST NOT silently refresh or fall back to a PAT or writeback credential.

### 2.7 Version 0.1.9 engineering requirements

#### External embedding profile registry

- A deployment MUST connect at least one external embedding interface: `ollama`, `vllm`, or `openai_compatible`. An in-process/local sentence-transformers runtime is not a supported production profile; it may be used only by isolated benchmark/build fixtures.
- Chat and embedding profiles are independent. A configured chat model never implies embedding capability. The selected embedding service MUST expose an embeddings operation and a model identity that can be probed before activation.
- The authenticated Web Admin MUST support embedding-profile create, read, update, delete, probe, and explicit activation. At most one profile may be `active`; deleting or disabling the active profile is rejected unless a replacement has passed its probe. A deployment with no valid active profile is not ready for semantic retrieval.
- A profile records a stable local ID, provider kind, provider model ID, server-side endpoint/credential references, observed dimension, normalization, query/passage prefixes, capability status, and timestamps. Secret values and private URLs never enter browser responses, public YAML, bundles, logs, or snapshots.
- Activating a new profile whose model identity, dimension, prefix, normalization, or provider semantics differ from the active bundle MUST enter `reindex_required`/`reindexing` state. The candidate is probed, indexed, validated, and smoke-tested before an atomic switch. Any failure keeps the last-known-good profile/bundle serving.
- The first-run model center MUST start with explicit service selection and no selected provider/model. Only after the owner chooses Ollama may its curated catalog recommend `qwen3-embedding:0.6b`, with `BAAI/bge-m3` and `embeddinggemma:300m` as alternatives. Catalog entries MUST show license, language/context notes, resource estimate, and provider support; recommendations never create a profile, download a model, or substitute for a live probe.
- Ollama MAY expose provider-native installed-model listing, curated pull, progress/cancel, and delete actions. vLLM and generic OpenAI-compatible providers expose connect/list/probe/select only; installation is performed on the provider host. RepoNPC MUST NOT download arbitrary URLs, arbitrary local paths, or unverified model archives.

#### Private administration and password policy

- The deployment profile MUST be explicit. `loopback_evaluation` uses the 0.2.0 local-launch grant and has no password creation/login UI. `production` (and any non-loopback admin exposure) requires a 15–128 Unicode-code-point password. Fifteen is a minimum, not a maximum. No character-class composition rule is required; new passwords are rejected when present in the configured common/compromised-password blocklist.
- Existing password hashes remain usable during migration and are not deleted in loopback mode. Production password creation/change and host recovery apply the production policy. Argon2id, backoff, secure cookie sessions, CSRF, origin checks, idle/absolute expiry, and revocation remain mandatory where applicable.
- A non-standard port is not an access control. The supported headless topology binds the admin-capable service to loopback and uses an SSH local-port tunnel, or uses a private LAN/VPN with firewall allowlisting. A reverse proxy MAY expose visitor routes while denying `/admin` and `/api/admin` from the public Internet. A public `0.0.0.0` admin listener is not a supported default.

#### Local-first owner and recovery

- In `loopback_evaluation`, `reponpc admin launch-token` creates a 256-bit one-use two-minute grant only after loopback configuration validation. Its digest is stored in runtime SQLite; the browser receives it only in a URL fragment and exchanges it for the normal session. The first valid exchange atomically creates or reuses the sole local owner without asking for a username or password. A missing/expired grant presents a relaunch action, not registration or GitHub sign-in.
- In production or any non-loopback mode, host-issued setup proof MUST be followed by local username/password creation. The local password remains the break-glass recovery method. `reponpc admin set-password --data-dir <dir>` is host-only, changes only the local hash, never reopens setup or changes the independent writeback credential, and is required before a passwordless local owner can become production-ready.
- GitHub OAuth and public-read PATs are unsupported under 0.2.1 and have no owner-session role. Public repository discovery/analysis uses anonymous REST capacity.

#### Bounded operations CLI

- Web Admin is the daily surface for configuration, embedding profiles, provider probes, and status. The host CLI is limited to `admin launch-token` for loopback launch, `admin setup-code`/`admin set-password` for production bootstrap/recovery, `runtime check`, `runtime backup <path>`, `bundle status`, `bundle verify <id>`, `bundle pin <id>`, and `bundle unpin`.
- Linux/headless operators use SSH to reach the same Web Admin; no separate public management protocol or public setup port is added. Commands require explicit paths/IDs, stable safe errors, and consistency/rollback tests.

### 2.8 Version 0.2.2 model setup requirements

| ID | Requirement |
| --- | --- |
| FR-038 | The authenticated owner MUST configure chat and embedding independently using a provider-neutral service form with an explicit protocol/preset, API base URL, write-only API key when needed, and editable model ID. Listing is optional assistance; model capability testing is mandatory before use. New deployments MUST start with neither provider nor model selected and allow administration/manual authoring without models. |
| FR-039 | Model connections MUST persist through a deployment-local protected secret boundary, with server-issued references, explicit credential replacement/removal, bounded validated egress, safe metadata-only reads, and transactional revision/activation behavior. Editing a destination MUST NOT forward a previously stored key to that destination. Environment-based configurations remain supported and cannot silently overwrite owner-managed selections. |
| FR-040 | First-run model setup MUST present separate chat and search capabilities, reversible steps, contextual recovery, and bilingual plain-language statuses. Dimensions, prefixes, connection references, raw errors, and model-installation diagnostics MUST NOT be required knowledge in the primary flow. Configuration, test, activation, download, reindex, and publication are distinct operations. |

These requirements extend FR-006/FR-012/FR-025/FR-035 and NFR-001/002/003/008/009/011/012/013/014. AC-053 through AC-057 define their acceptance. All prior non-legacy v1 requirements remain required.

### 2.9 Version 0.2.3 model-first guided workflow

| ID | Requirement |
| --- | --- |
| FR-041 | The authenticated first-run AI route MUST configure, test, and explicitly select both analysis/chat and search models before repository selection and analysis. Welcome is unnumbered; the six steps are models, repositories, analysis, contributions, profile, and preview/draft. A manual route MUST be available at welcome, model setup, and analysis blockers without an attempted model call. Existing draft/resume/edit routes MUST preserve unrelated work and lead directly to any missing prerequisite. |
| FR-042 | Admin analysis MUST use an explicitly selected, tested, immutable chat/embedding revision pair independently of public bundle activation. A clean runtime MUST be able to configure this pair and analyze a confirmed repository without a published bundle, preconfigured environment provider, or restart. Public semantic chat still requires validated compatible bundle activation. Model or selection changes MUST invalidate stale admission plans/caches without retargeting in-flight work, silently generating again, or discarding owner-confirmed text. |

These extend FR-025/FR-027/FR-028/FR-033/FR-038/FR-040 and NFR-001/002/003/008/009/011/013/014. AC-058 through AC-060 are additional release gates. Section 11.6 governs order and analysis selection where older sections conflate a selected analysis profile with a publicly active embedding profile.

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
- Runtime secrets and deployment-specific values come from environment variables, mounted secret files, or the protected deployment-local model connection store defined in section 11.5. Public YAML never contains connection credentials or private endpoints.
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
- `embedding.model`, `embedding.dimension`, and `embedding.query_prefix` become part of the bundle compatibility contract. The descriptor is a public compatibility record only; provider endpoints, credentials, and profile registry state remain deployment-local. `embedding.adapter` MUST be one of the external bundle identities (`ollama` or `openai_compatible`); `vllm` is normalized to `openai_compatible` in the bundle. A local adapter value is permitted only in explicitly marked benchmark fixtures.

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

There is no RepoNPC-local production embedding default. Every deployment MUST connect at least one external embedding interface: `ollama`, `vllm`, or `openai_compatible`. The local sentence-transformers adapter may remain in isolated benchmark/build fixtures only; it is not a runtime requirement.

The embedding profile registry is deployment-local mutable state and is independent from the chat profile. Each profile contains a stable local ID, provider kind, provider model ID, server-side endpoint/credential references, and the observed compatibility identity: dimension, normalized float32 behavior, query prefix, passage prefix, and provider/model version where available. Secret values and private endpoints are never serialized into public YAML, bundles, browser responses, logs, or snapshots.

The authenticated Web Admin MUST support profile create/read/update/delete, probe, and explicit activation. At most one profile may be active. A profile cannot be deleted or disabled while it is the only valid active profile. Probe MUST call the provider's model/embedding capability and a bounded sample embedding; a model-list response alone is insufficient. A profile is `ready` only when probe succeeds and its identity matches the active index bundle.

Changing provider, model identity, dimension, prefixes, normalization, or relevant provider semantics invalidates vector compatibility and MUST set `reindex_required`. Activation then follows `probe -> build/reindex -> validate -> smoke test -> atomic switch`; until the final switch, the prior profile/bundle remains the last-known-good service. Failed, cancelled, or timed-out reindex work MUST clean staging and leave the prior state active. RepoNPC MUST NOT silently select another profile/provider/model.

After explicit Ollama selection, its curated model catalog SHOULD include `qwen3-embedding:0.6b` as a recommendation, `BAAI/bge-m3` and `embeddinggemma:300m` as alternatives, and larger Qwen3-Embedding variants for hosts with more memory. This is not a product default. Catalog metadata MUST include license, language/context notes, approximate resource requirements, and supported provider operations; the live probe remains authoritative for dimension and capability.

The initial catalog is intentionally small and uses provider/model IDs rather than pretending that every provider exposes the same inventory:

| Candidate | Best fit | Upstream/provider notes | RepoNPC operation |
| --- | --- | --- | --- |
| Ollama `qwen3-embedding:0.6b` | Recommended starter for a personal zh-TW/en/code portfolio | Qwen3-Embedding 0.6B, Apache-2.0; 32K context and up to 1024 dimensions upstream; Ollama publishes a roughly 639 MB quantized tag | Curated pull/list/probe/delete through Ollama-native APIs |
| Ollama `bge-m3` | Strong multilingual and longer-document alternative | BGE-M3, MIT; 100+ languages, 8K context, 1024 dimensions; Ollama publishes a roughly 1.2 GB tag | Curated pull/list/probe/delete through Ollama-native APIs |
| Ollama `embeddinggemma:300m` | Smaller-resource alternative | Google Gemma license/terms apply; 100+ languages and a 2K Ollama context tag; verify license acceptance and probe identity before activation | Curated pull/list/probe/delete through Ollama-native APIs |
| Ollama `qwen3-embedding:4b` or `:8b` | Quality/recall experiments on capable hardware | Larger Qwen3 variants trade memory and latency for quality; exact quantization, dimension, and resource cost are provider-tag dependent | Curated pull/list/probe/delete only after an allowlisted catalog entry exists |
| vLLM or generic OpenAI-compatible model ID | Operators already serving an embedding endpoint | The operator may serve Qwen3, BGE-M3, EmbeddingGemma, or another licensed model through `/v1/embeddings`; model installation stays on that provider host | Connect/list/probe/select; no RepoNPC download |
| Hosted OpenAI-compatible API (for example, a gateway exposing `text-embedding-3-small`/`text-embedding-3-large`) | No local model lifecycle desired | Availability, pricing, retention, dimensions, and terms belong to the selected provider; the model ID is not guaranteed across gateways | Connect/list/probe/select; no RepoNPC download |

The Qwen3 0.6B, BGE-M3, and EmbeddingGemma dimensions/context values above are catalog hints, not bundle contracts. A sample establishes actual dimension and finite-vector behavior. Query/passage prefixes, task instructions, pooling, and model revision cannot in general be inferred from one vector; they come from a reviewed model preset or explicit advanced settings and are recorded with the observed identity. Never apply the E5 `query: ` / `passage: ` defaults to every model. Normalization is the explicit RepoNPC adapter contract and is validated at build/runtime. A structurally successful sample does not prove retrieval quality; AC-009 remains required.

RepoNPC MUST provide a provider-aware **model center**, not a generic download area. For Ollama, a curated model ID may be pulled, monitored, cancelled, and deleted by calling Ollama on the configured private host. For vLLM and generic APIs, the owner follows the provider's own installation/serving process and then enters or selects the served model ID. The browser never receives a provider key and RepoNPC never accepts arbitrary URLs, local paths, shell commands, or unverified archives. This boundary prevents SSRF, supply-chain substitution, license ambiguity, and accidental disk/CPU exhaustion while still making the common Ollama path self-service.

Model lifecycle is provider-owned. For Ollama, the Web Admin MAY expose a curated catalog, installed-model list, pull/progress/cancel, and delete through Ollama-native endpoints. For vLLM and generic OpenAI-compatible services, the Web Admin exposes connect/list/probe/select only; operators install or serve models on those hosts. RepoNPC MUST NOT implement an arbitrary URL/local-path model downloader or execute provider-supplied installation commands.

Index and runtime query embeddings MUST use the same profile identity and semantics. Embedding credentials remain in protected server-side storage on the host that performs the operation; an index builder receives an explicit frozen profile snapshot plus independently provisioned secrets. A successful runtime probe does not prove that a GitHub Actions runner can reach a private provider. Section 11.5 does not change the publication topology.

### 5.5 Executable CLI

The installed `reponpc` console entrypoint has the following bounded commands:

```text
reponpc
reponpc serve
reponpc admin launch-token [--data-dir <directory>]
reponpc admin setup-code [--data-dir <directory>]
reponpc admin set-password [--data-dir <directory>] [--username <owner>]
reponpc admin hash-password
reponpc runtime check [--data-dir <directory>]
reponpc runtime backup <path> [--data-dir <directory>]
reponpc bundle status [--data-dir <directory>]
reponpc bundle verify <bundle-id> [--data-dir <directory>]
reponpc bundle pin <bundle-id> [--data-dir <directory>]
reponpc bundle unpin [--data-dir <directory>]
reponpc config validate <path>
reponpc index build --config <path> --output <directory>
reponpc index publish --bundle-dir <directory>
reponpc index publish-manifest --bundle-dir <directory>
```

- No arguments and `serve` MUST enter the same validated FastAPI/Uvicorn startup path.
- `admin launch-token` MUST work only for a fully validated `loopback_evaluation` configuration, replace any unused prior grant, store only a SHA-256 digest with a two-minute expiry, and print one URL whose secret is confined to the `#local-launch=` fragment. It MUST fail for production, non-loopback, or trusted-proxy configurations. The local launcher invokes it automatically after readiness.
- `admin setup-code` MUST initialize the selected runtime database, replace any unused prior code, store only a SHA-256 digest with a 15-minute expiry, print the new 256-bit code once, and fail safely after a durable owner exists.
- `admin hash-password` remains an OPTIONAL pre-provisioning/legacy command and MUST print only a PHC-format Argon2id hash after non-echoing confirmation.
- `admin set-password` is host-only production recovery. It discovers or accepts the sole owner explicitly, creates or updates only the local Argon2id hash, applies the production password policy, and never reopens setup or changes GitHub credentials.
- `runtime check` verifies runtime SQLite integrity, schema, permissions, and active/previous bundle pointers without printing secrets. `runtime backup` uses an online-consistent SQLite backup (or a documented stopped-process fallback), refuses ambiguous/broad paths, and never includes provider bodies or raw session tokens.
- `bundle status`, `bundle verify`, `bundle pin`, and `bundle unpin` inspect or change only local bundle state. Verification performs checksum/schema/model/dimension/database/smoke checks; pin/unpin is atomic and preserves the active last-known-good bundle on failure.
- Embedding profile CRUD/model pull is intentionally Web Admin functionality; the CLI does not duplicate interactive provider management.
- Help, configuration validation, and index commands MUST NOT start the server or require unrelated deployment settings.
- `index build` MUST resolve exact public repository commits, use the configured production embedding adapter, build/verify the index and bundle, generate `public/profile.json`, and fail closed if the required non-profile public assets are missing or invalid. Until the Phase 4 card/character producer is integrated, those assets are supplied from the command's documented `public/` input directory; the CLI MUST NOT fabricate production placeholder assets.
- `index publish` MUST create, upload, and verify the immutable Release asset, then write only a local pending stable-manifest artifact below the bundle directory. It MUST NOT mutate the remote stable manifest.
- `index publish-manifest` MUST accept only that verified pending artifact and perform the sole remote `stable-manifest.json` update.
- Every command MUST return a nonzero exit with a stable safe message on failure and MUST NOT print credentials, upstream bodies, or raw rejected configuration.

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
    "greeting": "歡迎探索我的作品集。",
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
  "character": {
    "mode": "builtin",
    "asset_url": "/api/public/character.png",
    "revision": 1,
    "frame_duration_ms": 160,
    "movement": "subtle"
  },
  "index": {"version": "...", "built_at": "...", "repository_count": 1}
}
```

The endpoint returns `503 INDEX_UNAVAILABLE` before first bundle activation. It uses an ETag derived from bundle version and locale.

The immutable bundle stores one internal `public/profile.json` with this schema-v1 shape:

```json
{
  "schema_version": 1,
  "locales": {
    "zh-TW": {
      "profile": {},
      "repositories": [],
      "suggested_questions": []
    },
    "en": {
      "profile": {},
      "repositories": [],
      "suggested_questions": []
    }
  },
  "character": {},
  "index": {}
}
```

The locale keys MUST be exactly `zh-TW` and `en`; both locale objects MUST contain every field needed for the public response, including the localized `profile.greeting`. Character metadata MUST include the configured `frame_duration_ms` (80–1000 ms) and `movement` (`none` or `subtle`). The bundle producer derives these values from the validated configuration and built index metadata. The verifier validates both locales before activation. The route selects only the requested locale and constructs the response with `locale` added at the top level. Missing or invalid locale data fails closed; the route MUST NOT cross-fallback to the other required locale.

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

### 9.5 Authenticated analysis-batch API (0.1.7)

The following same-origin authenticated admin endpoints set `Cache-Control: no-store`. Creation and every state change require the current CSRF token. Snapshot payloads contain safe metadata, normalized validated results, aggregate counts, rate/capacity status, and server-assigned IDs only; they never contain credentials, archive bytes, repository bodies, prompts, provider bodies, staging paths, or incomplete output.

| Method and path | Contract |
| --- | --- |
| `POST /api/admin/onboarding/analysis-batches/preflight` | Validates one explicit confirmed public selection (1–50 repositories), resolves eligible immutable commits through bounded unauthenticated REST, predicts cache use/capacity, and creates a short-lived selection-bound `plan_id`. |
| `POST /api/admin/onboarding/analysis-batches` | Requires a valid `plan_id` and opaque idempotency key; creates or returns the one owner-scoped active batch. |
| `GET /api/admin/onboarding/analysis-batches/active` | Returns the active safe snapshot or `404 NOT_FOUND`. |
| `GET /api/admin/onboarding/analysis-batches/{id}` | Returns a safe snapshot for the requesting owner only. |
| `GET /api/admin/onboarding/analysis-batches/{id}/events` | Streams ordered SSE events with monotonically increasing numeric event IDs and supports `Last-Event-ID` replay. Snapshot reconciliation is authoritative if an event was pruned. |
| `POST /api/admin/onboarding/analysis-batches/{id}/pause`, `/resume`, `/cancel`, `/retry` | Performs the named idempotent state transition. Retry may resume only retryable items and MUST require explicit confirmation for an interrupted generation. |

Batch state is `queued -> running <-> paused -> cancelling -> cancelled|completed|completed_with_errors|failed`. An item reports the safe stage `queued`, `resolving_commit`, `fetching_source`, `filtering`, `indexing`, `embedding`, `generating`, `validating`, `cleaning_up`, or `complete`, or an explicit terminal/waiting reason. The old one-repository analysis endpoint remains a compatibility adapter: it creates a one-item batch, waits only for its terminal snapshot within its existing request deadline, and returns the prior safe result shape rather than bypassing batch policy.

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
| 401 | `LOCAL_LAUNCH_DENIED` | Local-launch grant or loopback boundary is absent, invalid, expired, replayed, or unsafe. |
| 401 | `SETUP_DENIED` | First-owner code is absent, invalid, expired, or submitted with mismatched owner fields. |
| 403 | `CSRF_FAILED` / `WRITE_NOT_ALLOWED` | Security policy rejected the operation. |
| 404 | `NOT_FOUND` | Allowlisted resource does not exist. |
| 409 | `CONFIG_CONFLICT` | Expected Git blob SHA no longer matches. |
| 409 | `SETUP_ALREADY_COMPLETE` | A durable or explicitly pre-provisioned owner already closes first-owner setup. |
| 410 | `GITHUB_LOGIN_REMOVED` | A retired GitHub login/setup route was called; connect GitHub from an authenticated settings session. |
| 409 | `ANALYSIS_BATCH_ACTIVE` / `ANALYSIS_PLAN_STALE` | Another owner batch is active, or the selection-bound preflight plan expired or no longer matches. |
| 413 | `PAYLOAD_TOO_LARGE` | Config, question, or asset limit exceeded. |
| 422 | `CONFIG_INVALID` / `ASSET_INVALID` | Structurally valid request fails domain validation. |
| 429 | `RATE_LIMITED` / `DAILY_BUDGET_EXHAUSTED` / `CONCURRENCY_LIMIT` | Cost/abuse limit reached. |
| 429 | `GITHUB_RATE_LIMITED` | GitHub primary or secondary rate budget requires admission to wait; safe retry metadata is supplied when known. |
| 502 | `PROVIDER_ERROR` / `GITHUB_ERROR` | Upstream failed safely. |
| 503 | `INDEX_UNAVAILABLE` / `MODEL_UNAVAILABLE` / `SERVICE_NOT_READY` | Required capability unavailable. |
| 504 | `PROVIDER_TIMEOUT` | Configured model exceeded timeout. |

`GITHUB_RATE_LIMITED` is a safe recoverable result when anonymous REST capacity is exhausted. It includes only a sanitized retry time, never triggers credential collection or writeback-token fallback, and leaves manual continuation available.

## 11. Admin contract

### 11.1 Authentication

- A new deployment starts with no product default username or password. `GET /api/admin/auth/methods` reports the configured access mode without exposing owner or credential state.
- In `loopback_evaluation`, the launcher creates a random 256-bit grant only after the server is ready. Runtime SQLite stores only its SHA-256 digest and two-minute expiry; reissuing invalidates the prior unused grant. The browser URL uses `/admin#local-launch=<grant>` so the secret is not sent in the HTTP request, Referer header, or server access log.
- The frontend reads the fragment once, immediately calls same-origin `POST /api/admin/session/local-launch`, and clears the fragment with `history.replaceState` before rendering external links. Grant consumption, creation/reuse of the sole owner, session issuance, and invalidation of competing unused grants are one transaction. Concurrent exchanges create exactly one owner and at most one successful session per grant.
- The server accepts local launch only when the deployment profile, configured bind, public base URL, request peer, `Host`, and origin are loopback-valid and trusted-proxy interpretation is disabled. It treats forwarded headers as untrusted in this mode. Invalid, expired, replayed, cross-origin, forwarded, and non-loopback exchanges return the same safe failure.
- A loopback browser with neither a valid session nor a launch grant receives no registration or password/GitHub login form. It sees one localized action telling it to reopen RepoNPC with the local launcher.
- In `production`, `GET /api/admin/setup` reports only whether password setup is required and whether an unexpired code is available. The host operator runs `reponpc admin setup-code` to create a random 256-bit code valid for 15 minutes. Runtime SQLite stores only its SHA-256 digest; reissuing invalidates the prior unused code.
- The production first-owner request supplies the code, a trimmed 1–64 character username, and a 15–128-character password plus confirmation. No character composition rule is imposed, but new values are checked against the common/compromised-password blocklist. Code consumption, Argon2id hash storage, setup deletion, and initial session creation are atomic. After an owner exists, production setup is permanently unavailable and later visits receive the password sign-in surface.
- For explicit pre-provisioning/backward compatibility, operators MAY set `REPONPC_ADMIN_USERNAME` and a PHC-format `REPONPC_ADMIN_PASSWORD_HASH` generated by `reponpc admin hash-password`. This mode disables first-owner setup.
- A GitHub OAuth App or public-read PAT is neither required nor supported. Owner sessions and local/manual work remain independent; anonymous GitHub capacity affects only discovery/analysis and returns a retryable bounded state.
- Production password login uses a generic failure message and exponential per-IP/account backoff. Local-launch failure is generic and rate-limited independently.
- Successful password or local-launch exchange creates a random 256-bit server-side session and sets `__Host-reponpc_session` with `Secure`, `HttpOnly`, `Path=/`, and `SameSite=Strict`.
- Idle expiration defaults to 30 minutes; absolute expiration defaults to 12 hours. Refresh rotates the session ID.
- A random CSRF token is returned in the login/refresh JSON body, stored only in browser memory, hashed in the session row, and required as `X-CSRF-Token` on every state-changing authenticated request.
- Logout revokes the current session. Logout-all increments the admin session epoch; production requires the current local password, while loopback evaluation requires a fresh unconsumed local-launch grant and leaves the browser requiring relaunch.
- `GET /api/admin/auth/methods` returns only `{mode:"local_launch"|"password",password:{available},setup_required}`. GitHub is not reported as an authentication method.
- Authenticated `GET /api/admin/github/oauth/setup-guide` returns `{configured,callback_url,documentation_url,next_step}` with `Cache-Control: no-store`. The callback is the validated same-origin fixed callback; no secret, token, secret-file path, environment value, or owner identity is returned.
- `POST /api/admin/github/connections/oauth/start` creates one bounded authenticated connection transaction and redirects to GitHub with PKCE. Legacy `POST /api/admin/session/github/start` and `POST /api/admin/setup/github/start` MUST return `410 GITHUB_LOGIN_REMOVED`, MUST NOT redirect, create an owner/session, or consume setup/local-launch proof. One fixed `GET /api/admin/github/callback` validates only the connection intent.
- Legacy OAuth callback/start, connection, PAT, setup-guide, and identity endpoints MUST become non-redirecting, non-mutating `410 GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED` responses during the compatibility window and MUST be removed after that window. They MUST NOT accept, decrypt, return, or log credential material.
- Embedding profile endpoints (`GET/POST /api/admin/embedding-profiles`, `GET/PUT/DELETE /api/admin/embedding-profiles/{id}`, `POST /api/admin/embedding-profiles/{id}/probe`, and `POST /api/admin/embedding-profiles/{id}/activate`) expose only safe metadata. They enforce one active profile, never return credentials/private URLs, and report `probe`, `reindex_required`, `reindexing`, `ready`, or `last_known_good` states. Ollama model pull/delete actions are separate provider-native operations and require explicit confirmation.

### 11.2 Endpoints

| Method and path | Contract |
| --- | --- |
| `GET /api/admin/setup` | Production-only public safe state `{setup_required,setup_code_available}`; loopback mode reports setup unavailable and never returns code, digest, path, or expiry. |
| `POST /api/admin/setup` | Production-only same-origin `{setup_code,username,password,password_confirmation}` -> initial session/cookie, `SETUP_DENIED`, or `SETUP_ALREADY_COMPLETE`; rejected in loopback mode. |
| `POST /api/admin/session/local-launch` | Loopback-only same-origin `{grant}` -> `{csrf_token,expires_at,absolute_expires_at}` and cookie; grant is consumed atomically and never returned. |
| `POST /api/admin/session` | Production-only `{username,password}` -> `{csrf_token,expires_at,absolute_expires_at}` and cookie; rejected in loopback mode. |
| `GET /api/admin/auth/methods` | Safe `{mode,password:{available},setup_required}` without GitHub or owner identity state. |
| `GET /api/admin/github/oauth/setup-guide` | Authenticated safe `{configured,callback_url,documentation_url,next_step}` for host-side setup guidance; no credential or identity material. |
| `POST /api/admin/session/github/start` | Removed login route; always `410 GITHUB_LOGIN_REMOVED` with no redirect or state change. |
| `POST /api/admin/setup/github/start` | Removed setup route; always `410 GITHUB_LOGIN_REMOVED` with no redirect or state change. |
| `POST /api/admin/github/connections/oauth/start` | Authenticated connection transaction -> redirect response and short-lived transaction cookie. |
| `GET /api/admin/github/callback` | Single fixed registered callback validates session/state/cookie/connection intent, stores safe connection metadata, and redirects to a fixed `/admin` result. |
| Legacy `/api/admin/github/connections...`, OAuth callback/start, setup-guide, and identity routes | Non-mutating `410 GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED` during the bounded compatibility window; no redirect, credential input, state mutation, or secret output. |
| `POST /api/admin/session/refresh` | Auth + CSRF -> rotated session and CSRF token. |
| `DELETE /api/admin/session` | Auth + CSRF -> `204`, revoke current session. |
| `DELETE /api/admin/sessions` | Auth + CSRF + `{password?}` -> `204`, revoke all sessions. The local password is required as the recovery proof; a fresh GitHub sign-in cannot replace it. |
| `GET /api/admin/config` | Return `{content,blob_sha,commit_sha,updated_at}` for `reponpc.yml`. |
| `POST /api/admin/config/validate` | `{content}` -> normalized errors/warnings and parsed preview; no write. |
| `POST /api/admin/config/preview` | `{content}` -> localized profile/card/character preview; no write or model call. |
| `PUT /api/admin/config` | `{content,expected_blob_sha,commit_message}` -> commit result or `CONFIG_CONFLICT`. |
| `POST /api/admin/assets/character/validate` | Multipart PNG -> validation result and ephemeral preview; no write. |
| `PUT /api/admin/assets/character/{filename}` | PNG + `expected_blob_sha` + commit message -> allowlisted GitHub commit. |
| `GET /api/admin/readme-snippet` | Query variant -> `{markdown,asset_url,target_url}`. |
| `POST /api/admin/index/dispatch` | Trigger allowlisted `build-index.yml`; return dispatch acknowledgement. |
| `GET /api/admin/index/status` | Return last publication/activation detail and safe error diagnostics. |
| `GET /api/admin/embedding-profiles` | Authenticated list of profile IDs, provider/model labels, observed compatibility identity, active/status flags, and safe timestamps; never credentials or private URLs. |
| `POST /api/admin/embedding-profiles` | Auth + CSRF + provider/model connection reference -> create a non-active profile after structural validation; no model download unless an explicit Ollama pull action is separately confirmed. |
| `GET /api/admin/embedding-profiles/{id}` / `PUT /api/admin/embedding-profiles/{id}` | Read or update one profile's non-secret settings; a changed identity is marked `reindex_required` until a probe and verified reindex complete. |
| `DELETE /api/admin/embedding-profiles/{id}` | Auth + CSRF -> delete a non-active profile only; deleting the only valid active profile is rejected. |
| `POST /api/admin/embedding-profiles/{id}/probe` | Auth + CSRF -> bounded provider/model capability and sample-embedding probe; returns safe identity/status only. |
| `POST /api/admin/embedding-profiles/{id}/activate` | Auth + CSRF -> queue probe/reindex and atomically activate only after bundle compatibility and smoke checks; last-known-good remains on failure. |
| `GET /api/admin/embedding-models/catalog` / `GET /api/admin/embedding-models/installed` | Authenticated curated catalog and provider-native installed-model metadata; no arbitrary URL/path input. |
| `POST /api/admin/embedding-models/ollama/pull` / `DELETE /api/admin/embedding-models/ollama/{model}` | Explicit Ollama-native pull/delete with bounded model IDs, progress/status, cancellation, and no secret/private-URL disclosure. |

Admin APIs set `Cache-Control: no-store`. Login and state-changing requests require same-origin `Origin`/`Referer` validation in addition to CSRF. Admin responses never return environment values, password hashes, GitHub tokens, provider keys, or private provider URLs; the setup-guide exception is limited to its canonical callback and fixed documentation URL.

### 11.3 GitHub writeback

- The token MUST be a fine-grained token limited to contents/actions permissions on `REPONPC_CONFIG_REPOSITORY`.
- The target branch is `REPONPC_CONFIG_BRANCH`; it is never supplied by the browser.
- Allowed target paths are exactly `reponpc.yml` and normalized paths matching `assets/character/*.png`. Nested paths, deletion, renames, and arbitrary filenames are rejected in v1.
- `expected_blob_sha` is mandatory for replacement. Creation uses explicit `null` and fails if the file exists.
- Configuration is fully validated before commit. Assets are decoded and validated, not trusted by MIME/extension alone.
- Commit messages are length-limited plain text with a safe default.
- Every write creates a safe audit record with time, path, resulting commit SHA, request ID, and outcome, but not file bodies or credentials.

### 11.4 Guided onboarding contract (0.1.4)

All routes below are authenticated same-origin admin routes with `Cache-Control: no-store`; provider-consuming operations also require the current CSRF token.

#### Repository discovery and manual resolution

- `POST /api/admin/onboarding/repositories/discover` accepts `{account,page}` where `account` is a GitHub username or `https://github.com/{owner}` profile URL, `page` is 1–5, and the fixed page size is 50. It returns normalized public metadata only: slug, name, description, primary language, default branch, fork/archived flags, updated time, and HTML URL, plus `{page,has_more}`.
- `POST /api/admin/onboarding/repositories/resolve` accepts `{repository,ref}` where `repository` is `owner/name` or an exact GitHub.com repository URL and optional `ref` is a branch, tag, or SHA. It returns the normalized public slug and safe metadata; it does not fetch the repository tree, build evidence, or call a model.
- Discovery uses unauthenticated public GitHub REST requests and never sends the configured fine-grained writeback token. GitHub.com/API hosts, redirects, response bytes, timeouts, and URL normalization remain server-owned allowlists. Private, missing, or inaccessible repositories return the same `404 NOT_FOUND` behavior.
- Listing does not authorize source analysis. The browser must present checkboxes and record an explicit confirmation of the selected set before calling analysis.

#### Selected-only repository analysis

- Repository analysis is optional and MUST NOT be a prerequisite for contribution entry, local validation, local preview, copy, or download. The analysis stage exposes an explicit manual continuation before any preflight/provider/GitHub request and again on every blocker or failure. Choosing it preserves the confirmed selection and changes only still-unconfirmed analysis-derived suggestions.
- Version 0.1.7 supersedes the 0.1.4 synchronous execution lifecycle with the durable batch API in section 9.5. It does not supersede the selected-only trust boundary, explicit cost action, optional/manual path, owner-confirmation rule, or cleanup requirement.
- `POST /api/admin/onboarding/repositories/analyze` is a legacy response-shape compatibility adapter. It accepts exactly one confirmed `{slug,ref,include,exclude}` selection, creates a one-item durable batch governed by section 9.5, and waits only within the existing 120-second HTTP deadline. It MUST NOT run an independent synchronous analysis pipeline or reuse bundle publication as an implicit side effect. If the HTTP wait ends before the batch does, the durable batch remains recoverable through the batch snapshot/event API unless the owner explicitly cancels it.
- Only one owner-scoped batch may be active. The compatibility adapter and batch API reuse the exact-SHA resolver, exclusions, secret scan, parsing/chunking, evidence IDs, retrieval, context packing, prompt isolation, provider adapter, output validation, stage caps, and retry policy. Provider generation remains inside the configured maximum and defaults to 45 seconds; the existing source, evidence, context, and output hard maxima still apply.
- Analysis uses only the configured provider/model and shares the global generation semaphore. It does not decrement the anonymous public daily-chat counter. It performs no automatic retry after a completed provider call and no provider/model/cloud fallback.
- Archive bytes, repository bodies, prompts, provider bodies, incomplete output, and staging paths remain ephemeral and are removed on every terminal/recovery path. Runtime SQLite may retain only the safe batch metadata, ordered events, cache identities, and validated normalized terminal result allowed by sections 15.1 and 15.4 for at most 24 hours. A generation already dispatched is never retried after interruption without explicit owner confirmation.
- The response identifies the exact slug/commit and returns `REPOSITORY_FACT` items with supporting evidence IDs/locations plus separately labeled `MODEL_INFERENCE` suggestions. It never returns server paths, raw prompt bodies, credentials, private provider URLs, or unrestricted repository bodies.

#### Contribution suggestions and confirmation

- `POST /api/admin/onboarding/contributions/suggest` accepts one selected slug plus an owner-authored statement of at most 4,000 Unicode scalar values describing personal work, results, collaboration, and non-attribution boundaries. The original statement is returned unchanged beside editable proposed localized role/summary/claims.
- This operation may call only the configured model under the same provider, timeout, semaphore, privacy, and no-fallback rules. It MUST NOT strengthen a personal claim silently, mark a proposal confirmed, or infer authorship, employment, seniority, responsibility, achievement, or impact from repository content.
- The browser presents `REPOSITORY_FACT`, `MODEL_INFERENCE`, and proposed `OWNER_ASSERTION` groups separately. The owner may accept, edit, or reject each personal proposal. Only an explicit accept/edit action may place the text into role/summary/claims in a draft.
- Schema version 1 remains unchanged. Localized repository `role` and `summary` remain required; when the owner confirms them into `reponpc.yml`, they retain the existing `OWNER_ASSERTION` classification. Repository facts and unconfirmed model inferences are not serialized as owner assertions.

#### Draft, resume, validation, and export

- `POST /api/admin/onboarding/draft` accepts confirmed guided fields only and returns `{content,validation}` containing a complete UTF-8 schema-v1 YAML draft plus the existing normalized validation result. When `base_config` is supplied, fields outside the guided surface (including links, avatar, tags, demo URLs, card, character, and retrieval settings) are retained. It performs no model, GitHub, or publication call.
- Every non-terminal guided stage provides Back or an equivalent Edit action. Editing selection invalidates a preflight plan and analysis result only when its repository, ref, include, or exclude identity changed. Removing a repository removes only that repository's contribution state. Profile fields and unaffected repository statements/results MUST remain. A separate destructive Start over action requires confirmation.
- Existing validated configuration MUST hydrate the guided editor with its profile and selected repositories, including localized headline/bio/greeting, ref/include/exclude, role/summary, and claims. Guided draft generation MUST preserve validated fields outside the guided surface. Because the public configuration schema rejects unknown keys, a raw edit containing unmappable/unknown YAML remains in advanced mode with an actionable validation message rather than being silently discarded.
- Unsaved selections, owner-entered public statements, and confirmed suggestions MAY be stored in browser `sessionStorage` for reload/resume within the authenticated browser session. Logout and successful GitHub save MUST clear them. Session/CSRF tokens, credentials, raw repository bodies, raw prompts/outputs, and private URLs MUST NOT enter Web Storage.
- Copy and download of the generated `reponpc.yml` are local browser operations and remain available without a GitHub token. They do not mark the draft saved, mutate GitHub, or dispatch indexing.
- Existing `/config/validate` and `/config/preview` remain model-free and mutation-free. GitHub save, workflow dispatch, publication, and activation remain distinct explicit actions with existing conflict and last-known-good behavior.

#### Proposed error mapping

- Invalid usernames/URLs/slugs/pages/ref/include/exclude/owner statements return `400 VALIDATION_ERROR` with bounded field details.
- Missing/private/inaccessible accounts or repositories return `404 NOT_FOUND` without visibility disclosure.
- GitHub upstream/rate-limit failures return `502 GITHUB_ERROR` or `429 RATE_LIMITED` with bounded retry metadata when available.
- No eligible source content returns `422 CONFIG_INVALID` with safe reason `NO_ELIGIBLE_CONTENT`.
- Provider unavailable, invalid, timed out, or failed returns the existing `MODEL_UNAVAILABLE`, `PROVIDER_ERROR`, or `PROVIDER_TIMEOUT` code; selection and browser draft remain available and no fallback occurs.
- Cancellation/disconnect sends no replacement success body; server cleanup remains mandatory. Failure of one repository does not erase other confirmed selections.

### 11.5 Provider-neutral model setup (0.2.2)

This section is the current model-configuration boundary. Where older text prohibits all browser-originated provider keys/URLs, this section authorizes only owner-entered values in the authenticated same-origin model form. Reads remain metadata-only. Existing embedding routes in section 11.2 remain the migration baseline; the implementation handoff identifies the wire-contract preparation work before application edits.

#### Connection and role separation

- A connection identifies one explicitly selected protocol (`ollama` native or `openai_compatible`, with the existing `vllm` preset), one API base URL, and optional authentication. The protocol is not inferred from a model name or hostname. A base URL includes any gateway prefix such as `/v1`; fixed operation paths are appended once, without guessing another service.
- Chat and embedding have separate profile selections and capability tests. The same saved connection MAY be explicitly selected for both, but neither capability, model, nor credentials are automatically copied to another destination. A chat-only service leaves search unconfigured with a direct action to configure it.
- Model ID is manually editable for every provider, including existing non-catalog Ollama models. An optional model list is scoped to the selected connection. Unsupported listing (`404`/`405`/`501`) permits direct capability testing of the typed ID. Authentication, timeout, rate, and malformed-list failures are surfaced safely; none silently switch services. Listing never establishes readiness by itself.
- Chat testing uses a bounded synthetic request through the actual chat adapter and required envelope/capability validation. Embedding testing uses bounded synthetic query and passage samples and validates dimensions/finite values/normalization. Tests require explicit action, have cost/time/concurrency bounds, and never send repository content or owner drafts.
- A new deployment, launcher, or form with no explicit configuration MUST leave both roles unconfigured. Missing model settings MUST NOT prevent process health, protected admin access, manual authoring, validation, preview, or export. Semantic chat remains unavailable until its full prerequisites pass. No model download or upstream request occurs merely because the user opens setup.
- Public schema-v1 draft validation/export may retain an existing or explicitly labeled illustrative embedding descriptor from the public template. That descriptor is not a selected runtime connection or proof of readiness. Before a real build, replace it with the explicitly selected, verified profile identity and validate the match. This preserves manual export without adding a null descriptor, silently choosing a provider, or weakening bundle validation.
- Explicit existing environment/secret-file settings are represented as host-managed connections with safe labels; their values are not exposed or overwritten by the UI. An owner can create a managed alternative and explicitly select it. Restarts do not reselect environment defaults over a persisted explicit selection. Incomplete host configuration reports its own recovery state, never a fallback. Existing persisted profiles/bundles survive migration; a prior implicit default is not evidence of consent to new network work.

#### Secret ingress, storage, and egress

- The form accepts a base URL and optional API key through a bounded authenticated request body with session, CSRF, same-origin checks, private admin topology, and `Cache-Control: no-store`. Provider requests originate only on the server. Production admin transport uses HTTPS or the established protected private tunnel; the direct loopback exception retains its strict checks.
- Keys are write-only. The UI may show/hide only a newly typed value; responses show `key_configured` rather than key suffixes/fingerprints. No secret or private URL enters Web Storage, service-worker caches, URLs, telemetry, logs, public YAML, bundles, exports, errors, or snapshots. Clear typed keys after submission, cancellation, logout, session expiry, or form teardown. Backend validation must not echo invalid input bodies.
- Persist managed keys through a vetted authenticated-encryption library with a host-protected key separate from the database, or an equivalent supported OS secret store. No plaintext credential table or home-grown cryptography is allowed. Secret storage failure leaves existing state intact and returns an actionable unavailable state; it cannot downgrade to plaintext or create a new registration prerequisite.
- Endpoints and secret references are private server state. Read responses expose a display name, provider, server-issued ID/revision, configured booleans, safe model labels, and status only. Editing an endpoint uses explicit replacement input; the server does not return the prior private URL. Retain/replace/remove key intent must be distinguishable; a blank field cannot silently delete a stored key.
- Changing protocol or destination invalidates the candidate's tests and requires a fresh explicit credential choice. A retained key MUST NOT be sent to a changed destination. Active and in-flight work retain their previous immutable connection/profile revision until an explicit verified switch; unrelated profiles sharing a connection must not be silently changed.
- Accept only structurally validated HTTP(S) service endpoints, reject userinfo/query/fragment and unsafe paths, and use fixed protocol operations. Public API services require HTTPS. Private/loopback provider access is explicit and constrained by host egress policy; prohibit link-local/metadata/multicast/unspecified destinations and public-to-private DNS rebinding. Resolve and validate addresses at connection time and prevent redirect-based credential forwarding. This is not a generic proxy or downloader.
- Secret rotation, backup/restore, missing encryption keys, storage permissions, atomic updates, reference cleanup, and rollback MUST be tested. GitHub public-read credentials remain retired; provider-key storage cannot reuse OAuth/PAT tables, names, or authority. Existing writeback/authentication boundaries are unchanged.

#### Profile lifecycle and novice workflow

- Present two independent purposes: `回答模型 / Chat model` and `搜尋模型 / Search model`. Each starts at service choice, then connection/model input, explicit test, review, and explicit use. Back/Edit preserves unrelated public drafts and saved choices; cancelling does not activate a candidate. Figma artifacts are not a prerequisite.
- The primary form contains service type, API address, optional key, and model name. Dimensions, prefixes, connection IDs, and raw diagnostic codes belong to an optional advanced view. Unknown dimensions remain unknown until sampled; arbitrary numeric placeholders cannot be used to satisfy a required database column.
- Saving a candidate does not activate it. Chat switches after its capability test, with in-flight requests retaining the old revision; it does not itself require an embedding reindex. Chat-model changes invalidate incompatible analysis-result caches. Embedding changes retain the existing probe/reindex/verify/smoke/atomic-switch rule and last-known-good bundle. Zero active profiles is valid during setup; at most one is active per role, and a ready role has exactly one.
- A successful connection test, an installed model, a ready search index, and a published portfolio are distinct outcomes. Embedding candidates can request reindex without first pretending to be `ready`. A private provider unreachable from the chosen index builder must yield a publishing-specific recovery state; do not expose the provider publicly or change topology automatically.
- Primary states use localized descriptions and a next action: unconfigured, testing, available for use, building search index, currently in use, or failed. Show retry/edit and manual continuation when appropriate; a raw `probe_failed`/`EMBEDDING_PROBE_FAILED` alone is insufficient. Configuration/test errors preserve non-secret fields and unrelated repository work.
- Admin layout is a restrained workspace with clear navigation, aligned fields, readable state/action grouping, and responsive wrapping. The model catalog is contextual to its selected provider. Normal onboarding must not be preceded by an always-expanded technical model panel. Meet WCAG 2.2 AA, keyboard/focus/status announcements, both locales, reduced motion, and no overlap/content loss at 375/768/1024/1440 pixels and 200% zoom.
- Ollama curated pull/progress/cancel/delete stays explicit and provider-owned; connecting an existing model is not restricted to the download catalog. Generic APIs/vLLM have no download button. RepoNPC-managed GGUF/Hugging Face execution/download remains unapproved future work, requiring a separate runtime, hardware, licensing, artifact-integrity, isolation, and distribution decision.

### 11.6 Model-first guided onboarding (0.2.3)

This section supersedes section 11.4's first-run sequence and section 11.5's insufficient separation of analysis selection from public activation. It preserves authenticated write-only model setup, explicit repository consent, optional/manual authoring, bilingual validation, and the existing publication topology. A profile being selected for analysis does not set its public `active` flag or mark its public search index ready.

#### User journey

Welcome explains the outcome and offers **Set up AI and begin** and **Build manually first**. It is not counted as a completed step. The AI route has exactly six primary steps:

1. **Set up AI models:** configure `分析與回答模型 / Analysis and chat model`, then `搜尋模型 / Search model`. Each exposes service, API base URL, optional write-only key, editable model ID, explicit test, and explicit selection. A saved connection can be deliberately shared, but the two capabilities must be tested independently. Successful tests do not implicitly select models or start analysis. The step completes only when both tested revisions are selected; an existing valid selection is reusable without re-entering stored secrets.
2. **Choose projects:** discover public metadata, select repositories, and confirm the exact set. No source or model request is caused by listing or confirmation alone. The first-run AI path reaches this step after model setup; manual discovery and returning-owner selection editing remain available without models.
3. **Analyze projects:** summarize confirmed projects and the selected models. One primary **Start analysis** action orchestrates bounded preflight and durable batch creation under that explicit consent. Do not require users to operate a separate “prepare batch” control. Recheck prerequisites before upstream work; if the plan/selection/model identity changes or another batch exists, stop and reconcile before generation. Opening or returning to the page never starts/retries analysis. Show per-project progress, partial success, retry/cancel/recovery, and manual continuation. Internal cache/stage diagnostics remain secondary; durable batch controls are not removed from the API.
4. **Confirm my contribution:** distinguish observed repository facts, AI inferences, and owner-authored/confirmed contribution. Only explicit confirmation can turn proposed personal claims into public configuration. Missing analysis results permit manual entry.
5. **Complete basic information:** author the existing name, biography, greeting, and required bilingual fields. This amendment does not weaken schema-v1 or locale completeness rules or redesign character assets.
6. **Preview and complete draft:** validate/preview without model or publication side effects, edit, copy/download, and report publication prerequisites. Draft completion, GitHub save, workflow dispatch, index validation/activation, and public availability remain separate outcomes/actions. A missing writeback credential or published bundle cannot prevent a valid local draft.

The manual route skips model setup and analysis, proceeding through project selection, contribution, profile, and preview/draft. Its progress indicator counts only its four applicable steps; skipped AI work is not marked passed. Switching to AI at any point opens the missing model setup with a return destination and preserves the existing public draft. Model settings must be reachable directly in guided mode and from contextual recovery, not only through raw-YAML/advanced mode. Small viewports show the current step and count with an accessible expandable step list; the desktop indicator must wrap without clipping or presenting completion percentages as work estimates.

#### Analysis dependencies and public activation

- Analysis readiness is a server-owned capability for the selected chat/embedding revisions and required runtime storage/admission controls. It MUST NOT be derived solely from `/api/public/status.model.ready`, `/readyz`, a public `active` flag, model listing, or a browser-persisted boolean. A fresh live test is explicit; metadata reads do not generate probe traffic. A prior successful test is invalidated by relevant configuration/revision changes and never guarantees future upstream availability.
- Both models are required by the current analysis algorithm: passage/query embeddings and retrieval precede chat generation. This amendment does not introduce chat-only analysis or lexical fallback. Manual work requires neither model.
- Persist only the selected analysis references and safe validation metadata in deployment-local runtime state; resolve credentials through the existing protected connection boundary. Analysis selection is logically distinct from public active profiles and must not modify public bundle pointers. An embedding candidate can be tested and explicitly selected for analysis while awaiting its first public index. Selection itself performs no reindex, source download, generation, GitHub write, or publication.
- The clean bootstrap path MUST construct usable analysis dependencies after model selection even when the process started without providers. Public service assembly/reindex preparation MUST NOT require an already-working public model pair merely to prepare its first candidate. Restart is not the normal transition from saved settings to usable analysis.
- Preflight and batch acceptance bind the confirmed repository identity and selected connection/profile revisions, including complete embedding semantics and chat model identity. Work admitted under one pair retains that pair, or stops safely if it cannot be resolved; it cannot silently resolve the latest selection mid-item. Use existing bounded retention and interruption-confirmation rules. Changes invalidate incompatible plans/cache reuse; valid old results may remain labeled with their source/model identity, but are never presented as fresh results from the new pair. Owner-confirmed text is preserved.
- Public readiness remains stricter: a compatible verified bundle, public model selections, storage and provider availability must pass the existing validation/smoke/atomic-switch requirements. Analysis's ephemeral derived index is not a published portfolio bundle. A successful analysis must not publish or activate it. Existing last-known-good public service remains unchanged while a different analysis pair is configured/tested/used.

#### Recovery, compatibility, and implementation contract preparation

- Distinguish missing configuration, saved-but-untested, tested-but-unselected, unavailable selected service, missing public index, and publication-only blockers. Explain the missing role and offer **Set up search model**, **Test model**, **Select model**, **Retry**, or the relevant concrete action; do not label a clean unconfigured deployment “Ollama unavailable.”
- Contextual model editing records a safe return destination. Success/cancel returns to preserved work; cancellation does not change saved selection, and typed secrets clear under section 11.5. Completed configuration refreshes safe capability state without implicitly resubmitting analysis. Active jobs retain their frozen pair; navigation cannot duplicate or silently cancel them.
- Migrate old `reponpc.guided-onboarding.v1` / guided-draft state conservatively: retain allowed public selection/profile/contribution fields, reconcile batches with the server, and treat browser readiness as untrusted. An old analysis-stage resume with missing models shows direct setup recovery instead of requesting a destructive reset. Existing completed drafts remain editable/exportable without repeating AI steps. Unmappable advanced YAML remains intact in advanced mode. This does not approve durable server-side portfolio drafts.
- The authenticated additive analysis-selection contract is `GET /api/admin/analysis-selection` and `PUT`/`POST` on that path. The write body is exactly `chat_profile_id`, `embedding_profile_id`, and optional optimistic `expected_generation`; it requires the existing same-origin session and CSRF boundary. The no-store read view contains only role profile IDs, connection revisions, safe model IDs/status/test state, selection generation, eligibility, and a stable safe reason. It never returns endpoint, key, secret reference, provider body, or a public-readiness proxy. Invalid roles return `404`; unprobed roles and stale generation return `409`; unavailable selection service returns `503`.
- Runtime SQLite retains the current explicit selection separately from public active profiles, and each accepted batch retains one secret-free pair snapshot: selection generation; each profile/connection ID and connection revision; chat provider/model identity; and complete embedding provider/identity semantics. The preflight plan and batch creation must agree on that snapshot or return `ANALYSIS_PLAN_STALE`. Cache keys derive from the frozen embedding/chat identities. An in-flight/recovered item resolves only its persisted connection revisions through the protected store; missing/deleted/rekeyed material fails safely as `MODEL_UNAVAILABLE`, never by resolving the latest selection or falling back. Existing batches created before this snapshot migration also fail safely rather than retarget.
- Guided browser-state migration remains conservative: only serializable route/return/public-draft state is retained; model capability, secrets, and analysis readiness remain server-owned. Prefer existing registries/batch mechanisms; do not change legacy endpoint behavior or public schemas silently. Broader trust, topology, algorithm, scope, or validation changes still require a new owner decision.

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

External adapters MUST expose the identity, `embed_query`, `embed_passages`, and health behavior needed by both the index builder and runtime. The local adapter may implement this contract only in isolated benchmark/build fixtures; it is not a supported production runtime. Provider health, profile probing, and retry orchestration MUST consume this same contract rather than redefine it.

### 13.3 Required adapters and fallback rule

- `openai_compatible`: configurable base URL, key secret, chat model, embedding model, timeout, and optional headers from server-only secrets.
- `vllm`: named preset using the `openai_compatible` transport and embedding identity. It MAY use an explicitly configured private HTTP origin. Chat and embedding have independent base URL/model/key settings because a chat model does not imply `/v1/embeddings` capability. Model listing assists selection; direct bounded capability testing of the typed model is authoritative under section 11.5. The operator remains responsible for a valid chat template and an embedding-capable embedding model.
- `ollama`: private base URL, chat model, embedding model, explicit context/output caps, and health endpoint.
- A local sentence-transformers adapter MAY remain as an optional isolated benchmark dependency, but MUST NOT be advertised as the default or required for a production image. Production readiness requires one explicitly configured external profile from Ollama, vLLM, or a generic OpenAI-compatible embeddings service.

The selected chat and embedding adapters are explicit. RepoNPC MUST NOT silently try another provider, model, or cloud endpoint after failure. Provider keys and private base URLs remain protected server state after the narrowly authorized admin input described in section 11.5. They MUST NOT enter public/admin responses, logs, exports, or snapshots. Tests use synthetic canaries only.

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

`public/profile.json` uses the internal bilingual schema in section 9.1. The archive verifier MUST validate that complete schema, including both required locales and all required profile/repository/question/character/index fields, before a candidate can activate.

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
  "embedding": {"adapter": "ollama", "model_id": "qwen3-embedding:0.6b", "dimension": 1024, "normalized": true, "query_prefix": "", "passage_prefix": ""},
  "statistics": {"repositories": 1, "sources": 100, "evidence_records": 500},
  "files": [{"path": "index.sqlite", "size": 123, "sha256": "64hex"}]
}
```

The embedding values in this example are illustrative for an Ollama Qwen3 profile; the builder MUST replace dimension/prefix values with the observed probe result and MUST reject a guessed or mismatched identity.

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

- `admin_owner`: the sole durable username, Argon2id password hash, and creation time;
- `admin_auth_methods`: one local-password method and/or one unique GitHub numeric identity for the singleton owner, with safe display login metadata;
- `admin_oauth_transactions`: hashed state, encrypted PKCE verifier/setup proof where applicable, bounded intent, expiry, consumption time, and fixed return path;
- `admin_github_credentials`: authenticated-encryption nonce/ciphertext, algorithm/key version, purpose, GitHub user ID/display login, expiry, validation time, and safe status only;
- `admin_setup`: at most one SHA-256 setup-code digest and its creation/expiry times; deleted when consumed;
- `embedding_profiles`: deployment-local profile ID, provider/model labels, encrypted credential reference, private endpoint reference, observed compatibility identity, active/status state, reindex generation, and timestamps; never plaintext credentials or raw provider bodies;
- 0.2.2 adds protected model-connection revisions and independent chat-profile metadata alongside the existing embedding registry. Physical tables, migration numbers, and request DTOs must be documented in the implementation contract preparation step; no schema is implemented by this document update. Secrets are protected as specified in section 11.5 and never placed in the immutable index.
- `admin_sessions`: token hash, CSRF hash, created/seen/idle/absolute expiry, session epoch, revoked time;
- `rate_buckets`: HMAC-derived IP key, window/bucket counters and expiry;
- `daily_usage`: UTC date, accepted requests, reported input/output tokens and estimated cost where configured;
- `bundle_state`: active/previous/pinned IDs, ETags, checks and safe update error;
- `admin_audit`: timestamp, action, target path, result commit, request ID, outcome.
- `github_rate_state`: sanitized anonymous REST/core remaining, reset, retry, and secondary-limit admission state; it contains no token or upstream response body;
- `analysis_batches`, `analysis_batch_items`, and `analysis_batch_events`: owner-scoped durable job state, immutable commits, bounded safe events, validated terminal result metadata, idempotency keys, and TTL expiry;
- `analysis_cache_entries`: checksummed derived-index and validated-analysis cache metadata, identity keys, size/LRU metadata, and expiry only; raw archives, repository bodies, prompts, and provider bodies are excluded.

Raw session/CSRF tokens, raw IPs, raw provider credentials, and raw model/download bodies are never stored. IP keys use HMAC-SHA-256 with `REPONPC_IP_HASH_KEY`. Expired profile, probe, and reindex metadata are periodically removed while the active/previous bundle retention policy remains intact.

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

### 15.4 GitHub analysis admission and durable work (0.1.7)

- GitHub public analysis performs bounded unauthenticated REST metadata requests for the explicitly selected repositories, then a single immutable-SHA archive request per cache miss. It never resolves trees/blobs one by one in the batch path.
- Archive downloads stream into an item-unique staging directory. Compressed bytes, expanded bytes, regular-file count, individual file bytes, elapsed time, path normalization, duplicate paths, symbolic/hard links, devices, and cancellation are bounded before content reaches the existing filter/index pipeline.
- The central rate state maintains the anonymous REST/core primary budget plus a shared secondary-limit pause, leaves a documented safety reserve, honors `Retry-After` and reset timestamps, and does not poll `/rate_limit` or busy-loop while paused. Initial GitHub in-flight concurrency is one and hard-capped at two total requests.
- The initial scheduler limits whole work items to four, archive staging to one (hard maximum two after measured evidence), local filter/index to two, and GitHub API to two. Provider permits wrap only actual embedding/generation calls. A weighted fair scheduler reserves provider opportunities for public chat before `admin_single` and `admin_batch` work can consume all capacity.
- The active-execution deadline for one repository is 120 seconds. Queueing, owner pause, and rate-reset waiting do not spend it. Cancellation/restart propagates to every stage; uninterruptible upstream output is discarded; every terminal/recovery path removes staging.
- Batch snapshots/events and validated terminal results expire after 24 hours. Startup recovery requeues only immutable fetch/index work or verified cache work. Any item interrupted after provider generation dispatch becomes `needs_retry_confirmation` and is never automatically resubmitted.

### 15.5 Private administration topology and operations CLI (0.1.9, amended by 0.2.0)

- The application MUST keep the admin-capable listener on loopback or a private interface by default. A reverse proxy MAY publish `/`, static assets, and `/api/public/*`, but MUST deny `/admin` and `/api/admin/*` from public Internet networks unless the operator explicitly places those routes behind a private VPN/allowlist.
- A non-standard TCP port is not an access control and MUST NOT be presented as the security solution. The documented headless flow is `ssh -N -L <local-port>:127.0.0.1:<remote-port> user@host`, then opening the same-origin Web Admin at the local end. Tailscale/WireGuard or a firewall-restricted LAN listener are supported alternatives.
- The bounded host CLI MUST expose loopback launch (`admin launch-token`), production bootstrap/recovery (`admin setup-code`, `admin set-password`), runtime (`runtime check`, `runtime backup <path>`), and bundle (`bundle status`, `bundle verify <id>`, `bundle pin <id>`, `bundle unpin`) commands. It MUST use explicit paths/IDs, stable safe errors, and atomic/consistent operations. It MUST NOT become a second public management protocol.

## 16. Frontend behavior

- The visitor route defaults to `/`; admin routes are below `/admin` and are not advertised publicly.
- The UI renders profile and chat as semantic DOM. Canvas MAY render decorative scene elements but MUST NOT contain the only accessible content.
- Character states map to lifecycle: idle before input, listen while input is active, think during retrieval/provider wait, talk while validated tokens render, success on completion, offline on unavailable/error.
- Suggested questions are keyboard-operable buttons and remain editable before submission.
- Citation markers focus/scroll to a citation panel and links open immutable GitHub pages with safe `rel` attributes.
- Locale switching changes UI/profile fields and sends the selected locale with chat. It does not discard the visible conversation.
- Offline/setup/model unavailable states explain what visitors can still view and do not expose admin diagnostics.
- Once the backend has validated an answer and begun emitting SSE token events, the visitor UI MUST append those events progressively rather than buffering the complete SSE stream. Chat/profile failures expose a retry or status-recheck action with predictable focus, and citation rendering includes the safe evidence class and source location supplied by the server.
- The admin UI is code-split from the visitor application and clears in-memory CSRF/config drafts on logout.
- Disabled or unavailable admin primary actions MUST have a programmatically associated visible reason, recovery action, and unaffected local alternative where one exists. GitHub read, writeback, publication, and model-analysis readiness are independent capabilities; none may disable unrelated validation, preview, manual authoring, copy, or download.
- No GitHub OAuth or public-read PAT control appears before or after an admin session. Anonymous GitHub rate/capacity messages are contextual to discovery or analysis, bilingual, keyboard/screen-reader accessible, and include manual continuation without a credential prompt.
- Provider-neutral chat/search setup follows section 11.5, and the model-first/manual guided order follows section 11.6. Model secrets use an isolated write-only form, never the guided public draft or raw YAML editor. Empty model configuration does not prevent access to the manual path.
- `docs/SPRITE_FORMAT.md` MUST provide the exact grid diagram, state table, frame timing guidance, examples, validation errors, reduced-motion behavior, and an MIT-compatible template asset.

## 17. Edge cases and required behavior

| Condition | Required behavior |
| --- | --- |
| No active bundle on first boot | Public setup state; profile/chat `503 INDEX_UNAVAILABLE`; health alive, readiness false. |
| No active external embedding profile | Admin shows setup-required/model-center state; semantic chat returns `503 MODEL_UNAVAILABLE` or `INDEX_UNAVAILABLE` per bundle state; local/manual configuration and profile CRUD remain available. No local adapter or silent fallback is selected. |
| Embedding profile changed or probe/reindex fails | Keep the last-known-good profile/bundle active; expose `reindex_required`/safe failure and an explicit retry/recheck action. Never activate a dimension/prefix/model mismatch. |
| Ollama model missing/pull fails | Show provider-native install/pull error and retain other local admin functions; do not fetch an arbitrary URL or silently switch model/provider. |
| No admin owner on first loopback boot | The launcher mints a two-minute fragment-only grant after readiness; `/admin` exchanges it atomically without a registration form. A direct visit explains how to relaunch. |
| Local-launch grant expired, replayed, forwarded, or non-loopback | Generic `401 LOCAL_LAUNCH_DENIED`; mint a new grant through the local launcher. No owner/session is partially created and no failed value is logged. |
| No production admin owner | `/admin` explains the host `setup-code` step; no visitor can register without the 256-bit code. |
| Production setup code expired or reissued | Generic `401 SETUP_DENIED`; generate a new host code. No owner/session is partially created. |
| Legacy OAuth/PAT route is requested | Return non-mutating `410 GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED`; do not redirect, accept/decrypt credentials, issue a session, or change owner/setup state. |
| Concurrent first-owner submissions | One transaction creates exactly one owner/session; the loser receives `409 SETUP_ALREADY_COMPLETE`. |
| Active index but chat model down | Profile/card remain available; status degraded; chat `503 MODEL_UNAVAILABLE`; no provider fallback. |
| Model unavailable before guided analysis | Preserve selection and owner text; offer immediate manual contribution without requiring preflight, batch creation, or a failed model call. |
| AI route chosen with one or both analysis roles missing | Stay in or return to guided model setup, identify the missing role and offer its direct action plus manual continuation. Do not call source/provider work or label a clean deployment as an Ollama failure. |
| Analysis pair selected before the first public bundle | Permit explicit authenticated selected-only analysis in the same process, while `/readyz` and public chat remain unavailable until separate compatible bundle/public activation succeeds. Analysis must not publish its temporary index. |
| Anonymous GitHub REST capacity unavailable | Keep all local/manual draft functions available, report a sanitized retry time when known, and never offer or select OAuth/PAT/writeback fallback. |
| No GitHub writeback or publication capability | Validate, preview, copy, and download remain available; Save/Publish explains the missing capability and its setup/recovery action. |
| Admin requested through public Internet | Reverse proxy/firewall denies `/admin` and `/api/admin`; operator is directed to loopback/SSH/VPN. A non-standard port does not bypass this rule. |
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

For Phase 2 source classification, the exact root manifests `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, and `requirements.txt` are `repository_metadata`. They remain line-addressable `REPOSITORY_FACT` records at the real repository path/commit and use the configured `repository_metadata` retrieval weight. Owner-authored profile, role, summary, and claim text remains `OWNER_ASSERTION` even when it describes a repository. An empty repository is allowed to retain any available repository metadata or owner assertions, but publication still fails when total evidence is zero.

## 18. Explicit v1 exclusions

Private repositories, multi-owner/multi-tenant operation, billing, visitor authentication, OAuth device flow, GitHub-only owner setup, model fine-tuning, autonomous tools, live repository mutation by the model, arbitrary URL/model-archive ingestion, multiple NPCs, navigable worlds, keyboard gameplay, mobile-native apps, externally hosted frontend origins by default, distributed replicas, and a separate vector/database service are outside v1.

## 19. Implementation and release gates

Work follows `IMPLEMENTATION_PLAN.md`, but a milestone is complete only when its mapped acceptance criteria pass. Before v1 release:

- every FR and NFR has at least one automated or documented acceptance result;
- retrieval and bilingual evaluation thresholds pass on a committed, non-secret fixture corpus;
- Phase 2 formal retrieval acceptance runs a candidate container with only the repository fixture, public questions, and production embedding configuration; the reviewed oracle and scoring remain outside the container;
- Docker inspection proves the candidate has no oracle mount or readable oracle path, runs with `--cpus=4 --memory=8g`, and records the image digest, runtime/host provenance, warm-up policy, and raw timing samples;
- formal benchmark booleans are derived from observed provider identity, isolation/resource evidence, repeatability, and thresholds rather than accepted from caller/candidate flags;
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
**Latest amendment:** Technical Specification 0.2.3 / ENGD-011 / ADR-030 approved 2026-09-10 for sections 2.9 and 11.6. The owner explicitly confirmed the reviewed model-first flow and analysis/public-activation separation. This amendment is a documentation handoff; its implementation and acceptance remain pending. Local GGUF/Hugging Face runtime and Figma are outside this package.
**Approved on:** 2026-08-10; Phase 2 closure amendment approved 2026-08-11; first-owner onboarding, personal-deployment convenience, and guided-onboarding amendments approved 2026-08-14; vLLM provider-preset amendment approved 2026-08-15; GitHub identity/connection and bounded batch-analysis amendments approved 2026-08-16; OAuth setup-guidance UX and ENGD-001/002/003/006 amendments approved 2026-08-30; passwordless loopback launch and connection-only GitHub amendment approved 2026-09-04; GitHub OAuth/public-read PAT retirement approved 2026-09-08; provider-neutral model setup approved 2026-09-09; model-first guided workflow approved 2026-09-10
**Approval scope:** Technical Specification 0.1.0 and OR-001 through OR-007, version 0.1.1 Phase 2 closure decisions recorded in ADR-015, version 0.1.2 first-owner onboarding recorded in OR-008/ADR-016, version 0.1.3 loopback local-launcher defaults recorded in OR-009/ADR-017, version 0.1.4 guided onboarding recorded in OR-010/ADR-018, version 0.1.5 vLLM provider preset recorded in OR-011/ADR-019, historical version 0.1.6 GitHub identity/public-read connection recorded in OR-012/ADR-020, version 0.1.7 immutable public-repository resolver and durable batch analysis authorized by the owner on 2026-08-16 and recorded in ADR-021, historical version 0.1.8 OAuth setup-guidance UX recorded in ADR-022, version 0.1.9 external embedding profiles, deployment-aware password/private admin topology, local-first recovery, and bounded operations CLI recorded in ADR-023 through ADR-026, version 0.2.0 passwordless loopback launch plus connection-only GitHub recorded in ENGD-008/ADR-027, and version 0.2.1 OAuth/public-read PAT retirement plus anonymous REST resolution recorded in ENGD-009/ADR-028. The owner requested an MVP delivery phase; this is a sequencing decision and does not reduce the complete v1 scope except for the explicitly retired OAuth/public-read PAT capability.

# RepoNPC Architecture Decision Log

**Document status:** ADR-001 through ADR-026 accepted (ADR-023 through ADR-026 approved 2026-08-30)
**Approval rule:** These records were accepted together when the project owner approved `TECHNICAL_SPEC.md` 0.1.0. A later incompatible change requires a new ADR; do not silently rewrite an accepted decision.

## ADR-001: Use a modular monolith

- **Status:** Accepted
- **Decision:** The React application, FastAPI API, retrieval orchestration, provider adapters, admin service, bundle manager, and card renderer are modules in one deployable application image. The indexer is a CLI from the same Python package and runs in GitHub Actions.
- **Why:** One-owner self-hosting benefits from a single release, shared schemas, and low operational overhead. Module boundaries preserve the option to split services later.
- **Consequences:** Internal interfaces must remain explicit. CPU-heavy indexing does not run in the public web process.

## ADR-002: Separate the GitHub card from the interactive site

- **Status:** Accepted
- **Decision:** GitHub receives a script-free linked SVG/GIF card. All chat and interactive RPG behavior runs on an external RepoNPC deployment.
- **Why:** GitHub Markdown cannot execute the JavaScript required for a secure interactive application.
- **Consequences:** The card must communicate value without interaction, and deployment requires a public HTTPS URL.

## ADR-003: Use SQLite for bundle search and runtime state

- **Status:** Accepted
- **Decision:** Each immutable index contains one read-only SQLite database with FTS5 tables and vector blobs. Mutable sessions, revocations, rate counters, update status, and audit records live in a separate runtime SQLite database on a persistent volume.
- **Why:** SQLite is portable, inspectable, supports atomic replacement and FTS5, and avoids operating a database server for a single portfolio.
- **Consequences:** Runtime state must never be written into an index bundle. Multi-replica deployment is outside v1 unless operators provide affinity and an external rate-limit store.

## ADR-004: Store normalized float vectors as blobs and rank them in process

- **Status:** Accepted
- **Decision:** Embeddings are normalized `float32` arrays stored with their dimension and model ID. At load time they are read into NumPy; query similarity uses an in-process matrix product. RRF is implemented in Python.
- **Why:** The expected curated corpus is small enough for brute-force vector search and does not justify a vector server or platform-specific SQLite extension.
- **Consequences:** The corpus has explicit chunk/vector limits. A future approximate index requires a new bundle schema and ADR.

## ADR-005: Publish immutable bundles through GitHub Releases

- **Status:** Accepted
- **Decision:** GitHub Actions publishes a versioned `tar.zst` bundle as a GitHub Release asset. A stable manifest on the dedicated `reponpc-index` branch points to the active release asset and its checksum.
- **Why:** Readers need a stable discovery URL while citations and bundle contents remain immutable.
- **Consequences:** Publication writes the immutable asset before changing the stable manifest. Runtime activation is checksum-verified and atomic, with rollback to the last known-good bundle.

## ADR-006: Abstract both chat and embedding providers

- **Status:** Accepted
- **Decision:** Model integrations implement RepoNPC-owned interfaces and declare capabilities. v1 includes OpenAI-compatible HTTP adapters and Ollama adapters. The index manifest records the exact embedding provider/model/dimension contract.
- **Why:** OpenAI-compatible servers and Ollama differ in endpoints, streaming, roles, structured output, context limits, and error behavior.
- **Consequences:** There is no silent provider fallback. An embedding mismatch makes a bundle not ready rather than producing corrupt ranking.

## ADR-007: Separate evidence classes and let the server own citations

- **Status:** Accepted
- **Decision:** All evidence is classified as `OWNER_ASSERTION`, `REPOSITORY_FACT`, or `MODEL_INFERENCE`. The model emits only evidence IDs. The backend validates IDs, enforces person-claim policy, and constructs immutable GitHub links.
- **Why:** Repository presence does not prove personal responsibility, and free-form model URLs are not trustworthy.
- **Consequences:** Owner claims need stable IDs in configuration. Unsupported person-level claims are rejected or qualified. Citation rendering never trusts model-supplied URLs.

## ADR-008: Use SVG with a static first frame and provide GIF fallback

- **Status:** Accepted
- **Decision:** The primary README card is a self-contained, script-free animated SVG whose first frame is complete. The service also renders a GIF compatibility asset and a static PNG preview.
- **Why:** SVG offers crisp themes and lightweight animation, while GitHub image caching and client behavior can suppress animation.
- **Consequences:** Card output is sanitized, contains no remote assets, has strict response headers, and is verified on a real GitHub Profile.

## ADR-009: Use single-admin password sessions and least-privilege GitHub writeback

- **Status:** Accepted
- **Decision:** v1 has one configured admin identity. The server verifies an Argon2id password hash and issues revocable, short-lived server-side sessions in secure cookies with CSRF protection. A fine-grained GitHub token may write only to the configured configuration repository, and the application allowlists `reponpc.yml` plus `assets/character/`.
- **Why:** GitHub OAuth adds unnecessary onboarding and permission complexity for a single-owner deployment.
- **Consequences:** The operator must generate a password hash and token, terminate HTTPS, protect runtime storage, and rotate credentials. The browser never receives the GitHub token.

## ADR-010: Keep public presentation configuration in Git

- **Status:** Accepted
- **Decision:** `reponpc.yml` and approved character assets are the source of truth. The admin UI edits them through GitHub's contents API using blob-SHA conflict detection; it does not maintain a competing configuration database.
- **Why:** Git provides reviewability, rollback, and a natural trigger for index rebuilding.
- **Consequences:** Concurrent edits return a conflict for manual resolution. Secrets are environment-only and cannot be written through the admin UI.

## ADR-011: Serve the built web application from FastAPI under one origin

- **Status:** Accepted
- **Decision:** The production image builds the Vite application and serves its static output with the FastAPI application. Public and admin APIs use the same origin. Broad CORS is disabled by default.
- **Why:** Same-origin deployment simplifies self-hosting, cookies, CSRF, headers, and documentation.
- **Consequences:** Development may use Vite proxying to FastAPI. A separately hosted frontend is unsupported unless the operator deliberately configures a narrow origin allowlist.

## ADR-012: Use pnpm and uv with locked dependencies

- **Status:** Accepted
- **Decision:** Frontend dependencies use pnpm and `pnpm-lock.yaml`; Python uses a PEP 621 `pyproject.toml`, uv, and `uv.lock`.
- **Why:** Both support reproducible, fast local and CI workflows.
- **Consequences:** Agents must update lockfiles in the same change as dependency declarations and may not introduce a second package manager.

## ADR-013: Validate the complete answer before streaming it publicly

- **Status:** Accepted
- **Decision:** RepoNPC buffers the provider's complete answer envelope, validates evidence IDs, person-claim rules, inferences, links, and Markdown, then emits the accepted text as SSE token chunks.
- **Why:** True pass-through token streaming can expose an invented citation or unsupported personal claim before the backend knows the complete structure and cannot retract it.
- **Consequences:** Time to first visible token includes the full provider generation. The UI still receives a streaming rendering contract and must show a thinking state during generation/validation. Future speculative streaming needs a new security design and ADR.

## ADR-014: Use one canonical 4-by-7 character sheet

- **Status:** Accepted
- **Decision:** Built-in composition and custom uploads both produce a transparent `128x224` PNG consisting of four `32x32` frames for each of seven ordered states: idle, walk, listen, think, talk, success, and offline.
- **Why:** One fixed format keeps animation, validation, card generation, preview, reduced motion, and custom assets interoperable.
- **Consequences:** Custom artists must follow the documented grid. Changing dimensions, rows, or state order is a versioned asset-contract change.

## ADR-015: Close Phase 2 with a build-time provider, bilingual bundle profile, and isolated benchmark

- **Status:** Accepted historically; the local adapter is no longer a supported production default. ADR-023 supersedes its default/profile language while retaining build-time benchmark fixtures where explicitly named.
- **Decision:** Delivery Phase 2 includes the production `local_sentence_transformers` adapter as an optional indexer dependency and an executable `reponpc` index CLI. No arguments and `serve` retain the existing application startup path. Concrete OpenAI-compatible/Ollama adapters and runtime query-provider health/readiness integration remain Phase 3. One internal `public/profile.json` stores exact `zh-TW` and `en` locale payloads while the public API response remains unchanged. Root repository manifests are line-addressable `REPOSITORY_FACT` records with source type `repository_metadata`. Formal Phase 2 retrieval acceptance runs the production adapter in a Docker candidate limited to four CPUs and 8 GiB; only public questions and repository fixtures enter that container, while the reviewed oracle and scoring remain with the host controller. The audited state at Git commit `83c3dd44f7cc2856dc3b61d9f637337f1a466d3e` is the closure attribution baseline, and prior failed delta evidence remains immutable history.
- **Why:** The earlier Phase 2 implementation proved retrieval and bundle primitives but could not truthfully close the real workflow: the installed console entrypoint did not expose workflow commands, no production embedding adapter existed, the public route ignored locale selection, the producer emitted no `repository_metadata`, and the benchmark used a fixture provider with a readable oracle and unverified host limits.
- **Consequences:** Main owns the CLI, dependency/lockfile, provider contract, profile producer/verifier/route, index producer, publication-last split, benchmark controller, and all integration decisions. A bounded worker may implement only the frozen local adapter leaf. The normal runtime image is not bloated by the Phase 2 indexer dependency. A bundle missing either locale fails verification. `index publish` cannot update the remote stable pointer; only `index publish-manifest` can do so after immutable verification. Formal acceptance is derived from Docker inspection, access probes, provider identity, repeatability, measured thresholds, and recorded provenance rather than caller-supplied flags.

## ADR-016: Bootstrap the first owner with a host-issued one-time code

- **Status:** Accepted
- **Supersedes:** ADR-009 only for how the single configured owner is initially provisioned; its session, CSRF, Argon2id, and least-privilege writeback controls remain in force.
- **Decision:** New deployments ship with no default username or password. A host-only CLI creates a random 256-bit, 15-minute, one-time setup code and persists only its SHA-256 digest. The same-origin admin UI exchanges that code with an owner-chosen username and password; SQLite atomically creates the sole owner with an Argon2id hash, consumes the code, and creates the initial session. Reissuing invalidates an unused code, and durable owner creation permanently closes the setup API. Explicit environment username/hash pre-provisioning remains supported and also closes setup. GitHub credentials gate only GitHub-backed operations, not authentication.
- **Why:** A local self-hosted product needs a usable path to create credentials without a universal default or requiring every operator to construct a PHC hash before reaching the UI. Proof from the deployment host prevents the first Internet visitor from claiming an uninitialized instance.
- **Consequences:** Runtime backups contain the sole owner hash and are required for credential continuity. The setup status API exposes only safe booleans. Code expiry, replacement, one-time use, concurrent setup, restart durability, origin enforcement, secret absence, and legacy pre-provisioning require regression tests. Dynamic-owner password change/recovery is not added by this decision and needs a future owner-approved contract if required.

## ADR-017: Prefer personal-deployment convenience for local onboarding (partially superseded by ADR-024)

- **Status:** Accepted for explicit loopback evaluation only; production password scope superseded by ADR-024.
- **Decision:** First-owner passwords in the explicit loopback evaluation profile require 4–128 characters and confirmation, with no character-class composition rules. Argon2id, the host-issued setup code, login backoff, and session controls remain unchanged. The Windows one-click launcher defaults to loopback port 8090, still honors `REPONPC_PORT` and `-Port`, and does not change the production container's port 8000 contract. Any production/non-loopback admin surface follows ADR-024.
- **Why:** RepoNPC is normally a single-owner application deployed on the owner's own computer. A 12-character minimum and a commonly occupied development port added friction without materially improving the stronger host-proof, local-only binding, hash, and session boundaries already in place.
- **Consequences:** The loopback UI/API/service validation retain the four-character convenience. A non-loopback deployment must not reuse that boundary; its minimum and blocklist are defined by ADR-024. Local launcher examples use 8090; production and explicit port overrides remain backward compatible.

## ADR-018: Guide repository onboarding while preserving explicit trust boundaries

- **Status:** Accepted on 2026-08-14.
- **Lifecycle amendment:** ADR-021 supersedes the synchronous/ephemeral execution lifecycle below with the durable batch and one-item compatibility-adapter lifecycle. The selected-only trust boundary, owner-confirmation rule, optional local export, and no-fallback behavior remain accepted.
- **Decision:** Make guided onboarding the default authenticated admin experience and raw YAML an advanced mode. Discover public GitHub metadata without OAuth or the writeback token, require checkbox confirmation before source access, analyze one selected repository per synchronous ephemeral request, reuse the production indexing/provider/evidence boundaries, and require explicit owner confirmation before model suggestions become schema-v1 role/summary/claims. Permit local copy/download without GitHub writeback.
- **Why:** A new owner should understand what RepoNPC produces and choose repositories without learning YAML first. Repository understanding can be automated; personal attribution cannot be proven from source and must remain owner-confirmed.
- **Consequences:** Main owns five new authenticated onboarding endpoints, GitHub metadata pagination/rate-limit behavior, the 120-second analysis lifecycle and cleanup, provider-cost/cancellation behavior, evidence review, session-only browser resume, and guided-to-YAML generation. The existing fine-grained GitHub token permissions, configuration schema version, role/summary assertion semantics, preview no-model rule, publication flow, and no-fallback policy do not change. This decision adds FR-025 through FR-028 and AC-038 through AC-040.

## ADR-019: Treat vLLM as a named OpenAI-compatible deployment preset

- **Status:** Accepted on 2026-08-15.
- **Decision:** Accept `vllm` in server-side chat and embedding environment configuration, then reuse the existing OpenAI-compatible model-list, chat-completions, and embeddings adapters. Permit only explicitly configured private HTTP origins for this preset. Normalize its embedding identity and existing public status provider value to `openai_compatible`, while keeping chat and embedding URL/model/key settings independent and verifying the selected model in each server's model catalog.
- **Why:** vLLM implements an OpenAI-compatible server, so a third transport would duplicate parsing and error behavior. The preset still needs an explicit private-network policy and operator guidance because common self-hosted vLLM deployments do not terminate HTTPS themselves.
- **Consequences:** Bundle schema version 1, browser APIs, the existing public provider enum, secret persistence, and fallback rules do not change. Operators must serve a chat-template-capable chat model and a separate embedding-capable model/server when embeddings are required. Raw keys and private URLs remain server-only and are excluded from responses, object representations, logs, fixtures, and snapshots.

## ADR-020: Add GitHub OAuth identity without broadening ownership or writeback (partially superseded by ADR-025)

- **Status:** Accepted on 2026-08-16.
- **Supersedes:** ADR-009/ADR-016 only where they require password-only authentication, and ADR-018 only where it excludes OAuth/public-read credentials. The GitHub-only first-owner/recovery clause is superseded by ADR-025.
- **Decision:** GitHub OAuth Web Application Flow with PKCE is an alternative authentication method for the sole RepoNPC owner. Setup still requires the host-issued code followed by local username/password creation; an authenticated local owner may then link GitHub. Login/link use distinct one-time transactions; the GitHub numeric user ID is the stable link. OAuth requests no repository scope, supports public-read only, and its encrypted credential is never reused for writeback. Explicit fine-grained PAT public-read credentials are a non-login fallback. Writeback remains the configured separate fine-grained credential.
- **Why:** The owner needs a familiar sign-in and a safe public-read connection without creating open registration, multi-user accounts, or broader repository permissions.
- **Consequences:** Runtime schema adds authentication methods, encrypted credentials, and OAuth transactions. Password/pre-provisioned login remains compatible and is always retained as break-glass recovery; removal of the local method is rejected. Later GraphQL/archive and durable batch work are explicitly outside this amendment.

## ADR-021: Resolve selected public repositories through immutable archives and durable batches

- **Status:** Accepted on 2026-08-16.
- **Decision:** Guided multi-repository analysis uses a central, rate-aware GraphQL metadata resolver plus one exact-commit archive per cache miss. It creates at most one owner-scoped durable batch whose items advance through independently bounded stages and publish safe replayable events. OAuth/PAT public-read credentials are selected explicitly and never fall back; the writeback credential is unavailable to analysis. Validated index/result caches use complete immutable identity keys. The legacy one-repository route remains a batch compatibility adapter.
- **Why:** Per-blob REST resolution is rate-expensive and branch references can drift. Browser-controlled serial work cannot survive reloads, enforce server capacity fairly, or preserve the boundary between safe durable status and ephemeral untrusted source/model data.
- **Consequences:** Runtime SQLite gains rate, batch, event, and cache metadata. The scheduler must cap GitHub/archive/local/provider stages and reserve provider opportunities for public chat. Exact-SHA archive validation, 24-hour bounded batch result retention, explicit retry after dispatched generation interruption, restart cleanup, API/SSE contracts, and accessibility UI coverage are release requirements. This does not broaden repository visibility, provider access, OAuth scopes, writeback permission, or v1 hosting topology.

## ADR-022: Keep GitHub OAuth entry points actionable before host configuration

- **Status:** Accepted on 2026-08-30.
- **Supersedes:** ADR-020 only where its dual-authentication UI is described as disabled before OAuth configuration.
- **Decision:** GitHub setup, sign-in, link, and reauthentication entry points remain keyboard-operable when the deployment has not configured OAuth. Activating one opens a same-origin host-side setup guide dialog and does not submit an OAuth start request or redirect to GitHub. Once the server reports OAuth as configured, the same shared GitHub button performs the existing top-level Authorization Code Flow with PKCE S256. A public `GET /api/admin/github/oauth/setup-guide` returns only configured state, the canonical fixed callback URL, the fixed GitHub OAuth-App documentation URL, and a next-step label, with `Cache-Control: no-store`.
- **Why:** A disabled button gives ordinary users no actionable explanation and makes a deployment-only setup prerequisite look like a user-registration failure. An actionable guide preserves the security boundary while making the next safe step discoverable.
- **Consequences:** AC-043 and FR-031 gain the unconfigured-button/dialog behavior; frontend tests must cover icon/label uniqueness, focus management, bilingual copy, responsive layout, and no-secret rendering. The guide never accepts or returns client secrets, encryption keys, tokens, secret-file paths, or owner identity. OAuth token lifecycle/refresh remains a separate follow-up until explicitly implemented.

## ADR-023: Use external, provider-managed embedding profiles

- **Status:** Accepted on 2026-08-30.
- **Supersedes:** ADR-001/ADR-006/ADR-015 only where they describe `local_sentence_transformers` as the production default or required runtime. Local adapters may remain in isolated benchmark fixtures, but are not a supported v1 deployment profile.
- **Decision:** Every deployment must connect at least one external embedding interface: Ollama, vLLM, or a generic OpenAI-compatible embeddings endpoint. Chat and embedding profiles are independent. A deployment-local registry supports profile CRUD and stores only server-side connection references plus the probed compatibility identity. At most one profile is active. Activation probes the selected model, queues a reindex when the identity changes, and atomically switches only after a verified compatible bundle is ready; the last-known-good bundle remains active on failure.
- **Model management:** The Web Admin provides a provider-aware model center. Ollama may expose a curated catalog, installed-model listing, pull, and delete through Ollama-native operations. vLLM and generic OpenAI-compatible services expose connect/list/probe/select; installation remains on the provider host. RepoNPC never downloads from arbitrary URLs or local paths.
- **Recommended catalog:** Ollama `qwen3-embedding:0.6b` is the initial zh-TW/en/code-oriented recommendation; `BAAI/bge-m3` and `embeddinggemma:300m` are optional alternatives, with larger Qwen3-Embedding variants for capable hosts. Dimensions, prefixes, normalization, and model identity are measured at probe/build time, not assumed from a model label.
- **Why:** A chat endpoint does not imply embedding support, and a nominal local default can make a clean runtime fail when its optional dependency/model is absent. Provider-native management keeps downloads in the service that owns the model and avoids a dangerous arbitrary downloader.
- **Consequences:** Runtime readiness depends on one active external profile and a matching bundle. Model/profile changes are explicit reindex operations; no provider/model/cloud fallback is allowed. Index builders receive a frozen profile snapshot and server-side credentials through their own secret boundary.

## ADR-024: Separate loopback convenience from production password and admin exposure

- **Status:** Accepted on 2026-08-30.
- **Supersedes:** ADR-017 for non-loopback/production password validation.
- **Decision:** An explicit loopback evaluation profile permits 4–128 Unicode code points. Production or any non-loopback admin surface requires at least 15 and permits up to 128, with no character-class composition rule and a common/compromised-password blocklist. Argon2id, backoff, secure cookie sessions, CSRF, origin checks, and revocation remain mandatory. Existing hashes remain usable during migration; a new password/change uses the selected profile policy.
- **Network:** A non-standard port is not an access control. The supported headless path binds the application to loopback and uses an SSH local-port tunnel; persistent remote administration uses a private LAN/VPN and firewall allowlist. A reverse proxy may expose visitor routes while denying `/admin` and `/api/admin` publicly. Public `0.0.0.0` administration is not a supported default.
- **Why:** The product is personal/self-hosted, but password hashes and admin endpoints still require a stronger boundary whenever a non-loopback path exists. SSH provides transport without adding a second management protocol.
- **Consequences:** Deployment profile, proxy ACL, password-policy, blocklist, and tunnel tests become release gates.

## ADR-025: Create the local owner first and retain local recovery

- **Status:** Accepted on 2026-08-30.
- **Supersedes:** ADR-020 only where it permits GitHub-only first-owner setup or treats a free-form recovery command as readiness.
- **Decision:** Host-issued setup proof is followed by local username/password creation. GitHub OAuth may be linked only from an authenticated local owner session and may later be used as an alternative sign-in/public-read connection. The local password is always retained as break-glass recovery; the final local method cannot be removed. A GitHub-only owner is not supported in v1.
- **Recovery:** `reponpc admin set-password --data-dir <dir>` is the host-only recovery procedure. It changes only the local hash, never reopens setup, changes GitHub identity, or returns secrets. Recovery readiness is proven by this product-owned command and backup/restore tests; `REPONPC_GITHUB_OWNER_RECOVERY_COMMAND` is not a readiness switch.
- **Why:** A user who chooses GitHub must still be able to recover when OAuth configuration, network access, or the GitHub account is unavailable.
- **Consequences:** First-login/link UI, runtime migration, logout/unlink rules, backup guidance, and security tests must describe local-first ownership.

## ADR-026: Use Web Admin for daily work and a bounded host CLI for operations

- **Status:** Accepted on 2026-08-30.
- **Decision:** Web Admin owns daily configuration, embedding profile CRUD, provider probes, and status. The CLI is limited to host bootstrap/recovery (`admin setup-code`, `admin set-password`), runtime health/backup (`runtime check`, `runtime backup <path>`), and bundle lifecycle (`bundle status`, `bundle verify <id>`, `bundle pin <id>`, `bundle unpin`). Linux/headless users access the same Web Admin through SSH tunneling; no separate public management API or Internet-facing setup port is added.
- **Why:** A full CLI duplicates the UI and increases contract surface, while no CLI leaves headless operators without deterministic recovery.
- **Consequences:** The named command groups, stable help/errors, explicit path/ID validation, clean-host restore, pin/rollback, and backup consistency tests are required before release.

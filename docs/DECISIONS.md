# RepoNPC Architecture Decision Log

## ADR-053: Freeze A1 visitor gateway and private administration contracts

**Owner-approved B5 amendment (2026-10-02; implemented locally 2026-10-03):**
[Simplification plan §11.6](../legacy/docs/A5_PAGES_SHARING_SIMPLIFICATION_HANDOFF_2026-10-02.md)
supersedes the earlier derived verification comparisons and local-chat error
behavior: verify accepts only revision/confirmation, uses verified_at plus
listener readiness, and clears the five report fields on configuration/lifecycle
changes, never on bundle activation. Both chat routes share heartbeat handling
and generic gateway chat errors, retaining their identity, admission, projection
and retry boundaries. Migration 30 and external-operation authorization remain
unchanged. The earlier compatibility statement below is historical for chat.

- **Status:** Accepted 2026-09-28 (OR-027); implementation in progress.
- **Authorization:** After reading the reviewed A1 design explanation, the owner approved continuing with gpt-6-luna max implementation and Main review/takeover. No public activation, provider spending or GitHub write is authorized.
- **Decision:** Adopt [A1/F0](A1_FUNNEL_GATEWAY_CONTRACT.md) as Technical Specification 0.4.6: production-only same-process loopback visitor listener; exact API/build-asset allowlist; one github.io Pages origin without credentials; separate private admin Origin/Host/hostname; explicit independent proxy trust; aggregate or verified per-IP protection; bounded buffered-answer SSE with heartbeats and no usage disclosure; three distinct owner facts; migration 30/private controls; opt-in Linux host-network Compose.
- **Lifecycle:** Owner intent may resume the local listener on restart, but dated external verification cannot resume from persisted state. Local stop never claims Funnel off. Official Tailscale ownership/credentials remain outside RepoNPC.
- **Compatibility:** Supersedes ADR-047's pending F0 decisions and PUBLIC_BASE_URL-only private-admin binding. The gateway has its own public projection; existing local public contracts remain compatible. No provider/model fallback, hosted service or implicit network publication is added. A5/A8/A12 retain their assigned scope.
- **Verification:** Normal/failure/security/lifecycle/ASGI SSE/runtime/browser/Compose checks are required. No local result establishes external Funnel or v1 release acceptance.

**Document status:** ADR-001 through ADR-045 accepted; ADR-045 approved 2026-09-22. Historical supersession is stated in each record.
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

Superseded by ADR-071 (2026-10-20). Full text: [legacy](../legacy/docs/DECISIONS_SUPERSEDED.md#adr-005-publish-immutable-bundles-through-github-releases).

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

Superseded by ADR-071 (2026-10-20). Full text: [legacy](../legacy/docs/DECISIONS_SUPERSEDED.md#adr-010-keep-public-presentation-configuration-in-git).

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

- **Status:** Accepted for the 4-by-7 state protocol; frame/sheet dimensions superseded by ADR-040 before deployment.
- **Decision:** Built-in composition and custom uploads both produce one transparent four-column/seven-row PNG with four frames for each ordered state: idle, walk, listen, think, talk, success, and offline. The historical `32x32`／`128x224` dimensions are not supported runtime formats after ADR-040; canonical dimensions are now `64x64`／`256x448`.
- **Why:** One fixed format keeps animation, validation, card generation, preview, reduced motion, and custom assets interoperable.
- **Consequences:** Custom artists must follow the documented grid. Changing dimensions, rows, or state order is a versioned asset-contract change.

## ADR-015: Close Phase 2 with a build-time provider, bilingual bundle profile, and isolated benchmark

- **Status:** Accepted historically; the local adapter is no longer a supported production default. ADR-023 supersedes its default/profile language while retaining build-time benchmark fixtures where explicitly named.
- **Decision:** Delivery Phase 2 includes the production `local_sentence_transformers` adapter as an optional indexer dependency and an executable `reponpc` index CLI. No arguments and `serve` retain the existing application startup path. Concrete OpenAI-compatible/Ollama adapters and runtime query-provider health/readiness integration remain Phase 3. One internal `public/profile.json` stores exact `zh-TW` and `en` locale payloads; the public route selects one locale and exposes its greeting plus validated character animation metadata. Root repository manifests are line-addressable `REPOSITORY_FACT` records with source type `repository_metadata`. Formal Phase 2 retrieval acceptance runs the production adapter in a Docker candidate limited to four CPUs and 8 GiB; only public questions and repository fixtures enter that container, while the reviewed oracle and scoring remain with the host controller. The audited state at Git commit `83c3dd44f7cc2856dc3b61d9f637337f1a466d3e` is the closure attribution baseline, and prior failed delta evidence remains immutable history.
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
- **Consequences:** Main owns five new authenticated onboarding endpoints, GitHub metadata pagination/rate-limit behavior, the 120-second analysis lifecycle and cleanup, provider-cost/cancellation behavior, evidence review, return editing hydration, session-only browser resume, and guided-to-YAML generation with preservation of fields outside the guided surface. The existing fine-grained GitHub token permissions, configuration schema version, role/summary assertion semantics, preview no-model rule, publication flow, and no-fallback policy do not change. This decision adds FR-025 through FR-028 and AC-038 through AC-040.

## ADR-019: Treat vLLM as a named OpenAI-compatible deployment preset

- **Status:** Accepted on 2026-08-15.
- **0.2.2 amendment:** ADR-029 permits protected owner-entered model connections and makes listing optional when unsupported. Actual chat/embedding capability probes remain mandatory; no wire-protocol or bundle-identity change is implied.
- **Decision:** Accept `vllm` in server-side chat and embedding environment configuration, then reuse the existing OpenAI-compatible model-list, chat-completions, and embeddings adapters. Permit only explicitly configured private HTTP origins for this preset. Normalize its embedding identity and existing public status provider value to `openai_compatible`, while keeping chat and embedding URL/model/key settings independent and verifying the selected model in each server's model catalog.
- **Why:** vLLM implements an OpenAI-compatible server, so a third transport would duplicate parsing and error behavior. The preset still needs an explicit private-network policy and operator guidance because common self-hosted vLLM deployments do not terminate HTTPS themselves.
- **Consequences:** Bundle schema version 1, browser APIs, the existing public provider enum, secret persistence, and fallback rules do not change. Operators must serve a chat-template-capable chat model and a separate embedding-capable model/server when embeddings are required. Raw keys and private URLs remain server-only and are excluded from responses, object representations, logs, fixtures, and snapshots.

## ADR-020: Add GitHub OAuth identity without broadening ownership or writeback (legacy; superseded by ADR-028)

Superseded by ADR-071 (2026-10-20). Full text: [legacy](../legacy/docs/DECISIONS_SUPERSEDED.md#adr-020-add-github-oauth-identity-without-broadening-ownership-or-writeback-legacy-superseded-by-adr-028).

## ADR-021: Resolve selected public repositories through immutable archives and durable batches (partially superseded by ADR-028)

- **Status:** Accepted on 2026-08-16.
- **Decision:** Guided multi-repository analysis uses a central, rate-aware GraphQL metadata resolver plus one exact-commit archive per cache miss. It creates at most one owner-scoped durable batch whose items advance through independently bounded stages and publish safe replayable events. OAuth/PAT public-read credentials are selected explicitly and never fall back; the writeback credential is unavailable to analysis. Validated index/result caches use complete immutable identity keys. The legacy one-repository route remains a batch compatibility adapter.
- **Why:** Per-blob REST resolution is rate-expensive and branch references can drift. Browser-controlled serial work cannot survive reloads, enforce server capacity fairly, or preserve the boundary between safe durable status and ephemeral untrusted source/model data.
- **Consequences:** Runtime SQLite gains rate, batch, event, and cache metadata. The scheduler must cap GitHub/archive/local/provider stages and reserve provider opportunities for public chat. Exact-SHA archive validation, 24-hour bounded batch result retention, explicit retry after dispatched generation interruption, restart cleanup, API/SSE contracts, and accessibility UI coverage are release requirements. This does not broaden repository visibility, provider access, OAuth scopes, writeback permission, or v1 hosting topology.

## ADR-022: Keep GitHub OAuth entry points actionable before host configuration (legacy; superseded by ADR-028)

Superseded by ADR-071 (2026-10-20). Full text: [legacy](../legacy/docs/DECISIONS_SUPERSEDED.md#adr-022-keep-github-oauth-entry-points-actionable-before-host-configuration-legacy-superseded-by-adr-028).

## ADR-023: Use external, provider-managed embedding profiles

- **Status:** Accepted on 2026-08-30.
- **0.2.2 amendment:** ADR-029 removes preselected providers/models and adds protected connection entry. Recommendations apply only after explicit Ollama selection. External runtime, curated provider-native installation, one-active, and last-known-good boundaries remain accepted.
- **Supersedes:** ADR-001/ADR-006/ADR-015 only where they describe `local_sentence_transformers` as the production default or required runtime. Local adapters may remain in isolated benchmark fixtures, but are not a supported v1 deployment profile.
- **Decision:** Every deployment must connect at least one external embedding interface: Ollama, vLLM, or a generic OpenAI-compatible embeddings endpoint. Chat and embedding profiles are independent. A deployment-local registry supports profile CRUD and stores only server-side connection references plus the probed compatibility identity. At most one profile is active. Activation probes the selected model, queues a reindex when the identity changes, and atomically switches only after a verified compatible bundle is ready; the last-known-good bundle remains active on failure.
- **Model management:** The Web Admin provides a provider-aware model center. Ollama may expose a curated catalog, installed-model listing, pull, and delete through Ollama-native operations. vLLM and generic OpenAI-compatible services expose connect/list/probe/select; installation remains on the provider host. RepoNPC never downloads from arbitrary URLs or local paths.
- **Recommended catalog:** Ollama `qwen3-embedding:0.6b` is the initial zh-TW/en/code-oriented recommendation; `BAAI/bge-m3` and `embeddinggemma:300m` are optional alternatives, with larger Qwen3-Embedding variants for capable hosts. Dimensions, prefixes, normalization, and model identity are measured at probe/build time, not assumed from a model label.
- **Why:** A chat endpoint does not imply embedding support, and a nominal local default can make a clean runtime fail when its optional dependency/model is absent. Provider-native management keeps downloads in the service that owns the model and avoids a dangerous arbitrary downloader.
- **Consequences:** Runtime readiness depends on one active external profile and a matching bundle. Model/profile changes are explicit reindex operations; no provider/model/cloud fallback is allowed. Index builders receive a frozen profile snapshot and server-side credentials through their own secret boundary.

## ADR-024: Separate loopback convenience from production password and admin exposure (partially superseded by ADR-027)

- **Status:** Accepted on 2026-08-30.
- **Supersedes:** ADR-017 for non-loopback/production password validation.
- **Decision:** An explicit loopback evaluation profile permits 4–128 Unicode code points. Production or any non-loopback admin surface requires at least 15 and permits up to 128, with no character-class composition rule and a common/compromised-password blocklist. Argon2id, backoff, secure cookie sessions, CSRF, origin checks, and revocation remain mandatory. Existing hashes remain usable during migration; a new password/change uses the selected profile policy.
- **Network:** A non-standard port is not an access control. The supported headless path binds the application to loopback and uses an SSH local-port tunnel; persistent remote administration uses a private LAN/VPN and firewall allowlist. A reverse proxy may expose visitor routes while denying `/admin` and `/api/admin` publicly. Public `0.0.0.0` administration is not a supported default.
- **Why:** The product is personal/self-hosted, but password hashes and admin endpoints still require a stronger boundary whenever a non-loopback path exists. SSH provides transport without adding a second management protocol.
- **Consequences:** Deployment profile, proxy ACL, password-policy, blocklist, and tunnel tests become release gates.

## ADR-025: Create the local owner first and retain local recovery (partially superseded by ADR-027)

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

## ADR-027: Make loopback administration passwordless and GitHub connection-only (GitHub portion superseded by ADR-028)

- **Status:** Accepted on 2026-09-04.
- **Supersedes:** ADR-016/ADR-017/ADR-024/ADR-025 only for `loopback_evaluation` bootstrap and recovery; ADR-020/ADR-022 where they make GitHub an owner sign-in method or expose OAuth setup before an admin session. Production/non-loopback password authentication, private administration, session security, PKCE, encrypted credential storage, and credential-purpose isolation remain in force.
- **Context:** Real first-run use showed a circular and misleading path: an owner could be presented with **Sign in with GitHub** before OAuth was configured, configuration required host-side secrets, recheck could not redirect while those secrets were absent, and an already initialized runtime offered no registration path. For a launcher-bound local evaluation, asking the person who just started the process to register and repeatedly enter a password adds ceremony without establishing a meaningful new trust boundary. Removing every security control would still expose localhost services to malicious browser origins, DNS rebinding, other local processes, and accidental non-loopback binding.
- **Decision — local access:** `loopback_evaluation` has no registration or password-login UI. After readiness, the trusted host launcher creates a random 256-bit, one-use local-launch grant with a two-minute expiry, stores only its SHA-256 digest, and opens `/admin#local-launch=<grant>`. The frontend immediately exchanges the fragment through same-origin `POST /api/admin/session/local-launch`, removes the fragment with `history.replaceState` before external navigation, and retains the returned CSRF value only in memory. The server accepts the exchange only when the configured bind address, public base URL, request peer, `Host`, and origin are loopback-valid and trusted-proxy interpretation is disabled. Consumption and creation/reuse of the sole owner plus the normal 256-bit server-side session are atomic. Missing, expired, replayed, cross-origin, non-loopback, forwarded, or mismatched grants fail closed without revealing which check failed. A local browser without a valid session or grant shows one recovery action: reopen RepoNPC through the local launcher.
- **Decision — production access:** `production` and every non-loopback administration path retain the host-issued setup code, local username/password, Argon2id, common-password protection, backoff, recovery command, and private SSH/VPN/proxy topology. Environment validation MUST refuse `loopback_evaluation` when any bind/base URL/host/proxy setting can admit a non-loopback client. A passwordless local owner cannot be used after switching to production until the host operator creates a compliant password with `reponpc admin set-password`.
- **Decision — GitHub:** GitHub OAuth is an optional authenticated public-read connection, never an administrator authentication or registration method. OAuth setup/link/recheck controls exist only inside the authenticated GitHub settings surface. A configured connection uses the existing Authorization Code Flow with PKCE and fixed callback; an unconfigured connection opens the safe guide. Successful recheck changes the dialog primary action to **Continue to GitHub** rather than implying that recheck itself redirects. The login/setup OAuth intents and public GitHub sign-in button are removed; existing encrypted OAuth public-read credentials are preserved by migration, while identity-only login state is retired without exposing token material.
- **Decision — retained controls:** HttpOnly/Secure/SameSite session cookies, CSRF, origin/host validation, expiry, rotation, revocation, audit redaction, OAuth state/PKCE, encryption at rest, and GitHub writeback separation remain mandatory. "Passwordless" describes the local user experience, not an unauthenticated admin API.
- **Why:** This puts the security proof where it belongs: possession of a short-lived capability minted by the process the owner just launched for loopback use, or a durable password on remotely reachable deployments. It removes the first-run dead end and prevents GitHub configuration from becoming a prerequisite for entering settings.
- **Consequences:** The launcher, CLI, environment validation, runtime schema, auth API, frontend access panel, migrations, tests, README, and operations guide must change together. Existing local passwords remain stored so a user can return to production mode; local sessions still expire and logout requires relaunch. GitHub App Manifest automation may later reduce OAuth host configuration, but it is not part of this decision.
- **References:** [Chrome Local Network Access](https://developer.chrome.com/blog/local-network-access), [MDN Local Network Access](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Local_network_access), [Jupyter Server security](https://jupyter-server.readthedocs.io/en/stable/operators/security.html), [GitHub OAuth Web Flow](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps).

## ADR-028: Retire GitHub OAuth and public-read PATs in favor of anonymous public REST resolution

- **Status:** Accepted on 2026-09-08; deterministic implementation recorded in [GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_HANDOFF.md](../legacy/docs/GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_HANDOFF.md) on 2026-09-09; external release evidence remains pending.
- **Supersedes:** ADR-020 and ADR-022 in full; ADR-021 where it requires GraphQL or an `identity_public_read` / `public_read` credential; ADR-027 only for its GitHub connection/setup/PKCE/encrypted-public-read behavior. ADR-027's loopback launch, production password, recovery, session, CSRF, origin/host, and private-admin decisions remain accepted.
- **Context:** First-run use demonstrated that OAuth configuration adds deployment ceremony unrelated to RepoNPC ownership. Moving OAuth behind authentication removed the login dead end but left a prominent optional connection surface, client-secret/callback/encryption-key configuration, and a second public-read PAT path. For a single-owner application that supports only public repositories, this operational and secret-management cost is disproportionate. GitHub's GraphQL API requires authentication, while its REST API permits unauthenticated public-data access with a documented per-IP limit.
- **Decision:** Remove GitHub OAuth and browser-entered public-read PATs from the product. Public discovery and selected-repository analysis use bounded, fixed-origin unauthenticated GitHub REST requests, resolve a full immutable commit SHA, and fetch only the archive addressed by that SHA. Rate exhaustion produces a safe retry time and preserves manual authoring/export. Discovery and analysis never receive or fall back to the independent writeback token. Legacy OAuth/PAT routes become non-mutating `410` responses during a bounded compatibility window; runtime migration removes their transactions, identities, and encrypted public-read credential rows without decrypting or logging them.
- **Why:** This removes an OAuth App, callback, client secret, encryption key, token lifecycle, and PAT form from the normal self-hosting journey while retaining the public-repository use case. The accepted trade-off is GitHub's lower anonymous REST capacity, which matches the intended low-frequency personal deployment and must degrade recoverably.
- **Consequences:** FR-030/FR-034 and AC-041 through AC-043 become legacy; FR-031 is narrowed to deployment-aware local administration with no GitHub credential surface; FR-032/AC-044 move from credentialed GraphQL to anonymous REST; FR-037 and AC-051/AC-052 govern retirement and replacement. OAuth/PAT UI, API, environment variables, launcher mappings, services, tests, and operational instructions are removed in an ordered migration. Historical schema migrations remain readable. The separately configured least-privilege writeback token and its exact path/operation allowlist remain unchanged.
- **Implementation plan:** [GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_PLAN.md](../legacy/docs/GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_PLAN.md).
- **References:** [GitHub REST API rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api), [GitHub GraphQL authentication](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql).

## ADR-029: Configure model services through a provider-neutral owner workflow

- **Status:** Accepted on 2026-09-09. Connection/chat/embedding implementation is present at the 2026-09-10 review; integrated first-run acceptance remains incomplete. ADR-030 governs the corrected journey and bootstrap boundary.
- **Authorization:** The owner accepted the preceding analysis and requested updated specifications, project memory, and an implementation document with enough context for handoff. Figma is explicitly skipped. The owner's GGUF/Hugging Face idea remains exploratory and is not approval for a bundled runtime or arbitrary downloader.
- **Supersedes:** ADR-010's environment-only/no-admin-secret-entry clause for model connections only; ADR-019's mandatory model-list readiness rule when listing is unsupported; ADR-023's first-run Ollama recommendation placement and environment-reference-only entry path. No change to public YAML/bundle schema, GitHub credential retirement, private admin authentication, or no-fallback rules.
- **Evidence:** `EmbeddingProfilePanel.tsx` preselects Ollama/Qwen3/1024/`environment`, displays raw states, and requires a dimension. `AdminWorkspace.tsx` inserts that panel ahead of guided onboarding. `main.py::_environment_embedding_provider` resolves only the `environment` reference and matching environment provider. Multi-profile forms therefore do not provide arbitrary independent API connections. Registry/reindex/operations implementations already exist and must be extended, not recreated.
- **Decision:** Give chat and search independent model setup. Start unconfigured, select a protocol, enter API address, optional write-only key, and a manually editable model ID; offer optional model listing and explicit synthetic capability tests. Preserve manual portfolio authoring without models. Use localized status/action text and place low-level diagnostics behind Advanced. Keep Ollama recommendations/install actions contextual and optional; API/vLLM paths are connect/test/select only.
- **Secret boundary:** An authenticated same-origin form may submit newly entered URLs/keys to the backend; it may never receive stored values back or persist them in browser storage. Persist keys using vetted authenticated encryption or a supported OS secret store, with host-protected key material, backups, and explicit retain/replace/remove semantics. Connection changes create candidate revisions; a prior key cannot be sent to a changed destination. Server-validated egress, safe errors, CSRF/session controls, and reference cleanup remain mandatory.
- **Activation:** Explicit environment setups survive upgrades as host-managed connections. Managed selections survive restart without environment fallback. Chat switches only after capability validation; embedding switches only after the existing verified index lifecycle. In-flight work retains its old revision. Missing storage/model/provider capacity preserves manual work and last-known-good service.
- **Implementation authority:** The behavior and trust boundary in Technical Specification 0.2.2 section 11.5 are approved. Exact new DTOs, endpoint paths, physical migrations, key-store packaging, and host-egress configuration are contract-preparation deliverables, not existing APIs; freeze them before dependent implementation. Routine choices inside this approved boundary do not need repeated permission. Any expansion of trust, topology, runtime support, cost, or v1 scope requires a new owner decision.
- **Consequences:** Adds FR-038 through FR-040 and AC-053 through AC-057; requires API/storage/provider/bootstrap/frontend/migration tests and novice browser verification. Full release remains blocked until evidence is collected. Provider-neutral bootstrap requires coordinated environment/launcher changes; documentation approval cannot be reported as working UI.
- **Handoff:** `MODEL_SETUP_IMPLEMENTATION_HANDOFF.md` is the self-contained implementation entry point, including the current-source inventory, proposed contracts, ordered steps, failure cases, and release evidence rules.

## ADR-030: Configure models before AI onboarding and separate analysis selection from public activation

- **Status:** Accepted on 2026-09-10; documentation delivered, application correction pending.
- **Authorization:** After reviewing the six-step proposal and its backend implications, the owner replied “好”. The accepted package is model setup -> project selection -> analysis -> contribution confirmation -> basic information -> preview/draft, with unnumbered welcome and an immediate manual route. The current task is specification/memory/implementation-handoff work, not application edits.
- **Evidence:** `AdminWorkspace.tsx` renders model panels only outside guided mode; `guidedOnboarding.ts` routes confirmed selection directly to analysis. `AdminPage.tsx` projects public model status into guided status. `onboarding.py` needs both embeddings and chat. `main.py` leaves the runtime absent without both providers; `_replace_runtime_chat` only replaces an existing runtime and `_configure_embedding_reindex` requires that runtime. Individual profile/API tests do not prove the clean first-run chain.
- **Decision:** Put actionable model setup in the primary AI journey and keep independent tested selections for analysis/chat and search. Analysis uses a frozen, explicitly selected pair without requiring a published bundle or public-active embedding flag. Selection creates usable admin analysis dependencies without a restart and does not alter public serving state. Public activation still requires the complete verified bundle lifecycle. The manual branch skips both AI setup and analysis and preserves local drafting/export.
- **Supersedes:** ADR-018's first-run ordering; ADR-023/ADR-029 only where profile selection for admin analysis was conflated with public single-active/bundle readiness. The single-public-active, last-known-good, write-only secret, explicit-cost, selected-repository, no-fallback, bounded batch and citation rules remain.
- **UX and compatibility:** One Start analysis action wraps preflight/create; no request is triggered merely by visiting a step or returning from settings. Contextual recovery preserves public drafts and reconciles active jobs. Old browser progress cannot supply readiness or force destructive reset. Existing drafts remain editable without re-running AI. Exact additive wire/storage contracts must be frozen before code changes.
- **Scope limits:** No chat-only/lexical analysis redesign, new public schema, locale-threshold reduction, hosted service, publication-topology change, durable server portfolio drafts, Figma, or GGUF/Hugging Face runtime. Separate model references do not create another inference service or another public active model per role.
- **Consequences:** Adds FR-041/FR-042 and AC-058 through AC-060. Requires an actual clean-bootstrap-to-analysis integration/browser test, existing-public-service preservation, revision/cache consistency, old-state migration, manual-route and bilingual/accessibility coverage. Existing green tests are baseline evidence only.
- **Handoff:** `ONBOARDING_FLOW_IMPLEMENTATION_HANDOFF.md` is the next implementation entry point; the 0.2.2 handoff remains architectural history and a source of retained security obligations.

## ADR-031: Let owners replace or delete environment-default model connections

- **Status:** Accepted and implemented on 2026-09-12; full AC-055/056/057 release evidence remains pending.
- **Authorization:** The owner explicitly rejected immutable default connection cards and identified non-default Ollama ports as a concrete unusable case.
- **Context:** The UI hid edit/delete for `host-managed` connections. Although the backend CRUD path did not uniformly reject them, startup mirroring overwrote edits and recreated deleted rows, so adding buttons alone would produce misleading, non-durable behavior.
- **Decision:** Show edit/delete on host-managed cards. The first edit requires a complete newly entered URL and never reads back the environment URL/key. A successful replacement creates a new protected revision, changes the connection to owner-managed, and records durable precedence over startup mirroring. Startup then preserves the associated owner-edited model profile rather than rewriting its model identity from environment defaults. A prior key cannot cross a changed destination without explicit replacement/removal; an existing no-key state may remain no-key. Deletion remains blocked by Chat/Embedding profile references; otherwise it atomically stores a secret-free `disabled` marker and deletes the connection, and startup honors that marker instead of recreating the default.
- **Storage and recovery:** Runtime migration 21 adds `host_managed_connection_overrides(connection_id, state, updated_at)`, with state limited to `managed|disabled`. It stores no URL, secret reference, or credential. Runtime SQLite backup/restore therefore carries the owner's override/deletion choice; encrypted connection revisions still require the separately protected model-secret key.
- **Consequences:** Technical Specification advances to 0.2.4. FR-039/040 and AC-055/056/057 cover API, security, restart, bilingual UI, migration, and reference-safety behavior. Existing no-fallback, no-key-readback, managed-URL edit-endpoint, profile revision, and last-known-good rules remain unchanged.

## ADR-032: Rebind editable model candidates when their connection changes

- **Status:** Accepted and implemented on 2026-09-13; full live-provider/browser AC-055/056/057/060 evidence remains pending.
- **Authorization:** After observing that a working local Ollama service still produced `EMBEDDING_CONNECTION_REQUIRED`, the owner rejected the extra manual profile-save ceremony and explicitly requested the existing model settings be updated directly when their connection is updated.
- **Evidence:** The real Ollama `/api/version`, `/api/tags`, and `/api/embed` calls succeeded, including `qwen3-embedding:8b` with a 4096-dimensional vector. The stored connection was revision 2 while the environment embedding profile remained revision 1, so provider resolution returned no provider before any Ollama request. The connection update transaction changed only the connection row/secret revision and left dependent candidate rows stale.
- **Decision:** An effective provider/URL/key connection update atomically rebinds directly referencing editable Chat and Embedding candidates to the new connection revision; Embedding also follows the selected connection provider. Their prior probe observations/errors/timestamps are cleared and an explicit retest is required. If the current analysis selection references that connection, its generation advances and existing plans become stale while the explanatory selection IDs/revisions remain. A display-name-only edit changes none of these values. Unrelated profiles are untouched, and saving never auto-probes, activates, reindexes, analyzes, or publishes.
- **Protected revisions:** Public-active, previous last-known-good, and reindexing profiles are not rebound. Already frozen batch snapshots keep their old pair. Historical connection-secret revisions record the provider as safe metadata, allowing those pinned profiles/jobs to resolve the correct protocol plus encrypted endpoint/key after restart. No private URL/key is added to metadata reads.
- **Migration and consequences:** Runtime migration 22 backfills provider metadata for existing protected revisions and repairs safe candidates stranded by earlier connection updates, clearing invalid probe evidence and invalidating stale selection generations in one transaction. Technical Specification advances to 0.2.5. FR-039/040/042 and AC-055/056/057/060 govern this behavior. The explicit retest, no-fallback, key-cross-destination, last-known-good, and immutable in-flight rules remain.

## ADR-033: Resume a valid admin session after page reload

- **Status:** Accepted for implementation on 2026-09-13; full clean-browser release evidence remains pending.
- **Authorization:** The owner observed that refreshing a page opened by `start-reponpc.cmd` showed the relaunch screen even though both processes and the server session were still active, then approved the proposed strict same-origin session-resume correction.
- **Evidence:** The live `/healthz` endpoint remained alive and runtime SQLite retained one current unrevoked session. The frontend defined authentication solely as an in-memory CSRF value; reload erased it, the one-use fragment had correctly been removed, and bootstrap called only public auth-method discovery before selecting the relaunch screen. The existing refresh endpoint required the now-lost CSRF token, and tests covered grant exchange but not post-exchange page reload.
- **Decision:** Add empty-body `POST /api/admin/session/resume`. It requires the existing valid HttpOnly session cookie and the same host/origin/private-admin boundary, returns only session-bound CSRF and expiry metadata with `Cache-Control: no-store`, and consumes no local-launch/setup proof. CSRF is deterministically derived from the high-entropy session token through a domain-separated server HMAC, remains browser-memory-only, and is accepted alongside the pre-0.2.6 stored random CSRF for existing sessions until they expire. The frontend attempts resume whenever no launch fragment exists, then uses the prior relaunch/password recovery path on generic failure.
- **Consequences:** Technical Specification advances to 0.2.6. FR-017/029/031 and AC-049/050 require valid-session reload, expiry/revocation/cross-origin/forwarded-host failure, multi-tab compatibility, no storage/grant replay, and production-password regressions. No database migration, new credential, public management protocol, or launcher behavior is added.

## ADR-034: Give repository analysis its own output budget and reject truncation

- **Status:** Accepted for implementation on 2026-09-13.
- **Authorization:** The owner requested “調用luna max修改，預設token限制為8192 最大16k” after reviewing analysis JSON failures. Here 16k means 16,384 tokens.
- **Evidence:** Analysis used `min(800, provider capability)`, while managed chat capabilities inherited the visitor default 1,000 / maximum 2,000. Merely replacing 800 would therefore remain clamped. Synthetic adapter-to-analysis cases proved that nonempty `length` termination could become a schema error or even an accepted result. The historical failed response was not retained, so its actual termination cause is unknown. See `ANALYSIS_JSON_FAILURE_DIAGNOSIS_2026-09-13.md`.
- **Decision:** Add server-only `REPONPC_ANALYSIS_MAX_OUTPUT_TOKENS` (positive integer, default 8,192, maximum 16,384), wire an analysis-specific adapter ceiling, and reserve the effective output plus complete messages/schema/framing before packing evidence. Insufficient context rejects analysis before chat generation without breaking manual or public startup. Public chat/probes retain their configured 1,000 / maximum 2,000 policy; contribution suggestions retain 700. Context estimates are conservative and distinguished from provider-reported usage.
- **Validation:** Reject observed output-limit termination before parsing, including empty output and syntactically valid JSON. Use `PROVIDER_ERROR` with closed reason `PROVIDER_OUTPUT_LIMIT_REACHED`; migration 24 extends the existing constrained reason storage transactionally and the authenticated UI explains the limit in both languages. No partial output becomes a result/cache entry. Full JSON/Pydantic/evidence/person-claim checks remain.
- **Cache and scope:** Bind result-cache reuse/prediction/writing to the same configured budget, effective provider output/context caps and generation/validation policy used for generation. Keep frozen models, shared provider admission, deadlines, last-known-good state and explicit manual retry. No new inference call, automatic repair, fallback, RAG framework or hosted dependency is introduced.
- **Consequences:** Technical Specification advances to 0.2.7. FR-012/027/033/042, NFR-001/002/014 and AC-002/015/018/035/039/040/045/046/059 cover configuration bounds, real application wiring, context admission, truncation, migration, cache and public-policy regression. Synthetic tests do not prove a live gateway enforces schema or that larger repositories achieve complete evidence coverage.

### ADR-021 analysis diagnostic correction — 2026-09-13

- **Authorization:** After a real two-repository batch failed, the owner required the per-repository failure to remain visible and traceable instead of showing only an aggregate failure count.
- **Evidence:** Both items completed passage/query embedding. A flat repository then produced no `REPOSITORY_FACT` because its root-level source files matched none of the defaults, while the other item reached chat generation and failed one of three application-owned output checks. `GuidedOnboardingError.reason` was discarded at the batch-worker boundary, and the UI intentionally hid even the retained stable code.
- **Decision:** Empty include selections cover common source extensions in addition to the existing directory/manifest defaults, while all mandatory secret/binary/generated/path/size exclusions remain authoritative. Failed durable items retain only a closed-set application reason for no eligible content, output-schema mismatch, evidence-ID mismatch, or rejected personal attribution. The authenticated UI displays the allowlisted code/reason with bilingual recovery text after reload; unknown values are replaced or omitted.
- **Consequences:** Runtime migration 23 adds nullable `analysis_batch_items.error_reason`. Existing rows remain valid with null reasons and still display their stable error code. Provider/repository bodies, prompts, arbitrary exception text, request IDs, paths, URLs, and credentials remain prohibited. The current analysis algorithm still requires the explicitly selected embedding role for retrieval and chat role for generated analysis, with no fallback or automatic retry.

### ADR-029/030 implementation clarification — 2026-09-12

The owner approved the novice UI/UX repair findings as one batch. Unknown embedding dimensions use nullable untested profile metadata until an explicit successful query/passage probe; public bundle identities remain concrete. Connection update uses explicit endpoint retention versus replacement, with independent key intent and unchanged no-cross-destination-key-reuse constraints. Display-name-only edits preserve the effective connection revision. These additive runtime/API refinements implement the accepted no-guessing, write-only, explicit-selection directions; they do not add fallback, hosting, inference services or public schema changes. Technical Specification 11.5 records the exact wire rules; Operations records transaction-safe migration 19.

### ADR-029 diagnostic correction — 2026-09-12

The owner rejected the inferred Chinese HTTP 402 billing explanation and explicitly requested original provider error text. Provider prose is open-world data, not a closed translation vocabulary. Replace the HTTP explanation lookup with adapter-bound structural message extraction and preserve the original language in both locales. The owner-authorized additive `last_error_message` admin DTO/runtime field stores only bounded redacted error text; HTTP status remains a validated protocol value. Migration 20, parsing/redaction limits, unavailable-message behavior and regression criteria are frozen in Technical Specification 11.5, Security 21 and AC-054/055/057. Existing prohibitions on full provider bodies, secret disclosure, public diagnostic expansion and implicit fallback remain.

### ADR-029 URL editing correction — 2026-09-12

**Owner-approved URL editing exception (2026-09-12, ADR-029; FR-038/040, AC-055/057):** The owner explicitly requested that replacing a managed service URL prefill its saved value. Only `POST /api/admin/model-connections/{connection_id}/edit-endpoint`, guarded by the existing owner session, same-origin check and CSRF, may return `{connection_id, revision, base_url}` with `Cache-Control: no-store`. It accepts no arbitrary URL, reads the exact current encrypted revision, rejects host-managed/unknown connections with 404 and unavailable secret storage with 503, and makes no provider request or mutation. List/detail metadata remains URL-free; API keys, secret references and environment values are never returned. The UI fetches only on the explicit Replace URL action, keeps the result in the active form only, clears it on cancel/toggle-off/teardown, and ignores responses after a form or revision change. Loading disables URL editing/submission; failure permits retry or manual entry. No readback URL may enter browser storage, public drafts, exports, logs or snapshots. This narrow exception supersedes earlier blanket stored-URL readback prohibitions; stored-key prohibitions and destination-change credential rules remain unchanged.

## ADR-035: Treat same-origin path edits as the same service and make failures actionable

- **Status:** Accepted and implemented on 2026-09-14; full AC-055/057 release evidence remains pending.
- **Authorization:** The owner observed that adding `/v1` to the existing coderelay service was rejected unless the key was re-entered, called that same-service behavior unreasonable, and explicitly requested correction plus visible diagnostic/recovery feedback for every failed update or save.
- **Decision:** Compare the current and replacement URL by provider and normalized security origin: scheme, case-insensitive hostname, and effective port. A path-only edit on the same provider/origin may retain the encrypted key. A provider, scheme, hostname, or effective-port change remains a credential-boundary crossing and requires explicit key replacement or removal. Every effective URL edit still creates a revision, rebinds only safe dependent candidates, clears their probe evidence, and requires explicit retest; saving never calls the provider.
- **Error contract:** A connection create/update/delete/refresh failure renders exactly once in the initiating panel. It states the failed action, safe reason, whether existing state was preserved, and a recovery step; it associates field-specific errors, moves keyboard/screen-reader focus to the summary, exposes a safe request ID when available, and labels pending state. Browser-entered keys clear after submission on either outcome, and a failure explicitly says when re-entry is required. Provider bodies, stack traces, private URLs, keys and arbitrary exceptions remain excluded.
- **Consequences:** Technical Specification advances to 0.2.8. FR-039/040, NFR-003 and AC-055/057 cover origin comparison, cross-origin rejection, revision/retest behavior, bilingual recovery, single-alert scoping and secret clearing. ADR-029's narrow managed-URL readback and ADR-032's safe candidate rebinding remain unchanged. No migration, API shape, provider request, fallback, hosted dependency or public bundle change is introduced.

## ADR-036: Give Chat probes one non-duplicating timeout grace window

- **Status:** Accepted for implementation on 2026-09-14. Numbers superseded by ADR-074 (60 seconds).
- **Authorization:** A live owner-authorized coderelay check returned the model catalog in about 0.9 seconds and a valid `gpt-5.6-terra` Chat response in about 11.6 seconds, while RepoNPC's fixed 10-second probe repeatedly reported timeout. The owner concluded that the limit was too strict and explicitly requested a default 10 seconds followed by one additional 10 seconds. (Probe deadline numbers superseded by ADR-074.)
- **Decision:** Keep the 10-second probe baseline and grant one automatic 10-second grace window. Pass one 20-second deadline to the selected provider so the original in-flight request can complete; do not cancel and restart at 10 seconds. A single explicit test therefore remains exactly one potentially billable provider call. Existing response-schema checks, output budget, activation boundary, diagnostic persistence, and no-fallback rules remain unchanged. (Probe deadline numbers superseded by ADR-074.)
- **Consequences:** Technical Specification advances to 0.2.9. FR-038/040 and AC-054/057 cover a valid response during the grace window, final timeout after 20 seconds, and regression evidence that only one request is made. No environment variable, API or database migration is added. (Probe deadline numbers superseded by ADR-074.)

## ADR-037: Treat analysis limits as configurable active-work budgets

- **Status:** Accepted for implementation on 2026-09-14.
- **Authorization:** After reviewing the live batch failures and the complete limit inventory, the owner concluded that the fixed limits were too rigid for real projects and explicitly requested the flexible configuration proposed in the review.
- **Decision:** Repository analysis defaults to 1,800 active seconds with a 7,200-second deployment ceiling; archive, index and shared-provider semaphore waits do not spend it. Provider operations default to a 300-second socket/inactivity ceiling (maximum 3,600), GitHub I/O to 60 seconds (maximum 300), and transient rate-limit/timeout/unavailable failures may use three total attempts against only the frozen selected provider/model. Public chat output becomes 4,096-default / 8,192-maximum while authenticated analysis remains 8,192 / 16,384. Archive/source thresholds become validated server settings. An individual archive member over the materialization threshold is represented without its body and skipped as `FILE_TOO_LARGE`; unsafe structures and total compressed/uncompressed/entry ceilings still fail closed. Runtime migration 25 widens durable item budgets. Batch snapshots expose active elapsed time, total budget and generation-attempt count, while the UI preserves specific archive/timeout codes. An explicit owner retry upgrades an older batch to the current budget/attempt policy without resetting consumed active time, changing its frozen provider/model or silently resubmitting it.
- **Alternatives rejected:** Merely raising the old 120/45 constants still charges scheduler waits and remains inflexible. Removing all ceilings permits decompression bombs, unbounded memory/cost and stuck workers. Switching provider/model after failure changes owner intent and remains forbidden.
- **Consequences:** Technical Specification advances to 0.3.0. Large repositories and reasoning models can complete without artificial queue failures, while deployment operators retain explicit disaster ceilings. Complete buffered adapters can only approximate inactivity through socket timeouts; truthful first-token/token-idle progress remains dependent on a future streaming provider contract.

## ADR-038: Separate same-round retry from a controlled successor analysis round

- **Status:** Accepted for implementation on 2026-09-17.
- **Authorization:** After reviewing the repair plan and ChatGPT's workspace analysis, the owner explicitly instructed Codex to implement the recommended endpoint and runtime migration.
- **Decision:** Keep `/retry` as a continuation of the existing round and make its snapshot/action eligibility one shared predicate over terminal state, remaining generation attempts, remaining active-work time, and absence of an existing successor. Add explicit `/reanalyze` to create an idempotent successor batch for selected failed items after the source batch is terminal. Each source item may be consumed by only one direct successor; another round starts from that successor's latest failed item. The successor copies the immutable commit and selection policy, defaults to the source frozen model pair, resets only the new round's attempt/time counters, and preserves the source batch, source errors, successful siblings, and owner-confirmed content until their ordinary TTL. The durable request identity includes model selection, confirmation, and expected selection generation; an accepted create remains replayable after the in-memory preflight cache expires. Selecting the current model pair requires explicit confirmation bound to the expected selection generation. One-active-batch and lease rules remain unchanged.
- **Diagnostics and storage:** Runtime migration 26 adds only secret-free source batch/item IDs, analysis round, and failure stage. Migration 27 adds a secret-free source-consumed marker and bounded reanalysis idempotency receipts so cleanup cannot reopen consumed work and every accepted key remains request-bound. Existing frozen pair JSON remains the model identity record. Snapshot counts separate processed from successful results; terminal active clocks are settled once; `completed_with_errors` is terminal in SSE and UI. Stable 409 codes distinguish unavailable retry, invalid successor selection, non-terminal source, active-batch conflict, and missing model-change confirmation.
- **Consequences:** Technical Specification advances to 0.3.1. FR-027/033/041/042 and AC-039/040/045/060/061 govern concurrency, idempotency, source/model pinning, recovery, bilingual UI, migration rollback, privacy, and preservation. No automatic provider/model fallback, latest-commit refresh, hidden retry, new hosted dependency, or raw provider/source persistence is introduced.

## ADR-039: Use species-neutral versioned character packs

- **Status:** Accepted for implementation on 2026-09-21.
- **Authorization:** The owner explicitly rejected retaining the old humanoid-shaped public fields and instructed that they be corrected directly because RepoNPC has not been deployed.
- **Decision:** Built-in character configuration contains only `pack_id`, positive `pack_version`, and a bounded string `options` mapping. The trusted in-process registry maps that identity to a pack-owned option manifest and deterministic renderer. Core configuration/composition does not define a species enum and does not interpret anatomy- or costume-specific keys. Every pack and arbitrary custom character converges on ADR-014's canonical 4-by-7 sheet. The row name `walk` is a semantic locomotion/activity state, not a humanoid anatomy claim.
- **Compatibility:** Remove the undeployed top-level `body`, `skin`, `hair`, `outfit`, color, and `accessory` fields without aliases, dual-read behavior, or migration code. Unknown pack/version/option contracts fail closed without fallback. Existing humanoid rendering details remain private to `core/humanoid` version 1 and do not constrain future packs.
- **Consequences:** Technical Specification advances to 0.3.2. Adding a supported built-in form is a registry/pack addition plus tests and provenance, not a core schema edit. User-created forms outside the built-in catalog use the canonical custom-sheet path without declaring a species. Pack implementations remain trusted application code; YAML cannot inject code, paths, URLs, or renderer names.

## ADR-040: Normalize open-world character material to a 64px canonical protocol

- **Status:** Accepted for implementation on 2026-09-21.
- **Authorization:** After the species-neutral pack correction, the owner approved direct implementation of a larger canonical format and a conversion mechanism because uploaded material will not always match RepoNPC's requirements and the project has not been deployed.
- **Decision:** Replace the undeployed 32px frame with one `64x64` frame, making the 4x7 sheet `256x448`, without a legacy path. Runtime animation remains a fixed closed protocol. Ingestion is an open-world adapter: derive any square-cell 4x7 PNG structurally, or require schema-1 `sprite-pack.json` to map all 28 PNG frames in a bounded ZIP. Offer deterministic `pixel_exact` and `pixelize` policies behind one verifier and return a canonical preview plus warnings before any write.
- **Security and integrity:** User packs are data, never executable plugins. Normalize archive paths, reject links/encryption/traversal/duplicates/unsafe framing/animation/resource excess, and never infer frames from filenames or invent missing content. Conversion does not overwrite or persist the source; ordinary writeback receives only the revalidated canonical PNG after explicit owner action.
- **Consequences:** Technical Specification advances to 0.3.3. Web animation, cards, built-in rendering, custom validation, examples and tests use the same centralized 64px constants. High-resolution antialiased art can produce a deterministic draft, but warnings and visual review remain necessary; conversion is not evidence that the artwork is artistically release-ready.

## ADR-041: Discover structural sprite candidates in novice ZIP and folder uploads

- **Status:** Accepted for implementation on 2026-09-21.
- **Authorization:** After seeing that directly zipping `PixelNPC/Man` would not satisfy the strict manifest contract, the owner asked for a workflow that an inexperienced repository owner can use without preparing special files, approved researching established browser-upload patterns, and then approved implementation.
- **Decision:** The authenticated converter accepts one PNG/ZIP through drag, drop, or file selection and accepts a browser-selected folder as relative-path/file pairs. A root manifest retains ADR-040's strict deterministic behavior. Otherwise the server scans bounded PNG members by the closed 4-by-7 square-cell protocol. Exactly one candidate converts automatically; multiple candidates return canonical visual previews for explicit selection; none return actionable failure. Candidate IDs hash normalized path and bytes and are recomputed when selected.
- **Anti-hardcode boundary:** Filenames, folder names, source dimensions, species, anatomy, and visual meaning are open-world data and never choose the character automatically. The 4-by-7 state contract, canonical 64px frame, deterministic policies, and resource/security ceilings remain closed protocol. Standard folder input is a progressive enhancement; PNG/ZIP remains the interoperable fallback, without making experimental directory APIs mandatory.
- **Security and consequences:** Archive/folder paths, counts, bytes, pixels, animation, links, encryption, duplicates, and candidate count remain bounded and validated. Inspection and selection do not write, execute, or retain source material. Technical Specification advances to 0.3.4; human visual review remains necessary when several structurally valid layers/sheets exist.

## ADR-042: Make character and animation setup an ordinary owner workspace

- **Status:** Accepted for implementation on 2026-09-22.
- **Authorization:** After testing the admin page, the owner identified that an ordinary user would not enter a control labelled raw YAML and required every design decision to begin from ordinary-user experience rather than developer structure.
- **Decision:** Add `Character & animation` as a first-level authenticated workspace beside guided setup and advanced YAML. The normal flow is task-oriented: choose material, choose the intended character when ambiguous, preview each of the seven animation states, then download or save. Raw YAML, canonical dimensions, conversion policies, sheet layout and diagnostic codes are not primary navigation or primary copy; they remain available through explicit advanced/technical disclosure.
- **Accessibility and behavior:** Reuse the production character renderer so preview semantics match runtime behavior. State selection is keyboard-operable and programmatically pressed, primary targets are at least 44px, status changes remain announced, layouts collapse without horizontal scrolling, and operating-system reduced-motion preference stops frame motion.
- **Consequences:** Technical Specification advances to 0.3.5. Admin-only remains the correct authorization boundary, but technical implementation structure no longer determines information architecture. This changes no sprite, API, trust, writeback, or provider contract.

## ADR-043: Make frame-position repair opt-in, visual, and canonical

- **Status:** Accepted for implementation on 2026-09-22.
- **Authorization:** After viewing the Orange animation in the in-app browser, the owner approved repairing the abnormal frame movement. The observed idle and walk frames had changing horizontal pixel positions while the preview canvas remained fixed.
- **Decision:** The authenticated character workspace offers a reversible, geometry-only horizontal alignment suggestion for each four-frame state and pixel-level manual X/Y adjustments. It uses per-frame alpha occupancy, not filenames, species, anatomy, or an artwork-specific template. Suggested and manual offsets are constrained so no existing opaque pixel leaves its 64px frame. The original conversion result remains unchanged until the owner explicitly applies the edit.
- **Integrity boundary:** Browser compositing is only a draft preview. Applying the edit submits the draft PNG to the existing authenticated `/api/admin/assets/character/validate` endpoint; only its canonical re-encoded response may be downloaded or sent through normal GitHub writeback. A validation failure preserves the original result and blocks adjusted download/writeback. No new asset format, endpoint, persistence model, source overwrite, or silent alignment is introduced.
- **Consequences:** Technical Specification advances to 0.3.6. Automatic suggestions may not infer intended motion, and edge noise can limit safe offsets; the owner still reviews all seven states and may restore the original.

## ADR-044: Offer conservative edge-spill cleanup within material conversion

- **Status:** Accepted for implementation on 2026-09-22.
- **Authorization:** After the owner saw brown lines above some Orange animation poses, inspection found pixels from the preceding source-grid row inside the next row's cells. The owner approved adding cleanup directly to conversion, with a before/after preview and no silent source overwrite.
- **Decision:** Only structural grid PNGs may produce an optional cleaned variant. A source-cell-relative shallow top fragment must continue the preceding row's bottom pixels, end before a transparent gap, and leave independently occupied current-frame art. No filename, species, color, anatomy, or pose rule is allowed. The ordinary conversion remains unchanged; the alternate sheet is independently canonical-validated. The authenticated response returns nullable `edge_cleanup` containing its canonical asset, affected state/frame coordinates, and removed-source-pixel count.
- **Owner boundary:** The workspace compares the same state/frame of both versions and requires an explicit cleaned/original choice before download or GitHub writeback. Ambiguous content and separate manifest frames remain untouched. Source material is never overwritten or persisted, no new endpoint or server-side choice state is introduced, and subsequent position alignment uses the chosen version under ADR-043's validation gate.
- **Consequences:** Technical Specification advances to 0.3.7. This removes a conservative class of grid-boundary remnants but cannot infer arbitrary visual intent; human review of all states remains necessary.

## ADR-045: Auto-validate repeated layout drift and expose exact pixel offsets

- **Status:** Accepted for implementation on 2026-09-22.
- **Authorization:** After testing Man, the owner asked that safe frame-position correction run during conversion and that ordinary users receive an adjustment box for each position's pixel offset.
- **Decision:** The chosen canonical conversion is inspected without another click. A horizontal correction is automatic only when non-clipping per-column displacement agrees across at least half of the seven independent animation states, within frame-relative bounds and one unambiguous pattern. Isolated or conflicting movement remains a suggestion for review; neither species nor filename nor anatomy drives the decision. After any explicit edge-cleanup choice, the same check runs on that selected version. The owner may edit each selected frame's X and Y offsets in labeled integer-pixel fields, use one-pixel controls, or restore the unaligned version.
- **Integrity boundary:** Automatic composition and later manual edits use the existing authenticated canonical PNG validator. Automatic bytes become downloadable/writeable only after its success; invalid manual drafts cannot be applied, and a validation failure leaves the chosen original available. Source files and unselected variants are never changed, and GitHub writeback remains explicit.
- **Tradeoff:** Repeated deliberate motion can resemble repeated layout drift. The preview identifies automatic adjustment, keeps original restoration, and asks the owner to review all seven states. This supersedes ADR-043's opt-in-only timing but retains its non-clipping, validation, and reversibility guarantees. Technical Specification advances to 0.3.8.

Chat probe diagnostic follow-up (2026-09-12): the owner reported `PROVIDER_INVALID_RESPONSE` despite a working service. Inspection found a separate 32-token probe cap and collapsed parser failures. Main corrected the internal probe budget to the configured capability and added source-labelled, closed-set parser evidence under the existing diagnostic field, without inventing provider text or model-name special cases. No claim is made about the owner's actual response, which was not retained. Details: `docs/CHAT_PROBE_RESPONSE_CHECKS_2026-09-12.md`.

## ADR-046: Owner-controlled local publication and guided GitHub cards

- **Status:** Accepted for implementation, 2026-09-22.
- **Authorization:** Owner explicitly requested Luna Max implementation after correcting the plan to local embedding, local chat, and GitHub card-only sharing.
- **Decision:** Adopt [the frozen local publication contract](LOCAL_PUBLICATION_CONTRACT_2026-09-22.md). Local public drafts, verified bundles and disposable passage vectors live on the owner host. No Actions, Release or write credential is needed for the normal journey. Use explicit preparation/activation and the existing last-known-good controls. Local assertions have truthful same-origin citations.
- **UX:** Apply character to the shared draft, preview/try locally, then three short GitHub steps with actual account/file/link values. External reachability remains separately verified.
- **Compatibility:** This supersedes GitHub-only transport in ADR-001/005/010/030; legacy polling must stop at a durable local-source transition. No public model/admin access, automatic GitHub write, hosted dependency or model fallback is added.

## ADR-047: Select Tailscale Funnel for a no-purchase visitor URL

- **Status:** Owner-selected deployment direction on 2026-09-24; implementation and external acceptance pending.
- **Authorization:** After comparing Cloudflare Tunnel, GitHub Pages and free public URL options, the owner explicitly chose Tailscale Funnel and requested an updated plan. This authorizes planning the transport, not enabling a public endpoint or changing GitHub content in this task.
- **Decision:** Make an explicitly enabled Tailscale Funnel and its `*.ts.net` HTTPS hostname the planned default public visitor path for an individual owner who does not purchase a domain. Keep local portfolio creation usable without Tailscale and retain an operator-managed HTTPS gateway as an advanced deployment option. The public path reaches only visitor assets and public APIs through a default-deny gateway; the production admin and model services remain private. Do not attach the loopback evaluation launcher directly to Funnel.
- **Boundaries:** Tailscale supplies connectivity and HTTPS, not compute or models. The owner signs in to Tailscale and deliberately enables public reachability. No Tailscale credential belongs in public YAML, browser storage, logs, bundles or images. Existing same-origin visitor behavior, production authentication, no provider fallback, budgets, citations and last-known-good activation remain intact. Funnel's beta status, bandwidth limits and Personal-plan eligibility must be disclosed rather than promised away.
- **Consequences:** Follow [the deployment plan](TAILSCALE_FUNNEL_DEPLOYMENT_PLAN_2026-09-24.md). Before application or Compose changes, freeze the gateway allowlist, private-admin origin handling, proxy/client-IP trust, supported host and credential lifecycle in Technical Specification, Security, Operations and Acceptance Criteria. Current local verification and the older operator-domain recipe are not evidence that the Funnel route is implemented or externally reachable.

## ADR-048: Adopt the completion direction — segment answers, participation, reviewed FAQ, Pages + Funnel live chat, Windows installer, built-in bge-m3

- **Local implementation checkpoint (2026-09-28):** A4 FR-046 is covered by [the concrete coverage/FAQ contract](A4_COVERAGE_FAQ_IMPLEMENTATION.md). Runtime migration 29 preserves immutable bundles, and public delivery/export share an approved-current allowlist. This does not mark the remaining completion-direction milestones or public release accepted.

- **Status:** Accepted 2026-09-26; A2–A4 have partial/local implementation evidence through 2026-09-28. Remaining completion-direction work and formal A12 release evidence are pending.
- **Authorization:** The owner approved decisions D1–D9 (2026-09-25/26) and resolved Q1–Q9 on 2026-09-26, the final confirmation being Q8 = (b) and Q9 as recommended, and asked for the specification, acceptance criteria and project memory to be updated and committed on `main` without push.
- **Decision:** Adopt [the completion direction contract](COMPLETION_DIRECTION_CONTRACT_2026-09-26.md) as Technical Specification 0.4.0 §2.10 (FR-043–FR-049) and AC-062–AC-071:
  - envelope v2 typed segments (`person` / `participation` / `project` / `inference`) with backend-rendered `{{owner}}`, a centralized inflation lexicon, a numeric-fact check and silent per-segment drop;
  - person questions without owner statements answered from project and participation evidence with no gap message, and a localized no-match reply with suggested questions;
  - a count-free `PARTICIPATION` evidence class (repository-owner flag, first/last visible commit month, other-contributors flag; unavailable is never zero);
  - an informational coverage check and an owner-reviewed FAQ (approve / reject / regenerate / convert to owner statement), exported only when approved and bound to the bundle;
  - MVP free-form live chat: a manually uploaded GitHub Pages static shell calls the Tailscale Funnel visitor-only gateway, with a 「休息中」 resting state and in-browser matching of approved FAQ entries when the host is off;
  - a Windows PyInstaller onedir + Inno Setup per-user installer (unsigned, SHA-256 published) with Docker kept for Linux;
  - a built-in `builtin_onnx` `bge-m3` embedding default downloaded only after explicit first-use consent, with external embedding services still selectable;
  - owner-only model guidance (device check linking to canirun.ai without copying its data, Ollama explicit pull, plain-language errors, one-line status, cloud data disclosure).
- **Supersedes:** ADR-047's deferral of the gateway (Funnel gateway F0/F2 is MVP); the external-only embedding default in §5.4/§13.3 and FR-006/FR-012; FR-011/§8 whole-answer abstention and the any-person-keyword rejection; the §18 external-origin exclusion, for the configured Pages origin only (credential-free CORS to visitor APIs).
- **Boundaries:** No automatic GitHub write or push; the owner uploads the export manually. No silent provider/model switch or silent download. Visitors never see host uptime, hardware, provider, model or cost information. Views, visitor attachments, readiness tests, cost estimates, code signing and macOS installers are out of scope; browser-local microphone input is post-MVP. Personal roles are never inferred from code or participation.
- **Consequences:** Technical Specification becomes 0.4.0. AC-062–AC-071 start not-run, and the release audit/ledger must be extended to them. Implementation order starts with the gateway (F0/F2) and FR-043–FR-049. D8 validation is owner-run.

## ADR-049: Derive the visitor scene from the active character, never from a fixed species

- **Status:** Accepted 2026-09-26; implementation pending. No acceptance evidence exists. Superseded by ADR-051 (2026-09-26) on three points: colour derivation, pack scene hints, and the ban on visitor-selectable themes (visitors may now switch light/dark). The rule that the NPC follows the character stays.
- **Authorization:** On 2026-09-26 the owner stated that the visitor NPC and background must change with the character the owner uploads or selects, and that the cat in the reference mockup is only an example. The scene contract details (token roles, precedence, contrast solver and override limits) were drafted from that requirement under the anti-hardcode rule. The owner may revise them before implementation.
- **Context:** `CharacterRenderer` already draws any canonical sheet. The surrounding visitor page, however, uses fixed `--ui-*` tokens and literal colours. `card.themes` covers only the GitHub card, and the admin guide mascot is a CSS-drawn humanoid. A per-species theme table would be a closed list for an open-world input.
- **Decision:** Adopt [completion direction contract §4.4](COMPLETION_DIRECTION_CONTRACT_2026-09-26.md) as Technical Specification 0.4.1 FR-050 / §12.3 and AC-072–AC-073:
  - **Sheet-derived tokens:** deterministic scene tokens (a closed set of roles, light and dark) derived server-side from the canonical sheet's pixels.
  - **Precedence:** owner override, then optional opaque pack scene hints, then sheet derivation, then the neutral default (only on derivation error, with the reason reported).
  - **Contrast:** an AA contrast solver that adjusts lightness only and guarantees NPC/backdrop separation.
  - **Background image:** an optional validated, re-encoded PNG/WebP owner background that is decorative only.
  - **Delivery:** tokens are served in the public profile and exported in the hashed static-site manifest.
  - **Admin:** a 「場景」 preview step in the Character & animation workspace, and the admin guide mascot replaced by the active character.
- **Boundaries:** No species, `pack_id`, filename or option-name branching. No free-form CSS or arbitrary property names from configuration or packs. No text placed directly on an image. No animated backdrops, per-state scenes or visitor-selectable themes. `card.themes` stays explicit; an explicit copy-to-card action is optional. Visitor payloads remain free of host, model and cost data.
- **Consequences:** Technical Specification becomes 0.4.1. AC-072 and AC-073 start not-run. Visitor CSS literal colours must move behind scene tokens with a style guard. Scene fixtures must be species-agnostic and generated programmatically.

## ADR-050: Offer colour-scheme templates as registry data, and an owner background image with a realistic preview

- **Status:** Accepted 2026-09-26, revised the same day; implementation pending. No acceptance evidence exists. ADR-051 supersedes the hue-seed templates and the full-page backdrop placement. The owner image draft and preview flow stays, with the image moved to the welcome hero.
- **Authorization:** On 2026-09-26 the owner asked for several background and colour-scheme templates to choose in settings. After the first draft (procedural backdrop patterns), the owner said that programmatically drawn template backgrounds are not worth having, and asked for an owner background upload with a preview showing roughly how the interface looks with the image and the character. The registry schema, the starter set, the draft/preview flow and the precedence were drafted from those requests under the anti-hardcode rule. The owner may revise them before implementation.
- **Context:** ADR-049 derives one automatic scene from the active character. The owner also wants explicit colour choices and their own pictures. Hardcoding named themes in frontend CSS or in resolver branches would scatter literals and invite species- or pack-specific themes. Drawn geometric backdrops add little value, and an image chosen blind risks a published page the owner did not expect.
- **Decision:** Adopt [completion direction contract §4.5–§4.6](COMPLETION_DIRECTION_CONTRACT_2026-09-26.md) as Technical Specification 0.4.3 FR-051/FR-052 / §12.3 and AC-074–AC-075:
  - **Colour templates:** one versioned, schema-validated `scene_templates.yml`. Each entry has an id, version, localized labels and a palette mode (`follow_character` or `fixed` OKLCH hue seeds) with a named tone. No backdrop fields. Retired ids resolve through `aliases`. The default `auto` is the ADR-049 derived scene.
  - **Background image (MVP):** uploads become private, expiring drafts. The owner previews the visitor page, built from the real visitor components, with the image, the active character, template colours and a sample dialog, in both themes and desktop/phone frames. Focus point, dim and scaling are adjustable. 「套用」 promotes the draft; nothing public changes before that.
  - **Precedence:** palette is owner accent, then fixed seeds, then character hue (pack hint, derivation), then neutral default on error. Backdrop is owner image, then pack backdrop hint, then the plain background colour. The ADR-049 contrast solver and NPC-separation check run last.
  - **Parity:** preview and publication use the same server resolver.
  - **Export:** resolved tokens, template id and version, and the applied image.
- **Boundaries:** No template references a species, `pack_id`, filename or option key; no code branches on a template id; no hex or CSS in the registry; unknown ids fail closed. No drawn decorative backdrops; no bundled illustrated backgrounds in MVP. Drafts are never public or exported. The preview makes no provider call. Visitors cannot choose templates. `card.themes` stays explicit.
- **Consequences:** Technical Specification becomes 0.4.3. AC-074 and AC-075 start not-run. The FR-050 fixtures form the character axis of a template × character × theme × image contrast matrix. The security model gains the draft upload path.

## ADR-051: Use a plain chat interface with owner-selected colour schemes and light/dark mode

- **Status:** Accepted 2026-09-26; implementation pending. No acceptance evidence exists. Partly supersedes ADR-049 and ADR-050. ADR-072 (2026-10-23) supersedes its flat-colour and no-drawn-backdrop clauses, the ban on visitor scheme choice, the starter set and the chat layout; the registry, closed roles, AA validation, mode script and the NPC following the character remain in force.
- **Authorization:** On 2026-09-26 the owner said:
  - no bundled illustrated backgrounds are needed;
  - a simple chat UI is enough, like the SnowUI "ChatGPT UI Kit" Figma community file;
  - colours need not follow the character;
  - several colour schemes should be offered for the owner to choose, together with light and dark modes.

  The Figma file could not be fetched (it requires a login), so the layout was drafted from the kit's public description and common AI-chat layouts. The starter schemes, defaults and layout details were drafting assumptions; the owner confirmed all six the same day (「照你的建議，六點都確認」, contract §10 Q12). Exact hex values are set during implementation and reviewed with the generated contrast report.

- **Context:** ADR-049 derived page colours from the sheet, and ADR-050 added hue-seed templates and an owner background behind the whole page. The owner now prefers a familiar, quiet chat interface in which the character is the only personal visual element. Deriving colours from pixels adds complexity and unpredictable results for little owner value, and full-page images compete with the conversation.
- **Decision:** Adopt contract §4.0 and §4.4–§4.6 as revised. They become Technical Specification 0.4.4 (FR-047/050/051/052, §12.3, §16) and the revised AC-068 and AC-072–AC-075:
  - **Layout:**
    - a collapsible sidebar with the profile card and project list, which becomes a drawer on phones;
    - a top bar with the NPC status avatar, a language switch and a light/dark toggle;
    - a centred chat column with a welcome hero (large animated NPC, greeting, suggestion chips), right-aligned visitor bubbles, left-aligned NPC answers with an avatar and 「來源」, and a bottom input bar;
    - flat colours only, with no illustrated or drawn backgrounds.
  - **Colour schemes:**
    - one versioned, schema-validated `color_schemes.yml` with explicit light and dark `#rrggbb` values for each closed role (`surface_alt` added, `glow` removed);
    - every scheme must pass AA contrast as authored, or loading fails;
    - starter set: `neutral` (default), `ocean`, `forest`, `sunset`, `lavender`.
  - **Colour mode:** `system` (default), `light` or `dark`. `visitor_mode_toggle` (default on) lets visitors switch light/dark; their choice is stored only in their own browser's `localStorage`.
  - **Character:**
    - only the NPC follows the character: the hero, the answer avatars and the status avatar;
    - stage separation adjusts only the stage or uses a plate;
    - sheet-palette derivation, pack scene hints and hue-seed templates are retired.
  - **Owner image:** optional, shown only behind the NPC in the welcome hero. The ADR-050 draft and preview flow stays, and the config key `color_scheme` replaces `template`.
  - **Admin:** the 「場景」 step becomes 「外觀」. It holds the scheme gallery, the mode selector, the visitor toggle, the optional accent under 「進階」 and 「重設為預設」.
- **Boundaries:**
  - No scheme references a species, `pack_id`, filename or option key, and no code branches on a scheme id.
  - Frontend source holds no literal colours or scheme ids outside a build-generated fallback block.
  - Visitors may switch light/dark but cannot choose a scheme.
  - The visitor's mode choice is never sent to the server, exported or stored in a cookie.
  - No bundled illustrated backgrounds.
  - `card.themes` stays explicit.
- **Consequences:**
  - Technical Specification becomes 0.4.4.
  - AC-068 and AC-072–AC-075 are revised and remain not-run.
  - Superseded: ADR-049's derivation and pack-hint parts, and ADR-050's hue-seed template parts and full-page backdrop placement.
  - Still in force: the NPC follows the character, token mapping, the separation check, image validation and the draft/preview flow.

## ADR-052: Pin the official bge-m3 source, close R08/R11/R12-B minimally, and add a maintenance page

- **Status:** Accepted 2026-09-27; implementation pending. No acceptance evidence exists.
- **Authorization:** On 2026-09-26 the owner said 「A10 和 A11 照你的建議，A6 來源也照建議」. On 2026-09-27 the owner added that this is planning only and must not be over-designed, so each item below is the smallest version that closes the gap.
- **Decision:**
  - **bge-m3 source (FR-049):** the official `BAAI/bge-m3` Hugging Face repository at revision `5617a9f61b028005a4858fdac845db406aefb181`, folder `onnx/`, with every file checked against the SHA-256 list in contract §6.2. This is the fp32 export, about 2.29 GB. The earlier ~570 MB figure came from a third-party int8 upload, which is not a trusted source. The dialog shows the size from the pinned file list. Local int8 quantization is not part of the MVP.
  - **R08 (protected previews):** folded into A5. Every admin preview (character candidates, card previews, hero-image drafts) is served only by authenticated same-origin admin routes with `Cache-Control: no-store`, is unreachable from public routes and the export, and the CSP stays unchanged. Gate: AC-079.
  - **R11 (reload recovery):** `GET /api/admin/onboarding/analysis-batches/active` also returns the newest terminal batch when it still allows retry or reanalyze, finished within the last 7 days and has not been dismissed by the owner. The dismissal is stored on the server. Browser storage is never the source of truth. Gate: AC-077.
  - **R12-B (reusable derived index):** first measure whether the ADR-046 passage-vector cache already avoids the expensive work after a failure or restart. If it does, R12-B closes as covered. If not, the staged index is kept as a content-addressed file under the data directory with the same protections and cap/TTL mechanics as the passage cache; it is never served and is excluded from backup and export. Gate: AC-078.
  - **Maintenance page (FR-053):** a 「維護」 admin page that shows local / gateway / external-verified status, the active bundle and the last backup; creates and downloads a backup; restores from a file after confirmation and an automatic backup; pins a previous bundle; stops the visitor gateway; and explains how to update (run the newer installer) and how to turn Funnel off in Tailscale. It reuses the existing `runtime backup` and `bundle pin` primitives. Gate: AC-076.
- **Not included:** in-app installer download and verification, configurable R11 windows or R12-B cache sizes, and local model quantization. Each is added only if real use shows the need.
- **Consequences:** Technical Specification becomes 0.4.5, adding FR-053 and AC-076–AC-079. All four start not-run.

## ADR-054: Encrypt Web maintenance backups and restore in the same data directory

- **Status:** Accepted 2026-10-03; local implementation and verification in progress.
- **Authorization:** After reviewing the backup boundary and UX recommendation,
  the owner said 「好，那採用A」. See [the concrete decision](../legacy/docs/A11_BACKUP_BOUNDARY_DECISION_2026-10-03.md), OR-028 and Technical Specification §11.7.
- **Evidence:** The existing online SQLite backup contains the owner authentication
  hash and encrypted connection revisions; host encryption keys and referenced
  resources live outside SQLite. Raw Web download conflicts with the browser
  secret invariant and cannot represent a complete migration archive.
- **Decision:** Encrypt the online backup with an owner-entered password using
  bounded, versioned Scrypt/AES-GCM. Browser receives ciphertext only. Inspect
  and normalize untrusted SQLite against trusted migrations, validate retained
  resources, then require explicit confirmation. Drain real writers and stop the
  old lifespan; encrypt and retain the current state before atomic replacement.
  Roll back the database and pointer if fresh startup fails. Expire and remove
  private preview staging. Revoke sessions/grants and leave the gateway off.
- **Scope:** SQLite restoration requires the original data directory, host keys,
  compatible model files/bundles and referenced appearance/local assets. Missing
  resources fail closed. Full cross-host migration remains the stopped-service
  operations procedure. CLI host-only raw backup remains protected and unchanged.
- **Alternatives:** Raw browser SQLite download (option B) was not selected;
  stripping authentication or credentials would break recovery continuity.
- **Consequences:** Approved specification 0.4.7 freezes the private routes and
  artifact format, updates FR-053/AC-076 verification and operations/security
  guidance. No hosted dependency, fallback, public route or Tailscale credential
  authority is added. Formal AC-076 remains open until its complete browser and
  installed-deployment matrix has evidence.

## ADR-055: Preserve reasoning and bound combined generation at 16k

- **Status:** Accepted 2026-10-03 (OR-029); implementation and verification are separate from release acceptance. Chat/probe output ceiling and the subsequent chat default/maximum timeout are superseded by ADR-076; the 16,384 default output, analysis budget and reasoning policy remain unchanged.
- **Authorization:** The owner rejected default `think: false`, required reasoning ON and explicitly supported 16,384 tokens.
- **Evidence:** ADR-034/037 were approved budget policies. Current live reasoning-model evidence showed that the legacy chat ceiling did not establish successful completion for this workload; disabling reasoning would change the owner's intended behavior. No committed question, oracle or quality threshold is changed.
- **Decision:** Chat/probe and authenticated-analysis budgets remain independent, each with a 16,384-token default and hard maximum. Explicit lower settings remain valid. Ollama generation counts reasoning and answer within one ceiling, with a separate bounded input-plus-generation context. Supported reasoning controls remain ON; unknown support retains the backend default and is reported as unknown. No model-name heuristic establishes support. OpenAI-compatible/vLLM retain their existing provider semantics.
- **Safety:** Reserve full input/schema/framing and output before generation; a smaller verified provider context/cap wins. Output-limit termination fails before parsing or publication, including valid partial JSON. Preserve deadlines, the one-request 20-second probe, existing transient analysis policy, no output-limit retries, no fallback and trace privacy. Analysis cache identity includes the changed budget/reasoning policy. No public schema, toggle, streaming or new provider is added. (Probe deadline numbers superseded by ADR-074.)
- **Sources (checked 2026-10-03):** [Ollama thinking controls](https://docs.ollama.com/capabilities/thinking), [chat usage fields](https://docs.ollama.com/api/chat), [generation/context parameters](https://docs.ollama.com/modelfile), [context allocation](https://docs.ollama.com/context-length), and the [official Qwen3.5-9B model card](https://huggingface.co/Qwen/Qwen3.5-9B). Qwen documents thinking enabled by default and 262,144 native context; its 128k complex-reasoning recommendation is not a measured guarantee for RepoNPC's bounded 32,768 configuration. Generated token counts and model-tokenizer context are distinct from visible characters; no fixed Chinese-character ratio is claimed.
- **Consequences:** Approved Specification becomes 0.4.8; FR-012/027/033/038/040/041, NFR-002/003/011/012/014 and AC-023/039/054/055/057/061 gain bounded-control and privacy regressions. Earlier decisions retain their historical values; only their superseded output defaults/ceiling change. Live quality acceptance remains evidence-dependent.

## ADR-056: Align the two-facts validation question with its unchanged oracle

- **Status:** Accepted 2026-10-03 (OR-030); validation-fixture clarification only. Approved Specification remains 0.4.8.
- **Authorization:** The owner explicitly approved the [two-facts correction](../legacy/docs/A7_TWO_FACTS_FIXTURE_REVIEW_2026-10-03.md), after the unchanged reasoning-ON/16k suite returned 10/12. The original question asked only about storage, while its reviewed oracle required retrieval fusion and storage.
- **Decision:** Change only `supported_two_facts.question` in the committed answer-quality fixture to ask both parts explicitly; use the prescribed matching Traditional Chinese question in the new bilingual runner. Preserve evidence, source IDs, raw fixture answers, all expected claims/citations/refusal rules, thresholds, case count and all other questions. No production prompt, model-name branch or provider setting changes.
- **Evidence boundary:** Retain the original fixture bytes and old 10/12 reports unchanged. The corrected fixture fingerprint identifies a separate suite revision. Run the complete fixed 12 bilingual cases once; catalog admission still requires all cases passing and the existing verified model revision/source/license/quantization provenance. Approval of the question does not predict a pass or establish release acceptance.
- **Consequences:** Supplemental AC-057 evaluation guidance records this owner-approved semantic alignment. No FR/AC ID, schema, threshold, public API or specification-version expansion is needed; ADR-055 reasoning and budget controls remain unchanged.

## ADR-057: Real visitor chat progress and a longer bounded wait

- Status: Accepted 2026-10-04 for waiting UX (OR-031); thinking-text display remains pending. Timeout numbers superseded by ADR-076 (300-default / 600-maximum).
- Decision: Reuse existing chat SSE and provider transport for real service
  phases, native Ollama thinking activity (never its text), elapsed duration,
  native disclosure and cancellation. Default total timeout becomes 180 seconds,
  within the existing 300 maximum; explicit settings are retained. No fake
  timer phases, model tools, new dependencies or extra provider calls.
- Safety: Final content is buffered and passes unchanged validation. Progress
  contains only closed labels and elapsed_ms. Streamed calls never retry or
  fall back. Raw thinking/unknown compatible reasoning fields stay private.
  Automatic review rejected the proposed raw-text public callback; the owner's
  thinking-text request remains unfinished, with separate summary/trace choices.
- Contract: CHAT_PROCESSING_CONTRACT_2026-10-04.md. Requirements FR-043/044/047,
  NFR-005/009/014, AC-019/023/062/063/064/068/071; no acceptance threshold changes.
- References: native Ollama NDJSON, Chat Completions SSE, WHATWG disclosure and
  AbortController; official-source Luna Max review retained as dated evidence.

## ADR-058: Provider-defined public summaries on an explicit interface

Status: Accepted 2026-10-04 (OR-032). Reuse the protected connection form and encrypted revision lineage to select the chat interface explicitly. Add `chat_api` (`chat_completions` default or `responses`) to safe connection metadata and the encrypted revision payload; legacy ciphertext defaults to the old interface. Migration 35 adds one column, with no table rebuild. Responses is valid only for openai_compatible connections; embeddings retain their existing interface. Consume complete provider-defined summary paragraphs, privately check prompt copies and known credentials/endpoints before an optional bounded `reasoning_summary` SSE event. Preserve final validation, one call, deadline/cancel, ephemeral UI and no tools/fallback. [public summary contract](CHAT_PUBLIC_SUMMARY_CONTRACT_2026-10-04.md). *Amended 2026-11-07 by ADR-083: the form no longer asks for `chat_api`; "Test model" detects it.*

## ADR-059: Complete GitHub profile README as the sharing deliverable

- Status: Accepted 2026-10-12 (OR-033), owner explicitly approved implementation.
- Decision: Offer exact README content preview and **Download README.md** as the
  primary final sharing action. Use the confirmed public snapshot and existing
  verified GitHub Pages GIF so the owner can upload one file. Rebuild and compare
  the existing verification digest, check the fixed public GIF bytes with the
  existing Pages transport and recheck the source after that read.
- Preservation: Keep the copied card block and manual image-upload route. Explain
  the matching-account public repository root in both languages and never
  overwrite an existing README. GitHub displays the card; chat opens the existing
  RepoNPC website. No new hosting, provider, dependency, database state or GitHub
  write is introduced. Escape public text/URLs and reject final output over 500 KiB.
- Contract: [README export](PROFILE_README_EXPORT_CONTRACT_2026-10-12.md),
  Approved Specification 0.4.11, FR-016/024, AC-028; existing manual/external gates
  remain independent of local regression evidence.

## ADR-060: Validate model writing systems and use source-only analysis facts

- **Status:** Accepted 2026-10-14 (OR-034); implementation and verification are separate from release acceptance.
- **Authorization:** The owner approved plan items A–E on 2026-10-14 after reviewing the output-validation, cache/source-shape, and analysis-presentation repair.
- **Decision:**
  - Analysis output uses schema/prompt version 3 and validation version 2. Every inference requires localized `title` and `statement`; title bounds are 24 characters for `zh-TW` and 80 for `en` at the backend boundary. The same evidence-ID, personal-attribution and locale/source writing-system checks apply to both fields.
  - The writing-system check normalizes NFKC, treats locale-native systems as allowed, and permits another system only when it occurs in the packed analysis source. Contribution role, summary and claim strings use the owner-authored request as their source. Owner-authored input is not checked. Ungrounded output fails with the existing `PROVIDER_ERROR` / `PROVIDER_OUTPUT_SCHEMA_INVALID` reason, without retry, fallback, raw-output retention or cache success.
  - Analysis facts contain only evidence ID/class, path, line range and a pinned GitHub URL; `excerpt` and fact `title` are absent. Validated cache payloads retain those facts and the localized inferences so a cache hit has the same source links as a live result.
  - The admin analysis view uses repository metadata and commit chips, compact expandable Highlights rows, matched GitHub source links and a privacy popover. It keeps inferences unconfirmed and places contribution entry before reanalysis.
- **Boundaries:** Public schema-v1 configuration and owner-confirmation rules are unchanged. The backend remains the only citation/URL authority; no provider fallback, repository-text persistence or automatic owner assertion is introduced. The current UI does not render uncited facts as a separate block; a highlight with partly absent cited evidence keeps a one-line notice in its expanded content.
- **Consequences:** Technical Specification becomes 0.4.12, AC-080 is added, and old cache payloads without the new facts/title shape are invalidated and rebuilt. Local tests document the boundary; no live provider call or release acceptance is implied.

## ADR-061: Limit React Aria Components to the authenticated admin surface

- **Status:** Accepted 2026-10-14 (OR-035); implementation and verification are separate from release acceptance.
- **Authorization:** The owner approved plan item F and the admin-only React Aria scope on 2026-10-14. The client-only license supplement was added during implementation and still needs owner review before release.
- **Decision:** Add `react-aria-components@1.21.1` for the authenticated admin bundle only. Replace the approved `window.confirm` cases with a shared `ConfirmDialog` using React Aria `Modal`/`Dialog` with `alertdialog` semantics, Cancel autofocus, destructive confirmation styling, and explicit confirmation callbacks. Replace the hand-written display-settings `<details>` overlay and the Highlights privacy disclosure with React Aria `DialogTrigger`/`Popover`; retain native `<details>`, `<select>`, and specialized controls elsewhere. `client-only@0.0.1` (a transitive dependency) ships without license text although it declares MIT and points at the React project, so the Windows notices use a pinned supplement containing the MIT text of the installed `react@19.1.1` package, with its source and hash recorded.
- **Boundaries:** The visitor bundle does not import React Aria, no new admin/public endpoint or provider behavior is added, and browser focus/dismissal remains a browser-level verification item. Existing CSS variables and reduced-motion rules remain the style boundary.
- **CSP note (2026-10-15):** React Aria's runtime `<style>` injection is blocked by `style-src 'self'`; the CSP is unchanged, and the pressable `touch-action` rule is supplied statically in `styles.css`. Two residuals remain: one console CSP message per admin page load and no overscroll containment for confirmation dialogs in iOS Safari. Changing either requires an owner-approved CSP contract change.
- **Consequences:** Admin confirmation and popover markup gains shared accessible semantics while the visitor dependency surface remains unchanged. F's local tests cover authored markup and callbacks; a full browser/accessibility pass is still required before release acceptance.

## ADR-062: Owner-set Funnel ports in the gateway form

- **Status:** Accepted 2026-10-18 (owner-approved design); implementation verification is recorded separately from release acceptance.
- **Authorization:** The owner approved this gateway form change on 2026-10-18.
- **Decision:** The public Funnel HTTPS port stays part of the stored visitor origin, so the form only rewrites that origin (443 drops the explicit port). This adds no API field. The local visitor service port is stored in `visitor_gateway_settings.visitor_port` (runtime migration 36, nullable, 1024–65535); NULL falls back to `REPONPC_VISITOR_GATEWAY_PORT`. `PUT /api/admin/visitor-gateway` treats `visitor_port` as tri-state: omitted keeps the stored value, `null` clears it to the environment default, and an integer sets it. Changes are accepted only while the listener is stopped, must differ from the application port, and clear external verification.
- **Why:** The owner needs to avoid ports already used on the host, which a single environment default cannot do from the admin GUI.
- **Boundaries:** The listener still binds only `127.0.0.1`; no new error codes; the CSP, trial-mode logic and provider behavior are unchanged. Restore keeps the restored port value.
- **Consequences:** Clients that omit `visitor_port` keep the owner value. Any port change needs a fresh owner-reported external check before the entry is treated as verified.

## ADR-063: Model output cites only request-local evidence IDs

- **Status:** Accepted 2026-10-19 (owner-approved).
- **Authorization:** The owner approved the request-local evidence ID repair on 2026-10-19.
- **Why:** Diagnosis with qwen3.5:9b and qwen3.8:27b found 4 of 6 chat calls rejected because the model cited persistent `E_...` IDs exposed beside `S{n}` in evidence headers; replacing E IDs with the matching S IDs offline made the same outputs pass validation. Analysis had the inverse mismatch and produced `PROVIDER_EVIDENCE_ID_INVALID` in the clean-host run.
- **Decision:** Evidence headers expose only ordered request-local `S{n}` IDs plus existing metadata and escaped untrusted content. Chat and analysis structured-output schemas enumerate the request's allowed S IDs. Analysis prompts and examples use the same S IDs; after full validation the server maps them back to the ordered persistent IDs retained by context packing.
- **Boundaries:** Validation strictness is unchanged: unknown/unselected IDs still fail, and analysis rejects both persistent E IDs and unknown S IDs with `PROVIDER_EVIDENCE_ID_INVALID`. Stored and API `supporting_evidence_ids` remain persistent E IDs; no schema migration, provider fallback, CSP change, dependency or real-provider call is introduced. Empty chat selections preserve the existing no-match behavior without an empty schema enum.
- **Consequences:** Prompt-parsing fakes use request-local IDs. Provider adapters pass the schema enum through unchanged; local deterministic tests verify schema order, strict rejection and persistent-ID mapping. This repair does not establish live-provider or release acceptance.

## ADR-064: Owner-only closed reasons for chat no-match answers

- **Status:** Accepted; owner-approved 2026-10-19.
- **Context:** A live test produced an unexplained visitor abstention. Segment-drop diagnostics did not explain model abstention or envelope rejection.
- **Decision:** Carry a nullable internal `no_match_reason` through validated answers and chat delivery. The closed set is `MODEL_INSUFFICIENT_EVIDENCE`, `ENVELOPE_SCHEMA_INVALID`, `SOURCE_ID_UNKNOWN`, `MODEL_AUTHORED_MARKUP`, `INFERENCE_CYCLE`, `SELECTED_MAP_INVALID`, `ALL_SEGMENTS_DROPPED`, `VALIDATION_UNEXPECTED`, and `NO_EVIDENCE_SELECTED`. Integrity errors carry codes, never message-based classification. Answered and partial answers have no no-match reason; existing per-segment diagnostics remain.
- **Owner diagnostics:** Public chat and FAQ review emit INFO `chat.answer.no_match.<reason lowercased>` through SafeLogger with no fields. Migration 37 adds nullable CHECK-constrained `faq_entries.no_match_reason`; owner entry responses expose the code or null and the review panel shows one localized label. Regeneration clears the previous reason before generation and successful answers leave it null. `diagnostics_json` remains a list of `{segment_index, reason_codes}` and coverage-status logic is unchanged. Normal backup/restore preserves the column through the trusted schema.
- **Privacy boundary:** Only fixed codes enter these owner-only logs and review diagnostics. No question, answer, source/evidence ID, prompt, thinking, IP or session value is logged. The field/codes are excluded from public APIs, SSE, static exports and visitor browser assets. No daily statistics are added.
- **Compatibility:** Visitor text, suggestions, contact links, insufficiency flags, citations and SSE events are unchanged. Exhausted evidence budget uses `NO_EVIDENCE_SELECTED` without calling chat generation; an empty selected map still follows the existing model-call flow (model abstention takes precedence). Missing bundle/index remains the existing unavailable/503 path, not a no-match reply. No provider retry or fallback is added.
- **Requirements:** FR-043/044/046, NFR-012/014, AC-019/035/062/064/067; all existing acceptance thresholds remain.

## ADR-065: Visitor no-match reply polish

- **Status:** Accepted; owner-approved 2026-10-19. Requirements FR-011/014/022/044/047, NFR-008/009; AC-019/023/065/068.
- **Animation:** Completed no-match streams return to idle, matching offline FAQ non-answers; answered streams and approved FAQ answers keep success.
- **Copy:** Choose the unchanged long no-match text only when the final sanitized suggestion tuple is nonempty. Otherwise use 「這個問題我在作品集裡找不到相關內容。」 / "I couldn't find anything about that in this portfolio." Offline FAQ copy follows the same conditional promise.
- **Suggestions:** Keep in-turn buttons; omit the latest assistant turn's suggestion strings from the page-level list, hide its section and heading when empty, and restore the full list after an answered turn. Deduplicate each list; older in-turn buttons, keyboard/focus, admission and disabled behavior stay intact.
- **History:** Do not add no-match exchanges to model history. Existing limits, approved-FAQ exchanges and failed/cancelled-turn exclusions remain.
- **Boundaries:** Owner-only `no_match_reason`, contact links, citations, validation and SSE fields are unchanged. No frontend text matching, dependencies, CSP changes or provider calls are introduced.

## ADR-066: Visitor no-match kinds and ask-again

- **Status:** Accepted, owner-approved 2026-10-19.
- **Context:** A model-output integrity fault should not tell visitors that the portfolio has no relevant content. Preserve ADR-064 private diagnostics and ADR-065 no_content behavior.
- **Decision:** Classify every closed NoMatchReason in one exhaustive mapping in answers.py; a new unclassified reason fails the exhaustiveness test.

| Owner-only reason | Public kind |
| --- | --- |
| MODEL_INSUFFICIENT_EVIDENCE | no_content |
| NO_EVIDENCE_SELECTED | no_content |
| ALL_SEGMENTS_DROPPED | no_content |
| ENVELOPE_SCHEMA_INVALID | temporary |
| SOURCE_ID_UNKNOWN | temporary |
| MODEL_AUTHORED_MARKUP | temporary |
| INFERENCE_CYCLE | temporary |
| SELECTED_MAP_INVALID | temporary |
| VALIDATION_UNEXPECTED | temporary |

- **Public contract:** Only no-match complete events add no_match_kind: no_content | temporary. Answered events remain unchanged. Only the coarse kind is public; raw reason codes remain owner-only, absent from public APIs/SSE/exports. The visitor gateway preserves the field for local and Pages live chat.
- **Copy and action:** no_content keeps byte-identical ADR-065 long/short copy selected by sanitized suggestions and its optional contact route. Temporary uses zh-TW 「這次沒能整理出可靠的回答，請再問一次。」 / en "I couldn't put together a reliable answer this time. Please ask again.", empty suggestions and no contact link. Both keep insufficient_evidence=true and empty citations. The frontend accepts only the exact two kinds, defaulting absent/unknown values to no_content. Temporary adds one accessible 「再問一次」 / "Ask again" button via existing retryQuestion/onRetry, submitting the same question; disabled while pending or chat is unavailable. Both kinds return the character to idle and stay out of history. Temporary does not suppress page-level suggestions. Offline FAQ remains unchanged.
- **Owner FAQ:** answer_for_review stores the temporary localized text as answer_markdown with the same owner-only reason and no_relevant_content coverage status. Existing explicit review, active-bundle and export gates are unchanged; this does not introduce auto-approval or additional export capability.
- **Retry boundary:** No automatic backend retry is added. Automatic retry is deferred until ADR-064 logs show how often temporary failures happen.
- **Delivery:** Pages visitors receive the new frontend only after the owner re-exports and re-uploads the static site.
- **Boundaries:** No model, citation or validation changes, provider fallback, dependency, CSP change or real-model call.

## ADR-067: Apply REPONPC_LOG_LEVEL and give the installer a log file

- **Status:** Accepted; owner-approved 2026-10-19.
- **Why:** REPONPC_LOG_LEVEL was parsed but never applied and the reponpc logger had no handler. Python's last-resort WARNING threshold dropped the INFO diagnostics added by ADR-064, including real-server no-match events; pytest capture concealed the missing sink.
- **Decision:** prepare_application configures the reponpc logger at settings.log_level with one message-only stderr handler and propagation disabled. Idempotent configuration replaces only its marked handlers and preserves foreign handlers. App import remains side-effect-free. The source launcher captures stderr in its server .err.log; Docker sends it to docker logs; the in-process visitor gateway shares the same configuration.
- **Installer:** Move its RepoNPC level from WARNING to INFO and also write data_dir/logs/reponpc.log as UTF-8, with maxBytes=1,048,576 and backupCount=3 (one active file plus three backups, approximately 4 MiB total). Preserve this sink when maintenance rebuilds the application. Uvicorn remains warning with access_log=False.
- **Privacy:** What is logged is unchanged: SafeLogger sanitization, event names, levels and allowlisted fields stay intact. No question, answer, source/evidence ID, IP, prompt, thinking or secret is added. Maintenance SQLite backups and allowlisted static exports do not include the logs directory; the existing private full-data-directory backup procedure does.
- **Requirements:** NFR-012/014 and AC-035; enables the existing ADR-064 diagnostics for FR-043/044/046 and AC-019/062/064/067 without changing their acceptance thresholds.

## ADR-068: Report source failures and retry time when preparing the local NPC

- **Status:** Accepted; owner-approved 2026-10-20.
- **Why:** Local NPC preparation could report a GitHub safety-reserve refusal as `EMBEDDING_REINDEX_FAILED`, discard its retry time and overwrite the embedding model's successful probe state. This incorrectly demanded another model test before retrying a source operation.
- **Decision:** Classify by exception type plus code, never exception text. The closed source-failure set is `GITHUB_RATE_LIMITED`, `GITHUB_ERROR`, `GITHUB_TIMEOUT`, `NOT_FOUND`, `ARCHIVED_NOT_ALLOWED`, `ARCHIVE_TOO_LARGE`, `ARCHIVE_INVALID` and `ARCHIVE_UNSAFE`. `BatchResolverError` accepts these codes directly; `SourceResolutionError` also maps `github_rate_limited`, `github_request_failed`, `github_timeout` and `github_not_found` to their equivalent codes. Other codes keep their existing mappings. Safe logs include the source code as both `code` and `cause`, with code locations only and no exception text.
- **Scope:** Only `LocalPublication.prepare` explicitly opts into `queue(..., source_failures_reported_by_caller=True)`. For a classified source failure, the inactive candidate returns to `reindex_required` with `last_error_code` and `last_error_message` null and its probe fields unchanged; the publication receipt owns the failure. Retrying preparation needs no new probe. The 「重建並啟用」 / `operations.activate_embedding_profile` path intentionally keeps writing its failure into the shared profile error field (the stored value is now the classified source code instead of `EMBEDDING_REINDEX_FAILED`; the card text is unchanged); separating that path's probe and job errors would require a follow-up schema change. No migration or new database column is added. Model, bundle and activation failure handling and last-known-good protection are unchanged.
- **Retry contract:** `GET /api/admin/portfolio/status`, prepare and cancel status responses always include `retry_at`, an ISO-8601 UTC string or null. For a classified source error carrying typed `retry_after_seconds`, compute now plus that delay, rounded up to whole seconds, using the coordinator's injectable clock. A frozen completion outcome carries bundle ID, safe error code and nullable retry time to the existing `publication.json` receipt. Reload preserves it; a new preparation, successful completion or interrupted-job recovery clears it. Metadata blockers retain typed retry seconds internally; the preflight API still serializes only `{slug, code}`.
- **Boundaries:** The 25-request safety reserve, `admit` / `admit_cost` admission semantics and all limiter math are unchanged. No automatic retry, model retest, provider fallback, new status store or Maintenance-page change is introduced. Both owner locales show a short source-specific message and the existing batch retry-duration wording only while the retry time is in the future.
- **Requirements:** FR-035/040/042, NFR-003/012/014 and AC-035/053/055/057/060; existing acceptance thresholds remain unchanged.

## ADR-069: Name failing environment variables in startup errors

- **Status:** Accepted; owner-approved 2026-10-20.
- **Why:** A Windows Docker Desktop secret bind mount can fail Linux permission validation, but the generic startup error gave no variable or cause to fix.
- **Decision:** One shared formatter beside EnvironmentValidationError emits `deployment environment is invalid: NAME (code), NAME (code)`, deduplicated and sorted by name then code. The production entrypoint and Windows launcher's validation use it; CLI subcommands retain `reponpc: deployment_environment_invalid` followed by the same list and exit code 2. The launcher includes the formatted error and one short `.env` recovery sentence.
- **Privacy:** Read only issue name and code, never `message`, values or paths. Fully match names against `^[A-Z][A-Z0-9_]*$` and codes against `^[a-z][a-z0-9_]*$` (including rejecting a trailing newline); replace invalid fields with fixed `UNKNOWN_VARIABLE` / `unknown_code` before deduplication and sorting. An unknown REPONPC_* variable is still only a name, subject to the same check. Secret permission checks and environment validation are unchanged.
- **Requirements:** FR-036, NFR-002/003/010/012 and AC-001/035/036. Regression tests preserve canary exclusion and verify exact text, duplicate/order handling, malformed fields and CLI exit behavior; existing acceptance thresholds remain unchanged.

## ADR-070: Windows production mode on the owner's own computer

- **Status:** Accepted; owner-approved 2026-10-20 with decisions D1–D7 as recommended in [the Windows production plan](WINDOWS_PRODUCTION_PLAN_2026-10-20.md). W1, W2 and W3 are implemented; the real-host test is pending.
- **Why:** ADR-048 and the A1 gateway contract approve a Windows installation whose owner enables Funnel, but both Windows entry points force `loopback_evaluation`, and the visitor gateway starts only in `production`. Windows also skips every private-file permission check: secret files, `model-secrets/master.key`, the IP key and the 0600/0700 writes are enforced only where POSIX modes exist. A data directory inside a checkout inherits `Authenticated Users` and `Users` access from a non-system drive root.
- **Decision:** Windows production is the existing `production` profile with:
  - the application on `127.0.0.1`;
  - the explicit admin origin `http://localhost:<port>`;
  - the visitor gateway on `127.0.0.1`;
  - Funnel pointed only at the gateway.

  The owner decided the following:
  - **D1:** both the installer and the source launcher support Windows production mode.
  - **D2:** the source launcher honours `REPONPC_DEPLOYMENT_PROFILE` from `.env`; the installer adds a 「RepoNPC（正式模式）」 shortcut passing `--profile production`. Nothing upgrades automatically.
  - **D3:** the launcher prints a host setup code (ADR-016) for a new data directory, or runs the host-only `set-password` console flow for a passwordless trial owner, before opening the browser. The production password policy (ADR-024) applies.
  - **D6:** in both profiles, `REPONPC_CONFIG_REPOSITORY` and `REPONPC_INDEX_MANIFEST_URL` may be empty; the runtime then does not poll. Moot after ADR-071: the variables no longer exist.
  - **D7:** Windows production rejects direct secret values from `.env`.
- **Private files:** One shared helper creates and checks owner-only files and directories, replacing the per-module POSIX-only checks.
  - **D4:** on Windows, it uses advapi32 through ctypes, with no new dependency. The DACL may grant access only to the current user, SYSTEM and Administrators. Inheritance is disabled at creation, and an allow entry for any other account, explicit or inherited, is rejected. Windows enforces the check only in `production`, so existing trial data keeps working; POSIX checks are unchanged.
  - It applies to secret files (`unsafe_secret_permissions`), the model secret key (`MODEL_SECRET_STORAGE_UNAVAILABLE`) and, in Windows production, the data directory root (`REPONPC_DATA_DIR` with the existing `unsafe_secret_permissions`).
  - The Windows secret root defaults to `<data_dir>\private`. Launchers pass `_FILE` paths instead of copying secret values into the environment.
  - **D5:** for an existing over-broad data directory, the launcher stops and shows one `icacls` command for the owner to run; it does not change ACLs itself. The command is built from the path's DACL: the data directory root gets the protected three-account grant plus `/remove:g` for any other explicit account; a child path under an owner-only root gets `/reset /T`.
- **Boundaries:**
  - No new profile, public bind, API field, error code or Tailscale automation.
  - Windows Docker Desktop production, Windows services and non-loopback administration remain unsupported.
  - Administrators on the host can always read the data.
- **Consequences:**
  - README/OPERATIONS describe Windows production mode since W3 (2026-10-22); before that they kept the ADR-069 trial-only wording.
  - AC-081 adds the Windows production acceptance; external Funnel evidence stays under A12.
  - FR-048 gains the production option.
- **Requirements:** FR-017/029/047/048, NFR-002/003, AC-069/071 and new AC-081.

## ADR-071: Archive legacy paths and documents

- **Status:** Accepted 2026-10-20 (owner).
- **Decision:** Archive the obsolete paths listed in [legacy/README.md](../legacy/README.md) under `legacy/`; archived code is not imported. The README card links only to the verified Pages chat page. Historical handoffs and fully superseded ADRs and ACs move to `legacy/docs/`; superseded ADRs and ACs keep one-line stubs.
- **Supersedes:** ADR-005, ADR-010, ADR-020 and ADR-022 in full. It also supersedes the GitHub writeback, GitHub Release publication, remote manifest polling and operator-managed visitor URL clauses of ADR-009, ADR-015, ADR-016, ADR-018, ADR-021, ADR-027, ADR-028, ADR-040, ADR-042 through ADR-047 and ADR-070; their other decisions remain in force.
- **Consequences:** Removed `REPONPC_*` names are rejected as unknown, so existing `.env` files must delete them. ADR-070 D6 is moot.

## ADR-072: Pixel RPG interface for the visitor chat and owner pages

- **Status:** Accepted 2026-10-23; the owner approved D1–D8 as recommended in [the pixel UI plan](PIXEL_UI_PLAN_2026-10-23.md) (「D1–D8 全部照建議選項，核准 ADR-072」). Technical Specification 0.4.14 and AC-082 apply it. Implementation phases P0–P4 are pending. ADR-077 (2026-11-03) brings the README card into the pixel style; the plan's card exclusion no longer applies.
- **Authorization:** On 2026-10-22 the owner said the current UI is too ugly and asked for several design sets, allowing a UI component library. On 2026-10-23 the owner chose the prototypes in `output/mockups/ui-pixel-2026-10-23/`:
  - Set C "Pixel Guild" for the visitor chat, with visitor-selectable colour schemes and dark mode;
  - Set F "Pixel Workshop" for the owner settings and character pages.

  The owner then asked for this ADR and a plan, covering the Tailwind + daisyUI dependency and the change to ADR-051, before implementation.
- **Context:**
  - ADR-051 (implemented, AC-068/072–075 revised) requires flat colours, no drawn backdrop, an owner-only scheme choice and no literal colours in visitor source. The build guard `scripts/check_visitor_source.mjs` enforces the last rule.
  - The chosen design conflicts with three ADR-051 clauses:
    - it draws a pixel scene (sky, hills, grass, signpost) behind the NPC;
    - visitors choose a palette;
    - the chat layout differs from the FR-047 layout sentence (scene and RPG dialogue box beside a conversation log; projects in a drawer).
  - The prototypes target daisyUI 5 on Tailwind v4, loaded from CDNs. Production cannot use CDNs or Google Fonts: the CSP is `style-src 'self'; font-src 'self'` for both the app and the exported Pages site.
- **Decision (owner-approved recommended options; the rejected alternatives are in the plan):**
  - **D1 Styling stack:** no new UI dependency. Build a small pixel design system in project CSS: tokens, stepped borders, offset shadows and a few primitives. React Aria stays the admin behaviour layer (ADR-061). Reasons:
    - daisyUI themes ship literal colours and their own theme switch, which duplicate `color_schemes.yml` and break the colour guard;
    - its component class names collide with project classes (the prototype `.stack` overlap);
    - most of its rounded components would be overridden for the pixel look anyway.

    The alternatives are Tailwind v4 + daisyUI 5 as build-time `devDependencies` via `@tailwindcss/vite` (D1-b) or Tailwind only (D1-c). Either needs ADR-012 lockfile updates, notices, and guard and CSP checks.
  - **D2 Visitor scheme choice:** add `visitor_scheme_choice` (default `true`). Visitors may pick any registry scheme; the owner's `color_scheme` remains the default. The choice is stored only in that browser's `localStorage` and applied before first paint by the existing same-origin mode script. It is never sent, exported or set as a cookie. The export carries the resolved tokens of every scheme, not only the selected one.
  - **D3 Drawn scene:**
    - **Scene:** allow one character-agnostic pixel scene drawn with CSS, coloured only by scheme tokens.
    - **Limits:** no image files, no per-scheme drawing code and no branch on a scheme id.
    - **Owner image:** when set (FR-052), it replaces the drawn scene inside the same stage frame.
    - **NPC separation:** the check runs against the scene colours directly behind the NPC. When that fails, a pixel plate is drawn; text colours never change.
  - **D4 Schemes:** replace the starter set with pixel palettes `meadow` (default), `sunset`, `coast` and `sakura`. Each has a designed light (day) and dark (night) variant.
    - **Scene roles:** add `sky`, `horizon`, `hill_far`, `hill_near`, `grass`, `ground`, `wood` and `celestial`. They are decorative; each pair of adjacent layers (`sky`/`hill_far`, `hill_far`/`hill_near`, `hill_near`/`grass`, `grass`/`ground`, `celestial`/`sky`, `wood`/`sky`) must reach 1.5:1, so the scene stays legible.
    - **Contrast:** the existing text and non-text pairs keep their thresholds.
    - **Aliases:** `neutral`→`meadow`, `forest`→`meadow`, `ocean`→`coast`, `lavender`→`sakura`; `sunset` is re-versioned. No migration is needed.
  - **D5 Fonts:** self-host Press Start 2P (SIL OFL 1.1, Latin glyphs only) for the brand, Latin headings, numbers and buttons. Chinese and body text use the system font stack. There is no web-font download for CJK and no Google Fonts.
  - **D6 Layout:** revise the FR-047 layout sentence to the Set C layout:
    - **Desktop:** the scene stage and RPG dialogue box beside the conversation log, with the composer pinned; projects and the profile in a 「專案」 drawer that still shows name, description, language, stars and forks.
    - **Phones:** a compact scene strip, the log taking the remaining height, and one 「外觀」 control.
  - **D7 Owner pages:** the Set F language applies to every owner page:
    - quest list for the six setup steps;
    - 裝備欄 model cards;
    - character-creation screen for the character page.

    The models and character pages follow the approved mockups. The other pages are restyled with the same primitives and reviewed by the owner from real screenshots before commit, without separate mockups.
  - **D8 G-round copy:** fold the approved G-round text-reduction rules into the restyle of each page instead of a later separate round.
- **Boundaries:**
  - No new endpoint, error code or provider behaviour. The only new public data are the resolved tokens of every registry scheme (already public registry data) and the `visitor_scheme_choice` flag.
  - No change to CSP, the visitor dependency closure guard or ADR-061's admin-only React Aria scope.
  - Accessibility, reduced motion and zh-TW/en parity stay release gates. The pixel font is decorative only and never used for body text or inputs.
  - The prototype "設計狀態" switcher, the CDN builds and the demo data are not shipped.
- **Consequences:**
  - Technical Specification 0.4.14 revises FR-047 (layout), FR-050 (scene roles and plate) and FR-051 (visitor scheme choice, drawn scene), and §12.3 and §16.
  - New AC-082 covers the pixel interface. AC-068 and AC-072–AC-075 are revised.
  - ADR-051's clauses on flat colours, no drawn backdrop and owner-only scheme choice are superseded. Its other clauses (registry data, closed roles, AA validation, mode script, NPC follows the character) remain in force.
- **Requirements:** FR-047/050/051/052, NFR-001/009/011, AC-068/072–075 and new AC-082.

## ADR-073: Raise the contribution-suggestion output allowance to 16,384

- **Status:** Accepted 2026-10-28. Technical Specification 0.4.15.
- **Authorization:** After a flow walk (2026-10-28) the owner reviewed three options (larger allowance, `think: false`, clearer error only) and said 「本來就應該加大額度」.
- **Context:** ADR-034/037 fixed the contribution allowance at 700 tokens; ADR-055 later set reasoning ON and a 16,384 ceiling for chat/probe and analysis, but did not mention contribution suggestions. With a reasoning model, thinking and answer share one allowance, so 700 tokens end before any answer.
- **Evidence:** Real walk, Ollama `qwen3.5:9b` (reasoning supported, `think: true` sent): "產生可編輯建議" returned `PROVIDER_OUTPUT_LIMIT_REACHED` twice. Direct requests with the application's real contribution prompt and schema (short and medium owner statements):
  - reasoning ON, 700 tokens: `done_reason=length`, empty content, in 7 seconds;
  - reasoning ON, 8,192 tokens: finished with 5,181 and 5,233 tokens in about 50 seconds;
  - `think: false`, 700 tokens: finished with 92 and 398 tokens in 1 to 4 seconds.
- **Decision:** Set the fixed contribution allowance to 16,384 tokens, the same ceiling as ADR-055. It stays independent of the visitor and analysis budgets and has no new setting. Reasoning stays ON (ADR-055 is unchanged). Output-limit termination still fails before parsing, with no retry, fallback or partial promotion.
- **Rejected:** Sending `think: false` for this call (conflicts with the ADR-055 owner decision; not evaluated against the person-claim safety rules); changing only the error text (leaves the AI proposal unusable with the reference model of ADR-055).
- **Consequences:**
  - A reasoning model can take about a minute for one suggestion and holds the shared generation slot for that time. The 180-second chat timeout applied at this decision; its numbers are superseded by ADR-076 (300-default / 600-maximum).
  - With a configured context below 32,768 the allowance shrinks to half of the context at most, and to what the request leaves free. The request is counted as escaped JSON (six bytes per CJK character), as the Ollama adapter counts it, so a long Chinese statement is not rejected where 700 tokens worked. Only when nothing is left does the request fail safely before any provider call; manual entry stays available.
  - The limit message no longer tells the owner to shorten the statement first. It says the limit includes thinking, offers retry or manual entry, and suggests a model that thinks less if it keeps happening.
  - Only the 700 value of ADR-034/037 is superseded. The other contribution rules stay.
- **Requirements:** FR-012/027/033/038/040/041, NFR-002/003/011/012/014, AC-023/039/054/055/057/061 (value change only).

## ADR-074: Extend the Chat probe deadline to 60 seconds

- **Status:** Accepted 2026-10-30. Technical Specification 0.4.16.
- **Authorization:** For ADR-074, the owner said the 20-second model-test limit was too short and asked for at least 30 to 60 seconds (chat, 2026-10-30). The main agent chose 60 seconds, the top of that range.
- **Context:** ADR-036 established a 10-second baseline plus one 10-second grace window, a 20-second total. ADR-074 extends that limit because a local model must load on first use and can exceed it.
- **Decision:** Use one 60-second total deadline for the same single request. ADR-036's numbers are superseded; its rule of one non-duplicating request remains. There is no second billable request, activation, or provider/model fallback. Bounded Ollama capability preparation still consumes the same outer deadline; generation receives only the remaining time.
- **Consequences:**
  - Technical Specification advances to 0.4.16. FR-038/040 and AC-054/057 cover a valid response before 60 seconds, final timeout when the 60-second deadline is reached, and regression evidence that only one request is made.
  - No environment variable, API, database migration, UI copy, or new provider call is added.
- **Requirements:** FR-038/040, AC-054/057 (deadline change only).

## ADR-075: Explain empty GitHub projects as a permanent source failure

- **Status:** Accepted 2026-11-01. Technical Specification 0.4.17.
- **Authorization:** On 2026-11-01 the owner said "just directly showing a prompt like 'GitHub repository is an empty project' should be enough" and approved `EMPTY_REPOSITORY` and the bilingual text in the wrap-up brief.
- **Context:** GitHub commit lookup returns `409` with JSON `message: "Git Repository is empty."`. Treating it as `GITHUB_ERROR` describes an outage and invites retries that cannot add repository content.
- **Evidence:** Two anonymous public reads on 2026-11-01 confirmed `/repos/xu-0306/xu-0306/commits/main` returns that 409 JSON; `/tarball/main` returns a codeload redirect. Classification is shared by metadata/commit/source and archive HTTP errors, without any repository-specific branch.
- **Decision:** A 409 whose JSON string message, stripped and case-insensitive, contains `git repository is empty` maps to permanent `EMPTY_REPOSITORY`. Malformed/non-JSON bodies, other conflicts and other statuses retain their existing safe codes. Preflight consumes partial hints, reports the selected repository blocker and does not retry; source errors remain typed through onboarding, batch, NPC preparation and embedding reindex. Error envelopes use 422; preflight/job status keeps its existing payload and HTTP status. No retry timestamp is added; same-round retry and successor reanalysis are unavailable for the confirmed empty source.
- **Copy:** zh-TW: 「這個 GitHub repository 是空專案，沒有內容可以分析。請改選其他專案。」 en: "This GitHub repository is an empty project, so there is nothing to analyze. Choose another project." Every affected surface shows this plain text without a raw code or temporary-retry advice.
- **Consequences:** Keep the existing zero-size discovery hint and allow selection. No source/model call follows an empty-project blocker, no fallback or automatic retry is introduced, and last-known-good data remains active. Regression tests cover normalized messages, wrong status/shape, malformed bytes, propagation, permanent failure and both locales.
- **Requirements:** FR-002/026/027/032/033, NFR-001/002/011/012/014, AC-023/039/040/044/045/052.

## ADR-076: Raise chat deadline and optional output ceiling without increasing default context

- **Status:** Accepted 2026-11-01. Technical Specification 0.4.18.
- **Authorization:** On 2026-11-01 the owner said "The chat limit can be raised." The wrap-up brief explicitly approved the numbers below; no other contract changes are authorized.
- **Context:** A reasoning model spends most of its generation budget on hidden thinking. Measured 6,784 generated tokens took about 69 seconds on GPU; 16,384 tokens at about 98 tok/s take about 167 seconds before other request work. The old 180-second total deadline cannot reliably cover a full-budget answer; CPU-only hosts need far more time.
- **Decision:**

  | Setting | Default | Maximum |
  | --- | ---: | ---: |
  | `REPONPC_CHAT_TIMEOUT_SECONDS` | 300 seconds | 600 seconds |
  | `REPONPC_CHAT_MAX_OUTPUT_TOKENS` | 16384 (unchanged) | 32768 |
  | `REPONPC_CHAT_MAX_CONTEXT_TOKENS` | 32768 (unchanged) | provider capacity (unchanged) |
  | `REPONPC_ANALYSIS_MAX_OUTPUT_TOKENS` | 16384 (unchanged) | 16384 (unchanged) |

  `ANALYSIS_MAX_OUTPUT_TOKENS_HARD_LIMIT` and `CONTRIBUTION_MAX_OUTPUT_TOKENS` remain 16384. The ADR-074 single chat probe still has one 60-second deadline; embedding probes and analysis deadlines remain unchanged. Reasoning stays ON; `think` handling is unchanged. Existing explicit lower settings are retained.
- **Rejected:** Raising default context, because Ollama's `num_ctx` drives VRAM use on every install; raising default output, because the unchanged default context must leave room for input and evidence. Disabling reasoning is not approved.
- **Consequences:** Configured profiles, probes and all chat transports admit up to 32768 output only with sufficient explicitly configured context. Output at or above context fails with the existing configuration/capability error before any provider call; manual/non-AI startup remains available. Public ingress and generation share the configured total deadline; SSE keepalive/progress never renew it. Client progress and public-summary elapsed validation accepts through 600,000 ms so the maximum-budget stream can complete. Longer requests hold bounded worker capacity longer; unchanged concurrency, daily and input limits still apply. Operators must allow the total deadline plus margin through their actual Funnel/proxy path and restart matching frontend/backend. No new setting, endpoint, schema, service, migration or fallback is added. Historical ADR-055/057 chat ceiling/timeout numbers are superseded; their other controls and ADR-073 contribution budget remain in force.
- **Requirements:** FR-012/013/038/040/043/044/047, NFR-002/003/005/009/011/012/014, AC-015/017/018/019/023/039/054/055/057/061/068/071.

## ADR-077: Pixel-style README card (Scene template)

- **Status:** Accepted 2026-11-03. Technical Specification 0.4.19.
- **Authorization:** On 2026-11-03 the owner asked to unify every card template into the pixel style, reviewed four prototypes, chose variant B ("選 B", the Scene template) and approved this ADR as recommended in the wrap-up ("核准並開工").
- **Context:** The README card (SVG/GIF/PNG, `src/reponpc/cards/render.py`) was excluded from ADR-072 by `docs/PIXEL_UI_PLAN_2026-10-23.md` and still used the old template. Measured on 2026-11-03: the PNG had 406–429 colours, 251 of them anti-aliased text colours; frame radius 12 and button radius 7; smooth Noto text; the SVG carried `<text>` and about 100 KB of sprite rectangles; the default light call to action was 4.467:1 (NFR-009 needs 4.5:1). The old look was an implementation value, not an accepted visual threshold: FR-016/AC-021 and Technical Specification 12.2 fix size, formats, first-frame content and safety only.
- **Decision:**
  1. **Template.** The card is the pixel "Scene" template: 600 × 180; 4 px notched frame; left 180 × 160 scene band (sky, stepped sun, two cloud blocks, two stepped hill layers, 24 px ground with a 4 px line); character at 2× nearest-neighbour; name with a 2 px shadow; headline; a menu-bar call to action (label in panel colour on a text-colour bar) whose cursor blinks on even frames; right-aligned repository count. The character bobs 2 px on odd frames. Every pixel of PNG and GIF is one flat colour: no anti-aliased text, no interpolation, character alpha thresholded at 128.
  2. **Palette.** `card.themes` stays five explicit colours (`background`, `panel`, `text`, `accent`, `border`); saved themes are not migrated. Five more colours are derived by fixed integer mixes (`shade`, `soft`, `tint`, `hill_far`, `hill_near`). `accent` is decorative only (the sun); text pairs are `text`/`panel` and `panel`/`text`. New defaults: light `#f2e9d9 / #fff9ed / #322b2b / #9b3c21 / #44362e`; dark `#1d1814 / #2a221d / #f2e9d9 / #e9b452 / #c9b48e` (text on panel 13.21:1 and 12.96:1).
  3. **Fonts.** Latin-only names use Press Start 2P at 16 px (the web font, SIL OFL 1.1, copied into the Python package and wheel); other text uses the existing Noto Sans CJK TC at 14–16 px with anti-aliasing off. No new font or dependency.
  4. **SVG.** The SVG is the first frame as lossless pixel rectangles (`<path>` runs) with `<title>`/`<desc>` for the accessible name. It has no `<text>`, font, style, animation, script, handler or remote reference, so every viewer shows the same pixels (about 20 KB instead of about 100 KB). It is static; SPRITE_FORMAT section 7 already allows deterministic vector rectangles.
  5. **Unchanged.** 600 × 180, PNG/GIF/SVG, GIF four frames at 240 ms by default (80–1000 ms), one frame when animation is disabled, file names, URLs, README snippet strings and alt texts, endpoints, private preview protection, SHA/manifest verification and the manual upload flow. No GitHub write permission is added.
  6. **Scope.** This ADR covers the README card and its derived outputs. The remaining non-pixel admin panels (focus-preview gradient, built-in model and guidance panels, advanced model service/Chat/Embedding cards) are fixed under ADR-072/AC-082 in a separate change. Done 2026-11-03 (CSS only, no contract change): the owner allowed old-style panels to be retired or moved to `legacy/`; every one of them proved live, so they were restyled, not removed, and nothing moved. `apps/web/src` no longer defines the legacy `--ui-*`/`--admin-*` colour tokens, non-zero radii, soft shadows, colour literals outside the `--px-*` definitions or non-pixel gradients; `legacyStyles.test.js` keeps this from returning. The dead `.suggestion-list`, `.profile-headline` and `.profile-links` rules were deleted.
- **Rejected:** The Dialog, Badge and Quiet prototypes; a DOM component library, because the card is a server-rendered raster/SVG file; a pixel CJK font, because it adds a new font and licence (may be proposed later); text-based SVG, because viewer fonts differ.
- **Consequences:** Every card asset hash changes. The owner must rebuild, export, upload and re-verify; GitHub keeps showing the old image until then. CJK text is 1-bit Noto and looks coarse at 14 px; semi-transparent sprite edges become solid. Existing explicit `card.themes` keep working, but their accent now colours only the sun and tints. The 4.467:1 default call-to-action defect disappears with the new defaults. Tests change from old-look expectations to hard-edge pixel expectations without loosening any assertion.
- **Requirements:** FR-016/024, NFR-001/009, AC-021/022/028/082; amends the card exclusion of ADR-072 and the card appearance under ADR-002/008/051/059.

## ADR-078: Language registry, browser-language defaults and one-click profile translation (phase A)

- **Status:** Accepted 2026-11-03. Technical Specification 0.4.20.
- **Authorization:** On 2026-11-03 the owner asked for a one-click translation on the guided profile step, for English-native owners to be able to leave the zh-TW column blank, and for other languages (Simplified Chinese, Spanish) to be possible later. The owner called the fixed zh-TW/en pair a design defect, allowed a deterministic Simplified/Traditional conversion package, required that machine translation stay editable, and chose: content languages are an owner choice of one or more registry entries, browser language sets the admin and visitor defaults, languages without a hand-written UI catalog fall back to English chrome, and phase A ships before phase B. The owner also allowed parallel Codex workers. This ADR is phase A only; phase B (ADR-079) is not approved by it. The owner approved the ADR as written on 2026-11-03 (「核准並派工」).
- **Context:** Measured 2026-11-03: admin and visitor locale start as a fixed `useState("zh-TW")` (`App.tsx`, `VisitorApp.tsx`) and never read `navigator.languages`; the profile step renders exactly two columns `["zh-TW","en"]` in a fixed order with the label chosen by the UI language; `profileIsComplete` needs all eight values; `_LOCALE_BASE_SCRIPTS` in `admin/onboarding.py` repeats the same pair as code. FR-028 already treats translation suggestions as unconfirmed proposals but no translation action exists.
- **Decision:**
  1. **Registry.** One data file `src/reponpc/i18n/languages.json`, validated at load, is the only list of languages. Each entry has `tag` (BCP-47), `endonym`, `scripts` (Unicode script names whose words are allowed in that language, replacing `_LOCALE_BASE_SCRIPTS`), `direction` and `match` (lower-case tag prefixes used to match browser tags). Phase A contains exactly `zh-TW` (`zh-tw`, `zh-hk`, `zh-mo`, `zh-hant`, `zh`; endonym 繁體中文) and `en` (`en`; endonym English). A TypeScript module mirrors it, and a contract test fails if the two differ. `LocalesConfig`, YAML, bundles and every public API stay zh-TW + en exactly; phase B relaxes that.
  2. **Labels and order.** Every language column is labelled with its endonym, identical for all viewers, never with a translation into the UI language. The profile step lists the column of the current admin language first. Stored data and YAML key order do not change.
  3. **Browser language.** Initial admin and visitor locale is the first entry of `navigator.languages` that matches a supported entry by the longest `match` prefix; when none matches the current default zh-TW stays. A locale the person picks is saved in `localStorage` (`reponpc.locale`, read and written inside try/catch) and wins over the browser. Nothing is sent to the server and `<html lang>` keeps following the locale.
  4. **Blank side.** While editing, either language of headline, bio and greeting may be empty. The step's confirm button and its draft step still require every value, exactly as `profileIsComplete` does today, and its disabled reason points to the translate action. Stored data is therefore always complete.
  5. **Translate API.** `POST /api/admin/onboarding/profile/translate`, same session, same-origin and CSRF rules as `contributions/suggest`. Request `{ "items": [{ "field": "headline" | "bio" | "greeting", "source_locale": tag, "target_locale": tag, "text": 1..2000 characters }] }` with 1 to 6 items and unique `(field, target_locale)`. Both tags must be registry entries and differ. The direction is given by the client from the column that holds text; the server never guesses it from the script. Response `{ "items": [{ "field", "target_locale", "text", "method": "model", "confirmed": false }] }`. One provider call covers all items with a JSON schema that returns one string per item in request order. Server checks: equal item count, non-empty, at most 2000 characters, words only in the target locale's registry scripts plus the source text's scripts, and every URL, backtick code span, `@handle` and `owner/repo` slug of the source present verbatim. A failed check is `PROVIDER_ERROR` with reason `PROVIDER_OUTPUT_SCHEMA_INVALID` and fills nothing. The prompt treats the text as untrusted data, forbids adding, removing or strengthening claims, roles, authorship or numbers, and keeps names, code and URLs unchanged. The active accepted chat model is used with the existing generation limit, session operation and output-budget helpers; no tools, no retry, no provider fallback, and the text is not logged or stored. New error codes: none (existing validation, model and limit codes are reused).
  6. **Form.** The translate action has two forms: a section button that fills only empty targets from the filled sides, and a per-field action that retranslates a filled target after the existing confirm dialog. The result is placed into the textarea as an editable proposal. A filled-by-translation field shows "自動翻譯，尚未檢視" / "Machine translated, not reviewed yet" until the owner edits it or marks it reviewed; each such field offers "還原翻譯前" / "Restore previous text" (which can restore an empty value). The review step shows how many fields are unreviewed and never blocks. The marker and the previous text live only in component state. A response for a field whose source changed after the request started is discarded. The action is disabled with a visible reason while no chat model is accepted, and failures show the existing plain-language error copy in both locales. Status changes use a live region, focus stays on the action, and keyboard use is unchanged.
  7. **Scope.** Phase A covers headline, bio and greeting on the profile step only. Contribution proposals (role, summary, claims), FAQ and every other bilingual field keep their current flow. No deterministic conversion and no third language ship in phase A.
- **Rejected:** Detecting the source language from its script or by keyword (it breaks for mixed text and for any new language; the filled column is the structural signal); browser-built-in translation APIs (not available in every browser, and the model path already exists); storing the unreviewed marker in YAML (it would add a schema field for UI state); blocking confirmation on unreviewed fields (the owner may legitimately accept the translation).
- **Consequences:** One new admin endpoint, one new data file and one new web module; no schema, YAML, bundle, migration, dependency, setting or hosted service change. First-time visitors whose browser prefers English now see English instead of zh-TW; web tests that assumed the fixed default must set `navigator.languages` explicitly. A translated text is a model output shown only after the owner chooses to use it, and it becomes `OWNER_ASSERTION` only when the owner confirms the step (FR-028). Phase B (ADR-079) will make the language set configurable, add zh-CN through a deterministic conversion package, allow single-language sites and add es; it needs its own approval, spec and bundle version bump.
- **Requirements:** FR-028, FR-041/042, FR-054 (new), NFR-001/003/009/011/012/014, AC-055/060, AC-083 (registry parity and matching), AC-084 (translate API validation, security, no fallback), AC-085 (form: translate, edit, unreviewed marker, restore, stale response), AC-086 (browser-language defaults and stored choice).

## ADR-079: Configurable site languages, zh-CN by deterministic conversion, and es (phase B)

- **Status:** Accepted 2026-11-03. Technical Specification 0.5.0.
- **Authorization:** On 2026-11-03 the owner chose the direction (content languages are an owner choice of one or more registry entries, a deterministic Simplified/Traditional conversion package is allowed, languages without a hand-written UI catalog fall back to English chrome, phase A before phase B). After phase A shipped (origin/main `b40be85`) the owner said to continue with phase B (「好，可以繼續實作B階段」), was shown the contract, schema, dependency and safety-data points below, and approved the ADR as written on 2026-11-03 (「Approve and dispatch」). Parallel Codex workers are allowed by the owner's 2026-11-03 instruction.
- **Context:** Measured 2026-11-03. `LocalesConfig` accepts exactly zh-TW and en (`config/models.py:125`). The public profile (`indexing/public_profile.py`, `schema_version` 1) requires exactly those two keys and compares zh-TW with en. `index.sqlite` stores `summary_zh_tw` and `summary_en` columns (`INDEX_SCHEMA_VERSION` 1; the manifest verifier accepts only 1). The archive verifier requires card variants for exactly two locales. `faq_entries.locale` has `CHECK(locale IN ('zh-TW','en'))` (migration 29; the latest migration is 37). The static export iterates the pair. Public and admin API parameters are `Literal["zh-TW","en"]` and `DEFAULT_LOCALE` is the constant zh-TW. The chat answer validator is the trust control behind "never infer personal ownership from repository content alone" and depends on per-language data: `chat/policy/person_reference.<tag>.yml`, the `inflation_terms.yml` groups and the fixed visitor messages in `chat/answers.py`. Analysis and contribution prompts and schemas name zh-TW and en literally. Phase A (ADR-078) left the registry at two languages and the profile step reading it.
- **Decision:**
  1. **Site language set.** `locales.supported` is an ordered list of one or more unique registry tags and `default` is one of them. Every localized config value must have exactly those keys (the existing `_localized` rule). Existing zh-TW + en files stay valid and the config `schema_version` stays 1 (the value domain widens; no field is added). The owner chooses the set in the guided flow (decision 9); its order is the column and toggle order. A single-language site is allowed; this supersedes the "no locale reduction" sentence of `OWNER_REVIEW.md` line 275 by the owner's decision.
  2. **Registry growth.** Add `zh-CN` (endonym 简体中文; scripts CJK and LATIN; match `zh-cn`, `zh-sg`, `zh-hans`) and `es` (endonym Español; LATIN; match `es`); bare `zh` keeps matching zh-TW. New fields on every entry: `english_name` (used in model prompts), `title_max` (maximum characters of an analysis title, replacing `ANALYSIS_TITLE_MAX_CHARACTERS`), `chrome` (the hand-written admin catalog to show: zh-TW for zh-TW and zh-CN, en for en and es) and an optional `derive` of `{from, converter}` (zh-CN from zh-TW with `tw2sp`, zh-TW from zh-CN with `s2twp`). The Python and TypeScript mirrors and the parity test of phase A stay. The shared web catalog `i18n/messages.ts` gains a zh-CN catalog generated from zh-TW by the converter (committed, with a test that fails on drift); admin components that hold their own zh-TW/en copy keep two catalogs.
  3. **Deterministic conversion.** Add the pinned dependency `opencc-python-reimplemented==0.1.7` (Apache-2.0, pure Python wheel of about 482 KB, no native code, dictionaries shipped as package data) through uv and its lock file (ADR-012), behind one wrapper `reponpc.i18n.convert`. The wheel build and the Windows spec must include the dictionary data. Rejected: `zhconv` (GPLv2+) and the official OpenCC binding (a Python 3.14 wheel is unverified). Conversion runs only while authoring in the admin; serving and export never convert.
  4. **Translate API.** Items whose source and target form a `derive` pair are converted locally with no provider call: `method: "converted"` (the enum widens from `"model"`), still `confirmed: false`, still editable, with its own unreviewed marker ("自動轉換，尚未檢視" / "Converted automatically, not reviewed yet"). The script and token checks do not apply to them, and a request made only of converted items works when no chat model is accepted. Every other pair keeps the ADR-078 model path unchanged; limits and uniqueness are unchanged.
  5. **Chat trust data per language (fail closed).** A registry entry is valid only when `person_reference.<tag>.yml` exists with non-empty `references`, every `inflation_terms.yml` group has a non-empty list for the tag, and the fixed visitor messages exist for the tag or fall back to English. A missing or invalid file is a startup error, never a silent skip, and a contract test covers every registry tag. The person-reference check covers the visitor's language, English and every other site language (today: the language and its alternate). zh-CN data is generated from the zh-TW files by the converter through a committed script with a drift test. The es files are drafted in this phase; they need review by a Spanish speaker, and `docs/SECURITY.md` and a header in each es file record that status.
  6. **Public data model and bundles.** `public/profile.json` becomes `schema_version: 2` with `locales` keyed by exactly the site set. The verifier accepts 1 (legacy: exactly zh-TW and en) and 2, and compares every locale with the first one for non-localized fields and repository count. `index.sqlite` becomes `index_schema_version: 2`: summaries move to `repository_summaries(repository_id, locale, summary)` and the reader keeps the v1 column path. Required card variants are computed from the profile's locales (`public/card-{theme}-{tag}.{svg,gif,png}`). The manifest key set does not change. A v1 bundle stays activatable and is never rewritten, and the last known-good bundle rule is unchanged.
  7. **Runtime store.** Migration 38 rebuilds `faq_entries` without the locale `CHECK` (SQLite cannot drop a constraint in place), copies the rows and keeps `UNIQUE(locale, question_key)`. Locale validity is then checked against the registry and the active site set in application code. No other runtime table constrains a locale.
  8. **Public and admin API.** `locale` parameters accept registry tags and are rejected with the existing validation error when the tag is not in the active bundle's (public) or the draft's (admin) site set; the default is the site default, not a constant. The public profile response gains `available_locales: [{tag, endonym}]` in site order (additive). The static export writes `profile-<tag>.json` and `faq-<tag>.json` for every site language and sets `<html lang>` to the default.
  9. **Admin authoring.** A "Site languages" control opens the profile step: one checkbox per registry language (labelled by endonym), move-up and move-down buttons for order, a default choice and at least one language always selected. Adding a language adds empty columns that the owner fills or translates; removing a language that holds text asks the existing confirm dialog and then drops that text. The profile step, contribution proposals, claim editor, FAQ and review step iterate the site set instead of the pair. Model output follows what the code does (corrected 2026-11-05 at the owner's word 「改成已核准」, which kept the code and changed this text): the durable repository analysis always writes zh-TW and en (`ANALYSIS_LOCALES` in `i18n/plan.py`), so its cache never depends on the site set; the other site languages of an inference come from conversion or from profile translation; contribution suggestions take the site `locales`; derived FAQ languages are converted from the source-language entries after validation. Prompts name languages by `english_name` and script guards use the registry (phase A).
  10. **Visitor.** The language toggle lists `available_locales` and is hidden when there is one. The initial language is the first browser language that matches the site set, then the site default; a stored choice wins only while it is in the set. A language with no catalog uses the English chrome while content stays in its language, with `lang` set on the content.
  11. **Limits.** No cap beyond the registry size (four). Model output grows with the number of non-derived languages; a request that cannot fit its output budget fails through the existing provider-error path and is never truncated silently.
  12. **Delivery.** B0: registry entries and fields, converter wrapper and dependency, policy data, TypeScript mirror (sequential). Then parallel workers on disjoint files: data model, bundles, migration, export and cards; chat, FAQ, public API; onboarding and admin API; admin web; visitor web. Then integration: a v1 bundle still activates, a one-language build, a four-language build, a real-model run and a real-app walk.
- **Rejected:** Converting at serve time (hides edits and couples serving to a dictionary); generating zh-CN with the model (the pair is exactly derivable); accepting a language without chat policy data (a silently weaker trust control); a GPL converter; a database table of languages (the set belongs in the bundle); per-language YAML files (the localized-map shape already works).
- **Consequences:** One new dependency; bundle profile schema 2, index schema 2 and runtime migration 38, all forward-only (an older app rejects v2 bundles, so downgrading after building one is unsupported); every test that asserts the pair changes; admin chrome stays two hand-written catalogs; es safety data needs native review; spec 0.5.0, AC-087 to AC-094, FR-055, SECURITY.md, OPERATIONS.md (dependency, migration), README and `reponpc.example.yml` change on acceptance.
- **Requirements:** FR-028, FR-041/042, FR-054, FR-055 (new), NFR-001/003/009/011/012/014, AC-087 to AC-094 (new; to be written on acceptance).

## ADR-080: One Windows mode: local sign-in with sharing, no trial/production choice

- **Status:** Accepted 2026-11-05 (owner decision D1 = A, 「已知問題先列入這一輪修正規劃…你要假設使用者智商都不到80」, approved with the novice-round plan). Amends ADR-027 and ADR-070. Technical Specification 0.5.1.
- **Context:** Both Windows entry points start `loopback_evaluation`, and 07dfdb9 told the user to edit `.env` to get sharing. A novice cannot do that, so the default path ends before the README card. The visitor gateway refuses every profile except `production` (`api/visitor_gateway.py::_validate_configuration`), the admin same-origin check runs only in `production` (`api/admin.py`), and Windows private-folder checks are enforced only in `production`. `production` needs a typed 15-character password and a shortcut the novice does not know about. The password is not the control that protects the owner on a one-person Windows machine; the loopback bind, the host and forwarded-header checks, the one-use launch grant and the owner-only data folder are.
- **Decision:**
  1. **One default.** On Windows both launchers start `loopback_evaluation` and that profile supports sharing. User-visible text never says "trial", "evaluation" or "production" on the way to the README. The profile name stays in code and in `REPONPC_DEPLOYMENT_PROFILE` for compatibility.
  2. **Gateway.** `VisitorGateway` accepts `loopback_evaluation` as well as `production`. It still requires explicit loopback admin origins, an HTTPS gateway origin and a Pages origin on three distinct hosts. Both launchers set `REPONPC_ADMIN_ORIGINS=http://localhost:<port>` in both profiles.
  3. **Admin origin check.** The same-origin check (`CSRF_FAILED`) applies to every admin request in both profiles whenever admin origins are configured. A request whose `Host` is not a configured admin origin never reaches the admin API.
  4. **Funnel cannot reach the admin port.** Tailscale Funnel forwards from loopback and adds `X-Forwarded-*` headers and a `*.ts.net` `Host`. Two independent checks refuse such a request on the admin port: a Host allowlist (`REPONPC_TRUSTED_HOSTS`, `localhost` and `127.0.0.1` for the launchers; a generic 400) and `local_launch_boundary` (any `Forwarded` or `X-Forwarded-*` header is refused). Correction 2026-11-05: the first draft of this item said the Host allowlist already existed. A real test (W2) showed that `REPONPC_TRUSTED_HOSTS` was parsed and never enforced, so `GET /admin` with `Host: example.ts.net` returned 200 (the launch exchange and the session resume were still refused, so no session could be minted). This ADR therefore adds the enforcement to the main application, only for `loopback_evaluation` and only when the list is non-empty; `production`, Linux and Docker deployments do not change, and the visitor gateway runs its own application and is not affected. A test per check proves this through the real application. Funnel still points only at the gateway port.
  5. **Data folder.** Each launcher makes its own default data folder owner-only (current user, SYSTEM, Administrators; inheritance removed; existing children reset) before the server starts, using the helper and command builder from ADR-070. This reverses ADR-070 D5 for a launcher-default folder only. A folder set with `REPONPC_DATA_DIR` that is not owner-only still stops the launcher with the printed `icacls` command. The application's own startup check stays `production`-only so existing tests and Linux are unchanged.
  6. **Installer.** The 「RepoNPC（正式模式）」 shortcut is removed (ADR-070 D2). `--profile production` and `.env` `REPONPC_DEPLOYMENT_PROFILE=production` keep working with the existing setup-code and password flow for a person who wants it. The README, admin pages and error text do not mention that path.
  7. **Sharing UI.** `publicSharingAvailable` no longer depends on the access state. All trial-mode copy added by 07dfdb9 and earlier is deleted. Sign-in stays the one-use launch grant.
  8. **Proxy trust.** `REPONPC_VISITOR_TRUSTED_PROXY_CIDRS` stays `production`-only. Without it the gateway uses the aggregate rate-limit bucket, as Windows production does today.
- **Accepted risks (stated, not hidden):** the public gateway and the passwordless admin share one process, as `production` and its admin share one process. A flaw in the gateway that gives code execution reaches the data in either profile. Another program running as the same Windows user can read the data in either profile. Other Windows accounts are blocked only if item 5 succeeds.
- **Rejected:** (B) default `production` with a 15-character password set in the browser (a novice must invent and keep a password before seeing anything); (C) keep the trial default and add a restart button (still a mode choice).
- **Consequences:** `scripts/start-reponpc.ps1`, `src/reponpc/windows_launcher.py`, `config/environment.py`, `api/visitor_gateway.py`, `api/admin.py`, `packaging/windows/reponpc.iss`, the admin sharing panels, README, OPERATIONS, SECURITY, `.env.example`, FR-017/029/048 and AC-069/071/081 change together; the Windows production plan keeps its history and gains a pointer to this ADR.
- **Requirements:** FR-017/029/047/048, NFR-002/003, AC-069/071/081 (amended) and AC-096 (new).

## ADR-081: GitHub Pages and the README card without a visitor gateway (live chat is optional)

- **Status:** Accepted 2026-11-05 (owner decision D2 = A first, then B). Amends ADR-048 and the A1 gateway contract only where they make the gateway a prerequisite of Pages export. Technical Specification 0.5.1. Phase B (RepoNPC detects Tailscale and runs `tailscale funnel` from a button) is approved in principle and gets its own ADR when it starts; it is not part of this decision.
- **Context:** `PagesSharingService._current_origins` raises `SHARING_CONFIGURATION_INVALID` unless the visitor gateway holds both a Funnel (gateway) origin and a Pages origin. The exported `index.html` and `export-manifest.json` embed `gateway_origin`, and the visitor client (`visitorData.ts`) reads status, FAQ and chat targets from it. A novice who only wants the README card must therefore install Tailscale, enable Funnel HTTPS and type a Funnel URL first. The finish line is the README card that opens the chat page; the optional capability blocks it.
- **Decision:**
  1. **Pages needs only a Pages URL.** The Pages origin is the origin of the saved Pages URL, validated as today (HTTPS GitHub Pages origin). If the gateway settings also hold a Pages origin, it must equal that origin; otherwise the existing `SHARING_CONFIGURATION_INVALID`.
  2. **The gateway origin is optional in the export.** With no gateway origin configured, the exported HTML embeds none and `export-manifest.json` carries `gateway_origin: null`. A manifest with a gateway origin keeps `schema_version` 1 and stays byte-identical to today; a manifest without one uses `schema_version` 2 with `gateway_origin: null`. Readers (Python and the visitor client) accept both. Export, README, download and verify work in both cases. Export and verify still compare the origins they used and fail with `SHARING_CONFLICT` if they change.
  3. **The visitor page without a gateway.** The page shows the chat page in the resting state: static FAQ from the exported files, the status "resting" and a disabled chat box with the existing resting message. No request leaves the page for any gateway, and no console error appears. A manifest with a gateway origin behaves exactly as before.
  4. **Adding live chat later is one re-upload.** The owner sets the Funnel URL in the existing panel, starts the gateway, downloads the site again, uploads it and checks it. Pages already exported without a gateway keep working.
  5. **Admin flow.** The path is: Pages URL (one input), download, upload, README card. The Funnel and live-chat step moves after the README step and is optional. The two Pages URL fields (「Pages 網域」 in the gateway panel and 「Pages 網址」 in the Pages panel) become one input in the Pages panel; the origin is derived from it and no API field is removed or renamed.
  6. **No new endpoint, error code or environment variable.** The sharing state and the export response gain only additive fields, listed in the spec.
- **Rejected:** keeping the gateway as a prerequisite and only explaining it better (the owner's bar: remove the step before rewording it); exporting a page with a fake or placeholder gateway origin (the client would send requests to it).
- **Consequences:** `sharing/pages.py`, `sharing/export.py`, `sharing/manifest.py`, the sharing endpoints of `api/admin.py`, `visitorData.ts`, `VisitorApp.tsx`, the static-export tests, `PagesSharePanel`, `VisitorGatewayPanel`, README, OPERATIONS, PAGES_SHARING_GUIDE and FR-047, AC-068/071/072/074/082 change together. The static policy check `matchesStaticGatewayPolicy` must still reject any non-null origin that is not the configured policy.
- **Requirements:** FR-047, FR-048, NFR-001/014, AC-068/071/072/074/082 (revised where they assume a gateway) and AC-095 (new).

## ADR-082: One-button live chat: RepoNPC runs Tailscale Funnel for the owner (phase B)

- **Status:** Accepted 2026-11-06 (owner decision D2 = B, approved in principle 2026-11-05 and confirmed with 「好，這些問題照你建議去做，然後可以進行下一輪」 on 2026-11-06). Technical Specification 0.5.2. Amends ADR-048, ADR-053, ADR-070 and the A1 gateway contract only where they say RepoNPC never invokes Tailscale.
- **Context:** Live chat needs a Funnel URL, a Funnel port and two typed commands. The owner's bar is that a first-time user needs no technical step: remove it before rewording it. The maintainer's own machine already serves another local program through Funnel on 8443 and another through the tailnet on 443, so any automation must leave routes it did not create untouched. The real CLI (1.104.4) reports its state in `tailscale status --json` (`BackendState`, `Self.DNSName`, `Self.Online`, `Self.Capabilities` with `funnel`, `https` and the Funnel port list, `CertDomains`) and its routes in `tailscale serve status --json` (`TCP`, `Web`, `AllowFunnel`).
- **Decision:**
  1. **Scope.** Available only in `loopback_evaluation`, where the admin is local-only. `production` keeps the manual commands of the A1 contract.
  2. **What the owner still does.** Install Tailscale, sign in, turn on HTTPS certificates and allow Funnel in the Tailscale admin pages, once. RepoNPC never installs Tailscale, signs in, runs `tailscale up`, `login`, `set` or `serve`, edits tailnet policy, or reads or stores Tailscale credentials.
  3. **Commands.** Exactly four, each a fixed argument list started without a shell and with a short timeout (status 10 s, funnel 30 s): `tailscale status --json`, `tailscale serve status --json`, `tailscale funnel --bg --https=<port> http://127.0.0.1:<visitor-port>` and `tailscale funnel --https=<port> off`. `<port>` must be one of the tailnet's Funnel ports (from the capability list; default 443, 8443, 10000) and free; `<visitor-port>` is the effective visitor port (1024-65535). `funnel reset` is never used. Output is capped at 1 MiB, parsed as JSON where JSON is expected, and never logged or sent to the browser raw. Tailscale 1.52 or later is required.
  4. **States.** `status` returns one `state`: `unavailable_profile`, `not_installed`, `unsupported_version`, `needs_login`, `stopped`, `offline`, `https_disabled`, `funnel_not_allowed`, `no_free_port`, `ready`, `live` or `error`. The browser shows one plain instruction per state, with an official link where one exists.
  5. **Never overwrite.** A port is free when `serve status --json` holds no `Web` entry and no `TCP` entry for it. A route that proxies exactly `http://127.0.0.1:<visitor-port>` with Funnel on is RepoNPC's own: start reuses it and stop may remove it. Every other route is left as it is, including routes on the ports RepoNPC would prefer.
  6. **Start and stop.** Start (one button) runs: status, plan, `funnel --bg`, re-read `serve status --json` to confirm the route, configure the gateway origin and Pages origin (ADR-081), start the visitor connection. If a later step fails, a route that this call created is switched off with the scoped `off`; a reused route stays. Stop stops the visitor connection, runs the scoped `off` only when the route is RepoNPC's own, then clears the saved Funnel URL and Pages address so the README step and the next export read "live chat off" (owner decision 2026-11-06; the manual Stop button of the advanced form keeps the saved addresses).
  7. **No new state.** No environment variable, schema, file or stored flag: "managed or manual" is read from the live route. The Funnel URL field stays under an "advanced" disclosure.
  8. **Routes and codes.** `GET /api/admin/tailscale/status`, `POST /api/admin/tailscale/funnel/start` and `POST /api/admin/tailscale/funnel/stop`, with the same session, CSRF, same-origin and `no-store` rules as the visitor-gateway routes. New codes `TAILSCALE_NOT_READY` (409) and `TAILSCALE_FAILED` (503); a gateway revision conflict keeps `GATEWAY_CONFLICT`. The JSON shapes are in the A1 contract.
  9. **Executable lookup.** The first existing regular file of: `tailscale` on `PATH` (absolute `PATH` entries only), `%ProgramFiles%\Tailscale\tailscale.exe`, `/Applications/Tailscale.app/Contents/MacOS/Tailscale`, `/usr/bin/tailscale`, `/usr/local/bin/tailscale`. The working folder is never searched.
  10. **Logging.** Events carry the state code and port numbers only.
- **Rejected:** running `tailscale up` or login for the owner (credentials boundary); `funnel reset` or any change to a route RepoNPC did not create; changing the tailnet policy through an API or OAuth (needs credentials); automation in `production` now (the Docker and sidecar path stays manual); taking an occupied port; a new environment variable for the CLI path.
- **Consequences:** a new `reponpc/tailscale` package, three routes in `api/admin.py`, section 4 of the admin page, tests with a fake command runner, and real-host evidence (a real `tailscale funnel` changes what the internet can reach) as a dated, owner-approved item under AC-081. FR-047/048, the A1 contract and SECURITY change together.
- **Requirements:** FR-047, FR-048, NFR-001/002/003/014, AC-081 (extended), AC-097 and AC-098 (new).

## ADR-083: Built-in model GPU or CPU choice and automatic chat interface detection

- **Status:** Accepted 2026-11-07. Owner request in chat: 「那幫我新增可選項，讓使用者選擇是否使用gpu，否則使用cpu」 and 「API接口可以改為自動偵測服務商使用chat completion還是response」. Technical Specification 0.5.3. Amends FR-049 (the built-in adapter runs on CPU) and ADR-058 (the owner picks the chat interface on the connection form).
- **Context:** The built-in `bge-m3` adapter is pinned to the CPU, and the shipped `onnxruntime` wheel (1.30.0) lists only the CPU provider. An owner with an NVIDIA card has no way to use it. The connection form also asks a first-time user a protocol question (Chat Completions or Responses) that the service already answers.
- **Decision A: device choice for the built-in model.**
  1. **One stored value.** Migration 39 adds `embedding_profiles.compute_device` (`cpu` default, `gpu`, with a `CHECK`). No table rebuild; existing rows read as `cpu`.
  2. **The device is not part of the embedding identity.** Adapter, model ID, dimension and prefixes are unchanged, so a device change neither reindexes nor changes a bundle. The probe, dimension and normalisation checks stay.
  3. **GPU means ONNX Runtime `CUDAExecutionProvider`, first and only.** `gpu_available` is true only when the installed runtime lists it. A session whose first provider is not CUDA is refused; there is no silent fallback to CPU. DirectML and ROCm are out of scope (no matching wheel for the pinned runtime).
  4. **Prove before saving.** Choosing `gpu` loads the model on the GPU and requires `health().ready` before the value is stored. No CUDA provider returns `BUILTIN_GPU_UNAVAILABLE` (409); a failed load or health check returns `BUILTIN_DEVICE_FAILED` (502). Both leave the saved device unchanged. Choosing `cpu` needs no proof. A saved `gpu` whose provider later disappears fails closed when the model loads and never falls back.
  5. **Routes.** `GET /api/admin/embedding-models/builtin` adds `compute_device` and `gpu_available`; `PUT /api/admin/embedding-models/builtin/device` takes exactly `{"device":"cpu"|"gpu"}` with the admin session, CSRF and same-origin rules and returns the same descriptor. The embedding profile payload gains `compute_device`. A device other than `cpu` or `gpu` is `VALIDATION_ERROR`.
  6. **Admin page.** A "Compute device" select appears in the built-in panel once the profile exists. With no GPU support the GPU option is disabled and the panel says what is missing and that an Ollama service uses a GPU without installing anything. The built-in card and the workspace status show CPU or GPU.
  7. **Packaging.** The shipped dependency stays the CPU `onnxruntime`. Enabling the GPU is an operator step (replace it with `onnxruntime-gpu` and install the CUDA and cuDNN libraries it needs; OPERATIONS). No new hosted dependency or cost. **Amended by ADR-084:** on Windows the admin page installs the GPU runtime in one click, into a side folder.
- **Decision B: the chat interface is detected, not chosen.**
  1. **Where.** For a managed `openai_compatible` connection, the existing "Test model" probe tries Responses first and then Chat Completions inside the one 60-second probe deadline (ADR-074) and saves the interface that answered on the connection (a revision bump that rebinds safe dependents, as for any connection edit). When both work, Responses wins, so the provider-defined public summaries of ADR-058 stay available.
  2. **When it moves on.** Only a plain `INVALID_RESPONSE` from Responses (the service did not understand the request, for example a 404) triggers the second attempt. Authentication, rate limit, timeout, unavailable, output limit and context overflow stop the probe with no second request. If the second attempt also fails, its error is the result.
  3. **Where it does not run.** The active profile keeps the interface it serves with; host-managed connections, Ollama and vLLM are not detected.
  4. **Runtime is unchanged.** Answering makes one call on the saved interface and never retries on or switches to the other (ADR-058).
  5. **Form and API.** The connection form no longer asks for `chat_api`. The API still accepts and returns `chat_api`; the connection details show it as "detected when a model is tested". A value saved earlier stays until a later successful test detects another.
  6. **Accepted limit.** A connection holds one interface. Two models on one connection that need different interfaces: the most recent successful test wins.
- **Rejected:** a runtime fallback between interfaces (ADR-058 forbids protocol switching during an answer); a per-model interface (new schema for a rare case); detecting on every save of the form (a save is not a request to call the service); DirectML or ROCm now; failing over from GPU to CPU when the GPU breaks (the owner chose the device).
- **Consequences:** `providers/builtin_onnx.py`, `runtime/database.py` (migration 39), `admin/embedding_profiles.py`, `admin/operations.py`, `api/admin.py`, `main.py`, `admin/chat_profiles.py`, `BuiltinModelPanel`, `LocalModelSetup`, `EmbeddingProfilePanel`, `ModelConnectionPanel`, the admin error-code fixture, OPERATIONS and SECURITY change together. New codes `BUILTIN_GPU_UNAVAILABLE` and `BUILTIN_DEVICE_FAILED`. A real GPU inference run needs a machine with an NVIDIA card and the GPU runtime and is not part of the automated suite.
- **Requirements:** FR-012, FR-049, AC-099 and AC-100 (new).

## ADR-084: One-click GPU runtime for the built-in model

- **Status:** Accepted 2026-11-07. Owner request in chat: 「那有辦法實現，當偵測使用者沒有cuda環境時一鍵安裝的功能嗎?查查看最新的cuda環境安裝方法」, then 「照建議實作」 (build the recommended full one-click install). Technical Specification 0.5.4. Amends ADR-083 decision A.7 (enabling the GPU was an operator step) and supersedes the "replace `onnxruntime` with `onnxruntime-gpu`" instructions in OPERATIONS.
- **Context:** ADR-083 left the GPU to an operator who had to swap the ONNX Runtime package and install CUDA and cuDNN, which a novice cannot do (novice-first bar, 2026-11-05). Since ONNX Runtime 1.27 the PyPI `onnxruntime-gpu` wheel targets CUDA 13.0 with cuDNN 9, and the NVIDIA runtime libraries are published as ordinary wheels (`nvidia-*`), so no CUDA toolkit and no system installer is needed. The only system component is the NVIDIA driver (580 or newer; Turing or newer GPUs, compute capability 7.5).
- **Decision:**
  1. **A side folder, never the managed environment.** The pinned wheels are unpacked into `<data_dir>/gpu-runtime/<runtime_id>/`. `.venv`, `uv.lock` and the CPU `onnxruntime` are never touched, so `uv sync --frozen` and an upgrade cannot break or silently drop it, and no loaded package has to be replaced.
  2. **A generated, pinned manifest.** `src/reponpc/providers/gpu_runtime_manifest.yml` is produced by `scripts/generate_gpu_runtime_manifest.py` from the `onnxruntime==` pin: per wheel the file name, an exact `https://files.pythonhosted.org/packages/...` URL, the size and the SHA-256 (8 wheels, 1,330,778,450 bytes for runtime `ort-1.30.0-cuda13-cp314-win_amd64`). `--check` fails when the file drifts from PyPI or from the pin. The dependencies the app already ships (`numpy`, `protobuf`, `flatbuffers`, `packaging`) are excluded; the generator fails on any other unexpected dependency.
  3. **Detection.** `nvidia-smi` runs as a fixed argument list (no shell, 10-second timeout, 64 KiB output cap) from an absolute `PATH` entry or a standard NVIDIA folder. States: `can_install`, `no_nvidia_gpu`, `driver_too_old` (major below 580), `gpu_too_old` (capability below 7.5), `unsupported_platform`. Cached for 30 seconds. The install is offered only on Windows x86-64, started from the source launcher (not a frozen installer build), on the pinned Python.
  4. **Install flow.** One operation on the existing single lane (`OllamaModelOperationCoordinator`, `GET` and `DELETE /api/admin/embedding-model-operations/{id}`): free space of at least three times the download; a resumable, hash-verified download through a pinned HTTPS transport that connects only to `files.pythonhosted.org` and refuses redirects; unpacking of only `onnxruntime/**` and `nvidia/**/*.dll` into a staging folder; a **self-check in a child process** (`python -I -m reponpc.providers.gpu_runtime_check`) that imports the staged ONNX Runtime, creates a CUDA session on a tiny MatMul model with fallback disabled and checks the answer; only then a `READY.json` marker is written and the folder is published with one atomic rename. A failed or cancelled run publishes nothing, keeps the verified wheels for a retry, and leaves the CPU path and any earlier published folder alone.
  5. **Activation.** At the next start, before ONNX Runtime is first imported, `prepare_application` puts the published folder first on `sys.path` and registers its DLL folders (`os.add_dll_directory` and `PATH`); `builtin_onnx` calls `onnxruntime.preload_dlls()` once. `gpu_available()` is true when the CUDA provider is listed or the runtime was activated. The restart is manual: close RepoNPC, including the launcher window, and open it again. A folder whose marker does not match this build's manifest (a RepoNPC upgrade) is ignored and replaced by a new install.
  6. **Consent.** The install needs `{"confirmed": true}` and the panel's explicit consent checkbox, which names PyPI, the NVIDIA libraries and links the NVIDIA license. The device choice stays exactly as in ADR-083: the GPU is proven on a session before it is stored and there is no automatic fallback.
  7. **Routes and codes.** `POST /api/admin/embedding-models/builtin/gpu-runtime/install` (202, the operation payload; admin session, CSRF, same origin). `GET /api/admin/embedding-models/builtin` gains `gpu_runtime`. New envelope code `GPU_RUNTIME_UNAVAILABLE` (409: detection is not `can_install`). Operation `error_code` values: `GPU_RUNTIME_SELF_CHECK`, `GPU_RUNTIME_PATH`, `GPU_RUNTIME_EXTRACT`, `GPU_RUNTIME_UNSUPPORTED`, `GPU_RUNTIME_MANIFEST_INVALID` and the existing `BUILTIN_DOWNLOAD_*` codes.
  8. **Removal.** With RepoNPC stopped, deleting `<data_dir>/gpu-runtime/` returns to the CPU runtime; nothing else refers to it.
- **Rejected:** `pip install` into `.venv` (DLL locking while loaded, `uv sync --frozen` removes it, the package name collides with the CPU wheel); bundling CUDA in the repository or the installer (size and redistribution); restarting the process from inside the app (an ONNX Runtime import cannot be swapped safely); running NVIDIA's system installers (system change, administrator rights); DirectML (no wheel for the pinned runtime); trusting `nvidia-smi` text beyond a few validated fields.
- **Accepted limits:** the frozen installer build is not supported; the download is about 1.33 GB (about 4 GB of free space is needed while installing); the NVIDIA libraries carry NVIDIA's license, which the consent names and links; the restart is manual; the wheel layout (`nvidia/cu13/bin/x86_64`, `nvidia/cudnn/bin`) is checked by the self-check, so a layout change fails closed and is repaired by regenerating the manifest. A real CUDA session on an NVIDIA machine is an owner-approved run, not part of the automated suite.
- **Consequences:** `providers/gpu_runtime.py`, `providers/gpu_runtime_check.py`, `providers/gpu_runtime_manifest.yml`, `providers/builtin_http.py` (a second pinned transport on shared code), `providers/builtin_onnx.py`, `admin/model_operations.py`, `admin/operations.py`, `api/admin.py`, `main.py`, `scripts/generate_gpu_runtime_manifest.py`, `GpuRuntimeSupport`, `BuiltinModelPanel`, `LocalModelSetup`, the admin error-code fixture, OPERATIONS and SECURITY change together. No new hosted dependency, service or recurring cost; one new network destination (`files.pythonhosted.org`), used only after the owner's consent.
- **Requirements:** FR-049, NFR-001, AC-101 and AC-102 (new).

# RepoNPC Architecture Decision Log

**Document status:** ADR-001 through ADR-030 accepted; ADR-030 approved 2026-09-10. Historical supersession is stated in each record.
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
- **0.2.2 amendment:** ADR-029 supersedes only the prohibition on authenticated entry of model connection credentials. Public presentation stays in Git; model credentials remain deployment-local and cannot be written into public YAML.
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

- **Status:** Accepted on 2026-08-16.
- **Supersedes:** ADR-009/ADR-016 only where they require password-only authentication, and ADR-018 only where it excludes OAuth/public-read credentials. The GitHub-only first-owner/recovery clause is superseded by ADR-025.
- **Decision:** GitHub OAuth Web Application Flow with PKCE is an alternative authentication method for the sole RepoNPC owner. Setup still requires the host-issued code followed by local username/password creation; an authenticated local owner may then link GitHub. Login/link use distinct one-time transactions; the GitHub numeric user ID is the stable link. OAuth requests no repository scope, supports public-read only, and its encrypted credential is never reused for writeback. Explicit fine-grained PAT public-read credentials are a non-login fallback. Writeback remains the configured separate fine-grained credential.
- **Why:** The owner needs a familiar sign-in and a safe public-read connection without creating open registration, multi-user accounts, or broader repository permissions.
- **Consequences:** Runtime schema adds authentication methods, encrypted credentials, and OAuth transactions. Password/pre-provisioned login remains compatible and is always retained as break-glass recovery; removal of the local method is rejected. Later GraphQL/archive and durable batch work are explicitly outside this amendment.

## ADR-021: Resolve selected public repositories through immutable archives and durable batches (partially superseded by ADR-028)

- **Status:** Accepted on 2026-08-16.
- **Decision:** Guided multi-repository analysis uses a central, rate-aware GraphQL metadata resolver plus one exact-commit archive per cache miss. It creates at most one owner-scoped durable batch whose items advance through independently bounded stages and publish safe replayable events. OAuth/PAT public-read credentials are selected explicitly and never fall back; the writeback credential is unavailable to analysis. Validated index/result caches use complete immutable identity keys. The legacy one-repository route remains a batch compatibility adapter.
- **Why:** Per-blob REST resolution is rate-expensive and branch references can drift. Browser-controlled serial work cannot survive reloads, enforce server capacity fairly, or preserve the boundary between safe durable status and ephemeral untrusted source/model data.
- **Consequences:** Runtime SQLite gains rate, batch, event, and cache metadata. The scheduler must cap GitHub/archive/local/provider stages and reserve provider opportunities for public chat. Exact-SHA archive validation, 24-hour bounded batch result retention, explicit retry after dispatched generation interruption, restart cleanup, API/SSE contracts, and accessibility UI coverage are release requirements. This does not broaden repository visibility, provider access, OAuth scopes, writeback permission, or v1 hosting topology.

## ADR-022: Keep GitHub OAuth entry points actionable before host configuration (legacy; superseded by ADR-028)

- **Status:** Accepted on 2026-08-30.
- **Supersedes:** ADR-020 only where its dual-authentication UI is described as disabled before OAuth configuration.
- **Decision:** GitHub setup, sign-in, link, and reauthentication entry points remain keyboard-operable when the deployment has not configured OAuth. Activating one opens a same-origin host-side setup guide dialog and does not submit an OAuth start request or redirect to GitHub. Once the server reports OAuth as configured, the same shared GitHub button performs the existing top-level Authorization Code Flow with PKCE S256. A public `GET /api/admin/github/oauth/setup-guide` returns only configured state, the canonical fixed callback URL, the fixed GitHub OAuth-App documentation URL, and a next-step label, with `Cache-Control: no-store`.
- **Why:** A disabled button gives ordinary users no actionable explanation and makes a deployment-only setup prerequisite look like a user-registration failure. An actionable guide preserves the security boundary while making the next safe step discoverable.
- **Consequences:** AC-043 and FR-031 gain the unconfigured-button/dialog behavior; frontend tests must cover icon/label uniqueness, focus management, bilingual copy, responsive layout, and no-secret rendering. The guide never accepts or returns client secrets, encryption keys, tokens, secret-file paths, or owner identity. OAuth token lifecycle/refresh remains a separate follow-up until explicitly implemented.

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

- **Status:** Accepted on 2026-09-08; deterministic implementation recorded in `GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_HANDOFF.md` on 2026-09-09; external release evidence remains pending.
- **Supersedes:** ADR-020 and ADR-022 in full; ADR-021 where it requires GraphQL or an `identity_public_read` / `public_read` credential; ADR-027 only for its GitHub connection/setup/PKCE/encrypted-public-read behavior. ADR-027's loopback launch, production password, recovery, session, CSRF, origin/host, and private-admin decisions remain accepted.
- **Context:** First-run use demonstrated that OAuth configuration adds deployment ceremony unrelated to RepoNPC ownership. Moving OAuth behind authentication removed the login dead end but left a prominent optional connection surface, client-secret/callback/encryption-key configuration, and a second public-read PAT path. For a single-owner application that supports only public repositories, this operational and secret-management cost is disproportionate. GitHub's GraphQL API requires authentication, while its REST API permits unauthenticated public-data access with a documented per-IP limit.
- **Decision:** Remove GitHub OAuth and browser-entered public-read PATs from the product. Public discovery and selected-repository analysis use bounded, fixed-origin unauthenticated GitHub REST requests, resolve a full immutable commit SHA, and fetch only the archive addressed by that SHA. Rate exhaustion produces a safe retry time and preserves manual authoring/export. Discovery and analysis never receive or fall back to the independent writeback token. Legacy OAuth/PAT routes become non-mutating `410` responses during a bounded compatibility window; runtime migration removes their transactions, identities, and encrypted public-read credential rows without decrypting or logging them.
- **Why:** This removes an OAuth App, callback, client secret, encryption key, token lifecycle, and PAT form from the normal self-hosting journey while retaining the public-repository use case. The accepted trade-off is GitHub's lower anonymous REST capacity, which matches the intended low-frequency personal deployment and must degrade recoverably.
- **Consequences:** FR-030/FR-034 and AC-041 through AC-043 become legacy; FR-031 is narrowed to deployment-aware local administration with no GitHub credential surface; FR-032/AC-044 move from credentialed GraphQL to anonymous REST; FR-037 and AC-051/AC-052 govern retirement and replacement. OAuth/PAT UI, API, environment variables, launcher mappings, services, tests, and operational instructions are removed in an ordered migration. Historical schema migrations remain readable. The separately configured least-privilege writeback token and its exact path/operation allowlist remain unchanged.
- **Implementation plan:** `docs/GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_PLAN.md`.
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

### ADR-029/030 implementation clarification — 2026-09-12

The owner approved the novice UI/UX repair findings as one batch. Unknown embedding dimensions use nullable untested profile metadata until an explicit successful query/passage probe; public bundle identities remain concrete. Connection update uses explicit endpoint retention versus replacement, with independent key intent and unchanged no-cross-destination-key-reuse constraints. Display-name-only edits preserve the effective connection revision. These additive runtime/API refinements implement the accepted no-guessing, write-only, explicit-selection directions; they do not add fallback, hosting, inference services or public schema changes. Technical Specification 11.5 records the exact wire rules; Operations records transaction-safe migration 19.

### ADR-029 diagnostic correction — 2026-09-12

The owner rejected the inferred Chinese HTTP 402 billing explanation and explicitly requested original provider error text. Provider prose is open-world data, not a closed translation vocabulary. Replace the HTTP explanation lookup with adapter-bound structural message extraction and preserve the original language in both locales. The owner-authorized additive `last_error_message` admin DTO/runtime field stores only bounded redacted error text; HTTP status remains a validated protocol value. Migration 20, parsing/redaction limits, unavailable-message behavior and regression criteria are frozen in Technical Specification 11.5, Security 21 and AC-054/055/057. Existing prohibitions on full provider bodies, secret disclosure, public diagnostic expansion and implicit fallback remain.


### ADR-029 URL editing correction — 2026-09-12

**Owner-approved URL editing exception (2026-09-12, ADR-029; FR-038/040, AC-055/057):** The owner explicitly requested that replacing a managed service URL prefill its saved value. Only `POST /api/admin/model-connections/{connection_id}/edit-endpoint`, guarded by the existing owner session, same-origin check and CSRF, may return `{connection_id, revision, base_url}` with `Cache-Control: no-store`. It accepts no arbitrary URL, reads the exact current encrypted revision, rejects host-managed/unknown connections with 404 and unavailable secret storage with 503, and makes no provider request or mutation. List/detail metadata remains URL-free; API keys, secret references and environment values are never returned. The UI fetches only on the explicit Replace URL action, keeps the result in the active form only, clears it on cancel/toggle-off/teardown, and ignores responses after a form or revision change. Loading disables URL editing/submission; failure permits retry or manual entry. No readback URL may enter browser storage, public drafts, exports, logs or snapshots. This narrow exception supersedes earlier blanket stored-URL readback prohibitions; stored-key prohibitions and destination-change credential rules remain unchanged.

Chat probe diagnostic follow-up (2026-09-12): the owner reported `PROVIDER_INVALID_RESPONSE` despite a working service. Inspection found a separate 32-token probe cap and collapsed parser failures. Main corrected the internal probe budget to the configured capability and added source-labelled, closed-set parser evidence under the existing diagnostic field, without inventing provider text or model-name special cases. No claim is made about the owner's actual response, which was not retained. Details: `docs/CHAT_PROBE_RESPONSE_CHECKS_2026-09-12.md`.

# RepoNPC Architecture Decision Log

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

- **Status:** Accepted for implementation on 2026-09-14.
- **Authorization:** A live owner-authorized coderelay check returned the model catalog in about 0.9 seconds and a valid `gpt-5.6-terra` Chat response in about 11.6 seconds, while RepoNPC's fixed 10-second probe repeatedly reported timeout. The owner concluded that the limit was too strict and explicitly requested a default 10 seconds followed by one additional 10 seconds.
- **Decision:** Keep the 10-second probe baseline and grant one automatic 10-second grace window. Pass one 20-second deadline to the selected provider so the original in-flight request can complete; do not cancel and restart at 10 seconds. A single explicit test therefore remains exactly one potentially billable provider call. Existing response-schema checks, output budget, activation boundary, diagnostic persistence, and no-fallback rules remain unchanged.
- **Consequences:** Technical Specification advances to 0.2.9. FR-038/040 and AC-054/057 cover a valid response during the grace window, final timeout after 20 seconds, and regression evidence that only one request is made. No environment variable, API or database migration is added.

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

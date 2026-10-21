# Superseded and archived acceptance criteria

### AC-026 — Configuration writeback detects conflicts

**Maps to:** FR-019, NFR-001, NFR-003

- **Given** a valid expected blob SHA and then a concurrent GitHub edit,
- **When** the owner first saves against the original SHA and later retries stale content,
- **Then** the first operation commits only `reponpc.yml`, the stale operation returns `409 CONFIG_CONFLICT` with current blob SHA, and no overwrite or auto-merge occurs.

### AC-027 — Asset writeback is strictly allowlisted

**Maps to:** FR-018, FR-019, NFR-001

- **Given** valid PNG bytes plus attempts at traversal, nested paths, non-PNG/polyglot data, oversized/decompression-bomb images, deletion, or non-character target paths,
- **When** upload/writeback is requested,
- **Then** only a decoded/re-encoded `assets/character/*.png` target can commit and every other case is rejected before GitHub mutation.

### AC-029 — Publication advances the manifest last

**Maps to:** FR-020, NFR-003, NFR-011

- **Given** successful and deliberately failed builds/uploads,
- **When** the GitHub Action executes the real `config validate`, `index build`, `index publish`, and `index publish-manifest` commands,
- **Then** a successful run validates and publishes one immutable checksummed asset, verifies it, records a local pending manifest, and only then updates `stable-manifest.json`; any failure before the final command leaves the prior stable manifest unchanged and surfaces a failed Action.

### AC-041 — Legacy: GitHub OAuth connects only from the authenticated sole owner

**Legacy status:** Superseded by AC-051 under Technical Specification 0.2.1; retained only to identify behavior that must be removed safely.

**Maps to:** FR-017, FR-029, NFR-001, NFR-002

- **Given** configured and unavailable OAuth operators; valid/invalid, expired, replayed, cross-browser, and wrong-intent OAuth state/PKCE transactions; local-launch and password sessions; renamed GitHub accounts; legacy login/setup OAuth requests; and missing/expired RepoNPC sessions,
- **When** an authenticated owner connects GitHub or any unauthenticated/legacy route attempts OAuth,
- **Then** only an existing valid RepoNPC session can start and finish the connection, `/user` numeric identity is stored as connection metadata, legacy login/setup routes return `410 GITHUB_LOGIN_REMOVED` without redirect or state change, OAuth never creates an owner or RepoNPC session, callback/transaction cookies carry the required scoped attributes, removing/revoking GitHub affects only GitHub-backed work, and no token, verifier, secret, state plaintext, or identity-disclosure detail reaches browser storage, APIs, logs, fixtures, or runtime plaintext.

### AC-042 — Legacy: OAuth/PAT credential purposes and migration fail closed

**Legacy status:** Superseded by AC-050/AC-051 under Technical Specification 0.2.1. Local password recovery remains normative in AC-050; OAuth/PAT persistence does not.

**Maps to:** FR-030, NFR-001, NFR-002, NFR-013

- **Given** existing password/pre-provisioned and GitHub-linked deployments, a passwordless loopback owner switching to production, absent/invalid encryption keys, OAuth credentials with no scope or unsafe broad scope, expired/revoked credentials, PAT submissions, and writeback credentials,
- **When** migrations, OAuth/PAT persistence, validation, linking, unlinking, and GitHub-backed work run,
- **Then** existing password sign-in remains valid in production, encrypted OAuth public-read credentials migrate without plaintext, identity-only login state is retired, OAuth/PAT credentials retain their explicit read-only purpose, writeback is never reused, a `401` requires explicit reconnection without fallback, GitHub cannot authenticate or recover the owner, host-only `reponpc admin set-password` makes a passwordless local owner production-capable without reopening setup or changing GitHub credentials, and a failed migration preserves the last usable authentication state.

### AC-043 — Legacy: Profile-aware access with GitHub connection UI

**Legacy status:** Superseded by AC-049 through AC-051 under Technical Specification 0.2.1. Deployment-aware access remains normative; the GitHub connection UI must be removed.

**Maps to:** FR-031, FR-034, FR-022, NFR-001, NFR-009

- **Given** loopback launch/missing-grant, production setup/password, unavailable/configured OAuth, denial/callback-error, PAT, and connection-required states in `zh-TW` and `en`,
- **When** keyboard and assistive-technology users operate `/admin` at 375, 768, 1024, and 1440 pixels,
- **Then** loopback mode exchanges and removes a valid launch fragment without rendering registration/password/GitHub login controls, while a missing/failed grant presents one relaunch action; production alone renders setup or password login; GitHub controls appear only inside the authenticated settings surface; unconfigured OAuth opens a labeled host guide without redirecting or submitting secrets; recheck reports status and, only when configured, enables a distinct **Continue to GitHub** top-level PKCE action; the dialog exposes only the authoritative callback URL, fixed GitHub documentation link, host-secret/restart/recheck steps, and a no-secret warning; focus trap/Escape/focus return/status-alert/reduced-motion semantics hold; PAT input is a labeled password control cleared after submit; and no credential or launch-grant value appears in DOM after exchange, persistent storage, screenshots, or tests.

### AC-051 — OAuth and public-read PAT surfaces retire without damaging owner or writeback state

**Maps to:** FR-017, FR-019, FR-029 through FR-031, FR-034, FR-037, NFR-001 through NFR-003, NFR-009, NFR-013

- **Given** clean and upgraded runtimes containing no legacy connection, a pending OAuth transaction, an encrypted `identity_public_read` credential, an encrypted `public_read` PAT, active owner/session/local-launch/password state, and an independently configured writeback token,
- **When** the 0.2.1 migration and admin/API/configuration flows run,
- **Then** no OAuth/public-read PAT card, input, guide, callback, redirect, start/check/delete action, or client-secret/callback/encryption-key requirement remains reachable; legacy routes return the bounded non-mutating `410` compatibility response; OAuth transactions/identities/public-read credential rows are removed without decryption or secret output; owner authentication, recovery, sessions, drafts, bundles, and writeback configuration remain valid; and no legacy secret value appears in the DOM, API, logs, fixtures, snapshots, or migration diagnostics.

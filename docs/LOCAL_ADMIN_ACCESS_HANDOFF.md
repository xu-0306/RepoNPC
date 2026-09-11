# RepoNPC 0.2.0 Local Admin Access Handoff

> **0.2.1 follow-up (2026-09-08):** The owner approved removal of GitHub OAuth and browser-entered public-read PATs. OAuth-related instructions below are historical implementation context. Continue from `docs/GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_PLAN.md` / ADR-028.

**Status:** Application implementation integrated into the root working tree on 2026-09-08; final release evidence pending  
**Decision date:** 2026-09-04  
**Normative decision:** ENGD-008 / ADR-027  
**Acceptance focus:** AC-024, AC-041, AC-042, AC-043, AC-049, AC-050

## 1. Why this handoff exists

The implemented 0.1.9 UX creates a first-run dead end. The unauthenticated admin surface advertises GitHub sign-in even when OAuth is unconfigured; **Check configuration** cannot redirect while the required host settings are absent; and a runtime that already contains an owner correctly hides registration but gives the user no understandable recovery path. The owner decided that specifications must change when real use disproves the earlier workflow.

The approved correction does **not** expose unauthenticated admin APIs. It removes visible login ceremony only for a strictly local launcher deployment and retains the existing protected session boundary.

## 2. Approved outcome

### `loopback_evaluation`

- No registration, username/password, or GitHub-login UI.
- After health readiness, the trusted launcher mints a random 256-bit, one-use, two-minute local-launch grant and opens `/admin#local-launch=<grant>`.
- Runtime SQLite stores only the grant SHA-256 digest and timestamps.
- The frontend exchanges the fragment once through same-origin `POST /api/admin/session/local-launch`, immediately calls `history.replaceState`, and stores only the returned CSRF value in memory.
- Grant consumption, sole-owner creation/reuse, session creation, and invalidation of competing unused grants are atomic.
- A direct/expired/replayed visit shows one recovery instruction: reopen RepoNPC with the launcher.
- This mode is valid only with loopback bind, loopback public URL, loopback request peer, allowlisted loopback Host/origin, and no trusted-proxy interpretation. Unsafe configuration fails before startup or fails the exchange generically.

### `production` and every non-loopback administration path

- Retain the 15-minute setup code, sole local username/password, Argon2id, common-password block, backoff, and host-only `admin set-password` recovery.
- Password length remains 15–128 Unicode code points with no composition rule.
- SSH/VPN/private LAN access uses this profile even when the browser-facing end of an SSH tunnel is localhost.
- A passwordless local owner moved to production is not admin-ready until `admin set-password` creates a compliant hash.

### GitHub

- GitHub OAuth is never RepoNPC registration, sign-in, or recovery.
- It is an optional public-read connection started only inside an authenticated GitHub settings screen.
- Unconfigured state opens the safe guide. **Check configuration** only refreshes status; when ready, a separate **Continue to GitHub** button begins PKCE.
- Replace login/link identity intent with authenticated `POST /api/admin/github/connections/oauth/start`.
- Legacy `POST /api/admin/session/github/start` and `/api/admin/setup/github/start` return `410 GITHUB_LOGIN_REMOVED` with no redirect or state change.
- Preserve encrypted OAuth/PAT public-read credentials and writeback separation. Retire identity-only login state without exposing token material.

GitHub App Manifest automation may be evaluated later. It is explicitly outside this implementation.

## 3. Historical baseline before the 0.2.0 implementation

Before the 2026-09-08 integration, the runtime implemented 0.1.9 as follows. This section is retained as diagnosis history; current implementation details and verification evidence are in `docs/LOCAL_ADMIN_ACCESS_IMPLEMENTATION_HANDOFF.md`.

- `src/reponpc/runtime/database.py` migration 3 requires non-null `admin_owner.username` and Argon2id `password_hash`; migration 4 supports `local_password` and `github` auth methods plus OAuth intents `login`, `setup`, and `link`.
- `src/reponpc/admin/auth.py` implements setup-code owner creation, password login, and GitHub login.
- `src/reponpc/api/admin.py` exposes setup/password/GitHub-login routes and the unauthenticated setup guide.
- `apps/web/src/features/admin/AdminPage.tsx` renders the existing setup/login panel and unauthenticated GitHub button.
- `apps/web/src/features/admin/GitHubOAuthSetupGuideDialog.tsx` rechecks readiness but has no configured-state **Continue to GitHub** action.
- `scripts/start-reponpc.ps1` forces loopback settings but currently issues a 15-minute setup code instead of a launch grant.

Observed local runtime on 2026-09-04: `runtime-data/local/runtime.sqlite` contains one owner and one auth method, no open setup row, and live `/api/admin/auth/methods` reports password available / GitHub unavailable. This explains why no registration form appears; do not delete or rewrite this user runtime during implementation/tests.

## 4. Resume here

Implement in the following order. The first change must be the fail-closed loopback configuration guard; do not land a grant endpoint before it.

1. **Configuration boundary**
   - Extend `src/reponpc/config/environment.py` validation for the complete 0.2.0 loopback invariant.
   - Ensure `REPONPC_TRUSTED_PROXY_CIDRS` is empty/disabled in loopback evaluation and forwarded headers cannot establish locality.
   - Add contract tests for IPv4/IPv6 loopback, hostname normalization, malicious Host/Origin, DNS-rebinding-shaped hosts, wildcard/non-loopback binds, and proxy headers.

2. **Transactional migration**
   - Add a new forward-only migration; never edit existing migration SQL.
   - Represent a passwordless sole owner without a fabricated password hash. A table rebuild or separate credential table is acceptable, but existing owner/password rows and session epochs must survive exactly.
   - Add a launch-grant table with digest, creation/expiry/consumption timestamps, and constraints/indexes.
   - Normalize OAuth to connection intent while preserving encrypted `identity_public_read` material as read-only connection data. Migration failure must roll back completely.

3. **Auth service and API**
   - Add host-side grant minting and atomic exchange in `src/reponpc/admin/auth.py`.
   - Add `POST /api/admin/session/local-launch` and update `/api/admin/auth/methods` to `{mode,password:{available},setup_required}`.
   - Restrict setup/password routes to production and return safe stable errors in loopback mode.
   - Keep normal session/CSRF/refresh/logout protections. Loopback logout-all requires a fresh grant; production requires password.

4. **CLI and launcher**
   - Add `reponpc admin launch-token [--data-dir <directory>]`; emit exactly one fragment URL and no extra secret-bearing diagnostics.
   - In `scripts/start-reponpc.ps1`, mint only after `/healthz` succeeds, open the returned URL, and replace any unused grant on rerun.
   - Never pass the grant as a process argument if that exposes it to unrelated process listings; prefer stdout from the bounded child command or another equally contained host handoff.

5. **Frontend access state**
   - Parse `#local-launch` before rendering external links, exchange once, and immediately remove it from the address bar/history.
   - In loopback mode render neither registration nor username/password nor GitHub access controls. Missing/failed grants get one localized relaunch message.
   - Production retains setup/password UI.

6. **GitHub connection-only conversion**
   - Remove GitHub authentication/session issuance and unauthenticated guide access.
   - Require an existing session for OAuth start and callback completion.
   - Move the guide to the authenticated connection area. Add configured-state **Continue to GitHub**; recheck itself never navigates.
   - Preserve PKCE/state/cookie binding, fixed callback, numeric GitHub account metadata, encryption, credential purposes, and no-fallback/writeback isolation.

7. **Verification and documentation reconciliation**
   - Update generated/OpenAPI contracts if present, translations, API clients, examples, and operations evidence.
   - Run all focused Python and frontend tests before the wider suite. Do not edit or use `runtime-data/local` as a fixture.

## 5. Minimum test matrix

- Fresh/existing owner; existing password retained; passwordless local owner; local-to-production transition.
- Valid, expired, replaced, replayed, concurrent, malformed, cross-browser, cross-origin, non-loopback, forwarded, and rate-limited grants.
- URL fragment absent from HTTP request, Referer, logs, DOM after exchange, history, local/session storage, screenshots, snapshots, and error payloads.
- Atomic one-owner/one-use behavior under concurrent exchanges and migration rollback.
- Production setup/login/recovery regression and existing pre-provisioned environment credentials.
- Legacy GitHub login/setup routes cannot redirect or issue sessions; connection start/callback requires the initiating admin session.
- Existing encrypted OAuth/PAT data migrates; revoked/401 connection fails without PAT/writeback fallback.
- `zh-TW`/`en`, 375/768/1024/1440 widths, keyboard focus, screen-reader announcements, Escape/focus return, and reduced motion.
- Frontend format/lint/type/unit/build; Python format/lint/type/unit/contract/integration/security; Docker/Compose and clean-host smoke when available.

Every repository command must follow `AGENTS.md` and prefix each command segment with `rtk`.

## 6. Files expected to change

- `src/reponpc/config/environment.py`
- `src/reponpc/runtime/database.py`
- `src/reponpc/admin/auth.py`
- `src/reponpc/admin/oauth.py`
- `src/reponpc/api/admin.py`
- `src/reponpc/cli.py`
- `scripts/start-reponpc.ps1`
- `apps/web/src/features/admin/AdminPage.tsx`
- `apps/web/src/features/admin/GitHubButton.tsx`
- `apps/web/src/features/admin/GitHubOAuthSetupGuideDialog.tsx`
- Corresponding unit, contract, integration, security, browser, launcher, and accessibility tests

Do not assume every listed file must survive the final design. Deleting the unauthenticated `GitHubButton` path or identity-only code is allowed when tests prove the new contract, but preserve unrelated user changes.

## 7. Documentation already updated

- `docs/TECHNICAL_SPEC.md` → approved 0.2.0 contract
- `docs/DECISIONS.md` → ADR-027
- `docs/ACCEPTANCE_CRITERIA.md` → revised AC-024/041/042/043/049/050
- `docs/SECURITY.md` → localhost threat model and grant controls
- `docs/OPERATIONS.md` → split loopback/production procedures
- `README.md`, `.env.example`, `reponpc.example.yml`
- Local project-memory files `docs/PROJECT_CONTEXT.md`, `docs/OWNER_REVIEW.md`, and `docs/IMPLEMENTATION_PLAN.md` (these are intentionally gitignored in this workspace)

## 8. Baseline evidence and cautions

- Before this documentation change, `rtk pnpm --dir apps/web test -- AdminPage.test.tsx` ran the full Vitest suite and passed 67/67 tests. Those tests encode parts of the old UX and must be changed, not blindly preserved.
- No application tests were rerun for this docs-only handoff because no source code changed.
- Do not claim 0.2.0 implemented until all acceptance checks above pass.
- Do not use GitHub OAuth configuration as a prerequisite for entering settings.
- Do not remove session, CSRF, host/origin, expiry, rotation, revocation, or encryption controls.

## 9. Research basis

- [Chrome Local Network Access](https://developer.chrome.com/blog/local-network-access)
- [MDN Local Network Access](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Local_network_access)
- [Jupyter Server security](https://jupyter-server.readthedocs.io/en/stable/operators/security.html)
- [GitHub OAuth Web Flow](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps)
- [GitHub App Manifest](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-from-a-manifest) — future option only

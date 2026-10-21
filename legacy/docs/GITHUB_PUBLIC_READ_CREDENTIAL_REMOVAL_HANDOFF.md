# RepoNPC 0.2.1 GitHub public-read credential removal implementation handoff

**Updated:** 2026-09-09 (Asia/Taipei)  
**Status:** Review findings corrected; deterministic implementation gates pass in the shared uncommitted worktree  
**Scope:** ADR-028, ENGD-009, FR-031/FR-032/FR-037, AC-044/AC-051/AC-052

## Outcome

- The authenticated admin UI contains no GitHub connection card, OAuth guide/button, recheck/continue action, public-read PAT input, credential status, or missing-credential warning. Manual authoring, validation, preview, copy, and YAML download remain available.
- `GitHubRESTMetadataResolver` resolves public repository metadata plus default/explicit ref anonymously, validates a full 40-character commit SHA, and reuses durable partial resolution only while an attempt remains incomplete. A complete preflight consumes those mutable-ref mappings so a new analysis observes a moved branch/default ref. Request-cost admission covers metadata/ref work and archive cache misses without reducing the 1–50 repository contract.
- `UrllibGitHubArchiveTransport` accepts only the exact `https://codeload.github.com/{owner}/{repository}/legacy.tar.gz/{full_sha}` identity. Wrong owner/repository/SHA, malformed paths, query/fragment/userinfo, hostile host, second redirects, and final URL mismatch fail as `ARCHIVE_UNSAFE` before body consumption. Existing timeout, redirect, SSRF, byte/file/archive-bomb, traversal, link, cancellation, and staging cleanup guards remain.
- Missing/private/inaccessible repositories share the safe `NOT_FOUND` result. Primary/secondary/429 exhaustion returns `GITHUB_RATE_LIMITED` with bounded retry metadata; transient network/timeout/5xx/malformed responses remain retryable service errors rather than being mislabeled missing.
- Discovery, manual resolution, preflight, archive, and embedding-reindex transports share one persisted anonymous GitHub core limiter and never emit `Authorization`. They use fixed GitHub origins plus `Accept`, `User-Agent`, and API-version headers. The quota-bearing archive API redirect is observed before the bounded codeload request. `REPONPC_GITHUB_TOKEN(_FILE)` is loaded only to construct `GitHubAdminClient` for explicit writeback/workflow dispatch.
- OAuth/PAT current-path service, GraphQL credential selection, frontend components, fixtures, and the `cryptography` dependency were removed. Historical migrations and Legacy documentation remain readable.

## Review corrections

The findings in `GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_REVIEW_HANDOFF.md` are addressed as follows:

1. **18–50 repository progress:** metadata hints and durable exact-SHA resolution cache avoid repeated completed calls; each non-resumable repository unit is admitted for its current one/two-call cost; archive cache-miss admission is included. Tests cover 1, 17, 18, and 50 selections, partially consumed budgets, reset continuation, and cache hits/misses.
2. **Archive identity binding:** redirect and final URL validation now bind exact owner, repository, archive format, and full SHA. Production-opener tests cover correct and hostile redirect/final cases.
3. **Error classification:** only deliberately non-disclosing 401/403/404 repository cases become `NOT_FOUND`; rate, timeout, malformed, and service errors retain safe recovery codes. Secondary 403 without usable retry data receives a conservative 60-second retry.
4. **Uniform retired routes:** every compatibility handler accepts only `Request`; malformed/empty/oversized bodies, arbitrary callback parameters, invalid IDs, missing auth, and missing CSRF all return the same bounded 410 envelope without state mutation.
5. **Real tests:** obsolete short-circuited OAuth tests were deleted. REST/archive tests exercise production transports and assert that writeback canaries and `Authorization` never leave the process.
6. **Central rate accounting:** onboarding discovery/manual resolution and embedding reindex now use the same persisted limiter as batch metadata and archive work. Archive redirects contribute their GitHub REST headers before codeload is opened.
7. **Accessible retry state:** blocked preflight responses retain the longest sanitized primary/secondary retry duration; bilingual UI renders it, and `GITHUB_ERROR`/`GITHUB_TIMEOUT` use a transient GitHub-unavailable state.
8. **Mutable-ref freshness:** incomplete rate-limited resolution remains restart-safe, while completed preflight consumes metadata/exact-SHA continuation rows. New preflight attempts therefore resolve current branch/default-ref state. Expired SQLite rows are deleted rather than merely ignored.

## Runtime migration and compatibility

- Migration 14, `retire-github-oauth-public-read-credentials`, transactionally deletes pending OAuth transactions plus `identity_public_read` and `public_read` credential rows without decryption or secret output. It preserves owner/password/session/session epoch/local-launch/draft/batch/bundle/embedding/writeback state. A forced-failure test proves rollback to schema 13 with legacy ciphertext and usable authentication state intact.
- Migration 15, `anonymous-github-resolution-cache`, adds the bounded metadata/exact-resolution cache used for incomplete-attempt rate-reset continuation. Persistence, restart reuse, completed-attempt consumption, logical TTL expiry, and physical expiry pruning are covered.
- Retired setup-guide, connection status, OAuth start/callback, PAT create, check, and delete routes return HTTP 410 with code `GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED`; they never redirect, deserialize credentials, authenticate, decrypt, issue sessions, or mutate owner/setup/credential rows.
- Protected pre-migration backups can still contain encrypted legacy bytes and must remain protected until retention/destruction completes.

## Files

Current-path implementation and tests changed in:

- Backend: `src/reponpc/admin/batch_resolver.py`, `batch_execution.py`, `batch_runtime.py`, `batches.py`, `onboarding.py`, `src/reponpc/api/admin.py`, `src/reponpc/config/environment.py`, `src/reponpc/indexing/github.py`, `src/reponpc/main.py`, `src/reponpc/runtime/database.py`; retired `src/reponpc/admin/oauth.py`.
- Frontend: `AdminPage.tsx`, `AdminWorkspace.tsx`, `BatchAnalysisPanel.tsx` and their tests/styles; retired `GitHubButton.tsx` and `GitHubOAuthSetupGuideDialog.tsx`; retained `LocalLaunchAccessPanel.tsx`.
- Contracts/security: `.env.example`, `reponpc.example.yml`, `compose.yml`, `scripts/start-reponpc.ps1`, `pyproject.toml`, `uv.lock`, environment/launcher/API/migration/batch/resolver/security tests, and release audit inputs.
- Documentation: `README.md`, `docs/TECHNICAL_SPEC.md`, `ACCEPTANCE_CRITERIA.md`, `DECISIONS.md`, `SECURITY.md`, `OPERATIONS.md`, `IMPLEMENTATION_PLAN.md`, the removal plan/review/handoff, local-admin handoff, and agent memory.

The root worktree also contains pre-existing uncommitted 0.2.0 and owner changes. No reset, checkout, or commit was performed.

## Verification

- Ruff format: `158 files already formatted`.
- Ruff lint: `All checks passed!`.
- mypy: `Success: no issues found in 63 source files`.
- Focused resolver/batch/migration/retirement/environment/security: `109 passed, 2 skipped, 1 warning`.
- Contract/release audit: `20 passed`.
- Full Python suite after the second-review corrections, with explicit `D:\RepoNPC\.tmp\full-fix-20260909`: `695 passed, 2 skipped, 1 warning in 79.87s`.
- Frontend Prettier: passed. ESLint: 0 errors, 12 existing Fast Refresh warnings. TypeScript: passed.
- Frontend Vitest after the second-review corrections: 9 files, `67 passed`; external LocalLaunch panel remains 1 file, `6 passed`; Vite production build: passed.
- Docker/Compose smoke: `1 passed in 25.84s`; the unique test project built the image, reached health/public status, preserved its runtime-volume marker across restart, and removed its containers/volume afterward. `docker compose config --quiet` also passed.
- `uv lock --check`: resolved 96 packages. `git diff --check`: passed.
- The requested `pnpm --dir apps/web format:check` script does not exist; the repository's equivalent `format` script is `prettier --check .` and passed.

## Outstanding release evidence and risk

- Not run/claimable: clean-host install, live provider, live GitHub primary/secondary exhaustion, and a real-browser/accessibility pass. The browser skill could not start because its optional global `puppeteer-core` dependency is absent; no global package installation was performed. The local unit/integration/semantic-DOM coverage is deterministic evidence, not a substitute for these Phase 5 checks.
- GitHub anonymous REST capacity is normally 60 requests per source IP per hour and is shared by deployments behind that IP. Large fresh batches may pause across reset windows; durable progress avoids repeating resolved repositories, sanitized retry time is shown, and local/manual work remains available.
- No owner decision is currently required; the approved 1–50 contract remains intact.

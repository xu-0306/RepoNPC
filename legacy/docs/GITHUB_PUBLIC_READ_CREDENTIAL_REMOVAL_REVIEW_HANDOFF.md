# GitHub public-read credential removal review handoff

**Date:** 2026-09-09  
**Status:** Historical review findings resolved in the shared uncommitted worktree; live acceptance evidence remains outstanding  
**Scope:** Follow-up corrections for ADR-028, FR-031, FR-032, FR-037, AC-044, AC-051, and AC-052

## Resolution update (2026-09-09)

The original findings below are retained as review history. The implementation now also closes the second-review gaps that were not represented in the original list:

- discovery, manual resolution, batch preflight/archive work, and embedding reindex share one persisted anonymous GitHub core limiter;
- the quota-bearing GitHub API archive redirect is observed before following the bounded codeload redirect, including conservative classification of a bare secondary-limit `403`;
- blocked preflight state preserves and renders the longest sanitized primary/secondary retry time in Traditional Chinese and English, while transient GitHub service failures no longer appear as selection changes;
- durable metadata/exact-SHA rows survive incomplete rate-limited attempts, but are consumed after a complete preflight so a new analysis re-resolves mutable default/explicit refs; expired rows are physically pruned.

Focused regressions and the full suites pass. AC-052 remains `blocked` in the acceptance ledger only because live GitHub exhaustion and real-browser/accessibility evidence have not run; deterministic implementation completion is not the same as final acceptance.

## 1. Background and owner intent

RepoNPC is primarily a locally deployed, single-owner application. The owner approved removing GitHub OAuth and the browser-entered public-read fine-grained PAT because they created a first-use dead end and disproportionate setup complexity.

The intended 0.2.1 behavior is:

- Local administration continues through the previously implemented local-launch/password setup and recovery model.
- GitHub OAuth is not used for login, owner registration, recovery, or public-repository analysis.
- The authenticated admin UI contains no GitHub OAuth connection card, setup dialog, callback flow, recheck/continue action, public-read PAT input, or missing-OAuth warning.
- Selected public repositories are resolved anonymously through fixed-origin GitHub REST calls.
- Every accepted repository is pinned to a validated full 40-character commit SHA before its archive is downloaded.
- Discovery and analysis never receive an OAuth token, public-read PAT, `REPONPC_GITHUB_TOKEN`, or an `Authorization` header.
- `REPONPC_GITHUB_TOKEN` / `REPONPC_GITHUB_TOKEN_FILE` remain a separate, server-only writeback/workflow-dispatch capability.
- Anonymous rate exhaustion is a recoverable capacity state and must not disable manual authoring, validation, preview, copy, or download.
- Existing encrypted OAuth/PAT runtime records are deleted transactionally without decryption or secret output.
- The existing public contract still accepts 1–50 selected repositories. Do not silently reduce that limit; ask the owner before changing it.

The prior implementation Agent reported the feature complete, but review found release-blocking defects and incomplete cleanup. Preserve all current working-tree changes and do not commit unless the owner explicitly requests it.

## 2. Required reading before changes

Follow `AGENTS.md` and read the required repository documents completely, especially:

1. `docs/PROJECT_CONTEXT.md`
2. `docs/OWNER_REVIEW.md`
3. `docs/TECHNICAL_SPEC.md`
4. `docs/ACCEPTANCE_CRITERIA.md`
5. `docs/DECISIONS.md`
6. `docs/SECURITY.md`
7. `docs/IMPLEMENTATION_PLAN.md`
8. `docs/OPERATIONS.md`
9. `README.md`
10. `reponpc.example.yml`
11. `.env.example`
12. `docs/GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_PLAN.md`
13. `docs/GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_HANDOFF.md`

The specification is approved. ADR-028 and the 0.2.1 amendments are authoritative. Update documentation only when necessary to make it match the corrected implementation; do not weaken the approved contract to make existing code pass.

## 3. Review outcome

The implementation must not yet be marked complete. Correct the following findings in priority order.

### P1 — Valid 18–50 repository batches cannot complete preflight

Relevant code:

- `src/reponpc/admin/batch_resolver.py`, `GitHubRESTMetadataResolver.resolve_page`
- metadata request near line 755
- commit request near lines 768–771
- `GitHubRateLimiter`, default `safety_reserve=25`
- `BatchPreflightPlanner.create`, resolution/catch near lines 1199–1204

The resolver performs two REST requests per selection:

1. `GET /repos/{owner}/{repository}`
2. `GET /repos/{owner}/{repository}/commits/{requested_ref}`

Anonymous GitHub REST normally provides 60 requests per originating IP per hour. With the default 25-request safety reserve, a fresh simulated budget rejects the 36th request. An 18-repository preflight therefore fails after 35 calls. `BatchPreflightPlanner` then discards the partially accumulated resolution, so retrying after reset starts again from the first repository. This makes the existing 18–50 selection range unable to produce a plan.

Confirmed reproduction:

```text
18 confirmed repositories
initial advertised remaining budget: 60
result: GITHUB_RATE_LIMITED
requests already consumed: 35
persisted partial resolution: none
```

The archive request consumes the same REST/core budget, so capacity planning must include metadata, ref resolution, and cache-miss archive requests rather than considering preflight calls alone.

Required correction:

- Preserve the 1–50 API contract.
- Reuse already trusted discovery metadata where it safely avoids duplicate repository requests.
- Add an explicit request-cost/capacity calculation before beginning a non-resumable unit of work.
- Persist or otherwise safely reuse immutable partial resolution so a rate reset does not restart the same calls from repository one.
- Ensure the exact commit result cannot drift across continuation.
- Include archive/cache-hit predictions in admission decisions.
- Do not borrow the writeback token and do not add a new credential prompt.
- If the 1–50 contract truly cannot be maintained, stop and present evidence/options to the owner instead of lowering the limit.

Add tests covering at least 1, 17, 18, and 50 selections, partial progress, reset/continuation, cache hits/misses, and a pre-existing partially consumed rate budget.

### P1 — Archive redirect validation is not bound to the selected source identity

Relevant code:

- `src/reponpc/admin/batch_resolver.py`, `_validate_archive_redirect`, near lines 1491–1505
- `_validate_archive_final_url`, near lines 1508–1509
- `UrllibGitHubArchiveTransport.stream`, redirect handling near lines 306–317

The initial API archive URL is checked against `ResolvedRepository`, but redirect validation only requires:

- HTTPS;
- `codeload.github.com`;
- no userinfo/fragment;
- any path component that resembles a 40-character SHA.

It does not verify that the redirect still identifies the expected owner, repository, and commit SHA. The following unrelated source was accepted by the validator during review:

```text
https://codeload.github.com/unrelated/repository/legacy.tar.gz/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
```

Required correction:

- Bind every redirect and final response URL to the original `ResolvedRepository` or to an equivalent immutable expected archive identity.
- Validate the exact allowed codeload path structure, owner, repository, archive format, and expected commit SHA.
- Reject unrelated repository/SHA redirects with `ARCHIVE_UNSAFE` before reading body bytes.
- Preserve the existing HTTPS, fixed-host, no-userinfo, no-fragment, timeout, redirect, response-size, archive-bomb, path, link, cancellation, and cleanup protections.
- Never forward an authorization header to either the initial archive endpoint or codeload.

Add production-transport tests for correct redirect, wrong owner, wrong repository, wrong SHA, malformed path, second redirect, hostile host, userinfo, query/fragment policy, and final URL mismatch.

### P2 — Transient GitHub failures are incorrectly converted to `NOT_FOUND`

Relevant code:

- `src/reponpc/admin/batch_resolver.py`, `GitHubRESTMetadataResolver.resolve_page`, near lines 789–793
- `GitHubRESTMetadataResolver._get`

`resolve_page` converts every `BatchResolverError` other than `GITHUB_RATE_LIMITED` into a per-repository `NOT_FOUND` blocker. Consequently, DNS/network errors, timeouts, bounded transport failures, GitHub 5xx responses, and generic `GITHUB_ERROR` conditions can be reported as though the repository does not exist.

Confirmed reproduction:

```text
transport raises: GITHUB_ERROR
resolver result: [('o/r', 'NOT_FOUND')]
```

Required correction:

- Use `NOT_FOUND` only for the intentionally non-disclosing private/missing/inaccessible cases.
- Preserve safe retryable categories for network, timeout, GitHub service, primary-limit, and secondary-limit failures.
- Do not expose private-repository existence or upstream response bodies.
- Ensure a secondary-limit `403` without a usable `Retry-After` value is not silently labeled `NOT_FOUND`.
- Present a bilingual, accessible recovery/retry state while retaining the immediate manual path.

Add tests for 404/private, 401, 403 primary exhaustion, 403 secondary exhaustion with and without `Retry-After`, 429, 5xx, timeout, malformed JSON, and oversized responses.

### P2 — Legacy endpoints validate and parse inputs before returning `410`

Relevant code:

- `src/reponpc/api/admin.py`, `GitHubPatRequest`, near line 93
- GitHub callback query declarations near lines 736–738
- PAT route body near lines 891–899
- check/delete `credential_id` path declarations near lines 911–936

FastAPI performs request validation before entering the handler. The early `return _github_public_read_removed(request)` therefore does not guarantee a uniform compatibility response and does not prevent the PAT body from being parsed.

Confirmed results:

```text
PUT /api/admin/github/connections/pat with {}       -> 400 VALIDATION_ERROR
PUT /api/admin/github/connections/pat with token "" -> 400 VALIDATION_ERROR
POST /api/admin/github/connections/0/check          -> 400 VALIDATION_ERROR
DELETE /api/admin/github/connections/0              -> 400 VALIDATION_ERROR
GET /api/admin/github/callback with 513-char state  -> 400 VALIDATION_ERROR
```

This contradicts the claimed uniform `410 GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED` behavior and the requirement that retired routes not accept/parse credential input.

Required correction:

- Make each retired compatibility route a minimal handler whose signature accepts only `Request` and values that cannot trigger framework validation before the handler.
- Do not declare or deserialize a PAT body.
- Do not validate old callback query values or credential IDs before returning the compatibility response.
- Return the same bounded, non-secret, non-mutating `410 GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED` for every request reaching a retired route, regardless of authentication, CSRF, body validity, query length, or path value.
- Do not redirect, decrypt, create OAuth state, issue/revoke sessions, or mutate owner/setup/credential data.
- Remove the unreachable handler bodies after the early returns.

Test malformed JSON, empty/oversized PAT bodies, arbitrary callback parameters, invalid IDs, missing auth/CSRF, and secret canaries. Assert the stable 410 envelope and absence of all state mutation.

### P2 — Tests were short-circuited instead of rewritten

Relevant code:

- `tests/integration/test_github_oauth.py`, unconditional returns near lines 347, 436, 486, 497, 576, and 669
- `tests/unit/test_github_rest_resolver.py`, `test_urllib_rest_transport_strips_authorization_header`, near line 64

Several OAuth integration tests assert one `410` response and then unconditionally `return`, leaving large blocks of old OAuth/PAT assertions unreachable. The new production transport header test merely asserts that a locally created empty dictionary is empty; it never instantiates or exercises `UrllibGitHubRESTTransport`.

Required correction:

- Delete obsolete OAuth/PAT success-flow tests rather than hiding them behind `return`.
- Replace them with focused retirement/migration/no-secret/no-mutation tests.
- Ensure no unreachable legacy assertions or fixtures remain.
- Exercise the actual production REST and archive transports with controlled openers/fakes.
- Verify emitted requests contain no `Authorization`, OAuth/PAT, or writeback canary.
- Add the rate, redirect, error-classification, continuation, and 1–50 coverage described above.

Do not use passing test counts as evidence until these short-circuited and vacuous tests are corrected.

## 4. Incomplete cleanup

The product UI is presently hidden by passing `githubConnectionView={null}`, but significant retired implementation remains:

- OAuth/PAT state, request functions, and callbacks in `apps/web/src/features/admin/AdminPage.tsx`.
- `apps/web/src/features/admin/GitHubButton.tsx`.
- `apps/web/src/features/admin/GitHubOAuthSetupGuideDialog.tsx`.
- OAuth service/storage logic in `src/reponpc/admin/oauth.py`.
- legacy GraphQL credential-selection and bearer-token paths in `src/reponpc/admin/batch_resolver.py`.
- unreachable OAuth/PAT bodies after early returns in `src/reponpc/api/admin.py`.
- migration-era tests and fixtures that still construct public-read credentials for active batch paths.

Historical database migrations and accepted/legacy decision records must remain readable. Current runtime/service/frontend behavior and dead application paths should be removed when they have no remaining consumer. Before deleting shared helpers, inventory imports and confirm they are not used by writeback or another approved capability.

Do not remove or weaken:

- writeback/workflow dispatch through `GitHubAdminClient`;
- historical migration definitions required to upgrade old databases;
- owner authentication, local-launch, password setup/recovery, sessions, drafts, bundles, batch state, or embedding profiles;
- documentation that clearly records historical decisions as legacy/superseded.

## 5. Migration review requirements

Migration 14 currently deletes OAuth transactions and both public-read credential purposes. Migration 13 retires the GitHub authentication method. Keep these operations transactional and prove that:

- pending OAuth transactions are removed;
- `identity_public_read` and `public_read` rows are removed without invoking decryption;
- GitHub owner identities/authentication methods are retired as specified;
- owner username/password, session epoch, active sessions, local-launch state, drafts, batches, bundles, embedding profiles, and unrelated rows remain intact;
- writeback configuration remains intact and available only to `GitHubAdminClient`;
- a deliberately failed retirement migration rolls back schema/version and row changes without losing the last usable authentication state;
- migration errors and logs never contain nonce, ciphertext, PAT, OAuth token, encryption key, callback code, or state plaintext.

Historical protected backups may still contain encrypted legacy bytes; keep that operational warning.

## 6. Verification already performed during review

Read-only review probes confirmed:

- malformed retired route inputs return `400 VALIDATION_ERROR` instead of uniform 410;
- an 18-selection resolver with a fresh simulated 60-request budget fails after 35 calls under the default safety reserve;
- an unrelated codeload repository/SHA redirect passes `_validate_archive_redirect`;
- a transport `GITHUB_ERROR` becomes a `NOT_FOUND` blocker;
- six unconditional early returns exist in the OAuth integration tests;
- the production REST transport test is vacuous.

Focused tests were rerun using a project-local pytest temporary directory:

```text
tests/unit/test_github_rest_resolver.py
tests/integration/test_runtime_database.py
tests/security/test_admin_security.py
tests/integration/test_github_oauth.py

Result: 39 passed, 1 warning
```

The result does not clear the findings because relevant tests are currently short-circuited or missing. The first attempt without an explicit `--basetemp` was blocked by permissions on `C:\Users\xu\AppData\Local\Temp\pytest-of-xu`; that was an environment setup error, not an application test failure.

The implementation handoff records `681 passed, 2 skipped`, while the later Agent report states `689 passed, 2 skipped, 3 warnings`. Re-run the final suite and update every handoff/evidence record to one consistent command/result.

## 7. Required final verification

After correcting the findings, run and report the exact commands/results for the relevant subset of:

- Python formatting check;
- Python lint;
- `mypy src`;
- focused REST resolver, archive, rate-limit, batch, migration, API retirement, and security tests;
- full Python pytest suite using an explicit accessible `--basetemp`;
- frontend Prettier check;
- frontend ESLint;
- frontend TypeScript typecheck;
- frontend Vitest;
- frontend production build;
- browser/accessibility coverage for the removed UI and rate/manual-continuation behavior;
- API and configuration contract tests;
- `git diff --check`.

Do not claim Docker/Compose, live GitHub exhaustion, live model providers, or real-browser evidence unless those checks actually run successfully. Record unavailable checks as not run with the exact reason.

## 8. Definition of done for this follow-up

This correction is complete only when:

1. A valid 1–50 selection can make durable forward progress without repeating already completed anonymous resolution after a rate reset.
2. Admission includes the complete expected REST cost and never borrows writeback authority.
3. Every archive redirect/final URL remains bound to the selected owner/repository/full SHA.
4. Missing/private and transient/rate/service failures have correct, non-disclosing recovery semantics.
5. Every retired OAuth/PAT route returns the same bounded 410 before body/query/path validation and makes no state change.
6. OAuth/PAT frontend and current application service code with no remaining consumer is removed; historical migrations/records remain readable.
7. Migration success and rollback behavior are covered without decrypting or exposing legacy values.
8. Tests exercise production transports and contain no unconditional short-circuit used to hide obsolete assertions.
9. Traditional Chinese and English behavior remain materially equivalent and manual authoring remains immediately available.
10. Documentation, handoffs, and release evidence state one consistent set of verified results.

## 9. Required final report from the implementing Agent

Return:

- outcome and exact files changed;
- explanation of the rate/capacity and resumability design;
- explanation of archive redirect identity binding;
- legacy route behavior matrix, including malformed inputs;
- migration version/behavior and rollback evidence;
- proof that discovery/analysis cannot access the writeback token;
- FR/AC identifiers addressed;
- every command run with pass/fail/not-run results;
- remaining risks or owner decisions;
- confirmation that no commit was created unless explicitly requested.

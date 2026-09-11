# GitHub public-read credential removal plan

**Status:** Owner-approved on 2026-09-08; implemented in the 2026-09-09 working tree  
**Decision:** ADR-028  
**Scope:** Retire GitHub OAuth and browser-entered public-read PATs while preserving public-repository analysis and the independent writeback credential.

## 1. Target outcome

RepoNPC will not ask a self-hosting owner to create a GitHub OAuth App or paste a public-read PAT. The authenticated admin workspace will contain no GitHub connection card, OAuth setup guide, public-read PAT input, or missing-OAuth warning.

Public repository discovery and selected-repository analysis will use bounded unauthenticated GitHub REST requests. Analysis will still resolve an immutable full commit SHA before downloading an archive. GitHub rate limiting is an ordinary recoverable capacity state: the UI reports a safe retry time and always keeps manual authoring, validation, preview, copy, and download available.

This decision does **not** remove the separately configured fine-grained writeback token used for explicitly requested configuration/asset writes, workflow dispatch, or publication. The writeback credential remains server-only, repository-scoped, and structurally unavailable to discovery and analysis.

## 2. Legacy surface to remove

- Admin GitHub OAuth connection card, setup dialog, recheck/continue flow, callback handling, and OAuth start endpoints.
- Browser submission and runtime persistence of `public_read` fine-grained PATs.
- `identity_public_read`, OAuth transaction, GitHub identity, connection-status, and public-read credential selection paths that have no remaining consumer.
- OAuth client ID, client secret, callback URL, and public-read credential-encryption configuration. The implementation must first inventory whether the encryption key has another consumer.
- OAuth/PAT-specific frontend, API, service, migration, security, and launcher tests, replacing them with removal and anonymous-resolution regression coverage.

Historical migrations and decision records remain readable. They are not a reason to retain reachable OAuth/PAT product behavior.

## 3. Replacement contract

1. Normalize and validate only `github.com/<owner>/<repository>` identities already admitted by the selected-only workflow.
2. Resolve public repository eligibility, the requested/default ref, and its immutable commit SHA through fixed-origin, bounded GitHub REST endpoints without an `Authorization` header.
3. Download only an archive addressed by that validated full SHA from the existing fixed GitHub archive origin allowlist.
4. Preserve redirect, hostname, timeout, response-size, archive-bomb, path, symlink, file-count, cancellation, staging-cleanup, and untrusted-content protections.
5. Never send the writeback token as a fallback. Private or inaccessible repositories remain unsupported and non-disclosing.
6. Track REST `core` rate headers and `Retry-After` centrally. On exhaustion, return a safe retry state rather than asking for a credential or repeatedly probing GitHub.
7. Manual contribution authoring remains available before preflight and on every capacity, provider, or GitHub failure.

GitHub documents that unauthenticated REST access to public data is limited to 60 requests per originating IP per hour. This is an accepted constraint for the single-owner, low-frequency local deployment profile; release tests must prove graceful exhaustion behavior rather than assume unlimited capacity.

## 4. Ordered implementation

### Phase A — Contract and compatibility inventory

- Land ADR-028 and the Technical Specification 0.2.1 / acceptance updates.
- Inventory every OAuth/PAT route, environment variable, launcher mapping, runtime table/column, UI state, resolver dependency, fixture, and operational instruction.
- Confirm that `REPONPC_GITHUB_TOKEN(_FILE)` remains writeback-only and that removing the public-read encryption key does not affect another encrypted runtime feature.

### Phase B — Anonymous resolver before UI removal

- Add the bounded unauthenticated REST resolver and exact-SHA archive flow.
- Change preflight, rate-state, durable batch, and error contracts from GraphQL/credential readiness to REST capacity readiness.
- Add public/private/missing/ref/rate-limit/redirect/archive/cancellation tests and prove no `Authorization` header or writeback fallback is used.

### Phase C — Remove product and configuration surfaces

- Remove the authenticated GitHub connection card and every OAuth/PAT browser flow.
- Remove OAuth/PAT API and service code. Legacy endpoints must return a stable `410 GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED` during the compatibility window and must not redirect, accept credentials, or mutate state.
- Stop reading OAuth client/secret/callback/public-read encryption settings. For one compatibility release, recognize their names only to emit a local deprecation warning that contains no value; then remove the names entirely.
- Remove launcher mappings and public examples for the retired variables.

### Phase D — Runtime-data retirement

- Add a transactional migration that deletes OAuth transactions, connection identities, and `identity_public_read` / `public_read` credential rows without decrypting or logging them.
- Preserve owner/session/password/local-launch records and the independent writeback configuration.
- Document that protected backups made before migration may still contain encrypted legacy records and remain subject to the existing backup-retention policy.

### Phase E — Verification and documentation closure

- Update bilingual UI/API/browser/security tests and run the full relevant Python and frontend gates.
- Verify an upgraded runtime, a clean runtime, rate exhaustion, manual continuation, exact-SHA fetching, and writeback isolation.
- Remove legacy operations text after the implementation and migration pass; until then, label it as implemented legacy behavior rather than recommended setup.

## 5. Exit gates

- No OAuth or public-read PAT control, route, callback, secret input, client configuration, or setup guidance remains reachable in the product.
- Public selected-repository analysis succeeds without any GitHub credential when anonymous REST capacity is available.
- Rate exhaustion is bilingual, accessible, retryable, non-secret, and never blocks manual authoring/export.
- No analysis/discovery request contains the writeback token or any authorization header.
- Existing encrypted public-read records are retired without damaging authentication, sessions, drafts, batches, bundles, or writeback configuration.
- Frontend format/lint/type/unit/build, relevant browser/accessibility checks, Python format/lint/type/full tests, API/configuration contracts, migration/security tests, and Git diff checks pass.

## 6. Requirement mapping

- Supersedes the OAuth/PAT portions of FR-030, FR-031, FR-034 and AC-041 through AC-043.
- Amends FR-032 and AC-044 from authenticated GraphQL resolution to unauthenticated REST resolution.
- Adds FR-037 and AC-051/AC-052 for credential retirement, anonymous resolution, migration, rate-limit recovery, and writeback isolation.
- Preserves FR-017, FR-019, FR-026 through FR-029, FR-033, FR-036, NFR-001 through NFR-003, NFR-009, NFR-012 through NFR-014, and the manual path in AC-039/AC-040.

## 7. References

- [GitHub REST API rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- [GitHub GraphQL authentication](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql)

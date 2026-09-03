# RepoNPC v1 Acceptance Criteria

**Document status:** Approved through 0.1.9
**Applies to:** RepoNPC v1 Technical Specification 0.1.9
**Rule:** Every criterion is required unless its mapped requirement is changed through an approved specification update.

## 1. How acceptance works

- `Given / When / Then` describes the externally observable result, not an implementation preference.
- `Automated` criteria MUST run in CI unless they explicitly require a real GitHub Profile, browser, provider, or clean deployment environment.
- `Evaluation` criteria run against committed non-secret fixture repositories and question sets in `evals/`.
- `Manual` criteria require dated evidence in the release checklist, including environment/version and screenshots or logs where suitable.
- A passing happy path does not override a failing security, rollback, conflict, or negative scenario.
- Test fixtures MUST contain both Traditional Chinese and English content, exact code symbols/paths, owner assertions, negative questions, malicious instructions, and deliberately unsupported person claims.

## 2. Configuration and indexing

### AC-001 — Valid configuration is sufficient

**Maps to:** FR-001, FR-018, NFR-010, NFR-013  
**Verification:** Automated contract test plus clean-install test

- **Given** a valid copy of `reponpc.example.yml` and all required deployment secrets,
- **When** a new owner validates the file and starts the documented index/deployment flow without changing source code,
- **Then** the installed `reponpc config validate` and `reponpc index build` entrypoints execute without starting the server, a bundle can be built when required public assets are supplied, and the profile reaches the setup/ready states described in the specification.

### AC-002 — Invalid and unknown configuration is rejected safely

**Maps to:** FR-001, NFR-001

- **Given** configurations containing an unknown root key, unsupported locale, duplicate repository, duplicate claim ID, absolute/parent path, invalid URL, secret field, non-finite weight, or out-of-range limit,
- **When** CLI or admin validation runs,
- **Then** every case returns a stable field-level error without writing to GitHub, starting an index build, or echoing secret-like content.

### AC-003 — Exact source revisions are recorded

**Maps to:** FR-002, FR-010, FR-020, NFR-011

- **Given** repositories configured by default branch, named branch, tag, and commit SHA,
- **When** an index build completes,
- **Then** the manifest/database record one resolved 40-character commit SHA per repository and all generated source links use those SHAs rather than mutable refs.

### AC-004 — Unsafe and excessive files never enter evidence

**Maps to:** FR-003, NFR-001, NFR-002

- **Given** a fixture repository containing binaries, symlinks, submodules, `.env`, private keys, generated/minified/vendor files, lock files, oversized text, excluded paths, and a high-confidence test secret,
- **When** indexing runs,
- **Then** none produce evidence or embeddings, each skip has a reason code, logs do not include contents, and size budgets cannot be exceeded by many individually valid files.

### AC-005 — Supported code uses stable symbol chunks

**Maps to:** FR-004, NFR-011, NFR-013

- **Given** fixture files in Python, JavaScript, TypeScript/TSX, Go, and Rust containing nested and oversized symbols,
- **When** identical inputs are indexed twice,
- **Then** complete bounded symbols are preferred, line ranges are one-based/inclusive/correct, oversize nodes split deterministically, and evidence IDs/content hashes are stable.

### AC-006 — Unsupported text falls back without data loss or overflow

**Maps to:** FR-004, NFR-011

- **Given** Markdown and allowlisted text in unsupported programming languages,
- **When** indexed,
- **Then** heading-aware or line-window chunks cover eligible content, respect overlap/size limits, and retain correct paths and line ranges.

## 3. Retrieval and answer quality

### AC-007 — Lexical retrieval finds exact technical terms

**Maps to:** FR-005, FR-007, NFR-006

- **Given** evaluation questions containing exact filenames, paths, API names, configuration keys, short symbols, English terms, and Traditional Chinese phrases,
- **When** lexical retrieval runs,
- **Then** expected evidence appears in the configured candidate set and no raw question is interpreted as executable FTS syntax.

### AC-008 — Semantic retrieval crosses language and phrasing

**Maps to:** FR-006, FR-022, NFR-006, NFR-008

- **Given** paraphrased and cross-language questions with no exact keyword match,
- **When** vector retrieval uses the bundle-declared production embedding contract,
- **Then** expected evidence is returned, output vectors have the declared finite normalized float32 shape, an external-profile/model/dimension/prefix mismatch prevents readiness, exactly one active embedding profile is reported, and adapter/model load or encode failure does not invoke another provider or model.

### AC-009 — Hybrid retrieval meets the committed benchmark

**Maps to:** FR-005, FR-006, FR-007, NFR-004, NFR-006, NFR-008  
**Verification:** Evaluation and performance test

- **Given** the versioned standard evaluation corpus and questions,
- **When** a Docker candidate limited to four CPUs and 8 GiB receives only the repository fixture and public questions, uses the production embedding adapter, and returns term/trigram/vector/RRF candidates for host-side scoring,
- **Then** Docker inspection and an access probe prove the reviewed oracle was neither mounted nor readable, the host controller derives every pass/provenance boolean, Recall@8 is at least 85%, paired `zh-TW`/`en` questions retrieve materially equivalent expected evidence at least 90% of the time, and warm retrieval p95 is at most 750 ms with image/runtime/host provenance and timing samples recorded.

### AC-010 — Evidence classes cannot be conflated

**Maps to:** FR-008, FR-009, FR-011

- **Given** an owner assertion about responsibility, a repository fact about implementation, and an inference supported by both,
- **When** they are indexed, retrieved, sent to the model, and rendered,
- **Then** each keeps its evidence class, owner statements are visibly labeled, root manifest records classified as `repository_metadata` remain line-addressable `REPOSITORY_FACT`, configured source weighting consumes that category, and the inference lists non-inference supporting IDs.

### AC-011 — Valid answers have immutable citations

**Maps to:** FR-009, FR-010, FR-013, NFR-007

- **Given** supported evaluation questions,
- **When** RepoNPC produces answers,
- **Then** the model supplies selected source IDs only, the backend maps them to indexed records, every rendered citation contains the correct repository/commit/path/lines, and at least 95% of emitted citations resolve to the expected location.

### AC-012 — Claims are entailed and person claims require assertions

**Maps to:** FR-008, FR-009, FR-010, FR-011, NFR-007

- **Given** factual and person-level evaluation claims,
- **When** responses are scored by the committed rubric,
- **Then** at least 90% of material factual claims are entailed by cited evidence and no role, employment, ownership, seniority, responsibility, achievement, or impact is stated as fact without a matching `OWNER_ASSERTION` citation.

### AC-013 — Unsupported questions abstain

**Maps to:** FR-009, FR-011, NFR-007

- **Given** questions about unselected repositories, private work, technologies absent from evidence, unasserted personal contributions, and unrelated topics,
- **When** answers are evaluated,
- **Then** at least 90% explicitly state that available portfolio evidence cannot confirm the answer, do not fabricate a project/claim/citation, and may redirect to supported topics.

### AC-014 — Forged or malformed model output is never published

**Maps to:** FR-009, FR-010, FR-011, NFR-001

- **Given** provider outputs with unknown IDs, invented GitHub URLs, malformed envelopes, unsupported person claims, inference cycles, script-bearing Markdown, or no evidence markers,
- **When** response validation runs,
- **Then** unsafe content is removed or the whole answer becomes a localized abstention after at most one bounded repair; no unvalidated partial answer reaches the client.

## 4. Providers and streaming

### AC-015 — OpenAI-compatible and vLLM providers obey one RepoNPC contract

**Maps to:** FR-012, NFR-005, NFR-013

- **Given** mocked generic OpenAI-compatible and vLLM servers with and without streaming, system roles, structured output, usage, health, selected models, and different context caps,
- **When** capability discovery and generation run,
- **Then** RepoNPC adapts request/parse behavior, enforces the smallest context/output limit, normalizes result/errors, passes no unsupported parameter, maps `vllm` to the OpenAI-compatible transport/bundle identity, supports independent chat and embedding server/model settings, rejects readiness when either selected model is absent, and exposes no key or private URL.

### AC-016 — Ollama remains private and has no cloud fallback

**Maps to:** FR-012, FR-023, NFR-001, NFR-002

- **Given** Ollama is selected and then becomes unreachable,
- **When** health and chat are requested,
- **Then** status reports the safe unavailable state, chat returns `MODEL_UNAVAILABLE`/`PROVIDER_ERROR`, profile/card remain usable, no OpenAI-compatible/cloud endpoint is called, and the private Ollama URL is not exposed.

### AC-017 — SSE event order and terminal behavior are stable

**Maps to:** FR-013, NFR-005, NFR-012

- **Given** successful, abstaining, timed-out, disconnected, and midstream-internal-error requests,
- **When** the public chat endpoint is consumed through streaming fetch,
- **Then** events and headers match the exact contract; success has one metadata and complete event, failure has one terminal error event, citation IDs match answer markers, and request IDs correlate safe logs.

### AC-018 — Limits are enforced before provider cost

**Maps to:** FR-013, NFR-014

- **Given** oversized messages/history, exhausted IP bucket, exhausted UTC daily budget, and full global concurrency,
- **When** another request arrives,
- **Then** it receives the specified 4xx code/retry metadata before an embedding or chat generation call and profile/card endpoints remain available.

## 5. Visitor, character, card, and locale

### AC-019 — Visitor journey works on desktop and mobile

**Maps to:** FR-014, FR-022, FR-023, NFR-003, NFR-009

- **Given** an active bundle with healthy, initially unavailable, and recovered model/status fixtures,
- **When** a visitor opens the site on supported desktop/mobile viewports, selects or edits a suggested question, submits it, receives validated SSE token events, opens a citation, and retries or rechecks after failure,
- **Then** profile/project context, including the localized greeting and configured character animation behavior, remains usable during model degradation; validated token events render progressively without waiting for stream completion; citation evidence class, safe source location, and immutable link are visible; and loading/error/retry, status announcement, and focus behavior work without layout loss.

### AC-020 — Custom and built-in characters share all states

**Maps to:** FR-015, NFR-009

- **Given** a built-in selection, a valid `128x224` custom sheet, and invalid sheets with wrong dimensions/grid/content/size,
- **When** preview/build/rendering runs,
- **Then** both valid modes expose all seven four-frame states, configured frame duration and movement are honored within bounds, invalid assets receive actionable errors and are not written, and reduced motion displays stable first frames.

### AC-021 — Card outputs are static-safe and injection-safe

**Maps to:** FR-016, NFR-001, NFR-009

- **Given** light/dark and both locale variants, including hostile profile text,
- **When** SVG/GIF/PNG endpoints are fetched,
- **Then** outputs are valid `600x180` assets, first/static frames convey complete content, user text is safely escaped/truncated, SVG has required headers and no scripts/handlers/foreign objects/remote references, and ETags change with bundle/variant/revision.

### AC-022 — Real GitHub rendering remains useful

**Maps to:** FR-016, FR-024, NFR-009  
**Verification:** Manual release check

- **Given** generated README snippets committed to a test GitHub Profile,
- **When** viewed through GitHub in current Chrome, Firefox, and Safari with light/dark preferences and animation disabled where possible,
- **Then** the linked card loads through GitHub's image proxy, the static first frame is readable, fallback output works, and the click opens the configured HTTPS RepoNPC site.

### AC-023 — Chinese and English workflows are materially equivalent

**Maps to:** FR-022, NFR-008, NFR-009

- **Given** every visitor/admin route, state, validation error, suggested question, profile field, and standard answer scenario,
- **When** locale switches between `zh-TW` and `en`,
- **Then** neither locale exposes untranslated keys or missing critical content, one verified bundle profile contains both complete locale payloads, the public profile route returns the requested locale without cross-fallback, chat uses the selected language while preserving technical names/citations, and switching does not erase the visible conversation.

## 6. Administration and GitHub writeback

### AC-024 — Admin sessions resist common abuse

**Maps to:** FR-017, NFR-001, NFR-002

- **Given** a fresh deployment without default credentials, host-issued/reissued/expired setup codes, concurrent first-owner attempts, loopback and production password profiles (including three/four/fourteen/fifteen-character, 128-character, Unicode, and common-password cases), repeated failures, absent/forged CSRF, cross-origin requests, expired/rotated/revoked cookies, logout-all, private/public route attempts, and cookie inspection,
- **When** admin endpoints are exercised,
- **Then** only the current 256-bit code can create exactly one owner within 15 minutes, reissue invalidates the prior code, creation/password hashing/code consumption/session issuance are atomic, setup permanently closes afterward, loopback accepts 4–128 while production/non-loopback accepts 15–128 and blocks common passwords, only valid current private/same-origin sessions succeed, backoff applies, cookies carry all required attributes, rotation invalidates the old ID, logout-all revokes all prior sessions, public proxy requests to admin routes are denied, and no plaintext password, setup code, secret, token, or hash appears in response or logs.

### AC-025 — Admin can validate and preview without side effects

**Maps to:** FR-018, FR-022, NFR-003

- **Given** valid and invalid draft configuration in both locales, including authenticated deployments without public-read, writeback, or publication credentials,
- **When** the owner validates and previews it,
- **Then** field errors/warnings and locally resolvable profile/card/character previews are accurate, no GitHub write or model call occurs, manual authoring plus local validation/preview/copy/download remain available, every unavailable GitHub-backed action identifies its specific cause and recovery, a preview that must fetch a custom GitHub asset fails closed, and secrets cannot be added through editor fields or raw YAML.

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

### AC-028 — README snippet generation is copy-ready

**Maps to:** FR-024, FR-016

- **Given** configured public base URL and card revision,
- **When** the owner selects locale, light/dark, and SVG/GIF/PNG variant,
- **Then** generated Markdown uses the exact public asset URL and external-site target, safely encodes values, and renders without owner source edits.

## 7. Publication, update, and recovery

### AC-029 — Publication advances the manifest last

**Maps to:** FR-020, NFR-003, NFR-011

- **Given** successful and deliberately failed builds/uploads,
- **When** the GitHub Action executes the real `config validate`, `index build`, `index publish`, and `index publish-manifest` commands,
- **Then** a successful run validates and publishes one immutable checksummed asset, verifies it, records a local pending manifest, and only then updates `stable-manifest.json`; any failure before the final command leaves the prior stable manifest unchanged and surfaces a failed Action.

### AC-030 — Bundle validation rejects every unsafe candidate

**Maps to:** FR-021, NFR-001, NFR-003

- **Given** candidates with outer/internal checksum failure, excessive size, traversal, symlink, duplicate path, missing file, incompatible schema/app/model/dimension, corrupt SQLite, or failed smoke query,
- **When** runtime update runs,
- **Then** each candidate is rejected/quarantined, never becomes active, produces safe diagnostics, and the current bundle continues serving.

### AC-031 — Activation is atomic and rollback works

**Maps to:** FR-021, NFR-003

- **Given** active bundle A, valid bundle B, in-flight requests using A, and a later owner pin back to A,
- **When** B activates and A is subsequently pinned,
- **Then** in-flight A requests finish on A, new requests use B after one atomic transition, pinning restores A for new requests, and both transitions expose correct version/status without partial files.

### AC-032 — First boot and degraded states are actionable

**Maps to:** FR-021, FR-023, NFR-003, NFR-012

- **Given** no bundle, valid bundle/model unavailable, valid bundle/embedding mismatch, recovered dependencies, and fully ready states,
- **When** public status, health, readiness, profile, card, and chat endpoints are called and the visitor rechecks an unavailable capability,
- **Then** each returns the status/code defined in the technical specification, usable surfaces remain available, no active external embedding profile is reported as ready, the UI identifies what is unavailable and offers a retry/recheck or model-center action where recovery is possible, and sensitive diagnostics are never disclosed.

## 8. Security, privacy, operations, and release quality

### AC-033 — Repository prompt injection has no authority

**Maps to:** FR-003, FR-009, NFR-001

- **Given** repository/configuration evidence instructing the model to ignore policy, reveal secrets, call URLs, run commands, forge citations, or change roles,
- **When** it is retrieved in adversarial chat tests,
- **Then** it remains delimited as evidence, no forbidden capability is invoked, no secret is revealed, citations remain server-owned, and the answer follows RepoNPC policy or abstains.

### AC-034 — Web and SVG output contexts are protected

**Maps to:** FR-014, FR-016, FR-018, NFR-001

- **Given** HTML/Markdown/SVG/URL injection strings in configuration, questions, repository content, provider output, filenames, and commit messages,
- **When** every public/admin preview and response is rendered,
- **Then** no script, event handler, unsafe scheme, markup breakout, traversal, or arbitrary fetch executes and CSP/content-type protections remain present.

### AC-035 — Privacy-safe diagnostics remain useful

**Maps to:** FR-023, NFR-002, NFR-012

- **Given** successful/failing chat, login, writeback, provider, retrieval, and bundle operations containing recognizable canary secrets and personal text,
- **When** logs, runtime database, status endpoints, and error bodies are inspected,
- **Then** request/timing/status/count diagnostics correlate by request ID while raw IPs, bodies, answers, cookies, CSRF, credentials, secret-like evidence, private URLs, and public stack traces are absent.

### AC-036 — Clean self-hosted deployment is reproducible

**Maps to:** NFR-010, NFR-011, NFR-013  
**Verification:** Automated image build plus manual clean-host run

- **Given** a supported clean x86_64 Linux host with Docker Engine, documented secrets, configuration, and published bundle,
- **When** the owner follows `docs/OPERATIONS.md`,
- **Then** one Compose application starts without external database/vector services, connects to a documented external embedding provider (or reports an actionable setup-required state until one is available), health/readiness and bundle identity checks behave correctly, admin routes are loopback/private/VPN-only while visitor routes may remain public, persistent runtime/bundle/profile state survives restart, and locked builds do not require undocumented manual changes.

### AC-037 — Required documentation and release checks are complete

**Maps to:** FR-015, FR-020, FR-021, NFR-001, NFR-010, NFR-013

- **Given** a v1 release candidate,
- **When** the release checklist is reviewed,
- **Then** `OPERATIONS.md`, `SECURITY.md`, and `SPRITE_FORMAT.md` contain every topic required by `TECHNICAL_SPEC.md`, CI/test/evaluation results are linked, browser/GitHub checks are dated, licenses/notices are present, and no FR/NFR is missing acceptance evidence.

## 9. Guided-onboarding acceptance (0.1.4)

The following criteria are normative release requirements under the owner-approved OR-010 and Technical Specification 0.1.4 amendment.

### AC-038 — Public repository discovery requires explicit selection

**Maps to:** FR-025, FR-026, NFR-001, NFR-002, NFR-009

- **Given** an authenticated owner enters a valid username/profile URL, an unknown account, a hostile/non-GitHub URL, a manual public slug/URL, and GitHub pagination/rate-limit fixtures,
- **When** discovery or resolution runs,
- **Then** RepoNPC returns at most 50 public metadata rows per page for at most five pages, normalizes only GitHub.com identities, exposes actionable safe errors, performs no source/tree download or model call, sends no configured writeback token, and does not analyze any repository until the owner checks and confirms it.

### AC-039 — Analysis is selected-only, batch-backed, and evidence-safe

**Maps to:** FR-027, FR-028, FR-008 through FR-012, NFR-001, NFR-002, NFR-014

- **Given** confirmed/unconfirmed repositories, excluded/secret/symlink/binary/generated/oversized content, repository prompt injection, model outage/timeout/invalid output, cancellation/disconnect, legacy one-item requests, and two concurrent attempts by the sole owner,
- **When** the owner explicitly analyzes repositories,
- **Then** only confirmed public repositories enter analysis, every item pins one full commit and reuses production exclusions/chunking/evidence/provider validation, only one owner-scoped durable batch is active, and the legacy one-item route creates a one-item batch instead of bypassing batch policy. The 120-second active-item and configured provider deadlines apply; every terminal/recovery path removes unique staging; no archive, repository body, prompt, provider body, incomplete output, or path becomes durable; only bounded safe progress and validated normalized results may persist; no fallback occurs; and returned results keep `REPOSITORY_FACT` separate from supported `MODEL_INFERENCE`.

### AC-040 — Personal claims require confirmation and the guided flow remains usable

**Maps to:** FR-025, FR-028, FR-018, FR-022, NFR-002, NFR-003, NFR-009

- **Given** bilingual owner statements; model suggestions that omit or strengthen the statement; accept/edit/reject actions; provider-not-ready, missing public-read connection, preflight blocker, analysis failure, and missing GitHub writeback states; backward navigation and repository/ref/include/exclude edits; invalid generated YAML; reload/logout/save; keyboard-only use; and 375/768/1024/1440-pixel viewports,
- **When** the owner completes guided setup,
- **Then** the owner can skip analysis and enter contributions before any preflight or failed request; loading an existing configuration hydrates the guided profile/repository fields for return editing; the original statement remains visible; unconfirmed proposals never become `OWNER_ASSERTION`; Back/Edit preserves profile and unaffected repository input while invalidating only changed selection-bound plans/results; destructive Start over requires confirmation; confirmed role/summary/claims produce valid schema-v1 YAML while validated non-guided fields are preserved; raw edits with unknown/unmappable YAML remain in advanced mode instead of being silently discarded; ordinary validation/preview makes no model or GitHub call; copy/download works without a token; every blocked primary action exposes its cause, next action, and safe alternative; resume stores only approved public draft state and clears it on logout/save; raw YAML remains an advanced path; both locales are materially equivalent; focus/error/status behavior is accessible; and no horizontal content loss occurs.

### AC-047 — External embedding profile CRUD and single-active lifecycle

**Maps to:** FR-006, FR-012, FR-035, NFR-003, NFR-011

- **Given** Ollama, vLLM, and generic OpenAI-compatible profile fixtures; create/read/update/delete/probe/activate requests; duplicate active attempts; invalid credentials/model IDs; changed dimensions/prefixes/normalization; provider outage; and a valid last-known-good bundle,
- **When** the owner manages profiles in Web Admin,
- **Then** at least one external interface can be configured, profile CRUD is authenticated and secret-safe, exactly one profile is active, probe performs a bounded sample embedding and records the observed identity, changed identity enters `reindex_required`/`reindexing`, activation occurs only after a verified reindex and smoke check, failed/cancelled work preserves the last-known-good profile/bundle, and no fallback or local runtime is selected.

### AC-048 — Provider-aware model center and safe installation boundaries

**Maps to:** FR-035, NFR-001, NFR-002

- **Given** curated catalog entries, installed Ollama models, vLLM `/v1/models`, generic embedding endpoints, arbitrary URLs/paths/commands, license acknowledgements, pull progress/cancel/delete, and disk/resource-limit failures,
- **When** the owner opens the embedding model center or requests an installation,
- **Then** Ollama alone exposes bounded native pull/delete operations, vLLM and generic providers expose connect/list/probe/select only, catalog/license/resource information is visible, arbitrary URL/local-path downloads and shell commands are rejected, progress/errors contain no secret/private URL or raw provider body, and a model is not marked ready until its probe and bundle identity pass.

### AC-049 — Deployment-aware password and private admin topology

**Maps to:** FR-017, FR-036, NFR-001, NFR-009

- **Given** explicit `loopback_evaluation` and `production` profiles, boundary passwords, common-password values, public/private interface bindings, unusual ports, SSH tunnels, VPN/LAN allowlists, and reverse-proxy route rules,
- **When** setup, login, password change, recovery, and admin-route requests run,
- **Then** loopback evaluation accepts 4–128 code points, production/non-loopback accepts 15–128 and blocks compromised/common values without composition rules, Argon2id/session/CSRF/backoff controls remain, a non-standard port alone never grants access, SSH/VPN/private routes reach the same Web Admin, public proxies deny `/admin` and `/api/admin/*`, and visitor routes remain independently usable.

### AC-050 — Local recovery and bounded operations CLI

**Maps to:** FR-029, FR-036, NFR-003, NFR-012

- **Given** a fresh owner, optional GitHub link, OAuth outage/revocation, forgotten password, copied runtime database, corrupt backup, active/previous/pinned bundles, and unknown CLI paths/IDs,
- **When** the owner runs the host recovery or runtime/bundle commands,
- **Then** local username/password is created before GitHub binding, the local method remains usable, `reponpc admin set-password --data-dir <dir>` changes only the local hash without reopening setup or changing GitHub identity, `runtime check/backup` are consistent and secret-safe, `bundle verify/pin/unpin` preserve last-known-good state, help/errors are stable, and no second public management protocol is required.

## 10. Traceability matrix

| Requirement | Acceptance criteria |
| --- | --- |
| FR-001 | AC-001, AC-002 |
| FR-002 | AC-003, AC-044, AC-046 |
| FR-003 | AC-004, AC-033, AC-044 |
| FR-004 | AC-005, AC-006 |
| FR-005 | AC-007, AC-009 |
| FR-006 | AC-008, AC-009, AC-046, AC-047 |
| FR-007 | AC-007, AC-009 |
| FR-008 | AC-010, AC-012 |
| FR-009 | AC-011–AC-014, AC-033 |
| FR-010 | AC-003, AC-011, AC-012, AC-014 |
| FR-011 | AC-010, AC-012–AC-014 |
| FR-012 | AC-015, AC-016, AC-046, AC-047 |
| FR-013 | AC-011, AC-017, AC-018 |
| FR-014 | AC-019, AC-034 |
| FR-015 | AC-020, AC-037 |
| FR-016 | AC-021, AC-022, AC-028, AC-034 |
| FR-017 | AC-024, AC-041, AC-049 |
| FR-018 | AC-001, AC-025, AC-027, AC-034, AC-040 |
| FR-019 | AC-026, AC-027 |
| FR-020 | AC-003, AC-029, AC-037 |
| FR-021 | AC-030–AC-032, AC-037 |
| FR-022 | AC-008, AC-019, AC-023, AC-025, AC-040, AC-043 |
| FR-023 | AC-016, AC-019, AC-032, AC-035 |
| FR-024 | AC-022, AC-028 |
| FR-025 | AC-038, AC-040 |
| FR-026 | AC-038 |
| FR-027 | AC-039, AC-045 |
| FR-028 | AC-039, AC-040 |
| FR-029 | AC-041, AC-050 |
| FR-030 | AC-042 |
| FR-031 | AC-043 |
| FR-032 | AC-044 |
| FR-033 | AC-045, AC-046 |
| FR-034 | AC-043 |
| FR-035 | AC-047, AC-048 |
| FR-036 | AC-049, AC-050 |
| NFR-001 | AC-002, AC-004, AC-014, AC-016, AC-024, AC-027, AC-030, AC-033, AC-034, AC-037–AC-039, AC-041–AC-046, AC-048, AC-049 |
| NFR-002 | AC-004, AC-016, AC-024, AC-035, AC-038–AC-042, AC-044–AC-046, AC-048 |
| NFR-003 | AC-019, AC-025, AC-026, AC-029–AC-032, AC-040, AC-043, AC-047, AC-050 |
| NFR-004 | AC-009 |
| NFR-005 | AC-015, AC-017 |
| NFR-006 | AC-007–AC-009 |
| NFR-007 | AC-011–AC-013 |
| NFR-008 | AC-008, AC-009, AC-023 |
| NFR-009 | AC-019–AC-023, AC-038, AC-040, AC-043, AC-049 |
| NFR-010 | AC-001, AC-036, AC-037 |
| NFR-011 | AC-003, AC-005, AC-006, AC-029, AC-036, AC-046, AC-047 |
| NFR-012 | AC-017, AC-032, AC-035, AC-044, AC-045, AC-050 |
| NFR-013 | AC-001, AC-005, AC-015, AC-036, AC-037, AC-042 |
| NFR-014 | AC-018, AC-039, AC-045 |

Version 0.1.9 additions:

| Requirement | Acceptance criteria |
| --- | --- |
| External embedding profiles and provider-aware model management | AC-008, AC-032, AC-047, AC-048 |
| Deployment-aware password/private administration | AC-024, AC-036, AC-049 |
| Local-first GitHub binding and host recovery | AC-041, AC-042, AC-050 |
| Bounded operations CLI | AC-049, AC-050 |

Version 0.1.4 additions:

| Requirement | Acceptance criteria |
| --- | --- |
| FR-025 | AC-038, AC-040 |
| FR-026 | AC-038 |
| FR-027 | AC-039 |
| FR-028 | AC-039, AC-040 |

Version 0.1.5 strengthens existing FR-012/AC-015 with the named vLLM preset; it adds no requirement ID, browser endpoint, or bundle schema.

Version 0.1.8 strengthens FR-031/AC-043 with actionable OAuth setup guidance and the safe setup-guide endpoint; configured OAuth flow, credential purposes, and writeback isolation do not change.

The 2026-08-30 usability clarification strengthens existing FR-025, FR-027, FR-028, NFR-003, AC-019, AC-025, AC-032, and AC-040 without changing an endpoint, credential boundary, provider fallback rule, or schema: optional analysis has an immediate manual path, guided navigation is reversible with selective invalidation, and unavailable capabilities explain their cause/recovery without disabling unrelated local work.

### AC-041 — GitHub OAuth creates only the same sole owner

**Maps to:** FR-017, FR-029, NFR-001, NFR-002

- **Given** configured and unavailable OAuth operators; valid/invalid, expired, replayed, cross-browser, and cross-intent OAuth state/PKCE transactions; linked/unlinked and renamed GitHub identities; and concurrent password/GitHub first-owner attempts,
- **When** a first owner sets up, an existing owner signs in, or an authenticated password owner links GitHub,
- **Then** the host proof followed by local username/password creation remains required for initial ownership, exactly one owner can be created, GitHub OAuth can be linked only from that authenticated local owner, code consumption/session issuance are atomic, `/user` numeric identity is used, wrong/unlinked identities receive only `INVALID_CREDENTIALS`, OAuth callback/session cookies carry the required scoped attributes, the local password remains available for recovery, and no token, verifier, secret, state plaintext, or identity-disclosure detail reaches browser storage, APIs, logs, fixtures, or runtime plaintext.

### AC-042 — Credential purposes, migration, and recovery fail closed

**Maps to:** FR-030, NFR-001, NFR-002, NFR-013

- **Given** existing password/pre-provisioned deployments, absent/invalid encryption keys, OAuth credentials with no scope or unsafe broad scope, expired/revoked credentials, PAT submissions, writeback credentials, and an attempted final-method unlink,
- **When** migrations, OAuth/PAT persistence, validation, linking, unlinking, and GitHub-backed work run,
- **Then** existing password sign-in remains valid, encrypted credential records never contain plaintext, OAuth/PAT credentials retain their explicit read-only purpose, writeback is never reused, a `401` requires explicit reconnection without fallback, GitHub-only ownership is rejected because local-first setup is mandatory, host-only `reponpc admin set-password` restores local access without reopening setup or changing GitHub identity, and the final local authentication method cannot be removed.

### AC-043 — Dual sign-in and connection UI is accessible and secret-safe

**Maps to:** FR-031, FR-034, FR-022, NFR-001, NFR-009

- **Given** setup, local-password-only, dual-method, unavailable-OAuth, denial/callback-error, linking, PAT, and connection-required states in `zh-TW` and `en`,
- **When** keyboard and assistive-technology users operate `/admin` at 375, 768, 1024, and 1440 pixels,
- **Then** configured OAuth buttons perform a top-level PKCE redirect, while an unconfigured OAuth button remains operable and opens a labeled host-side setup dialog without redirecting or submitting secrets; the dialog exposes only the authoritative callback URL, fixed GitHub documentation link, host-secret/restart/recheck steps, and a no-secret warning, supports focus trap/Escape/focus return/status-alert semantics and reduced motion, password and GitHub pending/error state remain independent, exactly one actionable authentication error is announced, prerequisite-disabled controls explain why, focus returns to the authentication summary after callback failure, PAT input is a labeled password control cleared after submit, and no credential value appears in DOM, storage, screenshots, or tests.

### AC-044 — GitHub preflight is immutable, bounded, and credential-safe

**Maps to:** FR-032, FR-002, FR-003, NFR-001, NFR-002, NFR-012

- **Given** confirmed and unconfirmed selections; public, private, inaccessible, archived, malformed, and duplicate repositories; OAuth/PAT/writeback credential fixtures; GraphQL metadata, primary/secondary limit, `Retry-After`, reset, redirect, traversal, symlink, archive-bomb, and cancellation fixtures,
- **When** a batch preflight and exact-SHA source fetch run,
- **Then** no unconfirmed/ineligible repository enters analysis; one page covers at most 100 selected repositories; every accepted item records one full commit SHA and uses its immutable archive; compressed/expanded bytes, entries, paths, links, files, time, and cleanup are bounded; no per-blob batch path occurs; selected OAuth/PAT read capacity never uses writeback; a `401` changes only that selected connection to connection-required; and primary/secondary pauses produce safe retry state without busy looping.

### AC-045 — Durable analysis batches preserve safe bounded progress

**Maps to:** FR-033, FR-027, NFR-001, NFR-002, NFR-012, NFR-014

- **Given** duplicate idempotency requests, reload/SSE reconnect, pause/resume/cancel, partial failures, expired plans, restart during every stage, rate waiting, provider contention, and interrupted generation fixtures,
- **When** the owner starts a multi-repository batch or the legacy one-item route,
- **Then** exactly one active owner batch and one idempotent job are observed; snapshots/events replay monotonically; every item keeps its immutable commit, isolated staging, validated terminal result, and terminal cleanup; public chat retains provider opportunities; stage caps are never exceeded; restart repeats only immutable fetch/index or verified cache work; cancelled/in-flight provider output is discarded; and a dispatched generation becomes explicit-retry-only rather than being automatically resent.

### AC-046 — Analysis caches are identity-complete and private

**Maps to:** FR-033, FR-002, FR-006, FR-012, NFR-001, NFR-002, NFR-011

- **Given** otherwise equal batches whose commit, include/exclude policy, parser version, embedding identity, chat model, prompt version, output-schema version, or validation version differs,
- **When** cache prediction/reuse and expiry cleanup run,
- **Then** only checksummed/integrity-checked compatible derived indexes and validated normalized results are reused; every identity change misses the corresponding cache; raw source/archive/prompt/provider body never persists; and TTL/LRU cleanup removes expired entries without changing active work or prior validated results.

## 11. Approval result format

Release acceptance MUST report:

- application version and bundle ID;
- commit SHA and test environment;
- every AC ID as pass/fail/not-run with linked evidence;
- benchmark totals and confidence/reviewer method;
- all exceptions approved by the owner;
- remaining known limitations that are within the explicit v1 exclusions.

No criterion may be marked passed merely because implementation exists; observable evidence is required.

The current machine-readable evidence ledger is `release-evidence/acceptance-ledger.json`. It is the authoritative per-criterion status record; local implementation tests and external/manual evidence must be appended there with reproducible commands and artifact hashes.

# RepoNPC v1 Acceptance Criteria

**Document status:** Draft  
**Applies to:** RepoNPC v1 Technical Specification 0.1.0  
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
- **Then** validation succeeds, a bundle can be built, and the profile reaches the setup/ready states described in the specification.

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
- **When** vector retrieval uses the bundle-declared embedding contract,
- **Then** expected evidence is returned, output vectors have the declared finite normalized shape, and a model/dimension/prefix mismatch prevents readiness.

### AC-009 — Hybrid retrieval meets the committed benchmark

**Maps to:** FR-005, FR-006, FR-007, NFR-004, NFR-006, NFR-008  
**Verification:** Evaluation and performance test

- **Given** the versioned standard evaluation corpus and questions,
- **When** term/trigram lexical ranks and vector ranks are fused with configured RRF and final `k=8`,
- **Then** Recall@8 is at least 85%, paired `zh-TW`/`en` questions retrieve materially equivalent expected evidence at least 90% of the time, and warm retrieval p95 is at most 750 ms on the documented reference host.

### AC-010 — Evidence classes cannot be conflated

**Maps to:** FR-008, FR-009, FR-011

- **Given** an owner assertion about responsibility, a repository fact about implementation, and an inference supported by both,
- **When** they are indexed, retrieved, sent to the model, and rendered,
- **Then** each keeps its evidence class, owner statements are visibly labeled, and the inference lists non-inference supporting IDs.

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

### AC-015 — OpenAI-compatible providers obey one RepoNPC contract

**Maps to:** FR-012, NFR-005, NFR-013

- **Given** mocked compatible servers with and without streaming, system roles, structured output, usage, health, and different context caps,
- **When** capability discovery and generation run,
- **Then** RepoNPC adapts request/parse behavior, enforces the smallest context/output limit, normalizes result/errors, and passes no unsupported parameter.

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

**Maps to:** FR-014, FR-022, FR-023, NFR-009

- **Given** an active bundle and healthy model,
- **When** a visitor opens the site on supported desktop/mobile viewports, selects or edits a suggested question, submits it, and opens a citation,
- **Then** profile/project context, character states, streamed answer, evidence labels, immutable link, loading/error state, and focus behavior are usable without layout loss.

### AC-020 — Custom and built-in characters share all states

**Maps to:** FR-015, NFR-009

- **Given** a built-in selection, a valid `128x224` custom sheet, and invalid sheets with wrong dimensions/grid/content/size,
- **When** preview/build/rendering runs,
- **Then** both valid modes expose all seven four-frame states, invalid assets receive actionable errors and are not written, and reduced motion displays stable first frames.

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
- **Then** neither locale exposes untranslated keys or missing critical content, chat uses the selected language while preserving technical names/citations, and switching does not erase the visible conversation.

## 6. Administration and GitHub writeback

### AC-024 — Admin sessions resist common abuse

**Maps to:** FR-017, NFR-001, NFR-002

- **Given** valid/invalid passwords, repeated failures, absent/forged CSRF, cross-origin requests, expired/rotated/revoked cookies, logout-all, and cookie inspection,
- **When** admin endpoints are exercised,
- **Then** only valid current same-origin sessions succeed, backoff applies, cookies carry all required attributes, rotation invalidates the old ID, logout-all revokes all prior sessions, and no secret/token/hash appears in response or logs.

### AC-025 — Admin can validate and preview without side effects

**Maps to:** FR-018, FR-022

- **Given** valid and invalid draft configuration in both locales,
- **When** the owner validates and previews it,
- **Then** field errors/warnings and profile/card/character previews are accurate, no GitHub write or model call occurs, and secrets cannot be added through editor fields or raw YAML.

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
- **When** the GitHub Action executes,
- **Then** a successful run validates and publishes one immutable checksummed asset before updating `stable-manifest.json`, while any failure leaves the prior stable manifest unchanged and surfaces a failed Action.

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

- **Given** no bundle, valid bundle/model unavailable, valid bundle/embedding mismatch, and fully ready states,
- **When** public status, health, readiness, profile, card, and chat endpoints are called,
- **Then** each returns the status/code defined in the technical specification, usable surfaces remain available, and sensitive diagnostics are never disclosed.

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
- **Then** one Compose application starts without external database/vector services, health/readiness succeed, persistent runtime/bundle state survives restart, and locked builds do not require undocumented manual changes.

### AC-037 — Required documentation and release checks are complete

**Maps to:** FR-015, FR-020, FR-021, NFR-001, NFR-010, NFR-013

- **Given** a v1 release candidate,
- **When** the release checklist is reviewed,
- **Then** `OPERATIONS.md`, `SECURITY.md`, and `SPRITE_FORMAT.md` contain every topic required by `TECHNICAL_SPEC.md`, CI/test/evaluation results are linked, browser/GitHub checks are dated, licenses/notices are present, and no FR/NFR is missing acceptance evidence.

## 9. Traceability matrix

| Requirement | Acceptance criteria |
| --- | --- |
| FR-001 | AC-001, AC-002 |
| FR-002 | AC-003 |
| FR-003 | AC-004, AC-033 |
| FR-004 | AC-005, AC-006 |
| FR-005 | AC-007, AC-009 |
| FR-006 | AC-008, AC-009 |
| FR-007 | AC-007, AC-009 |
| FR-008 | AC-010, AC-012 |
| FR-009 | AC-011–AC-014, AC-033 |
| FR-010 | AC-003, AC-011, AC-012, AC-014 |
| FR-011 | AC-010, AC-012–AC-014 |
| FR-012 | AC-015, AC-016 |
| FR-013 | AC-011, AC-017, AC-018 |
| FR-014 | AC-019, AC-034 |
| FR-015 | AC-020, AC-037 |
| FR-016 | AC-021, AC-022, AC-028, AC-034 |
| FR-017 | AC-024 |
| FR-018 | AC-001, AC-025, AC-027, AC-034 |
| FR-019 | AC-026, AC-027 |
| FR-020 | AC-003, AC-029, AC-037 |
| FR-021 | AC-030–AC-032, AC-037 |
| FR-022 | AC-008, AC-019, AC-023, AC-025 |
| FR-023 | AC-016, AC-019, AC-032, AC-035 |
| FR-024 | AC-022, AC-028 |
| NFR-001 | AC-002, AC-004, AC-014, AC-016, AC-024, AC-027, AC-030, AC-033, AC-034, AC-037 |
| NFR-002 | AC-004, AC-016, AC-024, AC-035 |
| NFR-003 | AC-026, AC-029–AC-032 |
| NFR-004 | AC-009 |
| NFR-005 | AC-015, AC-017 |
| NFR-006 | AC-007–AC-009 |
| NFR-007 | AC-011–AC-013 |
| NFR-008 | AC-008, AC-009, AC-023 |
| NFR-009 | AC-019–AC-023 |
| NFR-010 | AC-001, AC-036, AC-037 |
| NFR-011 | AC-003, AC-005, AC-006, AC-029, AC-036 |
| NFR-012 | AC-017, AC-032, AC-035 |
| NFR-013 | AC-001, AC-005, AC-015, AC-036, AC-037 |
| NFR-014 | AC-018 |

## 10. Approval result format

Release acceptance MUST report:

- application version and bundle ID;
- commit SHA and test environment;
- every AC ID as pass/fail/not-run with linked evidence;
- benchmark totals and confidence/reviewer method;
- all exceptions approved by the owner;
- remaining known limitations that are within the explicit v1 exclusions.

No criterion may be marked passed merely because implementation exists; observable evidence is required.

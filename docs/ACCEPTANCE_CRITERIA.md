# RepoNPC v1 Acceptance Criteria

**2026-09-22 local-publication amendment (ADR-046):** The owner authorized implementation of the local-first NPC and guided GitHub card journey. [Local publication contract](LOCAL_PUBLICATION_CONTRACT_2026-09-22.md) supersedes GitHub-only configuration/build/activation transport; all validation, attribution, privacy and last-known-good requirements remain. Implementation/acceptance evidence must distinguish local tests from actual public deployment.

**Owner-approved automatic alignment and pixel-offset amendment (2026-09-22, ADR-045; FR-015/018, AC-020/023):** After choosing a converted asset, consistent non-clipping column drift across at least half of the seven states is automatically composed and accepted only after protected canonical validation. An isolated moving state, ambiguous competing patterns, clipped/excessive offsets, and already stable frames do not receive automatic correction. Every frame has labeled integer X/Y pixel fields with safe limits, live preview, invalid-entry feedback, manual apply/validation, and restore. Edge-cleanup version choice precedes alignment; source files and GitHub remain untouched without separate owner action.

**Owner-approved edge-spill cleanup amendment (2026-09-22, ADR-044; FR-015/018, AC-020/023):** A structural grid with a shallow, preceding-row-continuous fragment and transparent gap offers a separately validated cleaned preview, while the original remains available. The owner compares the same state/frame and explicitly chooses a version before download/writeback. Unrelated detached effects, art connected to the current frame, deeper or ambiguous boundary content, manifest frames, unfamiliar species and filenames, and stable grids receive no invented cleanup. Source bytes remain unchanged; selected cleanup and subsequent alignment never bypass canonical validation or ordinary writeback security.

**Owner-approved frame-position repair amendment (2026-09-22, ADR-043; FR-015/018, AC-020/023):** Converted sprites with unintended frame-to-frame horizontal drift offer a reversible visual alignment suggestion and non-clipping per-frame X/Y adjustment. Draft adjustments do not change download/writeback until explicit apply passes the existing protected canonical validation endpoint. Stable frames receive no invented motion, arbitrary species and filenames behave identically, invalid/cropping edits fail safely, and bilingual keyboard/reduced-motion behavior remains intact.

**Owner-approved ordinary-owner character-workspace amendment (2026-09-22, ADR-042; FR-015/018, NFR-003/009, AC-020/023):** Character setup is a first-level authenticated admin destination, not hidden under raw YAML. The default flow is plain-language upload, visual selection, seven-state animation preview, and download/save; conversion policies and diagnostics use progressive disclosure and reduced motion remains effective.

**Owner-approved novice material discovery amendment (2026-09-21, ADR-041; FR-015/018, AC-020):** An authenticated owner may drop/select a PNG or ZIP, or select a folder, without renaming files or authoring a manifest. Manifestless bundles are inspected structurally: one candidate converts automatically, several return visual choices, none fail actionably, and a selected candidate is content-bound and revalidated. No filename/species heuristic or inspection-time write is allowed.

**Owner-approved 64px canonical sprite and material-conversion amendment (2026-09-21, ADR-040; FR-015/018, AC-020):** Canonical frames are `64x64` in a `256x448` sheet, with no undeployed 32px compatibility path. The authenticated converter derives arbitrary square-cell grid sizes structurally or consumes an exact 28-frame manifest ZIP, produces a deterministic preview/report, rejects missing or unsafe material, and commits only separately confirmed canonical PNG bytes.

**Owner-approved species-neutral character-pack amendment (2026-09-21, ADR-039; FR-015/018, AC-020):** Built-in configuration uses only a versioned pack identity and bounded pack-owned options; core code has no species enum or humanoid slot contract. The undeployed humanoid top-level fields are rejected without aliases. An independently defined non-humanoid fixture pack must compile through the same generic path without core changes, while arbitrary custom species continue to use the canonical sheet.

**Owner-approved URL editing exception (2026-09-12, ADR-029; FR-038/040, AC-055/057):** The owner explicitly requested that replacing a managed service URL prefill its saved value. Only `POST /api/admin/model-connections/{connection_id}/edit-endpoint`, guarded by the existing owner session, same-origin check and CSRF, may return `{connection_id, revision, base_url}` with `Cache-Control: no-store`. It accepts no arbitrary URL, reads the exact current encrypted revision, rejects host-managed/unknown connections with 404 and unavailable secret storage with 503, and makes no provider request or mutation. List/detail metadata remains URL-free; API keys, secret references and environment values are never returned. The UI fetches only on the explicit Replace URL action, keeps the result in the active form only, clears it on cancel/toggle-off/teardown, and ignores responses after a form or revision change. Loading disables URL editing/submission; failure permits retry or manual entry. No readback URL may enter browser storage, public drafts, exports, logs or snapshots. This narrow exception supersedes earlier blanket stored-URL readback prohibitions; stored-key prohibitions and destination-change credential rules remain unchanged.

**Owner-approved environment-connection control amendment (2026-09-12, ADR-031; FR-039/040, AC-055/056/057):** Host-managed cards expose edit/delete. Replacement requires a complete new URL without reading the environment URL, promotes the connection to owner-managed, and survives environment changes/restarts. A prior key cannot cross destinations; an existing no-key state may remain no-key. Deletion is reference-safe and writes a secret-free durable suppression marker so restart does not recreate the default.

**Owner-approved session-resume amendment (2026-09-13, ADR-033; FR-017/029/031, AC-049/050):** Reloading an authenticated admin page first resumes the still-valid HttpOnly-cookie session through strict same-origin `POST /api/admin/session/resume`. It returns only memory-held session-bound CSRF and expiry metadata with `Cache-Control: no-store`, consumes no launcher grant, and preserves generic failure, expiry, revocation, host/origin, and deployment-profile recovery behavior.

**Owner-approved same-service URL and actionable-error amendment (2026-09-14, ADR-035; FR-039/040, NFR-003, AC-055/057):** Same-provider URL edits retain a key only when normalized scheme, hostname, and effective port are unchanged; a path-only `/v1` correction is allowed, while provider/origin changes require replace/remove intent. Every connection create/update/delete/refresh failure yields one operation-scoped accessible alert with safe cause, preservation state, recovery action, affected-field association, focus, and a safe request ID when available. Submitted keys still clear and the alert explains re-entry.

**Owner-approved chat-probe grace amendment (2026-09-14, ADR-036; FR-038/040, AC-054/057):** Chat probe acceptance uses one provider request with a 10-second baseline plus one automatic 10-second grace window. A response completing during the grace window passes normal response validation. Timeout is reported only after the 20-second total deadline, with no second request, activation, or provider/model fallback.

2026-09-12 UI/event follow-up evidence (partial AC-019/023/025/038/040/057/058): shared checkbox semantics and responsive alignment, select font inheritance, status-card and long-text reflow, credential-intent event ordering, account discovery pagination reset with collected projects preserved, revision-bound installed-model lists with stale-response rejection, raw-draft preview invalidation, and suggestion-input focus. See [dated UI/system event audit](UI_SYSTEM_EVENT_AUDIT_2026-09-12.md) and `tests/browser/`. The 40 layout cases use root-font enlargement, not native browser zoom; synthetic browser tests and 121 frontend tests do not constitute full AC, live-provider, screen-reader, or novice-walkthrough acceptance.

2026-09-12 owner-approved novice setup regression scope (FR-038/039/040, AC-054/055/057/058; bilingual AC-023): optional embedding dimensions remain unknown until an explicit successful two-sample test; unknown/failed/stale profiles cannot be activated or selected as ready. Existing dimensions, selections, switch intents and foreign keys survive runtime migration 19, including rollback on migration failure. Name-only service edits retain protected endpoint/key and revision; destination changes require explicit credential intent. Newly entered keys clear after submission and form closure. Scoped Ollama listing is explicit and distinguishes failure from empty. Successful operation results survive a failed/stale list refresh. These focused checks do not constitute full v1 or release acceptance.

**Document status:** Approved through 0.3.8
**Applies to:** RepoNPC v1 Technical Specification 0.3.9
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

**0.2.2 amendment:** Model-list presence is not mandatory when listing is unsupported. A typed ID must pass the actual bounded chat/embedding capability test; known missing models and failed tests remain unavailable. Provider keys/private URLs may be entered only through section 11.5's protected write-only form, never returned.

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

### AC-020 — Species-neutral built-in packs and custom characters share all states

**Maps to:** FR-015, NFR-009

- **Given** the registered humanoid pack, a test-only non-humanoid pack whose options contain no humanoid fields, a valid `256x448` custom sheet representing an arbitrary user-defined species/form, structurally valid source grids with multiple previously unseen square cell sizes, a manifest ZIP with explicit 28-frame mappings, ordinary manifestless ZIP/folder bundles with zero/one/several structural candidates and unrelated files, malformed/unsafe/missing-frame material, a forged/stale candidate ID, legacy humanoid top-level configuration, and invalid canonical sheets with wrong dimensions/grid/content/size,
- **When** the authenticated owner opens the first-level Character & animation workspace, drops/selects a PNG or ZIP, selects a folder, chooses a returned candidate when required, switches among seven animated state previews, or runs preview/build/rendering,
- **Then** no raw-YAML knowledge is required; default copy and actions describe the owner's task rather than canonical-grid internals, while conversion policies/full sheets/diagnostics are progressively disclosed; both packs compile through the same species-agnostic registry path without modifying core configuration/composition; grid cell size is structurally derived rather than matched to examples; no filename/folder/species/content heuristic chooses meaning; one discovered candidate converts automatically, several return visual choices, none fail actionably, and a selected candidate is rebound to the submitted path/bytes; `pixel_exact` accepts only integer ratios while `pixelize` returns deterministic 64px frames plus bounded review warnings; manifest paths/counts/frames/images and all archive/folder security ceilings are validated before decode/use; missing frames are never synthesized; discovery/conversion performs no write; only a separately confirmed canonical PNG can be downloaded or written; all valid built-in/custom modes expose all seven four-frame states; configured frame duration and movement are honored within bounds; unknown pack/version/options, legacy fields, unsafe archives, stale/forged selection and invalid assets fail without fallback or mutation; and reduced motion displays stable first frames.

Frame-position regression: unseen sheets with a repeated column-displacement pattern across at least half of the states receive non-clipping automatic correction after protected validation, independent of species, filename, pose, or source cell size. One isolated moving state, incompatible patterns, excessive or clipping offsets, and an already aligned sheet do not auto-correct. The owner can inspect the animation, enter integer X/Y pixels for every frame, use keyboard one-pixel controls, restore the original, and explicitly apply later edits. Before successful protected validation, adjusted download/writeback remains unavailable; after validation it uses only returned canonical bytes. Invalid input and failed validation preserve the chosen original asset. The seven-state preview and reduced-motion first-frame rule still apply.

Edge-spill regression: source grids of more than one previously unseen cell size with a shallow top fragment continuous with the preceding row and separated from the present sprite yield original and cleaned canonical bytes, affected frame coordinates, and a no-write comparison in the same conversion flow. Download/writeback is unavailable until the owner chooses one version. Selecting either version and later position alignment uses exactly that version. Unrelated floating art, art connected to this frame, ambiguous or deep edge content, and explicit manifest packs do not trigger deletion; the uploaded bytes remain unchanged. Both locales, keyboard actions, reduced motion, and narrow layouts remain usable.

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

- **Given** a fresh deployment without default credentials; valid, expired, replayed, reissued, concurrent, cross-origin, forwarded, and non-loopback local-launch grants; production setup codes and password boundaries; repeated failures; absent/forged CSRF; expired/rotated/revoked cookies; logout-all; private/public route attempts; and cookie inspection,
- **When** admin endpoints are exercised,
- **Then** `loopback_evaluation` accepts only the current host-minted 256-bit two-minute grant under strict loopback/no-trusted-proxy conditions, consumes it atomically, creates or reuses exactly one owner, issues at most one session, clears the browser fragment, and presents no registration/password/GitHub login form; production accepts only the current 256-bit 15-minute setup code and a compliant 15–128-character non-common password; only valid private/same-origin sessions succeed; backoff/rate limits apply; cookies carry all required attributes; rotation invalidates the old ID; logout-all revokes prior sessions using profile-appropriate proof; public proxy requests to admin routes are denied; and no plaintext password, setup code, launch grant, secret, token, or hash appears in responses, logs, Referer headers, browser history, fixtures, or snapshots.

### AC-025 — Admin can validate and preview without side effects

**0.2.2 clarification:** The no-secret editor rule applies to public portfolio fields/raw YAML. The isolated model-connection form is the sole provider-key ingress exception; it cannot serialize secrets into a portfolio draft.

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

**0.2.7 / ADR-034 regression, amended by 0.3.0 / ADR-037:** With `REPONPC_ANALYSIS_MAX_OUTPUT_TOKENS` absent, actual analysis generation requests 8,192 tokens when provider/context capacity permits. An explicit 16,384 is accepted; non-positive, non-integer and larger values are rejected safely. Visitor/probe output remains independent and now uses the ADR-037 4,096-default / 8,192-maximum policy; contribution suggestions remain 700. Both analysis paths reserve full prompt, evidence/IDs, schema/framing and output before generation; insufficient context triggers no chat call. A returned `length` termination or adapter empty-output/length diagnostic fails with `PROVIDER_ERROR` / `PROVIDER_OUTPUT_LIMIT_REACHED` before parsing, even for valid JSON, without retry, raw-output retention or successful cache insertion. Normal complete bilingual output still passes canonical/evidence/person validation. Exercise OpenAI-compatible and Ollama transports, a smaller actual provider capability and clean application wiring; synthetic results do not establish live-model quality.

**Maps to:** FR-027, FR-028, FR-008 through FR-012, NFR-001, NFR-002, NFR-014

- **Given** confirmed/unconfirmed repositories, conventional directory layouts, flat repositories with common root-level source files, excluded/secret/symlink/binary/generated/oversized content, repository prompt injection, model outage/timeout/invalid output, cancellation/disconnect, legacy one-item requests, and two concurrent attempts by the sole owner,
- **When** the owner explicitly analyzes repositories,
- **Then** only confirmed public repositories enter analysis, every item pins one full commit and reuses production exclusions/chunking/evidence/provider validation, an empty include selection covers documented directories/manifests and common root-level source extensions without bypassing mandatory exclusions, only one owner-scoped durable batch is active, and the legacy one-item route creates a one-item batch instead of bypassing batch policy. The configurable bounded active-item and provider deadlines in AC-061 apply; every terminal/recovery path removes unique staging; no archive, repository body, prompt, provider body, incomplete output, or path becomes durable; only bounded safe progress, closed-set failure reasons, and validated normalized results may persist; no fallback occurs; and returned results keep `REPOSITORY_FACT` separate from supported `MODEL_INFERENCE`.

### AC-040 — Personal claims require confirmation and the guided flow remains usable

**Maps to:** FR-025, FR-028, FR-018, FR-022, NFR-002, NFR-003, NFR-009

- **Given** bilingual owner statements; model suggestions that omit or strengthen the statement; accept/edit/reject actions; provider-not-ready, missing public-read connection, preflight blocker, analysis failure, and missing GitHub writeback states; backward navigation and repository/ref/include/exclude edits; invalid generated YAML; reload/logout/save; keyboard-only use; and 375/768/1024/1440-pixel viewports,
- **When** the owner completes guided setup,
- **Then** the owner can skip analysis and enter contributions before any preflight or failed request; loading an existing configuration hydrates the guided profile/repository fields for return editing; the original statement remains visible; unconfirmed proposals never become `OWNER_ASSERTION`; Back/Edit preserves profile and unaffected repository input while invalidating only changed selection-bound plans/results; destructive Start over requires confirmation; confirmed role/summary/claims produce valid schema-v1 YAML while validated non-guided fields are preserved; raw edits with unknown/unmappable YAML remain in advanced mode instead of being silently discarded; ordinary validation/preview makes no model or GitHub call; copy/download works without a token; every blocked primary action and failed repository exposes its safe code/reason, cause, next action, and safe alternative; resume stores only approved public draft state and clears it on logout/save; raw YAML remains an advanced path; both locales are materially equivalent; focus/error/status behavior is accessible; and no horizontal content loss occurs.

For contribution-model assistance, the request keeps the fixed 700-token output policy independently of visitor and analysis settings, reserves the full bilingual prompt and exact response schema before dispatch, and performs no provider call when the context cannot safely fit. Output-limit termination is rejected before parsing with `PROVIDER_OUTPUT_LIMIT_REACHED`, including syntactically valid partial JSON; a complete invalid shape uses `PROVIDER_OUTPUT_SCHEMA_INVALID`. Neither condition retries, falls back, stores raw model text, or blocks manual authoring. Runtime response validation rejects mismatched repository/original-statement identities, pre-confirmed content, extra fields and duplicate/invalid claim IDs. Editing a confirmed proposal removes confirmation until the owner confirms the edited version, and delayed results from an older selection, statement or request generation cannot overwrite current guided state. These cases are exercised in unit/API tests and the production AdminPage/FastAPI browser flow in both locales.

### AC-047 — External embedding profile CRUD and single-active lifecycle

**0.2.2 clarification:** Setup may have zero active profiles; a ready deployment has exactly one active embedding profile. Dimension is observed from bounded samples, while prefixes/task semantics come from reviewed presets or explicit advanced configuration, not guesses. Candidate testing and activation are separate.

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

- **Given** explicit `loopback_evaluation` and `production` profiles, loopback/non-loopback binds and public URLs, trusted-proxy settings, production boundary/common passwords, unusual ports, SSH tunnels, VPN/LAN allowlists, and reverse-proxy route rules,
- **When** startup validation, local launch, production setup/login/password change/recovery, and admin-route requests run,
- **Then** loopback evaluation refuses every non-loopback or proxy-trusting combination and uses only one-use launcher grants with no credential form; reloading a page with a still-valid session resumes it without another grant while an absent/expired/revoked or boundary-invalid session shows the existing recovery surface; production/non-loopback requires 15–128 code points and blocks compromised/common values without composition rules; CSRF stays in browser memory and all existing Argon2id/session/CSRF/backoff/expiry/revocation controls remain where applicable; a passwordless local owner cannot make production ready until `set-password` succeeds; a non-standard port alone never grants access; SSH/VPN/private routes reach the password-protected Web Admin; public proxies deny `/admin` and `/api/admin/*`; and visitor routes remain independently usable.

### AC-050 — Local recovery and bounded operations CLI

**Maps to:** FR-029, FR-036, NFR-003, NFR-012

- **Given** a fresh loopback owner, a production owner, optional GitHub connection, OAuth outage/revocation, a forgotten or absent production password, copied runtime database, corrupt backup, active/previous/pinned bundles, and unknown CLI paths/IDs,
- **When** the owner runs the host recovery or runtime/bundle commands,
- **Then** `admin launch-token` works only for a validated loopback profile and emits one fragment-only two-minute URL; the grant is needed to create a local session but not to reload that still-valid session; production setup/password exists independently of GitHub; `reponpc admin set-password --data-dir <dir>` creates or changes only the production-capable local hash without reopening setup or changing GitHub credentials; `runtime check/backup` are consistent and secret-safe; `bundle verify/pin/unpin` preserve last-known-good state; help/errors are stable; and no second public management protocol is required.

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
| FR-017 | AC-024, AC-049, AC-050 |
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
| FR-029 | AC-050 |
| FR-030 | Legacy; AC-051 proves retirement |
| FR-031 | AC-051 |
| FR-032 | AC-044, AC-052 |
| FR-033 | AC-045, AC-046 |
| FR-034 | Legacy; AC-051 proves retirement |
| FR-035 | AC-047, AC-048 |
| FR-036 | AC-049, AC-050 |
| FR-037 | AC-051, AC-052 |
| FR-038 | AC-053, AC-054, AC-056 |
| FR-039 | AC-054, AC-055, AC-056 |
| FR-040 | AC-053, AC-057 |
| FR-041 | AC-058, AC-060 |
| FR-042 | AC-059, AC-060 |
| NFR-001 | AC-002, AC-004, AC-014, AC-016, AC-024, AC-027, AC-030, AC-033, AC-034, AC-037–AC-040, AC-044–AC-046, AC-048–AC-052, AC-059 |
| NFR-002 | AC-004, AC-016, AC-024, AC-035, AC-038–AC-040, AC-044–AC-046, AC-048, AC-051, AC-052, AC-059, AC-060 |
| NFR-003 | AC-019, AC-025, AC-026, AC-029–AC-032, AC-040, AC-047, AC-050–AC-053, AC-056–AC-060 |
| NFR-004 | AC-009 |
| NFR-005 | AC-015, AC-017 |
| NFR-006 | AC-007–AC-009 |
| NFR-007 | AC-011–AC-013 |
| NFR-008 | AC-008, AC-009, AC-023, AC-057, AC-058 |
| NFR-009 | AC-019–AC-023, AC-038, AC-040, AC-049–AC-052, AC-057, AC-058, AC-060 |
| NFR-010 | AC-001, AC-036, AC-037 |
| NFR-011 | AC-003, AC-005, AC-006, AC-029, AC-036, AC-046, AC-047, AC-056, AC-059, AC-060 |
| NFR-012 | AC-017, AC-032, AC-035, AC-044, AC-045, AC-050, AC-052 |
| NFR-013 | AC-001, AC-005, AC-015, AC-036, AC-037, AC-051, AC-053–AC-060 |
| NFR-014 | AC-018, AC-039, AC-045, AC-052, AC-054, AC-055, AC-059 |

Version 0.1.9 additions:

| Requirement | Acceptance criteria |
| --- | --- |
| External embedding profiles and provider-aware model management | AC-008, AC-032, AC-047, AC-048 |
| Deployment-aware password/private administration | AC-024, AC-036, AC-049 |
| Local-first GitHub binding and host recovery | AC-041, AC-042, AC-050 |
| Bounded operations CLI | AC-049, AC-050 |

Version 0.2.0 corrections:

| Requirement | Acceptance criteria |
| --- | --- |
| Passwordless one-use loopback launch | AC-024, AC-043, AC-049, AC-050 |
| Production password/setup preservation and migration | AC-024, AC-042, AC-049, AC-050 |
| GitHub OAuth connection-only behavior | AC-041, AC-042, AC-043 |

Version 0.2.1 retirement amendment:

| Requirement | Acceptance criteria |
| --- | --- |
| Remove OAuth and browser-entered public-read PAT product surfaces | AC-051 |
| Migrate encrypted public-read state without affecting owner/writeback state | AC-051 |
| Anonymous REST exact-SHA public-repository analysis | AC-044, AC-052 |
| Recoverable anonymous GitHub rate exhaustion and manual continuation | AC-052, AC-039, AC-040 |

Version 0.2.2 model-setup amendment additionally maps FR-006/FR-012/FR-035 to AC-054/AC-056, FR-025/FR-022 to AC-053/AC-057, NFR-001/002 to AC-055, NFR-003/011 to AC-056, NFR-008/009 to AC-057, NFR-012/014 to AC-054/AC-055, and NFR-013 to AC-053 through AC-057. Earlier evidence does not establish these new results.

AC-041 through AC-043 are historical 0.1.6–0.2.0 criteria and are not 0.2.1 release gates. Their still-applicable owner/session/recovery/accessibility controls are covered by AC-024, AC-049 through AC-052. OAuth/PAT-specific behavior is superseded by ADR-028.

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

### AC-044 — GitHub preflight is immutable, bounded, and anonymous

**Maps to:** FR-032, FR-002, FR-003, NFR-001, NFR-002, NFR-012

- **Given** confirmed and unconfirmed selections; public, private, inaccessible, archived, malformed, and duplicate repositories; writeback-secret canaries; REST metadata, primary/secondary limit, `Retry-After`, reset, redirect, traversal, symlink, archive-bomb, and cancellation fixtures,
- **When** a batch preflight and exact-SHA source fetch run,
- **Then** no unconfirmed/ineligible repository enters analysis; every accepted item records one full commit SHA and uses its immutable archive; compressed/expanded bytes, entries, paths, links, files, time, and cleanup are bounded; no per-blob batch path occurs; discovery/resolution/archive requests contain no OAuth/PAT/writeback authorization; and primary/secondary pauses produce safe retry state without busy looping.

### AC-045 — Durable analysis batches preserve safe bounded progress

**0.2.7 / ADR-034 regression:** Migration 24 preserves preexisting batch items, results, events, foreign keys and indexes while permitting the new fixed output-limit reason; injected migration failure rolls back. Snapshots after reload preserve the reason, both locales distinguish it from schema mismatch, and unknown/raw provider values remain excluded. A truncated result never reports success or causes automatic regeneration.

**Maps to:** FR-033, FR-027, NFR-001, NFR-002, NFR-012, NFR-014

- **Given** duplicate idempotency requests, reload/SSE reconnect, pause/resume/cancel, partial failures, expired plans, restart during every stage, rate waiting, provider contention, and interrupted generation fixtures,
- **When** the owner starts a multi-repository batch or the legacy one-item route,
- **Then** exactly one active owner batch and one idempotent job are observed; snapshots/events replay monotonically; every item keeps its immutable commit, isolated staging, validated terminal result, terminal cleanup, and any closed-set application-owned failure reason across restart/reload; public chat retains provider opportunities; stage caps are never exceeded; restart repeats only immutable fetch/index or verified cache work; cancelled/in-flight provider output is discarded; unknown/raw upstream details never become a reason; and a dispatched generation becomes explicit-retry-only rather than being automatically resent.
- **And** same-round retry is offered and accepted only while both the effective persisted/current policy attempt ceiling and active-work budget have capacity. Each generation dispatch reserves one attempt atomically and cancellation rejects dispatch admission. An exhausted selected failure can create one idempotent successor round that preserves its source batch/item lineage, fixed commit/selection policy, old errors, successful sibling results, and frozen model pair. Reusing the request key or submitting another key for an already-consumed source item cannot duplicate work; another active batch conflicts; switching to the current pair requires explicit confirmation bound to its selection generation.

### AC-046 — Analysis caches are identity-complete and private

**Maps to:** FR-033, FR-002, FR-006, FR-012, NFR-001, NFR-002, NFR-011

- **Given** otherwise equal batches whose commit, include/exclude policy, parser version, embedding identity, chat model, prompt version, output-schema version, validation/generation policy version, analysis output budget, or effective provider output/context capacity differs,
- **When** cache prediction/reuse and expiry cleanup run,
- **Then** only checksummed/integrity-checked compatible derived indexes and validated normalized results are reused; every identity change misses the corresponding cache; raw source/archive/prompt/provider body never persists; and TTL/LRU cleanup removes expired entries without changing active work or prior validated results.

### AC-051 — OAuth and public-read PAT surfaces retire without damaging owner or writeback state

**Maps to:** FR-017, FR-019, FR-029 through FR-031, FR-034, FR-037, NFR-001 through NFR-003, NFR-009, NFR-013

- **Given** clean and upgraded runtimes containing no legacy connection, a pending OAuth transaction, an encrypted `identity_public_read` credential, an encrypted `public_read` PAT, active owner/session/local-launch/password state, and an independently configured writeback token,
- **When** the 0.2.1 migration and admin/API/configuration flows run,
- **Then** no OAuth/public-read PAT card, input, guide, callback, redirect, start/check/delete action, or client-secret/callback/encryption-key requirement remains reachable; legacy routes return the bounded non-mutating `410` compatibility response; OAuth transactions/identities/public-read credential rows are removed without decryption or secret output; owner authentication, recovery, sessions, drafts, bundles, and writeback configuration remain valid; and no legacy secret value appears in the DOM, API, logs, fixtures, snapshots, or migration diagnostics.

### AC-052 — Anonymous GitHub resolution is exact-SHA, rate-aware, and never borrows writeback authority

**Maps to:** FR-026, FR-027, FR-032, FR-037, NFR-001 through NFR-003, NFR-009, NFR-012, NFR-014

- **Given** public/private/missing repositories, default and explicit refs, immutable commit changes, exhausted/available REST capacity, primary and secondary limits, `Retry-After`, redirect/host manipulation, and writeback-secret canaries,
- **When** discovery, preflight, resolution, archive fetch, cancellation, retry, and manual continuation run,
- **Then** only fixed-origin unauthenticated REST requests resolve eligible public selections; each accepted archive is addressed by the returned validated full commit SHA; no discovery/analysis request contains an authorization header or writeback credential; rate state is centrally bounded and sanitized; exhaustion reports an accessible bilingual retry state without busy looping; and manual authoring, validation, preview, copy, and download remain immediately available.

### AC-053 - Provider-neutral first boot and independent role setup

**Maps to:** FR-025, FR-038, FR-040, NFR-003, NFR-013

- **Given** a clean runtime with no model settings, an explicit environment setup, and a migrated persisted setup,
- **When** the owner launches the app, opens administration, selects or skips model setup, and restarts,
- **Then** clean setup preselects no service/model and issues no implicit model request/download; health/admin/manual authoring/validation/preview/export remain available; chat/search are separately configured; existing explicit settings and selected revisions survive without fallback; semantic readiness is false until the required tested profiles and bundle are available.

### AC-054 - Typed model IDs and real capability tests work across services

Diagnostic regression (owner correction, 2026-09-12; AC-054/055/057 and bilingual AC-023): Chat and Embedding probes retain actual upstream HTTP status (including 402 and 503) as safe `last_error_code` metadata and structurally extracted, redacted original error text as nullable `last_error_message`. Both locales display the same provider text outside advanced details after reload, without translating or guessing a cause from the status. Different languages, unknown vocabulary, JSON envelope shapes, explicit plain text, missing/unsupported/malformed/oversized responses, encoded configured secrets, URL spans, escaped markup, and truncation boundaries are covered. No usable message means actual status plus an honest missing-text notice. Timeout without a response must not acquire a guessed HTTP status; unknown/legacy failures offer explicit retest. Successful retest clears both fields; failed retest preserves an active last-known-good profile. Unrelated body metadata and configured secret/private-URL canaries never appear in returned metadata. Migration 20 preserves existing rows and rolls back both column additions if either fails. Both create buttons read `新增模型 / Add model`.

**Maps to:** FR-012, FR-035, FR-038, FR-039, NFR-012, NFR-014

- **Given** Ollama, vLLM, and generic gateway fixtures with independent endpoints/keys/models, base-path prefixes, no-key authentication, supported/unsupported model listing, chat-only models, invalid keys, timeouts, rate limits, malformed vectors, and model-specific task presets,
- **When** the owner explicitly tests a typed or listed model,
- **Then** only the chosen connection and exact model receive bounded synthetic requests; listing alone never proves readiness and unsupported listing permits manual testing; actual chat/query/passage operations validate capabilities; dimensions are measured, task prefixes are explicit, limits and safe errors hold, no repository content is sent, and failed tests retain an edit/retry/manual path without fallback.

### AC-055 - Write-only model credentials and network boundaries hold

**Maps to:** FR-039, NFR-001, NFR-002, NFR-012

- **Given** recognizable synthetic key/private-URL canaries, host-managed defaults, forged/expired sessions, absent CSRF, cross-origin calls, hostile URL/redirect/DNS fixtures, changed destinations, empty/replace/remove credential intents, and unavailable/corrupt secret storage,
- **When** connections are created, tested, read, edited, deleted, backed up, restored, and rejected,
- **Then** only authenticated same-origin ingress accepts typed values; the browser never directly contacts providers; stored values never appear in read/error responses, public YAML, bundles, logs, history, browser storage, exports, or recorded screenshots; host-managed editing requires a complete replacement without environment URL readback; key inputs clear after submission/exit; storage is protected and fails closed; a same-provider path-only edit with unchanged normalized scheme/hostname/effective-port may retain the old key, but provider or origin changes never forward it without explicit replacement/removal; reference cleanup preserves live revisions; and GitHub/authentication secrets cannot be borrowed. URL policy covers normalized IPv4/IPv6, forbidden ranges, redirects, and DNS changes at connection time.

### AC-056 - Model changes preserve active service and recover after restart

**Maps to:** FR-006, FR-035, FR-038, FR-039, NFR-003, NFR-011

- **Given** active chat/search revisions, a compatible bundle, host-managed replacement/deletion, candidate edits, concurrent activations, shared connections, failed/cancelled probes/reindexes, key rotation, migration failure, restart, and an index builder unable to reach a private endpoint,
- **When** the owner saves and explicitly uses candidates,
- **Then** saving alone cannot alter active service; chat switches only after its test while old requests complete on their revision; embedding activation requires probe/reindex/validation/smoke and an atomic switch; failed work preserves the last-known-good profile/bundle; compatible cache reuse and incompatible result invalidation follow the selected identities; restarts preserve explicit selections and do not overwrite/recreate an owner-replaced/deleted environment default or remirror environment model fields into its owner-edited profile; unreachable builders show a publication-specific recovery path with no secret export or unapproved topology change; backups restore connection/profile/key/override availability using the documented protected procedure.
- **And** an effective connection update atomically rebinds only directly referencing inactive candidates that are neither previous last-known-good nor reindexing, clears their prior probe evidence, refreshes their cards, and requires an explicit retest without a second profile save; analysis selection generation becomes stale. Public-active, previous last-known-good, reindexing, and frozen batch work remain on their historical revision/provider and can be resolved after restart. Migration 22 repairs earlier stranded safe candidates without provider calls or changing unrelated profiles.

### AC-057 - Novice model setup is readable, reversible, and accessible

**Maps to:** FR-022, FR-025, FR-040, NFR-008, NFR-009

- **Given** both locales, first-time and returning owners, keyboard/screen-reader use, 375/768/1024/1440-pixel widths, 200% zoom, reduced motion, and long model IDs/errors,
- **When** they select a service, enter address/key/model, test, edit, cancel, activate/reindex, skip setup, and return to their portfolio draft,
- **Then** the primary flow asks only service/address/key/model information, lets the owner edit or delete environment defaults (including a non-default Ollama port), allows a same-origin path correction such as `/v1` without unnecessary key re-entry, updates safe dependent model settings as part of the same connection save rather than requiring another profile edit-save, distinguishes chat from search and connection success from publication, never requires dimension/reference jargon, provides contextual recovery and manual continuation, preserves unrelated work, keeps Ollama catalog/actions conditional, and has no overlap, clipped controls, untranslated status keys, lost focus, duplicated/silent connection failure, or color-only status. Each failed connection operation identifies what failed, a safe cause, preserved state, recovery action, and cleared-key re-entry requirement; field errors are associated and the summary receives focus. Automated browser/accessibility evidence plus a dated novice walkthrough are required; Figma is not required.

### AC-058 - Model-first AI flow and immediate manual flow

**Maps to:** FR-025, FR-027, FR-028, FR-038, FR-040, FR-041, NFR-003, NFR-008, NFR-009

- **Given** a new authenticated owner with neither model configured, one role configured, saved-but-untested profiles, tested-but-unselected profiles, and a returning owner with valid selections,
- **When** the owner chooses AI setup or manual authoring in either locale,
- **Then** welcome is unnumbered; AI setup follows models -> repositories -> analysis -> contributions -> profile -> preview/draft; model controls are reachable without advanced mode; both roles need successful tests and explicit selection before the first-run AI route advances; manual mode uses its four applicable steps and never marks skipped AI work passed; the single Start analysis action runs bounded preflight/create only on explicit consent; missing prerequisites explain their role and offer direct repair/manual actions; and ordinary step visits/return navigation cause no source analysis or model generation. No default Ollama/model or failed-request prerequisite is introduced.
- **Verification:** reducer/component/API orchestration plus real-browser keyboard, focus, screen-reader/status, both locales, 375/768/1024/1440 pixels, 200% zoom and reduced motion; no clipped/wrapped-off controls. Retain AC-057's dated novice walkthrough.

### AC-059 - Clean first-run analysis works before public index activation

**Maps to:** FR-006, FR-012, FR-027, FR-033, FR-039, FR-042, NFR-001, NFR-002, NFR-003, NFR-011, NFR-014

- **Given** a clean application runtime with no environment model, no public bundle and no active public model pair, plus controlled Ollama/OpenAI-compatible provider and public GitHub fixtures,
- **When** the authenticated owner creates connections, tests and explicitly selects both analysis roles, confirms a repository and starts analysis through the real application wiring,
- **Then** the same running process builds the required bounded analysis dependencies and completes embedding/retrieval/generation/validation without restart, manual database edits, preloaded runtime injection or a published bundle. The job uses only its frozen selected revisions; selection itself invokes no source/model/reindex work. Public readiness remains unavailable until a separately verified compatible public bundle/model activation; no temporary analysis index is published. An existing public last-known-good pair/bundle remains serving while a different analysis pair is selected or fails. Wrong capability, missing key-store, outage and stale revision fail safely without fallback, raw output disclosure or generation before admission controls.
- **Verification:** application-factory/startup integration tests (not only registry mocks), first-run browser flow, canary/security tests, existing bundle atomicity/reindex regression. Record live-provider evidence separately from deterministic fixtures.

### AC-060 - Recovery, revision changes and old guided state preserve work

**Maps to:** FR-025, FR-028, FR-033, FR-041, FR-042, NFR-002, NFR-003, NFR-009, NFR-011, NFR-013

- **Given** legacy session-only progress at every old step, completed drafts, unmappable advanced YAML, an active durable batch, partially successful analysis, changed repository selection or model/connection revisions, and session expiry,
- **When** the owner resumes, returns to model setup, cancels, selects replacements, retries or switches between manual and AI routes,
- **Then** allowed public draft fields and unaffected confirmed contributions survive; a missing model at old analysis state offers direct setup and a safe return without reset; completed drafts stay editable/exportable; the server owns model readiness and active-job reconciliation. Changed identities invalidate stale plans and incompatible cache reuse; active work retains its frozen pair or fails safely, never retargets/retries silently. Old validated results remain accurately labeled, not fresh results for a changed pair. Model setup success does not auto-resubmit analysis. New key/URL inputs never enter browser persistence and are cleared as specified; logout retains its existing clearing boundary. An intentional destructive reset remains separately confirmed.
- **Verification:** migration/reducer/orchestration, batch identity/race/restart/security and real-browser recovery tests; a single-item failure cannot erase other validated results.

Version 0.2.3 additionally extends AC-040/AC-053/AC-056/AC-057 with section 11.6's model-first journey and analysis/public-activation distinction. “Active profile” in public-readiness criteria continues to mean public serving state; an analysis-only selection does not satisfy it. AC-058 through AC-060 start **not-run** until the correction is implemented and observed. Prior 0.2.2 tests do not establish these outcomes.

Version 0.2.5 extends AC-055/056/057/060 with ADR-032's connection-rebinding correction. A connection update is one owner action for editable dependent candidates, but test/use/publication remain explicit actions and protected historical work remains pinned. Runtime migration 22 is upgrade compatibility evidence, not live-provider or full release acceptance by itself.

### AC-061 - Flexible analysis budgets support large repositories without removing safety ceilings

**Maps to:** FR-027, FR-033, FR-041, NFR-003, NFR-011, NFR-014

- **Given** one or more repositories contending for archive, index and provider capacity; a slow but responsive configured model; transient timeout/rate/unavailable failures; an archive with an oversized individual file; and deployments using default, valid override and invalid relationship values,
- **When** the owner starts analysis, observes progress, waits, retries or continues manually,
- **Then** scheduler semaphore waiting does not spend active repository time; the default active/provider/GitHub budgets are 1,800/300/60 seconds and remain bounded by 7,200/3,600/300-second ceilings; only the same frozen provider/model is retried for transient failures up to three attempts; public chat requests 4,096 tokens by default and never more than 8,192/provider/context capacity; analysis remains independently capped at 8,192/16,384; individual archive members over the materialization threshold are body-free `FILE_TOO_LARGE` skips while unsafe paths/types and total archive ceilings fail closed; snapshots and both locales show the specific terminal code, active elapsed time, budget and generation-attempt count; invalid cross-limit configuration prevents startup without exposing secrets.
- **And** terminal elapsed time is immutable, `completed_with_errors` is terminal for controls/SSE/ETA, processed and successful counts remain distinct, migration 26 preserves existing batches/events/results while adding only secret-free lineage and failure-stage metadata, and migration 27 preserves source consumption plus bounded reanalysis request bindings across ordinary cleanup.
- **Verification:** environment/Compose contract tests, migration-25/26/27 preservation and rollback, deterministic semaphore-clock tests, archive skip and zip-bomb regressions, same-provider retry/no-fallback tests, frontend unit/accessibility checks, production build and a controlled slow-provider browser run. Buffered-provider evidence must be labeled as socket-inactivity behavior rather than token-level streaming evidence.

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

**0.2.2 evidence boundary:** AC-053 through AC-057 are not-run until implemented and observed. The current release-audit code enumerates only AC-001 through AC-052 and must be extended during implementation; a passing old audit is not coverage of this amendment. Preserve historical evidence provenance and add current candidate evidence instead of relabeling old runs.

**0.2.3 evidence boundary (2026-09-10):** Release coverage must extend through AC-060, excluding legacy AC-041 through AC-043. The auditor still enumerates only AC-052 at this review. Extend both document coverage and ledger validation, with missing/duplicate-new-ID tests, during the implementation package. Source presence is not full acceptance for AC-053 through AC-057 either.

Chat parser regression (2026-09-12, amended 2026-09-14; AC-054/055/057 and AC-023): test OpenAI-compatible and Ollama HTTP-200 responses with malformed JSON, invalid message/content/termination/usage, and empty or partial output stopped by `length`. The retained diagnostic identifies the application check and excludes arbitrary body canaries. A configured output budget above 32 can complete the synthetic reasoning-budget case; a configured smaller budget remains bounded and fails honestly. One explicit test means one provider call with a 10-second baseline plus one 10-second grace window, no activation and no hidden retry. Successful retest clears diagnostics. Both languages show the same source-labelled check, while actual HTTP error prose stays unmodified. A synthetic regression does not establish the cause of an unreplayed live gateway failure.

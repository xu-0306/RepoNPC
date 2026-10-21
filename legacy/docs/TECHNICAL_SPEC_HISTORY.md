# Technical Specification History

0.4.13 — 2026-10-20 — legacy archive (ADR-071): remote bundle polling, GitHub Release publishing, OAuth tombstones and the legacy visitor URL route removed; superseded spec text moved to legacy/docs/.

**Owner-approved README delivery (2026-10-12, OR-033 / ADR-059, Approved 0.4.11):**
[The README export contract](../../docs/PROFILE_README_EXPORT_CONTRACT_2026-10-12.md) extends
FR-024 with complete localized README download and exact content preview from
the verified public snapshot. It uses the existing Pages GIF, rechecks its bytes,
preserves existing README/copy-card paths, and explains the same-name public
repository root requirement. No new hosting, GitHub write or model call is added.

**Owner-approved analysis-output and admin-presentation repair (2026-10-14, OR-034 / ADR-060, OR-035 / ADR-061, Approved 0.4.12, AC-080):** Analysis and contribution model output now uses the shared schema, personal-inference, and locale/source writing-system checks. Analysis facts expose source locations and pinned GitHub permalinks without repository excerpts; inferences require a localized `title`. The admin view presents compact, expandable highlights and uses React Aria only for the approved admin dialogs/popovers. These local implementation changes do not by themselves establish release acceptance.

**Owner-approved public summaries (2026-10-04, OR-032 / ADR-058, Approved 0.4.10):** [public summary contract](../../docs/CHAT_PUBLIC_SUMMARY_CONTRACT_2026-10-04.md) supersedes prior pending-summary notes. An explicitly selected Responses interface may show bounded provider-defined public summaries, separate from validated answers; raw thinking stays private.

**Owner-approved waiting experience (2026-10-04, ADR-057 / OR-031, Approved
0.4.9):** [Chat processing contract](../../docs/CHAT_PROCESSING_CONTRACT_2026-10-04.md)
defines real bounded progress, elapsed time, cancellation and a 180-second default
within the existing 300-second maximum. Final answers retain full validation.
Raw thinking text remains private; its requested display is pending after an
automatic approval-review rejection.

**Owner-approved reasoning and generation budget amendment (2026-10-03,
ADR-055 / OR-029):** Reasoning remains enabled for supported Ollama chat models.
Visitor chat, its synthetic probe and authenticated repository analysis each
default to a 16,384-token generation ceiling, with a 16,384 hard maximum.
Explicitly configured lower budgets remain valid. Sections 4.3 and 13.3 govern
context reservation and provider controls; deadlines and validation remain unchanged.

**Owner-approved A11 backup boundary (2026-10-03, ADR-054 / OR-028):**
The owner chose option A in the [backup decision](A11_BACKUP_BOUNDARY_DECISION_2026-10-03.md).
Section 11.7 defines password-encrypted Web backups and same-data-directory
restoration. This authorizes implementation; it does not close AC-076 or release gates.

**2026-10-03 A6/A7 local implementation:** the approved built-in model choice,
cancel/resume downloader, CPU provider lifetime, nullable local profile binding
and explicit device check are wired through the existing private model workspace.
Migration 34 preserves profile/selection/switch-intent references. Synthetic
integration and in-app browser evidence are recorded in the
[parallel handoff](PARALLEL_IMPLEMENTATION_HANDOFF_2026-10-03.md). Real pinned
weights and retrieval quality were pending at that checkpoint. The next parallel
run on 2026-10-03 now records real fixed-artifact CPU evaluation and reviewed
per-model cards in the handoff. Verified catalog admission and release acceptance
remain separate gates; this checkpoint does not change the Approved specification.

**A7 card completion (2026-10-03, FR-040 / AC-057):** the existing private device
check also returns authored catalog metadata for individual resource-grade cards.
The [implementation contract](../../docs/A7_MODEL_CARDS_IMPLEMENTATION_2026-10-03.md) records
the additive fields and explicit handoff to the existing Chat model form. Choosing
a card makes no download/provider call or activation and preserves unsaved inputs.

**Implementation checkpoint (2026-09-30, A5/R08):** The approved visitor/appearance/Pages scope is being implemented under the [A5 integration contract](../../docs/A5_VISITOR_APPEARANCE_EXPORT_CONTRACT.md). ChatGPT review6 accepted prior repairs and identified a technical path/dot FAQ collision; Luna max repaired it and Main reproduced six failures before repair. Final Web377/37 files, frontend format/lint/type/build, registry/source guard and Docker/Compose2 passed; earlier native phone drawer checks at host1440/375 remain applicable to unchanged CSS. The unchanged 62 Python inputs retain Python1,638/2 Windows skips, mypy91 and Ruff221 checks. The final FAQ repair has not received another ChatGPT review; the owner requested a [pause and handoff](A5_HANDOFF_2026-09-30.md). This evidence does not change Approved status or close release acceptance. Static live chat remains incomplete pending explicit payload/destination authorization; native ZIP completion and actual200% zoom are unverified.

**Approved A1 gateway amendment (2026-09-28, OR-027 / ADR-053; FR-047, AC-068/071):** [The frozen A1/F0 contract](../../docs/A1_FUNNEL_GATEWAY_CONTRACT.md) is normative for gateway routing, environment fields, runtime migration 30, private API/Host/Origin authentication, identity protection, SSE and operator lifecycle. The owner approved the reviewed design and requested gpt-6-luna max implementation with Main review/takeover. Implementation is in progress; no public activation or external acceptance is implied.

**Implementation progress (2026-09-28):** A3 participation is implemented locally, including the bounded local/reindex build integration correction. A4 coverage and reviewed FAQ now have local build/API/security/storage and browser evidence; see [A4 contract](../../docs/A4_COVERAGE_FAQ_IMPLEMENTATION.md) and [local verification](../../release-evidence/a4/local-checks.md). Formal A12 release/Pages/Funnel evidence remains pending. The dated checkpoint below records the earlier state.

**Implementation progress (2026-09-27):** A2's v2 answer validator/service integration, owner-only fixed drop-reason logging and collapsible Sources list; R11's owner-scoped recent batch recovery with a synthetic authenticated browser reload check; and R12-B's passage-cache work-count and route/export/backup exclusion tests have local evidence. AC-065's participation-backed answer still depends on A3, and A4 must expose the coverage report. Formal AC-062–AC-065 and AC-077–AC-078 release evidence remains pending in A12. Historical “not implemented” amendment notes below describe the state when each decision was approved.

**Model source, repair closure and maintenance amendment (2026-09-27, ADR-052; FR-049, FR-053, AC-076–AC-079):** The built-in bge-m3 is the official `BAAI/bge-m3` fp32 ONNX export pinned to revision `5617a9f61b02` (about 2.29 GB, per-file SHA-256). Admin previews are served only through authenticated `no-store` admin routes (R08). The active-batch endpoint also returns a recent actionable terminal batch until the owner dismisses it (R11). R12-B first checks whether the passage-vector cache already covers the need. A 「維護」 page covers status, backup, restore, bundle rollback, stopping the gateway and update/Funnel guidance. Not implemented yet.

**Chat interface and colour scheme amendment (2026-09-26, ADR-051; FR-047/050/051/052, NFR-009/011, AC-068, AC-072–AC-075):** The owner asked for a simple chat UI instead of bundled illustrated backgrounds, colours that do not follow the character, several colour schemes to choose from, and light/dark mode. [Completion direction contract §4.0 and §4.4–§4.6](../../docs/COMPLETION_DIRECTION_CONTRACT_2026-09-26.md) is normative.

- The visitor page is a simple chat interface with flat colours:
  - a collapsible sidebar with the profile and projects, which becomes a drawer on phones;
  - a top bar with the NPC status avatar, the language switch and a light/dark toggle;
  - a centred chat column with a welcome hero, message bubbles and a pinned input bar.
- Colours come from one versioned, schema-validated registry (`color_schemes.yml`) of fixed schemes with explicit light and dark `#rrggbb` values. A scheme that fails AA contrast as authored stops the registry from loading. Starter set: `neutral` (default), `ocean`, `forest`, `sunset`, `lavender`.
- `color_mode` is `system` (default), `light` or `dark`. With `visitor_mode_toggle` on (default), visitors can switch light/dark, and the choice stays in their browser's `localStorage`.
- Only the NPC follows the character. Sheet-palette derivation, pack scene hints and hue-seed templates are retired, and only `stage` may be adjusted to keep the NPC separable.
- The owner image is optional and appears only in the welcome hero.
- No code branches on scheme ids.
- This amendment is not implemented yet.

**Scene template and background image amendment (2026-09-26, ADR-050; FR-051/052, FR-050, FR-018, NFR-001/009/011, AC-074–AC-075; revised by ADR-051 above):** The owner asked for several background and colour-scheme templates to choose in settings, then clarified that programmatically drawn template backgrounds are not wanted, and asked for an owner background upload with a realistic preview. [Completion direction contract §4.5–§4.6](../../docs/COMPLETION_DIRECTION_CONTRACT_2026-09-26.md) is normative.

- Templates are **colour schemes only**, as data in one versioned, schema-validated registry (`scene_templates.yml`). Each has a palette mode (`follow_character`, or `fixed` OKLCH hue seeds) with a named tone. The default `auto` is the ADR-049 character-derived scene. No template draws a backdrop.
- The owner background image is MVP. An upload becomes a private draft, which is previewed in the real visitor components with the active character, a sample dialog, light/dark themes and desktop/phone frames. Focus point, dim and scaling are adjustable, and nothing public changes until 「套用」.
- Every template, with or without an image, passes the FR-050 contrast solver and NPC-separation check with every character.
- No code branches on template ids, and no template references a species, `pack_id`, filename or option key.

**Character-driven visitor scene amendment (2026-09-26, ADR-049; FR-047/050, FR-015/018, NFR-001/009/011, AC-072–AC-073; colour derivation retired by ADR-051 above):** The owner clarified that the reference mockup's cat is only an example: the visitor NPC and its scene MUST follow whatever character the owner selects or uploads. [Completion direction contract §4.4](../../docs/COMPLETION_DIRECTION_CONTRACT_2026-09-26.md) is normative.

- The scene is a closed set of token roles in light and dark themes. It is derived deterministically from the canonical sheet's pixels (OKLCH clustering).
- Tokens resolve in this order: explicit owner override, optional opaque pack scene hints, sheet derivation, and a neutral default only on derivation error.
- A contrast solver guarantees WCAG 2.2 AA text contrast and NPC/backdrop separation.
- An optional validated owner background image is supported.
- No code path may branch on species, `pack_id`, filename or option names.
- Tokens are computed server-side and exported with the static site, so live and Pages rendering match.
- This amendment is not implemented yet.

**Owner-approved completion-direction amendment (2026-09-26, ADR-048; FR-006/011/012/014/040, FR-043–FR-049, AC-062–AC-071):** [The completion direction contract](../../docs/COMPLETION_DIRECTION_CONTRACT_2026-09-26.md) is normative. (1) Chat answers use envelope v2: typed segments (`person | participation | project | inference`) with per-segment citation rules, `{{owner}}` rendered by the backend, a centralized inflation lexicon and numeric-fact check, and silent per-segment drop instead of whole-answer abstention; person questions without an owner statement are answered with what the project does and how it is built plus participation facts, never with a visitor-facing gap message. (2) A new `PARTICIPATION` evidence class carries GitHub login-matched participation period, owner flag and other-contributors flag, never raw counts. (3) An informational coverage check and an owner-reviewed FAQ (approve / reject / regenerate / rewrite-as-statement) are added; only approved, bundle-bound FAQ entries are exported or served. (4) The MVP public experience includes free-form live chat with the animated NPC: the owner manually uploads an exported static site to their own GitHub Pages repository, which calls the Tailscale Funnel visitor gateway for live answers and falls back to in-browser matching of approved FAQ entries while the host is offline. ADR-047's gateway split and Funnel transport return to MVP scope; visitors never see host, model, provider or cost information. (5) Windows novices install through a PyInstaller onedir bundle in an unsigned per-user Inno Setup installer; Docker remains for Linux/advanced use. (6) A built-in ONNX Runtime `bge-m3` embedding adapter is the production default after an explicit first-use download; external embedding services remain selectable. (7) Owner-only model guidance adds a device check, Ollama helper, plain-language errors, a status line and a data disclosure. This supersedes the "no RepoNPC-local production embedding default" text in FR-006/FR-012/§5.4/§13.3/§17, the whole-answer person-claim abstention in FR-011/§8, and the "externally hosted frontend origins" exclusion in §18 for the configured Pages origin only. No GitHub write, silent provider switch, public admin route or model-authored URL is introduced. Nothing in this amendment is implemented yet.

**2026-09-24 public-entry planning note (ADR-047):** The owner selected Tailscale Funnel as the future no-purchase HTTPS visitor entry. [The focused deployment plan](../../docs/TAILSCALE_FUNNEL_DEPLOYMENT_PLAN_2026-09-24.md) must settle gateway routing, private admin origin, proxy/client-IP trust, host support and credential lifecycle before implementation changes. Existing approved behavior and local-only acceptance are unchanged; no Funnel path has passed public deployment verification. **Updated 2026-09-26 (ADR-048):** the Funnel visitor gateway is MVP scope, and its CORS allowlist additionally admits exactly the configured GitHub Pages origin without credentials.

**2026-09-22 local-publication amendment (ADR-046):** The owner authorized implementation of the local-first NPC and guided GitHub card journey. [Local publication contract](../../docs/LOCAL_PUBLICATION_CONTRACT_2026-09-22.md) supersedes GitHub-only configuration/build/activation transport; all validation, attribution, privacy and last-known-good requirements remain. Implementation/acceptance evidence must distinguish local tests from actual public deployment.

**Owner-approved automatic alignment and pixel-offset amendment (2026-09-22, ADR-045; FR-015/018, AC-020/023):** After a conversion yields one chosen canonical asset (and after an explicit original/cleaned choice when edge cleanup exists), the authenticated workspace MUST inspect frame positions automatically. It MAY auto-apply only non-clipping horizontal offsets backed by a consistent column-displacement pattern across at least half of the seven states; a drift confined to one state or an ambiguous competing pattern remains a manual review. Automatic composition MUST pass the existing protected canonical validation endpoint before it becomes downloadable or writable. The owner MUST have labeled per-frame X/Y integer-pixel input fields with visible bounds, immediate draft preview, rejection of clipping/invalid values, explicit apply/validation for manual edits, and restore. Source material and unselected cleanup variants remain unchanged. This supersedes ADR-043's opt-in-only suggestion timing, not its canonical validation or reversibility boundary.

**Owner-approved edge-spill cleanup amendment (2026-09-22, ADR-044; FR-015/018, AC-020/023):** Structural grid conversion MAY offer a separate canonical cleaned preview when a shallow top-edge fragment demonstrably continues the preceding row, is separated from this frame's main content by a transparent gap, and can be removed without emptying the frame. Detection uses alpha geometry and grid adjacency only, never species, filename, color, anatomy, or pose. The original conversion remains available and unchanged. The authenticated response returns nullable `edge_cleanup` with separately validated canonical bytes, affected state/frame coordinates, and a bounded removed-source-pixel count. The owner MUST compare the same state/frame and explicitly choose cleaned or original before download/writeback; ambiguous content is preserved. Alignment thereafter operates on the chosen version. No source overwrite, new endpoint, automatic write, or relaxed canonical validation is allowed.

**Owner-approved frame-position repair amendment (2026-09-22, ADR-043; FR-015/018, AC-020/023):** The authenticated Character & animation workspace MUST offer an opt-in, reversible alignment preview after conversion. Suggestions use only alpha occupancy within each canonical frame and do not infer species, anatomy, filename, or intended motion. Manual X/Y adjustments MUST not crop opaque content or bleed into adjacent frames. Neither a suggestion nor a draft preview changes the downloadable/writable asset: explicit apply sends the composed PNG through the existing protected canonical validation endpoint, and only its successful response becomes downloadable or writable. Validation failure leaves the original result intact. All seven states, keyboard access, bilingual feedback, and reduced-motion behavior remain available.

**Owner-approved ordinary-owner character-workspace amendment (2026-09-22, ADR-042; FR-015/018, NFR-003/009, AC-020/023):** Character upload and animation preview are a normal authenticated owner task, not a raw-YAML capability. The admin workspace MUST expose a first-level localized `Character & animation` destination beside guided setup and advanced YAML. Its default path uses plain-language upload, visual candidate choice, seven-state animated preview, and download/save actions. Structural terms, conversion policies, the full sheet, diagnostics, and raw identifiers are progressively disclosed as advanced or technical information. Keyboard access, 44px controls, responsive layout, status announcements, and reduced-motion behavior remain required.

**Owner-approved novice material discovery amendment (2026-09-21, ADR-041; FR-015/018, AC-020):** The authenticated character converter accepts a PNG, a ZIP, or a browser-selected folder without requiring contributors to rename files or author a manifest. A strict root manifest remains deterministic when present; otherwise the backend discovers structurally valid 4-by-7 PNG grids inside the bounded material bundle. Exactly one candidate converts automatically, multiple candidates require an explicit visual choice, and zero candidates fail with actionable guidance. Candidate identity is content-bound and recomputed on selection. Filenames, folder names, species, and visual semantics are never guessed. Inspection is side-effect-free and preserves the existing explicit download/writeback boundary.

**Owner-approved 64px canonical sprite and material-conversion amendment (2026-09-21, ADR-040; FR-015/018, AC-020):** Before deployment, the canonical frame changes directly from `32x32` to `64x64`, making the complete four-column/seven-row sheet `256x448`; no 32px compatibility path remains. The authenticated admin may convert a bounded untrusted structural 4x7 PNG grid at any square cell size, or a ZIP whose strict `sprite-pack.json` explicitly maps all 28 PNG frames. `pixel_exact` accepts only integer scale ratios; `pixelize` performs deterministic bounded resampling, palette reduction, and alpha thresholding. Conversion is preview-first, preserves no executable input, never invents missing frames, never overwrites the source, and emits review warnings before optional download or ordinary validated GitHub writeback.

**Owner-approved species-neutral character-pack amendment (2026-09-21, ADR-039; FR-015/018, AC-020):** Built-in character configuration is now exactly a versioned `pack_id`, `pack_version`, and a bounded pack-owned `options` mapping. Core configuration and composition MUST NOT define a species enum or universal humanoid slots. Each trusted in-process pack owns its option manifest and deterministic renderer and MUST compile to the same canonical 4-by-7 sheet used by arbitrary custom characters. The undeployed legacy top-level humanoid fields (`body`, `skin`, `hair`, `outfit`, color fields, and `accessory`) are removed without aliases or migration code. Unknown packs, versions, option names, missing required options, and invalid option values fail closed; they never fall back to another pack.

**Owner-approved analysis-recovery amendment (2026-09-17, ADR-038; FR-027/033/041/042, AC-039/040/045/060/061):** Same-round `retry` is available only while every requeued item has both generation attempts and active-execution time remaining. Exhausted failed items expose a separate explicit `reanalyze` operation that creates one idempotent successor batch for selected failed items, preserves the source batch and successful results, pins the original commit/selection policy, and defaults to the original frozen model pair. Using the current selected pair requires an explicit model-change confirmation. Runtime migration 26 records secret-free batch/item lineage, analysis round, and failure stage; migration 27 adds a durable source-consumed marker and bounded reanalysis idempotency receipts. Terminal snapshots freeze elapsed time, distinguish processed/success/failed/cancelled/confirmation counts, and treat `completed_with_errors` as terminal across API, SSE, and UI.

**Owner-approved URL editing exception (2026-09-12, ADR-029; FR-038/040, AC-055/057):** The owner explicitly requested that replacing a managed service URL prefill its saved value. Only `POST /api/admin/model-connections/{connection_id}/edit-endpoint`, guarded by the existing owner session, same-origin check and CSRF, may return `{connection_id, revision, base_url}` with `Cache-Control: no-store`. It accepts no arbitrary URL, reads the exact current encrypted revision, rejects host-managed/unknown connections with 404 and unavailable secret storage with 503, and makes no provider request or mutation. List/detail metadata remains URL-free; API keys, secret references and environment values are never returned. The UI fetches only on the explicit Replace URL action, keeps the result in the active form only, clears it on cancel/toggle-off/teardown, and ignores responses after a form or revision change. Loading disables URL editing/submission; failure permits retry or manual entry. No readback URL may enter browser storage, public drafts, exports, logs or snapshots. This narrow exception supersedes earlier blanket stored-URL readback prohibitions; stored-key prohibitions and destination-change credential rules remain unchanged.

**Owner-approved environment-connection control amendment (2026-09-12, ADR-031; FR-039/040, AC-055/056/057):** Host-managed connection cards are editable and deletable in authenticated Web Admin. Editing one requires a complete replacement URL because its environment URL is never read back; a successful replacement creates protected owner-managed state and takes precedence over later startup environment changes. A stored key may not cross destinations without explicit replacement/removal, while the first replacement of a host-managed no-key connection may remain no-key. Deletion remains blocked by live profile references, otherwise records a durable suppression marker before removing the connection so startup does not recreate it. Suppression/override metadata contains no URL or credential. This amendment supersedes section 11.5 text that limited the owner to creating a separate alternative.

**Owner-approved connection-rebinding amendment (2026-09-13, ADR-032; FR-039/040/042, AC-055/056/057/060):** An effective connection update atomically rebinds directly dependent editable candidates to the new connection revision, clears their prior probe evidence, and requires an explicit retest; the owner does not have to edit-save each model profile merely to repair its reference. Public-active, previous last-known-good, reindexing, and already frozen batch work remain pinned to their historical revision/provider. The analysis selection generation advances when its referenced connection changes, so stale plans are rejected without automatic probe, activation, reindex, or generation work.

**Owner-approved session-resume amendment (2026-09-13, ADR-033; FR-017/029/031, AC-049/050):** Reloading an authenticated admin page MUST resume the still-valid server session instead of demanding another launcher grant or password login. When no launch fragment is present, the frontend first calls strict same-origin `POST /api/admin/session/resume` with the existing `Secure`/`HttpOnly`/`SameSite=Strict` session cookie. A valid session returns a session-bound CSRF token and expiry metadata with `Cache-Control: no-store`; the token remains browser-memory-only. The endpoint never accepts or recreates a launch grant, and an absent, expired, revoked, wrong-origin, wrong-host, forwarded, or otherwise invalid session falls back to the existing relaunch/password recovery surface without disclosing session state.

**Owner-approved same-service URL and actionable-error amendment (2026-09-14, ADR-035; FR-039/040, NFR-003, AC-055/057):** A URL edit that keeps the provider and normalized security origin (scheme, case-insensitive hostname, and effective port) MAY retain the protected key; changing only the path, such as adding `/v1`, is not a credential transfer to another service. A provider, scheme, hostname, or effective-port change still requires explicit key replacement or removal. Every failed connection create/update/delete/refresh MUST produce exactly one visible, accessible operation-scoped alert that says what failed, gives a safe cause, confirms whether existing state was preserved, and gives a recovery action. Field errors are associated with the affected control, focus moves to the failure summary, a safe request ID is shown when available, and a submitted key is cleared with explicit re-entry guidance.

**Owner-approved chat-probe grace amendment (2026-09-14, ADR-036; FR-038/040, AC-054/057):** A Chat model probe keeps a 10-second baseline and automatically grants one additional 10-second window before reporting timeout. The provider receives one bounded 20-second deadline so the same in-flight request may finish; RepoNPC MUST NOT restart the request, double bill, activate, retry another model, or switch providers implicitly.

**Owner-approved flexible analysis-budget amendment (2026-09-14, ADR-037; FR-027/033/041, NFR-003/011, AC-058/059/060/061):** Repository analysis uses independently configurable active-work, provider-inactivity, archive and source budgets. The standard defaults are 1,800 seconds per repository, 300 seconds per provider operation, three same-provider transient attempts, 60 seconds for GitHub I/O, 256 MiB compressed archive, 1 GiB declared uncompressed archive, 100,000 archive entries, 2 MiB materialized/source file, 100 MiB repository text and 250 MiB corpus text. Waiting for archive, index or shared provider capacity does not spend active execution time. Oversized individual members are represented as body-free skipped evidence and do not fail an otherwise analyzable repository; unsafe paths/types and total archive ceilings still fail closed. The then-approved public chat output default was 4,096 with an 8,192 maximum; ADR-055 supersedes those output values only. Provider/model fallback remains forbidden. Complete buffered providers use the provider timeout as a socket/inactivity approximation; true first-token/token-idle progress requires a future streaming contract.

Application implementation is authorized under this approved specification. The words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY, and OPTIONAL are normative as described by RFC 2119.

Version 0.4.12 / ADR-060/061 records the 2026-10-14 owner-approved analysis-output validation, cache/source payload, compact admin highlights, and admin-only React Aria dialog/popover scope; the client-only license supplement is recorded in the Windows notices. Version 0.4.5 / ADR-052 pins the official bge-m3 source (FR-049), closes R08/R11/R12-B minimally and adds the admin maintenance page (FR-053, AC-076–AC-079). Version 0.4.4 / ADR-051 replaces the illustrated and character-derived scene with a simple chat interface, owner-selected fixed colour schemes and light/dark mode; only the NPC follows the character (FR-047/050/051/052, §12.3). Version 0.4.3 / ADR-050 (revised) makes templates colour-only and adds the owner background image with a realistic preview (FR-052, §12.3). Version 0.4.2 / ADR-050 adds owner-selectable scene templates (FR-051, §12.3). Version 0.4.1 / ADR-049 adds the character-driven visitor scene (FR-050, §12.3). Version 0.4.0 / ADR-048 approves the completion direction in §2.10 and the linked contract. Version 0.3.9 / ADR-046 approves the local-first portfolio, activation and guided GitHub card path. External testing is deferred by the owner until a public URL is supplied.

Technical Specification 0.3.8 / ADR-045 was approved on 2026-09-22 for validated automatic correction of repeated frame drift and exact per-frame pixel inputs. Version 0.3.7 / ADR-044 remains the approved preview-first structural edge-spill cleanup boundary.

The output defaults recorded in ADR-034/037 and the older version summaries below are historical; ADR-055 supersedes only their chat/analysis output defaults and chat hard maximum. Their independently approved execution and safety boundaries remain in force.

Version 0.3.0 / ADR-037 replaces the fixed 120-second repository / 45-second analysis-provider envelope with configurable active-work and inactivity budgets, excludes scheduler-capacity waiting, adds bounded same-provider transient retries, degrades oversized individual files to explicit skips, and widens public chat output to 4,096-default / 8,192-maximum.

Version 0.2.9 / ADR-036 gives a Chat probe a 10-second baseline plus one automatic 10-second grace window in the same bounded provider request. The 0.2.8 same-origin URL and actionable-error amendment remains in force.

Version 0.2.7 / ADR-034 was explicitly owner-approved on 2026-09-13: repository analysis defaults to 8,192 output tokens with a configurable hard maximum of 16,384. This is a separate authenticated-analysis policy, not an increase to visitor chat or synthetic model-test limits. Analysis rejects observed output-limit termination before JSON validation and retains only a fixed safe reason. All earlier amendments remain in force.

Version 0.2.6 makes page reload a continuation of a still-valid admin session. It adds a strict same-origin, cookie-authenticated resume exchange that reissues only session-bound CSRF/expiry metadata, retains CSRF in browser memory, consumes no launcher grant, and preserves all existing expiry, revocation, host/origin, and deployment-profile boundaries.

Version 0.2.5 makes a connection update one coherent owner action: directly referencing editable candidate profiles follow the new revision transactionally and become untested, while protected serving/reindex/frozen work remains on its historical provider revision. Runtime migration 22 repairs candidates stranded by earlier updates and records provider metadata on historical protected revisions. No provider request is implicit.

**0.2.3 approval:** On 2026-09-10 the owner approved the reviewed six-step model-first AI journey, an immediate manual route, and separate analysis-model readiness from published-index activation (ENGD-011 / ADR-030). This work package updates documents only. Existing 0.2.2 connection/profile implementation is present, but guided integration and clean-bootstrap lifecycle gaps remain; see `ONBOARDING_FLOW_IMPLEMENTATION_HANDOFF.md`. Figma and RepoNPC-managed GGUF/Hugging Face execution remain outside scope.

**0.2.2 historical approval:** On 2026-09-09 the owner accepted the provider-neutral onboarding analysis and requested specification, memory, and implementation-handoff updates under ENGD-010 / ADR-029. That documentation delivery did not establish application acceptance. The 2026-09-10 source review supersedes its then-current “not implemented” inventory without claiming complete release verification.

Version 0.2.3 puts model setup before project analysis on the AI route, adds an explicit four-step manual route, and separates the model pair selected for owner analysis from the publicly active bundle/model state. It requires the clean no-model/no-bundle runtime to become analysis-capable after explicit model setup without restart, while keeping publication and public chat behind their stricter bundle lifecycle.

Version 0.2.2 adds independent chat/embedding setup through authenticated Web Admin: explicit service selection, API base URL, write-only API key, manually entered model ID, optional model discovery, and capability testing. There is no automatically selected provider/model on a clean deployment. Section 11.5 supersedes the environment-only/browser-input prohibition in older sections only for this protected model-connection form. Stored keys and private endpoints are still never returned to browsers, exported, logged, or sent directly from the browser to providers. ADR-029 also supersedes a mandatory model-list gate when a gateway does not support listing; actual capability testing remains required.

Version 0.1.1 records the owner-approved Phase 2 closure boundary as historical context: Phase 2 shipped a build-time local embedding adapter and executable index CLI, while concrete chat adapters and runtime query-provider integration remained Phase 3 work. The local adapter is retained only for isolated reproducibility fixtures; version 0.1.9 is normative for production embedding deployment and requires an external profile.

Version 0.1.2 records the owner-approved first-owner onboarding amendment. A new deployment has no product default credential: a host-issued, short-lived, one-time setup code authorizes creation of the sole durable owner through `/admin`. The environment username/Argon2id-hash mode remains available for explicit pre-provisioning, and GitHub credentials gate GitHub operations rather than admin authentication.

Version 0.1.3 records the owner-approved personal-deployment convenience amendment as historical context. The four-character convenience now applies only to the explicit loopback evaluation profile; version 0.1.9/ADR-024 is normative for production and non-loopback administration. The Windows one-click launcher still defaults to local port 8090 without changing the production container port contract.

Version 0.1.4 records the owner-approved guided-onboarding amendment. It adds guided public-repository discovery, explicit selected-only analysis, owner-confirmed contribution suggestions, advanced raw-YAML mode, and no-token YAML export without changing schema version 1, writeback permissions, or provider fallback behavior.

Version 0.1.5 records the owner-approved vLLM provider-preset amendment. `vllm` is a named server-side deployment preset over the existing OpenAI-compatible transport, not a third wire protocol or bundle adapter. It permits explicitly configured private HTTP origins, keeps chat and embedding server/model/key settings independent, validates selected-model availability, and does not expose keys/private URLs or add fallback behavior.

Version 0.1.6 records the owner-approved GitHub identity and public-read connection amendment. GitHub OAuth Web Application Flow with PKCE is an alternative authentication method for the same sole owner, never open registration or a visitor account system. The host-issued setup proof remains mandatory for first-owner creation. OAuth and explicit public-read PAT credentials are separately encrypted in mutable runtime state; writeback remains a separate least-privilege credential.

Version 0.1.7 records the owner's 2026-08-16 authorization for the bounded GitHub resolver and durable analysis-batch extension. It replaces per-blob guided analysis with server-owned GraphQL metadata plus immutable-commit archives, and replaces browser-driven serial work with one durable, bounded-parallel batch for the sole owner. It does not add private-repository support, another owner, a hosted dependency, model tools, or credential/provider fallback.

Version 0.1.8 records the owner's 2026-08-30 authorization for the GitHub OAuth setup-guidance UX amendment. GitHub entry points remain actionable when OAuth is not configured: they open a host-side setup guide instead of redirecting to GitHub. Configured OAuth continues to use the existing top-level Authorization Code Flow with PKCE S256. The guide endpoint exposes only a canonical callback URL, fixed GitHub documentation URL, configuration state, and a next-step label; it never exposes secrets, tokens, secret-file paths, or owner identity.

Version 0.1.9 records the owner's 2026-08-30 engineering decisions: production embeddings are external provider profiles with CRUD and one active profile; Ollama may manage models through provider-native pull/delete while vLLM and generic OpenAI-compatible services are connect/probe-only; administration uses an explicit loopback/production password policy and private access topology; first-owner setup is local-password-first with optional GitHub binding and local break-glass recovery; and daily Web Admin work is complemented by a bounded host operations CLI. Where the historical 0.1.1/0.1.3 paragraphs above describe a local production embedding default or an unrestricted four-character production password, this 0.1.9 amendment is normative.

Version 0.2.0 records the owner's 2026-09-04 correction after observing the implemented first-run flow. The `loopback_evaluation` launcher now uses a short-lived one-use local-launch capability and presents no registration, password-login, or GitHub-login screen. Production and every non-loopback administration path retain the setup-code, local password, and host recovery controls. GitHub OAuth is connection-only and begins from authenticated settings; it never creates or authenticates the RepoNPC owner. ADR-027 is normative where the historical 0.1.2/0.1.3/0.1.6/0.1.8/0.1.9 text describes loopback password setup, GitHub sign-in, or a public OAuth setup guide.

Version 0.2.1 records the owner's 2026-09-08 decision to retire GitHub OAuth and browser-entered public-read PATs entirely. Public discovery and selected-repository analysis move to bounded unauthenticated GitHub REST resolution followed by an archive addressed by a validated full commit SHA. Anonymous rate exhaustion is a recoverable capacity state and never blocks manual authoring/export. The independent least-privilege writeback credential remains server-only and MUST NOT be sent to discovery or analysis. ADR-028 is normative where historical 0.1.6 through 0.2.0 text requires OAuth, public-read PATs, GraphQL, connection UI, or public-read credential storage. The current OAuth/PAT implementation is legacy until the ordered removal plan is complete; it is not a release target.

The local Windows launcher is also required to reconcile its own runtime state at startup: when the recorded process is stale, it MUST verify the recorded PID and configured Python executable before stopping it, MAY fall back from process-tree termination to a direct stop of that same verified PID when Windows reports an elevation-context error, and MUST never terminate an unknown process occupying the port.

## Superseded sections

### 5.5 Removed publication commands

The former CLI commands were:

```text
reponpc index publish --bundle-dir <directory>
reponpc index publish-manifest --bundle-dir <directory>
```

`index publish` created and verified an immutable Release asset and a pending stable-manifest artifact. `index publish-manifest` accepted that artifact and updated the remote `stable-manifest.json`. ADR-071 removed both commands.

### 11.2 Removed admin endpoint rows

The former API table included these rows:

| Method and path | Former contract |
| --- | --- |
| `GET /api/admin/config` | Return `{content,blob_sha,commit_sha,updated_at}` for `reponpc.yml`. |
| `PUT /api/admin/config` | Commit `{content,expected_blob_sha,commit_message}` or return `CONFIG_CONFLICT`. |
| `PUT /api/admin/assets/character/{filename}` | Commit an allowlisted PNG to GitHub. |
| `POST /api/admin/index/dispatch` | Dispatch `build-index.yml` and return an acknowledgement. |
| `POST /api/admin/session/github/start` / `POST /api/admin/setup/github/start` | Retired login/setup tombstone routes. |
| Legacy GitHub OAuth/PAT routes | Retired public-read credential tombstone routes. |

ADR-071 removed these rows with the routes.

### 14.4 Runtime activation (remote polling, superseded)

The former runtime fetched `stable-manifest.json` on startup and at a configured interval with ETags, downloaded a Release asset into staging, verified it, and atomically activated it. Pinning suppressed newer remote versions and unpinning resumed polling. ADR-071 replaced this remote lifecycle with verified local-bundle activation in the kept specification.


### 2.4 Legacy version 0.1.6 identity and connection requirements (superseded by 0.2.1)

The following bullets document the implemented migration source only. They are not 0.2.1 release requirements and MUST NOT be used to justify retaining a reachable OAuth/PAT product flow after ADR-028 is implemented.

- GitHub OAuth uses the Authorization Code Web Application Flow with a cryptographically random one-use `state`, PKCE S256 verifier/challenge, server-side token exchange, fixed configured callback URL, and a short-lived `HttpOnly` OAuth transaction cookie with `SameSite=Lax`. It is initiated only from an existing authenticated RepoNPC session and returns a public-read connection to that same owner; it never issues an owner session.
- OAuth has one connection intent. Legacy setup/login intents must return a safe removal error and must never create an owner, consume setup/local-launch proof, or redirect to GitHub. Expired, replaced, replayed, wrong-intent, and cross-browser transactions fail closed.
- The GitHub numeric user ID is stable connection metadata. The GitHub login is display metadata only and has no RepoNPC authentication meaning.
- OAuth requests no repository scope. RepoNPC rejects a broader reported scope, including `public_repo`. A selected OAuth token may be used only as `identity_public_read`; it can read public metadata/source after a bounded server-side readiness probe, but cannot write. A `401` makes that connection unavailable and MUST NOT select a PAT or writeback credential automatically.
- A manually submitted fine-grained PAT is never an authentication method. Its input is cleared immediately after submission and its persisted form is `public_read` only. It is never shown, echoed, masked, fingerprinted, logged, or returned to the browser.
- GitHub-only ownership is not supported in v1. Removing an OAuth connection affects only GitHub-backed public-read work and cannot revoke or create a RepoNPC session.

### 2.6 Legacy version 0.1.8 OAuth setup-guidance requirements (superseded by 0.2.1)

This section is historical migration context. The 0.2.1 target removes the setup guide and every OAuth/PAT entry point; FR-037 and ADR-028 are normative.

- When OAuth is not configured, the authenticated GitHub connection button MUST remain keyboard-operable and MUST open a setup guide dialog. It MUST NOT submit an OAuth start request or redirect to GitHub in that state.
- Recheck reports configuration state and does not implicitly navigate. When OAuth is configured, the dialog exposes a distinct **Continue to GitHub** action that performs the top-level redirect and preserves Authorization Code Flow, PKCE S256, one-use state, fixed callback, server-side token exchange, and connection intent.
- The setup guide MUST identify host-side deployment configuration, show the authoritative callback URL, link only to the fixed GitHub official OAuth-App documentation URL, explain host-secret configuration and service restart/recheck steps, and warn that secrets, encryption keys, and tokens MUST NOT be pasted into the browser.
- GET /api/admin/github/oauth/setup-guide MUST require an authenticated session and return only configured, callback_url, documentation_url, and next_step. It MUST set Cache-Control: no-store and MUST NOT return environment values, secret-file paths, secret material, token material, or owner identity.
- Dialog behavior MUST meet NFR-009: semantic dialog labeling, focus trap, Escape close, focus return to the invoking button, visible status/error announcements, Traditional Chinese/English parity, responsive layouts at 375/768/1024/1440 pixels, and reduced-motion compatibility.
- GitHub expiring-token refresh, refresh-token rotation, and revoke-error recovery are explicitly deferred from 0.1.8. Until a separately approved lifecycle amendment is implemented, a selected credential that receives `401` is marked `connection_required` and requires explicit reconnection; RepoNPC MUST NOT silently refresh or fall back to a PAT or writeback credential.

### 11.3 GitHub writeback

- The token MUST be a fine-grained token limited to contents/actions permissions on `REPONPC_CONFIG_REPOSITORY`.
- The target branch is `REPONPC_CONFIG_BRANCH`; it is never supplied by the browser.
- Allowed target paths are exactly `reponpc.yml` and normalized paths matching `assets/character/*.png`. Nested paths, deletion, renames, and arbitrary filenames are rejected in v1.
- `expected_blob_sha` is mandatory for replacement. Creation uses explicit `null` and fails if the file exists.
- Configuration is fully validated before commit. Assets are decoded and validated, not trusted by MIME/extension alone.
- Commit messages are length-limited plain text with a safe default.
- Every write creates a safe audit record with time, path, resulting commit SHA, request ID, and outcome, but not file bodies or credentials.

### 14.3 Stable manifest

The `reponpc-index` branch contains `stable-manifest.json`:

```json
{
  "stable_manifest_schema_version": 1,
  "bundle_id": "...",
  "release_tag": "index-...",
  "asset_url": "https://github.com/owner/repo/releases/download/.../...tar.zst",
  "asset_size": 123,
  "asset_sha256": "64hex",
  "published_at": "2026-08-10T12:01:00Z"
}
```

The Action uploads the immutable asset, verifies its availability, then updates this document in the final publication step. The URL host/repository must match configured allowlists.

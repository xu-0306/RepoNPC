# RepoNPC v1 Technical Specification

**Owner-approved README delivery (2026-10-12, OR-033 / ADR-059, Approved 0.4.11):**
[The README export contract](PROFILE_README_EXPORT_CONTRACT_2026-10-12.md) extends
FR-024 with complete localized README download and exact content preview from
the verified public snapshot. It uses the existing Pages GIF, rechecks its bytes,
preserves existing README/copy-card paths, and explains the same-name public
repository root requirement. No new hosting, GitHub write or model call is added.

**Owner-approved analysis-output and admin-presentation repair (2026-10-14, OR-034 / ADR-060, OR-035 / ADR-061, Approved 0.4.12, AC-080):** Analysis and contribution model output now uses the shared schema, personal-inference, and locale/source writing-system checks. Analysis facts expose source locations and pinned GitHub permalinks without repository excerpts; inferences require a localized `title`. The admin view presents compact, expandable highlights and uses React Aria only for the approved admin dialogs/popovers. These local implementation changes do not by themselves establish release acceptance.

**Owner-approved public summaries (2026-10-04, OR-032 / ADR-058, Approved 0.4.10):** [public summary contract](CHAT_PUBLIC_SUMMARY_CONTRACT_2026-10-04.md) supersedes prior pending-summary notes. An explicitly selected Responses interface may show bounded provider-defined public summaries, separate from validated answers; raw thinking stays private.

**Owner-approved waiting experience (2026-10-04, ADR-057 / OR-031, Approved
0.4.9):** [Chat processing contract](CHAT_PROCESSING_CONTRACT_2026-10-04.md)
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
The [implementation contract](A7_MODEL_CARDS_IMPLEMENTATION_2026-10-03.md) records
the additive fields and explicit handoff to the existing Chat model form. Choosing
a card makes no download/provider call or activation and preserves unsaved inputs.

**Implementation checkpoint (2026-09-30, A5/R08):** The approved visitor/appearance/Pages scope is being implemented under the [A5 integration contract](A5_VISITOR_APPEARANCE_EXPORT_CONTRACT.md). ChatGPT review6 accepted prior repairs and identified a technical path/dot FAQ collision; Luna max repaired it and Main reproduced six failures before repair. Final Web377/37 files, frontend format/lint/type/build, registry/source guard and Docker/Compose2 passed; earlier native phone drawer checks at host1440/375 remain applicable to unchanged CSS. The unchanged 62 Python inputs retain Python1,638/2 Windows skips, mypy91 and Ruff221 checks. The final FAQ repair has not received another ChatGPT review; the owner requested a [pause and handoff](A5_HANDOFF_2026-09-30.md). This evidence does not change Approved status or close release acceptance. Static live chat remains incomplete pending explicit payload/destination authorization; native ZIP completion and actual200% zoom are unverified.

**Approved A1 gateway amendment (2026-09-28, OR-027 / ADR-053; FR-047, AC-068/071):** [The frozen A1/F0 contract](A1_FUNNEL_GATEWAY_CONTRACT.md) is normative for gateway routing, environment fields, runtime migration 30, private API/Host/Origin authentication, identity protection, SSE and operator lifecycle. The owner approved the reviewed design and requested gpt-6-luna max implementation with Main review/takeover. Implementation is in progress; no public activation or external acceptance is implied.

**Implementation progress (2026-09-28):** A3 participation is implemented locally, including the bounded local/reindex build integration correction. A4 coverage and reviewed FAQ now have local build/API/security/storage and browser evidence; see [A4 contract](A4_COVERAGE_FAQ_IMPLEMENTATION.md) and [local verification](../release-evidence/a4/local-checks.md). Formal A12 release/Pages/Funnel evidence remains pending. The dated checkpoint below records the earlier state.

**Implementation progress (2026-09-27):** A2's v2 answer validator/service integration, owner-only fixed drop-reason logging and collapsible Sources list; R11's owner-scoped recent batch recovery with a synthetic authenticated browser reload check; and R12-B's passage-cache work-count and route/export/backup exclusion tests have local evidence. AC-065's participation-backed answer still depends on A3, and A4 must expose the coverage report. Formal AC-062–AC-065 and AC-077–AC-078 release evidence remains pending in A12. Historical “not implemented” amendment notes below describe the state when each decision was approved.

**Model source, repair closure and maintenance amendment (2026-09-27, ADR-052; FR-049, FR-053, AC-076–AC-079):** The built-in bge-m3 is the official `BAAI/bge-m3` fp32 ONNX export pinned to revision `5617a9f61b02` (about 2.29 GB, per-file SHA-256). Admin previews are served only through authenticated `no-store` admin routes (R08). The active-batch endpoint also returns a recent actionable terminal batch until the owner dismisses it (R11). R12-B first checks whether the passage-vector cache already covers the need. A 「維護」 page covers status, backup, restore, bundle rollback, stopping the gateway and update/Funnel guidance. Not implemented yet.

**Chat interface and colour scheme amendment (2026-09-26, ADR-051; FR-047/050/051/052, NFR-009/011, AC-068, AC-072–AC-075):** The owner asked for a simple chat UI instead of bundled illustrated backgrounds, colours that do not follow the character, several colour schemes to choose from, and light/dark mode. [Completion direction contract §4.0 and §4.4–§4.6](COMPLETION_DIRECTION_CONTRACT_2026-09-26.md) is normative.

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

**Scene template and background image amendment (2026-09-26, ADR-050; FR-051/052, FR-050, FR-018, NFR-001/009/011, AC-074–AC-075; revised by ADR-051 above):** The owner asked for several background and colour-scheme templates to choose in settings, then clarified that programmatically drawn template backgrounds are not wanted, and asked for an owner background upload with a realistic preview. [Completion direction contract §4.5–§4.6](COMPLETION_DIRECTION_CONTRACT_2026-09-26.md) is normative.

- Templates are **colour schemes only**, as data in one versioned, schema-validated registry (`scene_templates.yml`). Each has a palette mode (`follow_character`, or `fixed` OKLCH hue seeds) with a named tone. The default `auto` is the ADR-049 character-derived scene. No template draws a backdrop.
- The owner background image is MVP. An upload becomes a private draft, which is previewed in the real visitor components with the active character, a sample dialog, light/dark themes and desktop/phone frames. Focus point, dim and scaling are adjustable, and nothing public changes until 「套用」.
- Every template, with or without an image, passes the FR-050 contrast solver and NPC-separation check with every character.
- No code branches on template ids, and no template references a species, `pack_id`, filename or option key.

**Character-driven visitor scene amendment (2026-09-26, ADR-049; FR-047/050, FR-015/018, NFR-001/009/011, AC-072–AC-073; colour derivation retired by ADR-051 above):** The owner clarified that the reference mockup's cat is only an example: the visitor NPC and its scene MUST follow whatever character the owner selects or uploads. [Completion direction contract §4.4](COMPLETION_DIRECTION_CONTRACT_2026-09-26.md) is normative.

- The scene is a closed set of token roles in light and dark themes. It is derived deterministically from the canonical sheet's pixels (OKLCH clustering).
- Tokens resolve in this order: explicit owner override, optional opaque pack scene hints, sheet derivation, and a neutral default only on derivation error.
- A contrast solver guarantees WCAG 2.2 AA text contrast and NPC/backdrop separation.
- An optional validated owner background image is supported.
- No code path may branch on species, `pack_id`, filename or option names.
- Tokens are computed server-side and exported with the static site, so live and Pages rendering match.
- This amendment is not implemented yet.

**Owner-approved completion-direction amendment (2026-09-26, ADR-048; FR-006/011/012/014/040, FR-043–FR-049, AC-062–AC-071):** [The completion direction contract](COMPLETION_DIRECTION_CONTRACT_2026-09-26.md) is normative. (1) Chat answers use envelope v2: typed segments (`person | participation | project | inference`) with per-segment citation rules, `{{owner}}` rendered by the backend, a centralized inflation lexicon and numeric-fact check, and silent per-segment drop instead of whole-answer abstention; person questions without an owner statement are answered with what the project does and how it is built plus participation facts, never with a visitor-facing gap message. (2) A new `PARTICIPATION` evidence class carries GitHub login-matched participation period, owner flag and other-contributors flag, never raw counts. (3) An informational coverage check and an owner-reviewed FAQ (approve / reject / regenerate / rewrite-as-statement) are added; only approved, bundle-bound FAQ entries are exported or served. (4) The MVP public experience includes free-form live chat with the animated NPC: the owner manually uploads an exported static site to their own GitHub Pages repository, which calls the Tailscale Funnel visitor gateway for live answers and falls back to in-browser matching of approved FAQ entries while the host is offline. ADR-047's gateway split and Funnel transport return to MVP scope; visitors never see host, model, provider or cost information. (5) Windows novices install through a PyInstaller onedir bundle in an unsigned per-user Inno Setup installer; Docker remains for Linux/advanced use. (6) A built-in ONNX Runtime `bge-m3` embedding adapter is the production default after an explicit first-use download; external embedding services remain selectable. (7) Owner-only model guidance adds a device check, Ollama helper, plain-language errors, a status line and a data disclosure. This supersedes the "no RepoNPC-local production embedding default" text in FR-006/FR-012/§5.4/§13.3/§17, the whole-answer person-claim abstention in FR-011/§8, and the "externally hosted frontend origins" exclusion in §18 for the configured Pages origin only. No GitHub write, silent provider switch, public admin route or model-authored URL is introduced. Nothing in this amendment is implemented yet.

**2026-09-24 public-entry planning note (ADR-047):** The owner selected Tailscale Funnel as the future no-purchase HTTPS visitor entry. [The focused deployment plan](TAILSCALE_FUNNEL_DEPLOYMENT_PLAN_2026-09-24.md) must settle gateway routing, private admin origin, proxy/client-IP trust, host support and credential lifecycle before implementation changes. Existing approved behavior and local-only acceptance are unchanged; no Funnel path has passed public deployment verification. **Updated 2026-09-26 (ADR-048):** the Funnel visitor gateway is MVP scope, and its CORS allowlist additionally admits exactly the configured GitHub Pages origin without credentials.

**2026-09-22 local-publication amendment (ADR-046):** The owner authorized implementation of the local-first NPC and guided GitHub card journey. [Local publication contract](LOCAL_PUBLICATION_CONTRACT_2026-09-22.md) supersedes GitHub-only configuration/build/activation transport; all validation, attribution, privacy and last-known-good requirements remain. Implementation/acceptance evidence must distinguish local tests from actual public deployment.

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

| Field         | Value                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Status        | **Approved**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| Version       | 0.4.12                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| Product       | RepoNPC v1                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| Audience      | Implementation Agents, reviewers, maintainers                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| Last updated  | 2026-10-14                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| Approval date | 2026-08-10; Phase 2 closure amendment approved 2026-08-11; first-owner onboarding, personal-deployment convenience, and guided-onboarding amendments approved 2026-08-14; vLLM provider-preset amendment approved 2026-08-15; GitHub identity and connection amendment approved 2026-08-16; OAuth setup-guidance UX and ENGD-001/002/003/006 amendments approved 2026-08-30; passwordless loopback launch and connection-only GitHub amendment approved 2026-09-04; GitHub OAuth/public-read PAT retirement approved 2026-09-08; provider-neutral setup approved 2026-09-09; model-first guided workflow approved 2026-09-10; safe connection-revision rebinding and authenticated session resume approved 2026-09-13; same-service URL retention, actionable connection errors, Chat probe grace, and flexible analysis budgets approved 2026-09-14; controlled analysis recovery approved 2026-09-17; species-neutral character packs, direct legacy-field removal, 64px canonical sprites, bounded material conversion, and novice material discovery approved 2026-09-21; ordinary-owner character workspace and animated preview approved 2026-09-22; local publication approved 2026-09-22; completion direction (segment answers, participation, FAQ review, Pages + Funnel live chat, Windows installer, built-in bge-m3 embedding, owner model guidance) approved 2026-09-26; character-driven visitor scene (ADR-049) added 2026-09-26; scene templates (ADR-050) added 2026-09-26; colour-only templates and owner background preview (ADR-050 revision) added 2026-09-26; simple chat interface and fixed colour schemes with light/dark mode (ADR-051) added 2026-09-26; bge-m3 source pin, R08/R11/R12-B closure and maintenance page (ADR-052) added 2026-09-27; encrypted maintenance backups (ADR-054) and reasoning ON / 16k generation (ADR-055) approved 2026-10-03; analysis-output validation, cache/source shape and admin highlights (ADR-060) and admin-only React Aria scope/license supplement (ADR-061) approved 2026-10-14 |

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

## 1. System boundary

RepoNPC is a single-owner, open-source, self-hosted application that:

1. builds a searchable evidence index from owner-selected public GitHub repositories and owner-authored configuration;
2. presents a bilingual pixel-RPG portfolio on an external web page;
3. answers visitor questions using a configured OpenAI-compatible (including vLLM) or Ollama model;
4. attaches server-validated immutable GitHub citations;
5. supplies a script-free GitHub Profile README card;
6. lets the owner edit public configuration and approved character assets through an authenticated admin UI.

The production deployment is one application image plus persistent storage. Index building runs separately in GitHub Actions using the same Python package.

## 2. Requirement catalogue

### 2.1 Functional requirements

| ID     | Requirement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-001 | The system MUST load and validate a versioned `reponpc.yml` without source-code edits and MUST reject unknown keys by default.                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| FR-002 | The indexer MUST resolve and record an exact commit SHA for every enabled public repository and the configuration repository.                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| FR-003 | The indexer MUST enforce path, file type, symlink, secret, generated-content, and size exclusions before text enters the index.                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| FR-004 | The indexer MUST create stable line-addressable evidence records using Tree-sitter for Python, JavaScript/TypeScript, Go, and Rust, with a bounded text fallback.                                                                                                                                                                                                                                                                                                                                                                                                                         |
| FR-005 | The system MUST provide lexical retrieval through SQLite FTS5/BM25 for words, symbols, paths, and multilingual text.                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| FR-006 | The system MUST provide semantic retrieval with a multilingual embedding profile whose identity, revision and dimension are recorded in the bundle. The production default is the built-in `bge-m3` ONNX profile (FR-049) once the owner consents to its download; external OpenAI-compatible and Ollama embedding profiles remain selectable.                                                                                                                                                                                                                                            |
| FR-007 | The retriever MUST fuse independently ranked lexical and vector candidates using Reciprocal Rank Fusion (RRF) and apply only documented metadata policies.                                                                                                                                                                                                                                                                                                                                                                                                                                |
| FR-008 | Every evidence record and answer claim MUST preserve the distinction between `OWNER_ASSERTION`, `REPOSITORY_FACT`, `PARTICIPATION`, and `MODEL_INFERENCE`.                                                                                                                                                                                                                                                                                                                                                                                                                                |
| FR-009 | The chat service MUST answer only from retrieved evidence and MUST treat all repository/configuration text as delimited untrusted data.                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| FR-010 | The model MUST emit evidence IDs rather than URLs; the backend MUST validate them and construct immutable GitHub permalinks.                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| FR-011 | The service MUST NOT present a personal role, responsibility or achievement without a supporting owner assertion (FR-043). When no owner assertion matches, it MUST answer from project and participation evidence without a visitor-facing gap message (FR-044); when nothing relevant is retrieved it MUST return the localized no-match reply with suggested questions only when sanitized suggestions remain (ADR-065).                                                                                                                                                                                                                |
| FR-012 | The provider layer MUST support generic OpenAI-compatible chat/embedding APIs, the vLLM named OpenAI-compatible preset, and Ollama chat/embedding APIs through declared capability contracts. It MUST also provide the built-in `builtin_onnx` embedding adapter defined by FR-049. The local sentence-transformers adapter MAY remain only for isolated build/benchmark fixtures and MUST NOT be the production default or a runtime requirement.                                                                                                                                        |
| FR-013 | The public chat API MUST deliver validated answers, citations, completion data, and failures using the SSE contract in this document.                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| FR-014 | The public site MUST show profile/project content, suggested questions, evidence-linked chat, index/model status, and responsive bilingual controls.                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| FR-015 | The character system MUST support versioned species-neutral built-in packs, arbitrary custom sprite sheets, and preview-first conversion of bounded untrusted PNG, ZIP, or folder material. Core code MUST NOT require a species taxonomy, humanoid option slots, known filenames, or a contributor-authored manifest; every valid mode MUST produce the specified 64px canonical animation states with accessibility and reduced-motion behavior.                                                                                                                                        |
| FR-016 | The card service MUST provide sanitized, self-contained SVG, GIF fallback, and static preview outputs with light/dark and `zh-TW`/`en` variants.                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| FR-017 | The admin surface MUST use the single-admin session, CSRF, origin/host validation, expiration, rotation, and revocation controls defined here. `loopback_evaluation` MUST bootstrap that session only from a host-minted one-use local-launch grant and MUST expose no registration/password-login UI; production or any non-loopback administration MUST use the deployment-aware password, setup proof, and backoff controls. Reloading MAY resume only a still-valid HttpOnly-cookie session through the strict same-origin resume endpoint; it MUST NOT reuse or mint a launch grant. |
| FR-018 | The admin UI/API MUST read, validate, preview, and edit configuration and character assets without exposing secrets.                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| FR-019 | Admin writeback MUST use blob-SHA conflict detection and MUST modify only `reponpc.yml` or `assets/character/` in the configured repository.                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| FR-020 | GitHub Actions MUST validate sources, build a reproducible immutable bundle, publish it to a GitHub Release, and update the stable manifest last.                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| FR-021 | The runtime MUST poll, verify, atomically activate, retain, and roll back bundles according to this document.                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| FR-022 | All visitor/admin workflows and equivalent answers MUST support Traditional Chinese (`zh-TW`) and English (`en`).                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| FR-023 | The system MUST expose public status plus process/readiness health endpoints without revealing secrets or sensitive diagnostics.                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| FR-024 | The admin UI MUST provide complete localized README.md download and exact content preview from the confirmed public snapshot and verified Pages card, with same-name public repository root guidance; it MUST retain ready-to-copy GitHub README snippets for SVG, GIF, light/dark, and locale selections.                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| FR-029 | RepoNPC MUST support exactly one owner through profile-specific local authentication: one-use launcher grants for `loopback_evaluation`, and host-issued setup proof plus local password sign-in/recovery for production or non-loopback administration. GitHub OAuth MUST NOT authenticate or register the owner.                                                                                                                                                                                                                                                                        |
| FR-030 | **Legacy in 0.2.1; superseded by FR-037.** OAuth and browser-entered public-read PAT storage is not a release requirement. Writeback credential isolation remains normative under FR-019 and FR-037.                                                                                                                                                                                                                                                                                                                                                                                      |
| FR-031 | The admin UI MUST expose the access state appropriate to the deployment profile with bilingual, keyboard-accessible, no-secret behavior. It MUST NOT expose GitHub OAuth setup/connection controls, public-read PAT inputs, or missing-public-read-credential warnings.                                                                                                                                                                                                                                                                                                                   |
| FR-034 | **Legacy in 0.2.1; superseded by FR-037.** The OAuth setup-guide, recheck, and Continue-to-GitHub contract is retained only as historical migration context.                                                                                                                                                                                                                                                                                                                                                                                                                              |
| FR-035 | The deployment MUST provide an authenticated embedding-profile registry with create/read/update/delete, provider/model probing, at most one active profile (exactly one when ready), explicit reindex status, and atomic last-known-good switching.                                                                                                                                                                                                                                                                                                                                       |
| FR-036 | The deployment MUST provide the bounded host operations CLI and private-admin access topology defined in sections 5.5, 11.1, and 15.5; it MUST NOT add a separate public management protocol or treat a non-standard port as access control.                                                                                                                                                                                                                                                                                                                                              |
| FR-037 | RepoNPC MUST retire GitHub OAuth and browser-entered public-read PATs, resolve selected public repositories through bounded unauthenticated GitHub REST requests, and fetch source only by a validated immutable full commit SHA. Rate exhaustion MUST provide a safe retry state and preserve manual continuation. Discovery and analysis MUST NOT receive or fall back to the independent writeback credential.                                                                                                                                                                         |

### 2.2 Non-functional requirements

| ID      | Requirement                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| NFR-001 | Security: untrusted inputs MUST NOT change system policy, execute code/tools, create arbitrary network requests, traverse paths, or inject active HTML/SVG.                                                                                                                                                                                                                                                  |
| NFR-002 | Privacy: raw conversations MUST NOT be persisted by default; logs MUST omit secrets, full prompts, full answers, and raw IP addresses.                                                                                                                                                                                                                                                                       |
| NFR-003 | Availability and capability degradation: an invalid update MUST NOT replace the last known-good bundle; first boot without a bundle MUST present an actionable setup state; and an unavailable optional integration MUST NOT disable unrelated local or public functions. Every unavailable primary action MUST identify the specific cause, a next recovery action, and a safe alternative when one exists. |
| NFR-004 | Performance: with the reference corpus (up to 50,000 chunks), warm retrieval p95 MUST be <= 750 ms on the reference 4-core/8-GB CPU host, excluding model time.                                                                                                                                                                                                                                              |
| NFR-005 | Streaming: after the validated model response is available, the first SSE event MUST be emitted within 250 ms; the overall public request timeout defaults to 180 seconds (maximum 300); real bounded progress may precede validated delivery (ADR-057).                                                                                                                                                                                                                                    |
| NFR-006 | Retrieval quality: the committed evaluation set MUST achieve Recall@8 >= 85%.                                                                                                                                                                                                                                                                                                                                |
| NFR-007 | Answer quality: >= 95% of emitted citations MUST resolve correctly, >= 90% of factual answer claims MUST be entailed, and >= 90% of deliberately unsupported questions MUST produce a correct abstention.                                                                                                                                                                                                    |
| NFR-008 | Language parity: equivalent `zh-TW` and `en` evaluation questions MUST retrieve materially equivalent evidence at least 90% of the time.                                                                                                                                                                                                                                                                     |
| NFR-009 | Accessibility: visitor and admin UIs MUST meet WCAG 2.2 AA for implemented flows, including keyboard use, focus, labels, contrast, and reduced motion.                                                                                                                                                                                                                                                       |
| NFR-010 | Portability: the documented Docker Compose installation MUST work on current Docker Engine for x86_64 Linux without external database/vector services.                                                                                                                                                                                                                                                       |
| NFR-011 | Reproducibility: identical configuration, source commits, schema, and model inputs MUST produce equivalent evidence IDs and bundle contents except declared build metadata.                                                                                                                                                                                                                                  |
| NFR-012 | Observability: health, update, retrieval, latency, usage, and error data MUST be diagnosable by request ID without logging sensitive bodies.                                                                                                                                                                                                                                                                 |
| NFR-013 | Maintainability: Python and TypeScript public module boundaries MUST be typed, tested, and covered by locked dependency graphs.                                                                                                                                                                                                                                                                              |
| NFR-014 | Cost control: per-IP/global concurrency, request limits, output limits, and daily generation budgets MUST be enforced before paid provider work is accepted.                                                                                                                                                                                                                                                 |

### 2.3 Version 0.1.4 functional requirements

| ID     | Requirement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| FR-025 | The authenticated admin UI MUST default to a guided onboarding flow that explains the product outcome, preserves raw YAML as an advanced mode, resumes saved configuration, and exposes the next valid action with a reason when blocked. Every non-terminal guided stage MUST support backward navigation or an equivalent Edit action without requiring a full reset; only selection-bound results and data for removed or materially changed repositories may be invalidated.                 |
| FR-026 | RepoNPC MUST discover and resolve public GitHub repositories from an owner-supplied username/profile URL or manual repository slug without OAuth, private-repository access, source download, model calls, or broadened writeback-token permissions before explicit repository selection.                                                                                                                                                                                                        |
| FR-027 | RepoNPC MUST analyze only explicitly confirmed public repositories, reuse the production indexing/trust boundaries, invoke only the configured provider/model, clean temporary data, and return separately labeled repository facts and model inferences. Analysis is an optional enhancement: before preflight and on every blocked or failed analysis state, the owner MUST be able to skip it and continue with owner-authored contribution fields without first triggering a failed request. |
| FR-028 | Model-generated role, responsibility, achievement, context, summary, or translation suggestions MUST remain unconfirmed proposals until the owner accepts or edits them; only confirmed configuration text becomes `OWNER_ASSERTION`. The owner MUST be able to author contributions manually and validate, preview, copy, or download a complete YAML draft without model availability, a GitHub public-read connection, or GitHub writeback.                                                   |

### 2.4 Legacy version 0.1.6 identity and connection requirements (superseded by 0.2.1)

The following bullets document the implemented migration source only. They are not 0.2.1 release requirements and MUST NOT be used to justify retaining a reachable OAuth/PAT product flow after ADR-028 is implemented.

- GitHub OAuth uses the Authorization Code Web Application Flow with a cryptographically random one-use `state`, PKCE S256 verifier/challenge, server-side token exchange, fixed configured callback URL, and a short-lived `HttpOnly` OAuth transaction cookie with `SameSite=Lax`. It is initiated only from an existing authenticated RepoNPC session and returns a public-read connection to that same owner; it never issues an owner session.
- OAuth has one connection intent. Legacy setup/login intents must return a safe removal error and must never create an owner, consume setup/local-launch proof, or redirect to GitHub. Expired, replaced, replayed, wrong-intent, and cross-browser transactions fail closed.
- The GitHub numeric user ID is stable connection metadata. The GitHub login is display metadata only and has no RepoNPC authentication meaning.
- OAuth requests no repository scope. RepoNPC rejects a broader reported scope, including `public_repo`. A selected OAuth token may be used only as `identity_public_read`; it can read public metadata/source after a bounded server-side readiness probe, but cannot write. A `401` makes that connection unavailable and MUST NOT select a PAT or writeback credential automatically.
- A manually submitted fine-grained PAT is never an authentication method. Its input is cleared immediately after submission and its persisted form is `public_read` only. It is never shown, echoed, masked, fingerprinted, logged, or returned to the browser.
- GitHub-only ownership is not supported in v1. Removing an OAuth connection affects only GitHub-backed public-read work and cannot revoke or create a RepoNPC session.

### 2.5 Version 0.1.7 bounded resolver and batch requirements

| ID     | Requirement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-032 | GitHub-backed guided analysis MUST use a centralized unauthenticated public-read resolver that obtains public repository eligibility and immutable commit OIDs through bounded fixed-origin REST metadata, and downloads only an archive addressed by that full commit SHA. It MUST reject unconfirmed, private, inaccessible, or policy-disallowed archived repositories before source access; it MUST never send or fall back to the writeback credential. Anonymous primary/secondary rate exhaustion MUST produce a safe bounded retry state without busy looping. |
| FR-033 | Guided analysis MUST run as a durable, owner-scoped, idempotent batch with safe snapshots/events, bounded stage-specific concurrency, pause/resume/cancel/retry/restart recovery, isolated staging and terminal cleanup. Cache reuse MUST be integrity-checked and keyed by immutable commit plus policy, parser, embedding, chat model, prompt, and output-schema identities. A dispatched generation interrupted by cancellation or restart MUST require explicit retry confirmation.                                                                                |

### 2.6 Legacy version 0.1.8 OAuth setup-guidance requirements (superseded by 0.2.1)

This section is historical migration context. The 0.2.1 target removes the setup guide and every OAuth/PAT entry point; FR-037 and ADR-028 are normative.

- When OAuth is not configured, the authenticated GitHub connection button MUST remain keyboard-operable and MUST open a setup guide dialog. It MUST NOT submit an OAuth start request or redirect to GitHub in that state.
- Recheck reports configuration state and does not implicitly navigate. When OAuth is configured, the dialog exposes a distinct **Continue to GitHub** action that performs the top-level redirect and preserves Authorization Code Flow, PKCE S256, one-use state, fixed callback, server-side token exchange, and connection intent.
- The setup guide MUST identify host-side deployment configuration, show the authoritative callback URL, link only to the fixed GitHub official OAuth-App documentation URL, explain host-secret configuration and service restart/recheck steps, and warn that secrets, encryption keys, and tokens MUST NOT be pasted into the browser.
- GET /api/admin/github/oauth/setup-guide MUST require an authenticated session and return only configured, callback_url, documentation_url, and next_step. It MUST set Cache-Control: no-store and MUST NOT return environment values, secret-file paths, secret material, token material, or owner identity.
- Dialog behavior MUST meet NFR-009: semantic dialog labeling, focus trap, Escape close, focus return to the invoking button, visible status/error announcements, Traditional Chinese/English parity, responsive layouts at 375/768/1024/1440 pixels, and reduced-motion compatibility.
- GitHub expiring-token refresh, refresh-token rotation, and revoke-error recovery are explicitly deferred from 0.1.8. Until a separately approved lifecycle amendment is implemented, a selected credential that receives `401` is marked `connection_required` and requires explicit reconnection; RepoNPC MUST NOT silently refresh or fall back to a PAT or writeback credential.

### 2.7 Version 0.1.9 engineering requirements

#### External embedding profile registry

- A deployment MUST have one usable embedding profile: the built-in `builtin_onnx` `bge-m3` profile after explicit download consent (FR-049, 0.4.0), or an external `ollama`, `vllm`, or `openai_compatible` interface. An in-process/local sentence-transformers runtime is not a supported production profile; it may be used only by isolated benchmark/build fixtures.
- Chat and embedding profiles are independent. A configured chat model never implies embedding capability. The selected embedding service MUST expose an embeddings operation and a model identity that can be probed before activation.
- The authenticated Web Admin MUST support embedding-profile create, read, update, delete, probe, and explicit activation. At most one profile may be `active`; deleting or disabling the active profile is rejected unless a replacement has passed its probe. A deployment with no valid active profile is not ready for semantic retrieval.
- A profile records a stable local ID, provider kind, provider model ID, server-side endpoint/credential references, observed dimension, normalization, query/passage prefixes, capability status, and timestamps. Secret values and private URLs never enter browser responses, public YAML, bundles, logs, or snapshots.
- Activating a new profile whose model identity, dimension, prefix, normalization, or provider semantics differ from the active bundle MUST enter `reindex_required`/`reindexing` state. The candidate is probed, indexed, validated, and smoke-tested before an atomic switch. Any failure keeps the last-known-good profile/bundle serving.
- The first-run model center MUST start with explicit service selection and no selected provider/model. Only after the owner chooses Ollama may its curated catalog recommend `qwen3-embedding:0.6b`, with `BAAI/bge-m3` and `embeddinggemma:300m` as alternatives. Catalog entries MUST show license, language/context notes, resource estimate, and provider support; recommendations never create a profile, download a model, or substitute for a live probe.
- Ollama MAY expose provider-native installed-model listing, curated pull, progress/cancel, and delete actions. vLLM and generic OpenAI-compatible providers expose connect/list/probe/select only; installation is performed on the provider host. RepoNPC MUST NOT download arbitrary URLs, arbitrary local paths, or unverified model archives.

#### Private administration and password policy

- The deployment profile MUST be explicit. `loopback_evaluation` uses the 0.2.0 local-launch grant and has no password creation/login UI. `production` (and any non-loopback admin exposure) requires a 15–128 Unicode-code-point password. Fifteen is a minimum, not a maximum. No character-class composition rule is required; new passwords are rejected when present in the configured common/compromised-password blocklist.
- Existing password hashes remain usable during migration and are not deleted in loopback mode. Production password creation/change and host recovery apply the production policy. Argon2id, backoff, secure cookie sessions, CSRF, origin checks, idle/absolute expiry, and revocation remain mandatory where applicable.
- Windows production (ADR-070) keeps the application, the explicit `http://localhost:<port>` admin origin and the visitor gateway on loopback. Secret files, `model-secrets/master.key` and the data directory must pass the owner-only check: on Windows the DACL grants access only to the current user, SYSTEM and Administrators, with no allow entry, explicit or inherited, for any other account. Windows enforces this only in `production`. The Windows secret root is `<data_dir>\private`, and launchers pass `_FILE` paths instead of secret values.
- A non-standard port is not an access control. The supported headless topology binds the admin-capable service to loopback and uses an SSH local-port tunnel, or uses a private LAN/VPN with firewall allowlisting. A reverse proxy MAY expose visitor routes while denying `/admin` and `/api/admin` from the public Internet. A public `0.0.0.0` admin listener is not a supported default.

#### Local-first owner and recovery

- In `loopback_evaluation`, `reponpc admin launch-token` creates a 256-bit one-use two-minute grant only after loopback configuration validation. Its digest is stored in runtime SQLite; the browser receives it only in a URL fragment and exchanges it for the normal session. The first valid exchange atomically creates or reuses the sole local owner without asking for a username or password. A missing/expired grant presents a relaunch action, not registration or GitHub sign-in.
- In production or any non-loopback mode, host-issued setup proof MUST be followed by local username/password creation. The local password remains the break-glass recovery method. `reponpc admin set-password --data-dir <dir>` is host-only, changes only the local hash, never reopens setup or changes the independent writeback credential, and is required before a passwordless local owner can become production-ready.
- GitHub OAuth and public-read PATs are unsupported under 0.2.1 and have no owner-session role. Public repository discovery/analysis uses anonymous REST capacity.

#### Bounded operations CLI

- Web Admin is the daily surface for configuration, embedding profiles, provider probes, and status. The host CLI is limited to `admin launch-token` for loopback launch, `admin setup-code`/`admin set-password` for production bootstrap/recovery, `runtime check`, `runtime backup <path>`, `bundle status`, `bundle verify <id>`, `bundle pin <id>`, and `bundle unpin`.
- Linux/headless operators use SSH to reach the same Web Admin; no separate public management protocol or public setup port is added. Commands require explicit paths/IDs, stable safe errors, and consistency/rollback tests.

### 2.8 Version 0.2.2 model setup requirements

| ID     | Requirement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-038 | The authenticated owner MUST configure chat and embedding independently using a provider-neutral service form with an explicit protocol/preset, API base URL, write-only API key when needed, and editable model ID. Listing is optional assistance; model capability testing is mandatory before use. New deployments MUST start with neither provider nor model selected and allow administration/manual authoring without models.                                                                                                                                                                                                                                                                                                                                                                                                          |
| FR-039 | Model connections MUST persist through a deployment-local protected secret boundary, with server-issued references, explicit credential replacement/removal, bounded validated egress, safe metadata-only reads, and transactional revision/activation behavior. Editing a destination MUST NOT forward a previously stored key to that destination. Environment-based configurations remain supported; their cards can be explicitly replaced or deleted, and a durable owner override/suppression MUST prevent startup from silently overwriting or recreating that choice. Effective updates MUST atomically rebind directly dependent editable candidates and invalidate their probe evidence/analysis generation while retaining historical provider revisions for public-active, previous last-known-good, reindexing, and frozen work. |
| FR-040 | First-run model setup MUST present separate chat and search capabilities, reversible steps, contextual recovery, and bilingual plain-language statuses. Dimensions, prefixes, connection references, raw errors, and model-installation diagnostics MUST NOT be required knowledge in the primary flow. Configuration, test, activation, download, reindex, and publication are distinct operations.                                                                                                                                                                                                                                                                                                                                                                                                                                          |

These requirements extend FR-006/FR-012/FR-025/FR-035 and NFR-001/002/003/008/009/011/012/013/014. AC-053 through AC-057 define their acceptance. All prior non-legacy v1 requirements remain required.

### 2.9 Version 0.2.3 model-first guided workflow

| ID     | Requirement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-041 | The authenticated first-run AI route MUST configure, test, and explicitly select both analysis/chat and content-finder (embedding) models before repository selection and analysis. Welcome is unnumbered; the six steps are models, repositories, analysis, contributions, profile, and preview/draft. A manual route MUST be available at welcome, model setup, and analysis blockers without an attempted model call. Existing draft/resume/edit routes MUST preserve unrelated work and lead directly to any missing prerequisite.                              |
| FR-042 | Admin analysis MUST use an explicitly selected, tested, immutable chat/embedding revision pair independently of public bundle activation. A clean runtime MUST be able to configure this pair and analyze a confirmed repository without a published bundle, preconfigured environment provider, or restart. Public semantic chat still requires validated compatible bundle activation. Model or selection changes MUST invalidate stale admission plans/caches without retargeting in-flight work, silently generating again, or discarding owner-confirmed text. |

These extend FR-025/FR-027/FR-028/FR-033/FR-038/FR-040 and NFR-001/002/003/008/009/011/013/014. AC-058 through AC-060 are additional release gates. Section 11.6 governs order and analysis selection where older sections conflate a selected analysis profile with a publicly active embedding profile.

### 2.10 Version 0.4.0 completion direction (ADR-048)

**A4 local implementation (2026-09-28):** FR-046 is realized by the [coverage/FAQ implementation contract](A4_COVERAGE_FAQ_IMPLEMENTATION.md), including authenticated routes, runtime migration 29, exact-bundle approval, the existing contribution-editor/save/prepare/regenerate flow and public/export allowlists. This local evidence does not establish A5 static export or public deployment acceptance.

**Owner FAQ diagnostics (ADR-064, owner-approved 2026-10-19; FR-043/044/046):** Owner FAQ entry responses from `GET /api/admin/portfolio/faq` and the check/regenerate/review/variants operations include `no_match_reason: <closed code> | null`. Codes are `MODEL_INSUFFICIENT_EVIDENCE`, `ENVELOPE_SCHEMA_INVALID`, `SOURCE_ID_UNKNOWN`, `MODEL_AUTHORED_MARKUP`, `INFERENCE_CYCLE`, `SELECTED_MAP_INVALID`, `ALL_SEGMENTS_DROPPED`, `VALIDATION_UNEXPECTED`, and `NO_EVIDENCE_SELECTED`. Migration 37 adds nullable CHECK-constrained `faq_entries.no_match_reason`; backup/restore retains it. Regeneration clears the old reason before generation; answered and partial answers use null. Existing `dropped_segments` / `diagnostics_json` retain the list of `{segment_index, reason_codes}`, and coverage-status logic is unchanged. Only the authenticated review panel shows a short localized label. Public APIs, SSE, approved-FAQ JSON/static exports and visitor assets exclude the field and codes; raw diagnostics remain private; ADR-066 additionally publishes only the coarse no_match_kind and its visitor copy. Empty evidence budget returns no-match before chat generation, empty retrieval retains the existing model-call behavior, and missing bundle/index retains unavailable/503 behavior.


The [completion direction contract](COMPLETION_DIRECTION_CONTRACT_2026-09-26.md) is normative for the details of these requirements.

| ID     | Requirement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| FR-043 | The chat provider MUST return envelope v2: an ordered list of segments, each with a closed `kind` (`person`, `participation`, `project`, `inference`), text and `source_ids`, plus `insufficient_evidence`. The model MUST refer to the portfolio owner only through the `{{owner}}` placeholder, which the backend renders from `profile.display_name`. `person` segments MUST cite at least one `OWNER_ASSERTION`, MAY paraphrase it, MUST pass the centralized inflation lexicon (`src/reponpc/chat/policy/inflation_terms.yml`) and the numeric-fact check, and are labelled as the owner's own statement. `participation` segments MUST cite `PARTICIPATION` and MUST NOT assert a role. `project` segments MUST cite repository evidence; if the configuration-derived identity registry or per-locale person-reference data detects a person reference, the segment is reclassified as `person` and revalidated. `inference` keeps the existing non-cyclic rule. A failing segment is dropped silently with an owner-only reason code; envelope-level integrity failures (schema, model-authored URL/HTML, unknown/unselected source, inference cycle) still reject the whole answer. Keyword/pronoun lists are non-authoritative recall data only.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| FR-044 | Person-oriented questions without a matching owner assertion MUST be answered from `participation` and `project` segments (whose project it is, when the owner was active, what the project does and how it is built) without any visitor-facing "not explained" or partial-omission note. With no valid segment or `insufficient_evidence=true`, the service MUST return the localized no-match reply classified by ADR-066, with no provider retry: no_content offers up to three sanitized, distinct suggested questions and MUST NOT promise suggestions when none remain (ADR-065); temporary offers the fixed ask-again text and button, no suggestions and no contact link. The NPC speaks about the owner in the third person. Citations are grouped into one collapsible Sources row labelled owner statement / GitHub participation / project documents and code, with permalink details on expansion.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| FR-045 | The indexer MUST derive `PARTICIPATION` evidence per enabled repository at the pinned SHA from the confirmed `profile.github_login` (required, prefilled from the configuration repository owner; `profile.aliases` optional): `is_repository_owner`, `first_commit` and `last_commit` (month-granular dates with immutable commit permalinks), `has_visible_commits`, and `other_contributors_visible`. It uses GitHub's `author` filter, the commits `Link rel="last"` page and `contributors?per_page=2`. Unlinked commit emails are ignored. Raw counts MUST NOT be displayed. A failed request MUST record the fact as unavailable, never as zero or non-participation. No collector means no participation evidence, including ephemeral onboarding analysis with no confirmed login. Participation facts live in source/evidence metadata; the unused duplicate bundle-meta key is omitted from new bundles and tolerated in old ones. Any host-side read token MUST NOT be exported.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| FR-046 | Before publication the admin MUST offer an informational coverage check over a per-locale standard question registry, reporting answered / partially answered with owner-only reason codes / no relevant content, and an optional shortcut to add an owner statement. It MUST NOT block publication. FAQ candidates from `profile.suggested_questions` and the coverage set pass the normal answer pipeline; the owner may approve, reject, regenerate, or rewrite as an owner statement (saved as a claim, then regenerated). Free editing of answer text is not allowed. Approval is bound to the bundle ID; a bundle change marks items as needing reconfirmation. Only approved items are exported or served.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| FR-047 | The MVP visitor experience MUST provide the profile card, project cards (name, description, language, stars, forks), the animated NPC with an available/resting indicator, free-form live chat with streamed answers, suggestion chips and collapsible citations. Live answers run on the owner host behind the ADR-047 visitor-only gateway exposed through Tailscale Funnel (route allowlist, rate limits, daily caps, size limits, SSE timeouts, no credentials, no host/model/provider/cost fields in visitor responses). An admin "Export share site" action MUST produce a self-contained static folder (HTML/CSS/JS, public JSON, character assets, `.nojekyll`, hashed manifest) that the owner uploads manually to their own GitHub Pages repository; RepoNPC performs no GitHub write. Gateway CORS MUST admit only the configured Pages origin without credentials. While the gateway is unreachable, the page MUST remain usable, show the resting state, and match typed questions in the browser against approved FAQ entries only, never generating text. Export MUST include only public data, pass a secret scan, respect GitHub Pages size limits, and exclude admin routes and data. The GitHub card links to the owner-entered page URL after a fetch and manifest-hash check. Views/traffic counts and attachments are excluded; microphone input is post-MVP and browser-local only. (0.4.4, ADR-051) The page MUST use a simple chat layout: a collapsible sidebar with the profile and project cards (a drawer on phones); a top bar with the NPC status avatar, language switch and light/dark toggle; and a centred chat column with a welcome hero (large animated NPC, greeting, suggestion chips), right-aligned visitor bubbles, left-aligned NPC answers with an avatar and citations, and an input bar pinned to the bottom. |
| FR-048 | Windows novices MUST be able to install and start RepoNPC without Docker or a separate Python installation, using a PyInstaller onedir bundle wrapped in a per-user Inno Setup installer with shortcuts and an uninstaller. The launcher MUST start the loopback backend, wait for health and open the admin page in the default browser, with an obvious open-admin/quit control. User data lives outside the install folder, survives uninstall unless explicitly removed, and survives installing a newer version. The installer does not bundle the embedding model. Unsigned MVP releases MUST publish SHA-256 checksums and SmartScreen guidance. Docker remains supported for Linux and advanced deployments; macOS is out of first-release scope. An explicitly selected Windows production mode (ADR-070) runs the `production` profile on loopback with setup-code or host `set-password` sign-in and owner-only private-file checks, so the owner can start the visitor gateway for Funnel.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| FR-049 | The provider layer MUST include a `builtin_onnx` embedding adapter (ONNX Runtime, CPU, no PyTorch) serving `bge-m3` (1024 dimensions, no prompt prefix, 8192-token context) as the default embedding profile. The first time an index is needed, the owner MUST choose between downloading the built-in model (showing size, license and source, then a cancellable/resumable progress bar), configuring another embedding service, or deferring (building stays blocked with an explanation). Nothing is downloaded without that explicit choice. The download MUST be verified against a pinned source and checksum before use. Changing the embedding model MUST warn that a full re-index is required before confirmation. (0.4.5, ADR-052) The pinned source is the official `BAAI/bge-m3` `onnx/` folder at revision `5617a9f61b028005a4858fdac845db406aefb181` (fp32, about 2.29 GB); the dialog shows the size from the pinned file list, not a hardcoded value.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| FR-050 | (0.4.1, ADR-049; revised 0.4.4, ADR-051) The visitor NPC MUST be the active character, whether built-in or uploaded, in the welcome hero, the answer avatars and the status avatar. Page colours MUST NOT follow the character. They come from the owner-selected colour scheme (FR-051) as closed token roles (`background`, `surface`, `surface_alt`, `ink`, `muted_ink`, `accent`, `accent_ink`, `border`, `stage`, `focus`) for light and dark variants. The only per-character adjustment is NPC separation: when the NPC edge colour vs `stage` is below 3:1, only `stage` lightness is adjusted, or a contrasting plate is drawn if that is not enough. Text colours never change for the NPC. An optional owner accent is validated against WCAG 2.2 AA and adjusted with a visible reason. An optional owner image appears only in the welcome hero (FR-052). Scene decisions MUST NOT depend on species, `pack_id`, filenames or option names, and no page colour is derived from sheet pixels. Tokens are resolved server-side, served in the public profile and exported in the hashed static-site manifest (§12.3).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| FR-051 | (0.4.2/0.4.3, ADR-050; revised 0.4.4, ADR-051) The owner MUST be able to choose a colour scheme and a colour mode in settings. Schemes MUST be data in one versioned, schema-validated registry (`color_schemes.yml`) with a stable id, version, localized labels and explicit light and dark `#rrggbb` values for every token role. The registry MUST fail to load, naming the scheme, variant and pair, when any text pair is below 4.5:1 or any non-text pair is below 3:1; scheme values are never corrected at runtime. `color_mode` is `system` (default, following `prefers-color-scheme`), `light` or `dark`, and both variants are always published. When `visitor_mode_toggle` is true (default), visitors MAY switch light/dark. The choice MUST be stored only in the visitor's browser `localStorage`, never sent, exported or set as a cookie, and a same-origin script applies it before first paint. Visitors MUST NOT choose a scheme. An unknown configured id MUST fail closed; retired ids resolve through registry aliases. No code path may branch on a scheme id, no scheme may reference a species, `pack_id`, filename or option key, and no scheme draws a backdrop. The export stores resolved tokens plus the scheme id and version (§12.3).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| FR-052 | (0.4.3, ADR-050; placement revised 0.4.4, ADR-051) The owner MUST be able to upload a background image (PNG/WebP, validated and re-encoded per FR-050) and see, before publishing, a preview of the visitor page rendered by the real visitor components with that image in the welcome hero, the active character, the selected colour scheme and a sample dialog in the chat layout marked as an example, in light and dark themes and desktop and phone frames. Uploads MUST become private, expiring drafts that no public route or export can reach. The owner MUST be able to set a focus point, a dim level (`auto` picks the lowest level that separates the NPC) and scaling, and then apply, cancel or remove. The preview and the published page MUST resolve the scene through the same server function, so equal settings render identically. The preview makes no provider call. Nothing public changes until the owner applies.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| FR-053 | (0.4.5, ADR-052) The admin MUST provide a 「維護」 page that shows local / gateway configured / externally verified status, the active bundle and the last backup time; creates a backup with the existing `runtime backup` primitive and offers it for download; restores from an uploaded backup only after confirmation and an automatic backup of the current state; pins a retained previous bundle through the existing pin primitive; stops the visitor gateway immediately; and explains how to update by running the newer installer and how to turn Funnel off in Tailscale's own flow. It never handles Tailscale credentials and shows nothing to visitors.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |

These extend FR-005–FR-014, FR-020, FR-038–FR-042 and NFR-001/002/003/008/009/011/013/014. Owner-only model guidance (device check against a RepoNPC-maintained `model_catalog.yml` graded suitable / marginal / not recommended using the public parameters-times-bits estimation method, a canirun.ai link without copying its data or calling its API, an Ollama helper with explicit pull, plain-language probe error mapping, a one-line active-model status, and a cloud data disclosure) extends FR-040 and is never shown to visitors; the readiness test and cost estimate are deferred. AC-062 through AC-071 are additional release gates. FR-050 (0.4.1, ADR-049) extends FR-015/FR-018/FR-047 and NFR-001/009/011; its gates are AC-072 and AC-073. FR-051 (0.4.2, ADR-050) extends FR-050; its gate is AC-074. FR-052 (0.4.3, ADR-050) extends FR-050/FR-018; its gate is AC-075. ADR-051 (0.4.4) revises FR-047 and FR-050–FR-052 without new FR or AC IDs; AC-068 and AC-072–AC-075 are revised accordingly. ADR-052 (0.4.5) adds FR-053 (gate AC-076) and closes repair items R11, R12-B and R08 through AC-077, AC-078 and AC-079.

### 2.11 Version 0.4.6 visitor gateway freeze (ADR-053)

For FR-047 and AC-071, the complete endpoint, body, response, error-code,
configuration, storage and lifecycle definitions in [A1/F0](A1_FUNNEL_GATEWAY_CONTRACT.md)
are normative. They supersede historical PUBLIC_BASE_URL-only admin-origin
binding and public model/usage disclosure on the gateway only. Existing local
public-response contracts remain compatible. Production private management
binds configured Origin/Referer to the exact request scheme and Host; its host
must differ from Pages and Funnel even across ports. New fields are
`REPONPC_ADMIN_ORIGINS`, `REPONPC_VISITOR_GATEWAY_PORT` and
`REPONPC_VISITOR_TRUSTED_PROXY_CIDRS`; the gateway defaults off and loopback-only. The owner may store a local
visitor port (1024–65535, not the application port) in the admin gateway form;
while stored it overrides `REPONPC_VISITOR_GATEWAY_PORT`. `PUT
/api/admin/visitor-gateway` treats an omitted `visitor_port` as keep, `null`
as clear to the environment default, and an integer as set (ADR-062).
Aggregate daily/provider/in-flight protection is the default identity mode;
verified trusted-proxy mode additionally enforces per-IP admission and fails
closed on invalid/missing identity. Exact visitor assets come from a validated
build manifest, with no admin dynamic chunk or SPA fallback. Only the configured
`https://<validlabel>.github.io` origin receives credential-free public API CORS.
Local usability, configured entry and dated owner-reported external check are
separate facts; restart/restore cannot reinstate external verification. A1
includes the opt-in Linux host-network Compose recipe and local checks. A5
Pages export/offline matching, A8 installer and A12 external acceptance remain
required and separate. No new provider, hosted dependency or automatic Funnel
operation is added.

## 3. Normative repository structure

Implementation MUST start with this structure. New directories are allowed when they preserve the module boundaries; moving or merging these boundaries requires an ADR update.

```text
RepoNPC/
├─ AGENTS.md
├─ README.md
├─ LICENSE
├─ pyproject.toml
├─ uv.lock
├─ package.json
├─ pnpm-lock.yaml
├─ pnpm-workspace.yaml
├─ reponpc.example.yml
├─ .env.example
├─ compose.yml
├─ Dockerfile
├─ apps/
│  └─ web/
│     ├─ index.html
│     ├─ package.json
│     ├─ vite.config.ts
│     └─ src/
│        ├─ app/
│        ├─ api/
│        ├─ features/admin/
│        ├─ features/card/
│        ├─ features/chat/
│        ├─ features/character/
│        ├─ features/profile/
│        ├─ i18n/
│        └─ test/
├─ src/reponpc/
│  ├─ api/                 # FastAPI routes, dependencies, headers, error mapping
│  ├─ admin/               # auth, sessions, CSRF, GitHub writeback
│  ├─ bundles/             # manifest polling, validation, atomic activation
│  ├─ cards/               # SVG/GIF/PNG generation and sanitization
│  ├─ chat/                # prompt assembly, policy validation, SSE orchestration
│  ├─ config/              # YAML and environment schemas
│  ├─ domain/              # evidence, citation, profile, common contracts
│  ├─ indexing/            # GitHub input, parsing, chunking, bundle builder CLI
│  ├─ providers/           # chat and embedding interfaces/adapters
│  ├─ retrieval/           # FTS, vectors, filters, RRF, context packing
│  ├─ runtime/             # runtime SQLite, budgets, rate limits, audit
│  ├─ observability/       # structured safe logging and metrics
│  └─ main.py
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ security/
│  ├─ contract/
│  └─ fixtures/repos/
├─ evals/
│  ├─ questions.yml
│  ├─ expected_evidence.yml
│  └─ README.md
├─ docs/
│  ├─ PROJECT_CONTEXT.md
│  ├─ TECHNICAL_SPEC.md
│  ├─ ACCEPTANCE_CRITERIA.md
│  ├─ DECISIONS.md
│  ├─ IMPLEMENTATION_PLAN.md
│  ├─ OPERATIONS.md
│  ├─ SECURITY.md
│  └─ SPRITE_FORMAT.md
└─ .github/workflows/
   ├─ ci.yml
   ├─ build-index.yml
   └─ release.yml
```

`OPERATIONS.md`, `SECURITY.md`, and `SPRITE_FORMAT.md` are implementation deliverables and MUST be complete before the relevant release gate. Their required content is defined in sections 15 and 16.

## 4. Configuration contract

### 4.1 Sources and precedence

- Public portfolio/index settings come from UTF-8 `reponpc.yml` in `REPONPC_CONFIG_REPOSITORY` at `REPONPC_CONFIG_BRANCH`. Under local publication (ADR-046), `REPONPC_CONFIG_REPOSITORY` and `REPONPC_INDEX_MANIFEST_URL` may be empty in either profile, and the runtime then does not poll (ADR-070).
- Runtime secrets and deployment-specific values come from environment variables, mounted secret files, or the protected deployment-local model connection store defined in section 11.5. Public YAML never contains connection credentials or private endpoints.
- Secrets MUST NOT be accepted in YAML.
- Environment variables MUST NOT override public semantic fields in ways that make the built bundle disagree with its manifest.
- Unknown YAML keys MUST fail validation unless a future schema version explicitly defines an extension namespace.

### 4.2 Root YAML shape

`schema_version` MUST equal integer `1`. The exact public structure is:

```yaml
schema_version: 1
locales:
  default: zh-TW
  supported: [zh-TW, en]
profile: {}
repositories: []
character: {}
card: {}
retrieval: {}
```

The normative populated example is `reponpc.example.yml`. Rules:

- Localized text is a mapping whose keys exactly match `locales.supported`.
- `profile.github_login` is required and confirmed by the owner; `profile.aliases` is optional. The guided editor prefills the login from the configuration repository owner when configured, otherwise from the entered GitHub account, and the owner can correct it before building.
- Missing localized required text is a validation error; fallback is allowed only for optional fields.
- Repository `slug` is `owner/name`; duplicates are invalid.
- Repository `ref` is optional. If omitted, the GitHub default branch is resolved at build time. A branch, tag, or SHA may be supplied, but the bundle always records the resolved full commit SHA.
- `include` and `exclude` use repository-relative gitignore-style patterns. Absolute paths and `..` are invalid.
- Owner claim IDs match `^[a-z][a-z0-9_-]{2,63}$` and are globally unique.
- Claim `kind` is `role`, `responsibility`, `achievement`, or `context`.
- Owner claims, localized profile headline/bio, and repository role/summary fields become `OWNER_ASSERTION` evidence sourced to the exact configuration commit and line range. Suggested questions and visual copy do not become evidence.
- A repository `role` is presentation shorthand; person-level answers SHOULD cite an explicit item in that repository's `claims` list rather than rely only on the shorthand.
- URLs MUST be absolute HTTPS, except `http://localhost` and private-network Ollama URLs are environment-only and never part of this YAML.
- `character.mode` is exactly `builtin` or `custom`.
- Built-in mode contains exactly `pack_id`, positive integer `pack_version`, and a bounded string-to-string `options` mapping. The trusted pack registry, not the core schema, defines required option names, allowed values, and rendering behavior.
- Character configuration contains no universal species field. Adding a built-in species or form means registering a new versioned pack; an unanticipated user-created species uses the canonical custom sheet without taxonomy changes.
- The legacy top-level built-in fields `body`, `skin`, `hair`, `outfit`, `hair_color`, `primary_color`, `secondary_color`, and `accessory` are invalid. Because no deployment consumed that draft contract, v1 provides no compatibility aliases or migration shim.
- A custom sprite path MUST be below `assets/character/`, must be a `.png`, and must satisfy section 12.
- (0.4.1, FR-050; 0.4.2–0.4.4, FR-051/052) Optional `character.scene` contains exactly these fields:
  - `color_scheme`: a registry id, default `neutral`;
  - `color_mode`: `system | light | dark`, default `system`;
  - `visitor_mode_toggle`: boolean, default `true`;
  - `accent`: null or `#rrggbb`;
  - `background_path`: null, or a `.png`/`.webp` directly below `assets/scene/`, shown only in the welcome hero;
  - `background_scaling`: `smooth` or `pixelated`, default `smooth`;
  - `background_focus`: `{x, y}` percentages 0–100, default 50/50;
  - `background_dim`: `auto | none | low | medium | high`, default `auto`.

  Omitting the block means `neutral`, `system`, the visitor toggle on and no overrides. An unknown `color_scheme` fails validation with the list of valid ids; a retired id resolves through the registry `aliases`. The unreleased 0.4.2 `template` key is rejected. The block has no species or free-form CSS field, and scene changes are versioned by `character.revision`.

- `card.revision` is a non-negative integer used for cache-busting snippets.
- Retrieval weights are non-negative finite numbers and at least one source weight must be positive.
- `embedding.model`, `embedding.dimension`, and `embedding.query_prefix` become part of the bundle compatibility contract. The descriptor is a public compatibility record only; provider endpoints, credentials, and profile registry state remain deployment-local. `embedding.adapter` MUST be one of the external bundle identities (`ollama` or `openai_compatible`); `vllm` is normalized to `openai_compatible` in the bundle. A local adapter value is permitted only in explicitly marked benchmark fixtures.

### 4.3 Default limits

| Setting                                    |                     Default |   Hard maximum |
| ------------------------------------------ | --------------------------: | -------------: |
| Configuration file                         |                     256 KiB |          1 MiB |
| Source file                                |                       2 MiB |         16 MiB |
| Indexed text per repository                |                     100 MiB |        500 MiB |
| Indexed text across corpus                 |                     250 MiB |          1 GiB |
| Evidence records/chunks                    |                     100,000 |        100,000 |
| Chunk characters                           |                       6,000 |         12,000 |
| Chunk lines                                |                         200 |            400 |
| Fallback overlap                           |                    12 lines |       40 lines |
| Public message                             | 2,000 Unicode scalar values |          4,000 |
| Supplied history                           |    6 messages / 6,000 chars |    10 / 12,000 |
| Retrieval candidates                       |              30 per channel |            100 |
| Final context records                      |                           8 |             20 |
| Total model context                        |    32,768 or provider limit | provider limit |
| Visitor chat output / synthetic chat probe |               16,384 tokens |         16,384 |
| Admin repository analysis output           |               16,384 tokens |         16,384 |
| Character upload                           |                       1 MiB |          2 MiB |
| Downloaded bundle                          |                     512 MiB |          1 GiB |

Configuration can lower defaults. Raising a value above a hard maximum requires source changes, an ADR, and new resource/security tests.

Under ADR-055, `REPONPC_ANALYSIS_MAX_OUTPUT_TOKENS` and `REPONPC_CHAT_MAX_OUTPUT_TOKENS` are independent positive integers, each defaulting to `16384` with a maximum of `16384`. Analysis governs both analysis execution paths; synthetic chat probes follow the selected chat capability. Explicit lower deployment values remain valid and are not silently upgraded. The selected analysis adapter must not inherit the visitor policy as its capability ceiling. The effective request respects any smaller provider capability. Full input messages, evidence delimiters/IDs, schema and framing headroom plus reserved output must fit the configured model context. Without safe input space, analysis fails before chat generation; it must not force a minimum input allowance or disable otherwise usable public/manual features at startup. Token counting without the actual model tokenizer is a documented conservative estimate, not measured usage. For Ollama, this generation ceiling includes reasoning and final-answer tokens together; it does not reserve a second answer-only allowance, require padding to the ceiling or promise a particular visible length. Context is a separate total capacity for input and generation, not the output setting.

Contribution suggestions retain their fixed 700-token policy independently of visitor and analysis request budgets. The adapter capability used by this internal operation MUST admit that policy when the configured provider and context permit it; lowering the analysis request budget MUST NOT silently clamp contribution suggestions. The service reserves the complete contribution messages, exact response schema, effective output allowance and framing margin before generation. Insufficient context fails before the provider call with the existing safe configuration error. A `length` termination or adapter output-limit diagnostic fails before JSON parsing with `PROVIDER_OUTPUT_LIMIT_REACHED`, even if the partial text is valid JSON; a complete but structurally invalid response uses `PROVIDER_OUTPUT_SCHEMA_INVALID`. Localized contribution role, summary, and claim strings also pass the locale/source writing-system check; an ungrounded writing-system word uses the same schema-invalid reason. Neither case retries, falls back, stores raw output or promotes partial content. An owner edit after confirmation creates a new unconfirmed proposal, and the browser applies an asynchronous result only while its request generation and original statement still match the active guided state.

## 5. Indexing contract

### 5.1 Allowed inputs

The indexer MUST access only:

- `reponpc.yml` and allowlisted character assets in the configuration repository;
- enabled public GitHub repositories named in the validated configuration;
- GitHub metadata required for repository name, description, topics, default branch, and resolved commit.

Every GitHub redirect and final host MUST remain on the configured GitHub host allowlist. The indexer MUST NOT fetch URLs found inside repository content.

### 5.2 Mandatory exclusions

The indexer MUST skip:

- Git submodules and symlinks;
- binary or undecodable files;
- `.env*`, credential/key/certificate files, `.git/`, dependency/vendor directories, build output, coverage, caches, generated documentation, minified assets, maps, archives, media, database files, and lock files;
- paths excluded by global rules or repository configuration;
- files that exceed configured limits;
- content matching a high-confidence secret detector.

A skipped-file summary records path, reason code, and size but MUST NOT record secret-like content. Secret scanning is defense in depth; owners remain responsible for public repository content.

### 5.3 Parsing and stable identifiers

- Supported Tree-sitter languages are Python, JavaScript, TypeScript/TSX, Go, and Rust.
- Complete named functions, methods, classes, structs, interfaces, traits, modules, and exported declarations SHOULD form chunks when within limits.
- Oversized syntax nodes are split on child boundaries, then bounded line windows.
- Unsupported text uses heading-aware sections for Markdown and line windows for other text.
- Every record stores exact one-based inclusive `start_line` and `end_line`.
- Evidence ID is `E_` plus the first 24 lowercase hexadecimal characters of SHA-256 over: `schema_version`, evidence class, repository slug, commit SHA, normalized POSIX path, line range, and normalized content hash.
- Explicit owner claims retain their stable YAML claim ID in `owner_claim_id`; they use the same content-addressed `E_...` evidence-ID format as every other indexed record.
- Line endings normalize to LF for hashing; displayed excerpts preserve safe text, not control characters.

### 5.4 Embeddings

**Amended 2026-09-26 (ADR-048, FR-049):** the production default for new portfolios is the built-in `builtin_onnx` profile serving `bge-m3` (ONNX Runtime on CPU, no PyTorch; official fp32 ONNX export, about 2.29 GB download, 1024 dimensions, no prompt prefix, 8192-token context, MIT). It is not bundled in the installer: the first time an index is needed, the owner explicitly chooses to download it (size, license and source shown; cancellable/resumable progress; pinned source and checksum verified before use), to configure `ollama`, `vllm` or `openai_compatible` instead, or to defer, in which case building stays blocked with an explanation. External embedding interfaces remain fully selectable. Third-party quantized uploads are not a trusted default source; the pinned artifact is the `onnx/` folder of `BAAI/bge-m3` at revision `5617a9f61b028005a4858fdac845db406aefb181` with per-file SHA-256 (ADR-052, contract §6.2). The bge-m3 retrieval quality is measured on the zh-TW/en fixtures before release. The local sentence-transformers adapter may remain in isolated benchmark/build fixtures only; it is not a runtime requirement. The previous "no RepoNPC-local production embedding default" rule is superseded.

The embedding profile registry is deployment-local mutable state and is independent from the chat profile. Each profile contains a stable local ID, provider kind, provider model ID, server-side endpoint/credential references, and the observed compatibility identity: dimension, normalized float32 behavior, query prefix, passage prefix, and provider/model version where available. Secret values and private endpoints are never serialized into public YAML, bundles, browser responses, logs, or snapshots.

The authenticated Web Admin MUST support profile create/read/update/delete, probe, and explicit activation. At most one profile may be active. A profile cannot be deleted or disabled while it is the only valid active profile. Probe MUST call the provider's model/embedding capability and a bounded sample embedding; a model-list response alone is insufficient. A profile is `ready` only when probe succeeds and its identity matches the active index bundle.

Changing provider, model identity, dimension, prefixes, normalization, or relevant provider semantics invalidates vector compatibility and MUST set `reindex_required`. Activation then follows `probe -> build/reindex -> validate -> smoke test -> atomic switch`; until the final switch, the prior profile/bundle remains the last-known-good service. Failed, cancelled, or timed-out reindex work MUST clean staging and leave the prior state active. RepoNPC MUST NOT silently select another profile/provider/model.

After explicit Ollama selection, its curated model catalog SHOULD include `qwen3-embedding:0.6b` as a recommendation, `BAAI/bge-m3` and `embeddinggemma:300m` as alternatives, and larger Qwen3-Embedding variants for hosts with more memory. This Ollama recommendation applies only when the owner chooses Ollama instead of the built-in default. Catalog metadata MUST include license, language/context notes, approximate resource requirements, and supported provider operations; the live probe remains authoritative for dimension and capability.

The initial catalog is intentionally small and uses provider/model IDs rather than pretending that every provider exposes the same inventory:

| Candidate                                                                                                        | Best fit                                                   | Upstream/provider notes                                                                                                                                  | RepoNPC operation                                                             |
| ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Ollama `qwen3-embedding:0.6b`                                                                                    | Recommended starter for a personal zh-TW/en/code portfolio | Qwen3-Embedding 0.6B, Apache-2.0; 32K context and up to 1024 dimensions upstream; Ollama publishes a roughly 639 MB quantized tag                        | Curated pull/list/probe/delete through Ollama-native APIs                     |
| Ollama `bge-m3`                                                                                                  | Strong multilingual and longer-document alternative        | BGE-M3, MIT; 100+ languages, 8K context, 1024 dimensions; Ollama publishes a roughly 1.2 GB tag                                                          | Curated pull/list/probe/delete through Ollama-native APIs                     |
| Ollama `embeddinggemma:300m`                                                                                     | Smaller-resource alternative                               | Google Gemma license/terms apply; 100+ languages and a 2K Ollama context tag; verify license acceptance and probe identity before activation             | Curated pull/list/probe/delete through Ollama-native APIs                     |
| Ollama `qwen3-embedding:4b` or `:8b`                                                                             | Quality/recall experiments on capable hardware             | Larger Qwen3 variants trade memory and latency for quality; exact quantization, dimension, and resource cost are provider-tag dependent                  | Curated pull/list/probe/delete only after an allowlisted catalog entry exists |
| vLLM or generic OpenAI-compatible model ID                                                                       | Operators already serving an embedding endpoint            | The operator may serve Qwen3, BGE-M3, EmbeddingGemma, or another licensed model through `/v1/embeddings`; model installation stays on that provider host | Connect/list/probe/select; no RepoNPC download                                |
| Hosted OpenAI-compatible API (for example, a gateway exposing `text-embedding-3-small`/`text-embedding-3-large`) | No local model lifecycle desired                           | Availability, pricing, retention, dimensions, and terms belong to the selected provider; the model ID is not guaranteed across gateways                  | Connect/list/probe/select; no RepoNPC download                                |

The Qwen3 0.6B, BGE-M3, and EmbeddingGemma dimensions/context values above are catalog hints, not bundle contracts. A sample establishes actual dimension and finite-vector behavior. Query/passage prefixes, task instructions, pooling, and model revision cannot in general be inferred from one vector; they come from a reviewed model preset or explicit advanced settings and are recorded with the observed identity. Never apply the E5 `query: ` / `passage: ` defaults to every model. Normalization is the explicit RepoNPC adapter contract and is validated at build/runtime. A structurally successful sample does not prove retrieval quality; AC-009 remains required.

RepoNPC MUST provide a provider-aware **model center**, not a generic download area. For Ollama, a curated model ID may be pulled, monitored, cancelled, and deleted by calling Ollama on the configured private host. For vLLM and generic APIs, the owner follows the provider's own installation/serving process and then enters or selects the served model ID. The browser never receives a provider key and RepoNPC never accepts arbitrary URLs, local paths, shell commands, or unverified archives. This boundary prevents SSRF, supply-chain substitution, license ambiguity, and accidental disk/CPU exhaustion while still making the common Ollama path self-service.

Model lifecycle is provider-owned. For Ollama, the Web Admin MAY expose a curated catalog, installed-model list, pull/progress/cancel, and delete through Ollama-native endpoints. For vLLM and generic OpenAI-compatible services, the Web Admin exposes connect/list/probe/select only; operators install or serve models on those hosts. RepoNPC MUST NOT implement an arbitrary URL/local-path model downloader or execute provider-supplied installation commands.

Index and runtime query embeddings MUST use the same profile identity and semantics. Embedding credentials remain in protected server-side storage on the host that performs the operation; an index builder receives an explicit frozen profile snapshot plus independently provisioned secrets. A successful runtime probe does not prove that a GitHub Actions runner can reach a private provider. Section 11.5 does not change the publication topology.

### 5.5 Executable CLI

The installed `reponpc` console entrypoint has the following bounded commands:

```text
reponpc
reponpc serve
reponpc admin launch-token [--data-dir <directory>]
reponpc admin setup-code [--data-dir <directory>]
reponpc admin set-password [--data-dir <directory>] [--username <owner>]
reponpc admin hash-password
reponpc runtime check [--data-dir <directory>]
reponpc runtime backup <path> [--data-dir <directory>]
reponpc bundle status [--data-dir <directory>]
reponpc bundle verify <bundle-id> [--data-dir <directory>]
reponpc bundle pin <bundle-id> [--data-dir <directory>]
reponpc bundle unpin [--data-dir <directory>]
reponpc config validate <path>
reponpc index build --config <path> --output <directory>
reponpc index publish --bundle-dir <directory>
reponpc index publish-manifest --bundle-dir <directory>
```

- No arguments and `serve` MUST enter the same validated FastAPI/Uvicorn startup path.
- `admin launch-token` MUST work only for a fully validated `loopback_evaluation` configuration, replace any unused prior grant, store only a SHA-256 digest with a two-minute expiry, and print one URL whose secret is confined to the `#local-launch=` fragment. It MUST fail for production, non-loopback, or trusted-proxy configurations. The local launcher invokes it automatically after readiness.
- `admin setup-code` MUST initialize the selected runtime database, replace any unused prior code, store only a SHA-256 digest with a 15-minute expiry, print the new 256-bit code once, and fail safely after a durable owner exists.
- `admin hash-password` remains an OPTIONAL pre-provisioning/legacy command and MUST print only a PHC-format Argon2id hash after non-echoing confirmation.
- `admin set-password` is host-only production recovery. It discovers or accepts the sole owner explicitly, creates or updates only the local Argon2id hash, applies the production password policy, and never reopens setup or changes GitHub credentials.
- `runtime check` verifies runtime SQLite integrity, schema, permissions, and active/previous bundle pointers without printing secrets. `runtime backup` uses an online-consistent SQLite backup (or a documented stopped-process fallback), refuses ambiguous/broad paths, and never includes provider bodies or raw session tokens.
- `bundle status`, `bundle verify`, `bundle pin`, and `bundle unpin` inspect or change only local bundle state. Verification performs checksum/schema/model/dimension/database/smoke checks; pin/unpin is atomic and preserves the active last-known-good bundle on failure.
- Embedding profile CRUD/model pull is intentionally Web Admin functionality; the CLI does not duplicate interactive provider management.
- Help, configuration validation, and index commands MUST NOT start the server or require unrelated deployment settings.
- `index build` MUST resolve exact public repository commits, use the configured production embedding adapter, build/verify the index and bundle, generate `public/profile.json`, and fail closed if the required non-profile public assets are missing or invalid. Until the Phase 4 card/character producer is integrated, those assets are supplied from the command's documented `public/` input directory; the CLI MUST NOT fabricate production placeholder assets.
- `index publish` MUST create, upload, and verify the immutable Release asset, then write only a local pending stable-manifest artifact below the bundle directory. It MUST NOT mutate the remote stable manifest.
- `index publish-manifest` MUST accept only that verified pending artifact and perform the sole remote `stable-manifest.json` update.
- Every command MUST return a nonzero exit with a stable safe message on failure and MUST NOT print credentials, upstream bodies, or raw rejected configuration.

## 6. Index database schema

`index.sqlite` is built once, integrity-checked, then opened read-only by the application. Schema version `1` contains at least these logical tables (additional indexes are allowed):

```sql
CREATE TABLE bundle_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE repositories (
  repo_id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  commit_sha TEXT NOT NULL CHECK(length(commit_sha) = 40),
  default_branch TEXT,
  github_html_url TEXT NOT NULL,
  summary_zh_tw TEXT,
  summary_en TEXT
);

CREATE TABLE sources (
  source_id INTEGER PRIMARY KEY,
  repo_id INTEGER NOT NULL REFERENCES repositories(repo_id),
  path TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  language TEXT,
  source_type TEXT NOT NULL,
  UNIQUE(repo_id, path, content_sha256)
);

CREATE TABLE evidence (
  evidence_id TEXT PRIMARY KEY,
  evidence_class TEXT NOT NULL CHECK(evidence_class IN
    ('OWNER_ASSERTION','REPOSITORY_FACT','PARTICIPATION','MODEL_INFERENCE')),
  source_id INTEGER NOT NULL REFERENCES sources(source_id),
  owner_claim_id TEXT,
  title TEXT,
  symbol TEXT,
  content TEXT NOT NULL,
  start_line INTEGER NOT NULL CHECK(start_line >= 1),
  end_line INTEGER NOT NULL CHECK(end_line >= start_line),
  language TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE VIRTUAL TABLE evidence_fts_terms USING fts5(
  evidence_id UNINDEXED, title, symbol, path, content,
  tokenize='unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE evidence_fts_trigram USING fts5(
  evidence_id UNINDEXED, title, symbol, path, content,
  tokenize='trigram'
);

CREATE TABLE embeddings (
  evidence_id TEXT PRIMARY KEY REFERENCES evidence(evidence_id),
  model_id TEXT NOT NULL,
  dimension INTEGER NOT NULL,
  normalized INTEGER NOT NULL CHECK(normalized = 1),
  vector_f32_le BLOB NOT NULL
);
```

`MODEL_INFERENCE` rows are optional derived portfolio summaries created during indexing. They MUST list supporting immutable evidence IDs in `metadata_json`. Runtime answer inferences are ephemeral and follow the same dependency rule but are not written into the immutable database.

The lexical search channel combines ranks from the term and trigram tables. Queries shorter than three characters MAY use a bounded exact `instr` fallback. It MUST treat user text as values and generate only allowlisted FTS syntax; raw user query syntax is forbidden.

## 7. Retrieval and context contract

1. Normalize the question for locale without translating code symbols, paths, or product names.
2. Apply explicit filters only when confidently extracted (repository, language, evidence class, source type).
3. Retrieve the configured candidate count independently from lexical and vector channels.
4. Within the lexical channel, fuse term and trigram ranks. Across lexical and vector channels, use RRF score `sum(weight_c / (k + rank_c))`, with default `k=60`, lexical weight `1.0`, vector weight `1.0`.
5. Add configured source/evidence weights after ranking as documented multipliers. Owner assertions do not receive an unconditional global relevance boost.
6. Deduplicate identical/overlapping ranges and cap any one repository at six of the final eight records unless the question names that repository.
7. Pack records in rank order within the smaller of the configured and provider context budget.
8. Delimit each record with an assigned request-local source ID (`S1`, `S2`, ...) plus evidence class and metadata. Clearly state that record text is data, not instruction.

Model-visible records carry only request-local IDs, and the output schema restricts `source_ids` to those IDs (ADR-063).

Search results and logs use persistent evidence IDs. The model sees only request-local IDs.

## 8. Answer and citation policy

### 8.1 Model output contract

**Envelope v2 (0.4.0, ADR-048, FR-043):** the provider is instructed to produce typed segments instead of free `answer_markdown`:

```json
{
  "segments": [
    { "kind": "person", "text": "{{owner}} ...", "source_ids": ["S1"] },
    { "kind": "participation", "text": "{{owner}} ...", "source_ids": ["S4"] },
    { "kind": "project", "text": "...", "source_ids": ["S2", "S3"] },
    { "kind": "inference", "text": "...", "source_ids": ["S2"] }
  ],
  "insufficient_evidence": false
}
```

`kind` is the closed set shown. `{{owner}}` is the only permitted reference to the portfolio owner and is rendered by the backend. Citation markers are rendered by the backend from `source_ids`. Only envelope v2 is accepted; v1 is rejected. Answers are not persisted, so no stored-answer migration is required.

Native structured output is used when supported; otherwise RepoNPC parses a constrained text envelope. Validation does not regenerate on failure (FR-044). The model MUST NOT output source URLs. Markdown is sanitized and only a conservative display subset is rendered. Validation and rendering preserve model text except for the explicit `{{owner}}` anchor, backend labels and citations; pronouns are never rewritten. Singular person references still reclassify project/inference segments as `person`, which must contain `{{owner}}`. Collective project wording (we/our/us/they/them/their/我們/他們) alone does not trigger reclassification.

### 8.2 Validation before public delivery

The backend MUST buffer the complete provider result before releasing answer text to the public stream. It then:

- rejects unknown or unselected source IDs;
- removes model-authored links presented as citations;
- requires every material factual claim to carry one or more known source markers;
- applies the per-segment rules of FR-043: `person` segments cite at least one `OWNER_ASSERTION`, may paraphrase it, and pass the inflation lexicon and numeric-fact check; `participation` segments cite `PARTICIPATION` and assert no role; `project` segments cite repository evidence and are reclassified as `person` when the identity registry or person-reference data detects the owner; a personal role, responsibility or achievement is never derived from code or participation evidence;
- drops a failing segment silently, recording an owner-only reason code, while keeping valid segments;
- requires every inference to cite supporting non-inference evidence;
- converts selected IDs into immutable citation objects;
- rejects the whole answer for envelope-level integrity failures (schema, model-authored URL/HTML, unknown or unselected source ID, inference cycle) and, like an answer with no valid segment or `insufficient_evidence=true`, returns the localized no-match reply classified by ADR-066 (FR-044) without regenerating; only no_content offers available sanitized suggested questions.

The legacy whole-answer abstention and the rule that any person keyword without a matching owner assertion rejects the entire answer are superseded by ADR-048.

After validation, the service emits answer text in SSE `token` chunks. This preserves the streaming UI contract without exposing unvalidated partial claims.

For no_content, ADR-065 (owner-approved 2026-10-19) selects copy from the final sanitized suggestion tuple. With suggestions, keep zh-TW 「這個問題我在作品集裡找不到相關內容，可以試試下面這些問題。」 and en "I couldn't find anything about that in this portfolio. Try one of these questions." Without suggestions, use zh-TW 「這個問題我在作品集裡找不到相關內容。」 and en "I couldn't find anything about that in this portfolio." Offline approved-FAQ matching likewise retains its existing suggestion copy only when questions are shown, otherwise uses 「這個問題沒有足夠接近的已核准問答。」 / "No approved answer is close enough to this question." Owner-only `no_match_reason`, citations and validation remain unchanged; no_content retains the configured contact link. ADR-066 (owner-approved 2026-10-19) classifies every reason in answers.py: MODEL_INSUFFICIENT_EVIDENCE, NO_EVIDENCE_SELECTED and ALL_SEGMENTS_DROPPED are no_content; ENVELOPE_SCHEMA_INVALID, SOURCE_ID_UNKNOWN, MODEL_AUTHORED_MARKUP, INFERENCE_CYCLE, SELECTED_MAP_INVALID and VALIDATION_UNEXPECTED are temporary. Temporary uses zh-TW 「這次沒能整理出可靠的回答，請再問一次。」 / en "I couldn't put together a reliable answer this time. Please ask again." with empty suggestions and no contact link. Both kinds keep insufficient_evidence=true and empty citations. There is no automatic validation retry.

### 8.3 Immutable GitHub permalink

For GitHub.com, the server constructs:

```text
https://github.com/{owner}/{repo}/blob/{40-char-commit}/{percent-encoded-path}#L{start}-L{end}
```

Owner assertion citations point to `reponpc.yml` in the configuration repository at its indexed commit. Repository slug, host, commit, path, and lines come only from validated index records. A single-line citation uses `#L{start}`.

## 9. Public HTTP API

All JSON is UTF-8. `/api/public/*` responses set `Cache-Control: no-store` except card/profile resources with explicit validators. Every response carries `X-Request-ID`. Clients MAY send an opaque UUID in `X-Request-ID`; invalid values are replaced.

### 9.1 `GET /api/public/profile`

Query: optional `locale=zh-TW|en`; default is configured locale.

Success `200`:

```json
{
  "schema_version": 1,
  "locale": "zh-TW",
  "profile": {
    "display_name": "Example Developer",
    "headline": "...",
    "bio": "...",
    "greeting": "歡迎探索我的作品集。",
    "location": null,
    "avatar_url": null,
    "links": [{ "label": "GitHub", "url": "https://github.com/example" }]
  },
  "repositories": [
    {
      "slug": "example/project",
      "summary": "...",
      "role": "...",
      "tags": ["Python"],
      "demo_url": null,
      "language": null,
      "stars": null,
      "forks": null
    }
  ],
  "suggested_questions": ["這個專案解決什麼問題？"],
  "character": {
    "mode": "builtin",
    "asset_url": "/api/public/character.png",
    "revision": 1,
    "frame_duration_ms": 160,
    "movement": "subtle",
    "scene": {
      "revision": 1,
      "scheme": { "id": "neutral", "version": 1 },
      "color_mode": "system",
      "visitor_mode_toggle": true,
      "themes": {
        "light": { "background": "#rrggbb", "...": "#rrggbb" },
        "dark": { "...": "#rrggbb" }
      },
      "background_url": null,
      "background_scaling": "smooth",
      "background_focus": { "x": 50, "y": 50 },
      "background_dim": "auto"
    }
  },
  "index": { "version": "...", "built_at": "...", "repository_count": 1 }
}
```

The endpoint returns `503 INDEX_UNAVAILABLE` before first bundle activation. It uses an ETag derived from bundle version and locale.

A5's approved project sidebar receives `language`, `stars` and `forks` as
nullable snapshot metadata from the existing public repository GET during the
build. Language is bounded to 100 characters; counts are integers from zero
through 2,147,483,647. Missing/invalid upstream values remain null; legacy bundles
may omit these additive fields. Both locales carry equal metadata. Visitor
rendering never fetches live GitHub counts or treats missing values as zero.

The immutable bundle stores one internal `public/profile.json` with this schema-v1 shape:

```json
{
  "schema_version": 1,
  "locales": {
    "zh-TW": {
      "profile": {},
      "repositories": [],
      "suggested_questions": []
    },
    "en": {
      "profile": {},
      "repositories": [],
      "suggested_questions": []
    }
  },
  "character": {},
  "index": {}
}
```

The locale keys MUST be exactly `zh-TW` and `en`; both locale objects MUST contain every field needed for the public response, including the localized `profile.greeting`. Character metadata MUST include the configured `frame_duration_ms` (80–1000 ms) and `movement` (`none` or `subtle`). The bundle producer derives these values from the validated configuration and built index metadata. The verifier validates both locales before activation. The route selects only the requested locale and constructs the response with `locale` added at the top level. Missing or invalid locale data fails closed; the route MUST NOT cross-fallback to the other required locale.

### 9.2 `POST /api/public/chat/stream`

Request content type is `application/json`:

```json
{
  "message": "請介紹你最有代表性的專案",
  "locale": "zh-TW",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

`history` is optional, must alternate roles starting with `user`, and is treated as untrusted conversational context. The client sends it on each request; the server does not persist it by default.

If validation/rate/readiness fails before streaming, the endpoint returns a normal JSON error. Once accepted, it returns `200 text/event-stream`, `Cache-Control: no-store`, `Connection: keep-alive`, and `X-Accel-Buffering: no`.

Optional `progress` events defined by ADR-057 may precede validated delivery.
They contain only `stage` and `elapsed_ms`, never model text. Terminal `complete`
adds nonnegative `elapsed_ms` for accepted-handler work.
Events for validated answer delivery, in required order:

```text
event: metadata
data: {"request_id":"...","index_version":"...","locale":"zh-TW","evidence_count":8}

event: token
data: {"delta":"..."}

event: citations
data: {"items":[{"id":"S1","evidence_id":"E_...","evidence_class":"REPOSITORY_FACT","repository":"owner/repo","commit_sha":"...","path":"src/app.py","start_line":10,"end_line":24,"title":"...","excerpt":"...","url":"https://github.com/..."}]}

event: complete
data: {"finish_reason":"stop","usage":{"input_tokens":1234,"output_tokens":321},"insufficient_evidence":false}
```

- There is exactly one `metadata`, zero or more `token`, at most one `citations`, and exactly one terminal `complete` on success.
- A failure after SSE starts emits exactly one terminal `error` event with the common error body and closes the stream; it does not emit `complete`.
- Keepalive comments (`: keepalive`) MAY occur at least every 15 seconds and carry no semantics.
- `usage` fields are nullable when the provider does not report them.
- Only when `insufficient_evidence=true`, `complete` includes `no_match_kind: "no_content" | "temporary"` and `suggested_questions`; temporary has an empty list and omits `contact_link`. Answered payloads are unchanged. Only the coarse kind is public; raw `no_match_reason` and reason codes never appear in SSE. The visitor gateway passes the kind through to local and Pages visitors (ADR-066).

### 9.3 Card and character endpoints

- `GET /api/public/card.svg?theme=light|dark&locale=zh-TW|en&rev=N`
- `GET /api/public/card.gif?theme=light|dark&locale=zh-TW|en&rev=N`
- `GET /api/public/card.png?theme=light|dark&locale=zh-TW|en&rev=N`
- `GET /api/public/character.png?rev=N`
- `GET /api/public/scene-background?rev=N` (0.4.1, FR-050): the validated, re-encoded owner welcome-hero image (0.4.4). It never serves drafts (FR-052). Returns 404 when none is configured. It sends `X-Content-Type-Options: nosniff` and the same ETag rules. Scene tokens are part of the profile payload; no endpoint accepts CSS.

Unsupported query values return `400 VALIDATION_ERROR`. Outputs use an ETag including bundle version, variant, and revision. SVG response headers include `Content-Type: image/svg+xml`, `X-Content-Type-Options: nosniff`, and a restrictive `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src data:`. SVG contains no scripts, event handlers, foreign objects, or external URLs.

### 9.4 Status and health

`GET /api/public/status` returns `200` even when degraded:

```json
{
  "status": "ready|setup_required|degraded|offline",
  "index": {
    "ready": true,
    "version": "...",
    "last_checked_at": "...",
    "update_error": null
  },
  "model": { "ready": true, "provider": "ollama", "last_checked_at": "..." },
  "chat_available": true
}
```

Sensitive provider URLs, model credentials, stack traces, filesystem paths, and admin state are excluded.

- `GET /healthz` returns `200` when the process event loop responds.
- `GET /readyz` returns `200` only when a valid index is active, runtime storage is usable, and the configured chat/embedding contracts are compatible; otherwise `503`.

### 9.5 Authenticated analysis-batch API (0.1.7)

The following same-origin authenticated admin endpoints set `Cache-Control: no-store`. Creation and every state change require the current CSRF token. Snapshot payloads contain safe metadata, normalized validated results, aggregate counts, rate/capacity status, and server-assigned IDs only; they never contain credentials, archive bytes, repository bodies, prompts, provider bodies, staging paths, or incomplete output.

| Method and path                                                                          | Contract                                                                                                                                                                                                                                                                                       |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `POST /api/admin/onboarding/analysis-batches/preflight`                                  | Validates one explicit confirmed public selection (1–50 repositories), resolves eligible immutable commits through bounded unauthenticated REST, predicts cache use/capacity, and creates a short-lived selection-bound `plan_id`.                                                             |
| `POST /api/admin/onboarding/analysis-batches`                                            | Requires a valid `plan_id` and opaque idempotency key; creates or returns the one owner-scoped active batch.                                                                                                                                                                                   |
| `GET /api/admin/onboarding/analysis-batches/active`                                      | Returns the active safe snapshot with `recovery=false`; otherwise (0.4.5, ADR-052) the newest terminal batch that still allows retry or reanalyze, finished within 7 days and is not owner-dismissed, with `recovery=true`; otherwise `404 NOT_FOUND`. The dismissal is persisted server-side. |
| `GET /api/admin/onboarding/analysis-batches/{id}`                                        | Returns a safe snapshot for the requesting owner only.                                                                                                                                                                                                                                         |
| `GET /api/admin/onboarding/analysis-batches/{id}/events`                                 | Streams ordered SSE events with monotonically increasing numeric event IDs and supports `Last-Event-ID` replay. Snapshot reconciliation is authoritative if an event was pruned.                                                                                                               |
| `POST /api/admin/onboarding/analysis-batches/{id}/pause`, `/resume`, `/cancel`, `/retry` | Performs the named idempotent state transition. Retry may resume only retryable items and MUST require explicit confirmation for an interrupted generation.                                                                                                                                    |
| `POST /api/admin/onboarding/analysis-batches/{id}/dismiss`                               | Requires the owner session, same origin and CSRF token; idempotently hides one still-actionable terminal recovery from the active lookup and returns `{"dismissed":true}`. It does not delete results or prevent explicit access by ID.                                                        |
| `POST /api/admin/onboarding/analysis-batches/{id}/reanalyze`                             | Creates or returns one idempotent successor batch for explicitly selected failed item IDs. The request supplies `item_ids`, `idempotency_key`, `model_selection=frozen                                                                                                                         | current`, `confirm_model_change`, and, for `current`, `expected_selection_generation`. Source commits/policies and prior terminal records are immutable; `current` may replace the frozen pair only when the confirmed generation still matches. |

Batch state is `queued -> running <-> paused -> cancelling -> cancelled|completed|completed_with_errors|failed`. An item reports the safe stage `queued`, `resolving_commit`, `fetching_source`, `filtering`, `indexing`, `embedding`, `generating`, `validating`, `cleaning_up`, or `complete`, or an explicit terminal/waiting reason. The old one-repository analysis endpoint remains a compatibility adapter: it creates a one-item batch, waits only for its terminal snapshot within its existing request deadline, and returns the prior safe result shape rather than bypassing batch policy.

Snapshots expose `source_batch_id`, `analysis_round`, per-item `source_item_id`, terminal `failure_stage`, same-round `retryable`, successor-round `reanalyzable`, and a closed retry blocker (`ATTEMPTS_EXHAUSTED`, `EXECUTION_BUDGET_EXHAUSTED`, or `SUCCESSOR_EXISTS`) when applicable. The persisted `maximum_generation_attempts` and per-item `execution_budget_seconds` remain the historical limits for that round; separate `recovery_maximum_generation_attempts` and `recovery_execution_budget_seconds` report the currently effective policy used by retry admission. `retryable` and the mutation guard use that same effective state/attempt/time/successor predicate. Reserving each provider generation attempt is atomic and cannot exceed the batch maximum after restart or an explicit retry. Terminal transitions settle and clear the active clock so later reads cannot increase elapsed time. Once a source item has a successor it cannot return to same-round retry even if deployment limits later increase or the successor's full result has expired. Every accepted reanalysis idempotency key, including a second key that deduplicates to an existing successor, remains bound to the complete request identity for the lifetime of that successor result.

Each failed item snapshot retains its stable `error_code` plus an optional closed-set `error_reason`. Allowed reasons are `NO_ELIGIBLE_CONTENT`, `PROVIDER_OUTPUT_SCHEMA_INVALID`, `PROVIDER_EVIDENCE_ID_INVALID`, `PROVIDER_PERSONAL_INFERENCE_REJECTED`, and `PROVIDER_OUTPUT_LIMIT_REACHED`. They describe only application-owned checks; provider bodies, prompts, arbitrary exception text, request IDs, URLs, paths, and credentials remain prohibited. Runtime migration 23 introduced the nullable reason; migration 24 transactionally extends its allowlist for output-limit termination while preserving existing items/results/events and constraints. Unknown reasons are discarded, and the frontend renders only allowlisted codes/reasons with bilingual recovery text.

## 10. Common error contract

JSON failures use:

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Localized safe message",
    "request_id": "...",
    "details": {},
    "retry_after_seconds": 30
  }
}
```

`details` contains field-level validation data only and never internal exceptions. Required stable codes:

| HTTP | Code                                                                             | Meaning                                                                                                                            |
| ---: | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
|  400 | `VALIDATION_ERROR`                                                               | Body/query/config value invalid.                                                                                                   |
|  401 | `AUTHENTICATION_REQUIRED` / `INVALID_CREDENTIALS`                                | Admin authentication failed or missing.                                                                                            |
|  401 | `LOCAL_LAUNCH_DENIED`                                                            | Local-launch grant or loopback boundary is absent, invalid, expired, replayed, or unsafe.                                          |
|  401 | `SETUP_DENIED`                                                                   | First-owner code is absent, invalid, expired, or submitted with mismatched owner fields.                                           |
|  403 | `CSRF_FAILED` / `WRITE_NOT_ALLOWED`                                              | Security policy rejected the operation.                                                                                            |
|  404 | `NOT_FOUND`                                                                      | Allowlisted resource does not exist.                                                                                               |
|  409 | `CONFIG_CONFLICT`                                                                | Expected Git blob SHA no longer matches.                                                                                           |
|  409 | `SETUP_ALREADY_COMPLETE`                                                         | A durable or explicitly pre-provisioned owner already closes first-owner setup.                                                    |
|  410 | `GITHUB_LOGIN_REMOVED`                                                           | A retired GitHub login/setup route was called; connect GitHub from an authenticated settings session.                              |
|  409 | `ANALYSIS_BATCH_ACTIVE` / `ANALYSIS_PLAN_STALE`                                  | Another owner batch is active, or the selection-bound preflight plan expired or no longer matches.                                 |
|  409 | `ANALYSIS_IDEMPOTENCY_CONFLICT`                                                  | A previously accepted opaque key is replayed with different plan, selection, model-confirmation, or selection-generation identity. |
|  409 | `ANALYSIS_RETRY_NOT_AVAILABLE` / `ANALYSIS_REANALYZE_NOT_AVAILABLE`              | No item is eligible for the requested same-round retry or successor analysis round.                                                |
|  409 | `ANALYSIS_SOURCE_BATCH_NOT_TERMINAL` / `ANALYSIS_REANALYZE_ITEM_INVALID`         | Reanalysis source state or selected item IDs do not satisfy the successor-round contract.                                          |
|  409 | `ANALYSIS_SOURCE_STATE_CHANGED` / `ANALYSIS_SUCCESSOR_CONFLICT`                  | The failed source changed during admission, or a successor already consumes one of the selected source items.                      |
|  409 | `ANALYSIS_MODEL_SELECTION_STALE`                                                 | The current analysis-selection generation no longer matches the version explicitly confirmed by the owner.                         |
|  409 | `ANALYSIS_GENERATION_ATTEMPTS_EXHAUSTED` / `ANALYSIS_EXECUTION_BUDGET_EXHAUSTED` | The same-round retry ceiling is exhausted; an eligible terminal failed item may use the explicit successor-round operation.        |
|  409 | `ANALYSIS_MODEL_CHANGE_CONFIRMATION_REQUIRED`                                    | Reanalysis requested the current pair and it differs from the source pair without explicit confirmation.                           |
|  413 | `PAYLOAD_TOO_LARGE`                                                              | Config, question, or asset limit exceeded.                                                                                         |
|  422 | `CONFIG_INVALID` / `ASSET_INVALID`                                               | Structurally valid request fails domain validation.                                                                                |
|  429 | `RATE_LIMITED` / `DAILY_BUDGET_EXHAUSTED` / `CONCURRENCY_LIMIT`                  | Cost/abuse limit reached.                                                                                                          |
|  429 | `GITHUB_RATE_LIMITED`                                                            | GitHub primary or secondary rate budget requires admission to wait; safe retry metadata is supplied when known.                    |
|  502 | `REQUEST_FAILED` / `PROVIDER_ERROR` / `GITHUB_ERROR`                             | Chat uses the generic REQUEST_FAILED; other upstream operations retain their existing safe codes.                                  |
|  503 | `INDEX_UNAVAILABLE` / `MODEL_UNAVAILABLE` / `SERVICE_NOT_READY`                  | Required capability unavailable.                                                                                                   |
|  504 | `REQUEST_TIMEOUT` / `PROVIDER_TIMEOUT`                                           | Chat uses generic REQUEST_TIMEOUT (terminal SSE after headers); other model operations retain PROVIDER_TIMEOUT.                    |

Portfolio job failures are returned in the status body's `error_code` (HTTP 200 for status/cancel, HTTP 202 for an accepted prepare), rather than as a new HTTP error envelope (ADR-068):

| HTTP | Code | Meaning in portfolio status `error_code` |
| ---: | --- | --- |
| 200 | `GITHUB_RATE_LIMITED` | GitHub admission or quota limit; `retry_at` reports the known UTC retry time. |
| 200 | `GITHUB_ERROR` | GitHub source request failed temporarily. |
| 200 | `GITHUB_TIMEOUT` | GitHub source operation timed out. |
| 200 | `NOT_FOUND` | The selected public repository/ref was not found or is inaccessible. |
| 200 | `ARCHIVED_NOT_ALLOWED` | The selected repository is archived and disallowed by the existing policy. |
| 200 | `ARCHIVE_TOO_LARGE` | The source archive exceeds an existing resource bound. |
| 200 | `ARCHIVE_INVALID` | The source archive is invalid. |
| 200 | `ARCHIVE_UNSAFE` | The source archive failed existing safety validation. |

`GITHUB_RATE_LIMITED` is a safe recoverable result when anonymous REST capacity is exhausted. It includes only a sanitized retry time, never triggers credential collection or writeback-token fallback, and leaves manual continuation available.

## 11. Admin contract

### 11.1 Authentication

- A new deployment starts with no product default username or password. `GET /api/admin/auth/methods` reports the configured access mode without exposing owner or credential state.
- In `loopback_evaluation`, the launcher creates a random 256-bit grant only after the server is ready. Runtime SQLite stores only its SHA-256 digest and two-minute expiry; reissuing invalidates the prior unused grant. The browser URL uses `/admin#local-launch=<grant>` so the secret is not sent in the HTTP request, Referer header, or server access log.
- The frontend reads the fragment once, immediately calls same-origin `POST /api/admin/session/local-launch`, and clears the fragment with `history.replaceState` before rendering external links. Grant consumption, creation/reuse of the sole owner, session issuance, and invalidation of competing unused grants are one transaction. Concurrent exchanges create exactly one owner and at most one successful session per grant.
- The server accepts local launch only when the deployment profile, configured bind, public base URL, request peer, `Host`, and origin are loopback-valid and trusted-proxy interpretation is disabled. It treats forwarded headers as untrusted in this mode. Invalid, expired, replayed, cross-origin, forwarded, and non-loopback exchanges return the same safe failure.
- A loopback browser with neither a valid session nor a launch grant receives no registration or password/GitHub login form. It sees one localized action telling it to reopen RepoNPC with the local launcher.
- In `production`, `GET /api/admin/setup` reports only whether password setup is required and whether an unexpired code is available. The host operator runs `reponpc admin setup-code` to create a random 256-bit code valid for 15 minutes. Runtime SQLite stores only its SHA-256 digest; reissuing invalidates the prior unused code.
- The production first-owner request supplies the code, a trimmed 1–64 character username, and a 15–128-character password plus confirmation. No character composition rule is imposed, but new values are checked against the common/compromised-password blocklist. Code consumption, Argon2id hash storage, setup deletion, and initial session creation are atomic. After an owner exists, production setup is permanently unavailable and later visits receive the password sign-in surface.
- For explicit pre-provisioning/backward compatibility, operators MAY set `REPONPC_ADMIN_USERNAME` and a PHC-format `REPONPC_ADMIN_PASSWORD_HASH` generated by `reponpc admin hash-password`. This mode disables first-owner setup.
- A GitHub OAuth App or public-read PAT is neither required nor supported. Owner sessions and local/manual work remain independent; anonymous GitHub capacity affects only discovery/analysis and returns a retryable bounded state.
- Production password login uses a generic failure message and exponential per-IP/account backoff. Local-launch failure is generic and rate-limited independently.
- Successful password or local-launch exchange creates a random 256-bit server-side session and sets `__Host-reponpc_session` with `Secure`, `HttpOnly`, `Path=/`, and `SameSite=Strict`.
- When the launch fragment is absent, the frontend calls strict same-origin `POST /api/admin/session/resume` before showing access recovery. The endpoint accepts no body or grant, validates the existing HttpOnly cookie under the normal session plus host/origin/private-admin boundary, and returns only `{csrf_token,expires_at,absolute_expires_at}` with `Cache-Control: no-store`. Invalid sessions return the generic authentication failure and the frontend continues to the existing deployment-appropriate relaunch/password surface.
- Idle expiration defaults to 30 minutes; absolute expiration defaults to 12 hours. Refresh rotates the session ID.
- A 256-bit pseudorandom CSRF token is bound to the session through a domain-separated server HMAC, returned in login/local-launch/refresh/resume JSON, stored only in browser memory, hashed in the session row for new sessions, and required as `X-CSRF-Token` on every state-changing authenticated request. Resume deterministically reissues the same token for that valid session, so reload and multiple tabs do not invalidate each other. Existing pre-0.2.6 random CSRF hashes remain accepted for their original session lifetime while resume-issued tokens are also accepted; no raw token is migrated or persisted.
- Logout revokes the current session. Logout-all increments the admin session epoch; production requires the current local password, while loopback evaluation requires a fresh unconsumed local-launch grant and leaves the browser requiring relaunch.
- `GET /api/admin/auth/methods` returns only `{mode:"local_launch"|"password",password:{available},setup_required}`. GitHub is not reported as an authentication method.
- Authenticated `GET /api/admin/github/oauth/setup-guide` returns `{configured,callback_url,documentation_url,next_step}` with `Cache-Control: no-store`. The callback is the validated same-origin fixed callback; no secret, token, secret-file path, environment value, or owner identity is returned.
- `POST /api/admin/github/connections/oauth/start` creates one bounded authenticated connection transaction and redirects to GitHub with PKCE. Legacy `POST /api/admin/session/github/start` and `POST /api/admin/setup/github/start` MUST return `410 GITHUB_LOGIN_REMOVED`, MUST NOT redirect, create an owner/session, or consume setup/local-launch proof. One fixed `GET /api/admin/github/callback` validates only the connection intent.
- Legacy OAuth callback/start, connection, PAT, setup-guide, and identity endpoints MUST become non-redirecting, non-mutating `410 GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED` responses during the compatibility window and MUST be removed after that window. They MUST NOT accept, decrypt, return, or log credential material.
- Embedding profile endpoints (`GET/POST /api/admin/embedding-profiles`, `GET/PUT/DELETE /api/admin/embedding-profiles/{id}`, `POST /api/admin/embedding-profiles/{id}/probe`, and `POST /api/admin/embedding-profiles/{id}/activate`) expose only safe metadata. They enforce one active profile, never return credentials/private URLs, and report `probe`, `reindex_required`, `reindexing`, `ready`, or `last_known_good` states. Ollama model pull/delete actions are separate provider-native operations and require explicit confirmation.
- Local preparation (ADR-046/068, owner-approved 2026-10-20) uses `POST /api/admin/portfolio/prepare`, `GET /api/admin/portfolio/status` and `DELETE /api/admin/portfolio/prepare`. The shared status shape includes `state` (`idle | preparing | ready | failed`), nullable `revision` and `error_code`, `retry_at` (ISO-8601 UTC string or null), nullable `active_bundle_id` and `draft_revision`, and boolean `index_ready` and `draft_changed`. Recorded jobs additionally include `profile_id`, `chat_profile_id` and nullable `bundle_id`; GET may also include nullable `scene_state`. `retry_at` is always present, including old receipts without that key. It persists in the existing `publication.json` receipt and clears on a new prepare, success or `EMBEDDING_REINDEX_INTERRUPTED` recovery.
- In that local-publication path only, `queue(..., source_failures_reported_by_caller=True)` treats the closed source codes in §10 as publication failures: an inactive candidate ends in `reindex_required`, with null profile error code/message and unchanged successful probe fields, so it remains eligible for analysis and explicit preparation retry without probing again. Classify `BatchResolverError` / `SourceResolutionError` by type and code; the latter's lower-case aliases are `github_rate_limited` → `GITHUB_RATE_LIMITED`, `github_request_failed` → `GITHUB_ERROR`, `github_timeout` → `GITHUB_TIMEOUT` and `github_not_found` → `NOT_FOUND`. Other codes, model errors, bundle/activation failures and the default 「重建並啟用」 path retain existing handling. Typed retry seconds propagate through metadata blockers and a frozen completion outcome; the coordinator computes UTC now plus delay and rounds up to whole seconds. Logs expose safe codes/locations only. The 25-request reserve, admission semantics, preflight `{slug, code}` payload and last-known-good protection are unchanged; no schema migration or automatic retry is introduced.

### 11.2 Endpoints

| Method and path                                                                                        | Contract                                                                                                                                                                                                                                                                                                                                                                                                             |
| ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/admin/setup`                                                                                 | Production-only public safe state `{setup_required,setup_code_available}`; loopback mode reports setup unavailable and never returns code, digest, path, or expiry.                                                                                                                                                                                                                                                  |
| `POST /api/admin/setup`                                                                                | Production-only same-origin `{setup_code,username,password,password_confirmation}` -> initial session/cookie, `SETUP_DENIED`, or `SETUP_ALREADY_COMPLETE`; rejected in loopback mode.                                                                                                                                                                                                                                |
| `POST /api/admin/session/local-launch`                                                                 | Loopback-only same-origin `{grant}` -> `{csrf_token,expires_at,absolute_expires_at}` and cookie; grant is consumed atomically and never returned.                                                                                                                                                                                                                                                                    |
| `POST /api/admin/session`                                                                              | Production-only `{username,password}` -> `{csrf_token,expires_at,absolute_expires_at}` and cookie; rejected in loopback mode.                                                                                                                                                                                                                                                                                        |
| `POST /api/admin/session/resume`                                                                       | Strict same-origin, valid HttpOnly session cookie, empty body -> `{csrf_token,expires_at,absolute_expires_at}` with `Cache-Control: no-store`; consumes no launch/setup proof and sets no browser-persistent CSRF value.                                                                                                                                                                                             |
| `GET /api/admin/auth/methods`                                                                          | Safe `{mode,password:{available},setup_required}` without GitHub or owner identity state.                                                                                                                                                                                                                                                                                                                            |
| `GET /api/admin/github/oauth/setup-guide`                                                              | Authenticated safe `{configured,callback_url,documentation_url,next_step}` for host-side setup guidance; no credential or identity material.                                                                                                                                                                                                                                                                         |
| `POST /api/admin/session/github/start`                                                                 | Removed login route; always `410 GITHUB_LOGIN_REMOVED` with no redirect or state change.                                                                                                                                                                                                                                                                                                                             |
| `POST /api/admin/setup/github/start`                                                                   | Removed setup route; always `410 GITHUB_LOGIN_REMOVED` with no redirect or state change.                                                                                                                                                                                                                                                                                                                             |
| `POST /api/admin/github/connections/oauth/start`                                                       | Authenticated connection transaction -> redirect response and short-lived transaction cookie.                                                                                                                                                                                                                                                                                                                        |
| `GET /api/admin/github/callback`                                                                       | Single fixed registered callback validates session/state/cookie/connection intent, stores safe connection metadata, and redirects to a fixed `/admin` result.                                                                                                                                                                                                                                                        |
| Legacy `/api/admin/github/connections...`, OAuth callback/start, setup-guide, and identity routes      | Non-mutating `410 GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED` during the bounded compatibility window; no redirect, credential input, state mutation, or secret output.                                                                                                                                                                                                                                                  |
| `POST /api/admin/session/refresh`                                                                      | Auth + CSRF -> rotated session and CSRF token.                                                                                                                                                                                                                                                                                                                                                                       |
| `DELETE /api/admin/session`                                                                            | Auth + CSRF -> `204`, revoke current session.                                                                                                                                                                                                                                                                                                                                                                        |
| `DELETE /api/admin/sessions`                                                                           | Auth + CSRF + `{password?}` -> `204`, revoke all sessions. The local password is required as the recovery proof; a fresh GitHub sign-in cannot replace it.                                                                                                                                                                                                                                                           |
| `GET /api/admin/config`                                                                                | Return `{content,blob_sha,commit_sha,updated_at}` for `reponpc.yml`.                                                                                                                                                                                                                                                                                                                                                 |
| `POST /api/admin/config/validate`                                                                      | `{content}` -> normalized errors/warnings and parsed preview; no write.                                                                                                                                                                                                                                                                                                                                              |
| `POST /api/admin/config/preview`                                                                       | `{content}` -> localized profile/card/character preview; no write or model call.                                                                                                                                                                                                                                                                                                                                     |
| `PUT /api/admin/config`                                                                                | `{content,expected_blob_sha,commit_message}` -> commit result or `CONFIG_CONFLICT`.                                                                                                                                                                                                                                                                                                                                  |
| `POST /api/admin/assets/character/validate`                                                            | Multipart PNG -> validation result and ephemeral preview; no write.                                                                                                                                                                                                                                                                                                                                                  |
| `PUT /api/admin/assets/character/{filename}`                                                           | PNG + `expected_blob_sha` + commit message -> allowlisted GitHub commit.                                                                                                                                                                                                                                                                                                                                             |
| `GET /api/admin/readme-snippet`                                                                        | Query variant -> `{markdown,asset_url,target_url}`.                                                                                                                                                                                                                                                                                                                                                                  |
| `POST /api/admin/index/dispatch`                                                                       | Trigger allowlisted `build-index.yml`; return dispatch acknowledgement.                                                                                                                                                                                                                                                                                                                                              |
| `GET /api/admin/index/status`                                                                          | Return last publication/activation detail and safe error diagnostics.                                                                                                                                                                                                                                                                                                                                                |
| `GET /api/admin/embedding-profiles`                                                                    | Authenticated list of profile IDs, provider/model labels, observed compatibility identity, active/status flags, and safe timestamps; never credentials or private URLs.                                                                                                                                                                                                                                              |
| `POST /api/admin/embedding-profiles`                                                                   | Auth + CSRF + provider/model connection reference -> create a non-active profile after structural validation; no model download unless an explicit Ollama pull action is separately confirmed.                                                                                                                                                                                                                       |
| `GET /api/admin/embedding-profiles/{id}` / `PUT /api/admin/embedding-profiles/{id}`                    | Read or update one profile's non-secret settings; a changed identity is marked `reindex_required` until a probe and verified reindex complete.                                                                                                                                                                                                                                                                       |
| `DELETE /api/admin/embedding-profiles/{id}`                                                            | Auth + CSRF -> delete a non-active profile only; deleting the only valid active profile is rejected.                                                                                                                                                                                                                                                                                                                 |
| `POST /api/admin/embedding-profiles/{id}/probe`                                                        | Auth + CSRF -> bounded provider/model capability and sample-embedding probe; returns safe identity/status only.                                                                                                                                                                                                                                                                                                      |
| `POST /api/admin/embedding-profiles/{id}/activate`                                                     | Auth + CSRF -> queue probe/reindex and atomically activate only after bundle compatibility and smoke checks; last-known-good remains on failure.                                                                                                                                                                                                                                                                     |
| `GET /api/admin/embedding-models/catalog` / `GET /api/admin/embedding-models/installed`                | Authenticated curated catalog and provider-native installed-model metadata; no arbitrary URL/path input.                                                                                                                                                                                                                                                                                                             |
| `POST /api/admin/embedding-models/ollama/pull` / `DELETE /api/admin/embedding-models/ollama/{model}`   | Explicit Ollama-native pull/delete with bounded model IDs, progress/status, cancellation, and no secret/private-URL disclosure.                                                                                                                                                                                                                                                                                      |
| `GET /api/admin/embedding-models/builtin`                                                              | Fixed manifest descriptor and latest operation only: pinned model ID, display name, total bytes, license, public source URL and nullable profile ID. Does not inspect or download weights.                                                                                                                                                                                                                           |
| `POST /api/admin/embedding-models/builtin/download`                                                    | Auth + CSRF + exact `{confirmed:true}`; queues the sole pinned download in the existing model-operation lane. No URL/path/model inputs; no automatic probe, selection, reindex or activation.                                                                                                                                                                                                                        |
| `GET /api/admin/embedding-model-operations/{id}` / `DELETE /api/admin/embedding-model-operations/{id}` | Existing owner-only operation polling/cancellation, shared by explicit Ollama and built-in downloads. Safe progress and constant error codes only.                                                                                                                                                                                                                                                                   |
| `POST /api/admin/model-guidance/device-check`                                                          | Auth + CSRF + empty object; numeric nullable host RAM/free memory, disk and single-device VRAM observations plus packaged per-model CPU estimates, parameter/quantization/download/overhead facts, review date, public source/license links and dated envelope-v2 evidence. No host identifiers, saved service URLs/keys, prompt bodies, automatic model work or third-party transmission. See the A7 card contract. |

Admin APIs set `Cache-Control: no-store`. Login and state-changing requests require same-origin `Origin`/`Referer` validation in addition to CSRF. Admin responses never return environment values, password hashes, GitHub tokens, provider keys, or private provider URLs; the setup-guide exception is limited to its canonical callback and fixed documentation URL.

### 11.3 GitHub writeback

- The token MUST be a fine-grained token limited to contents/actions permissions on `REPONPC_CONFIG_REPOSITORY`.
- The target branch is `REPONPC_CONFIG_BRANCH`; it is never supplied by the browser.
- Allowed target paths are exactly `reponpc.yml` and normalized paths matching `assets/character/*.png`. Nested paths, deletion, renames, and arbitrary filenames are rejected in v1.
- `expected_blob_sha` is mandatory for replacement. Creation uses explicit `null` and fails if the file exists.
- Configuration is fully validated before commit. Assets are decoded and validated, not trusted by MIME/extension alone.
- Commit messages are length-limited plain text with a safe default.
- Every write creates a safe audit record with time, path, resulting commit SHA, request ID, and outcome, but not file bodies or credentials.

### 11.4 Guided onboarding contract (0.1.4)

All routes below are authenticated same-origin admin routes with `Cache-Control: no-store`; provider-consuming operations also require the current CSRF token.

#### Repository discovery and manual resolution

- `POST /api/admin/onboarding/repositories/discover` accepts `{account,page}` where `account` is a GitHub username or `https://github.com/{owner}` profile URL, `page` is 1–5, and the fixed page size is 50. It returns normalized public metadata only: slug, name, description, primary language, default branch, fork/archived flags, updated time, and HTML URL, plus `{page,has_more}`.
- `POST /api/admin/onboarding/repositories/resolve` accepts `{repository,ref}` where `repository` is `owner/name` or an exact GitHub.com repository URL and optional `ref` is a branch, tag, or SHA. It returns the normalized public slug and safe metadata; it does not fetch the repository tree, build evidence, or call a model.
- Discovery uses unauthenticated public GitHub REST requests and never sends the configured fine-grained writeback token. GitHub.com/API hosts, redirects, response bytes, timeouts, and URL normalization remain server-owned allowlists. Private, missing, or inaccessible repositories return the same `404 NOT_FOUND` behavior.
- Listing does not authorize source analysis. The browser must present checkboxes and record an explicit confirmation of the selected set before calling analysis.

#### Selected-only repository analysis

- Repository analysis is optional and MUST NOT be a prerequisite for contribution entry, local validation, local preview, copy, or download. The analysis stage exposes an explicit manual continuation before any preflight/provider/GitHub request and again on every blocker or failure. Choosing it preserves the confirmed selection and changes only still-unconfirmed analysis-derived suggestions.
- Version 0.1.7 supersedes the 0.1.4 synchronous execution lifecycle with the durable batch API in section 9.5. It does not supersede the selected-only trust boundary, explicit cost action, optional/manual path, owner-confirmation rule, or cleanup requirement.
- `POST /api/admin/onboarding/repositories/analyze` is a legacy response-shape compatibility adapter. It accepts exactly one confirmed `{slug,ref,include,exclude}` selection, creates a one-item durable batch governed by section 9.5, and waits within the configured repository budget (1,800 seconds by default). It MUST NOT run an independent synchronous analysis pipeline or reuse bundle publication as an implicit side effect. If the HTTP wait ends before the batch does, the durable batch remains recoverable through the batch snapshot/event API unless the owner explicitly cancels it.
- Only one owner-scoped batch may be active. The compatibility adapter and batch API reuse the exact-SHA resolver, exclusions, secret scan, parsing/chunking, evidence IDs, retrieval, context packing, prompt isolation, provider adapter, output validation, stage caps, and retry policy. Provider operations use the independent configured inactivity ceiling (300 seconds by default); analysis output uses section 4.3's separate 16,384-default / 16,384-maximum policy (ADR-055), with explicit lower deployment values still accepted.
- Analysis uses only the configured provider/model and shares the global generation semaphore. It does not decrement the anonymous public daily-chat counter. Transient rate-limit, timeout and unavailable failures may retry the same frozen provider/model up to three total attempts inside the repository budget; authentication, context, validation, output-limit and completed invalid responses do not retry. No provider/model/cloud fallback occurs.
- Waiting to acquire archive, index or shared provider capacity MUST NOT spend the repository active-execution budget. The durable snapshot exposes active elapsed time, budget and dispatched generation attempts. Oversized individual archive members are skipped without materializing their bodies and appear in the safe skipped summary; total compressed/uncompressed/entry ceilings and unsafe archive structures still fail closed.
- An explicit owner retry adopts the currently configured repository budget and generation-attempt ceiling, including for a batch created before migration 25. It preserves already consumed active time, frozen provider/model identity and prior terminal evidence; deployment never resubmits old work automatically.
- Before parsing analysis JSON, reject `finish_reason=length` (including the native Ollama equivalent) as `PROVIDER_ERROR` with `PROVIDER_OUTPUT_LIMIT_REACHED`, even when content is nonempty or happens to be valid JSON. An adapter's empty-output/length diagnostic maps to the same reason. Discard partial content; do not repair, retry, or cache it as success. Other malformed/schema-invalid output still uses `PROVIDER_OUTPUT_SCHEMA_INVALID`; each required localized inference `title` and `statement` is checked for the configured locale's writing systems, and any writing-system word absent from both the locale base set and the packed request source is rejected. Full evidence/person-claim validation remains mandatory.
- Analysis result cache identity includes the configured output budget, effective provider output/context caps and generation/validation policy version in addition to frozen source/model identities. Preflight prediction, execution and cache writing use the same policy identity as generation. Changed capacity/budget/policy misses old results without deleting owner-confirmed text; compatible derived indexes may still be reused.
- The server-owned analysis system prompt MUST repeat the exact JSON-only envelope, property names, bilingual string requirements, and the request's allowlisted evidence IDs even when the adapter also requests native structured output. Repository evidence remains inside an explicit untrusted-data boundary. The backend still validates the complete response; prompt instructions or provider-native schema support are never treated as proof of conformance.
- Bulk passage embedding MUST be split into deterministic, order-preserving batches sized from the configured vector dimension so a valid high-dimensional JSON response stays below the bounded provider-transport response limit. Each batch is validated independently before any vector is inserted; increasing the shared response cap is not a substitute for batching.
- Archive bytes, repository bodies, prompts, provider bodies, incomplete output, and staging paths remain ephemeral and are removed on every terminal/recovery path. Runtime SQLite may retain only the safe batch metadata, ordered events, cache identities, validated normalized terminal result, source-consumed marker, bounded idempotency receipt and recovery dismissal allowed by sections 15.1 and 15.4. Failed and `completed_with_errors` batches expire after 7 days for ADR-052 recovery; other terminal batches expire after 24 hours. Startup recovery runs expiry cleanup before lease recovery; a stoppable in-process cleanup loop continues during service operation, and reads reject and remove an already-expired terminal snapshot immediately. Expired terminal source rows may be removed even while a successor remains active because the successor already contains its own immutable commit, selection policy, frozen model identity, and safe lineage IDs; lineage must not retain full ancestor results past their TTL. A still-retained source item's consumed marker survives earlier successor-result cleanup so it cannot create duplicate work. A generation already dispatched is never retried after interruption without explicit owner confirmation.
- The model cites only request-local IDs (`S1`, `S2`, ...), and the server validates and maps them back to persistent evidence IDs for stored and API `supporting_evidence_ids` (ADR-063).
- The validated analysis payload contains `facts` with exactly `evidence_id`, `evidence_class`, `path`, `start_line`, `end_line`, and a pinned GitHub `url`; it does not return `excerpt` or a model-authored fact `title`. Each `MODEL_INFERENCE` contains localized `title` and `statement` plus `supporting_evidence_ids`; `title` is bounded by the analysis schema and is checked by the same evidence/person/writing-system rules as `statement`.
- The response identifies the exact slug/commit and returns `REPOSITORY_FACT` items with supporting evidence IDs/locations plus separately labeled `MODEL_INFERENCE` suggestions. It never returns server paths, raw prompt bodies, credentials, private provider URLs, or unrestricted repository bodies.

#### Contribution suggestions and confirmation

- `POST /api/admin/onboarding/contributions/suggest` accepts one selected slug plus an owner-authored statement of at most 4,000 Unicode scalar values describing personal work, results, collaboration, and non-attribution boundaries. The original statement is returned unchanged beside editable proposed localized role/summary/claims.
- This operation may call only the configured model under the same provider, timeout, semaphore, privacy, and no-fallback rules. It MUST NOT strengthen a personal claim silently, mark a proposal confirmed, or infer authorship, employment, seniority, responsibility, achievement, or impact from repository content.
- The browser presents `REPOSITORY_FACT`, `MODEL_INFERENCE`, and proposed `OWNER_ASSERTION` groups separately. The owner may accept, edit, or reject each personal proposal. Only an explicit accept/edit action may place the text into role/summary/claims in a draft.
- Owner-approved presentation update (2026-10-07, implemented 2026-10-14): each analyzed repository shows its slug, primary-language chip when available, pinned commit short SHA, and a `Highlights` section. Each inference is a flat row with a localized short title, an optional first-source chip with a `+N` count, and a keyboard-operable button that expands the localized statement and matched GitHub permalink list. The info popover states that the AI summary is for reference and is never public or added automatically to the portfolio. The UI does not render excerpts, technical evidence IDs or uncited facts separately; when some cited evidence is absent from the result, the expanded row says so in one muted line instead of implying verification. A final `Next: describe my contribution` action precedes `Analyze again`; reading, expanding, or opening a source never confirms personal work or calls a model. Both locales and the manual route remain in the existing journey.
- Schema version 1 remains unchanged. Localized repository `role` and `summary` remain required; when the owner confirms them into `reponpc.yml`, they retain the existing `OWNER_ASSERTION` classification. Repository facts and unconfirmed model inferences are not serialized as owner assertions.

#### Draft, resume, validation, and export

- `POST /api/admin/onboarding/draft` accepts confirmed guided fields only and returns `{content,validation}` containing a complete UTF-8 schema-v1 YAML draft plus the existing normalized validation result. When `base_config` is supplied, fields outside the guided surface (including links, avatar, tags, demo URLs, card, character, and retrieval settings) are retained. It performs no model, GitHub, or publication call.
- Every non-terminal guided stage provides Back or an equivalent Edit action. Editing selection invalidates a preflight plan and analysis result only when its repository, ref, include, or exclude identity changed. Removing a repository removes only that repository's contribution state. Profile fields and unaffected repository statements/results MUST remain. A separate destructive Start over action requires confirmation.
- Existing validated configuration MUST hydrate the guided editor with its profile and selected repositories, including localized headline/bio/greeting, ref/include/exclude, role/summary, and claims. Guided draft generation MUST preserve validated fields outside the guided surface. Because the public configuration schema rejects unknown keys, a raw edit containing unmappable/unknown YAML remains in advanced mode with an actionable validation message rather than being silently discarded.
- Unsaved selections, owner-entered public statements, and confirmed suggestions MAY be stored in browser `sessionStorage` for reload/resume within the authenticated browser session. Logout and successful GitHub save MUST clear them. Session/CSRF tokens, credentials, raw repository bodies, raw prompts/outputs, and private URLs MUST NOT enter Web Storage.
- Copy and download of the generated `reponpc.yml` are local browser operations and remain available without a GitHub token. They do not mark the draft saved, mutate GitHub, or dispatch indexing.
- Existing `/config/validate` and `/config/preview` remain model-free and mutation-free. GitHub save, workflow dispatch, publication, and activation remain distinct explicit actions with existing conflict and last-known-good behavior.

#### Proposed error mapping

- Invalid usernames/URLs/slugs/pages/ref/include/exclude/owner statements return `400 VALIDATION_ERROR` with bounded field details.
- Missing/private/inaccessible accounts or repositories return `404 NOT_FOUND` without visibility disclosure.
- GitHub upstream/rate-limit failures return `502 GITHUB_ERROR` or `429 RATE_LIMITED` with bounded retry metadata when available.
- No eligible source content returns `422 CONFIG_INVALID` with safe reason `NO_ELIGIBLE_CONTENT`.
- An empty include selection uses the documented directory/manifest defaults plus common root-level source extensions (`c`, `cc`, `cpp`, `cs`, `css`, `go`, `h`, `hpp`, `html`, `java`, `js`, `jsx`, `kt`, `kts`, `php`, `py`, `rb`, `rs`, `sh`, `sql`, `swift`, `ts`, `tsx`, `vue`, `ps1`, `bat`, and `cmd`). Mandatory binary/generated/secret/path exclusions still run after matching; explicit owner include/exclude values remain authoritative.
- Provider unavailable, invalid, timed out, or failed returns the existing `MODEL_UNAVAILABLE`, `PROVIDER_ERROR`, or `PROVIDER_TIMEOUT` code; selection and browser draft remain available and no fallback occurs. Analysis-output schema failure, including malformed/missing `title`, ungrounded writing-system words, evidence-ID mismatch, and rejected personal attribution, retains the respective safe reason `PROVIDER_OUTPUT_SCHEMA_INVALID`, `PROVIDER_EVIDENCE_ID_INVALID`, or `PROVIDER_PERSONAL_INFERENCE_REJECTED` without retaining provider output.
- Cancellation/disconnect sends no replacement success body; server cleanup remains mandatory. Failure of one repository does not erase other confirmed selections.

### 11.5 Provider-neutral model setup (0.2.2)

This section is the current model-configuration boundary. Where older text prohibits all browser-originated provider keys/URLs, this section authorizes only owner-entered values in the authenticated same-origin model form. Reads remain metadata-only. Existing embedding routes in section 11.2 remain the migration baseline; the implementation handoff identifies the wire-contract preparation work before application edits.

#### Connection and role separation

- A connection identifies one explicitly selected protocol (`ollama` native or `openai_compatible`, with the existing `vllm` preset), one API base URL, and optional authentication. The protocol is not inferred from a model name or hostname. A base URL includes any gateway prefix such as `/v1`; fixed operation paths are appended once, without guessing another service.
- Chat and embedding have separate profile selections and capability tests. The same saved connection MAY be explicitly selected for both, but neither capability, model, nor credentials are automatically copied to another destination. A chat-only service leaves search unconfigured with a direct action to configure it.
- Model ID is manually editable for every provider, including existing non-catalog Ollama models. An optional model list is scoped to the selected connection. Unsupported listing (`404`/`405`/`501`) permits direct capability testing of the typed ID. Authentication, timeout, rate, and malformed-list failures are surfaced safely; none silently switch services. Listing never establishes readiness by itself.
- Chat testing uses a bounded synthetic request through the actual chat adapter and required envelope/capability validation. Embedding testing uses bounded synthetic query and passage samples and validates dimensions/finite values/normalization. Tests require explicit action, have cost/time/concurrency bounds, and never send repository content or owner drafts.
- A new deployment, launcher, or form with no explicit configuration MUST leave both roles unconfigured. Missing model settings MUST NOT prevent process health, protected admin access, manual authoring, validation, preview, or export. Semantic chat remains unavailable until its full prerequisites pass. No model download or upstream request occurs merely because the user opens setup.
- Public schema-v1 draft validation/export may retain an existing or explicitly labeled illustrative embedding descriptor from the public template. That descriptor is not a selected runtime connection or proof of readiness. Before a real build, replace it with the explicitly selected, verified profile identity and validate the match. This preserves manual export without adding a null descriptor, silently choosing a provider, or weakening bundle validation.
- Explicit existing environment/secret-file settings are represented as host-managed connections with safe labels. The UI may replace or delete them but never reads back their environment URL/key. Replacement requires a complete newly entered URL, writes a new protected owner-managed revision, and durably wins over later environment changes. Once that connection is owner-managed, startup MUST also preserve its owner-edited model profile instead of remirroring environment model fields into it. Deletion first requires references to be removed, then persists secret-free suppression so restart does not recreate the card or its environment profile. An owner may also create another managed connection and select it. Incomplete host configuration reports its own recovery state, never a fallback. Existing persisted profiles/bundles survive migration; a prior implicit default is not evidence of consent to new network work.

#### Secret ingress, storage, and egress

- The form accepts a base URL and optional API key through a bounded authenticated request body with session, CSRF, same-origin checks, private admin topology, and `Cache-Control: no-store`. Provider requests originate only on the server. Production admin transport uses HTTPS or the established protected private tunnel; the direct loopback exception retains its strict checks.
- Keys are write-only. The UI may show/hide only a newly typed value; responses show `key_configured` rather than key suffixes/fingerprints. No secret or private URL enters Web Storage, service-worker caches, URLs, telemetry, logs, public YAML, bundles, exports, errors, or snapshots. Clear typed keys after submission, cancellation, logout, session expiry, or form teardown. Backend validation must not echo invalid input bodies.
- Persist managed keys through a vetted authenticated-encryption library with a host-protected key separate from the database, or an equivalent supported OS secret store. No plaintext credential table or home-grown cryptography is allowed. Secret storage failure leaves existing state intact and returns an actionable unavailable state; it cannot downgrade to plaintext or create a new registration prerequisite.
- Endpoints and secret references are private server state. Read responses expose a display name, provider, server-issued ID/revision, configured booleans, safe model labels, and status only. Editing uses explicit replacement input; the owner-approved edit-endpoint exception above may prefill a prior owner-entered managed URL, never a host-managed environment URL. Retain/replace/remove key intent must be distinguishable; a blank field cannot silently delete a stored key.
- Changing protocol or destination invalidates candidate tests. A retained key MUST NOT be sent to a changed destination and therefore requires explicit replacement/removal. The first replacement of a host-managed connection may retain a proven no-key state; ordinary managed destination changes retain the existing explicit key-intent contract. In the same database transaction, directly referencing candidates that are inactive and neither previous last-known-good nor reindexing MUST bind the new connection revision/provider, clear observed/probe/error metadata, and return to an explicit-test-required state. The owner MUST NOT need a separate profile edit-save to perform that rebinding. Analysis selections referencing the changed connection keep their explanatory IDs/revisions but advance selection generation and become stale until retested/reselected. Public-active, previous last-known-good, reindexing, and already frozen work retain their immutable historical connection/profile revision and historical provider metadata until an explicit verified switch or terminal completion. Profiles that do not reference the changed connection MUST NOT be changed. No connection save automatically probes, activates, reindexes, analyzes, or publishes.
- Accept only structurally validated HTTP(S) service endpoints, reject userinfo/query/fragment and unsafe paths, and use fixed protocol operations. Public API services require HTTPS. Private/loopback provider access is explicit and constrained by host egress policy; prohibit link-local/metadata/multicast/unspecified destinations and public-to-private DNS rebinding. Resolve and validate addresses at connection time and prevent redirect-based credential forwarding. This is not a generic proxy or downloader.
- Secret rotation, backup/restore, missing encryption keys, storage permissions, atomic updates, reference cleanup, and rollback MUST be tested. GitHub public-read credentials remain retired; provider-key storage cannot reuse OAuth/PAT tables, names, or authority. Existing writeback/authentication boundaries are unchanged.

#### Profile lifecycle and novice workflow

- Owner-corrected diagnostic refinement (2026-09-12, FR-038/039/040, AC-054/055/057): authenticated Chat and Embedding test cards show the actual upstream HTTP status and the provider's original error message outside technical details. Do not translate the provider's text or infer a cause/recovery from a status-code lookup. Preserve `PROVIDER_HTTP_<100..599>` in `last_error_code`; the existing fixed transport/validation categories remain supported when no HTTP response exists. The additive nullable `last_error_message` field in both authenticated profile DTOs and runtime tables contains only bounded, redacted message text from a failed synthetic probe. At the adapter boundary, inspect at most 65,536 response bytes; accept nonempty JSON strings at `error.message`, `error`, `message`, or `detail` in that priority order, or an explicit UTF-8 `text/plain` response that is not an HTML page. Unsupported/malformed responses provide no message. Remove configured secrets/private URLs (including URL-encoded forms and the configured hostname), URL spans, and unsafe display controls before limiting the text to 2,000 characters with an ellipsis. Do not retain full JSON/HTML bodies, other metadata, headers, exception text or credentials. Render as escaped plain text with wrapping and preserved line breaks in both locales. When usable text is absent, display the actual status plus `未提供可顯示的錯誤文字。 / No displayable error message was provided.` without guessing. Runtime migration 20 adds the two nullable columns transactionally; existing rows retain their data and receive null messages. Reload retains the latest failed diagnostic; successful retest or an edit invalidating the test clears it. Old errors require an explicit retest to acquire original text; never invent it. Public diagnostics, response HTTP status, activation and fallback policy are unchanged. Both create actions remain `新增模型 / Add model`.

- Present two independent purposes: `回答模型 / Chat model` and `資料查找模型 / Content finder` (technical name: embedding model). Each starts at service choice, then connection/model input, explicit test, review, and explicit use. Back/Edit preserves unrelated public drafts and saved choices; cancelling does not activate a candidate. Figma artifacts are not a prerequisite.
- The primary form contains service type, API address, optional key, and model name. Dimensions, prefixes, connection IDs, and raw diagnostic codes belong to an optional advanced view. Unknown dimensions remain unknown until sampled; arbitrary numeric placeholders cannot be used to satisfy a required database column.
- Owner-approved novice-setup refinement (2026-09-12): embedding profile create/update accepts an omitted or null `dimension`; a supplied dimension must be 1–65536. Persist unknown as SQL NULL. Only an explicit successful query-and-passage probe establishes and persists the observed identity; a failed probe preserves the previous dimension. Unknown identities cannot activate, build, or satisfy analysis readiness. Existing concrete bundle identities remain unchanged. Managed profile create/update binds the current connection revision server-side.
- Connection writes accept `endpoint_action: replace|retain` (default `replace` for existing clients). Creation requires `replace` and a valid `base_url`. Ordinary managed updates with `retain` require an omitted/null URL and use the protected current endpoint without returning it; `replace` requires a new URL. A host-managed update rejects endpoint `retain` as `HOST_CONNECTION_REPLACEMENT_REQUIRED`, accepts only a complete newly entered URL, and converts the connection to owner-managed on success. Key retain/replace/remove remains independent. When key intent is `retain`, the server compares the validated old and new provider plus normalized origin: scheme, case-insensitive hostname, and effective port (default 80/443 included). A path-only edit on the same provider/origin may retain the key; changing provider, scheme, hostname, or effective port returns `CREDENTIAL_REPLACE_REQUIRED` unless the owner explicitly replaces or removes the key. Display-name-only edits of ordinary managed connections preserve connection revision and test validity; every effective provider/URL/key change creates a new revision, rebinds only safe candidates, clears probe evidence, and requires explicit retest.
- Failed connection create/update/delete/refresh operations return or map to safe stable reasons and never disappear silently. The UI renders one alert in the panel that initiated the action, moves focus to its summary, associates URL/credential errors through `aria-invalid` and `aria-describedby`, and includes what failed, safe cause, preservation status, and next action in both locales. A validated request ID may be displayed for server-log correlation. It MUST NOT display bodies, secret values, private URLs, stack traces, or arbitrary exception text. A newly submitted key is cleared regardless of outcome; a failed operation explicitly tells the owner to re-enter it if the retry still needs replacement. Pending submission disables duplicate actions and labels the in-progress state.
- `GET /api/admin/embedding-models/installed` accepts optional `connection_id` and lists only that explicitly selected native Ollama connection; omitted IDs retain the legacy configured-host contract. Opening setup does not call this endpoint. Loading, failure, empty, and populated states remain distinct, and listing never marks a model tested.
- Apply successful mutation responses to the affected card before refreshing lists. Older list responses cannot overwrite newer mutation results; a later list failure preserves the completed operation and offers refresh. Analysis selection must distinguish unconfirmed edits from saved eligible selection, exclude invalid/stale profile IDs, and label options with their safe service display name. Model testing and public-index rebuilding have distinct status/action labels in both locales.
- Saving a candidate does not activate it. Chat switches after its capability test, with in-flight requests retaining the old revision; it does not itself require an embedding reindex. Chat-model changes invalidate incompatible analysis-result caches. Embedding changes retain the existing probe/reindex/verify/smoke/atomic-switch rule and last-known-good bundle. Zero active profiles is valid during setup; at most one is active per role, and a ready role has exactly one.
- A successful connection test, an installed model, a ready search index, and a published portfolio are distinct outcomes. Embedding candidates can request reindex without first pretending to be `ready`. A private provider unreachable from the chosen index builder must yield a publishing-specific recovery state; do not expose the provider publicly or change topology automatically.
- Primary states use localized descriptions and a next action: unconfigured, testing, available for use, building search index, currently in use, or failed. Show retry/edit and manual continuation when appropriate; a raw `probe_failed`/`EMBEDDING_PROBE_FAILED` alone is insufficient. Configuration/test errors preserve non-secret fields and unrelated repository work.
- Admin layout is a restrained workspace with clear navigation, aligned fields, readable state/action grouping, and responsive wrapping. The model catalog is contextual to its selected provider. Normal onboarding must not be preceded by an always-expanded technical model panel. Meet WCAG 2.2 AA, keyboard/focus/status announcements, both locales, reduced motion, and no overlap/content loss at 375/768/1024/1440 pixels and 200% zoom.
- Ollama curated pull/progress/cancel/delete stays explicit and provider-owned; connecting an existing model is not restricted to the download catalog. Generic APIs/vLLM have no download button. RepoNPC-managed GGUF/Hugging Face execution/download remains unapproved future work, requiring a separate runtime, hardware, licensing, artifact-integrity, isolation, and distribution decision.

### 11.6 Model-first guided onboarding (0.2.3)

**Built-in extension (FR-049, ADR-052):** the built-in profile has
`provider=builtin_onnx`, `connection_reference=null`, `connection_revision=0`,
the full pinned revision in `model_id`, 1024 normalized dimensions and empty
prefixes. External profiles continue to require a nonempty connection reference.
The download consent is a strict boolean true, not a coerced string/number. Merely
opening the panel reads the manifest and latest safe operation; weights and device
information are accessed only after the respective explicit action. A successful
download still requires the existing capability test and deliberate analysis
selection or verified public reindex. The empty verified model catalog is reported
honestly and cannot be used as evidence of model compatibility or speed.

This section supersedes section 11.4's first-run sequence and section 11.5's insufficient separation of analysis selection from public activation. It preserves authenticated write-only model setup, explicit repository consent, optional/manual authoring, bilingual validation, and the existing publication topology. A profile being selected for analysis does not set its public `active` flag or mark its public search index ready.

#### User journey

Welcome explains the outcome and offers **Set up AI and begin** and **Build manually first**. It is not counted as a completed step. The AI route has exactly six primary steps:

1. **Set up AI models:** configure `分析與回答模型 / Analysis and chat model`, then `資料查找模型 / Content finder` (embedding model). Each exposes service, API base URL, optional write-only key, editable model ID, explicit test, and explicit selection. A saved connection can be deliberately shared, but the two capabilities must be tested independently. Successful tests do not implicitly select models or start analysis. The step completes only when both tested revisions are selected; an existing valid selection is reusable without re-entering stored secrets.
2. **Choose projects:** discover public metadata, select repositories, and confirm the exact set. No source or model request is caused by listing or confirmation alone. The first-run AI path reaches this step after model setup; manual discovery and returning-owner selection editing remain available without models.
3. **Analyze projects:** summarize confirmed projects and the selected models. One primary **Start analysis** action orchestrates bounded preflight and durable batch creation under that explicit consent. Do not require users to operate a separate “prepare batch” control. Recheck prerequisites before upstream work; if the plan/selection/model identity changes or another batch exists, stop and reconcile before generation. Opening or returning to the page never starts/retries analysis. Show per-project progress, partial success, retry/cancel/recovery, and manual continuation. Internal cache/stage diagnostics remain secondary; durable batch controls are not removed from the API.
4. **Confirm my contribution:** distinguish observed repository facts, AI inferences, and owner-authored/confirmed contribution. Only explicit confirmation can turn proposed personal claims into public configuration. Missing analysis results permit manual entry.
5. **Complete basic information:** author the existing name, biography, greeting, and required bilingual fields. This amendment does not weaken schema-v1 or locale completeness rules or redesign character assets.
6. **Preview and complete draft:** validate/preview without model or publication side effects, edit, copy/download, and report publication prerequisites. Draft completion, GitHub save, workflow dispatch, index validation/activation, and public availability remain separate outcomes/actions. A missing writeback credential or published bundle cannot prevent a valid local draft.

The manual route skips model setup and analysis, proceeding through project selection, contribution, profile, and preview/draft. Its progress indicator counts only its four applicable steps; skipped AI work is not marked passed. Switching to AI at any point opens the missing model setup with a return destination and preserves the existing public draft. Model settings must be reachable directly in guided mode and from contextual recovery, not only through raw-YAML/advanced mode. Small viewports show the current step and count with an accessible expandable step list; the desktop indicator must wrap without clipping or presenting completion percentages as work estimates.

#### Analysis dependencies and public activation

- Analysis readiness is a server-owned capability for the selected chat/embedding revisions and required runtime storage/admission controls. It MUST NOT be derived solely from `/api/public/status.model.ready`, `/readyz`, a public `active` flag, model listing, or a browser-persisted boolean. A fresh live test is explicit; metadata reads do not generate probe traffic. A prior successful test is invalidated by relevant configuration/revision changes and never guarantees future upstream availability.
- Both models are required by the current analysis algorithm: passage/query embeddings and retrieval precede chat generation. This amendment does not introduce chat-only analysis or lexical fallback. Manual work requires neither model.
- Persist only the selected analysis references and safe validation metadata in deployment-local runtime state; resolve credentials through the existing protected connection boundary. Analysis selection is logically distinct from public active profiles and must not modify public bundle pointers. An embedding candidate can be tested and explicitly selected for analysis while awaiting its first public index. Selection itself performs no reindex, source download, generation, GitHub write, or publication.
- The clean bootstrap path MUST construct usable analysis dependencies after model selection even when the process started without providers. Public service assembly/reindex preparation MUST NOT require an already-working public model pair merely to prepare its first candidate. Restart is not the normal transition from saved settings to usable analysis.
- Preflight and batch acceptance bind the confirmed repository identity and selected connection/profile revisions, including complete embedding semantics and chat model identity. Work admitted under one pair retains that pair, or stops safely if it cannot be resolved; it cannot silently resolve the latest selection mid-item. Use existing bounded retention and interruption-confirmation rules. Changes invalidate incompatible plans/cache reuse; valid old results may remain labeled with their source/model identity, but are never presented as fresh results from the new pair. Owner-confirmed text is preserved.
- Public readiness remains stricter: a compatible verified bundle, public model selections, storage and provider availability must pass the existing validation/smoke/atomic-switch requirements. Analysis's ephemeral derived index is not a published portfolio bundle. A successful analysis must not publish or activate it. Existing last-known-good public service remains unchanged while a different analysis pair is configured/tested/used.

#### Recovery, compatibility, and implementation contract preparation

- Distinguish missing configuration, saved-but-untested, tested-but-unselected, unavailable selected service, missing public index, and publication-only blockers. Explain the missing role and offer **Set up content finder**, **Test model**, **Select model**, **Retry**, or the relevant concrete action; do not label a clean unconfigured deployment “Ollama unavailable.”
- Contextual model editing records a safe return destination. Success/cancel returns to preserved work; cancellation does not change saved selection, and typed secrets clear under section 11.5. Completed configuration refreshes safe capability state without implicitly resubmitting analysis. Active jobs retain their frozen pair; navigation cannot duplicate or silently cancel them.
- Migrate old `reponpc.guided-onboarding.v1` / guided-draft state conservatively: retain allowed public selection/profile/contribution fields, reconcile batches with the server, and treat browser readiness as untrusted. An old analysis-stage resume with missing models shows direct setup recovery instead of requesting a destructive reset. Existing completed drafts remain editable/exportable without repeating AI steps. Unmappable advanced YAML remains intact in advanced mode. This does not approve durable server-side portfolio drafts.
- The authenticated additive analysis-selection contract is `GET /api/admin/analysis-selection` and `PUT`/`POST` on that path. The write body is exactly `chat_profile_id`, `embedding_profile_id`, and optional optimistic `expected_generation`; it requires the existing same-origin session and CSRF boundary. The no-store read view contains only role profile IDs, connection revisions, safe model IDs/status/test state, selection generation, eligibility, and a stable safe reason. It never returns endpoint, key, secret reference, provider body, or a public-readiness proxy. Invalid roles return `404`; unprobed roles and stale generation return `409`; unavailable selection service returns `503`.
- Runtime SQLite retains the current explicit selection separately from public active profiles, and each accepted batch retains one secret-free pair snapshot: selection generation; each profile/connection ID and connection revision; chat provider/model identity; and complete embedding provider/identity semantics. The preflight plan and batch creation must agree on that snapshot or return `ANALYSIS_PLAN_STALE`. Cache keys derive from the frozen embedding/chat identities. An in-flight/recovered item resolves only its persisted connection revisions through the protected store; missing/deleted/rekeyed material fails safely as `MODEL_UNAVAILABLE`, never by resolving the latest selection or falling back. Existing batches created before this snapshot migration also fail safely rather than retarget.
- Guided browser-state migration remains conservative: only serializable route/return/public-draft state is retained; model capability, secrets, and analysis readiness remain server-owned. Prefer existing registries/batch mechanisms; do not change legacy endpoint behavior or public schemas silently. Broader trust, topology, algorithm, scope, or validation changes still require a new owner decision.

### 11.7 Encrypted maintenance backup and restore (0.4.7)

FR-053 uses the existing SQLite online backup primitive on the host. The Web
artifact MUST be password-encrypted; raw SQLite, admin hashes, host keys and
stored secrets MUST NOT be returned to the browser. The owner enters a new
12–1024-character password for each backup or inspection (UTF-8 maximum 4096
bytes). Password inputs clear after submission and remain outside storage,
logs, fixtures and public drafts. A successful backup is also retained as
ciphertext in `data/private/maintenance/`; retaining a file does not prove that
the browser completed its download.

The `.reponpc-backup` v1 container is exactly `RepoNPCBackup` plus bytes
`00 01`, a fresh 16-byte salt, a fresh 12-byte nonce, and AES-256-GCM ciphertext
including its 16-byte tag. The full header is authenticated additional data.
Scrypt parameters are fixed at `N=131072, r=8, p=1`, deriving 32 bytes; uploaded
content cannot change KDF cost. Encrypted plaintext contains a four-byte
big-endian metadata length, strict JSON metadata (maximum 4096 bytes; exactly
UTC `created_at`, positive `schema_version`, `application_version`), then SQLite
bytes (maximum 128 MiB). Metadata is disclosed only after authentication.
Unknown formats, duplicate JSON keys, invalid sizes and incompatible application
versions fail closed. Initial restoration requires the exact application version
and a recognized runtime migration prefix; it normalizes to the current trusted schema.

All routes below retain private Host/Origin, owner session and mutation CSRF
checks, including loopback evaluation, and use `Cache-Control: no-store`.
Authentication precedes JSON or multipart parsing. POST JSON is bounded to
8192 actual bytes. Multipart has exactly one `backup` file and one `password`
field, a single valid Content-Length, no Transfer-Encoding, maximum file size
128 MiB + 8192 bytes, and maximum actual body size 128 MiB + 24576 bytes.

After backup creation the UI offers a native download link using only the exact
same-origin `Content-Location` path and fixed backup-ID grammar. It does not read
plaintext, store the password or invent a download-completion receipt. The GET
attachment requires current owner authentication even if its identifier is known.
It cannot create another backup or start provider work. The initial binary POST
response remains compatible; Blob URLs, synthetic clicks and release timers are
not part of the UI download lifecycle.

| Method and path                                      | Contract                                                                                                                                                                                                                                                                               |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/admin/maintenance/status`                  | Exactly safe `active_bundle_id`, `previous_bundle_id`, `pinned_bundle_id`, nullable `last_backup_at`, `local_ready`, `gateway_configured`, `externally_verified`. Gateway observation retains the A1/F0 rules.                                                                         |
| `POST /api/admin/maintenance/backup`                 | `{password}`; ciphertext `application/octet-stream` attachment `reponpc-backup.reponpc-backup`, after successful local ciphertext retention; additive `Content-Location` gives the same-origin encrypted-file URL.                                                                     |
| `GET /api/admin/maintenance/backup/{backup_id}`      | Owner-authenticated native attachment download of the saved ciphertext; same private Host plus Origin or same-origin Referer boundary, no key/password input or new snapshot. Identifier is the fixed timestamp/random filename suffix, never a bearer authority; absence returns 404. |
| `POST /api/admin/maintenance/restore/inspect`        | Multipart `backup` and `password`; returns only opaque session-bound `preview_id`, authenticated metadata and `expires_at`. One preview is retained for ten minutes; replacement, cancellation, expiry or shutdown clears its password and private staging.                            |
| `POST /api/admin/maintenance/restore`                | `{preview_id,confirmed:true}` with strict boolean true; `202 {status:"restoring"}` acknowledges acceptance, not completion. The current mounted UI disables duplicate writes and asks the owner to reopen management after restoration.                                                |
| `DELETE /api/admin/maintenance/restore/{preview_id}` | Clears only that session's valid preview; `204`.                                                                                                                                                                                                                                       |
| `POST /api/admin/maintenance/pin`                    | `{bundle_id,confirmed:true}`; only the retained previous bundle is eligible, checked atomically by the existing pin primitive; returns safe maintenance status.                                                                                                                        |
| `POST /api/admin/maintenance/gateway/stop`           | Empty object; stops the existing local visitor gateway and returns safe maintenance status. It cannot operate Tailscale.                                                                                                                                                               |

Restoration is SQLite state restoration in the same original data directory,
not a full migration archive. Preserve host keys, retained bundles, model files,
appearance and local-portfolio assets separately. Verify owner identity,
decryptability of retained connection revisions, exact trusted schema, integrity,
foreign keys, bundle/model compatibility and every referenced local resource
before confirmation and again before replacement. Uploaded SQL is never executed:
copy validated rows into a database created from trusted application migrations.
Missing resources fail without creating keys, downloading models or changing providers.

After explicit confirmation, reject new admissions and drain actual writers,
including detached provider workers. Recheck expiry and resources, stop the old
lifespan, save an automatic encrypted backup of the current state with the
inspection password, checkpoint SQLite and replace the normalized database and
bundle pointer. Retain a private rollback copy until the new lifespan starts.
Failure preserves or restores the old database and pointer; an unsafe stop or
failed rollback keeps maintenance closed. Restore revokes all sessions, setup
proofs and launch grants, clears transient jobs, and leaves the gateway disabled
and its external observation empty. Require a fresh production login or loopback
launcher grant. Update and Funnel-off guidance remain separate owner actions.

## 12. Character and card asset contract

### 12.1 Custom sprite sheet and material conversion

The v1 custom sheet is a transparent, non-animated PNG:

- exact size: `256 x 448` pixels;
- grid: 4 columns x 7 rows;
- frame: `64 x 64` pixels;
- rows in order: `idle`, `walk`, `listen`, `think`, `talk`, `success`, `offline`;
- four frames per state from left to right;
- RGBA or indexed color with transparency; decoded pixel count and file size are enforced;
- no ancillary text/profile chunks are retained after server re-encoding;
- horizontal direction MAY be rendered by flipping frames; the sheet contains one facing direction.

The protected converter accepts a single static PNG, a bounded ZIP, or a browser-selected folder represented as relative-path/file pairs. A ZIP with root `sprite-pack.json` schema 1 uses its exact seven-state, 28-frame mapping. Without that root manifest, ZIP and folder material are normalized into the same bounded bundle and every PNG is inspected structurally for a four-column/seven-row grid of equal square cells. The converter MUST derive cell size from dimensions and MUST NOT infer meaning from filenames, directories, species labels, example sizes, or visual content. Exactly one structurally valid candidate converts automatically; multiple candidates return canonical previews and require an explicit owner choice; zero candidates fail with actionable guidance. Candidate IDs bind normalized path and bytes, are recomputed on every selection request, and cannot be used to select omitted or changed content.

A single uploaded PNG or compressed ZIP is limited to 16 MiB. ZIP/folder bundles are limited to 64 entries, 8 MiB per member, 64 MiB total expanded bytes, 256 characters per normalized path, and 16 convertible candidates. Paths are normalized POSIX-relative paths. Traversal, backslashes, absolute paths, links, encryption, duplicate names, unsafe image framing, animation, resource-limit violations, and malformed or extra manifest fields fail closed. Non-PNG files and bounded PNGs that are not structural candidates may be ignored and reported; a strict manifest never silently ignores missing, duplicate, or invalid referenced frames. Bundle inspection and candidate selection are authenticated, same-origin, side-effect-free operations and do not persist source material.

`pixel_exact` uses nearest-neighbor sampling only when each source-to-64 axis is an integer upscale or downscale. `pixelize` deterministically contains non-square manifest frames on a transparent bottom-centered square, uses bounded resampling, reduces to at most 64 colors, and thresholds alpha to hard pixels. It reports partial-alpha removal, palette reduction, padding, edge contact, mixed frame dimensions, and bounded unreferenced ZIP members. A warning never becomes silent success: the owner sees the canonical preview/report before download or writeback. Missing/empty frames are fatal and are never copied or synthesized. Only canonical re-encoded PNG bytes enter ordinary asset writeback; source archives/images, manifest text, metadata, ignored members, and conversion diagnostics are not committed automatically.

For structural grid PNGs only, conversion MAY additionally return a nullable `edge_cleanup` option. The detector scans a small source-cell-relative top band for pixels continuous with the preceding row's bottom edge, followed by a transparent separator and independently occupied content in the current cell. It MUST preserve uncertain, deep, connected-to-current-art, or unsupported-border content. The alternative MUST pass normal canonical validation before returning. The normal `asset` remains unchanged; `edge_cleanup.asset`, `affected_frames` (`state` plus zero-based `frame`), and `removed_source_pixels` are bounded owner-only response data. The UI compares the same state/frame in original and cleaned previews and requires an explicit choice before download/writeback. Selection creates no server state and does not overwrite source material. Subsequent position alignment starts from the chosen canonical asset.

After conversion and any required cleanup-version choice, the workspace MUST inspect horizontal alpha-occupancy anchors automatically. It MAY auto-apply bounded, non-clipping offsets only when at least half of the seven states exhibit one consistent per-column displacement pattern; isolated drift, incompatible patterns, clipped shifts, or excessive offsets remain review-only. The composed automatic result MUST pass `POST /api/admin/assets/character/validate` before it becomes downloadable or writable. The owner MAY also preview all suggestions, adjust each frame through labeled X/Y integer-pixel fields or one-pixel controls, and restore the chosen unaligned version. Manual edits remain local drafts until explicit apply and successful protected validation. Every shift MUST keep all non-transparent pixels inside its original `64x64` cell. No automatic change to source files or inference of artistic intent is permitted; deliberate repeated motion can be visually indistinguishable from layout drift, so the owner still reviews all seven states.

Built-in characters are selected by `(pack_id, pack_version)` and validated against a trusted in-process pack registry. A pack manifest owns its bounded option schema and renderer; core configuration/composition treats option keys as opaque and does not branch on species, anatomy, clothing, or locomotion type. A registered pack compiles deterministically into the same canonical sheet, so frontend state logic is identical for humanoids, animals, objects, fantasy creatures, and custom user art. Registry code cannot be supplied through YAML, and pack options cannot contain paths, URLs, executable code, or arbitrary renderer names.

Unknown pack IDs, unsupported versions, unknown or missing option keys, and invalid values fail closed without fallback. Built-in pack output then passes the same canonical sprite validation as custom uploads. Animation timing is configuration-bounded from 80–1000 ms. Reduced motion uses the first frame of each state with no movement/transitions. The semantic row named `walk` means the character's locomotion/activity loop; it does not assert legs or a humanoid gait.

### 12.2 README card

Under 0.4.11 / ADR-059, FR-024 additionally requires the complete `README.md`
delivery and exact content preview defined by the [README export contract](PROFILE_README_EXPORT_CONTRACT_2026-10-12.md).
The private readonly `GET /api/admin/sharing/readme?locale=zh-TW|en` returns the
confirmed public introduction, project links and NPC/visitor entry only after
the current deterministic Pages snapshot matches its verified digest and its
existing locale GIF is checked publicly. It is a UTF-8 Markdown attachment named
`README.md`, no-store/nosniff, with unchanged admin Host/Origin/session checks.
Missing/stale verification, unsafe source, unavailable/mismatched GIF and escaped
content above 500 KiB fail through existing sharing error codes. Both locales
explain the public matching-account repository root and preservation of an
existing README. The existing snippet variants and manual upload path remain.

- canonical view box/output size: `600 x 180` CSS pixels;
- first frame includes character, display name, headline, call to action, and visible RepoNPC identity;
- SVG animation uses allowlisted CSS only and remains understandable when animation is stripped;
- GIF is generated from the canonical frames at build time and loops at a bounded rate;
- PNG is the exact static first-frame rendering;
- user text is length-bounded and XML-escaped; remote fonts/images are forbidden;
- card links are provided by Markdown around the image, never embedded executable behavior.

### 12.3 Visitor chat interface colours and character NPC (0.4.1 FR-050, revised 0.4.4 ADR-051)

The visitor page is a plain chat interface (FR-047, contract §4.0). Its colours come from an owner-selected colour scheme with light and dark variants, not from the character. Only the NPC changes with the character: it is drawn from the same canonical sheet that every built-in pack and custom upload produces, so no species, pack or filename knowledge is needed.

**Retired before implementation (0.4.4)**

- The 0.4.1 sheet-palette derivation (OKLCH clustering of sheet pixels into page colours) and its per-role L/C target table.
- Pack scene providers (hue/accent hints and backdrops). Pack manifests gain no scene field.
- The 0.4.2/0.4.3 `scene_templates.yml` hue-seed templates (`follow_character`, `fixed`, tones).

**Token roles** (closed set, light and dark, `#rrggbb`)

- `background`, `surface`, `surface_alt`, `ink`, `muted_ink`, `accent`, `accent_ink`, `border`, `stage`, `focus`. The 0.4.1 `glow` role is removed.
- The frontend maps each role to a fixed `--scene-<role>` custom property through one mapping.

**Colour-scheme registry (0.4.4, FR-051)**

- `color_schemes.yml` is packaged data, schema-validated at startup, and the only source of scheme colours. Entries hold `id`, `version`, `label` per locale and explicit `light` and `dark` role maps, plus a top-level `aliases` map.
- Load-time validation fails, naming scheme, variant and pair, on: a duplicate or malformed id; a missing locale; a missing or unknown role; a value that is not `#rrggbb`; an unknown field (image, backdrop, pack, species, font or CSS); an alias cycle or dangling alias; and any failing contrast pair:
  - `ink` and `muted_ink` on `background`, `surface` and `surface_alt`: ≥ 4.5:1;
  - `accent_ink` on `accent`: ≥ 4.5:1;
  - `accent`, `border` and `focus` against `background`, `surface` and `surface_alt`: ≥ 3:1.
- Scheme values are never corrected at runtime.
- The starter set (contract §4.5) is `neutral` (default), `ocean`, `forest`, `sunset` and `lavender`. Bundled illustrated backgrounds are not in scope.

**Colour mode (0.4.4, FR-051)**

- `color_mode: system | light | dark` (default `system`) selects the default variant; `system` follows `prefers-color-scheme`.
- `visitor_mode_toggle` (default `true`) shows a light/dark toggle. The visitor's choice is kept only in that browser's `localStorage` (one key). It is never sent, exported or set as a cookie, and it is ignored when the toggle is disabled.
- Both variants are always published. A small same-origin `<head>` script (not inline; CSP unchanged) applies a stored choice before first paint.

**Resolution per role**

1. Owner accent (optional): replaces `accent`; `accent_ink` becomes the scheme's `ink` or `background`, whichever passes. A failing accent is adjusted in lightness, and the adjusted value and reason are shown before saving.
2. The selected scheme's value for the variant.
3. NPC separation (per character): the average colour of the NPC's edge pixels vs `stage` must be ≥ 3:1. If not, only `stage` lightness is adjusted (hue kept); if that is impossible, `stage` becomes a contrasting plate (a disc behind the hero NPC, a ring behind avatars). Text colours never change for the NPC.

**NPC placement**

- The welcome hero (empty conversation) shows the large animated NPC on `stage`, the third-person greeting and suggestion chips.
- Each NPC answer has a small NPC avatar. Only the newest avatar animates (`talking` while streaming, then `idle`); older avatars show a static frame.
- The top bar shows a small status avatar with the available/resting state. Reduced motion shows static frames everywhere.

**Welcome-hero image (optional)**

- Owner images are PNG or WebP only: no SVG, no animation, ≤ 2 MB, 640×360 to 2560×1600. They are decoded under the existing image guards and re-encoded with metadata stripped.
- The image appears only as the backdrop of the welcome hero card behind the large NPC, never behind the sidebar, messages or input. It is decorative (`alt=""`); hero text sits on an opaque `surface` panel, and a `surface`-derived scrim keeps both variants legible.
- Without an image (default), the hero is the plain `surface` colour plus the NPC stage. No pattern or illustration is drawn.

**Frontend**

- Visitor CSS MUST NOT contain literal colours or scheme ids. The fallback token block used before data loads is generated at build time from the registry's default scheme; the style guard fails on any other literal colour.

**Computation and output**

- Tokens are resolved at validation/bundle time, byte-identical for identical inputs, and included with any hero image in the static-site export manifest.
- `character.scene` carries `revision`, `scheme {id, version}`, `color_mode`, `visitor_mode_toggle`, `themes {light, dark}`, `background_url`, `background_scaling`, `background_focus` and `background_dim`. The 0.4.1 `source` field is removed; stage and accent adjustment notices are returned only by the admin preview API.
- The export stores resolved tokens, so a registry change reaches a published site only on the next export.

**Owner background image and preview (0.4.3, FR-052, ADR-050; placement revised 0.4.4)**

- Upload creates a private draft in runtime data (one per owner session, replaced by a new upload, deleted on cancel or after 24 hours). Drafts are never under `assets/`, never served publicly and never exported.
- Admin API (authenticated; mutations need CSRF):
  - `POST /api/admin/assets/scene/background-drafts` (multipart) returns `{draft_id, width, height, format, notices[]}` or a plain-language error;
  - `GET` and `DELETE /api/admin/assets/scene/background-drafts/{id}` (`no-store`, `nosniff`);
  - `POST /api/admin/scene/preview` resolves proposed settings (`color_scheme`, `color_mode`, `visitor_mode_toggle`, `accent`, `background: draft:<id> | current | none`, `focus`, `dim`, `scaling`) and returns the public `character.scene` shape plus notices, persisting nothing;
  - `PUT /api/admin/scene` applies the settings, promotes a referenced draft to `assets/scene/<content-hash>.png|webp` and bumps `character.revision`.
- Preview and publication use the same server resolver, so equal settings give identical scene objects.
- Focus maps to `object-position` inside the hero card; dim is a scrim from `--scene-surface` at a registry-defined opacity per level. `auto` chooses the lowest level at which NPC separation passes without a plate, else the plate.
- Non-blocking notices: upscaling beyond the hero frame, strong cropping in desktop or phone frames, and a busy area behind the NPC.

## 13. Provider interfaces

### 13.1 Chat provider

Every adapter exposes:

```text
capabilities() -> {
  streaming, system_role, structured_output, usage_reporting,
  health_check, max_context_tokens, max_output_tokens
}
generate(messages, response_schema, max_output_tokens, timeout) -> ProviderResult
health() -> ProviderHealth
```

Server-internal optional reasoning support/control metadata records verified support or unknown and the enabled provider control (ADR-055). It adds no public DTO, configuration field or user toggle.

ADR-057 adds optional server-internal `generate_with_progress(..., on_progress,
cancelled) -> ProviderResult`. Activity callbacks carry closed labels only while
the method still returns complete buffered content. This is not unvalidated
answer streaming; the existing buffered interface/capabilities remain. An adapter
without this method generates once through its existing interface. Selected API
services must support standard Chat Completions SSE for native activity; rejection
is a safe failure without a buffered retry or provider switch.

`ProviderResult` contains raw structured/text content, finish reason, nullable usage, provider request ID, and timing. Provider exceptions map to stable internal categories: authentication, rate limit, timeout, unavailable, invalid response, and context overflow.

### 13.2 Embedding provider

```text
identity() -> {adapter, model_id, dimension, normalized, query_prefix, passage_prefix}
embed_query(texts) -> float32 matrices
embed_passages(texts) -> float32 matrices
health() -> ProviderHealth
```

The application validates output shape, finite values, and normalization. Indexing batches may retry transient failures with bounded exponential backoff; runtime queries default to at most two transient attempts within the overall timeout.

External adapters and the built-in `builtin_onnx` adapter MUST expose the identity, `embed_query`, `embed_passages`, and health behavior needed by both the index builder and runtime. The sentence-transformers adapter may implement this contract only in isolated benchmark/build fixtures; it is not a supported production runtime. Provider health, profile probing, and retry orchestration MUST consume this same contract rather than redefine it.

### 13.3 Required adapters and fallback rule

- `openai_compatible`: configurable base URL, key secret, chat model, embedding model, timeout, and optional headers from server-only secrets.
- `vllm`: named preset using the `openai_compatible` transport and embedding identity. It MAY use an explicitly configured private HTTP origin. Chat and embedding have independent base URL/model/key settings because a chat model does not imply `/v1/embeddings` capability. Model listing assists selection; direct bounded capability testing of the typed model is authoritative under section 11.5. The operator remains responsible for a valid chat template and an embedding-capable embedding model.
- `ollama`: private base URL, chat model, embedding model, explicit context/output caps, and health endpoint. Under ADR-055, bounded selected-model `/api/show` preparation establishes supported reasoning controls and a verified native context when available. Boolean-supported reasoning sends `think: true`; named-only controls use the exact advertised supported reasoning default. Legacy positive thinking capability permits `true`; fully unknown controls remain unknown and omit the override to preserve the backend default. Present control metadata must have a correctly typed default belonging to its advertised values; malformed controls/context fail with existing safe provider errors before generation. Insufficient model context must preserve non-AI/manual application startup. RepoNPC MUST NOT infer control support from a model name or silently send `think: false`. Preparation consumes the outer operation budget and does not add repeated metadata calls or generation retries. Each chat request sets `options.num_ctx` to the configured total context, reduced by any smaller verified native model limit, and `options.num_predict` to the effective combined generation ceiling. Complete serialized UTF-8 messages and response schema, output allowance and 256-token framing reserve must fit before `/api/chat`; this is a conservative estimate, not an actual model-tokenizer count. The current configured context default is 32,768, not the model's advertised upper bound. The adapter discards `message.thinking` and validates only final `message.content` under the existing envelope contract. OpenAI-compatible/vLLM requests retain their existing reasoning semantics without invented provider-specific knobs.
- `builtin_onnx` (0.4.0, FR-049): embedding only; loads the pinned, checksum-verified `bge-m3` ONNX artifact from the deployment data directory and runs it on CPU through ONNX Runtime. It is the production default after explicit owner download consent and exposes the same identity/probe contract as external adapters.
- A local sentence-transformers adapter MAY remain as an optional isolated benchmark dependency, but MUST NOT be advertised as the default or required for a production image. Production readiness requires either the downloaded built-in profile or one explicitly configured external profile from Ollama, vLLM, or a generic OpenAI-compatible embeddings service.

The selected chat and embedding adapters are explicit. RepoNPC MUST NOT silently try another provider, model, or cloud endpoint after failure. Provider keys and private base URLs remain protected server state after the narrowly authorized admin input described in section 11.5. They MUST NOT enter public/admin responses, logs, exports, or snapshots. Tests use synthetic canaries only.

## 14. Bundle publication and activation

### 14.1 Immutable bundle layout

Release asset name: `reponpc-index-{bundle_id}.tar.zst`.

```text
manifest.json
checksums.sha256
index.sqlite
public/profile.json
public/character.png
public/card-light-zh-TW.svg
public/card-dark-zh-TW.svg
public/card-light-en.svg
public/card-dark-en.svg
public/card-*.gif
public/card-*.png
```

Archives MUST contain only regular files at normalized relative paths, no symlinks/hardlinks/devices, and no path traversal. Unknown required files or duplicate paths fail validation.

`public/profile.json` uses the internal bilingual schema in section 9.1. The archive verifier MUST validate that complete schema, including both required locales and all required profile/repository/question/character/index fields, before a candidate can activate.

### 14.2 Internal manifest

`manifest.json` canonical JSON fields:

```json
{
  "manifest_schema_version": 1,
  "index_schema_version": 1,
  "bundle_id": "20260810T120000Z-0123456789ab",
  "built_at": "2026-08-10T12:00:00Z",
  "application_compatibility": {
    "minimum": "1.0.0",
    "maximum_exclusive": "2.0.0"
  },
  "config": {
    "repository": "owner/profile",
    "commit_sha": "40hex",
    "path": "reponpc.yml",
    "sha256": "64hex"
  },
  "repositories": [{ "slug": "owner/repo", "commit_sha": "40hex" }],
  "embedding": {
    "adapter": "ollama",
    "model_id": "qwen3-embedding:0.6b",
    "dimension": 1024,
    "normalized": true,
    "query_prefix": "",
    "passage_prefix": ""
  },
  "statistics": { "repositories": 1, "sources": 100, "evidence_records": 500 },
  "files": [{ "path": "index.sqlite", "size": 123, "sha256": "64hex" }]
}
```

The embedding values in this example are illustrative for an Ollama Qwen3 profile; the builder MUST replace dimension/prefix values with the observed probe result and MUST reject a guessed or mismatched identity.

`bundle_id` is UTC build timestamp plus the first 12 hex characters of a deterministic hash over schema, normalized configuration, source commits, parser/chunker version, and embedding identity. Rebuilding identical inputs retains the hash suffix; timestamps are declared non-deterministic metadata.

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

### 14.4 Runtime activation

1. On startup and every 300 seconds by default, fetch stable manifest with `If-None-Match`.
2. If the bundle is already active, update check time only.
3. Download to a unique staging directory with byte/time limits while hashing.
4. Verify outer SHA-256, safe archive structure, all internal checksums, manifest schema/application compatibility, embedding compatibility, required files, and SQLite `PRAGMA quick_check`.
5. Open the candidate database read-only and run a retrieval/card smoke check.
6. Atomically replace an `active` pointer/file only after all checks pass.
7. Keep the current and previous validated bundles; clean older bundles only after the new bundle serves successfully.
8. On failure, delete/quarantine only the candidate, retain current active state, record a safe diagnostic, and retry with bounded backoff.

An admin MAY pin a previously downloaded compatible bundle by ID. Automatic polling then reports a newer version but does not activate it until unpinned.

## 15. Runtime storage, security, and operations

### 15.1 Mutable runtime database

`REPONPC_DATA_DIR/runtime.sqlite` is separate from bundles and contains logical tables:

- `admin_owner`: the sole durable username, Argon2id password hash, and creation time;
- `admin_auth_methods`: one local-password method and/or one unique GitHub numeric identity for the singleton owner, with safe display login metadata;
- `admin_oauth_transactions`: hashed state, encrypted PKCE verifier/setup proof where applicable, bounded intent, expiry, consumption time, and fixed return path;
- `admin_github_credentials`: authenticated-encryption nonce/ciphertext, algorithm/key version, purpose, GitHub user ID/display login, expiry, validation time, and safe status only;
- `admin_setup`: at most one SHA-256 setup-code digest and its creation/expiry times; deleted when consumed;
- `embedding_profiles`: deployment-local profile ID, provider/model labels, encrypted credential reference, private endpoint reference, observed compatibility identity, active/status state, reindex generation, and timestamps; never plaintext credentials or raw provider bodies;
- 0.2.2 adds protected model-connection revisions and independent chat-profile metadata alongside the existing embedding registry. Physical tables, migration numbers, and request DTOs must be documented in the implementation contract preparation step; no schema is implemented by this document update. Secrets are protected as specified in section 11.5 and never placed in the immutable index.
- `admin_sessions`: token hash, CSRF hash, created/seen/idle/absolute expiry, session epoch, revoked time;
- `rate_buckets`: HMAC-derived IP key, window/bucket counters and expiry;
- `daily_usage`: UTC date, accepted requests, reported input/output tokens and estimated cost where configured;
- `bundle_state`: active/previous/pinned IDs, ETags, checks and safe update error;
- `admin_audit`: timestamp, action, target path, result commit, request ID, outcome.
- `github_rate_state`: sanitized anonymous REST/core remaining, reset, retry, and secondary-limit admission state; it contains no token or upstream response body;
- `analysis_batches`, `analysis_batch_items`, `analysis_batch_events`, and `analysis_batch_idempotency_receipts`: owner-scoped durable job state, immutable commits, durable source-consumed markers, bounded safe events and reanalysis request bindings, validated terminal result metadata, idempotency keys, and TTL expiry;
- `analysis_cache_entries`: checksummed derived-index and validated-analysis cache metadata, identity keys, size/LRU metadata, expiry, and the validated result payload. The payload contains repository identity, source-only `facts` (evidence ID/class, path, line range and pinned GitHub URL), localized inference `title`/`statement` and supporting IDs, and the skipped summary; it excludes `excerpt`, raw archives, repository bodies, prompts, and provider bodies.

Raw session/CSRF tokens, raw IPs, raw provider credentials, and raw model/download bodies are never stored. IP keys use HMAC-SHA-256 with `REPONPC_IP_HASH_KEY`. Expired profile, probe, and reindex metadata are periodically removed while the active/previous bundle retention policy remains intact.

### 15.2 Default public controls

- per-IP token bucket: capacity 10, refill 10 requests/minute;
- global concurrent model generations: 2;
- global accepted chat requests per UTC day: 200;
- public request timeout: 180 seconds (hard maximum 300; ADR-057);
- provider connect/read timeouts are bounded inside that deadline;
- response and history limits follow section 4.3.

Rate and budget checks occur before retrieval/provider work. Operators can lower or raise defaults within documented hard limits through environment variables.

### 15.3 Safe logging

Structured logs contain timestamp, severity, event name, request ID, route template, status, latency, index version, provider adapter/model alias, retrieval counts/ranks, token usage, rate outcome, and sanitized error category. They exclude credentials, cookies, CSRF values, raw IPs, full questions, history, prompts, evidence bodies, full answers, uploaded files, and stack traces in public responses.

ADR-064 permits owner-only INFO `chat.answer.no_match.<closed reason lowercased>` events through SafeLogger for both public chat validation and FAQ review, with no fields, alongside existing `chat.answer.segment_dropped.<reason lowercased>` events. The reason set is defined in the owner FAQ diagnostics above. No question/answer text, source/evidence IDs, prompts, thinking, IP or session values enter these events; no daily statistics or raw diagnostic public/SSE fields are added; ADR-066 publishes only the coarse no_match_kind.


`docs/SECURITY.md` MUST document the threat model, trust boundaries, secret handling, injection defenses, SSRF/redirect controls, HTML/Markdown/SVG escaping, admin controls, dependency/secret scanning, disclosure process, and operator checklist.

`docs/OPERATIONS.md` MUST document prerequisites, password/token creation, GitHub Action permissions, installation, HTTPS/reverse proxy, backup, update, pin/rollback, logs/health, provider setup, cost limits, key rotation, upgrade compatibility, and disaster recovery.

### 15.4 GitHub analysis admission and durable work (0.1.7)

- GitHub public analysis performs bounded unauthenticated REST metadata requests for the explicitly selected repositories, then a single immutable-SHA archive request per cache miss. It never resolves trees/blobs one by one in the batch path.
- Archive downloads stream into an item-unique staging directory. Compressed bytes, expanded bytes, regular-file count, individual file bytes, elapsed time, path normalization, duplicate paths, symbolic/hard links, devices, and cancellation are bounded before content reaches the existing filter/index pipeline.
- The central rate state maintains the anonymous REST/core primary budget plus a shared secondary-limit pause, leaves a documented safety reserve, honors `Retry-After` and reset timestamps, and does not poll `/rate_limit` or busy-loop while paused. Initial GitHub in-flight concurrency is one and hard-capped at two total requests.
- The initial scheduler limits whole work items to four, archive staging to one (hard maximum two after measured evidence), local filter/index to two, and GitHub API to two. Provider permits wrap only actual embedding/generation calls. A weighted fair scheduler reserves provider opportunities for public chat before `admin_single` and `admin_batch` work can consume all capacity.
- The active-execution deadline for one repository defaults to 1,800 seconds and is configurable from 1–7,200 seconds. Archive/index/provider-capacity queueing, owner pause, and rate-reset waiting do not spend it. A provider operation defaults to a 300-second socket/inactivity ceiling and may be configured up to 3,600 seconds. Cancellation/restart propagates to every stage; uninterruptible upstream output is discarded; every terminal/recovery path removes staging.
- Failed and `completed_with_errors` batch snapshots/events and validated terminal results expire after 7 days for ADR-052 owner recovery; other terminal batches expire after 24 hours. Startup recovery requeues only immutable fetch/index work or verified cache work. Any item interrupted after provider generation dispatch becomes `needs_retry_confirmation` and is never automatically resubmitted.

### 15.5 Private administration topology and operations CLI (0.1.9, amended by 0.2.0)

- The application MUST keep the admin-capable listener on loopback or a private interface by default. A reverse proxy MAY publish `/`, static assets, and `/api/public/*`, but MUST deny `/admin` and `/api/admin/*` from public Internet networks unless the operator explicitly places those routes behind a private VPN/allowlist.
- A non-standard TCP port is not an access control and MUST NOT be presented as the security solution. The documented headless flow is `ssh -N -L <local-port>:127.0.0.1:<remote-port> user@host`, then opening the same-origin Web Admin at the local end. Tailscale/WireGuard or a firewall-restricted LAN listener are supported alternatives.
- The bounded host CLI MUST expose loopback launch (`admin launch-token`), production bootstrap/recovery (`admin setup-code`, `admin set-password`), runtime (`runtime check`, `runtime backup <path>`), and bundle (`bundle status`, `bundle verify <id>`, `bundle pin <id>`, `bundle unpin`) commands. It MUST use explicit paths/IDs, stable safe errors, and atomic/consistent operations. It MUST NOT become a second public management protocol.

## 16. Frontend behavior

- The visitor route defaults to `/`; admin routes are below `/admin` and are not advertised publicly.
- The UI renders profile and chat as semantic DOM. Canvas MAY render decorative scene elements but MUST NOT contain the only accessible content.
- (0.4.1, FR-050; revised 0.4.4, ADR-051) The visitor page is a simple chat interface (FR-047):
  - a collapsible sidebar with the profile and project cards (a drawer on phones);
  - a top bar with the NPC status avatar, the language switch and the light/dark toggle;
  - a centred chat column with the welcome hero, message bubbles and a pinned input bar.

  Colours come from the owner's colour scheme and mode. The NPC is always the owner's active character, and no page element depicts a fixed species. Visitors can switch only light/dark, when enabled, and the choice stays in their browser's `localStorage`.

  The Character & animation workspace has an 「外觀」 step (formerly 「場景」):
  - a large live preview of the chat page with the active character, in light and dark variants, available and resting states, empty and in-conversation, and reduced motion;
  - (FR-051) a colour-scheme gallery as a keyboard-operable radio group:
    - each tile is a live half-light / half-dark miniature of the chat page with the active character;
    - selection updates the preview, and saving is explicit;
    - a stage adjustment or plate needed for this character is noted in plain language;
    - visitors cannot choose schemes;
  - a colour-mode selector 跟隨系統 / 淺色 / 深色, and a switch 「讓訪客切換淺色／深色」;
  - a custom accent under 「進階」, with any adjustment and its reason shown before saving;
  - (0.4.3, FR-052) welcome-hero image upload by file picker or drag and drop, followed by a preview built from the real visitor components:
    - it shows the image in the welcome hero, the animated active character, the owner's name, and a sample dialog marked 「範例」 with sample chips and the input bar, with no provider call;
    - it offers light/dark, desktop/phone frames, empty/in-conversation, NPC state (待機 / 說話 / 休息中), reduced motion and a before/after comparison;
    - focus point (drag, click or arrow keys, with desktop and phone crop outlines), dim and scaling update it immediately;
    - 「套用」, 「取消」 and 「移除背景圖」 are explicit;
  - 「重設為預設」, which restores `neutral`, `system`, the visitor toggle on and no accent.

  The admin guide mascot renders the active character, with the CSS mascot used only when no character exists.

- Character states map to lifecycle: idle before input, listen while input is active, think during retrieval/provider wait, talk while validated tokens render, success on answered completion, idle on no-match completion (`insufficient_evidence=true`), offline on unavailable/error (ADR-065).
- Suggested questions are keyboard-operable buttons and remain editable before submission. Each list deduplicates exact strings. While the latest assistant turn has in-turn suggestions, omit those strings from the page-level list; hide its entire section and heading when empty. Keep older in-turn buttons, admission, disabled and focus behavior unchanged; restore the full page-level list when the latest assistant turn has no suggestions (ADR-065).
- A temporary no-match turn shows the backend text and one keyboard-accessible 「再問一次」 / "Ask again" button, reusing the failed-turn retryQuestion/onRetry mechanism to submit the same question. Disable it while pending or chat is unavailable. Accept only exact no_match_kind values no_content and temporary; missing or unknown values behave as no_content. Both kinds leave the character idle. Temporary has no in-turn suggestions, so the full page-level suggestions remain. Offline FAQ matching is unchanged and has no temporary kind. Pages visitors receive this frontend only after the owner re-exports and re-uploads the static site (ADR-066).
- No-match exchanges MUST NOT enter client-supplied model history. Retain existing whole-exchange limits, approved-FAQ history, and failed/cancelled-turn exclusion (ADR-065).
- Citation markers focus/scroll to a citation panel and links open immutable GitHub pages with safe `rel` attributes.
- Locale switching changes UI/profile fields and sends the selected locale with chat. It does not discard the visible conversation.
- Offline/setup/model unavailable states explain what visitors can still view and do not expose admin diagnostics. From 0.4.0 (FR-047) the visitor indicator shows only available or resting; it never shows host uptime, provider, model, hardware or cost information. In the exported GitHub Pages site the resting state keeps profile, projects and approved FAQ answers usable and matches typed questions against approved FAQ entries in the browser without generating text.
- The NPC speaks about the owner in the third person. Citations are grouped into one collapsible Sources row with visitor-friendly labels (owner statement, GitHub participation, project documents and code) that expands to file, line and commit permalink details (FR-044).
- Once the backend has validated an answer and begun emitting SSE token events, the visitor UI MUST append those events progressively rather than buffering the complete SSE stream. Chat/profile failures expose a retry or status-recheck action with predictable focus, and citation rendering includes the safe evidence class and source location supplied by the server.
- The admin UI is code-split from the visitor application and clears in-memory CSRF/config drafts on logout.
- Disabled or unavailable admin primary actions MUST have a programmatically associated visible reason, recovery action, and unaffected local alternative where one exists. GitHub read, writeback, publication, and model-analysis readiness are independent capabilities; none may disable unrelated validation, preview, manual authoring, copy, or download.
- No GitHub OAuth or public-read PAT control appears before or after an admin session. Anonymous GitHub rate/capacity messages are contextual to discovery or analysis, bilingual, keyboard/screen-reader accessible, and include manual continuation without a credential prompt.
- Provider-neutral chat/search setup follows section 11.5, and the model-first/manual guided order follows section 11.6. Model secrets use an isolated write-only form, never the guided public draft or raw YAML editor. Empty model configuration does not prevent access to the manual path.
- `docs/SPRITE_FORMAT.md` MUST provide the exact grid diagram, state table, frame timing guidance, examples, validation errors, reduced-motion behavior, and an MIT-compatible template asset.

## 17. Edge cases and required behavior

| Condition                                                           | Required behavior                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| No active bundle on first boot                                      | Public setup state; profile `503 INDEX_UNAVAILABLE`, chat `503 SERVICE_NOT_READY`; health alive, readiness false.                                                                                                                                                                                                                           |
| No active embedding profile                                         | Admin shows the first-use embedding choice (download built-in `bge-m3`, configure another service, or later) and the model-center state; semantic chat returns `503 SERVICE_NOT_READY`; local/manual configuration and profile CRUD remain available. Nothing is downloaded and no adapter is selected without the owner's explicit choice. |
| Built-in model download interrupted, cancelled or checksum mismatch | Keep partial data out of use, allow resume or retry, and keep indexing blocked; never activate an unverified artifact or switch to another service silently.                                                                                                                                                                                |
| Visitor gateway unreachable from the exported Pages site            | Show the resting state and approved-FAQ matching; never show host, model, provider or cost details or an admin diagnostic.                                                                                                                                                                                                                  |
| Person question without a matching owner assertion                  | Answer with participation and project segments; no gap message; no personal-role assertion.                                                                                                                                                                                                                                                 |
| Embedding profile changed or probe/reindex fails                    | Keep the last-known-good profile/bundle active; expose `reindex_required`/safe failure and an explicit retry/recheck action. Never activate a dimension/prefix/model mismatch.                                                                                                                                                              |
| Ollama model missing/pull fails                                     | Show provider-native install/pull error and retain other local admin functions; do not fetch an arbitrary URL or silently switch model/provider.                                                                                                                                                                                            |
| No admin owner on first loopback boot                               | The launcher mints a two-minute fragment-only grant after readiness; `/admin` exchanges it atomically without a registration form. A direct visit explains how to relaunch.                                                                                                                                                                 |
| Local-launch grant expired, replayed, forwarded, or non-loopback    | Generic `401 LOCAL_LAUNCH_DENIED`; mint a new grant through the local launcher. No owner/session is partially created and no failed value is logged.                                                                                                                                                                                        |
| No production admin owner                                           | `/admin` explains the host `setup-code` step; no visitor can register without the 256-bit code.                                                                                                                                                                                                                                             |
| Production setup code expired or reissued                           | Generic `401 SETUP_DENIED`; generate a new host code. No owner/session is partially created.                                                                                                                                                                                                                                                |
| Legacy OAuth/PAT route is requested                                 | Return non-mutating `410 GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED`; do not redirect, accept/decrypt credentials, issue a session, or change owner/setup state.                                                                                                                                                                                |
| Concurrent first-owner submissions                                  | One transaction creates exactly one owner/session; the loser receives `409 SETUP_ALREADY_COMPLETE`.                                                                                                                                                                                                                                         |
| Active index but chat model down                                    | Profile/card remain available; status degraded; chat `503 SERVICE_NOT_READY`; no provider fallback.                                                                                                                                                                                                                                         |
| Model unavailable before guided analysis                            | Preserve selection and owner text; offer immediate manual contribution without requiring preflight, batch creation, or a failed model call.                                                                                                                                                                                                 |
| AI route chosen with one or both analysis roles missing             | Stay in or return to guided model setup, identify the missing role and offer its direct action plus manual continuation. Do not call source/provider work or label a clean deployment as an Ollama failure.                                                                                                                                 |
| Analysis pair selected before the first public bundle               | Permit explicit authenticated selected-only analysis in the same process, while `/readyz` and public chat remain unavailable until separate compatible bundle/public activation succeeds. Analysis must not publish its temporary index.                                                                                                    |
| Anonymous GitHub REST capacity unavailable                          | Keep all local/manual draft functions available, report a sanitized retry time when known, and never offer or select OAuth/PAT/writeback fallback.                                                                                                                                                                                          |
| No GitHub writeback or publication capability                       | Validate, preview, copy, and download remain available; Save/Publish explains the missing capability and its setup/recovery action.                                                                                                                                                                                                         |
| Admin requested through public Internet                             | Reverse proxy/firewall denies `/admin` and `/api/admin`; operator is directed to loopback/SSH/VPN. A non-standard port does not bypass this rule.                                                                                                                                                                                           |
| Embedding query service down                                        | Exact/lexical-only fallback is allowed only if explicitly enabled and visibly reported; default is chat unavailable to preserve retrieval contract.                                                                                                                                                                                         |
| Repository renamed/deleted/private                                  | Index build fails that configured repository; stable manifest is not advanced. Existing bundle remains valid.                                                                                                                                                                                                                               |
| Empty repository/no eligible text                                   | Build emits a warning; repository metadata/owner assertions may remain; zero total evidence fails publication.                                                                                                                                                                                                                              |
| Invalid custom sprite                                               | Admin/build returns row/dimension/format errors; previous asset/bundle remains.                                                                                                                                                                                                                                                             |
| GitHub write conflict                                               | Return `409 CONFIG_CONFLICT` with current blob SHA; never overwrite or auto-merge.                                                                                                                                                                                                                                                          |
| Unknown model source ID                                             | Discard output and return the no-match reply (FR-044); never publish invented citation.                                                                                                                                                                                                                                                     |
| Provider stops mid-generation                                       | Terminal SSE error; no partial unvalidated answer is sent because public output is buffered.                                                                                                                                                                                                                                                |
| Daily budget exhausted                                              | Reject before model call with localized `429`; profile/card remain usable.                                                                                                                                                                                                                                                                  |
| Malicious repository prompt                                         | It remains delimited evidence; no tool/network capability; evaluation security case must pass.                                                                                                                                                                                                                                              |
| File lines changed after indexing                                   | Citation still points to recorded commit SHA and remains stable.                                                                                                                                                                                                                                                                            |
| Browser blocks SVG animation                                        | Static first frame remains complete; generated snippet can use GIF/PNG.                                                                                                                                                                                                                                                                     |
| Concurrent bundle read/activation                                   | In-flight requests retain their opened bundle handle; new requests use new active bundle.                                                                                                                                                                                                                                                   |
| Locale field missing                                                | Required localized field fails configuration validation; optional field follows configured fallback policy.                                                                                                                                                                                                                                 |

For Phase 2 source classification, the exact root manifests `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, and `requirements.txt` are `repository_metadata`. They remain line-addressable `REPOSITORY_FACT` records at the real repository path/commit and use the configured `repository_metadata` retrieval weight. Owner-authored profile, role, summary, and claim text remains `OWNER_ASSERTION` even when it describes a repository. An empty repository is allowed to retain any available repository metadata or owner assertions, but publication still fails when total evidence is zero.

## 18. Explicit v1 exclusions

Private repositories, multi-owner/multi-tenant operation, billing, visitor authentication, OAuth device flow, GitHub-only owner setup, model fine-tuning, autonomous tools, live repository mutation by the model, arbitrary URL/model-archive ingestion, multiple NPCs, navigable worlds, keyboard gameplay, mobile-native apps, externally hosted frontend origins by default (except the owner-configured GitHub Pages origin of the exported share site under FR-047, which receives credential-free CORS to the visitor gateway only), distributed replicas, and a separate vector/database service are outside v1. Visitor traffic/view counts, visitor attachments, readiness tests, cost estimates, code signing and macOS installers are outside the 0.4.0 MVP; browser-local microphone input is post-MVP.

## 19. Implementation and release gates

Work follows `IMPLEMENTATION_PLAN.md`, but a milestone is complete only when its mapped acceptance criteria pass. Before v1 release:

- every FR and NFR has at least one automated or documented acceptance result;
- retrieval and bilingual evaluation thresholds pass on a committed, non-secret fixture corpus;
- Phase 2 formal retrieval acceptance runs a candidate container with only the repository fixture, public questions, and production embedding configuration; the reviewed oracle and scoring remain outside the container;
- Docker inspection proves the candidate has no oracle mount or readable oracle path, runs with `--cpus=4 --memory=8g`, and records the image digest, runtime/host provenance, warm-up policy, and raw timing samples;
- formal benchmark booleans are derived from observed provider identity, isolation/resource evidence, repeatability, and thresholds rather than accepted from caller/candidate flags;
- security tests cover all named trust boundaries;
- current Chrome, Firefox, and Safari plus a real GitHub Profile render are manually verified where automation is insufficient;
- Compose installation succeeds from clean documented prerequisites;
- operations, security, sprite, upgrade, and rollback documentation is complete;
- the owner approves any change to this specification and all ADR statuses are consistent.

## 20. Owner approval record

To approve, the project owner should explicitly state that RepoNPC v1 Technical Specification version `0.1.0` is approved. The approving change must update:

- this document's status to `Approved` and record approval date;
- all `Proposed` ADRs adopted by the approval to `Accepted`;
- any owner-requested exceptions before application implementation starts.

**Approved by:** project owner  
**Latest approved amendment:** Technical Specification 0.4.8 / ADR-055 / OR-029 (2026-10-03), reasoning enabled and independently bounded 16,384-token chat/analysis defaults (§4.3/13.3). The prior 0.4.7 / ADR-054 / OR-028 option A encrypted maintenance backup and same-data-directory restore (§11.7) remains in force. The prior 0.4.6 / ADR-053 / OR-027 A1/F0 visitor gateway freeze remains in force. Local implementation evidence is distinct from external and release acceptance; older notes retain their historical state.
**Earlier amendment:** Technical Specification 0.4.5 / ADR-052 (2026-09-27): official bge-m3 source pin, R08/R11/R12-B minimal closure and the admin maintenance page (FR-049, FR-053, AC-076–AC-079); not implemented. Previous: 0.4.4 / ADR-051 (2026-09-26): simple chat interface, owner-selected fixed colour schemes with light/dark mode and a visitor light/dark toggle; only the NPC follows the character; the owner image is optional and shown in the welcome hero (FR-047/050/051/052, §12.3, AC-068, AC-072–AC-075); not implemented. Previous: 0.4.3 / ADR-050 revised (2026-09-26): templates are colour schemes only (no drawn backdrops); owner background image with private drafts and a realistic visitor-page preview (FR-051/052, §12.3, AC-074–AC-075); not implemented. Previous: 0.4.2 / ADR-050 (2026-09-26): owner-selectable scene templates as registry data. Earlier: 0.4.1 / ADR-049 (2026-09-26): character-driven visitor scene derived from the canonical sheet, with owner overrides and AA contrast solver (FR-050, §12.3, AC-072–AC-073); not implemented. Previous: 0.4.0 / ADR-048 approved 2026-09-26: envelope v2 segment answers, `PARTICIPATION` evidence, coverage check and reviewed FAQ, MVP live chat through an exported GitHub Pages site plus the Tailscale Funnel visitor gateway, Windows PyInstaller/Inno Setup installer, built-in `bge-m3` embedding default and owner-only model guidance (§2.10 and the completion direction contract). Not implemented yet; no acceptance evidence exists. Earlier: 0.3.9 / ADR-046 local publication (2026-09-22); 0.3.1 / ADR-038 controlled analysis recovery (2026-09-17). Same-round retry now requires remaining persisted attempts and active time; exhausted failed items may create an explicit idempotent successor round pinned to their source commit, policy and frozen pair. Migration 26 adds secret-free lineage/failure-stage diagnostics; migration 27 preserves source consumption and bounded request bindings across cleanup. Terminal clocks and `completed_with_errors` behavior are stable across API, SSE and UI. ADR-037 flexible budgets and all earlier amendments remain in force. This correction does not establish full v1 or live-provider acceptance.
**Approved on:** 2026-08-10; Phase 2 closure amendment approved 2026-08-11; first-owner onboarding, personal-deployment convenience, and guided-onboarding amendments approved 2026-08-14; vLLM provider-preset amendment approved 2026-08-15; GitHub identity/connection and bounded batch-analysis amendments approved 2026-08-16; OAuth setup-guidance UX and ENGD-001/002/003/006 amendments approved 2026-08-30; passwordless loopback launch and connection-only GitHub amendment approved 2026-09-04; GitHub OAuth/public-read PAT retirement approved 2026-09-08; provider-neutral model setup approved 2026-09-09; model-first guided workflow approved 2026-09-10; environment-connection editing/deletion approved 2026-09-12; connection rebinding and authenticated session resume approved 2026-09-13; flexible analysis budgets approved 2026-09-14; controlled successor analysis recovery approved 2026-09-17; local publication approved 2026-09-22; completion direction approved 2026-09-26
**Approval scope:** Technical Specification 0.1.0 and OR-001 through OR-007, version 0.1.1 Phase 2 closure decisions recorded in ADR-015, version 0.1.2 first-owner onboarding recorded in OR-008/ADR-016, version 0.1.3 loopback local-launcher defaults recorded in OR-009/ADR-017, version 0.1.4 guided onboarding recorded in OR-010/ADR-018, version 0.1.5 vLLM provider preset recorded in OR-011/ADR-019, historical version 0.1.6 GitHub identity/public-read connection recorded in OR-012/ADR-020, version 0.1.7 immutable public-repository resolver and durable batch analysis authorized by the owner on 2026-08-16 and recorded in ADR-021, historical version 0.1.8 OAuth setup-guidance UX recorded in ADR-022, version 0.1.9 external embedding profiles, deployment-aware password/private admin topology, local-first recovery, and bounded operations CLI recorded in ADR-023 through ADR-026, version 0.2.0 passwordless loopback launch plus connection-only GitHub recorded in ENGD-008/ADR-027, and version 0.2.1 OAuth/public-read PAT retirement plus anonymous REST resolution recorded in ENGD-009/ADR-028. The owner requested an MVP delivery phase; this is a sequencing decision and does not reduce the complete v1 scope except for the explicitly retired OAuth/public-read PAT capability.

### Chat probe parse diagnostics correction (2026-09-12)

For FR-038/040 and AC-054/055/057, chat probes use the selected provider's configured `max_output_tokens` capability instead of a separate 32-token constant. They make one bounded provider call with a 10-second baseline plus one automatic 10-second grace window, for a 20-second total deadline. Under ADR-055, bounded Ollama capability preparation consumes that same outer deadline; generation receives only the remaining time. RepoNPC does not issue a second generation request, activate, retry another model, or switch providers implicitly. The output defaults/ceiling are amended in §4.3; no new configuration field is added.

When an HTTP 200 chat response fails an adapter parse check, `PROVIDER_INVALID_RESPONSE` remains the failure code. The existing authenticated `last_error_message` may additionally contain a fixed application-owned diagnostic prefixed `RepoNPC response check:`. These diagnostics identify JSON/envelope/message/content/termination/usage/id checks and output-limit termination, never arbitrary response values. They are not upstream error quotations or inferred HTTP explanations. Existing HTTP failure messages retain their original language and redaction behavior. Partial or empty output with an observed `length` termination fails the probe with the output-limit diagnostic. Old records cannot recover a discarded parse reason and need explicit retesting. See `docs/CHAT_PROBE_RESPONSE_CHECKS_2026-09-12.md` for evidence and scope.

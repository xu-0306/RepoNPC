# Plan REPONPC-P4-OWNER-ASSETS-PUBLICATION-20260813

## Objective

Implement and verify RepoNPC Delivery Phase 4 owner administration, assets, card outputs, GitHub writeback, and publication with Main retaining every security and shared seam and Luna max owning only frozen sprite-composer and admin-presentation leaves.

## Main model

- Source: `current_conversation`
- Resolved model: ``
- Verification: `unavailable`

## Architecture decision

- Mode: `hybrid_main_seams`
- Profile: `full`
- Advisor required: `false`
- Reasons: Phase 4 crosses authentication, durable sessions, CSRF, GitHub mutation, untrusted image decoding, SVG output, workflow publication, and producer-consumer boundaries that remain Main-owned.; The approved execution playbook exposes deterministic sprite composition as a disjoint worker leaf after the canonical asset contract is frozen.

## Current-state evidence

| Path | Symbol | Observation | Status |
| --- | --- | --- | --- |
| .github/workflows/build-index.yml | Validate, build, publish, publish-manifest steps | The workflow invokes the production publication-last commands in the required order; Phase 4 must integrate generated assets and fault-order evidence without weakening permissions. | observed |
| apps/web/src/features | existing visitor leaves | The verified Phase 3 visitor and character renderer are present as an uncommitted owner-owned baseline; there is no admin feature directory or route. | observed |
| src/reponpc/api/public.py | character and card routes | Public routes already consume bundle character/card bytes and create ETags, but no Phase 4 producer, validator, strict SVG CSP specialization, or admin API exists. | observed |
| src/reponpc/config/models.py | BuiltinCharacterConfig, CustomCharacterConfig, CardConfig | The approved built-in IDs, color contract, canonical custom path, timing, themes, and card revision are already strict typed inputs. | observed |
| src/reponpc/runtime/database.py | MIGRATIONS version 1 | Runtime SQLite already reserves admin_sessions and admin_audit tables but exposes no session/authentication owner methods. | observed |

## Control flow

| ID | Kind | Path | Symbol | Next | Failure path |
| --- | --- | --- | --- | --- | --- |
| FLOW-ADMIN-SESSION | authentication and durable lifecycle | src/reponpc/api/admin.py | admin session routes | src/reponpc/admin/auth.py, src/reponpc/runtime/database.py | Generic localized safe error, no cookie on failure, and no raw credential/session/CSRF value persisted or logged. |
| FLOW-ADMIN-WRITE | producer to external mutation | src/reponpc/api/admin.py | config and asset write routes | src/reponpc/admin/github.py, GitHub contents/actions mock | Reject before mutation for invalid draft/path/image/origin/CSRF; stale SHA maps to CONFIG_CONFLICT without overwrite. |
| FLOW-ASSET-PRODUCER | untrusted bytes to immutable bundle consumer | src/reponpc/cards/assets.py | validate_sprite and compose_character | src/reponpc/cards/render.py, src/reponpc/indexing/pipeline.py, src/reponpc/bundles/archive.py | Invalid or unsafe bytes produce stable ASSET_INVALID detail and never reach preview, GitHub, or bundle mutation. |
| FLOW-CARD-PRODUCER | sanitized output producer to public routes | src/reponpc/cards/render.py | render_card_assets and readme_snippet | bundle public assets, src/reponpc/api/public.py, admin snippet API | Reject unsafe input/URL; never emit active SVG content or remote references. |
| FLOW-PUBLICATION | workflow side-effect sequence | .github/workflows/build-index.yml | publication-last job | immutable release asset, stable-manifest.json, runtime bundle updater | Any validation/build/upload/verification failure exits nonzero before the stable pointer mutation. |

## Invariants

| ID | Class | Statement | Owner | Counterexample | Gates | Oracle origins |
| --- | --- | --- | --- | --- | --- | --- |
| INV-ADMIN-AUTH | critical | Only the configured admin with a current same-origin session and matching CSRF token may access protected operations; rotation, expiry, logout, and logout-all revoke authority durably. | Main-owned Argon2 verifier, RuntimeDatabase session transaction, origin/CSRF dependency, and real HTTP tests | Refresh one session concurrently and use the old cookie or issue a state-changing request with the cookie but a forged CSRF token and hostile Origin. | GATE-ADMIN-AUTH, GATE-PYTHON, GATE-EVALUATION | existing_contract, deterministic_derived, evaluator_authored |
| INV-ADMIN-UI | critical | The code-split admin UI exposes equivalent zh-TW/en validation, preview, conflict, asset, status, and snippet flows with keyboard/focus/mobile accessibility and clears CSRF/drafts on logout. | Main-owned typed admin client/store/components and component/browser integration tests | Create a draft and CSRF token, log out, navigate back, and observe either value or a still-enabled save action. | GATE-WEB, GATE-EVALUATION | existing_contract, deterministic_derived, evaluator_authored |
| INV-ASSET-CANONICAL | critical | Only bounded, decoded, canonical 128x224 non-animated transparent RGBA PNG bytes with nonempty state frames reach preview, GitHub writeback, cards, or bundles, and every consumer receives identical canonical bytes. | Main-owned Pillow decode/re-encode validator and producer-consumer integration tests | Upload an APNG or valid PNG plus trailing script bytes and observe preview success or a GitHub mutation. | GATE-ASSET, GATE-CARD, GATE-EVALUATION | existing_contract, deterministic_derived, evaluator_authored |
| INV-CARD-SAFE | critical | All twelve card variants are deterministic valid 600x180 static-safe assets; SVG and snippets escape hostile text/URLs and public responses apply exact validators and restrictive content headers. | Main-owned card serializer, image/XML parsers, public route tests, and browser injection tests | Use display name </text><script>alert(1)</script> and javascript target text, then parse the produced SVG and public response. | GATE-CARD, GATE-WEB, GATE-EVALUATION | existing_contract, deterministic_derived, evaluator_authored |
| INV-GITHUB-WRITE | critical | Admin reads/writes/dispatch target only the server-fixed public repository, branch, workflow, reponpc.yml, or one flat validated assets/character PNG; stale SHA never overwrites. | Main-owned GitHub adapter/coordinator with exact allowlist and mutation-recording integration mock | Submit assets/character/../workflow.yml or a stale expected blob SHA through the real admin route and observe any external mutation. | GATE-GITHUB-WRITE, GATE-PUBLICATION, GATE-EVALUATION | existing_contract, deterministic_derived, evaluator_authored |
| INV-PRIVACY | critical | Admin credentials, GitHub tokens, raw session/CSRF tokens, full drafts/uploads, private URLs, and upstream bodies never enter public/admin diagnostics, logs, bundles, snapshots, browser code, or persistent rows beyond defined hashes/audit metadata. | Opaque secret types, safe logger, persistence schema, response serializers, and canary scans | Trigger failed login, config validation, asset upload, GitHub failure, and status calls with distinct canaries and scan every sink. | GATE-ADMIN-AUTH, GATE-GITHUB-WRITE, GATE-ASSET, GATE-PYTHON, GATE-WEB, GATE-EVALUATION | existing_contract, deterministic_derived, evaluator_authored |
| INV-PUBLICATION-LAST | critical | The production workflow validates, builds complete generated public assets, uploads and verifies one immutable release asset, then and only then advances the stable manifest; runtime activation retains last known good on failure. | Production CLI/workflow ordering, mutation-recording GitHub adapter, and real bundle consumer lifecycle tests | Inject upload verification failure after asset creation and observe any stable-manifest mutation or last-known-good replacement. | GATE-PUBLICATION, GATE-PYTHON, GATE-EVALUATION | existing_contract, deterministic_derived, evaluator_authored |
| INV-SPRITE-COMPOSITION | critical | Built-in composition deterministically produces every pixel in all 28 canonical frames from allowlisted IDs/colors with the frozen layer order and no implicit fallback. | Pure composer, pixel/golden focused tests, and Main canonical validator integration | Compose twice with one unknown accessory and compare accepted bytes or observe a silent default; then pass output through the real canonical validator. | GATE-SPRITE, GATE-ASSET, GATE-DELTA | existing_contract, deterministic_derived |
| INV-WORKER-ATTRIBUTION | noncritical | Luna leaf acceptance is limited to exact owned-path diff review and executable consumer evidence when shared-workspace fingerprints cannot isolate concurrent Main changes. | Main exact-path diff review, focused leaf gates, and real consumer integration gates, with fingerprint limitations retained | Worker changes assets.py, models.py, pyproject.toml, an existing Phase 3 file, or a campaign artifact. | GATE-DELTA | deterministic_derived |

## Packages and ownership

| ID | Wave | Owner | Depends on | Owned | Prohibited | Gates | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PKG-LUNA-P4-ADMIN-FORM | 3 | worker | PKG-MAIN-P4-BACKEND | apps/web/src/features/admin/AdminWorkspace.tsx, apps/web/src/features/admin/AdminWorkspace.test.tsx | apps/web/src/app/**, apps/web/src/i18n/**, apps/web/src/styles.css, apps/web/package.json, src/**, docs/**, .agent-foreman/** | GATE-WEB | verified |
| PKG-LUNA-P4-SPRITE | 1 | worker | PKG-MAIN-P4-CONTRACTS | src/reponpc/cards/sprite_composer.py, tests/unit/test_sprite_composer.py | src/reponpc/cards/assets.py, src/reponpc/cards/render.py, src/reponpc/config/**, src/reponpc/api/**, src/reponpc/admin/**, src/reponpc/indexing/**, src/reponpc/bundles/**, apps/**, docs/**, README.md, pyproject.toml, uv.lock, reponpc.example.yml, .env.example, .github/**, .agent-foreman/** | GATE-SPRITE, GATE-DELTA | verified |
| PKG-MAIN-P4-BACKEND | 2 | main | PKG-LUNA-P4-SPRITE | src/reponpc/admin, src/reponpc/cards, src/reponpc/api/admin.py, src/reponpc/runtime/database.py, src/reponpc/main.py, src/reponpc/cli.py, src/reponpc/indexing, .github/workflows/build-index.yml, tests | Changing any frozen public endpoint, error code, environment variable, sprite layout, or publication sequence without owner approval | GATE-ADMIN-AUTH, GATE-GITHUB-WRITE, GATE-ASSET, GATE-CARD, GATE-PUBLICATION, GATE-PYTHON | verified |
| PKG-MAIN-P4-CLOSURE | 4 | main | PKG-LUNA-P4-ADMIN-FORM | .agent-foreman/phase4-owner-assets-publication, docs, README.md, .claude/skills/agent-memory/memories/reponpc | Calling RepoNPC v1 complete before Phase 5, Rewriting historical failed evidence | GATE-ADMIN-AUTH, GATE-GITHUB-WRITE, GATE-ASSET, GATE-SPRITE, GATE-CARD, GATE-PUBLICATION, GATE-PYTHON, GATE-WEB, GATE-DELTA, GATE-EVALUATION | verified |
| PKG-MAIN-P4-CONTRACTS | 0 | main |  | .agent-foreman/phase4-owner-assets-publication | Pre-existing Phase 3 production and evidence paths except where Main integration explicitly requires compatible edits | GATE-PLAN | verified |

## Dependency graph

| From | To |
| --- | --- |
| PKG-LUNA-P4-ADMIN-FORM | PKG-MAIN-P4-CLOSURE |
| PKG-LUNA-P4-SPRITE | PKG-MAIN-P4-BACKEND |
| PKG-MAIN-P4-BACKEND | PKG-LUNA-P4-ADMIN-FORM |
| PKG-MAIN-P4-CONTRACTS | PKG-LUNA-P4-SPRITE |

## Acceptance gates

| ID | Scope | Command | Oracle | Artifact | Invariants | Blocking | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GATE-ADMIN-AUTH | runtime | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline pytest -p no:cacheprovider --basetemp D:/RepoNPC/.pytest-tmp/p4-auth tests/integration/test_admin_auth.py tests/security/test_admin_security.py -q | Real HTTP/cookie/runtime SQLite tests cover Argon2 generic failure and backoff, Secure HttpOnly SameSite Strict __Host cookie, origin+CSRF, idle/absolute expiry, atomic rotation, restart, logout and logout-all without raw token/hash leakage. | .agent-foreman/phase4-owner-assets-publication/artifacts/gate-admin-auth.txt | INV-ADMIN-AUTH, INV-PRIVACY | true | passed |
| GATE-ASSET | integration | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline pytest -p no:cacheprovider --basetemp D:/RepoNPC/.pytest-tmp/p4-assets tests/unit/test_sprite_composer.py tests/unit/test_sprite_assets.py tests/integration/test_admin_assets.py tests/integration/test_asset_bundle_consumer.py -q | Valid built-in/custom sprites become identical deterministic canonical bytes for preview, GitHub and bundle consumers; wrong dimensions, APNG, polyglot, bomb, metadata, opacity, empty state and filename cases fail before mutation. | .agent-foreman/phase4-owner-assets-publication/artifacts/gate-assets.txt | INV-ASSET-CANONICAL, INV-SPRITE-COMPOSITION, INV-PRIVACY | true | passed |
| GATE-CARD | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline pytest -p no:cacheprovider --basetemp D:/RepoNPC/.pytest-tmp/p4-card tests/unit/test_card_rendering.py tests/integration/test_card_producer_consumer.py tests/security/test_card_injection.py -q | XML/image parsers validate every 600x180 variant and complete first frame; hostile bilingual text and URLs cannot create active/remote SVG content; ETags, headers, revisions and parsed Markdown snippets are exact. | .agent-foreman/phase4-owner-assets-publication/artifacts/gate-card.txt | INV-ASSET-CANONICAL, INV-CARD-SAFE | true | passed |
| GATE-DELTA | integration | rtk proxy D:/RepoNPC/.venv/Scripts/python.exe C:/Users/xu/.codex/skills/agent-foreman/scripts/guard_delta.py --plan .agent-foreman/phase4-owner-assets-publication/plan.json --package PKG-LUNA-P4-SPRITE --dispatch-manifest .agent-foreman/phase4-owner-assets-publication/fingerprints/dispatch-manifest.json --handoff-manifest .agent-foreman/phase4-owner-assets-publication/fingerprints/handoff-manifest.json | Only the two Luna-owned sprite composer files differ from the dispatch snapshot; no prohibited or pre-existing Phase 3/user path is attributed to the worker. | .agent-foreman/phase4-owner-assets-publication/artifacts/gate-delta.json | INV-WORKER-ATTRIBUTION | false | failed |
| GATE-EVALUATION | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline pytest -p no:cacheprovider --basetemp D:/RepoNPC/.pytest-tmp/p4-eval .agent-foreman/phase4-owner-assets-publication/evaluation/probes -q | A fresh read-only evaluator's eight CSRF, SHA conflict, malicious PNG, sprite-consumer, card injection, publication-fault, admin UI, and secret-canary probes all exit 0 against production entrypoints without production writes. | .agent-foreman/phase4-owner-assets-publication/evaluation/evaluation-phase4.json | INV-ADMIN-AUTH, INV-GITHUB-WRITE, INV-ASSET-CANONICAL, INV-CARD-SAFE, INV-PUBLICATION-LAST, INV-ADMIN-UI, INV-PRIVACY | true | passed |
| GATE-GITHUB-WRITE | integration | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline pytest -p no:cacheprovider --basetemp D:/RepoNPC/.pytest-tmp/p4-github tests/integration/test_admin_github.py tests/security/test_admin_writeback.py -q | Real admin routes and mutation-recording mock prove side-effect-free preview, exact path/repository/branch/workflow policy, mandatory blob SHA, 409 conflict without overwrite, validated bytes only, safe audit, and no token/body leakage. | .agent-foreman/phase4-owner-assets-publication/artifacts/gate-github-write.txt | INV-GITHUB-WRITE, INV-PRIVACY | true | passed |
| GATE-PLAN | integration | rtk proxy D:/RepoNPC/.venv/Scripts/python.exe C:/Users/xu/.codex/skills/agent-foreman/scripts/validate_plan.py .agent-foreman/phase4-owner-assets-publication/plan.json | Validator exits 0 with full profile, resolved contracts, acyclic ownership, exact worker scope, referenced invariants/gates, and no placeholders. | .agent-foreman/phase4-owner-assets-publication/artifacts/gate-plan.txt | INV-ADMIN-AUTH, INV-GITHUB-WRITE, INV-ASSET-CANONICAL, INV-CARD-SAFE, INV-PUBLICATION-LAST | true | passed |
| GATE-PUBLICATION | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline pytest -p no:cacheprovider --basetemp D:/RepoNPC/.pytest-tmp/p4-publication tests/integration/test_publication_last.py tests/integration/test_github_publication.py tests/integration/test_bundle_producer_consumer.py tests/integration/test_phase4_publication.py -q | A successful production flow generates assets, publishes/verifies immutable bytes, advances the manifest last, and activates them; each injected earlier-stage failure records zero stable-pointer mutations and preserves the active bundle. | .agent-foreman/phase4-owner-assets-publication/artifacts/gate-publication.txt | INV-GITHUB-WRITE, INV-PUBLICATION-LAST | true | passed |
| GATE-PYTHON | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline pytest -p no:cacheprovider --basetemp D:/RepoNPC/.pytest-tmp/p4-all tests -q | All Python unit, contract, integration, security, evaluation and smoke tests collect and pass except explicitly documented environment-dependent skips; no pre-existing Phase 3 behavior regresses. | .agent-foreman/phase4-owner-assets-publication/artifacts/gate-python.txt | INV-ADMIN-AUTH, INV-GITHUB-WRITE, INV-ASSET-CANONICAL, INV-SPRITE-COMPOSITION, INV-CARD-SAFE, INV-PUBLICATION-LAST, INV-PRIVACY | true | passed |
| GATE-SPRITE | component | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline pytest -p no:cacheprovider --basetemp D:/RepoNPC/.pytest-tmp/p4-sprite tests/unit/test_sprite_composer.py -q | Focused tests prove 128x224 RGBA output, all 28 frames and layer order, deterministic bytes, exact palette substitution, and explicit unknown ID/color rejection. | .agent-foreman/phase4-owner-assets-publication/artifacts/gate-sprite.txt | INV-SPRITE-COMPOSITION | true | passed |
| GATE-WEB | system | rtk proxy pnpm run web:check | Prettier, ESLint, TypeScript, all component tests and production build pass; admin is code-split, bilingual, keyboard/mobile accessible, clears CSRF/drafts on logout, and built output contains no secret canaries. | .agent-foreman/phase4-owner-assets-publication/artifacts/gate-web.txt | INV-CARD-SAFE, INV-ADMIN-UI, INV-PRIVACY | true | passed |

## Evidence ledger

| ID | Actor | Gate | Observed | Artifact | Class |
| --- | --- | --- | --- | --- | --- |
| EVID-P4-ASSET | gate_runner | GATE-ASSET | 18 passed. | .agent-foreman/phase4-owner-assets-publication/integrations/integration-phase4.json | deterministic |
| EVID-P4-AUTH | gate_runner | GATE-ADMIN-AUTH | 8 passed; one upstream TestClient deprecation warning. | .agent-foreman/phase4-owner-assets-publication/integrations/integration-phase4.json | deterministic |
| EVID-P4-CARD | gate_runner | GATE-CARD | 5 passed. | .agent-foreman/phase4-owner-assets-publication/integrations/integration-phase4.json | deterministic |
| EVID-P4-DELTA | gate_runner | GATE-DELTA | Failed and attribution-limited because concurrent Main changes, caches, test temporaries, and campaign artifacts contaminated the fingerprint; result is retained and is not a product correctness oracle. | .agent-foreman/phase4-owner-assets-publication/fingerprints/handoff-manifest.json | deterministic |
| EVID-P4-EVALUATION | evaluator | GATE-EVALUATION | 8 fresh production-boundary probes passed (7 Python, 1 AdminWorkspace); one upstream TestClient deprecation warning. | .agent-foreman/phase4-owner-assets-publication/evaluation/artifacts/gate-evaluation-final.txt | deterministic |
| EVID-P4-GITHUB | gate_runner | GATE-GITHUB-WRITE | 7 passed; one upstream TestClient deprecation warning. | .agent-foreman/phase4-owner-assets-publication/integrations/integration-phase4.json | deterministic |
| EVID-P4-PUBLICATION | gate_runner | GATE-PUBLICATION | 23 passed; one upstream TestClient deprecation warning. | .agent-foreman/phase4-owner-assets-publication/integrations/integration-phase4.json | deterministic |
| EVID-P4-PYTHON | gate_runner | GATE-PYTHON | 461 passed, 3 skipped; one upstream TestClient deprecation warning. | .agent-foreman/phase4-owner-assets-publication/integrations/integration-phase4.json | deterministic |
| EVID-P4-SPRITE | gate_runner | GATE-SPRITE | 6 focused sprite tests passed; composed 128x224 RGBA bytes passed the real canonical validator. | .agent-foreman/phase4-owner-assets-publication/integrations/integration-phase4.json | deterministic |
| EVID-P4-WEB | gate_runner | GATE-WEB | Prettier, ESLint with zero errors, TypeScript, 13 tests, and production build passed; five Fast Refresh warnings; separate AdminPage chunk emitted. | .agent-foreman/phase4-owner-assets-publication/integrations/integration-phase4.json | deterministic |

## Stop conditions

- Stop and ask the owner before changing a frozen public endpoint, error code, environment variable, cookie/session policy, GitHub permission, sprite layout, card size, publication order, trust model, hosted dependency/cost, or v1 scope.
- Stop worker execution when any unowned path or Main-owned security/lifecycle/producer-consumer decision is required.
- Switch the affected frozen implementation leaf to a Terra max worker only after deterministic focused/aggregate gate failure, unauthorized delta, or Main diff review demonstrates inadequate Luna output.
- Do not declare Phase 4 verified while any blocking gate or fresh evaluator probe is failed or not run; do not call RepoNPC v1 complete before Phase 5.

## Fallback

- Mode: `main_takeover`
- Triggers: One failed precise repair of a critical invariant; Unauthorized worker delta; Main would need to rewrite more than 60 percent of worker-owned changed lines; Two integration repair rounds fail; Luna quality is deterministically inadequate; then freeze and dispatch an owner-authorized Terra max repair package for the same or narrower scope

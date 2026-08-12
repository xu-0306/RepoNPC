# Plan REPONPC-P3-FOUNDATIONS-20260812

## Objective

Freeze the Phase 3 provider/runtime/frontend foundations and deliver one bounded canonical character-renderer leaf without transferring public API, network, security, lifecycle, or integration authority from Main.

## Main model

- Source: `current_conversation`
- Resolved model: ``
- Verification: `unavailable`

## Architecture decision

- Mode: `hybrid_main_seams`
- Profile: `full`
- Advisor required: `false`
- Reasons: Phase 3 crosses provider network, secret, runtime persistence, SSE, answer validation, accessibility, and producer-consumer boundaries that remain Main-owned.; The approved playbook exposes the canonical character renderer as a disjoint presentational leaf after the seven-state sprite contract is frozen.

## Current-state evidence

| Path | Symbol | Observation | Status |
| --- | --- | --- | --- |
| apps/web/src/app/App.tsx | App | The current frontend is a bilingual semantic setup shell and contains no character renderer or chat lifecycle controller. | observed |
| baseline | focused checks | Focused Python baseline passed 22 and skipped 2 using a workspace basetemp; pnpm web format/lint/typecheck/unit/build passed; git diff --check passed with line-ending warnings only. | observed |
| src/reponpc/indexing/sources.py | EmbeddingProvider | Phase 2 already freezes identity, query, and passage embedding methods but does not define Phase 3 health ownership or the chat provider contract. | observed |
| src/reponpc/main.py | create_app | FastAPI owns runtime initialization, bundle polling, same-origin built web serving, request IDs, and public security headers; provider lifecycle is not yet attached. | observed |
| tests/mocks/servers.py | create_mock_app | A deterministic provider mock already exposes health, capabilities, generation, normalized failures, and mutation accounting without outbound network access. | observed |

## Control flow

| ID | Kind | Path | Symbol | Next | Failure path |
| --- | --- | --- | --- | --- | --- |
| FLOW-CHARACTER-LEAF | presentational leaf | apps/web/src/features/character/CharacterRenderer.tsx | CharacterRenderer | future Main-owned visitor lifecycle composition | Invalid state is prevented by the frozen type; reduced motion renders frame zero and accessible state text remains present. |
| FLOW-PROVIDER-CONTRACT | provider boundary | src/reponpc/providers/contracts.py | ChatProvider and RuntimeEmbeddingProvider | future concrete OpenAI-compatible/Ollama adapters, future Main-owned chat orchestration | Stable safe provider error category; never expose upstream body or choose a fallback adapter. |
| FLOW-PUBLIC-RUNTIME | application lifecycle | src/reponpc/main.py | create_app | src/reponpc/api/public.py:create_public_router, built React assets | Setup/degraded status remains safe and same-origin; this campaign does not attach provider network clients. |

## Invariants

| ID | Class | Statement | Owner | Counterexample | Gates | Oracle origins |
| --- | --- | --- | --- | --- | --- | --- |
| INV-ATTRIBUTION | noncritical | The Luna worker changes only its three exact owned files and does not overwrite pre-existing user edits or campaign control artifacts. | Dispatch fingerprint and Main delta guard | The handoff changes App.tsx, package manifests, i18n contracts, normative docs, or an existing user-modified path. | GATE-DELTA | deterministic_derived |
| INV-CHARACTER-RENDERER | critical | The renderer maps all seven canonical states to rows 0-6, frames to columns 0-3, disables motion at frame zero when reduced motion is requested, preserves pixel rendering, and exposes an accessible state label. | Frozen CharacterState mapping plus deterministic component and static-markup tests | Render offline with reduced motion and observe a nonzero row, nonzero frame, active animation, or no accessible label. | GATE-CHARACTER-LEAF, GATE-WEB | existing_contract, deterministic_derived |
| INV-PROVIDER-CONTRACT | critical | All future chat adapters share one strict RepoNPC-owned capability/result/health/error contract and runtime embedding reuses the Phase 2 identity contract. | Typed provider protocols and deterministic contract tests | Construct a provider error with a private URL in its cause and observe that string conversion contains the URL or an unknown failure category is accepted. | GATE-PROVIDER-CONTRACT | existing_contract, deterministic_derived |
| INV-SAME-ORIGIN-SECRET-SAFE | critical | The existing same-origin frontend and public setup boundary remain intact and built assets contain no provider secret or private URL canary. | FastAPI static route and secret-canary integration test | Build the frontend with recognizable provider canaries and find either canary in dist or a cross-origin provider fetch in the component leaf. | GATE-SAME-ORIGIN, GATE-WEB | existing_contract, deterministic_derived |

## Packages and ownership

| ID | Wave | Owner | Depends on | Owned | Prohibited | Gates | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PKG-LUNA-CHARACTER | 1 | worker | PKG-MAIN-P3-FOUNDATIONS | apps/web/src/features/character/CharacterRenderer.tsx, apps/web/src/features/character/CharacterRenderer.css, apps/web/src/features/character/CharacterRenderer.test.tsx | apps/web/src/app/App.tsx, apps/web/src/app/App.test.ts, apps/web/src/i18n/messages.ts, apps/web/src/styles.css, apps/web/package.json, package.json, pnpm-lock.yaml, src/**, docs/**, README.md, reponpc.example.yml, .env.example, .agent-foreman/phase3-grounded-visitor/plan.json | GATE-CHARACTER-LEAF, GATE-DELTA | in_progress |
| PKG-MAIN-INTEGRATION | 2 | main | PKG-LUNA-CHARACTER | .agent-foreman/phase3-grounded-visitor/artifacts, .agent-foreman/phase3-grounded-visitor/fingerprints, .agent-foreman/phase3-grounded-visitor/handoffs, .agent-foreman/phase3-grounded-visitor/integrations, .agent-foreman/phase3-grounded-visitor/evaluation, .agent-foreman/phase3-grounded-visitor/evidence-ledger.jsonl, .agent-foreman/phase3-grounded-visitor/plan.json, .agent-foreman/phase3-grounded-visitor/plan.md | Pre-existing user-owned modified documentation and contract test paths | GATE-PROVIDER-CONTRACT, GATE-SAME-ORIGIN, GATE-CHARACTER-LEAF, GATE-WEB, GATE-DELTA | frozen |
| PKG-MAIN-P3-FOUNDATIONS | 0 | main |  | src/reponpc/providers/contracts.py, src/reponpc/providers/__init__.py, tests/contract/test_chat_provider_contract.py | README.md, docs/OPERATIONS.md, docs/P2_FOUNDATION_HANDOFF.md, docs/PROJECT_CONTEXT.md, docs/SUBAGENT_EXECUTION_PLAYBOOK.md, tests/contract/test_phase2_closure_spec.py, apps/web/src/features/character/** | GATE-PROVIDER-CONTRACT, GATE-SAME-ORIGIN | implemented |

## Dependency graph

| From | To |
| --- | --- |
| PKG-LUNA-CHARACTER | PKG-MAIN-INTEGRATION |
| PKG-MAIN-P3-FOUNDATIONS | PKG-LUNA-CHARACTER |

## Acceptance gates

| ID | Scope | Command | Oracle | Artifact | Invariants | Blocking | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GATE-CHARACTER-LEAF | component | rtk proxy pnpm --dir apps/web exec vitest run src/features/character/CharacterRenderer.test.tsx | Focused tests cover all seven row mappings, columns 0-3, reduced-motion frame zero with no animation, pixelated rendering, duration bounds, and accessible static markup. | .agent-foreman/phase3-grounded-visitor/artifacts/gate-character-leaf.txt | INV-CHARACTER-RENDERER | true | not_run |
| GATE-DELTA | integration | rtk proxy D:/RepoNPC/.venv/Scripts/python.exe C:/Users/xu/.codex/skills/agent-foreman/scripts/guard_delta.py --plan .agent-foreman/phase3-grounded-visitor/plan.json --package PKG-LUNA-CHARACTER --dispatch-manifest .agent-foreman/phase3-grounded-visitor/fingerprints/dispatch-manifest.json --handoff-manifest .agent-foreman/phase3-grounded-visitor/fingerprints/handoff-manifest.json | Only the three Luna-owned character renderer files differ from the dispatch snapshot; pre-existing dirty files and every prohibited path are unchanged by the worker. | .agent-foreman/phase3-grounded-visitor/artifacts/gate-delta.json | INV-ATTRIBUTION | true | not_run |
| GATE-PROVIDER-CONTRACT | integration | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline pytest -p no:cacheprovider --basetemp D:/RepoNPC/.pytest-tmp/phase3-provider-contract tests/contract/test_embedding_provider_contract.py tests/contract/test_chat_provider_contract.py -q | Both runtime-checkable protocols accept conforming fakes, reject missing methods structurally, preserve Phase 2 embedding identity, bound capabilities, and expose only generic stable provider errors. | .agent-foreman/phase3-grounded-visitor/artifacts/gate-provider-contract.txt | INV-PROVIDER-CONTRACT | true | not_run |
| GATE-SAME-ORIGIN | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline pytest -p no:cacheprovider --basetemp D:/RepoNPC/.pytest-tmp/phase3-same-origin tests/integration/test_static_web.py tests/integration/test_mvp_api.py -q | The real FastAPI entrypoint serves built assets under one origin, setup/status remain safe, and built assets contain no provider-secret or private-URL canary. | .agent-foreman/phase3-grounded-visitor/artifacts/gate-same-origin.txt | INV-SAME-ORIGIN-SECRET-SAFE | true | not_run |
| GATE-WEB | system | rtk proxy pnpm run web:check | Prettier, ESLint, TypeScript, all Vitest tests, and the Vite production build pass with the renderer included and no new dependency. | .agent-foreman/phase3-grounded-visitor/artifacts/gate-web.txt | INV-SAME-ORIGIN-SECRET-SAFE, INV-CHARACTER-RENDERER | true | not_run |

## Evidence ledger

No evidence has been recorded.

## Stop conditions

- Stop and ask the owner before changing a public endpoint, SSE event, stable error code, environment variable, trust boundary, provider fallback behavior, hosted dependency, sprite contract, or v1 scope.
- Stop worker execution when any unowned path or Main-owned lifecycle/security decision is required.
- Switch implementation repair to Terra only after a deterministic focused or aggregate quality failure, unauthorized delta, or Main inspection finding demonstrates inadequate Luna output.

## Fallback

- Mode: `main_takeover`
- Triggers: One failed precise repair of a critical invariant; Unauthorized worker delta; Main would need to rewrite more than 60 percent of worker-owned changed lines; Two integration repair rounds fail; Luna quality is deterministically inadequate, in which case the owner-authorized Terra worker receives a newly frozen repair package

# Plan REPONPC-P3-CLOSURE-20260812

## Objective

Verify complete RepoNPC Delivery Phase 3 grounded chat and visitor experience after delegated implementation, Main integration, fresh falsification, browser, and deployment gates.

## Main model

- Source: `current_conversation`
- Resolved model: ``
- Verification: `unavailable`

## Architecture decision

- Mode: `hybrid_main_seams`
- Profile: `full`
- Advisor required: `false`
- Reasons: Main retained provider selection, transport, lifecycle, grounding, persistence, limits, cancellation, public API, and integration seams.; The owner authorized Luna max leaf implementation with Terra fallback; bounded presentation and deterministic quality-evaluation leaves were delegated while executable aggregate gates remained authoritative.

## Current-state evidence

| Path | Symbol | Observation | Status |
| --- | --- | --- | --- |
| .agent-foreman/phase3-grounded-visitor/evaluation/fresh/evaluation.json | post-repair evaluation | Fresh read-only evaluator reports backend 6/6 and Edge 6/6 with no P0/P1/P2 finding. | observed |
| apps/web/src/app/App.tsx | App | The semantic bilingual visitor consumes same-origin profile and typed SSE, preserves history across locale changes, and owns accessible character lifecycle state. | observed |
| src/reponpc/chat/answers.py | validate_answer | Complete buffered model output is converted to validated text and backend-owned immutable citations or localized abstention. | observed |
| src/reponpc/chat/service.py | GroundedChatService.answer | One limit permit and bundle handle bound retrieval, embedding, provider generation, validation, shared deadline, and cooperative cancellation. | observed |
| src/reponpc/main.py | create_app | Production assembly selects exactly one configured chat and embedding provider, attaches health lifecycle, public limits, same-origin web, and pure-ASGI response headers. | observed |

## Control flow

| ID | Kind | Path | Symbol | Next | Failure path |
| --- | --- | --- | --- | --- | --- |
| FLOW-CHAT | producer-consumer | POST /api/public/chat/stream -> GroundedChatService.answer -> validate_answer -> delivery_events | chat_stream | FLOW-VISITOR | Pre-stream failures use common JSON; post-start failure has one error terminal; disconnect emits no response. |
| FLOW-PROVIDER | provider lifecycle | environment -> create_app -> ProviderRuntime -> selected adapter | _configure_provider_lifecycle | FLOW-CHAT | Selected provider remains safely unavailable; no cloud, model, or adapter fallback is constructed. |
| FLOW-VISITOR | same-origin browser | React App -> profile/status/chat SSE -> semantic DOM and CharacterRenderer | App |  | Setup/offline/error remain accessible and profile content remains usable without leaking server configuration. |

## Invariants

| ID | Class | Statement | Owner | Counterexample | Gates | Oracle origins |
| --- | --- | --- | --- | --- | --- | --- |
| INV-CLOSURE-EVIDENCE | noncritical | Final Phase 3 status is supported by current aggregate, browser, Docker, fresh evaluator, hygiene, and canonical Foreman artifacts without rewriting historical failures. | Main integration record, append-only closure ledger, Foreman validator, and project memory | Remove the Docker/fresh evaluator artifact or mark the old GATE-DELTA passed and still validate closure. | GATE-PYTHON-ALL, GATE-QUALITY, GATE-WEB, GATE-FRESH-BACKEND, GATE-FRESH-BROWSER, GATE-DOCKER, GATE-HYGIENE, GATE-FOREMAN | deterministic_derived, evaluator_authored |
| INV-GROUNDED-ANSWER | critical | Only fully validated evidence-backed material is published; citations resolve to reviewed evidence and backend-owned immutable locations; unsupported and unasserted person claims fail closed. | validate_answer, GroundedChatService, deterministic scenario scorer, and grounding security tests | Cite an unrelated OWNER_ASSERTION for 'Alice founded the company' or emit an extra unreviewed citation and obtain a supported answer/perfect score. | GATE-QUALITY, GATE-PYTHON-ALL, GATE-FRESH-BACKEND | existing_contract, deterministic_derived, evaluator_authored |
| INV-PROVIDER-RUNTIME | critical | OpenAI-compatible, Ollama, and local runtime embedding paths obey one safe typed contract, exact provider selection, bounded retry/deadline, readiness lifecycle, and no silent fallback. | ProviderRuntime, concrete adapters, production assembly, and provider contract/integration tests | Configure Ollama/local, booby-trap cloud constructors, fail local health, and observe any cloud construction or ready state. | GATE-PYTHON-ALL, GATE-FRESH-BACKEND, GATE-DOCKER | existing_contract, deterministic_derived, evaluator_authored |
| INV-SECRET-SAME-ORIGIN | critical | Provider secrets/private URLs remain server-only and production frontend/API remain same-origin with restrictive security headers and safe logs/errors. | environment assembly, provider transports, pure-ASGI response middleware, same-origin app, and security regression tests | Inject a secret/private URL canary into provider failure and find it in public response, browser build, log, or Edge console/network output. | GATE-PYTHON-ALL, GATE-WEB, GATE-FRESH-BACKEND, GATE-FRESH-BROWSER, GATE-DOCKER | existing_contract, deterministic_derived, evaluator_authored |
| INV-SSE-LIMITS-CANCEL | critical | Public chat has stable validated SSE terminals, correlated safe diagnostics, one overall deadline, cost-before-work admission, and silent bounded disconnect cancellation. | pure-ASGI public boundary, chat_stream, ChatLimits, GroundedChatService, and direct-ASGI integration probes | Send body then immediate http.disconnect while answer blocks and observe an unfinished ASGI task or any response bytes. | GATE-PYTHON-ALL, GATE-FRESH-BACKEND, GATE-DOCKER | existing_contract, deterministic_derived, evaluator_authored |
| INV-VISITOR | critical | The same-origin visitor is responsive, bilingual, semantic, keyboard/named-control accessible, reduced-motion aware, citation safe, and preserves conversation across locale changes. | React semantic DOM, typed SSE client, CharacterRenderer, web gates, and real Edge browser probes | Populate chat at 390px, switch locale, and observe overflow, lost turns, unsafe citation rel/href, wrong html lang, or animated nonzero frame under reduced motion. | GATE-WEB, GATE-FRESH-BROWSER, GATE-DOCKER | existing_contract, deterministic_derived, evaluator_authored |

## Packages and ownership

| ID | Wave | Owner | Depends on | Owned | Prohibited | Gates | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PKG-MAIN-P3-CLOSURE | 2 | main | PKG-TERRA-QUALITY | .agent-foreman/phase3-closure/**, .claude/skills/agent-memory/memories/reponpc/**, README.md, docs/PROJECT_CONTEXT.md, docs/SUBAGENT_EXECUTION_PLAYBOOK.md, tests/contract/test_phase2_closure_spec.py | Historical phase3-grounded-visitor evidence except evaluator-owned post-repair refresh | GATE-PYTHON-ALL, GATE-QUALITY, GATE-WEB, GATE-FRESH-BACKEND, GATE-FRESH-BROWSER, GATE-DOCKER, GATE-HYGIENE, GATE-FOREMAN | verified |
| PKG-MAIN-P3-SEAMS | 0 | main |  | src/reponpc/providers/**, src/reponpc/chat/**, src/reponpc/api/public.py, src/reponpc/main.py, apps/web/src/app/**, apps/web/src/i18n/**, apps/web/src/styles.css | Owner-modified unrelated documentation outside Phase 3 status lines | GATE-PYTHON-ALL, GATE-WEB, GATE-FRESH-BACKEND, GATE-FRESH-BROWSER, GATE-DOCKER | verified |
| PKG-TERRA-QUALITY | 1 | worker | PKG-MAIN-P3-SEAMS | tests/fixtures/chat/answer_quality_scenarios.json, tests/eval/test_chat_answer_quality.py | src/**, apps/**, docs/**, .agent-foreman/** | GATE-QUALITY, GATE-PYTHON-ALL | verified |

## Dependency graph

| From | To |
| --- | --- |
| PKG-MAIN-P3-SEAMS | PKG-TERRA-QUALITY |
| PKG-TERRA-QUALITY | PKG-MAIN-P3-CLOSURE |

## Acceptance gates

| ID | Scope | Command | Oracle | Artifact | Invariants | Blocking | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GATE-DOCKER | runtime | rtk proxy powershell -NoProfile -Command <Docker PATH plus pytest tests/smoke/test_container.py --junitxml=.agent-foreman/phase3-grounded-visitor/artifacts/gate-docker-final.xml> | Current Phase 3 Compose image builds, becomes healthy, restarts, and preserves runtime volume state: 1 passed, 0 failures/errors/skips. | .agent-foreman/phase3-grounded-visitor/artifacts/gate-docker-final.xml | INV-PROVIDER-RUNTIME, INV-SSE-LIMITS-CANCEL, INV-VISITOR, INV-SECRET-SAME-ORIGIN, INV-CLOSURE-EVIDENCE | true | passed |
| GATE-FOREMAN | integration | rtk proxy D:/RepoNPC/.venv/Scripts/python.exe C:/Users/xu/.codex/skills/agent-foreman/scripts/validate_plan.py .agent-foreman/phase3-closure/plan.json --ledger .agent-foreman/phase3-closure/evidence-ledger.jsonl | Canonical full-profile plan, references, package states, all passed gates, and append-only evidence ledger validate without diagnostics. | .agent-foreman/phase3-closure/plan.json | INV-CLOSURE-EVIDENCE | true | passed |
| GATE-FRESH-BACKEND | runtime | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --python C:/Python314/python.exe --no-managed-python .agent-foreman/phase3-grounded-visitor/evaluation/fresh/fresh_backend_probe.py | Fresh evaluator backend probes pass 6/6, including no-fallback, grounding, quality controls, exact SSE, shared deadline, and disconnect with completed ASGI task and no response bytes. | .agent-foreman/phase3-grounded-visitor/artifacts/fresh-backend-probe.json | INV-PROVIDER-RUNTIME, INV-GROUNDED-ANSWER, INV-SSE-LIMITS-CANCEL, INV-SECRET-SAME-ORIGIN, INV-CLOSURE-EVIDENCE | true | passed |
| GATE-FRESH-BROWSER | runtime | rtk proxy node .agent-foreman/phase3-grounded-visitor/evaluation/fresh/fresh_browser_probe.mjs | Fresh Microsoft Edge 151 passes 6/6 for pure-ASGI headers, desktop/mobile layout, edited question/SSE/citation/character, locale-history, reduced motion, and clean console/network. | .agent-foreman/phase3-grounded-visitor/artifacts/fresh-browser-probe.json | INV-VISITOR, INV-SECRET-SAME-ORIGIN, INV-CLOSURE-EVIDENCE | true | passed |
| GATE-HYGIENE | integration | rtk proxy D:/RepoNPC/.venv/Scripts/python.exe -m ruff check .; rtk proxy D:/RepoNPC/.venv/Scripts/python.exe -m ruff format --check .; rtk proxy D:/RepoNPC/.venv/Scripts/python.exe -m mypy src; rtk proxy git diff --check | Ruff, format check, mypy, and diff whitespace checks pass; CRLF conversion notices are nonblocking. | .agent-foreman/phase3-closure/integrations/integration-phase3-closure.json | INV-CLOSURE-EVIDENCE | true | passed |
| GATE-PYTHON-ALL | system | rtk proxy D:/RepoNPC/.venv/Scripts/python.exe -m pytest -p no:cacheprovider --basetemp D:/RepoNPC/.pytest-tmp/p3-final-docs -q --junitxml=.agent-foreman/phase3-closure/artifacts/gate-python-all-final.xml | 424 passed, 3 skipped, 0 failed/errors; only one third-party Starlette/httpx deprecation warning. | .agent-foreman/phase3-closure/artifacts/gate-python-all-final.xml | INV-PROVIDER-RUNTIME, INV-GROUNDED-ANSWER, INV-SSE-LIMITS-CANCEL, INV-SECRET-SAME-ORIGIN, INV-CLOSURE-EVIDENCE | true | passed |
| GATE-QUALITY | integration | rtk proxy D:/RepoNPC/.venv/Scripts/python.exe -m pytest tests/eval/test_chat_answer_quality.py -q | Reviewed citation resolution and supported factual entailment meet their thresholds; all unsupported/safety cases fail closed; scorer negative controls reject extra/wrong citations and unreviewed claims. | .agent-foreman/phase3-closure/artifacts/gate-python-all-final.xml | INV-GROUNDED-ANSWER, INV-CLOSURE-EVIDENCE | true | passed |
| GATE-WEB | system | rtk proxy pnpm run web:check | Prettier, ESLint with 0 errors, TypeScript, 7 unit tests, and production Vite build pass; five fast-refresh warnings are nonblocking. | .agent-foreman/phase3-grounded-visitor/artifacts/fresh-browser-probe.json | INV-VISITOR, INV-SECRET-SAME-ORIGIN, INV-CLOSURE-EVIDENCE | true | passed |

## Evidence ledger

| ID | Actor | Gate | Observed | Artifact | Class |
| --- | --- | --- | --- | --- | --- |
| EVID-P3C-DOCKER | gate_runner | GATE-DOCKER | 1 passed in 34.69s | .agent-foreman/phase3-grounded-visitor/artifacts/gate-docker-final.xml | deterministic |
| EVID-P3C-FRESH | evaluator | GATE-FRESH-BACKEND | Backend 6/6 and Edge 6/6; recommendation pass; no P0/P1/P2 | .agent-foreman/phase3-grounded-visitor/evaluation/fresh/evaluation.json | advisory |
| EVID-P3C-PYTHON | gate_runner | GATE-PYTHON-ALL | 424 passed, 3 skipped | .agent-foreman/phase3-closure/artifacts/gate-python-all-final.xml | deterministic |

## Stop conditions

- Stop before claiming verified if any blocking gate fails or is not run.
- Never rewrite the historical Phase 3 character attribution guard as passed.
- Stop and ask the owner before changing any public contract, provider fallback, trust boundary, threshold, hosted dependency, or v1 scope.

## Fallback

- Mode: `main_takeover`
- Triggers: One failed precise repair of a critical invariant; Fresh evaluator or deterministic gate conflicts with completion; Worker requires an unowned production path

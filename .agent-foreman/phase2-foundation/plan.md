# Plan REPONPC-P2-FOUNDATION-20260810

## Objective

Complete P2-00 and close every Delivery Phase 1 carry-forward obligation from Implementation Plan Milestone 1 before Phase 2 leaf delegation

## Main model

- Source: `current_conversation`
- Resolved model: ``
- Verification: `unavailable`

## Architecture decision

- Mode: `main_direct`
- Profile: `minimal`
- Advisor required: `false`
- Reasons: P2-00 changes shared configuration, secret, runtime persistence, application lifecycle, frontend-serving, deployment, dependency, and CI seams that the execution playbook reserves for Main; The owner requested that all Phase 1 carry-forward obligations be resolved before later work

## Current-state evidence

| Path | Symbol | Observation | Status |
| --- | --- | --- | --- |
| .agent-foreman/mvp/integration-mvp-final.json | MVP-FOUNDATION-FINAL | Delivery Phase 1 is verified with 56 tests and evaluator repairs, while the original worker delta guards remain failed and non-attributable | observed |
| D:/RepoNPC | repository root | Python source/tests and uv.lock exist; package/pnpm workspace, apps/web, runtime modules, mock servers, Dockerfile, compose.yml, and GitHub workflows are absent | observed |
| docs/SUBAGENT_EXECUTION_PLAYBOOK.md | sections 3.2 and P2-00 | Environment secrets, runtime SQLite, safe logging, mocks, frontend workspace/serving, Docker/Compose, and CI remain explicit Milestone 1 carry-forward items | observed |
| docs/TECHNICAL_SPEC.md | approval table and sections 3, 4, 15, 19 | Technical Specification 0.1.0 is approved and requires locked Python/TypeScript workspaces, separate runtime storage, safe operations, and release gates | observed |

## Control flow

| ID | Kind | Path | Symbol | Next | Failure path |
| --- | --- | --- | --- | --- | --- |
| FLOW-PUBLIC | public_http_boundary | src/reponpc/api/public.py | create_public_router |  | Unavailable capabilities return stable safe setup/degraded errors with request IDs |
| FLOW-RUNTIME | mutable_persistence_boundary | src/reponpc/runtime | runtime database lifecycle | FLOW-PUBLIC | Migration or integrity failure prevents readiness without mutating immutable index data |
| FLOW-STARTUP | production_entrypoint | src/reponpc/main.py | create_app and app | FLOW-PUBLIC | Invalid startup configuration must fail with redacted diagnostics before serving requests |
| FLOW-WEB | same_origin_static_boundary | apps/web and src/reponpc/main.py | Vite build and FastAPI static serving | FLOW-PUBLIC | Missing build assets leave API health behavior intact and never enable broad CORS |

## Invariants

| ID | Class | Statement | Owner | Counterexample | Gates | Oracle origins |
| --- | --- | --- | --- | --- | --- | --- |
| INV-CI-PARITY | noncritical | CI uses uv and pnpm locked workflows and runs the same lint, type, test, and production-build gates documented locally | .github/workflows/ci.yml | Parse the CI workflow and remove one locked install or required check from an evaluator-local copy | GATE-CI, GATE-TYPE, GATE-PY-LOCK, GATE-BUILD, GATE-ALL | existing_contract, deterministic_derived |
| INV-DEPLOYMENT-PORTABLE | critical | The production image/Compose contract is one non-root same-origin application with a persistent data volume, healthcheck, and no external database/vector service | Dockerfile and compose.yml | Render the Compose model and inspect the app user, mounts, healthcheck, ports, services, and read-only settings | GATE-DEPLOYMENT, GATE-CONTAINER, GATE-ALL | existing_contract, deterministic_derived |
| INV-LOGGING-SAFE | critical | Structured diagnostics retain request/event/status/count information while excluding bodies, raw IPs, tokens, cookies, prompts, answers, files, and private URLs | src/reponpc/observability/logging.py:SafeLogger | Log a nested event containing password, token, cookie, raw IP, prompt, answer, and private URL canaries and inspect the sink | GATE-LOGGING, GATE-ALL | existing_contract, deterministic_derived |
| INV-MOCKS-BOUNDED | critical | GitHub and provider mock servers expose deterministic contract scenarios without external network access or real credentials | tests/mocks/servers.py:create_mock_app | Send an unknown GitHub mutation path and unsupported provider capability request to the in-process mock app | GATE-MOCKS, GATE-ALL | existing_contract, deterministic_derived |
| INV-PHASE1-REGRESSION | critical | All verified Phase 1 configuration, evidence, RRF, chunking, i18n, and setup API behavior remains passing | tests/contract, tests/unit, and tests/integration | Run the complete pre-existing Phase 1 suite together with every new foundation test | GATE-API, GATE-PYTHON, GATE-ALL | existing_contract, deterministic_derived |
| INV-RUNTIME-SEPARATE | critical | Mutable runtime SQLite is transactional, migration-versioned, and separate from immutable index data | src/reponpc/runtime/database.py:RuntimeDatabase | Inject failure inside a migration transaction and reopen the database to inspect schema version and tables | GATE-RUNTIME, GATE-ALL | existing_contract, deterministic_derived |
| INV-SCOPE-APPROVED | critical | Foundation closure preserves approved public contracts, complete v1 scope, and the recorded Phase 1 limitations | docs/TECHNICAL_SPEC.md and docs/SUBAGENT_EXECUTION_PLAYBOOK.md | Run the foundation contract test against a Technical Specification copy whose status is Draft or a report that marks the MVP worker delta guard passed | GATE-SCOPE, GATE-ALL | existing_contract, deterministic_derived |
| INV-SECRETS-BOUNDARY | critical | Deployment secrets load from one direct or file source, collide fail-closed, and never appear in public responses or diagnostics | src/reponpc/config/environment.py:load_environment | Set one secret and its _FILE form to distinct canaries and inspect the startup error, logs, and public status | GATE-ENV, GATE-LOGGING, GATE-ALL | existing_contract, deterministic_derived |
| INV-WEB-LOCKED-SAME-ORIGIN | critical | The typed pnpm/Vite workspace builds reproducibly and FastAPI serves the built visitor shell under the same origin without weakening setup APIs | apps/web/package.json and src/reponpc/main.py:create_app | Build the web app from the lockfile, start the real FastAPI app with the output, and request both / and /api/public/status | GATE-WEB, GATE-API, GATE-ALL | existing_contract, deterministic_derived |

## Acceptance gates

| ID | Scope | Command | Oracle | Artifact | Invariants | Blocking | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GATE-ALL | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-all -p no:cacheprovider -q | All P2-00 blocking Python gates pass together; web, deployment, lock, and build artifacts are separately linked in the integration record | .agent-foreman/phase2-foundation/artifacts/gate-all.txt | INV-SCOPE-APPROVED, INV-SECRETS-BOUNDARY, INV-RUNTIME-SEPARATE, INV-LOGGING-SAFE, INV-MOCKS-BOUNDED, INV-WEB-LOCKED-SAME-ORIGIN, INV-DEPLOYMENT-PORTABLE, INV-CI-PARITY, INV-PHASE1-REGRESSION | true | not_run |
| GATE-API | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-api -p no:cacheprovider tests/integration/test_mvp_api.py tests/integration/test_static_web.py -q | The real FastAPI app serves the built semantic shell and preserves health, readiness, setup status, profile error, headers, request IDs, and safe missing-build behavior | .agent-foreman/phase2-foundation/artifacts/gate-api.txt | INV-WEB-LOCKED-SAME-ORIGIN, INV-PHASE1-REGRESSION | true | not_run |
| GATE-BUILD | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache build --offline --out-dir D:/RepoNPC/.agent-foreman/phase2-foundation/artifacts/dist | The locked Python project builds one sdist and wheel without caches, virtual environments, tests' temporary data, or governance artifacts | .agent-foreman/phase2-foundation/artifacts/gate-build.txt | INV-CI-PARITY | true | not_run |
| GATE-CI | integration | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-ci -p no:cacheprovider tests/contract/test_ci_deployment.py -q | The workflow, Dockerfile, Compose, package-manager, locked-install, permissions, healthcheck, and required local/CI command contracts pass | .agent-foreman/phase2-foundation/artifacts/gate-ci.txt | INV-CI-PARITY, INV-DEPLOYMENT-PORTABLE | true | not_run |
| GATE-CONTAINER | runtime | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-container -p no:cacheprovider tests/smoke/test_container.py -q | The production image starts as non-root through an isolated Compose project, reaches healthz and documented setup-required state, retains its test data volume across restart, and is cleaned up without touching operator data | .agent-foreman/phase2-foundation/artifacts/gate-container.txt | INV-DEPLOYMENT-PORTABLE | true | not_run |
| GATE-DEPLOYMENT | system | rtk proxy docker.exe compose -f D:/RepoNPC/compose.yml config --quiet | Docker Compose accepts one non-root read-only application service with a persistent data volume and healthcheck and no database/vector/model port service | .agent-foreman/phase2-foundation/artifacts/gate-deployment.txt | INV-DEPLOYMENT-PORTABLE | true | not_run |
| GATE-ENV | integration | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-env -p no:cacheprovider tests/contract/test_environment.py -q | Direct/file loading, collision, path/type/mode/size, empty secret, bounds, and canary-redaction contract cases pass | .agent-foreman/phase2-foundation/artifacts/gate-env.txt | INV-SECRETS-BOUNDARY | true | not_run |
| GATE-LOGGING | integration | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-logging -p no:cacheprovider tests/security/test_safe_logging.py -q | Structured safe events retain allowlisted diagnostics while all nested secret, raw-IP, body, prompt, answer, cookie, path, and private-URL canaries are absent | .agent-foreman/phase2-foundation/artifacts/gate-logging.txt | INV-SECRETS-BOUNDARY, INV-LOGGING-SAFE | true | not_run |
| GATE-MOCKS | integration | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-mocks -p no:cacheprovider tests/integration/test_mock_servers.py -q | The in-process GitHub/provider mocks expose deterministic health, capability, generation, contents, conflict, release, and workflow scenarios and deny unknown mutations | .agent-foreman/phase2-foundation/artifacts/gate-mocks.txt | INV-MOCKS-BOUNDED | true | not_run |
| GATE-PY-LOCK | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache lock --check --offline | uv confirms pyproject.toml and uv.lock are synchronized without network resolution | .agent-foreman/phase2-foundation/artifacts/gate-py-lock.txt | INV-CI-PARITY | true | not_run |
| GATE-PYTHON | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-python -p no:cacheprovider -q | All existing and new Python unit, contract, integration, and security tests pass together with no skipped blocking case | .agent-foreman/phase2-foundation/artifacts/gate-python.txt | INV-SCOPE-APPROVED, INV-SECRETS-BOUNDARY, INV-RUNTIME-SEPARATE, INV-LOGGING-SAFE, INV-MOCKS-BOUNDED, INV-WEB-LOCKED-SAME-ORIGIN, INV-DEPLOYMENT-PORTABLE, INV-CI-PARITY, INV-PHASE1-REGRESSION | true | not_run |
| GATE-RUFF | system | rtk ruff check . | Ruff reports no lint violations across production and tests | .agent-foreman/phase2-foundation/artifacts/gate-ruff.txt | INV-CI-PARITY, INV-PHASE1-REGRESSION | true | not_run |
| GATE-RUNTIME | runtime | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-runtime -p no:cacheprovider tests/integration/test_runtime_database.py -q | A real SQLite file migrates transactionally, opens with required tables/version, rejects partial migration, and never stores raw token/IP canaries | .agent-foreman/phase2-foundation/artifacts/gate-runtime.txt | INV-RUNTIME-SEPARATE | true | not_run |
| GATE-SCOPE | integration | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-scope -p no:cacheprovider tests/contract/test_foundation_scope.py -q | The approved specification, complete-v1 sequencing, carry-forward ledger, and failed MVP delta-guard limitation are all observed exactly | .agent-foreman/phase2-foundation/artifacts/gate-scope.txt | INV-SCOPE-APPROVED | true | not_run |
| GATE-TYPE | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python mypy src/reponpc | Mypy reports success for all typed production module boundaries | .agent-foreman/phase2-foundation/artifacts/gate-type.txt | INV-CI-PARITY | true | not_run |
| GATE-WEB | system | rtk proxy C:/Users/xu/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm.cmd --dir D:/RepoNPC run web:check | The locked frontend format, lint, type, unit, and production build commands all pass and emit deterministic dist assets | .agent-foreman/phase2-foundation/artifacts/gate-web.txt | INV-WEB-LOCKED-SAME-ORIGIN | true | not_run |

## Evidence ledger

No evidence has been recorded.

## Stop conditions

- Stop and ask the owner before changing any public API, error code, schema, environment variable, GitHub permission, security/privacy rule, deployment topology, provider fallback, dependency manager, or v1 scope
- Stop Phase 2 leaf delegation while any P2-00 blocking gate is failed or not run
- Do not report Implementation Plan Milestone 1 complete without the full Python/frontend/build/Compose/CI evidence
- Preserve all Phase 1 files, tests, governance artifacts, user changes, and failed delta-guard limitation

## Fallback

- Mode: `single_main`
- Triggers: An unexpected shared seam appears; A required executable oracle is unavailable; A governing contract is ambiguous; A blocking gate fails after one precise Main repair

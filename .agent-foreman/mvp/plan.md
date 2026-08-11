# Plan REPONPC-MVP-20260810

## Objective

Implement Phase 1 Core MVP foundation under approved Technical Specification 0.1.0 without reducing complete v1 scope

## Main model

- Source: `current_conversation`
- Resolved model: ``
- Verification: `unavailable`

## Architecture decision

- Mode: `hybrid_main_seams`
- Profile: `full`
- Advisor required: `false`
- Reasons: The documentation-only repository requires Main to establish public contracts, lifecycle, security boundaries, and integration seams while pure deterministic leaves can be isolated

## Current-state evidence

| Path | Symbol | Observation | Status |
| --- | --- | --- | --- |
| D:/RepoNPC | repository root | Only documentation and examples exist; pyproject.toml, application source, tests, and Git metadata are absent | observed |
| docs/DELIVERY_PHASES.md | Phase 1 — Core MVP vertical slice | The MVP is an initial complete-v1 delivery phase and does not waive later requirements | observed |
| docs/TECHNICAL_SPEC.md | approval table and section 20 | Technical Specification 0.1.0 is owner-approved on 2026-08-10 and implementation is authorized | observed |
| runtime | toolchain | Python 3.14.7, uv 0.12.3, Node 26.7.0, and pnpm 11.16.0 are available | observed |
| src/reponpc/config/models.py and src/reponpc/domain/evidence.py | Phase 1 shared contracts | Root implementation is present; configuration contract tests pass 11 cases, evidence contract tests pass 6 cases, and Ruff passes after a formatting-only repair | observed |

## Control flow

| ID | Kind | Path | Symbol | Next | Failure path |
| --- | --- | --- | --- | --- | --- |
| FLOW-API | planned production entrypoint | src/reponpc/main.py | app |  | No active bundle yields health 200, readiness 503, safe setup status, and profile INDEX_UNAVAILABLE |
| FLOW-CONFIG | planned approved-contract flow | src/reponpc/config/models.py | load_public_config | FLOW-EVIDENCE, FLOW-API | Strict validation raises a typed configuration error without echoing secret-like values |
| FLOW-EVIDENCE | planned deterministic domain flow | src/reponpc/domain/evidence.py | EvidenceRecord.model_validate | FLOW-API | Invalid class, path, commit, or line range is rejected before an evidence ID is produced |

## Invariants

| ID | Class | Statement | Owner | Counterexample | Gates | Oracle origins |
| --- | --- | --- | --- | --- | --- | --- |
| INV-AUTHORIZED-SCOPE | critical | Application files are created only after Technical Specification 0.1.0 and the MVP sequencing decision are recorded as owner-approved | Root plan gate and repository documents | TECHNICAL_SPEC status is Draft while pyproject.toml exists, or delivery phases claim later FRs are dropped | GATE-SPEC, GATE-ALL | existing_contract, deterministic_derived |
| INV-CHUNK-BOUNDED | noncritical | Fallback chunks are deterministic, non-empty, one-based/inclusive, and bounded by configured line and character limits | src/reponpc/indexing/line_chunker.py | A single overlong line creates a chunk above max_characters or overlap equal to max_lines never advances | GATE-CHUNK, GATE-ALL | existing_contract, deterministic_derived |
| INV-CONFIG-STRICT | critical | The normative example validates and unknown, secret, duplicate, invalid path, invalid URL, locale-incomplete, and invalid limit cases fail before side effects | src/reponpc/config/models.py | A root api_key field or repository include ../secret validates successfully | GATE-CONFIG, GATE-ALL | existing_contract, deterministic_derived |
| INV-EVIDENCE-STABLE | critical | Evidence preserves its class, exact immutable source metadata, one-based inclusive range, and deterministic E_ plus 24 lowercase hex identifier | src/reponpc/domain/evidence.py | Two identical records produce different IDs or an end line below the start line is accepted | GATE-EVIDENCE, GATE-ALL | existing_contract, deterministic_derived |
| INV-I18N-PARITY | critical | Traditional Chinese and English expose the same MVP message keys and safe setup errors | src/reponpc/i18n/catalog.py and integration parity test | INDEX_UNAVAILABLE exists only in English | GATE-I18N, GATE-API, GATE-ALL | existing_contract, deterministic_derived |
| INV-PUBLIC-SETUP-SAFE | critical | The real FastAPI entrypoint exposes the specified setup-state health, readiness, status, and profile behavior with request IDs and no sensitive diagnostics | src/reponpc/main.py and src/reponpc/api/public.py | GET /readyz returns 200 or GET /api/public/status contains REPONPC_CHAT_BASE_URL | GATE-API, GATE-ALL | existing_contract, deterministic_derived |
| INV-RRF-DETERMINISTIC | noncritical | RRF implements the approved one-based formula deterministically and rejects invalid channel inputs | src/reponpc/retrieval/rrf.py | The first record receives weight divided by k instead of k plus one | GATE-RRF, GATE-ALL | existing_contract, deterministic_derived |

## Packages and ownership

| ID | Wave | Owner | Depends on | Owned | Prohibited | Gates | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PKG-MAIN-API | 2 | main | PKG-MAIN-CONTRACTS, PKG-WORKER-RRF, PKG-WORKER-CHUNK, PKG-WORKER-I18N | src/reponpc/api/public.py, src/reponpc/main.py, tests/integration/test_mvp_api.py |  | GATE-API, GATE-ALL | verified |
| PKG-MAIN-CONTRACTS | 0 | main |  | pyproject.toml, uv.lock, src/reponpc/__init__.py, src/reponpc/config/models.py, src/reponpc/domain/evidence.py, tests/contract/test_config.py, tests/contract/test_evidence.py |  | GATE-SPEC, GATE-CONFIG, GATE-EVIDENCE | verified |
| PKG-WORKER-CHUNK | 1 | worker | PKG-MAIN-CONTRACTS | src/reponpc/indexing/line_chunker.py, tests/unit/test_line_chunker.py | pyproject.toml, src/reponpc/config/models.py, src/reponpc/domain/evidence.py, src/reponpc/main.py, src/reponpc/api/public.py | GATE-CHUNK | verified |
| PKG-WORKER-I18N | 1 | worker | PKG-MAIN-CONTRACTS | src/reponpc/i18n/catalog.py, tests/unit/test_i18n_catalog.py | pyproject.toml, src/reponpc/config/models.py, src/reponpc/domain/evidence.py, src/reponpc/main.py, src/reponpc/api/public.py | GATE-I18N | verified |
| PKG-WORKER-RRF | 1 | worker | PKG-MAIN-CONTRACTS | src/reponpc/retrieval/rrf.py, tests/unit/test_rrf.py | pyproject.toml, src/reponpc/config/models.py, src/reponpc/domain/evidence.py, src/reponpc/main.py, src/reponpc/api/public.py | GATE-RRF | verified |

## Dependency graph

| From | To |
| --- | --- |
| PKG-MAIN-CONTRACTS | PKG-WORKER-CHUNK |
| PKG-MAIN-CONTRACTS | PKG-WORKER-I18N |
| PKG-MAIN-CONTRACTS | PKG-WORKER-RRF |
| PKG-WORKER-CHUNK | PKG-MAIN-API |
| PKG-WORKER-I18N | PKG-MAIN-API |
| PKG-WORKER-RRF | PKG-MAIN-API |

## Acceptance gates

| ID | Scope | Command | Oracle | Artifact | Invariants | Blocking | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GATE-ALL | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/all-final-2 -p no:cacheprovider -q | All Phase 1 MVP tests pass together with no skipped blocking case | .agent-foreman/mvp/artifacts/gate-all.txt | INV-AUTHORIZED-SCOPE, INV-CONFIG-STRICT, INV-EVIDENCE-STABLE, INV-PUBLIC-SETUP-SAFE, INV-I18N-PARITY, INV-RRF-DETERMINISTIC, INV-CHUNK-BOUNDED | true | passed |
| GATE-API | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/api-final -p no:cacheprovider tests/integration/test_mvp_api.py -q | The real FastAPI app returns health 200, ready 503, setup status 200, profile 503 INDEX_UNAVAILABLE, safe bilingual messages, and request IDs | .agent-foreman/mvp/artifacts/gate-api.txt | INV-PUBLIC-SETUP-SAFE, INV-I18N-PARITY, INV-CONFIG-STRICT | true | passed |
| GATE-CHUNK | component | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/chunk -p no:cacheprovider tests/unit/test_line_chunker.py -q | Fixtures cover LF normalization, exact line ranges, overlap progress, empty text, overlong lines, and invalid limits | .agent-foreman/mvp/artifacts/gate-chunk.txt | INV-CHUNK-BOUNDED | true | passed |
| GATE-CONFIG | integration | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/config-final -p no:cacheprovider tests/contract/test_config.py -q | The normative example passes and every required invalid/secret/path/locale case fails with safe field locations | .agent-foreman/mvp/artifacts/gate-config.txt | INV-CONFIG-STRICT | true | passed |
| GATE-EVIDENCE | integration | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/evidence-final -p no:cacheprovider tests/contract/test_evidence.py -q | Stable ID, evidence class, immutable commit/path, normalized content, and one-based inclusive range cases pass | .agent-foreman/mvp/artifacts/gate-evidence.txt | INV-EVIDENCE-STABLE | true | passed |
| GATE-I18N | component | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/i18n -p no:cacheprovider tests/unit/test_i18n_catalog.py -q | zh-TW and en keys/placeholders are identical and unsupported locale/key cases fail explicitly | .agent-foreman/mvp/artifacts/gate-i18n.txt | INV-I18N-PARITY | true | passed |
| GATE-RRF | component | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/rrf -p no:cacheprovider tests/unit/test_rrf.py -q | Known rankings produce exact one-based RRF scores and ties/errors are deterministic | .agent-foreman/mvp/artifacts/gate-rrf.txt | INV-RRF-DETERMINISTIC | true | passed |
| GATE-SPEC | system | rtk proxy rg -n "Approved\|Accepted" docs/TECHNICAL_SPEC.md docs/OWNER_REVIEW.md docs/DECISIONS.md docs/DELIVERY_PHASES.md | Technical Specification 0.1.0, OR-001 through OR-007, all ADRs, and MVP sequencing are recorded approved on 2026-08-10 | .agent-foreman/mvp/artifacts/gate-spec.txt | INV-AUTHORIZED-SCOPE | true | passed |

## Evidence ledger

| ID | Actor | Gate | Observed | Artifact | Class |
| --- | --- | --- | --- | --- | --- |
| EVID-BUILD-001 | gate_runner |  | Built an 18,704-byte sdist and 17,469-byte wheel; archive inspection confirmed caches, virtualenvs, and governance artifacts are excluded | .agent-foreman/mvp/artifacts/gate-build.txt | deterministic |
| EVID-DELTA-GUARD-LIMITATION-001 | main |  | All three delta guards failed because whole-workspace fingerprints included concurrent Root/worker changes plus virtualenv, cache, bytecode, and pytest temporary files; with no Git history or per-worker write sandbox, the deltas cannot be attributed. Manual owned-path inspection is weaker evidence and the guards remain failed. | .agent-foreman/mvp/integration-mvp-pre-eval.json | deterministic |
| EVID-EVALUATOR-001 | evaluator |  | Fresh evaluator ran five new probes: three passed and two failed, identifying malformed evidence repository slugs and private-state reflection through public status | .agent-foreman/mvp/evaluation/evaluation.json | deterministic |
| EVID-EVALUATOR-REPAIR-001 | main | GATE-ALL | All five evaluator-authored probes passed after one Root repair round | .agent-foreman/mvp/evaluation/root-repair-verification.json | deterministic |
| EVID-GATE-ALL-001 | gate_runner | GATE-ALL | All 56 Phase 1 MVP tests passed together; one non-blocking Starlette TestClient/httpx deprecation warning was emitted | .agent-foreman/mvp/artifacts/gate-all.txt | deterministic |
| EVID-GATE-API-001 | gate_runner | GATE-API | 7 production FastAPI entrypoint tests passed, including safe serialization of injected internal state; one non-blocking Starlette TestClient/httpx deprecation warning was emitted | .agent-foreman/mvp/artifacts/gate-api.txt | deterministic |
| EVID-GATE-CHUNK-001 | gate_runner | GATE-CHUNK | 9 bounded line-chunker tests passed in 0.02 seconds | .agent-foreman/mvp/artifacts/gate-chunk.txt | deterministic |
| EVID-GATE-CONFIG-001 | gate_runner | GATE-CONFIG | 12 configuration contract tests passed, including unsupported locale, absolute path, non-finite weight, and out-of-range limit rejection | .agent-foreman/mvp/artifacts/gate-config.txt | deterministic |
| EVID-GATE-EVIDENCE-001 | gate_runner | GATE-EVIDENCE | 6 evidence contract tests passed, including rejection of repository slugs outside exact owner/name shape | .agent-foreman/mvp/artifacts/gate-evidence.txt | deterministic |
| EVID-GATE-I18N-001 | gate_runner | GATE-I18N | 8 bilingual catalog tests passed in 0.01 seconds | .agent-foreman/mvp/artifacts/gate-i18n.txt | deterministic |
| EVID-GATE-RRF-001 | gate_runner | GATE-RRF | 14 RRF tests passed in 0.02 seconds | .agent-foreman/mvp/artifacts/gate-rrf.txt | deterministic |
| EVID-GATE-SPEC-001 | gate_runner | GATE-SPEC | Technical Specification and MVP sequencing are approved, OR-001 through OR-007 are approved, and ADR-001 through ADR-014 are accepted on 2026-08-10 | .agent-foreman/mvp/artifacts/gate-spec.txt | deterministic |
| EVID-HUMAN-APPROVAL-001 | human |  | Project owner approved the plan and authorized terra high subagents on 2026-08-10; MVP is interpreted as first delivery phase without scope reduction | docs/OWNER_REVIEW.md | human_ruling |
| EVID-PREFLIGHT-001 | main |  | Only .env.example, AGENTS.md, docs, README.md, and reponpc.example.yml existed before application implementation | .agent-foreman/mvp/plan.json | deterministic |

## Stop conditions

- Stop dispatch while plan validation or scope fingerprinting fails
- Stop a worker when an unowned/prohibited path or architectural decision is required
- Return any critical gate failure to Main after one precise repair
- Invalidate and replan the affected subgraph when two packages fail against one contract
- Do not declare MVP foundation verified while any blocking deterministic gate is not passed

## Fallback

- Mode: `main_takeover`
- Triggers: worker identity remains unverified and a package exceeds one production plus one test file; any worker changes an unauthorized path; a focused worker gate fails after one precise repair; integration repair exceeds two rounds

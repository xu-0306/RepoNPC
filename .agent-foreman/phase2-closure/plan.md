# Plan REPONPC-P2-CLOSURE-20260812

## Objective

Close RepoNPC Delivery Phase 2 from the owner-approved Git baseline by specifying and implementing the production index CLI, build-time local sentence-transformers adapter, bilingual public profile producer-consumer contract, repository metadata evidence, and a Docker-isolated formal retrieval benchmark while preserving prior evidence and last-known-good behavior.

## Main model

- Source: `current_conversation`
- Resolved model: ``
- Verification: `unavailable`

## Architecture decision

- Mode: `hybrid_main_seams`
- Profile: `full`
- Advisor required: `true`
- Reasons: The closure crosses the production console entrypoint, bundle publication, public API, provider identity, and benchmark trust boundary.; The owner explicitly authorized Terra, but only a frozen one-production-file/one-test-file embedding leaf is safe under degraded identity verification.

## Current-state evidence

| Path | Symbol | Observation | Status |
| --- | --- | --- | --- |
| .agent-foreman/phase2-review-repairs/integration-docker-rerun.json | GATE-DOCKER | A real Docker persistence/restart smoke passed on Docker Desktop 4.86.0 / Engine 29.7.2 and remains historical evidence. | observed |
| .git | HEAD | Owner-approved audited closure baseline is commit 83c3dd44f7cc2856dc3b61d9f637337f1a466d3e with a clean production tree. | observed |
| evals/phase2/run_benchmark.py | run | The benchmark uses FixtureEmbeddingProvider, reads the controller oracle in the candidate process, does not enforce Docker resource limits, and hardcodes formal_acceptance false. | observed |
| pyproject.toml | project.scripts.reponpc | The console script resolves to reponpc.main:run, so --help and every workflow subcommand enter deployment startup and fail environment validation. | observed |
| src/reponpc/api/public.py | create_public_router.profile | The route validates locale but returns the same unvalidated profile.json object for zh-TW and en. | observed |
| src/reponpc/bundles/archive.py | _verify_public_assets | The verifier requires only that profile.json decode to an object; it does not validate both locale payloads or the public response fields. | observed |
| src/reponpc/indexing/index_database.py | _source_type | All non-documentation files are classified as source_code, so the real Phase 2 fixture produces zero repository_metadata rows. | observed |
| src/reponpc/indexing/sources.py | PassageEmbeddingProvider | Only a protocol exists and its docstring explicitly defers concrete adapters; no production local sentence-transformers adapter is shipped. | observed |

## Control flow

| ID | Kind | Path | Symbol | Next | Failure path |
| --- | --- | --- | --- | --- | --- |
| FLOW-BENCHMARK | evaluation_boundary | host controller oracle -> Docker candidate with public inputs only -> candidate retrieval output -> host scoring | formal Phase 2 benchmark |  | Any oracle visibility, nonproduction provider, missing resource limit, missing provenance, or threshold miss forces formal_acceptance=false. |
| FLOW-BUILD | producer | config -> GitHub resolver -> embedding adapter -> IndexDatabaseBuilder -> public profile -> build_bundle | index build | FLOW-PUBLISH, FLOW-RUNTIME-PROFILE, FLOW-BENCHMARK | Any source, embedding, public-asset, database, or archive failure leaves no completed bundle and cannot advance a manifest. |
| FLOW-CLI | production_entrypoint | pyproject.toml -> src/reponpc/cli.py -> src/reponpc/main.py or indexing pipeline | reponpc | FLOW-BUILD, FLOW-PUBLISH | Argparse returns a nonzero safe error without loading deployment secrets for help/validation failures. |
| FLOW-PUBLISH | external_side_effect | bundle -> immutable release asset -> verified pending stable manifest -> stable branch update | index publish / index publish-manifest | FLOW-RUNTIME-PROFILE | Failure before publish-manifest leaves the previous remote stable manifest unchanged. |
| FLOW-RUNTIME-PROFILE | producer_consumer | public_profile producer -> archive verifier -> BundleManager active public directory -> GET /api/public/profile | profile.json locales selection |  | Missing, invalid, or incomplete locale data rejects the candidate or returns INDEX_UNAVAILABLE; it never cross-falls back. |

## Invariants

| ID | Class | Statement | Owner | Counterexample | Gates | Oracle origins |
| --- | --- | --- | --- | --- | --- | --- |
| INV-ATTRIBUTION | noncritical | Every closure delta is attributable to the new Git baseline and historical ledgers remain byte-for-byte unchanged. | Git baseline, fingerprint manifests, and Main delta guard | tests/unit/test_rrf.py or an old evidence-ledger.jsonl changes during the Terra package. | GATE-DELTA | deterministic_derived |
| INV-CLI-ENTRYPOINT | critical | The installed reponpc entrypoint starts the server with no arguments or serve, and executes config/index commands without entering deployment startup. | src/reponpc/cli.py argparse dispatch | reponpc config validate reponpc.example.yml exits with deployment environment is invalid. | GATE-CLI, GATE-WORKFLOW | existing_contract, deterministic_derived |
| INV-EMBEDDING-PRODUCTION | critical | Phase 2 indexing and formal evaluation use the shipped local_sentence_transformers adapter with exact identity, finite normalized float32 output, and no fallback. | local embedding adapter plus IndexDatabaseBuilder identity validation | The formal report names deterministic_fixture or accepts a 383-dimensional result. | GATE-LOCAL-EMBEDDING, GATE-FORMAL-BENCHMARK | existing_contract, deterministic_derived |
| INV-FORMAL-BENCHMARK | critical | The candidate container cannot read the oracle, runs the production adapter with 4 CPU and 8 GiB limits, and returns only candidate evidence/timings; the host controller derives formal results and provenance. | host benchmark controller plus Docker mount/resource inspection | The candidate can stat /workspace/evals/phase2/controller/expected-evidence.json or report formal_acceptance=true itself. | GATE-FORMAL-BENCHMARK | existing_contract, deterministic_derived, evaluator_authored |
| INV-LAST-KNOWN-GOOD | critical | Closure changes do not weaken bundle rejection, atomic activation, or preservation of the active bundle on failure. | BundleManager, verifier, updater, and regression gates | A profile missing en activates over a valid current bundle. | GATE-PROFILE, GATE-PUBLICATION-LAST, GATE-PYTHON-ALL, GATE-DOCKER | existing_contract, deterministic_derived |
| INV-PROFILE-BILINGUAL | critical | One produced profile.json contains complete zh-TW and en payloads, is schema-validated unchanged by the archive verifier, and yields the existing locale-specific public response. | public profile schema, bundle verifier, and public route | profile.json has only zh-TW and GET locale=en returns zh-TW content with 200. | GATE-PROFILE | existing_contract, deterministic_derived |
| INV-PUBLICATION-LAST | critical | Only publish-manifest mutates the stable pointer, and it can consume only a locally recorded manifest derived from a verified immutable asset. | PublicationCoordinator and GitHubReleasePublisher | Upload verification fails but the mock records a stable-manifest PUT. | GATE-CLI, GATE-PUBLICATION-LAST | existing_contract, deterministic_derived |
| INV-REPOSITORY-METADATA | critical | Allowlisted line-addressable root manifests are emitted as REPOSITORY_FACT evidence with source_type repository_metadata and participate in configured retrieval weighting. | IndexDatabaseBuilder source classifier and read-only retrieval policy | A root pyproject.toml is stored as source_code or an owner-authored role is stored as REPOSITORY_FACT. | GATE-REPOSITORY-METADATA, GATE-FORMAL-BENCHMARK | existing_contract, deterministic_derived |
| INV-SPEC-FIRST | critical | Owner-approved Phase 2 boundaries and all changed public/CLI/profile/benchmark contracts are recorded in approved normative documents before application implementation. | Main plus contract traceability tests | The local adapter is shipped while DELIVERY_PHASES still says all local adapters begin in Phase 3. | GATE-SPEC | existing_contract |

## Packages and ownership

| ID | Wave | Owner | Depends on | Owned | Prohibited | Gates | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PKG-MAIN-BENCHMARK | 3 | main | PKG-TERRA-LOCAL-EMBEDDING, PKG-MAIN-CLI-PUBLIC | evals/phase2/run_benchmark.py, evals/phase2/candidate_runner.py, evals/phase2/Dockerfile, evals/phase2/README.md, tests/integration/test_phase2_benchmark.py | evals/phase2/controller/expected-evidence.json, evals/phase2/public/questions.json, src/reponpc/providers/local_sentence_transformers.py | GATE-FORMAL-BENCHMARK | verified |
| PKG-MAIN-CLI-PUBLIC | 2 | main | PKG-MAIN-EMBEDDING-CONTRACT | src/reponpc/cli.py, src/reponpc/indexing/pipeline.py, src/reponpc/indexing/public_profile.py, src/reponpc/indexing/index_database.py, src/reponpc/indexing/github.py, src/reponpc/indexing/publication.py, src/reponpc/indexing/github_publication.py, src/reponpc/bundles/archive.py, src/reponpc/api/public.py, .github/workflows/build-index.yml, tests/integration/test_cli.py, tests/integration/test_index_build.py, tests/integration/test_retrieval_policy.py, tests/integration/test_bundle_producer_consumer.py, tests/integration/test_bundle_activation.py, tests/integration/test_mvp_api.py, tests/integration/test_publication_last.py, tests/integration/test_github_publication.py, tests/security/test_bundle_validation.py, tests/unit/test_phase2_fixture_corpus.py, tests/fixtures/phase2/reponpc.yml, tests/fixtures/repos/reponpc-demo/pyproject.toml | src/reponpc/providers/local_sentence_transformers.py, tests/unit/test_local_sentence_transformers.py, evals/phase2/controller/expected-evidence.json | GATE-CLI, GATE-WORKFLOW, GATE-PROFILE, GATE-REPOSITORY-METADATA, GATE-PUBLICATION-LAST | verified |
| PKG-MAIN-EMBEDDING-CONTRACT | 1 | main | PKG-MAIN-SPEC | src/reponpc/indexing/sources.py, src/reponpc/providers/__init__.py, pyproject.toml, uv.lock, tests/contract/test_embedding_provider_contract.py | src/reponpc/providers/local_sentence_transformers.py, tests/unit/test_local_sentence_transformers.py | GATE-SPEC, GATE-EMBEDDING-CONTRACT | verified |
| PKG-MAIN-INTEGRATION | 4 | main | PKG-MAIN-BENCHMARK | .agent-foreman/phase2-closure/artifacts, .agent-foreman/phase2-closure/evaluation, .agent-foreman/phase2-closure/integrations, .agent-foreman/phase2-closure/evidence-ledger.jsonl, .agent-foreman/phase2-closure/evidence-ledger-v2.jsonl, .agent-foreman/phase2-closure/plan.json, .agent-foreman/phase2-closure/plan.md | .agent-foreman/phase2-review-repairs/**, .agent-foreman/phase2-index-bundles/** | GATE-PYTHON-ALL, GATE-QUALITY, GATE-WEB, GATE-DOCKER, GATE-DELTA | verified |
| PKG-MAIN-SPEC | 0 | main |  | docs/TECHNICAL_SPEC.md, docs/ACCEPTANCE_CRITERIA.md, docs/DECISIONS.md, docs/DELIVERY_PHASES.md, docs/IMPLEMENTATION_PLAN.md, docs/OPERATIONS.md, README.md, tests/contract/test_phase2_closure_spec.py | src/**, evals/**, .github/workflows/** | GATE-SPEC | verified |
| PKG-TERRA-LOCAL-EMBEDDING | 2 | worker | PKG-MAIN-EMBEDDING-CONTRACT | src/reponpc/providers/local_sentence_transformers.py, tests/unit/test_local_sentence_transformers.py | pyproject.toml, uv.lock, src/reponpc/indexing/sources.py, src/reponpc/indexing/index_database.py, src/reponpc/cli.py, evals/phase2/run_benchmark.py, docs/TECHNICAL_SPEC.md, docs/ACCEPTANCE_CRITERIA.md, docs/DECISIONS.md, .github/workflows/build-index.yml, .agent-foreman/phase2-review-repairs/plan.json, .agent-foreman/phase2-review-repairs/evidence-ledger.jsonl | GATE-LOCAL-EMBEDDING, GATE-DELTA | verified |

## Dependency graph

| From | To |
| --- | --- |
| PKG-MAIN-BENCHMARK | PKG-MAIN-INTEGRATION |
| PKG-MAIN-CLI-PUBLIC | PKG-MAIN-BENCHMARK |
| PKG-MAIN-EMBEDDING-CONTRACT | PKG-MAIN-CLI-PUBLIC |
| PKG-MAIN-EMBEDDING-CONTRACT | PKG-TERRA-LOCAL-EMBEDDING |
| PKG-MAIN-SPEC | PKG-MAIN-EMBEDDING-CONTRACT |
| PKG-TERRA-LOCAL-EMBEDDING | PKG-MAIN-BENCHMARK |

## Acceptance gates

| ID | Scope | Command | Oracle | Artifact | Invariants | Blocking | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GATE-CLI | system | rtk proxy .venv/Scripts/python.exe -m pytest tests/integration/test_cli.py -q -p no:cacheprovider --basetemp .pytest-tmp/phase2-cli-r4 --junitxml=.agent-foreman/phase2-closure/artifacts/gate-cli-r4.xml | The real installed dispatch exposes help/config/index commands, preserves no-argument/serve startup, and exercises build/publish/publish-manifest failure ordering with safe exits. | .agent-foreman/phase2-closure/artifacts/gate-cli-r4.xml | INV-CLI-ENTRYPOINT, INV-PUBLICATION-LAST | true | passed |
| GATE-DELTA | integration | rtk git diff --name-status 83c3dd44f7cc2856dc3b61d9f637337f1a466d3e -- && rtk proxy .venv/Scripts/python.exe C:/Users/xu/.codex/skills/agent-foreman/scripts/guard_delta.py --plan .agent-foreman/phase2-closure/plan.json --package PKG-TERRA-LOCAL-EMBEDDING --dispatch-manifest .agent-foreman/phase2-closure/fingerprints/dispatch-manifest.json --handoff-manifest .agent-foreman/phase2-closure/fingerprints/handoff-manifest.json | Every worker delta is owned, historical campaign files are unchanged, and the guard exits 0. | .agent-foreman/phase2-closure/artifacts/gate-delta.txt | INV-ATTRIBUTION | true | passed |
| GATE-DOCKER | runtime | rtk proxy .venv/Scripts/python.exe -m pytest tests/smoke/test_container.py -q -p no:cacheprovider --basetemp .pytest-tmp/phase2-docker --junitxml=.agent-foreman/phase2-closure/artifacts/gate-docker.xml | The real container starts, preserves runtime state across restart, and serves the no-argument CLI server path. | .agent-foreman/phase2-closure/artifacts/gate-docker.xml | INV-CLI-ENTRYPOINT, INV-LAST-KNOWN-GOOD | true | passed |
| GATE-EMBEDDING-CONTRACT | integration | rtk proxy .venv/Scripts/python.exe -m pytest tests/contract/test_embedding_provider_contract.py -q --basetemp .pytest-tmp/embedding-contract-green -p no:cacheprovider --junitxml=.agent-foreman/phase2-closure/artifacts/gate-embedding-contract.xml && rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache lock --check --offline | The runtime-checkable provider protocol requires query and passage batches, safe failures expose only a stable code, and the Python 3.14-compatible optional indexer dependency is locked without entering the normal dependency set. | .agent-foreman/phase2-closure/artifacts/gate-embedding-contract.xml | INV-EMBEDDING-PRODUCTION, INV-SPEC-FIRST | true | passed |
| GATE-FORMAL-BENCHMARK | runtime | rtk proxy .venv/Scripts/python.exe evals/phase2/run_benchmark.py --artifacts .agent-foreman/phase2-closure/artifacts/formal-benchmark-r2.json | Docker inspect proves only public mounts, 4 CPU and 8 GiB limits; access probe cannot see the oracle; the report records the hard-bound canonical question/oracle SHA-256 values, names local_sentence_transformers, includes image/runtime/host provenance and raw timings, meets Recall@8/parity/p95 thresholds, and host-derived formal_acceptance=true. | .agent-foreman/phase2-closure/artifacts/formal-benchmark-r2.json | INV-EMBEDDING-PRODUCTION, INV-REPOSITORY-METADATA, INV-FORMAL-BENCHMARK | true | passed |
| GATE-LOCAL-EMBEDDING | component | rtk proxy .venv/Scripts/python.exe -m pytest tests/unit/test_local_sentence_transformers.py -q | The adapter applies exact prefixes, rejects identity/output mismatches, emits finite normalized float32 matrices, and never loads another model after failure. | .agent-foreman/phase2-closure/artifacts/worker-local-embedding.txt | INV-EMBEDDING-PRODUCTION | true | passed |
| GATE-PROFILE | integration | rtk proxy .venv/Scripts/python.exe -m pytest tests/integration/test_bundle_producer_consumer.py tests/integration/test_mvp_api.py -q -p no:cacheprovider --basetemp .pytest-tmp/phase2-profile-r5 --junitxml=.agent-foreman/phase2-closure/artifacts/gate-profile-r5.xml | The same produced bytes pass archive verification and return distinct complete zh-TW/en public payloads; missing/invalid locale data fails closed and preserves active state. | .agent-foreman/phase2-closure/artifacts/gate-profile-r5.xml | INV-PROFILE-BILINGUAL, INV-LAST-KNOWN-GOOD | true | passed |
| GATE-PUBLICATION-LAST | integration | rtk proxy .venv/Scripts/python.exe -m pytest tests/integration/test_publication_last.py tests/integration/test_github_publication.py -q -p no:cacheprovider --basetemp .pytest-tmp/phase2-publication-r2 --junitxml=.agent-foreman/phase2-closure/artifacts/gate-publication-last-r2.xml | Every pre-manifest injected failure records zero stable-manifest mutations and a success records immutable create/upload/verify before exactly one pointer write. | .agent-foreman/phase2-closure/artifacts/gate-publication-last-r2.xml | INV-PUBLICATION-LAST, INV-LAST-KNOWN-GOOD | true | passed |
| GATE-PYTHON-ALL | system | rtk proxy .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp .pytest-tmp/phase2-all-r3 --junitxml=.agent-foreman/phase2-closure/artifacts/gate-python-all-r3.xml | The complete Python suite exits 0 with no omitted failing domain. | .agent-foreman/phase2-closure/artifacts/gate-python-all-r3.xml | INV-CLI-ENTRYPOINT, INV-EMBEDDING-PRODUCTION, INV-PROFILE-BILINGUAL, INV-REPOSITORY-METADATA, INV-PUBLICATION-LAST, INV-LAST-KNOWN-GOOD | true | passed |
| GATE-QUALITY | system | rtk proxy .venv/Scripts/python.exe -m ruff check . && rtk proxy .venv/Scripts/python.exe -m ruff format --check . && rtk proxy .venv/Scripts/python.exe -m mypy src/reponpc evals/phase2/run_benchmark.py evals/phase2/candidate_runner.py | Ruff lint and format checks pass repository-wide; mypy passes the repository-established production package target plus both new formal benchmark runners. | .agent-foreman/phase2-closure/artifacts/gate-quality.txt | INV-CLI-ENTRYPOINT, INV-EMBEDDING-PRODUCTION, INV-PROFILE-BILINGUAL, INV-REPOSITORY-METADATA, INV-PUBLICATION-LAST | true | passed |
| GATE-REPOSITORY-METADATA | integration | rtk proxy .venv/Scripts/python.exe -m pytest tests/integration/test_index_build.py tests/integration/test_retrieval_policy.py -q -p no:cacheprovider --basetemp .pytest-tmp/phase2-metadata --junitxml=.agent-foreman/phase2-closure/artifacts/gate-repository-metadata.xml | A real root manifest produces line-addressable REPOSITORY_FACT repository_metadata rows and configured source weighting consumes them without reclassifying owner assertions. | .agent-foreman/phase2-closure/artifacts/gate-repository-metadata.xml | INV-REPOSITORY-METADATA | true | passed |
| GATE-SPEC | integration | rtk proxy .venv/Scripts/python.exe -m pytest tests/contract/test_phase2_closure_spec.py -q --basetemp .pytest-tmp/phase2-closure-spec-r2 -p no:cacheprovider --junitxml=.agent-foreman/phase2-closure/artifacts/gate-spec.xml | ADR-015 is Accepted; affected approved documents agree on Phase 2 adapter/CLI/profile/metadata/benchmark contracts and Phase 3 exclusions. | .agent-foreman/phase2-closure/artifacts/gate-spec.xml | INV-SPEC-FIRST | true | passed |
| GATE-WEB | system | rtk proxy pnpm run web:check | Frontend format, lint, typecheck, unit tests, and production build all exit 0 after public profile contract changes. | .agent-foreman/phase2-closure/artifacts/gate-web.txt | INV-PROFILE-BILINGUAL | true | passed |
| GATE-WORKFLOW | integration | rtk proxy .venv/Scripts/python.exe -m pytest tests/contract/test_ci_deployment.py -q -p no:cacheprovider --basetemp .pytest-tmp/phase2-workflow --junitxml=.agent-foreman/phase2-closure/artifacts/gate-workflow.xml | build-index.yml installs the locked indexer extra and invokes only implemented CLI commands in publication-last order. | .agent-foreman/phase2-closure/artifacts/gate-workflow.xml | INV-CLI-ENTRYPOINT | true | passed |

## Evidence ledger

| ID | Actor | Gate | Observed | Artifact | Class |
| --- | --- | --- | --- | --- | --- |
| EVID-P2C-BASELINE-001 | human |  | The owner approved the recommended Phase 2 closure boundaries and a new audited Git baseline. | conversation approval: 照建議方案 | human_ruling |
| EVID-P2C-BLOCKERS-001 | main |  | Historical review artifacts show real failures for CLI dispatch and profile localization, zero repository_metadata rows, and a nonformal benchmark. | .agent-foreman/phase2-review-repairs/integration-final.json | deterministic |
| EVID-P2C-DEPENDENCY-001 | main | GATE-EMBEDDING-CONTRACT | Python 3.14.7 resolved sentence-transformers 5.7.0 and torch 2.13.0 without installation; uv.lock now records the optional indexer graph and offline lock check passes. | pyproject.toml and uv.lock | deterministic |
| EVID-P2C-DOCKER-001 | main | GATE-DOCKER | 1 passed in 30.06s on Docker Desktop 4.86.0 / Engine 29.7.2; this remains historical and must be rerun after closure changes. | .agent-foreman/phase2-review-repairs/evaluation/gate-docker-live.xml | deterministic |
| EVID-P2C-DOCKER-002 | main | GATE-DOCKER | The current closure Compose startup, restart, health, and runtime-volume persistence smoke passed: 1 test, 0 failures, 0 errors, and 0 skipped in 26.05 seconds. | .agent-foreman/phase2-closure/artifacts/gate-docker.xml | deterministic |
| EVID-P2C-EMBED-CONTRACT-001 | main | GATE-EMBEDDING-CONTRACT | Five specification/provider contract tests passed; focused Ruff lint and format checks passed for all contract files. | .agent-foreman/phase2-closure/artifacts/gate-contracts-r2.xml | deterministic |
| EVID-P2C-EVALUATOR-002 | evaluator |  | Fresh read-only evaluation passed all critical probes, verified both current runtime artifacts, resolved the formal false-green and Docker not-run findings, excluded historical substitutes, and recommended pass with no open findings. | .agent-foreman/phase2-closure/evaluation/evaluation-phase2-closure.json | advisory |
| EVID-P2C-FORMAL-002 | main | GATE-FORMAL-BENCHMARK | The post-repair Docker benchmark used the production local_sentence_transformers provider, verified canonical input digests and oracle isolation, enforced 4 CPU/8 GiB/network-none, reached Recall@8=1.0 and language parity=1.0 with warm p95=56.001268 ms, and derived formal_acceptance=true with no blockers. | .agent-foreman/phase2-closure/artifacts/formal-benchmark-r2.json | deterministic |
| EVID-P2C-GIT-001 | main | GATE-DELTA | Owner-approved audited state committed as 83c3dd44f7cc2856dc3b61d9f637337f1a466d3e; production worktree was clean immediately afterward. | .git/HEAD | deterministic |
| EVID-P2C-INTEGRATION-001 | main |  | Main verified all 14 blocking gates and declared artifacts, accepted the fresh evaluator pass recommendation, confirmed no protected-history delta or non-test live-secret pattern, and completed the Phase 2 closure integration. | .agent-foreman/phase2-closure/integrations/integration-phase2-closure.json | deterministic |
| EVID-P2C-PYTHON-003 | main | GATE-PYTHON-ALL | The post-repair aggregate Python suite completed with 354 collected tests: 351 passed, 3 skipped, 0 failures, and 0 errors. | .agent-foreman/phase2-closure/artifacts/gate-python-all-r3.xml | deterministic |
| EVID-P2C-SPEC-001 | main | GATE-SPEC | Initial trace gate had two passes and one assertion wording mismatch; no production code was started. | .agent-foreman/phase2-closure/artifacts/gate-spec-initial.xml | deterministic |
| EVID-P2C-SPEC-002 | main | GATE-SPEC | Three Phase 2 closure specification trace tests passed after correcting the test oracle to the accepted ADR wording. | .agent-foreman/phase2-closure/artifacts/gate-spec.xml | deterministic |

## Stop conditions

- Stop and return to the owner before changing a schema version, public API shape, error code, environment variable, GitHub permission, provider fallback behavior, benchmark threshold, oracle, or reference resource limit beyond the approved decision.
- Do not dispatch Terra until normative documents, the embedding contract, optional dependency lock, plan validation/render, and dispatch fingerprint all complete.
- Do not mark Phase 2 verified while any blocking gate is failed or not run.
- Never rewrite prior campaign ledgers or represent their failed delta guards as passed.

## Fallback

- Mode: `main_takeover`
- Triggers: Terra requires an unowned path or fails one precise nontransient repair.; The sentence-transformers dependency is unsupported on Python 3.14 after one evidence-backed resolution attempt.; Two packages fail against the same embedding or profile contract.; Docker isolation or deterministic evidence conflicts with a model recommendation.

# Plan REPONPC-P2-01-EXCLUSIONS-20260810

## Objective

Implement the P2-01 pure mandatory exclusion classifier without adding I/O, configuration-model, indexing-orchestration, network, or database behavior.

## Main model

- Source: `current_conversation`
- Resolved model: ``
- Verification: `unavailable`

## Architecture decision

- Mode: `main_direct`
- Profile: `minimal`
- Advisor required: `false`
- Reasons: The classifier is a security-sensitive producer contract for all later indexing work, while Gitignore matching and reason-code precedence needed to be frozen by Main.; No production eligibility pipeline exists yet, so a worker could only deliver an unintegrated shared seam and would add coordination cost without an integration oracle.

## Current-state evidence

| Path | Symbol | Observation | Status |
| --- | --- | --- | --- |
| docs/ACCEPTANCE_CRITERIA.md | AC-004 | Unsafe paths/types/contents and individually valid files beyond size budgets must not produce evidence or embeddings, and skip reports must not include contents. | observed |
| docs/SUBAGENT_EXECUTION_PLAYBOOK.md | P2-01 | P2-01 is defined as a pure normalized-path-plus-metadata classifier with a future Main-owned production eligibility-pipeline integration gate. | observed |
| docs/TECHNICAL_SPEC.md | sections 4.2-4.3 and 5.1-5.2 | Repository include/exclude patterns are repo-relative Gitignore-style patterns; source-size limits are bounded; mandatory exclusions must precede text entering the index and emit only a path, reason code, and size in summaries. | observed |
| src/reponpc/config/models.py | RepositoryConfig and RetrievalLimitsConfig | Configuration already validates repository pattern syntax and provides max_file_bytes, max_repository_text_bytes, and max_corpus_text_bytes; P2-01 must consume only an internal immutable policy rather than alter these public models. | observed |
| src/reponpc/indexing/line_chunker.py | chunk_text | The only existing indexing production module chunks supplied text; no exclusions module, source intake, GitHub client, or index writer exists. | observed |

## Control flow

| ID | Kind | Path | Symbol | Next | Failure path |
| --- | --- | --- | --- | --- | --- |
| FLOW-P2-01-ELIGIBILITY | future_indexing_intake | src/reponpc/indexing/exclusions.py | classify_source | FLOW-P2-02-CHUNKING | Invalid paths, metadata, mandatory exclusions, configured exclusions, or size budgets yield a stable skip decision and never expose or accept a file body. |
| FLOW-P2-02-CHUNKING | future_producer_consumer | src/reponpc/indexing/line_chunker.py | chunk_text |  | No real eligibility-pipeline caller exists yet; only a future Main integration may provide text to chunking after an include decision. |

## Invariants

| ID | Class | Statement | Owner | Counterexample | Gates | Oracle origins |
| --- | --- | --- | --- | --- | --- | --- |
| INV-EXCLUSION-BUDGETS | critical | The classifier rejects a file exceeding its file limit and rejects individually valid candidates when adding their declared source bytes would exceed repository or corpus text budgets. | src/reponpc/indexing/exclusions.py:classify_source | A 10-byte otherwise eligible candidate with nine prior repository bytes and a 16-byte repository budget skips before admission; an analogous corpus limit also skips. | GATE-EXCLUSIONS-UNIT, GATE-EXCLUSIONS-INTEGRATION | existing_contract, deterministic_derived |
| INV-EXCLUSION-PURITY | critical | The classifier accepts only a normalized repository-relative POSIX path, bounded metadata, and immutable policy; it performs no file, network, configuration-model, database, logging, or body-content I/O and returns only include/skip plus a stable reason code. | src/reponpc/indexing/exclusions.py:classify_source | A backslash or alias path, malformed metadata, or a test canary that is not present in the metadata must receive a skip reason without any file read or canary-bearing output. | GATE-EXCLUSIONS-UNIT, GATE-EXCLUSIONS-SECURITY, GATE-EXCLUSIONS-INTEGRATION | existing_contract, deterministic_derived |
| INV-MANDATORY-EXCLUSIONS | critical | Invalid, non-regular, binary, undecodable, secret-flagged, environment, credential, VCS, dependency/vendor, build/generated/cache, minified/map, archive/media/database, and lock-file candidates are fail-closed with deterministic reason codes before any include rule can admit them. | src/reponpc/indexing/exclusions.py:classify_source | A path such as .env.production, id_rsa, node_modules/pkg/index.js, dist/app.min.js, archive.tar.zst, state.sqlite, or poetry.lock matched by an include rule must still skip with its mandatory reason. | GATE-EXCLUSIONS-UNIT, GATE-EXCLUSIONS-SECURITY, GATE-EXCLUSIONS-INTEGRATION | existing_contract, deterministic_derived |
| INV-PHASE1-REGRESSION | noncritical | The pure exclusions addition preserves the Phase 1 configuration, evidence, chunking, API, runtime, logging, and deployment test behavior. | tests | Run the entire Python suite after the new table-driven tests are added. | GATE-PYTHON-ALL, GATE-RUFF, GATE-TYPE | existing_contract, deterministic_derived |
| INV-POLICY-DETERMINISM | noncritical | Validated positive/negated Gitignore-style global, repository-exclude, and include rules are evaluated in input order after mandatory exclusions, with empty includes fail-closed and no path aliases normalized silently. | src/reponpc/indexing/exclusions.py:ExclusionPolicy and classify_source | A nested configured exclusion, an include matched through **, and a later negated exclude rule must each have the documented result while .env remains mandatory-excluded. | GATE-EXCLUSIONS-UNIT, GATE-EXCLUSIONS-INTEGRATION | existing_contract, deterministic_derived |

## Acceptance gates

| ID | Scope | Command | Oracle | Artifact | Invariants | Blocking | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GATE-EXCLUSIONS-INTEGRATION | integration | Deferred: run the future Main-owned real GitHub fixture metadata intake through the production eligibility pipeline before bytes reach chunking/evidence construction. | Real source metadata produces the same classifier decision and reason observed at the index intake boundary; excluded candidates never reach the text/chunk/evidence consumer. | .agent-foreman/phase2-exclusions/artifacts/gate-exclusions-integration.txt | INV-EXCLUSION-PURITY, INV-MANDATORY-EXCLUSIONS, INV-EXCLUSION-BUDGETS, INV-POLICY-DETERMINISM | false | not_run |
| GATE-EXCLUSIONS-SECURITY | component | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-01-security -p no:cacheprovider tests/unit/test_exclusions.py -k 'mandatory or invalid or secret or purity' -q | Unsafe alias/path/type/secret-category cases remain skipped even when include rules match, and the classifier's value-only API yields no file-body output. | .agent-foreman/phase2-exclusions/artifacts/gate-exclusions-security-r2.txt | INV-EXCLUSION-PURITY, INV-MANDATORY-EXCLUSIONS | true | passed |
| GATE-EXCLUSIONS-UNIT | component | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-01-unit -p no:cacheprovider tests/unit/test_exclusions.py -q | Table-driven normal, edge, invalid-path, file-type, mandatory-name, configured-pattern, and cumulative-budget cases return the exact include flag and stable reason code. | .agent-foreman/phase2-exclusions/artifacts/gate-exclusions-unit-r2.txt | INV-EXCLUSION-PURITY, INV-MANDATORY-EXCLUSIONS, INV-EXCLUSION-BUDGETS, INV-POLICY-DETERMINISM | true | passed |
| GATE-PYTHON-ALL | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-01-all -p no:cacheprovider -q | All existing and new Python tests pass together; platform-limited skips remain reported rather than treated as passes. | .agent-foreman/phase2-exclusions/artifacts/gate-python-all-r2.txt | INV-PHASE1-REGRESSION | true | passed |
| GATE-RUFF | component | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python ruff check src/reponpc/indexing/exclusions.py tests/unit/test_exclusions.py | Ruff reports no lint violations in the P2-01 production and test files. | .agent-foreman/phase2-exclusions/artifacts/gate-ruff-r2.txt | INV-PHASE1-REGRESSION | true | passed |
| GATE-TYPE | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python mypy src/reponpc | Mypy reports success for the typed production package after the exclusions module is added. | .agent-foreman/phase2-exclusions/artifacts/gate-type-r2.txt | INV-PHASE1-REGRESSION | true | passed |

## Evidence ledger

No evidence has been recorded.

## Stop conditions

- Stop and ask the owner before changing public configuration pattern semantics, configuration models, source-size defaults/hard limits, public APIs, error codes, dependencies, secret-scanning policy, or any indexing/bundle/network/database behavior.
- Do not claim the future production eligibility-pipeline integration gate passed while no production caller exists.
- Treat a focused blocking-gate failure after one precise repair as a Main replan/fail-closed condition.
- Preserve P2-00 evidence and all unrelated user changes; the non-Git workspace cannot prove a broad delta attribution pass.

## Fallback

- Mode: `single_main`
- Triggers: A required configuration-model or public-contract change appears; Gitignore semantics cannot be expressed without changing the approved configuration contract; A future integration needs an unimplemented source intake seam; A blocking focused gate fails after one precise Main repair

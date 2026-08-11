# Plan REPONPC-P2-03-P2-04-RETRIEVAL-20260810

## Objective

Implement safe lexical FTS compilation and deterministic vector validation/ranking primitives without owning SQLite schema, provider/network, bundle compatibility, or public API behavior.

## Main model

- Source: `current_conversation`
- Resolved model: ``
- Verification: `unavailable`

## Architecture decision

- Mode: `main_direct`
- Profile: `minimal`
- Advisor required: `false`
- Reasons: FTS raw-query denial and finite normalized vector validation are security/retrieval contracts, but actual worker model identity is unavailable and only degraded delegation is permitted.; The bounded modules need one Main-owned real SQLite FTS integration probe and shared future bundle consumer semantics.

## Current-state evidence

| Path | Symbol | Observation | Status |
| --- | --- | --- | --- |
| docs/TECHNICAL_SPEC.md | sections 5.4, 6, and 7 | Lexical FTS uses allowlisted syntax with raw user query syntax forbidden; vectors must be finite normalized float32 with declared dimension; lexical/vector channels later fuse through RRF. | observed |
| pyproject.toml and uv.lock | runtime dependencies | NumPy is now a locked runtime dependency under ADR-004; no provider, model identity, or bundle compatibility behavior exists yet. | observed |
| src/reponpc/retrieval/rrf.py | fuse_rankings | RRF already consumes ranked evidence ID sequences, but there is no FTS query compiler, SQLite retrieval adapter, vector matrix validator, or vector ranking module. | observed |

## Control flow

| ID | Kind | Path | Symbol | Next | Failure path |
| --- | --- | --- | --- | --- | --- |
| FLOW-FTS-COMPILER | future_lexical_channel | src/reponpc/retrieval/fts_query.py | compile_fts_query | FLOW-P2-06-SQLITE | Empty/control-only input returns a no-query mode and all accepted terms become allowlisted quoted FTS syntax, never executable user syntax. |
| FLOW-P2-06-SQLITE | future_producer_consumer | P2-06 index reader/writer (not yet implemented) | SQLite FTS/vector blob loading |  | Real bundle identity/mismatch/readiness integration remains deferred and cannot be claimed by primitive component gates. |
| FLOW-VECTOR-RANKER | future_vector_channel | src/reponpc/retrieval/vector.py | validate_vector_matrix and rank_vectors | FLOW-P2-06-SQLITE, src/reponpc/retrieval/rrf.py:fuse_rankings | Invalid shapes, IDs, values, norms, and dimensions fail before ranking; stable ordering makes equal scores reproducible. |

## Invariants

| ID | Class | Statement | Owner | Counterexample | Gates | Oracle origins |
| --- | --- | --- | --- | --- | --- | --- |
| INV-FTS-NO-RAW-SYNTAX | critical | Raw user FTS operators, quotes, wildcards, punctuation, and controls never become executable MATCH syntax; the compiler emits only allowlisted quoted term conjunctions or a no-query/short-exact value mode. | src/reponpc/retrieval/fts_query.py:compile_fts_query | An input containing OR, NEAR, quotes, parentheses, wildcard, NUL, path punctuation, and a two-character symbol cannot broaden a real FTS5 MATCH result beyond its literal terms. | GATE-FTS-UNIT, GATE-FTS-SQLITE-INTEGRATION | existing_contract, deterministic_derived |
| INV-RETRIEVAL-PRIMITIVE-SCOPE | noncritical | The primitives own no SQLite connection/schema, provider/network request, embedding identity, bundle compatibility/readiness, public API, logging, or RRF policy. | src/reponpc/retrieval/fts_query.py and src/reponpc/retrieval/vector.py | Compile and rank supplied values against a temporary FTS5 table/NumPy matrix with no network client or persistent production store. | GATE-FTS-SQLITE-INTEGRATION, GATE-VECTOR-UNIT, GATE-PYTHON-ALL | existing_contract, deterministic_derived |
| INV-VECTOR-STABLE-RANK | noncritical | Cosine/dot scores for valid normalized vectors rank descending and use evidence ID ascending as the deterministic equal-score tie-breaker. | src/reponpc/retrieval/vector.py:rank_vectors | Two distinct IDs with equal dot product are returned in lexical ID order and limit truncation preserves that order. | GATE-VECTOR-UNIT | existing_contract, deterministic_derived |
| INV-VECTOR-VALIDATION | critical | Vectors entering ranking have an exact declared dimension, finite float32 values, nonzero unit norms, one unique evidence ID per row, and a read-only normalized matrix representation. | src/reponpc/retrieval/vector.py:validate_vector_matrix and validate_query_vector | A wrong-dimension, NaN, Inf, zero, non-unit, duplicate-ID, empty/mismatched matrix input fails before any score is returned. | GATE-VECTOR-UNIT, GATE-VECTOR-BUNDLE-INTEGRATION | existing_contract, deterministic_derived |

## Acceptance gates

| ID | Scope | Command | Oracle | Artifact | Invariants | Blocking | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GATE-FTS-SQLITE-INTEGRATION | integration | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-03-fts-integration -p no:cacheprovider tests/integration/test_fts_query.py -q | Compiler output is passed unchanged as a bound value to real FTS5 term/trigram tables; injection-shaped inputs cannot broaden results or execute syntax. | .agent-foreman/phase2-retrieval-primitives/artifacts/gate-fts-sqlite-integration.txt | INV-FTS-NO-RAW-SYNTAX, INV-RETRIEVAL-PRIMITIVE-SCOPE | true | passed |
| GATE-FTS-UNIT | component | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-03-fts-unit -p no:cacheprovider tests/unit/test_fts_query.py -q | Normal, quoted/operator, punctuation/control, short-symbol, Chinese, and empty compiler cases emit the exact allowlisted mode and query/value representation. | .agent-foreman/phase2-retrieval-primitives/artifacts/gate-fts-unit.txt | INV-FTS-NO-RAW-SYNTAX | true | passed |
| GATE-PYTHON-ALL | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-03-p2-04-all -p no:cacheprovider -q | All existing and primitive tests pass together and report platform-limited skips exactly. | .agent-foreman/phase2-retrieval-primitives/artifacts/gate-python-all-r2.txt | INV-RETRIEVAL-PRIMITIVE-SCOPE | true | passed |
| GATE-VECTOR-BUNDLE-INTEGRATION | integration | Deferred: load real P2-06 embedding blobs and verify declared adapter/model/dimension/prefix compatibility before ranking. | A real bundle mismatch prevents readiness and valid blobs preserve evidence ID ordering without altered bytes. | .agent-foreman/phase2-retrieval-primitives/artifacts/gate-vector-bundle-integration.txt | INV-VECTOR-VALIDATION | false | not_run |
| GATE-VECTOR-UNIT | component | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-04-vector -p no:cacheprovider tests/unit/test_vector.py -q | Finite/normalized/dimension/ID validation rejects malformed inputs and valid ranking has exact scores, stable ties, and bounded limit behavior. | .agent-foreman/phase2-retrieval-primitives/artifacts/gate-vector-unit-r2.txt | INV-VECTOR-VALIDATION, INV-VECTOR-STABLE-RANK, INV-RETRIEVAL-PRIMITIVE-SCOPE | true | passed |

## Evidence ledger

No evidence has been recorded.

## Stop conditions

- Stop and ask the owner before changing FTS schema/tokenizer, configuration/query limits, RRF/metadata policy, provider/model identity, bundle compatibility/readiness, endpoint/API behavior, or dependency manager.
- Do not claim real vector-bundle compatibility before P2-06 SQLite/blob loading exists.
- A blocking FTS/vector gate failure after one precise Main repair returns the affected primitive to Main replan.

## Fallback

- Mode: `single_main`
- Triggers: SQLite FTS5 unavailable in the supported Python build; A required schema/provider/bundle contract change appears; A critical deterministic gate fails after one precise repair; A future consumer requires an unowned behavior

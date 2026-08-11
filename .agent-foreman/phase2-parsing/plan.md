# Plan REPONPC-P2-02-PARSING-20260810

## Objective

Add deterministic bounded Tree-sitter and text chunk candidates for Python, JavaScript, TypeScript/TSX, Go, Rust, Markdown, and fallback text without changing public configuration, evidence IDs, or index/bundle behavior.

## Main model

- Source: `current_conversation`
- Resolved model: ``
- Verification: `unavailable`

## Architecture decision

- Mode: `main_direct`
- Profile: `minimal`
- Advisor required: `false`
- Reasons: The parser registry, third-party grammar/lockfile choice, candidate contract, and future producer-to-consumer seam are shared Main-owned responsibilities.; The only potential parser leaves cannot be delegated safely until their grammar API, registry protocol, and independent integration oracle are established.

## Current-state evidence

| Path | Symbol | Observation | Status |
| --- | --- | --- | --- |
| docs/SUBAGENT_EXECUTION_PLAYBOOK.md | P2-02 | P2-02 requires language golden tests and a future Main producer-to-consumer integration from eligible source bytes to accepted evidence records. | observed |
| docs/TECHNICAL_SPEC.md | sections 5.3 and 4.3 | Supported Tree-sitter languages are Python, JavaScript/TypeScript, Go, and Rust; named symbols should be preferred, oversized nodes split deterministically, fallback is bounded, and line ranges are one-based inclusive. | observed |
| pyproject.toml and uv.lock | project dependencies | Tree-sitter and NumPy are absent from the locked Python environment; adding grammar bindings requires a normal uv dependency/lock update under ADR-012. | observed |
| src/reponpc/indexing/line_chunker.py | chunk_text | A deterministic bounded line fallback exists, but there is no parser registry, source-language dispatch, syntax candidate type, Markdown sectioning, or Tree-sitter dependency. | observed |

## Control flow

| ID | Kind | Path | Symbol | Next | Failure path |
| --- | --- | --- | --- | --- | --- |
| FLOW-EVIDENCE-BUILDER | future_producer_consumer | P2-06 index writer (not yet implemented) | candidate-to-evidence conversion |  | No current evidence writer consumes candidates, so the real source-to-evidence integration gate remains deferred rather than claimed passed. |
| FLOW-PARSER-DISPATCH | future_indexing_intake | src/reponpc/indexing/parsing.py | chunk_source | FLOW-EVIDENCE-BUILDER | Unsupported or syntactically invalid source returns deterministic bounded fallback candidates; no parser exception or unbounded node can reach a future evidence writer. |

## Invariants

| ID | Class | Statement | Owner | Counterexample | Gates | Oracle origins |
| --- | --- | --- | --- | --- | --- | --- |
| INV-LOCKED-DEPENDENCIES | noncritical | Required parser bindings are declared through uv and recorded in uv.lock; no second package manager or unpinned runtime package is introduced. | pyproject.toml and uv.lock | Run uv lock --check and import each configured grammar in the locked environment. | GATE-PARSER-IMPORTS, GATE-PY-LOCK | existing_contract, deterministic_derived |
| INV-PARSER-BOUNDS | critical | Every emitted candidate is nonempty and obeys configured character and line bounds; oversized syntax nodes split on deterministic child boundaries before falling back to bounded line windows. | src/reponpc/indexing/parsing.py:chunk_source | A class/function or one source line larger than max_characters yields deterministic bounded fragments that cover the original normalized content. | GATE-PARSING-UNIT, GATE-PARSER-CONSUMER-INTEGRATION | existing_contract, deterministic_derived |
| INV-PARSER-DETERMINISTIC | critical | For identical bytes, path, language, and limits, parser dispatch returns the same ordered symbol/text candidates with one-based inclusive line ranges and normalized LF content. | src/reponpc/indexing/parsing.py:chunk_source | Run a nested Python/JS/TS/Go/Rust fixture with CRLF and multibyte text twice, then compare all candidates and their line coordinates. | GATE-PARSING-UNIT, GATE-PARSER-CONSUMER-INTEGRATION | existing_contract, deterministic_derived |
| INV-PARSER-SCOPE | noncritical | P2-02 only parses already-eligible supplied text; it does not fetch repositories, read source paths, alter exclusion/configuration policy, construct evidence IDs, write SQLite, or change bundle behavior. | src/reponpc/indexing/parsing.py | A path-like input must be metadata only and source parsing succeeds without a filesystem/network adapter. | GATE-PARSING-UNIT, GATE-PYTHON-ALL | existing_contract, deterministic_derived |

## Acceptance gates

| ID | Scope | Command | Oracle | Artifact | Invariants | Blocking | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GATE-PARSER-CONSUMER-INTEGRATION | integration | Deferred: send real eligible source bytes through the future P2-06 index intake and evidence writer. | The unchanged parser candidate content/ranges become accepted evidence records and malformed/oversize inputs cannot reach the writer unbounded. | .agent-foreman/phase2-parsing/artifacts/gate-parser-consumer-integration.txt | INV-PARSER-DETERMINISTIC, INV-PARSER-BOUNDS | false | not_run |
| GATE-PARSER-IMPORTS | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python python -c "import tree_sitter, tree_sitter_go, tree_sitter_javascript, tree_sitter_python, tree_sitter_rust, tree_sitter_typescript" | The locked runtime imports the parser core and every required language binding. | .agent-foreman/phase2-parsing/artifacts/gate-parser-imports.txt | INV-LOCKED-DEPENDENCIES | true | passed |
| GATE-PARSING-UNIT | component | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-02-parsing -p no:cacheprovider tests/unit/test_parsing.py -q | Language, fallback, CRLF, multibyte, syntax-error, nested-symbol, and oversize fixtures return exact bounded candidates and coordinates. | .agent-foreman/phase2-parsing/artifacts/gate-parsing-unit.txt | INV-PARSER-DETERMINISTIC, INV-PARSER-BOUNDS, INV-PARSER-SCOPE | true | passed |
| GATE-PY-LOCK | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache lock --check --offline | uv confirms pyproject.toml and uv.lock describe the same locked dependency graph. | .agent-foreman/phase2-parsing/artifacts/gate-py-lock.txt | INV-LOCKED-DEPENDENCIES | true | passed |
| GATE-PYTHON-ALL | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-02-all -p no:cacheprovider -q | All existing and P2-02 Python tests pass together, with any platform-limited skips reported exactly. | .agent-foreman/phase2-parsing/artifacts/gate-python-all.txt | INV-PARSER-SCOPE | true | passed |

## Evidence ledger

No evidence has been recorded.

## Stop conditions

- Stop and request owner direction before changing public configuration limits/patterns, evidence-ID or schema contracts, source acquisition/network policy, bundle behavior, or adding a service/provider.
- Do not call the future source-to-evidence integration proved before a P2-06 writer exists.
- Fail closed and retain Main ownership if the selected grammar packages cannot support the approved Python runtime or locked dependency policy.

## Fallback

- Mode: `single_main`
- Triggers: Grammar API incompatibility or unavailable package support; A source-to-evidence contract change is required; A blocking parser gate fails after one precise Main repair; A new external/network or configuration requirement appears

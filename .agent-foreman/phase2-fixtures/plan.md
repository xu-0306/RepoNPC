# Plan REPONPC-P2-05-FIXTURES-20260810

## Objective

Create a license-safe public retrieval fixture corpus for Phase 2 without creating expected-evidence oracle material, benchmark thresholds, scorer logic, or production retrieval behavior.

## Main model

- Source: `current_conversation`
- Resolved model: ``
- Verification: `unavailable`

## Architecture decision

- Mode: `main_direct`
- Profile: `minimal`
- Advisor required: `false`
- Reasons: The fixture corpus establishes future retrieval and security test inputs, while hidden expected-evidence material must remain Main-owned and host oracle isolation is only best-effort.; Actual worker model identity is unavailable, and the required corpus spans multiple interdependent source/configuration fixtures beyond the degraded one-file/one-test delegation limit.

## Current-state evidence

| Path | Symbol | Observation | Status |
| --- | --- | --- | --- |
| docs/ACCEPTANCE_CRITERIA.md | sections 1-3 and AC-033 | Committed non-secret fixtures must contain Traditional Chinese and English material, exact symbols/paths, owner assertions, negative questions, malicious instructions, and deliberately unsupported person claims. | observed |
| docs/SUBAGENT_EXECUTION_PLAYBOOK.md | P2-05 | P2-05 creates only named public source fixtures; expected evidence, benchmark thresholds, scorer, and hidden probes remain Main-owned and prohibited. | observed |
| tests/fixtures and evals | filesystem state | No fixture-corpus or evaluation directory exists yet, so P2-05 must establish the public source material before P2-06/P2-07 consume it. | observed |

## Control flow

| ID | Kind | Path | Symbol | Next | Failure path |
| --- | --- | --- | --- | --- | --- |
| FLOW-P2-06-INDEX-BUILDER | future_producer-consumer | P2-06 index builder (not yet implemented) | fixture source/configuration to evidence/index bundle | FLOW-P2-07-HIDDEN-ORACLE | No P2-06 writer exists; public fixtures are not evidence records and cannot prove retrieval or benchmark outcomes alone. |
| FLOW-P2-07-HIDDEN-ORACLE | future-evaluation | P2-07 Main-owned scorer/oracle (not yet implemented) | question/evidence expectations and benchmark thresholds |  | Expected-evidence material and score policy remain absent from the P2-05 public corpus to avoid training fixtures against their own answers. |
| FLOW-PUBLIC-FIXTURE-CORPUS | fixture-input | tests/fixtures/phase2/reponpc.yml and tests/fixtures/repos/reponpc-demo | license-safe public configuration and source material | FLOW-P2-06-INDEX-BUILDER | A missing required topic, live secret-like credential, invalid public configuration, or oracle declaration fails the fixture gate before the corpus becomes an index input. |

## Invariants

| ID | Class | Statement | Owner | Counterexample | Gates | Oracle origins |
| --- | --- | --- | --- | --- | --- | --- |
| INV-FIXTURE-BILINGUAL-COVERAGE | critical | The public corpus supplies exact stable symbols/paths, English and Traditional Chinese equivalent retrieval material, explicit owner assertions, overlap material, unsupported person-claim material, and repository prompt-injection text. | tests/unit/test_phase2_fixture_corpus.py:test_fixture_corpus_contains_required_retrieval_and_adversarial_material | Removing the bilingual architecture explanation, `rank_evidence` symbol, explicit claim, unsupported-claim disclaimer, or delimited malicious instruction causes the deterministic fixture gate to fail. | GATE-FIXTURE-CORPUS, GATE-FIXTURE-CONSUMER-INTEGRATION | existing_contract, deterministic_derived |
| INV-FIXTURE-CORPUS-SAFETY | critical | Every P2 fixture is authored, license-safe, non-secret material; it contains no live credential, personal data, or externally copied source, and adversarial instruction text remains inert fixture data. | tests/unit/test_phase2_fixture_corpus.py:test_fixture_corpus_is_license_safe_and_contains_no_live_secret_patterns | A fixture path containing a GitHub-token-shaped string, PEM private-key header, external URL fetch instruction, or a missing local MIT license fails the deterministic fixture gate. | GATE-FIXTURE-CORPUS, GATE-FIXTURE-CONSUMER-INTEGRATION | existing_contract, deterministic_derived |
| INV-FIXTURE-ORACLE-SEPARATION | noncritical | Public fixtures declare inputs only; they contain no expected-evidence IDs, benchmark targets, score policy, or hidden evaluator probe definitions. | tests/unit/test_phase2_fixture_corpus.py:test_public_fixture_corpus_does_not_declare_an_evaluation_oracle | A public fixture containing `expected_evidence`, `recall_at_8`, or a P2-07 controller declaration fails the deterministic fixture gate. | GATE-FIXTURE-CORPUS, GATE-FIXTURE-CONSUMER-INTEGRATION | existing_contract, deterministic_derived |

## Acceptance gates

| ID | Scope | Command | Oracle | Artifact | Invariants | Blocking | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GATE-FIXTURE-CONSUMER-INTEGRATION | integration | Deferred: run the unchanged P2-05 configuration and source fixture repository through the real P2-06 source-to-evidence-to-bundle pipeline, then score with a separate P2-07 Main-owned oracle. | Real source/configuration inputs retain their declared metadata and cannot become a self-revealing expected-evidence oracle after indexing. | .agent-foreman/phase2-fixtures/artifacts/gate-fixture-consumer-integration.txt | INV-FIXTURE-CORPUS-SAFETY, INV-FIXTURE-BILINGUAL-COVERAGE, INV-FIXTURE-ORACLE-SEPARATION | false | not_run |
| GATE-FIXTURE-CORPUS | component | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-05-fixtures -p no:cacheprovider tests/unit/test_phase2_fixture_corpus.py -q | The named configuration/source fixtures validate, contain the required bilingual/adversarial inputs, carry a local licence, contain no live-secret patterns, and declare no evaluation answer key. | .agent-foreman/phase2-fixtures/artifacts/gate-fixture-corpus.txt | INV-FIXTURE-CORPUS-SAFETY, INV-FIXTURE-BILINGUAL-COVERAGE, INV-FIXTURE-ORACLE-SEPARATION | true | passed |
| GATE-PYTHON-ALL | system | rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-05-all -p no:cacheprovider -q | The complete Python suite accepts the fixture addition without weakening Phase 1/P2 behavior. | .agent-foreman/phase2-fixtures/artifacts/gate-python-all.txt | INV-FIXTURE-CORPUS-SAFETY, INV-FIXTURE-BILINGUAL-COVERAGE, INV-FIXTURE-ORACLE-SEPARATION | true | passed |

## Evidence ledger

No evidence has been recorded.

## Stop conditions

- Stop and ask the owner before adding a real external corpus, personal datum, configuration/public contract change, benchmark threshold, expected-evidence mapping, or production retrieval behavior.
- Do not claim retrieval quality, bilingual parity, prompt-injection resistance, source exclusion, or bundle behavior before P2-06/P2-07 consume this corpus through real producer/consumer gates.
- Keep expected evidence, scorer logic, and hidden evaluator probes outside the P2-05 public fixture paths.

## Fallback

- Mode: `single_main`
- Triggers: A fixture needs a new public configuration or source contract; Any material looks secret-like, licensed externally, or personally identifying; A fixture test conflicts with the separate-oracle boundary; A future P2-06 consumer requires a schema decision

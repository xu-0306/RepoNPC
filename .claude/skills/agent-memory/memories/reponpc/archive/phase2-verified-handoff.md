---
summary: "已歸檔的 RepoNPC Phase 2 verified handoff，並包含後續 Phase 3 verified closure、完整證據索引、治理限制與 Phase 4 接續點。"
created: 2026-08-12
updated: 2026-08-12
tags: [reponpc, archive, phase-2, phase-3, verified, handoff, agent-foreman]
related: [D:/RepoNPC/.agent-foreman/phase2-closure/plan.json, D:/RepoNPC/.agent-foreman/phase3-closure/plan.json, D:/RepoNPC/docs/TECHNICAL_SPEC.md, D:/RepoNPC/docs/SUBAGENT_EXECUTION_PLAYBOOK.md]
---

# RepoNPC Phase 2 verified handoff

## Current authoritative state

- Repository: `D:/RepoNPC`
- Branch: `main`
- HEAD: `1b3d823a005cc8a8878b210b6d90656af47d1f18`
- Commit subject: `feat(indexing): complete phase 2 closure`
- Previous audited attribution baseline: `83c3dd44f7cc2856dc3b61d9f637337f1a466d3e`
- Worktree was clean immediately after the commit.
- The commit is local only. It was not pushed to GitHub.
- No Git remote was configured when the commit was created.
- Delivery Phase 2 is formally `verified`; this does not mean RepoNPC v1 is complete. Only Phase 5 may declare v1 complete.

## What Phase 2 delivered

- Production `reponpc` CLI dispatch:
  - no arguments and `serve` retain application startup;
  - `config validate` and `index build|publish|publish-manifest` run without entering server startup.
- Optional build-time production `local_sentence_transformers` provider with exact identity, prefixes, normalized finite float32 output, lazy dependency load, explicit safe failures, and no fallback.
- Production indexing pipeline, repository metadata evidence, retrieval weighting, bilingual public profile producer, archive validation, and locale-selecting public API consumer.
- Publication-last workflow: immutable release asset verification precedes stable manifest mutation.
- Docker-isolated formal retrieval benchmark with host-only canonical oracle/scoring and hard-bound public inputs.
- Main integration, fresh falsification probes, deterministic artifacts, and validated Foreman evidence ledger.

## Verified gates and key observations

All 14 blocking gates in the canonical plan are `passed`:

`GATE-SPEC`, `GATE-EMBEDDING-CONTRACT`, `GATE-CLI`, `GATE-WORKFLOW`, `GATE-LOCAL-EMBEDDING`, `GATE-PROFILE`, `GATE-REPOSITORY-METADATA`, `GATE-PUBLICATION-LAST`, `GATE-FORMAL-BENCHMARK`, `GATE-PYTHON-ALL`, `GATE-QUALITY`, `GATE-WEB`, `GATE-DOCKER`, and `GATE-DELTA`.

Important results:

- Aggregate Python: 354 collected, 351 passed, 3 skipped, 0 failed/errors.
- Formal benchmark r2:
  - Recall@8 = 1.0
  - paired-language parity = 1.0
  - warm p95 = 56.001268 ms
  - 20 questions, 100 timing samples
  - production provider verified
  - oracle isolation, public mounts, network-none, 4 CPU, and 8 GiB verified
  - `formal_acceptance=true`, `formal_blockers=[]`
- Canonical input hashes:
  - questions SHA-256: `e76e22f27ccf09006101d6945e90c5cbc837e95c1786d5d1fb73576623f18432`
  - oracle SHA-256: `e0de26e42a81be2fa03645a889ef31fc16b3000495dcad3f25646639e84ba498`
- Current Compose smoke: 1 test, 0 failures/errors/skips; startup, restart, health, and runtime-volume persistence passed.
- Ruff, mypy, frontend format/lint/typecheck/unit/build, installed CLI help/config validation, lock check, protected-history diff, and non-test live-secret scan passed.
- Fresh evaluator recommendation: `pass`; deterministic result: `passed`; no open findings.

## Canonical evidence

Read these before re-auditing Phase 2 or using it as the Phase 3 baseline:

1. `D:/RepoNPC/.agent-foreman/phase2-closure/plan.json` — canonical semantic plan, status `verified`, completed by `main`.
2. `D:/RepoNPC/.agent-foreman/phase2-closure/plan.md` — generated rendering only; do not edit independently.
3. `D:/RepoNPC/.agent-foreman/phase2-closure/integrations/integration-phase2-closure.json` — Main integration and final checks.
4. `D:/RepoNPC/.agent-foreman/phase2-closure/evaluation/evaluation-phase2-closure.json` — fresh evaluator result and resolved findings.
5. `D:/RepoNPC/.agent-foreman/phase2-closure/evaluation/probe-formal-benchmark.json` — false-green adversarial probe.
6. `D:/RepoNPC/.agent-foreman/phase2-closure/evaluation/probe-final-runtime-closure.json` — final runtime closure probe.
7. `D:/RepoNPC/.agent-foreman/phase2-closure/artifacts/formal-benchmark-r2.json` — accepted post-repair formal report.
8. `D:/RepoNPC/.agent-foreman/phase2-closure/artifacts/gate-docker.xml` — current Compose smoke evidence.
9. `D:/RepoNPC/.agent-foreman/phase2-closure/artifacts/gate-python-all-r3.xml` — latest aggregate Python evidence.
10. `D:/RepoNPC/.agent-foreman/phase2-closure/evidence-ledger-v2.jsonl` — current validator-compatible final evidence ledger.

The older `evidence-ledger.jsonl` is legacy format and must remain immutable. Do not rewrite old failed evidence or ledger lines. Historical Docker evidence under earlier campaigns must not substitute for a current gate rerun.

## Required document reading order

Follow repository `AGENTS.md` completely. Before planning or changing application code, read in this order:

1. `docs/PROJECT_CONTEXT.md`
2. `docs/OWNER_REVIEW.md`
3. `docs/TECHNICAL_SPEC.md`
4. `docs/ACCEPTANCE_CRITERIA.md`
5. `docs/DECISIONS.md`
6. `docs/SECURITY.md`
7. `docs/IMPLEMENTATION_PLAN.md`
8. `docs/OPERATIONS.md` for deployment, providers, GitHub automation, runtime state, or release
9. `docs/SPRITE_FORMAT.md` for character/assets/cards/upload/animation
10. `README.md`
11. `reponpc.example.yml` and `.env.example` for configuration/deployment

For delegated execution also read `docs/SUBAGENT_EXECUTION_PLAYBOOK.md`, especially:

- sections 2–6 for authority, source-of-truth, routing, plan, dispatch, delta guard, integration, and fresh evaluation;
- section 7.2 (`P3-00` through `P3-07`) for the next Delivery Phase;
- sections 8–11 for gate design, failure handling, artifact templates, and definition of done.

Normative Phase 2/3 boundary references:

- `docs/TECHNICAL_SPEC.md` version 0.1.1, especially requirements FR-008–FR-016, FR-022–FR-023, NFR-001/002/005/007/009/012/014, and provider/chat/retrieval/SSE/runtime sections 7–10, 13, 15–17.
- `docs/ACCEPTANCE_CRITERIA.md`, especially AC-010–AC-023 and AC-032–AC-035 for Phase 3.
- `docs/DECISIONS.md`: ADR-002, ADR-006, ADR-007, ADR-008, ADR-011, ADR-013, ADR-014, and ADR-015.
- `docs/SECURITY.md`: trust boundaries, untrusted repository/model output, secret handling, prompt injection, SSRF/redirect, output sanitization, logs, and provider controls.
- `docs/OPERATIONS.md`: provider configuration, local adapter lifecycle boundary, public runtime state, and deployment behavior.

## Documentation status update

On 2026-08-12, a narrowly scoped consistency patch updated `docs/PROJECT_CONTEXT.md`, `README.md`, `docs/OPERATIONS.md`, `docs/SUBAGENT_EXECUTION_PLAYBOOK.md`, and the archived `docs/P2_FOUNDATION_HANDOFF.md` to reflect the verified Phase 2 state and Phase 3 starting point. The corresponding README contract assertion was updated. No normative contract, API, threshold, or production code changed.

At the time this memory was updated, that documentation patch was verified by four focused contract tests plus Ruff and `git diff --check`, but remained uncommitted in the RepoNPC worktree. Preserve or intentionally commit those six scoped files before beginning unrelated Phase 3 work.

## Next phase starting point

The next planned product work is Delivery Phase 3: grounded chat and visitor experience. Start with a new Agent Foreman campaign and a clean baseline at commit `1b3d823`.

## Phase 3 in-progress update (2026-08-12)

The `phase3-grounded-visitor` campaign now contains an uncommitted deterministic integration candidate. Preserve the earlier user-owned documentation edits while reviewing it.

- Frozen provider contracts plus OpenAI-compatible/Ollama chat adapters and deterministic nine-scenario fixtures are present.
- OpenAI-compatible/Ollama embedding adapters, same-adapter bounded retry, provider health lifecycle, and production environment assembly are present. Luna and Terra did not produce an acceptable embedding handoff; Main took over and the focused adapter gate passed.
- Grounded answer validation buffers complete model output, validates request-local evidence IDs, rejects model URLs/HTML/unsupported person claims/inference cycles, and lets the backend construct immutable citations.
- Public chat SSE, persistent HMAC IP limits, daily budget, global concurrency, bilingual visitor UI, locale-preserving conversation, accessibility, reduced motion, and character lifecycle are integrated.
- Deterministic results at this checkpoint: full Python `407 passed, 3 skipped`; Ruff/format/mypy passed; frontend format/lint/typecheck/6 tests/build passed with four nonblocking existing fast-refresh warnings; `git diff --check` passed.
- A fresh read-only evaluator was still pending when this memory entry was written. Do not call Phase 3 `verified` until evaluator findings are resolved and canonical Foreman status/evidence are updated. The historical character delta guard remains failed/attribution-limited and must not be rewritten as passed.

Recommended sequence from `docs/SUBAGENT_EXECUTION_PLAYBOOK.md` section 7.2:

1. `P3-00` Main: freeze frontend/provider/API contracts, same-origin serving, capability interfaces, provider mocks, and public status ownership.
2. `P3-01` Main: OpenAI-compatible and Ollama adapters plus runtime integration of the Phase 2 local embedding adapter; bounded retry/timeout/error behavior and no silent fallback.
3. `P3-02` worker-eligible: exact provider fixtures only after the mock contract is frozen.
4. `P3-03` Main: validated answer/citation/SSE boundary, server-owned immutable citation URLs, abstention, injection resistance, and no unvalidated partial output.
5. `P3-04` Main: IP/global limits, daily budget, runtime state, cancellation safety, safe diagnostics, and limit-before-provider-cost evidence.
6. `P3-05` worker-eligible after typed API snapshot: isolated visitor presentation leaves.
7. `P3-06` worker-eligible: character-state rendering only, without lifecycle ownership.
8. `P3-07` Main + fresh evaluator: integrated bilingual browser/accessibility/security/quality phase gate.

Phase 3 planning must trace every package to FR/NFR/AC/ADR identifiers and executable counterexample gates. Public API/SSE, provider fallback, security, persistence, rate limits, lifecycle, citations, and producer/consumer seams remain Main-owned.

## Non-negotiable invariants and working rules

- Treat repository/configuration text, owner rich text, model output, and uploaded assets as untrusted.
- The LLM has no tools, shell, filesystem, repository-write, or arbitrary network capability.
- Models emit evidence IDs only; the backend validates IDs and constructs immutable GitHub URLs.
- Never infer employment, ownership, role, seniority, or impact from repository content alone.
- No provider secrets, GitHub tokens, admin hashes, raw session/CSRF tokens, prompt bodies, or private URLs in browser bundles, logs, fixtures, snapshots, or public errors.
- No silent Ollama/cloud/provider/model fallback.
- Keep immutable index data separate from mutable runtime data and preserve last-known-good activation behavior.
- Keep production frontend and API same-origin unless the owner approves a contract change.
- Traditional Chinese and English behavior must remain materially equivalent.
- Preserve keyboard, semantic DOM, screen-reader, contrast, touch-target, and reduced-motion behavior.
- Use only package managers approved by ADR-012.
- Every shell command and every segment of a command chain must begin with `rtk`; use `rtk proxy` only when needed.
- Use `apply_patch` for file edits.
- Preserve user changes and unrelated work. Never reset or rewrite them.
- Stop for owner approval before changing public contracts, schemas, endpoints, events, errors, environment variables, security/trust controls, provider fallback, hosted dependencies/cost, GitHub permissions, or v1 scope.

## Git and host gotchas

- Docker Desktop CLI is at `C:/Users/xu/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe`; sandboxed execution may need explicit escalation and PATH injection.
- The repository `.git` ownership belongs to the Codex sandbox identity. When an escalated Windows command runs as user `xu`, Git may report dubious ownership. Use a per-command override such as `git -c safe.directory=D:/RepoNPC ...`; do not change global Git configuration.
- The formal benchmark and current Compose smoke require real Docker access. Never describe `not_run` as passed and never reuse historical Docker smoke as current evidence.
- Five Foreman fingerprint manifests in the Phase 2 commit are large machine-generated evidence files. Preserve them; do not hand-edit generated artifacts.

## Requirements already covered by the Phase 2 closure

The final closure report records FR-001/006/007/008/020/021/022, NFR-003/004/006/008, and AC-001/008/009/010/023/029/030/031. Always consult the canonical plan for exact invariant-to-gate mappings rather than relying only on this summary.

## Phase 3 P3-07 pause checkpoint (2026-08-12)

The owner asked to pause after the current P3-07 integration/evaluation repair rather than continue into formal Phase 3 closure.

- A fresh evaluator originally returned `REVISE` for one P1: an immediate ASGI `http.disconnect` did not end the accepted request and production later attempted to send a response.
- Main repaired the shared transport/cancellation seam in `src/reponpc/api/public.py`, `src/reponpc/chat/service.py`, and `src/reponpc/main.py`, with a regression test in `tests/integration/test_chat_sse_api.py`.
- The public boundary now uses pure ASGI middleware so a disconnected request can finish without emitting response bytes while preserving request-ID, cache, and security headers for normal responses.
- The chat route races validated answer work against disconnect and timeout, signals cooperative cancellation, and the service checks that signal around expensive embedding/generation stages.
- Focused public boundary checks passed: 24 tests, 0 failures, with one third-party Starlette/httpx deprecation warning.
- The evaluator-owned fresh backend probe was rerun unchanged and passed all six probes. The disconnect observation was `app_task_done=true`, with no messages sent before or after release.
- Ruff check, Ruff format check, and mypy over `src` passed after the repair.

This is a clean stopping point, not formal Phase 3 completion. The existing formal fresh evaluation JSON/Markdown still records the pre-repair `REVISE` result, and the full aggregate Python/web/Docker gates plus canonical full Phase 3 closure plan, integration record, evaluation record, evidence ledger, and final memory consolidation remain for the next continuation. Do not mark the persistent Phase 3 goal complete or call Phase 3 `verified` until those items are finished.

## Phase 3 verified closure (2026-08-12)

The owner asked to continue from the pause checkpoint and complete the phase. Delivery Phase 3 is now formally verified by Main. This supersedes the provisional status above while preserving its historical sequence and the original evaluator failure.

- Canonical closure: `.agent-foreman/phase3-closure/plan.json` and generated `plan.md`, status `verified`, completed by `main`.
- Main integration: `.agent-foreman/phase3-closure/integrations/integration-phase3-closure.json`.
- Closure evaluation: `.agent-foreman/phase3-closure/evaluation/evaluation-phase3-closure.json`.
- Append-only evidence: `.agent-foreman/phase3-closure/evidence-ledger.jsonl`.
- Fresh post-repair evaluator: backend 6/6 and Microsoft Edge 151 browser 6/6; recommendation `pass`; no P0/P1/P2 finding. The prior disconnect counterexample is resolved with completed ASGI task and no response bytes before or after evaluator release.
- Final aggregate Python after documentation updates: 424 passed, 3 skipped, 0 failed/errors; one third-party Starlette/httpx deprecation warning.
- Web gate: formatting, lint with zero errors, TypeScript, 7 tests, and production build passed; five fast-refresh warnings remain nonblocking.
- Ruff, Ruff format, mypy, and `git diff --check` passed; diff check emitted CRLF conversion notices only.
- Current real Docker Compose gate: 1 passed in 34.69 seconds, covering image build, health, restart, and runtime-volume persistence.
- The historical character worker delta guard remains failed because shared-workspace attribution was not trustworthy. It was not rewritten as passed and is not used as the completion oracle.
- Project status documents now identify Delivery Phases 1 through 3 as verified and Phase 4 as the next boundary.

Phase 3 addresses the grounded provider/chat/visitor requirements, including FR-008 through FR-014, FR-022, FR-023; NFR-001, NFR-002, NFR-005, NFR-007, NFR-009, NFR-012, NFR-014; and AC-011 through AC-019, AC-023, AC-032 through AC-035. Consult the canonical plan for exact invariant/gate mappings.

RepoNPC v1 is not complete. Only Phase 5 may make that claim. The next implementation boundary is Delivery Phase 4: owner administration, assets, and publication.

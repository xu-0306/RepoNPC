# RepoNPC P2-00 Foundation Handoff and Review Plan

| Field | Value |
| --- | --- |
| Handoff status | `COMPLETE` |
| Campaign | `REPONPC-P2-FOUNDATION-20260810` |
| Execution mode | Single implementation Main; no worker delegation |
| Receiving role | Implementer and integration owner |
| Returning role | Read-only reviewer when explicitly requested |
| Last handoff update | 2026-08-10 |
| Scope | P2-00 plus every Delivery Phase 1 carry-forward item from Implementation Plan Milestone 1 |

## 1. How to use this document

This is the live handoff, execution checklist, evidence index, and review-request form for the next Agent. The receiving Agent should:

1. read every required source in section 3;
2. verify the frozen campaign plan before editing;
3. execute sections 6 through 14 in order;
4. update the progress tables, evidence log, changed-file manifest, and blocker fields in this document after each step;
5. request review at checkpoints `R1`, `R2`, and `R3` using the form in section 17;
6. keep implementing until all blocking gates pass or a genuine owner/external blocker is recorded.

The reviewer should inspect repository evidence and append a review record in section 18. The reviewer does not implement repairs unless the owner explicitly changes that role.

Do not use conversational memory as the source of truth. If a claim is not in the repository or a linked artifact, treat it as unverified.

### 1.1 Fields the receiving Agent must maintain

The receiving Agent may update these live sections:

- section 2, `Current handoff state`;
- section 5, `Changed-file manifest`;
- section 15, `Execution tracker`;
- section 16, `Evidence log`;
- section 17, `Review request`;
- section 19, `Blockers, risks, and decisions`.

Do not silently rewrite the scope, source-of-truth order, frozen contract statements, gate oracles, or reviewer findings. A needed contract/gate change must be proposed in section 19 and reviewed before implementation continues.

### 1.2 Status vocabulary

Use only:

- `NOT_STARTED`;
- `IN_PROGRESS`;
- `IMPLEMENTED` — code exists and focused checks pass, not yet reviewed;
- `REVIEW_REQUESTED`;
- `REVIEWED_PASS`;
- `REVIEWED_REVISE`;
- `BLOCKED`;
- `NOT_RUN` — only for a named unavailable external gate;
- `COMPLETE` — only after final deterministic gates and reviewer `R3` pass.

## 2. Current handoff state

### 2.1 Work completed before handoff

- Technical Specification 0.1.0 and ADR-001 through ADR-014 are approved/accepted.
- Delivery Phase 1 is implemented and verified under `.agent-foreman/mvp/`.
- The Subagent Execution Playbook is available at `docs/SUBAGENT_EXECUTION_PLAYBOOK.md`.
- The P2-00 Main-direct campaign was created at `.agent-foreman/phase2-foundation/`.
- `plan.json` validates against `agent-foreman/plan` 1.0.
- `plan.md` was rendered from the validated JSON.
- The plan explicitly includes Python type checking, uv lock/build verification, deployment contract validation, and a real container smoke gate.

### 2.2 Work not started before handoff

No application or deployment implementation was made during P2-00 preparation. The following are absent and must be implemented by the receiving Agent:

- environment/secret-file loading;
- runtime SQLite schema/migrations;
- safe structured logging;
- GitHub/provider mock servers;
- package/pnpm/TypeScript/Vite workspace;
- built React same-origin serving;
- Dockerfile and Compose;
- GitHub CI workflow;
- new focused/aggregate tests and gate artifacts.

### 2.3 Current verified application baseline

The existing Phase 1 code includes:

- `src/reponpc/config/models.py`;
- `src/reponpc/domain/evidence.py`;
- `src/reponpc/indexing/line_chunker.py`;
- `src/reponpc/retrieval/rrf.py`;
- `src/reponpc/i18n/catalog.py`;
- `src/reponpc/api/public.py`;
- `src/reponpc/main.py`;
- 56 tests recorded passing in the Phase 1 campaign.

The Phase 1 evaluator initially found malformed repository-slug acceptance and private-state reflection; Main repaired both, and all five evaluator probes then passed.

The three original worker delta guards remain failed/non-attributable because the shared non-Git workspace included concurrent writes and cache noise. Never report them as passed.

### 2.4 Tool/environment observations to re-check

Observed in the handing-off environment:

| Tool/state | Observation | Receiving-Agent action |
| --- | --- | --- |
| Python | `3.14.7` at `C:/Python314/python.exe` | Re-probe; use a supported `>=3.12` interpreter |
| uv | `0.12.3` | Re-probe and preserve `uv.lock` |
| Node.js | `v24.14.0` bundled runtime | Re-probe before choosing CI/runtime versions |
| pnpm | `11.16.0` bundled runtime | Use pnpm only; update `pnpm-lock.yaml` mechanically |
| Docker | `docker.exe` was not found | Re-probe. If still absent, the container smoke gate remains `NOT_RUN` and P2-00/Milestone 1 cannot be called complete |
| Git | Repository is not a Git worktree | Use enumerated-path manifests; do not use Git status/diff as proof |

Do not treat a different receiving environment as a contract change. Record its exact runtime/tool versions in section 16.

## 3. Mandatory reading before edits

Read completely, in this order:

1. `AGENTS.md`;
2. `docs/PROJECT_CONTEXT.md`;
3. `docs/OWNER_REVIEW.md`;
4. `docs/TECHNICAL_SPEC.md`;
5. `docs/ACCEPTANCE_CRITERIA.md`;
6. `docs/DECISIONS.md`;
7. `docs/SECURITY.md`;
8. `docs/IMPLEMENTATION_PLAN.md`;
9. `docs/DELIVERY_PHASES.md`;
10. `docs/OPERATIONS.md`;
11. `docs/SPRITE_FORMAT.md`;
12. `docs/SUBAGENT_EXECUTION_PLAYBOOK.md`;
13. `README.md`;
14. `reponpc.example.yml`;
15. `.env.example`;
16. `.agent-foreman/mvp/plan.json`;
17. `.agent-foreman/mvp/integration-mvp-final.json`;
18. `.agent-foreman/mvp/evaluation/evaluation.json`;
19. `.agent-foreman/mvp/evaluation/root-repair-verification.json`;
20. `.agent-foreman/phase2-foundation/plan.json`;
21. this document.

### 3.1 Workstream reference map

| Workstream | Required sections/IDs |
| --- | --- |
| Authority and scope | Project Context 2, 7, 10; Technical Spec approval table, 1–2, 18–20; Delivery Phases scope/completion rules; Playbook 1–6, 11 |
| Milestone 1 carry-forward | Implementation Plan 4, 6, 12, 15; Playbook 3.2 and P2-00 |
| Environment/secrets | Technical Spec 4.1, 4.3, 15.3, 17; Security 2, 6, 7, 11; AC-001, AC-002, AC-035; `.env.example` |
| Runtime SQLite | Technical Spec 6, 14.4, 15.1, 17; ADR-003; Security 2, 7, 9, 11; AC-024, AC-031, AC-035, AC-036; Operations 10–13 |
| Safe logging | Technical Spec 10, 15.3; NFR-002, NFR-012; Security 2, 7, 11–12; AC-035 |
| Mock servers | Technical Spec 11.3, 13, 14; Implementation Plan 6 and 12; ADR-005, ADR-006, ADR-009 |
| Frontend workspace | Technical Spec 3, 9.4, 16; ADR-011, ADR-012; NFR-008, NFR-009, NFR-013; AC-019, AC-023, AC-032, AC-034, AC-036 |
| Same-origin serving | Technical Spec 9, 16; ADR-011; Security 8; AC-019, AC-034, AC-036 |
| Docker/Compose | Technical Spec 3, 15, 19; NFR-010; Security 6, 8, 9, 13; Operations 1, 2, 7, 8, 11, 12; AC-036, AC-037 |
| CI and locked builds | Technical Spec 3, 19; ADR-012; Implementation Plan 4, 6, 11; Security 4, 12; AC-036, AC-037 |

## 4. Authority, scope, and stop conditions

### 4.1 Receiving-Agent authority

The receiving Agent becomes the single implementation Main for P2-00. It owns implementation and integration inside the frozen scope. It must not delegate packages unless the owner/host explicitly authorizes delegation and a new full-profile plan is created and reviewed first.

It may choose internal reversible details that do not change a public contract, security/privacy control, schema contract, environment variable, provider behavior, deployment topology, recurring cost, or v1 scope.

### 4.2 In scope

Close every row of Playbook section 3.2:

1. environment/secret-file loader, collision checks, redacted errors;
2. runtime SQLite schema and transactional migrations;
3. safe structured logging;
4. GitHub/provider mock servers;
5. pnpm/TypeScript/Vite workspace, formatting/lint/type/test/build;
6. built React same-origin serving from FastAPI;
7. Dockerfile/Compose non-root/read-only/persistent/health posture;
8. CI workflow mirroring locked local checks;
9. preservation of all Phase 1 behavior and evidence limitations.

### 4.3 Out of scope

Do not start:

- P2-01 exclusions;
- Tree-sitter adapters;
- FTS5/vector search;
- index/bundle construction or activation;
- real provider or GitHub clients;
- chat, SSE, citations, visitor product UI, admin, cards/assets, or Actions publication.

Mocks and schemas may prepare those later workstreams, but cannot implement their production behavior in P2-00.

### 4.4 Stop and request owner/reviewer direction

Stop before changing:

- an endpoint, error code, response/event/schema, environment variable, database contract, cookie, GitHub permission, sprite contract, bundle contract, provider fallback, trust model, public behavior, or v1 scope;
- the one-image/one-origin/no-external-database deployment topology;
- uv/pnpm as package managers;
- any acceptance threshold;
- a frozen P2-00 invariant or oracle.

Also stop if two implementation areas fail against the same frozen contract, or if a deterministic gate contradicts a claimed pass.

## 5. Changed-file manifest

The receiving Agent must keep this table exhaustive. Add rows before requesting review.

| Path | Owner | State at handoff | Purpose/evidence |
| --- | --- | --- | --- |
| `docs/SUBAGENT_EXECUTION_PLAYBOOK.md` | Prior Main | Existing governance change | Durable execution routing; validated references |
| `README.md` | Prior Main | Existing governance navigation change | Links the playbook |
| `docs/IMPLEMENTATION_PLAN.md` | Prior Main | Existing governance navigation change | Requires the playbook for delegation |
| `.agent-foreman/phase2-foundation/plan.json` | Prior Main | New, frozen, validated | Semantic P2-00 main-direct plan; all gates `not_run` |
| `.agent-foreman/phase2-foundation/plan.md` | Generated | New, rendered | Human rendering of plan.json; do not hand-edit |
| `docs/P2_FOUNDATION_HANDOFF.md` | Prior Main / Receiving Main | Live | This handoff, review ledger, and receiving-Main baseline record |
| `.agent-foreman/phase2-foundation/artifacts/baseline-sha256.json` | Receiving Main | New generated baseline | Enumerated 52-file SHA-256 baseline; cache/temp/venv paths excluded |
| `src/reponpc/config/environment.py` | Receiving Main | New | Typed documented-environment loader; bounded direct/file secret boundary and redacted issues |
| `src/reponpc/runtime/__init__.py`, `src/reponpc/runtime/database.py` | Receiving Main | New | Transactional, versioned mutable SQLite foundation under `REPONPC_DATA_DIR/runtime.sqlite` |
| `src/reponpc/observability/__init__.py`, `src/reponpc/observability/logging.py` | Receiving Main | New | Allowlisted, bounded structured safe-event API |
| `src/reponpc/main.py` | Receiving Main | Modified | Production runner now loads typed host/port settings and fails with a redacted startup error |
| `tests/contract/test_environment.py` | Receiving Main | New | Environment/secret boundary and startup wiring tests |
| `tests/integration/test_runtime_database.py` | Receiving Main | New | Runtime migration, rollback, concurrency, integrity, and raw-value rejection tests |
| `tests/security/test_safe_logging.py` | Receiving Main | New | Nested secret/privacy canary and logging-failure tests |
| `src/reponpc/api/public.py`, `src/reponpc/main.py` | Receiving Main | Modified | Runtime lifecycle/readiness wiring and same-origin static serving without changing Phase 1 response schemas |
| `package.json`, `pnpm-workspace.yaml`, `pnpm-lock.yaml`, `apps/web/` | Receiving Main | New | Pinned pnpm React/Vite workspace; semantic bilingual setup shell and locked frontend gate |
| `pyproject.toml`, `uv.lock` | Receiving Main | Modified | Repository-wide Ruff scope plus locked mypy and PyYAML-stub development dependencies |
| `Dockerfile`, `compose.yml`, `.dockerignore`, `.github/workflows/ci.yml` | Receiving Main | New | One non-root read-only app container, localhost-only Compose contract, and pinned least-privilege CI |
| `tests/contract/test_foundation_scope.py`, `tests/contract/test_ci_deployment.py`, `tests/integration/test_static_web.py`, `tests/smoke/test_container.py` | Receiving Main | New | Scope, deployment/CI, static-serving, and isolated real-container smoke oracles |
| `tests/integration/test_mvp_api.py`, `tests/contract/test_environment.py`, `tests/security/test_safe_logging.py` | Receiving Main | Modified | R1 lifecycle, secret-serialization/race, and direct POSIX-path leak regression probes |
| `tests/__init__.py`, `tests/mocks/__init__.py`, `tests/mocks/servers.py`, `tests/integration/test_mock_servers.py` | Receiving Main | New | In-process deterministic provider/GitHub mock boundary |
| `docs/OPERATIONS.md` | Receiving Main | Modified | Documents the Compose secret-directory mount and locked local image build command |
| `.agent-foreman/phase2-foundation/artifacts/gate-*.txt`, `gate-final-exact.txt`, `evidence-ledger.jsonl`, `integration-p2-foundation.json` | Receiving Main | New | Gate outputs, append-only deterministic evidence, and Main integration status |

P2-00 implementation is now present. Generated dependency directories, caches, temporary test paths, and frontend build output remain excluded from the changed-file manifest and build context.

## 6. Step 0 — Takeover, baseline, and plan check

### Objective

Prove the receiving Agent is starting from the recorded state before any implementation edit.

### Actions

1. Complete section 3 reading.
2. Inventory repository files without deleting caches or unrelated work.
3. Re-probe Python, uv, Node, pnpm, and Docker.
4. Validate `.agent-foreman/phase2-foundation/plan.json` with the Agent Foreman validator.
5. Re-render `plan.md`; do not hand-edit it.
6. Run the existing 56-test aggregate suite before changing production.
7. Run Ruff and `uv lock --check --offline`.
8. Create enumerated SHA-256 baselines for all existing production, tests, documents, examples, and frozen plan files. Exclude cache/temp/venv paths explicitly.
9. Update sections 15 and 16.

### Exact baseline commands

Use runtime paths available in the receiving environment; record substitutions. Every shell command and chain segment must be prefixed with `rtk`.

```text
rtk proxy C:/Python314/python.exe C:/Users/xu/.codex/skills/agent-foreman/scripts/validate_plan.py D:/RepoNPC/.agent-foreman/phase2-foundation/plan.json
rtk proxy C:/Python314/python.exe C:/Users/xu/.codex/skills/agent-foreman/scripts/render_plan.py D:/RepoNPC/.agent-foreman/phase2-foundation/plan.json --out D:/RepoNPC/.agent-foreman/phase2-foundation/plan.md
rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/handoff-baseline -p no:cacheprovider -q
rtk ruff check .
rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache lock --check --offline
```

### Exit

- plan valid/rendered;
- baseline tests/checks recorded exactly;
- file baseline artifact exists;
- any pre-existing failure is reported before implementation.

Do not request `R1` yet unless baseline contradicts this handoff.

## 7. Step 1 — Environment and secret-file boundary

### References

Technical Spec 4.1, 4.3, 15.3, 17; Security 2, 6, 7, 11; AC-001, AC-002, AC-035; `.env.example`; plan invariants `INV-SECRETS-BOUNDARY`, `INV-SCOPE-APPROVED`.

### Required implementation

- Add a typed runtime environment loader below `src/reponpc/config/`.
- Support only environment variables already defined by `.env.example` unless the owner approves a contract update.
- For GitHub/provider/IP-HMAC secret pairs, accept one direct value or one `_FILE` value; both present is a safe startup error.
- Treat empty values consistently and document/test the decision without echoing values.
- Secret files must be bounded regular files inside explicitly allowed secret roots; reject links, traversal/outside roots, unsafe mode where the OS exposes it, oversize data, invalid encoding, and empty data.
- Represent secret values with redacted repr/serialization.
- Provide safe typed field-level issues that omit rejected values and internal filesystem details.
- Wire settings into production startup only as far as needed for the existing host/port/data/log/static foundations. Do not expose settings through public status.

### Expected paths

- `src/reponpc/config/environment.py`;
- `tests/contract/test_environment.py`;
- minimal changes to `src/reponpc/main.py` only when the loader has focused tests.

If other paths are required, add them to section 5 with a reason before editing.

### Smallest falsifiers

- direct and `_FILE` are both set to distinct canaries;
- symlink or directory presented as secret file;
- file outside allowed root;
- group/world-readable secret on POSIX;
- oversized/empty/non-UTF-8 secret;
- secret canary appears in exception, repr, response, or log;
- private provider URL appears in public status.

### Focused gate

Run `GATE-ENV` from `plan.json`. Update the gate result only with exact exit code and artifact.

## 8. Step 2 — Runtime SQLite and transactional migrations

### References

Technical Spec 15.1 and 17; ADR-003; Security 2, 7, 9, 11; Operations 10–13; AC-024, AC-031, AC-035, AC-036; plan invariant `INV-RUNTIME-SEPARATE`.

### Required implementation

- Add a runtime database owner below `src/reponpc/runtime/`.
- Force mutable data to `REPONPC_DATA_DIR/runtime.sqlite`; never accept or mutate `index.sqlite` as runtime storage.
- Implement explicit migration versioning and transaction boundaries.
- Create the logical tables required by Technical Spec 15.1: sessions, rate buckets, daily usage, bundle state, and admin audit.
- Store hashes/pseudonyms only; table/column names must not invite raw token, CSRF, password, question, answer, or IP storage.
- Configure foreign keys, bounded busy timeout, integrity checks, and safe connection lifecycle.
- Make initialization idempotent and concurrent-start safe for the supported single application process.
- Provide an online backup/check foundation only if it can be implemented without expanding the public CLI contract; otherwise keep it as a later explicitly tracked operation.

### Expected paths

- `src/reponpc/runtime/__init__.py`;
- `src/reponpc/runtime/database.py`;
- optionally one explicit migration module below `src/reponpc/runtime/`;
- `tests/integration/test_runtime_database.py`.

### Smallest falsifiers

- migration failure after one DDL statement;
- second initialization;
- two startup connections;
- runtime path points at `index.sqlite`;
- raw IP/session/CSRF canaries attempted;
- reopened database has partial version/table state;
- runtime DB unavailable yet `/healthz` still distinguishes process liveness from readiness.

### Focused gate

Run `GATE-RUNTIME` from `plan.json` against a real temporary SQLite file.

## 9. Step 3 — Safe structured logging

### References

Technical Spec 10 and 15.3; NFR-002 and NFR-012; Security 2, 7, 11–12; AC-035; plan invariants `INV-LOGGING-SAFE`, `INV-SECRETS-BOUNDARY`.

### Required implementation

- Add an allowlisted structured-event API below `src/reponpc/observability/`.
- Support the safe fields named in Technical Spec 15.3.
- Exclude credentials, cookies, CSRF, raw IP, request/history/prompt/evidence/answer/upload bodies, private provider URLs, filesystem paths, and public stack traces.
- Bound strings and collection sizes.
- Normalize errors to safe categories; never serialize arbitrary exception `repr`/`str` directly.
- Ensure logging failure cannot replace the application result or leak the original value.
- Add recognizable nested canaries in tests.

### Expected paths

- `src/reponpc/observability/__init__.py`;
- `src/reponpc/observability/logging.py`;
- `tests/security/test_safe_logging.py`.

### Smallest falsifiers

Nested mappings/lists containing token, password, cookie, prompt, answer, raw IP, Windows/Unix path, and private URL canaries; malicious exception text; oversized rank/value lists.

### Focused gate

Run `GATE-LOGGING`.

### Review checkpoint R1

After Steps 1–3 are `IMPLEMENTED`, update sections 5, 15–17 and request `R1`. Do not wire later provider/GitHub production behavior. The reviewer checks secret boundaries, migrations, logs, Phase 1 regression, and scope.

## 10. Step 4 — Deterministic GitHub/provider mock servers

### References

Implementation Plan 6 and 12; Technical Spec 11.3, 13, 14; ADR-005, ADR-006, ADR-009; Security 6, 7, 10.

### Required implementation

- Build in-process/mock-only servers under `tests/mocks/`; do not add a production service.
- Cover provider health, capability variations, normalized generation success/failure, usage nullability, timeouts, malformed output, and context overflow.
- Cover GitHub contents read/write, expected SHA conflict, exact repository/branch/path/workflow allowlists, Release asset publication state, and workflow dispatch acknowledgement.
- Track mutation counts so preview/validation tests can prove zero external side effects later.
- Deny unknown operations and paths.
- Use unmistakably fake credentials/hosts and no live network.

### Expected paths

- `tests/__init__.py` if import packaging requires it;
- `tests/mocks/__init__.py`;
- `tests/mocks/servers.py`;
- `tests/integration/test_mock_servers.py`.

### Smallest falsifiers

Unknown mutation with plausible wording; stale expected SHA; unconfigured repository/path/workflow; unsupported capability parameter; private URL/token in response; any outbound connection.

### Focused gate

Run `GATE-MOCKS`.

## 11. Step 5 — Locked TypeScript/pnpm/Vite workspace

### References

Technical Spec 3 and 16; ADR-011 and ADR-012; NFR-008, NFR-009, NFR-013; AC-019, AC-023, AC-032, AC-034, AC-036.

### Required implementation

- Create root `package.json`, `pnpm-workspace.yaml`, and `pnpm-lock.yaml` using pnpm only.
- Create `apps/web/` with Vite, TypeScript, React, Vitest, formatting, lint, type-check, unit-test, and production-build scripts.
- Pin the package-manager version and use a frozen lockfile in CI.
- Build only a semantic bilingual setup shell at this stage: product identity, `setup_required`/unavailable explanation, and accessible language control.
- Do not implement chat, visitor product journeys, admin, canvas-only semantics, character assets, or public API changes.
- Preserve keyboard operation, visible focus, semantic DOM, and reduced-motion-safe CSS foundations.
- Do not place secrets or provider URLs in Vite environment/client code.

### Expected paths

- `package.json`;
- `pnpm-workspace.yaml`;
- generated `pnpm-lock.yaml`;
- `apps/web/package.json`;
- Vite/TypeScript/ESLint/format/test configs below `apps/web/`;
- `apps/web/index.html`;
- minimal `apps/web/src/` shell, styles, and tests.

All manifest changes must be made with `apply_patch` or package-manager commands; the lockfile is generated mechanically and must not be hand-edited.

### Smallest falsifiers

Missing locale key; UI available only through animation/canvas; keyboard-inoperable locale control; browser bundle contains a secret/private URL canary; a second package manager; install succeeds only without lock; type/lint/test/build scripts diverge from CI.

### Focused gate

Run `GATE-WEB`. Record install and lockfile commands separately.

## 12. Step 6 — Same-origin FastAPI serving

### References

Technical Spec 9 and 16; ADR-011; Security 8; AC-019, AC-032, AC-034, AC-036; plan invariants `INV-WEB-LOCKED-SAME-ORIGIN`, `INV-PHASE1-REGRESSION`.

### Required implementation

- Serve built `apps/web/dist` through the production FastAPI application under the same origin.
- Register API/health routes before the root static mount/fallback.
- Preserve `/healthz`, `/readyz`, `/api/public/status`, and `/api/public/profile` behavior.
- Keep broad CORS disabled.
- Use headers that allow only the bundled same-origin JS/CSS/assets required by the shell while maintaining `nosniff`, `frame-ancestors 'none'`, referrer, and permissions policy.
- Missing build assets must not prevent API health/setup tests and must not expose a directory listing/path.
- Static path handling must not traverse outside the build directory.

### Expected paths

- `src/reponpc/main.py`;
- `tests/integration/test_static_web.py`;
- existing `tests/integration/test_mvp_api.py` only when an assertion must reflect the approved same-origin header contract.

### Smallest falsifiers

`/api/...` captured by SPA fallback; missing dist crashes startup; traversal/directory listing; CSP blocks required local bundle or allows remote script; broad CORS; setup status changed; static request exposes a filesystem path.

### Focused gate

Build the web app, then run `GATE-API`.

## 13. Step 7 — Docker/Compose and CI

### References

Technical Spec 3, 15, 19; NFR-010; ADR-001, ADR-003, ADR-011, ADR-012; Security 4, 6, 8, 9, 12–13; Operations 1, 2, 7, 8, 11, 12; AC-036, AC-037.

### Required Docker/Compose implementation

- Multi-stage locked frontend/Python build.
- One final application image; no public indexer service.
- Non-root runtime; only data/temp paths writable.
- Application source/build assets read-only at runtime where supported.
- Persistent `/var/lib/reponpc` volume.
- Healthcheck against `/healthz`.
- No PostgreSQL, Redis, vector service, or published Ollama/private provider port.
- Explicit host port and safe environment/secrets mounting contract consistent with `.env.example`.
- `.dockerignore` excludes caches, venvs, temporary artifacts, and real `.env`/secret material without excluding required source/lock/build inputs.

### Required CI implementation

- Minimal `contents: read` permission.
- Pinned trusted action revisions.
- Supported Python/Node/pnpm/uv versions.
- Locked uv and pnpm installation.
- Python format/lint/type/test/build gates.
- TypeScript format/lint/type/test/production build gates.
- Docker build and Compose configuration gates.
- No live credentials, providers, GitHub mutations, or broad workflow permissions.

### Expected paths

- `Dockerfile`;
- `compose.yml`;
- `.dockerignore`;
- `.github/workflows/ci.yml`;
- `tests/contract/test_ci_deployment.py`;
- `tests/smoke/test_container.py`.

### Smallest falsifiers

Root image user; writable source mount; missing persistent volume/healthcheck; extra database/provider service; `latest`-only contract; secrets copied into image/build context; workflow write permission; unpinned action; unlocked install; CI omits a local required gate.

### Focused gates

Run `GATE-CI`, `GATE-DEPLOYMENT`, and `GATE-CONTAINER`.

`GATE-CONTAINER` must use an isolated Compose project/container/volume name and clean only that exact test scope. It must never delete an operator/user volume. If Docker is unavailable, record the exact command failure as `NOT_RUN`; static YAML tests do not substitute for the real image/start/health/restart oracle.

### Review checkpoint R2

After Steps 4–7 are `IMPLEMENTED`, update sections 5, 15–17 and request `R2`. The reviewer checks package boundaries, same-origin serving, Docker/CI security, locked builds, and all R1 repairs.

## 14. Step 8 — Aggregate verification and closure

### Required checks

Run every gate in `.agent-foreman/phase2-foundation/plan.json`:

- `GATE-SCOPE`;
- `GATE-ENV`;
- `GATE-RUNTIME`;
- `GATE-LOGGING`;
- `GATE-MOCKS`;
- `GATE-WEB`;
- `GATE-API`;
- `GATE-DEPLOYMENT`;
- `GATE-CI`;
- `GATE-TYPE`;
- `GATE-PY-LOCK`;
- `GATE-BUILD`;
- `GATE-CONTAINER`;
- `GATE-PYTHON`;
- `GATE-RUFF`;
- `GATE-ALL`.

Also run the frontend formatter check if it is not included by `web:check`, and inspect sdist/wheel/image contents for caches, secret files, governance artifacts, and unintended frontend source maps/secrets.

### Required artifacts

Store raw or faithful command output under:

```text
.agent-foreman/phase2-foundation/artifacts/
```

Append deterministic evidence to:

```text
.agent-foreman/phase2-foundation/evidence-ledger.jsonl
```

Use the Agent Foreman append validation command; never edit an earlier JSONL line.

Create a Main integration record under:

```text
.agent-foreman/phase2-foundation/integration-p2-foundation.json
```

Keep deterministic results, reviewer recommendation, unavailable gates, and limitations separate.

### Completion boundary

P2-00 and Implementation Plan Milestone 1 may be reported complete only when:

- all blocking gates pass, including real Docker/container smoke;
- Phase 1 aggregate tests still pass;
- Python/frontend locked builds pass;
- documents/examples match implementation;
- no secret/personal data is introduced;
- `R3` reviewer recommendation is `pass` and no deterministic evidence contradicts it.

If Docker or another external oracle remains unavailable, report the implementation as `IMPLEMENTED`, P2-00 as `BLOCKED`/not verified, and Milestone 1 as incomplete. Do not start P2-01 delegation.

### Review checkpoint R3

Update sections 5, 15–17 and request final `R3` review. Include every command, exit code, artifact, limitation, and owner decision.

## 15. Execution tracker

The receiving Agent updates this table in place.

| ID | Step | Status | Implementer | Last update | Focused evidence | Reviewer state |
| --- | --- | --- | --- | --- | --- | --- |
| H-00 | Prior Phase 1 verified baseline | `COMPLETE` | Prior Main | 2026-08-10 | `.agent-foreman/mvp/integration-mvp-final.json` | Prior evaluator repairs passed; delta limitation retained |
| H-01 | P2-00 plan create/validate/render | `COMPLETE` | Prior Main | 2026-08-10 | `.agent-foreman/phase2-foundation/plan.json`, `plan.md` | `accepted` by receiving Main on 2026-08-10 after mandatory-source review, validation, and deterministic re-render |
| S-00 | Takeover/baseline | `COMPLETE` | Receiving Main | 2026-08-10 | Frozen plan validation/render, prior 56-test baseline, SHA-256 baseline | RISK-006 baseline observation retained |
| S-01 | Environment/secret loader | `IMPLEMENTED` | Receiving Main | 2026-08-10 | `GATE-ENV`: 9 passed, 2 Windows-only POSIX probes skipped | R2 repair verification passed, including custom limit above 64 KiB |
| S-02 | Runtime SQLite/migrations | `IMPLEMENTED` | Receiving Main | 2026-08-10 | `GATE-RUNTIME`: 5 passed; app lifecycle degradation probe passes | R2 review passed |
| S-03 | Safe logging | `IMPLEMENTED` | Receiving Main | 2026-08-10 | `GATE-LOGGING`: 4 passed, including `/tmp` redaction | R2 repair verification passed |
| S-04 | Mock servers | `IMPLEMENTED` | Receiving Main | 2026-08-10 | `GATE-MOCKS`: 8 passed | R2 review passed |
| S-05 | TypeScript/pnpm/Vite workspace | `IMPLEMENTED` | Receiving Main | 2026-08-10 | `GATE-WEB`: format/lint/type/Vitest/build pass | R2 review passed |
| S-06 | Same-origin FastAPI serving | `IMPLEMENTED` | Receiving Main | 2026-08-10 | `GATE-API`: 11 passed, including bundle canary | R2 review passed |
| S-07 | Docker/Compose and CI | `COMPLETE` | Receiving Main | 2026-08-10 | Compose config and real persistence smoke pass; `GATE-CI`: 2 passed | R3 persistence review passed |
| S-08 | Aggregate verification/evidence | `COMPLETE` | Receiving Main | 2026-08-10 | Docker-aware `GATE-ALL`: 90 passed, 2 Windows-only skips, 1 warning; exact-command evidence ledger validates | R3 persistence review passed; P2-00 and Milestone 1 carry-forward closure verified |

## 16. Evidence log

Append rows; never replace a failed or not-run observation.

| Time | Actor | Step/gate | Command/environment | Exit/result | Artifact | Observation |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-08-10 | Prior Main | Plan validation | Agent Foreman `validate_plan.py` | `0 / valid` | `.agent-foreman/phase2-foundation/plan.json` | Minimal/main-direct plan structurally valid; all implementation gates remain `not_run` |
| 2026-08-10 | Prior Main | Plan rendering | Agent Foreman `render_plan.py` | `0` | `.agent-foreman/phase2-foundation/plan.md` | Rendered from validated JSON |
| 2026-08-10 | Prior Main | Tool probe | Python 3.14.7, uv 0.12.3, Node 24.14.0, pnpm 11.16.0 | observed | This handoff section 2.4 | Docker executable not found; receiving Agent must re-probe |
| 2026-08-10 | Receiving Main | Mandatory source review | Section 3 source list plus Agent Foreman routing | complete | This handoff; approved contracts and prior Phase 1 evidence | P2-00 remains Main-owned: the remaining foundation work consists of shared security, lifecycle, persistence, serving, deployment, and CI seams; no eligible leaf is currently frozen for delegation |
| 2026-08-10 | Receiving Main | Tool probe | Python 3.14.7; uv 0.12.3; Node v26.7.0; pnpm 11.16.0; `docker.exe version` | Docker unavailable | This handoff section 2.4 | Docker executable remains unavailable; real container gate cannot yet run |
| 2026-08-10 | Receiving Main | Plan validation | `rtk proxy C:/Python314/python.exe C:/Users/xu/.codex/skills/agent-foreman/scripts/validate_plan.py D:/RepoNPC/.agent-foreman/phase2-foundation/plan.json` | `0 / valid` | `.agent-foreman/phase2-foundation/plan.json` | Existing frozen minimal Main-direct campaign remains structurally valid |
| 2026-08-10 | Receiving Main | Plan rendering | `rtk proxy C:/Python314/python.exe C:/Users/xu/.codex/skills/agent-foreman/scripts/render_plan.py ... --out .../plan.md` | `0` | `.agent-foreman/phase2-foundation/plan.md` | Re-rendered mechanically from the validated JSON |
| 2026-08-10 | Receiving Main | Phase 1 baseline | `rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/handoff-baseline -p no:cacheprovider -q` | `0 / 56 passed, 1 warning` | Terminal record | Existing FastAPI/TestClient deprecation warning is non-blocking |
| 2026-08-10 | Receiving Main | Lock baseline | `rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache lock --check --offline` | `0` | Terminal record | `pyproject.toml` and `uv.lock` are synchronized offline |
| 2026-08-10 | Receiving Main | Source/test lint baseline | `rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python ruff check src tests` | `0 / All checks passed` | Terminal record | The plan's unscoped `rtk ruff check .` cannot run in this host and its proxy fallback includes cache/governance paths; limitation recorded separately |
| 2026-08-10 | Receiving Main | SHA-256 baseline | Enumerated production, test, document, example, and frozen-plan paths | `0 / 52 entries` | `.agent-foreman/phase2-foundation/artifacts/baseline-sha256.json` | Manifest SHA-256 `8110EB7DCC62CFB40D5B9F30F7CAF37E2979BDE8E72C70CE73C8E8C3AC62BB97`; caches/temp/venvs excluded |
| 2026-08-10 | Receiving Main | GATE-ENV | `rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-env -p no:cacheprovider tests/contract/test_environment.py -q` | `0 / 8 passed, 1 skipped` | Terminal record | Direct/file collision, file-type/root/size/encoding/empty checks, redaction, unsupported settings, and runner wiring pass; POSIX mode check is unavailable on Windows |
| 2026-08-10 | Receiving Main | GATE-RUNTIME | `rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-runtime -p no:cacheprovider tests/integration/test_runtime_database.py -q` | `0 / 5 passed` | Terminal record | Idempotent/concurrent initialization, transactional rollback, integrity failure, runtime/index separation, and raw session/CSRF/IP rejection pass |
| 2026-08-10 | Receiving Main | GATE-LOGGING | `rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-logging -p no:cacheprovider tests/security/test_safe_logging.py -q` | `0 / 3 passed` | Terminal record | Nested canaries, raw IPs, private URLs, Windows/Unix paths, arbitrary exception text, overlong ranks, and logging-handler failure do not leak or replace application flow |
| 2026-08-10 | Receiving Main | R1 aggregate regression | `rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync --python C:/Python314/python.exe --no-managed-python pytest --basetemp D:/RepoNPC/.pytest-tmp/p2-r1-aggregate -p no:cacheprovider -q` | `0 / 72 passed, 1 skipped, 1 warning` | Terminal record | Phase 1 regressions remain passing; the Starlette/TestClient deprecation warning remains non-blocking |
| 2026-08-10 | R1 reviewer / Receiving Main | R1 review and repair | Read-only review found direct POSIX-path log emission, dataclass serialization of a secret, pathname secret-file race, and unreferenced runtime initialization | Repaired; focused repair suite `0 / 25 passed, 2 skipped` | Reviewer message; source/test paths in section 5 | Added descriptor traversal, opaque secret holder, safe path rejection, and production lifecycle readiness degradation |
| 2026-08-10 | Receiving Main | Locked frontend install and web gate | pnpm 11.16.0 frozen install; `pnpm run web:check` | `0 / format, lint, type, 2 Vitest tests, build` | `artifacts/gate-web.txt` | pnpm cache lies outside sandbox; final gate ran with scoped approval; lockfile is mechanically generated |
| 2026-08-10 | Receiving Main | P2 focused gates | `GATE-SCOPE`, `ENV`, `RUNTIME`, `LOGGING`, `MOCKS`, `API`, `CI`, `TYPE`, `PY-LOCK`, `BUILD` | all applicable commands `0` | `artifacts/gate-*.txt`; append-only evidence ledger | API 10 passed; CI contract 2 passed; mypy has no issues in 13 source files; sdist/wheel contents inspected |
| 2026-08-10 | Receiving Main | Aggregate gates | `pytest -q`; `ruff check .`; `ruff format --check .` | `0 / 87 passed, 3 skipped, 1 warning`; lint/format pass | `artifacts/gate-python.txt`, `gate-ruff.txt`, `gate-all.txt` | Skips are Windows-only POSIX probes and the unavailable Docker smoke; existing TestClient warning is non-blocking |
| 2026-08-10 | Receiving Main | Bundle-secret canary and rebuilt web gate | `test_static_web.py` + `test_mvp_api.py`; `pnpm run web:check`; ledger validation | `0 / 11 passed, 1 pre-existing warning`; `0 / format, lint, type, 2 frontend tests, build`; ledger valid | `artifacts/gate-api-bundle-canary.txt`, `gate-web-bundle-canary.txt`, `evidence-ledger.jsonl` | Built bundle excludes server-secret names and private-provider canaries; revised evidence ledger validates against the frozen plan |
| 2026-08-10 | Receiving Main / R2 reviewer | R2 repair and exact-evidence rerun | all frozen local gate commands; ledger validation; fresh reviewer probes | all available local gates `0`; `GATE-ALL` 89 passed, 3 skipped, 1 warning; reviewer repair check passed | `artifacts/gate-final-exact.txt`, `evidence-ledger.jsonl` | Restored exact command evidence without rewriting history; custom secret limit and `/tmp` logging redaction are covered; Docker remains the sole external blocker |
| 2026-08-10 | Receiving Main | Docker activation and persistence reruns | installed Docker Desktop Compose config; isolated UUID smoke; Docker-aware aggregate; lint | Compose `0`; persistence smoke `1 passed`; Python/All `90 passed, 2 skipped, 1 warning`; lint/format `0` | `artifacts/gate-docker-final.txt`, `gate-docker-persistence.txt`, `evidence-ledger.jsonl` | The initial restart timing observation and the initial missing-volume-canary R3 finding are preserved; the final smoke writes and reads a runtime-volume marker across restart |
| 2026-08-10 | Fresh R3 evaluator | Final persistence review | read-only Compose/volume/marker/evidence inspection | `pass` | `evaluation/r3-persistence-evaluation.json` | UUID marker is written to the mounted runtime volume and read after restart; evidence hashes and Docker-aware aggregates match |
| 2026-08-10 | Receiving Main | Docker gates | `docker.exe compose -f compose.yml config --quiet`; isolated `tests/smoke/test_container.py` | Docker executable missing; smoke `1 skipped` | `artifacts/gate-deployment.txt`, `gate-container.txt` | `NOT_RUN`; this is the sole P2-00/Milestone 1 verification blocker |

## 17. Review request — implementer fills this

Replace the placeholders for each request while preserving earlier requests below it.

```text
Review checkpoint: R1 | R2 | R3
Requested at:
Implementer:
Claimed status:
Steps included:
Exact changed paths:
Focused gates (command -> exit -> artifact):
Aggregate gates (command -> exit -> artifact):
Security/privacy counterexamples exercised:
Unavailable/not-run checks and exact reason:
Known limitations:
Owner decisions requested:
Questions for reviewer:
```

Current request:

```text
Review checkpoint: R1
Requested at: 2026-08-10
Implementer: Receiving Main
Claimed status: S-01 through S-03 IMPLEMENTED; P2-00 remains in progress
Steps included: Environment/secret boundary, runtime SQLite migration foundation, safe structured logging
Exact changed paths: src/reponpc/config/environment.py; src/reponpc/runtime/__init__.py; src/reponpc/runtime/database.py; src/reponpc/observability/__init__.py; src/reponpc/observability/logging.py; src/reponpc/main.py; tests/contract/test_environment.py; tests/integration/test_runtime_database.py; tests/security/test_safe_logging.py; this handoff ledger
Focused gates (command -> exit -> artifact): GATE-ENV -> 0 -> terminal record in section 16; GATE-RUNTIME -> 0 -> terminal record in section 16; GATE-LOGGING -> 0 -> terminal record in section 16
Aggregate gates (command -> exit -> artifact): full Python regression -> 0 (72 passed, 1 skipped, 1 warning) -> terminal record in section 16; source/test Ruff -> 0 -> terminal record in section 16
Security/privacy counterexamples exercised: direct/file collision; unsafe/outside/empty/oversize/non-UTF-8/symlink secret file; redacted secret repr/error; runtime/index separation; partial DDL rollback; concurrent initialization; raw session/CSRF/IP rejection; nested token/password/cookie/CSRF/prompt/answer/IP/path/private-URL canaries; arbitrary exception and failing handler
Unavailable/not-run checks and exact reason: POSIX secret-file mode probe skipped on Windows; Docker executable unavailable; unscoped `rtk ruff check .` cannot run in host configuration and the proxy fallback scans cache/governance paths (RISK-006)
Known limitations: No provider/GitHub production behavior wired; runtime database is foundation-only; GATE-RUFF has no approved repository-wide scope yet
Owner decisions requested: None
Questions for reviewer: Do the secret-file roots/value handling, SQLite migration/column constraints, and safe-event allowlist satisfy the frozen P2-00 contracts without altering Phase 1 public behavior?
```

## 18. Reviewer log — reviewer only

Next request:

```text
Review checkpoint: R2
Requested at: 2026-08-10
Implementer: Receiving Main
Claimed status: S-01 through S-07 IMPLEMENTED; S-08 BLOCKED only by unavailable real Docker gates
Steps included: R1 repairs; mocks; pnpm/Vite workspace; same-origin static serving; Docker/Compose/CI contract; locked Python type/build/lint checks
Exact changed paths: every Receiving Main path in section 5, with emphasis on src/reponpc/config/environment.py; src/reponpc/observability/logging.py; src/reponpc/main.py; src/reponpc/api/public.py; package.json; pnpm-workspace.yaml; pnpm-lock.yaml; apps/web/; Dockerfile; compose.yml; .github/workflows/ci.yml; tests/contract/test_ci_deployment.py; tests/integration/test_static_web.py; tests/smoke/test_container.py
Focused gates (command -> exit -> artifact): GATE-SCOPE/ENV/RUNTIME/LOGGING/MOCKS/API/CI/TYPE/PY-LOCK/BUILD -> 0 -> artifacts/gate-*.txt; GATE-WEB -> 0 -> artifacts/gate-web.txt
Aggregate gates (command -> exit -> artifact): GATE-PYTHON -> 0 (87 passed, 3 skipped, 1 warning) -> artifacts/gate-python.txt; GATE-RUFF -> 0 -> artifacts/gate-ruff.txt; GATE-ALL -> 0 (87 passed, 3 skipped, 1 warning) -> artifacts/gate-all.txt
Security/privacy counterexamples exercised: R1 direct POSIX path, dataclass serialization, symlink replacement, runtime migration failure; API/static route precedence, missing dist, traversal, CSP/CORS; private mock mutation/capability denials; Docker non-root/read-only/local-port/static CI assertions
Unavailable/not-run checks and exact reason: docker.exe is absent. GATE-DEPLOYMENT exited 1 before Compose invocation; GATE-CONTAINER skipped by an explicit docker-executable guard. Neither is reported as passed.
Known limitations: Real Docker build/config/smoke and R3 review are outstanding. The three original Phase 1 worker delta guards remain failed/non-attributable.
Owner decisions requested: None
Questions for reviewer: Do the repairs, same-origin CSP/static boundary, lock/build/CI contract, and Docker posture preserve the frozen scope and avoid a security or lifecycle regression before a Docker-capable R3 run?
```

```text
Review checkpoint: R3
Requested at: 2026-08-10
Implementer: Receiving Main
Claimed status: All P2-00 deterministic gates pass; S-08 is REVIEW_REQUESTED pending fresh final review
Steps included: Docker activation; Compose configuration; real isolated-container smoke; restart readiness repair; runtime-volume persistence canary repair; Docker-aware aggregate reruns
Exact changed paths: tests/smoke/test_container.py; docs/P2_FOUNDATION_HANDOFF.md; .agent-foreman/phase2-foundation/artifacts/gate-docker-final.txt; artifacts/gate-docker-persistence.txt; evidence-ledger.jsonl; integration-p2-foundation.json
Focused gates (command -> exit -> artifact): installed Docker Desktop Compose config -> 0 -> artifacts/gate-docker-final.txt; persistence GATE-CONTAINER -> 0 / 1 passed -> artifacts/gate-docker-persistence.txt
Aggregate gates (command -> exit -> artifact): Docker-aware GATE-PYTHON -> 0 / 90 passed, 2 Windows-only skips, 1 warning -> artifacts/gate-docker-persistence.txt; Docker-aware GATE-ALL -> 0 / same -> artifacts/gate-docker-persistence.txt; GATE-RUFF -> 0 -> same artifact
Security/lifecycle counterexamples exercised: real container restart timing; Unicode Docker-output decoding; a new volume canary must be readable after restart; UUID project isolation and project-local volume cleanup
Unavailable/not-run checks and exact reason: None for P2-00 blocking gates. Docker CLI is installed but not in PATH; the test process uses its discovered installation path only.
Known limitations: Docker evidence uses Docker Desktop desktop-linux, not a documented clean Linux operator host. Two POSIX secret-file probes remain Windows-only skips. Original Phase 1 delta guards remain failed/non-attributable.
Owner decisions requested: None
Questions for reviewer: Does the final smoke now prove persistent runtime-volume data through restart, with bounded readiness and project-scoped cleanup, and do the final integration/evidence states accurately permit P2-00 verification?
```

The reviewer appends one record per request and does not erase earlier findings.

```text
Checkpoint:
Reviewed at:
Scope/file manifest result:
Deterministic gate result:
Findings (priority, file:symbol, actual, expected, evidence, one next action):
Recommendation: pass | revise | blocked
Residual risk:
```

```text
Checkpoint: R1
Reviewed at: 2026-08-10
Scope/file manifest result: Seven requested files were declared; full-delta attribution remains unavailable because this is not a Git worktree.
Deterministic gate result: Reviewer focused suite 16 passed, 1 skipped; then-current aggregate 80 passed, 1 skipped.
Findings: P1 src/reponpc/observability/logging.py:_safe_text emitted a direct POSIX path; P1 src/reponpc/config/environment.py:SecretValue leaked through dataclasses.asdict; P1 src/reponpc/config/environment.py:_read_secret_file had a pathname resolve/stat/read race; P1 src/reponpc/main.py:run never initialized RuntimeDatabase or degraded readiness on failure. Main repaired all four and added direct regression probes; post-repair focused suite passed 25, with two Windows-only POSIX skips.
Recommendation: revise
Residual risk: Fresh aggregate evidence was required after repair and has been recorded; final Docker gates remain unavailable.
```

```text
Checkpoint: R2
Reviewed at: 2026-08-10
Scope/file manifest result: Declared R2 paths and prior R1 repairs were inspected; full-delta attribution remains unavailable because this is not a Git worktree.
Deterministic gate result: R2 focused suite 22 passed, 2 Windows-only skips; frozen plan and evidence ledger validated.
Findings: P1 .agent-foreman/phase2-foundation/evidence-ledger.jsonl and artifacts/gate-*.txt used abbreviated commands; P2 src/reponpc/config/environment.py:_read_open_secret_file capped reads at the default limit rather than the supplied maximum; P2 src/reponpc/observability/logging.py:_POSIX_PATH_RE did not redact a single-component absolute path such as /tmp.
Recommendation: revise
Residual risk: Docker is unavailable, so Compose parsing and real isolated-container smoke remain external gates not run.
```

```text
Checkpoint: R2 repair verification
Reviewed at: 2026-08-10
Scope/file manifest result: Main's three bounded R2 repairs and their tests/evidence were inspected read-only.
Deterministic gate result: New focused reviewer check 13 passed, 2 Windows-only skips; latest aggregate evidence 89 passed, 3 skipped, 1 pre-existing warning; plan and ledger validation passed.
Findings: None. Custom max_secret_bytes preserves the complete above-default secret value; /tmp is redacted in an allowlisted log field; EVID-P2-019 through EVID-P2-034 and artifacts/gate-final-exact.txt contain exact commands and faithful results.
Recommendation: pass
Residual risk: docker.exe remains unavailable; GATE-DEPLOYMENT and the real GATE-CONTAINER oracle must run in a Docker-capable environment before R3 and completion.
```

```text
Checkpoint: R3 (initial Docker review)
Reviewed at: 2026-08-10
Scope/file manifest result: Dockerfile/Compose stayed within the one non-root, read-only application-container scope. UUID project isolation and finally cleanup were present.
Deterministic gate result: Fresh Compose validation through the installed Docker Desktop CLI passed. EVID-P2-038 through EVID-P2-043 matched artifacts/gate-docker-final.txt.
Findings: P1 tests/smoke/test_container.py:test_compose_container_health_and_runtime_volume_survive_restart proved only health/status around restart, not runtime-volume persistence; health and setup_required can pass while runtime storage is unavailable. P1 integration-p2-foundation.json still recorded Docker as unavailable and status blocked.
Recommendation: revise
Residual risk: Docker Desktop desktop-linux is not the documented clean Linux operator host; two POSIX secret-file probes remain Windows-only skips.
```

```text
Checkpoint: R3 (persistence repair verification)
Reviewed at: 2026-08-10
Scope/file manifest result: Main's bounded smoke-test and integration-record repairs were inspected read-only.
Deterministic gate result: Fresh Compose validation passed; EVID-P2-044 through EVID-P2-047 hashes matched artifacts/gate-docker-persistence.txt; persistence smoke passed; Docker-aware GATE-PYTHON and GATE-ALL each reported 90 passed, 2 Windows-only skips, and 1 pre-existing warning.
Findings: None. The smoke writes a uuid4 marker to the mounted /var/lib/reponpc, restarts app, waits for health, and reads the exact marker back. It is not a /tmp or application-layer marker, and cleanup remains project-scoped.
Recommendation: pass
Residual risk: Docker evidence is Docker Desktop desktop-linux rather than a documented clean x86_64 Linux operator-host run; two POSIX secret-file probes and the original Phase 1 delta-attribution limitation remain platform/history constraints.
```

## 19. Blockers, risks, and decisions

| ID | State | Evidence | Required next action |
| --- | --- | --- | --- |
| RISK-001 | Open | Repository has no Git metadata | Receiving Agent creates enumerated SHA-256 manifests and reports attribution limits honestly |
| RISK-002 | Open | Original Phase 1 worker delta guards failed | Preserve the limitation; never rewrite it as passed |
| RISK-003 | Resolved | Installed Docker Desktop CLI was located outside PATH; Compose config and a real isolated persistence smoke passed | Preserve the recorded CLI-path substitution; run the documented clean-host gate again during Phase 5 |
| RISK-004 | Resolved | `pnpm-lock.yaml` is mechanically generated; frozen install and web gate pass | Preserve pnpm 11.16.0 and `allowBuilds.esbuild`; rerun frozen install in CI |
| RISK-005 | Resolved | P2-00 retained a single Main for security/persistence/lifecycle/deployment seams; R3 persistence review passed | Begin P2-01 only under a fresh Phase 2 campaign plan |
| RISK-006 | Mitigated | The original `rtk ruff check .` host failure is retained; `pyproject.toml` now excludes cache/temp/governance/generated paths and `rtk proxy uv ... ruff check .` passes | Keep the exact host limitation visible; CI uses the scoped equivalent command |

No owner contract decision is currently known to be required. Any new decision must include evidence, viable options, recommendation, and impact before implementation continues.

## 20. Handoff acceptance

The receiving Agent accepts this handoff by updating:

- `H-01` reviewer state to `accepted` or a precise contradiction;
- `S-00` to `IN_PROGRESS`;
- section 16 with environment and baseline commands;
- section 19 with any newly discovered blocker.

After that update, implementation may begin at Step 1. The receiving Agent should cite this file when requesting review so the reviewer can inspect the repository and append section 18 findings without relying on chat history.

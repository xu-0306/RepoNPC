# RepoNPC Subagent Execution Playbook

| Field | Value |
| --- | --- |
| Status | Active execution-routing guide |
| Applies to | Remaining RepoNPC v1 work after Delivery Phase 1 |
| Last updated | 2026-08-10 |
| Authority | Non-normative; it routes work to the approved specification |

## 1. Purpose and boundary

This playbook defines how Main/Root turns the approved RepoNPC specification into bounded work that a subagent can execute without inventing product behavior. It records:

- what must happen before, during, and after every delegation;
- which document sections govern each remaining work package;
- which seams always remain Main-owned;
- which leaf packages may be delegated;
- the required counterexamples, gates, evidence, handoffs, and escalation points.

This document does **not** approve a contract, replace a requirement, reduce v1 scope, or authorize delegation by itself. An actual delegation still requires current user/host authorization and a fresh full-profile campaign under `.agent-foreman/<campaign>/`.

When this playbook differs from a normative source, the normative source wins. Main must repair this playbook before dispatching an affected package.

## 2. Authority and required reading

### 2.1 Source-of-truth order

Use the precedence in `PROJECT_CONTEXT.md` section 10:

1. explicit recorded owner decisions, including the approved Technical Specification and approved delivery sequencing;
2. `TECHNICAL_SPEC.md` and FR/NFR identifiers;
3. `ACCEPTANCE_CRITERIA.md` and AC identifiers;
4. accepted ADRs in `DECISIONS.md`;
5. `SECURITY.md`, `OPERATIONS.md`, and `SPRITE_FORMAT.md` in their domains;
6. `IMPLEMENTATION_PLAN.md`;
7. this playbook as execution routing;
8. per-campaign `plan.json` as the frozen dispatch plan for one bounded campaign;
9. README, examples, worker summaries, and model opinions.

Deterministic gate evidence outranks a worker or evaluator recommendation. A lower-precedence artifact cannot turn a failing higher-precedence contract into a pass.

### 2.2 Read-before-planning set

Main must read the following completely before creating a campaign plan:

1. `docs/PROJECT_CONTEXT.md`;
2. `docs/OWNER_REVIEW.md`;
3. `docs/TECHNICAL_SPEC.md`;
4. `docs/ACCEPTANCE_CRITERIA.md`;
5. `docs/DECISIONS.md`;
6. `docs/SECURITY.md`;
7. `docs/IMPLEMENTATION_PLAN.md`;
8. `docs/DELIVERY_PHASES.md`;
9. `docs/OPERATIONS.md` for deployment, providers, GitHub automation, runtime state, or release work;
10. `docs/SPRITE_FORMAT.md` for character, assets, card, upload, or animation work;
11. `README.md`;
12. `reponpc.example.yml` and `.env.example` for configuration or deployment work;
13. root `AGENTS.md`;
14. this playbook.

A dispatch may provide a smaller `read_first` list only after Main has completed the full set. The worker reads every dispatch-listed section and file before editing.

### 2.3 Specification gate

Technical Specification 0.1.0 is approved as of 2026-08-10, so implementation is authorized. If its status returns to `Draft`, or an owner decision reopens an affected contract, Main must block the affected campaign before production edits.

## 3. Current baseline and honest completion state

### 3.1 Verified Delivery Phase 1 slice

The `.agent-foreman/mvp/` campaign verifies the bounded Delivery Phase 1 slice:

- strict public configuration models;
- stable evidence records and evidence IDs;
- deterministic RRF;
- bounded fallback line chunking;
- `zh-TW`/`en` catalog parity;
- FastAPI setup, health, readiness, status, and unavailable-profile behavior;
- 56 passing tests, Ruff lint/format, offline lock validation, and inspected sdist/wheel;
- five evaluator probes passing after one Main repair round.

Canonical evidence is in:

- `.agent-foreman/mvp/plan.json`;
- `.agent-foreman/mvp/integration-mvp-final.json`;
- `.agent-foreman/mvp/evaluation/evaluation.json`;
- `.agent-foreman/mvp/evaluation/root-repair-verification.json`.

The three original worker delta guards remain failed because this non-Git shared workspace mixed concurrent production writes with cache and temporary-file noise. They must never be reported as passed. Later campaigns must use package-local manifests or enforced path isolation.

### 3.2 What Phase 1 did not complete

Delivery Phase 1 is not the same as all of Implementation Plan Milestone 1. The following Milestone 1 obligations remain and must be carried forward:

| Carry-forward item | Governing references | Must be complete before |
| --- | --- | --- |
| Environment/secret-file loader, collision checks, redacted startup errors | Technical Spec 4.1, 15.3; Security 2, 7; AC-001, AC-002, AC-035 | Any real provider, GitHub token, admin, or production startup work |
| Runtime SQLite schema and transactional migrations | Technical Spec 15.1; ADR-003; AC-024, AC-031, AC-035, AC-036 | Bundle activation state in Phase 2 and public limits/admin in later phases |
| Safe structured logging and diagnostics | Technical Spec 15.3; Security 11; AC-035 | Any GitHub/provider/bundle background operation |
| GitHub and provider mock servers | Implementation Plan section 6 and section 12 | Their first network adapter integration gate |
| TypeScript/pnpm workspace, locked frontend toolchain, unit/build setup | Technical Spec 3; ADR-011, ADR-012; AC-019, AC-023, AC-036 | First visitor UI package in Phase 3 |
| Built React serving and same-origin production integration | Technical Spec 3, 16; ADR-011; AC-019, AC-034, AC-036 | Phase 3 visitor integration exit |
| Dockerfile/Compose, non-root/read-only posture, healthcheck, persistent volume | Technical Spec 3, 15; Security 9; Operations 1, 7; AC-036 | Phase 5 clean-host gate; create earlier when needed for integration |
| CI workflow spanning locked Python and TypeScript checks | Implementation Plan sections 4, 6, 11; ADR-012; AC-036, AC-037 | Before a phase is described as CI-verified |

No milestone report may claim Implementation Plan Milestone 1 complete until these rows and the section 6 exit gate have evidence.

## 4. Non-delegable Main/Root authority

Main/Root always retains interpretation of user intent, architecture, public behavior, completion, and final communication. The following seams are Main-owned unless the owner explicitly approves a different governance plan:

- public configuration, API, event, error-code, manifest, database, provider, and sprite contracts;
- lifecycle and production entrypoints;
- persistence, migrations, transactions, atomic activation, rollback, and concurrency;
- authentication, authorization, sessions, CSRF, GitHub permissions, and mutation allowlists;
- network clients, redirect/host validation, secret handling, prompt construction, and output policy;
- producer/consumer integration and shared serialization seams;
- release, deployment, migration, and irreversible/external side effects;
- all changes to `docs/TECHNICAL_SPEC.md`, `docs/ACCEPTANCE_CRITERIA.md`, `docs/DECISIONS.md`, `docs/SECURITY.md`, `docs/OPERATIONS.md`, `docs/SPRITE_FORMAT.md`, `reponpc.example.yml`, `.env.example`, dependency manifests, lockfiles, workflow permissions, and deployment configuration;
- plan freezing, integration records, final verified state, and owner escalation.

Workers may implement a pure internal leaf behind a frozen Main-owned interface. They may report only `implemented` or `blocked`; they cannot declare integration or completion.

## 5. Package eligibility and routing

### 5.1 A package may be delegated only when all are true

- Its inputs, outputs, stable errors, consumers, and prohibited behavior are frozen.
- It has no public contract, security policy, lifecycle, persistence, network, concurrency, migration, or external-side-effect authority.
- Exact owned paths do not overlap another active package.
- Focused executable gates and at least one smallest falsifying counterexample exist before dispatch.
- The worker's repository and tool access are known.
- A qualified capability card supports the risk and size of the package.
- Coordination cost is lower than Main implementing it directly.

Use `main_direct` when any condition is false. Do not create work merely to keep a subagent busy.

### 5.2 Package size

- Normal verified worker: at most three production files and three test files.
- Unverified/degraded worker: at most one production file and one test file.
- Larger work needs a written `size_exception` and still may not cross a Main-owned seam.
- Dispatches enumerate exact repository-relative files. Globs and directory-only ownership are not accepted.

### 5.3 Universal prohibited paths

Unless a package is explicitly Main-owned, every dispatch prohibits:

- all files not listed in `owned_paths`;
- `AGENTS.md` and all normative documents;
- `pyproject.toml`, `uv.lock`, package/pnpm manifests and lockfiles;
- `.env.example`, `reponpc.example.yml`, Docker/Compose files, and `.github/workflows/**`;
- `.agent-foreman/**` except the worker's named handoff/artifact directory;
- existing shared contract, entrypoint, router, migration, database, provider, authorization, security, and integration modules;
- generated files, caches, bytecode, virtual environments, and test temporary directories.

If an unowned path is required, the worker stops as `blocked`. It does not expand its own scope.

## 6. Mandatory campaign workflow

Every actual delegation follows these steps in order.

### Step 0 — Main preflight

Main:

1. confirms current user/host authorization for subagents;
2. reads the sources in section 2.2;
3. inventories current files, dirty/shared-workspace state, available runtimes, and existing tests;
4. identifies the exact Delivery Phase, Implementation Milestone, FR/NFR, AC, ADR, security, operations, and sprite references;
5. records unresolved contradictions and escalates high-impact choices;
6. establishes a cache-free baseline manifest for every candidate owned and prohibited path.

Exit: a written current-state evidence set exists. If the specification is not approved or a governing contract is ambiguous, use `main_direct` for documentation/diagnosis only or block.

### Step 1 — Freeze contracts and ownership

Main defines for each node:

- objective and non-objectives;
- frozen input, output, stable error, and consumer contracts;
- Main-owned seam and delegable leaf boundary;
- exact `owned_paths`, `prohibited_paths`, and `read_first` sections/files;
- critical/noncritical invariants;
- minimal counterexamples and phase-exit claims;
- focused, integration, system/runtime, and security gates;
- stop/replan policy.

Exit: no worker is being asked to discover or choose a public/shared contract.

### Step 2 — Route from capability evidence

Main creates a capability card from authoritative host readback when available. A requested model name is not proof of identity or qualification. Unknown repository/tool access forbids delegation. Degraded identity limits a package to one production and one test file.

Exit: each DAG node is explicitly `main`, `worker`, `evaluator`, or `gate_runner`, with a reason.

### Step 3 — Build and validate the full plan

For every campaign with a worker, Main creates:

```text
.agent-foreman/<campaign>/
  plan.json
  plan.md
  dispatches/
  handoffs/
  integrations/
  fingerprints/
  artifacts/
  evaluation/
  evidence-ledger.jsonl
```

`plan.json` uses the full `agent-foreman/plan` 1.x profile and is the semantic source. It includes capability cards, interfaces, lifecycle, state transitions, failure boundaries, packages, dependency graph, dispatches, handoffs, integration records, invariants, gates, evidence ledger, stop conditions, and fallback policy. `plan.md` is a deterministic human-readable rendering.

Package state advances only through:

```text
planned -> validated -> frozen -> assigned -> in_progress
        -> implemented -> integrated -> verified
```

Any state may become `blocked` only with its prior state, linked invariant/gate, exact evidence, and one next action. Main freezes plans, records integration, and declares final verification.

Evidence is append-only JSON Lines. Each entry has a stable ID, timestamp, actor role, invariant/gate links, exact command and exit code, concrete observation, artifact path/SHA-256, and deterministic/advisory classification. Never edit earlier evidence to make a later result appear clean.

Validate structure, references, ownership, cycles, path overlap, state, gates, oracle origins, and placeholders before freezing. Structural validation does not prove that Main selected the correct production caller, store, lifecycle owner, or oracle; Main must review those semantics separately.

Exit: `planned -> validated -> frozen`. No dispatch occurs before freeze.

### Step 4 — Create self-contained dispatches

Main writes one `agent-foreman/dispatch` per worker. It contains the plan/package IDs, authorization source, capability expectation, objective, frozen contracts, exact paths, read-first material, invariant/gate IDs, exact commands, expected artifacts, counterexamples, stop conditions, and allowed statuses.

Dispatches contain public task material only. They do not reveal evaluator-only defects, hidden probes, anti-oracles, controller paths, or expected hidden output.

Exit: package state is `assigned`; the worker can execute without asking Main to invent a contract.

### Step 5 — Execute with scope enforcement

The worker:

1. reads every `read_first` item;
2. verifies its package-local pre-edit fingerprint;
3. edits only exact owned paths;
4. adds normal, edge, failure, and trust-boundary tests proportional to the leaf;
5. prefixes every shell command and every command-chain segment with `rtk`, using `rtk proxy` only when a filtered form cannot work;
6. runs the focused gates exactly as dispatched;
7. writes only worker artifacts in the assigned artifact area;
8. returns `implemented` or a precise `blocked` record.

The worker must preserve unrelated work, must not reset/discard another actor's changes, and must not modify generated output manually.

### Step 6 — Verify handoff and delta

Main rejects a handoff unless:

- every changed path is owned and every owned changed path is reported;
- no prohibited path or unexpected generated/cache file changed;
- every focused gate has an integer exit code and concrete observation;
- an implemented handoff includes diff and test artifacts;
- a blocked handoff names exactly one next action.

Use host-enforced path isolation when available. In a shared non-Git workspace, fingerprint only enumerated package/prohibited paths and exclude caches before dispatch. If attribution cannot be proven, record the delta guard as failed/limited; never infer a pass from manual inspection.

Exit: accepted worker state is `implemented`, not `integrated`.

### Step 7 — Main integration

Main reviews the actual delta, wires the leaf through the real producer/consumer, entrypoint, lifecycle, database, or public boundary, and runs:

- all worker focused gates;
- contract tests at every touched seam;
- aggregate phase tests;
- applicable security/privacy gates;
- required build, lint, type, bundle, browser, Compose, benchmark, or runtime probes.

Main writes the `agent-foreman/integration` artifact. A blocking deterministic failure makes the phase `blocked` even when a worker/evaluator recommends pass. If two packages fail against one contract, Main invalidates and replans the reachable producer/consumer subgraph instead of patching both leaves independently.

Exit: package state may become `integrated`; no verification claim yet.

### Step 8 — Independent falsification

After Main integration, a fresh evaluator receives read-only production access and write access only to `.agent-foreman/<campaign>/evaluation/`. Prefer a different verified model family; otherwise disclose `same-model-fresh-context` or `unknown` diversity.

For each critical invariant, the evaluator adds at least one new probe with setup, fault injection, real production trigger, observable oracle, anti-oracle, exact command, and artifact. The evaluator cannot repair production, modify contracts, dispatch workers, or declare completion.

Main treats `pass|revise|blocked` as advice. Deterministic probe results decide the gate. Any Main repair requires aggregate-gate rerun and bounded repair accounting.

### Step 9 — Close and report

Only Main may transition integrated work to `verified`. Closure requires all blocking gates, required artifacts, cross-document updates, and acceptance evidence. The final report states:

- outcome and exact files changed;
- Delivery Phase, Implementation Milestone, FR/NFR, and AC IDs addressed;
- commands/checks and exact pass/fail/not-run results;
- security, privacy, accessibility, benchmark, browser, bundle, or operational evidence where applicable;
- remaining risks, assumptions, carry-forward items, and owner decisions;
- any failed/limited delta guard without softening it.

## 7. Remaining execution map

The following packages are routing defaults. Before dispatch, Main must convert each selected package into exact files and a fresh full plan. A package marked `MAIN` is still a required step; it is not a subagent task.

## 7.1 Delivery Phase 2 — Immutable evidence and retrieval

**Implementation mapping:** Milestone 2 plus the runtime/logging/mock prerequisites carried from Milestone 1.  
**Primary requirements:** FR-002–FR-007, FR-020, FR-021; NFR-001, NFR-003, NFR-004, NFR-006, NFR-008, NFR-011.  
**Acceptance focus:** AC-003–AC-009, AC-029–AC-032, and security portions of AC-033/AC-035.  
**Read first:** Technical Spec 4.3, 5–7, 10, 14, 15.1, 15.3, 17; Acceptance Criteria 2, 3 (AC-007–AC-009), 7, AC-033, AC-035; ADR-003–ADR-007; Security 2–7, 9, 11–12; Operations 3, 6, 10–12, 15.

| Package | Frozen input | Produced output | Stable failure boundary | Consumer |
| --- | --- | --- | --- | --- |
| P2-00 | Approved contracts, Phase 1 code, carry-forward ledger | Frozen interfaces, runtime/logging/secret prerequisites | Configuration/startup-safe errors; owner escalation for contract changes | P2-01–P2-07 |
| P2-01 | Normalized path plus bounded source metadata and policy | Include/skip decision and reason code | Reject invalid traversal/aliases; never include content in errors | Production indexing intake |
| P2-02 | Eligible source bytes, language, path, line-ending policy, limits | Deterministic bounded chunk candidates | Frozen parser/fallback error or skip result | Evidence-record builder |
| P2-03 | Normalized user query and locale | Allowlisted FTS representation or bounded short-query mode | Invalid/empty query result without executable raw syntax | Lexical SQLite channel |
| P2-04 | Validated query vector, matrix, evidence IDs, identity/dimension | Stable ranked IDs/scores | Shape, finite, normalization, and identity mismatch | Semantic retrieval channel |
| P2-05 | Public scenario brief and licence-safe source material | Exact fixture files only | Fixture schema/licence/secret-scan failure | Main-owned evaluation oracle/scorer |
| P2-06 | Valid config, resolved commits, evidence, embeddings, card assets | `index.sqlite`, immutable bundle/manifests, activation/publication state | Stable build/update/readiness errors; last-known-good retained | Runtime retrieval/status and GitHub publication |
| P2-07 | Integrated Phase 2 system and frozen benchmark corpus | Gate artifacts, evaluation record, verified/blocked phase state | Precise failed invariant/gate | Phase 3 readiness decision |

### P2-00 — Foundation catch-up and contract freeze (`MAIN`)

- **Do:** freeze resolved-repository, eligible-source, chunk, embedding identity, index schema, manifest, stable-manifest, bundle handle, activation-state, and safe-error interfaces. Implement the environment/secret loader, runtime migration basis, safe logging basis, and GitHub mock prerequisites needed by this phase.
- **Main-owned paths:** configuration/environment boundary, domain contracts, runtime database/migrations, GitHub network client, index/bundle orchestrators, CLI/entrypoint, dependency/lock files, normative examples.
- **Smallest falsifiers:** direct+`_FILE` secret collision; Draft spec; model/dimension/prefix mismatch; runtime and immutable index sharing one database; a private URL in a public error.
- **Gates:** configuration/secret contract tests, transactional migration test, safe-log canary, real CLI/application entrypoint probes.
- **Stop:** any new environment variable, schema field, database table contract, error code, network permission, or dependency choice not already approved.

### P2-01 — Pure mandatory exclusion classifier (`WORKER ELIGIBLE`)

- **Do:** classify normalized candidate path/type/size metadata using the frozen mandatory/global/configured exclusion policy. Return stable reason codes without file bodies.
- **Default candidate owned paths:** `src/reponpc/indexing/exclusions.py`; `tests/unit/test_exclusions.py`. A verified worker may additionally own one named security test file.
- **Prohibited:** GitHub fetching, secret contents/logging, configuration models, index orchestration, network/redirect logic, database writes.
- **Inputs/outputs:** immutable normalized POSIX path and bounded metadata -> include/skip decision plus stable reason; no I/O.
- **Smallest falsifiers:** `../x`, absolute path, backslash alias, `.env`, symlink, submodule, lockfile, individually valid files exceeding corpus budget, and a skipped secret canary appearing in output.
- **Gates:** focused table-driven unit tests; Main integration sends real GitHub fixture metadata through the production eligibility pipeline.
- **References:** Technical Spec 5.1–5.2 and 4.3; AC-004; Security 4, 7.

### P2-02 — Tree-sitter chunk leaves (`WORKER ELIGIBLE AFTER MAIN ADAPTER FREEZE`)

- **Do:** implement one bounded language group behind Main's parser protocol. Prefer whole named symbols, split oversized nodes deterministically, preserve one-based inclusive lines, and fall back only through the frozen boundary.
- **Default candidate owned paths:** one named parser module below `src/reponpc/indexing/parsers/` and its exact test file. Split Python/JS-TS/Go-Rust into separate serialized packages if the same registry file would be shared.
- **Prohibited:** parser registry, dependency manifests/lockfiles, evidence-ID schema, fallback chunker contract, index writer, configuration contract.
- **Smallest falsifiers:** nested symbol, oversized node, CRLF, multibyte text, syntax error, empty file, one line exceeding the character bound, repeated identical source.
- **Gates:** language golden tests plus Main producer-to-consumer test from eligible source bytes to accepted evidence records.
- **References:** Technical Spec 5.3; AC-005, AC-006; NFR-011; ADR-007.

### P2-03 — Safe lexical query compiler (`WORKER ELIGIBLE`)

- **Do:** compile normalized user terms into an allowlisted FTS query representation; keep raw user syntax as values and define the bounded short-query path.
- **Default candidate owned paths:** `src/reponpc/retrieval/fts_query.py`; `tests/unit/test_fts_query.py`.
- **Prohibited:** SQLite connection ownership, schema/migrations, public API, retrieval orchestration, logs.
- **Smallest falsifiers:** quotes, parentheses, `OR`, `NEAR`, wildcard, NUL/control characters, two-character symbols, Traditional Chinese, path punctuation, empty/only-punctuation query.
- **Gates:** exact compiler unit tests; Main integration against both real term and trigram FTS5 tables with an injection fixture.
- **References:** Technical Spec 6–7; AC-007; Security 12.

### P2-04 — Pure vector validation and ranking (`WORKER ELIGIBLE`)

- **Do:** validate finite normalized float32 shapes and rank a frozen matrix deterministically with stable tie behavior.
- **Default candidate owned paths:** `src/reponpc/retrieval/vector.py`; `tests/unit/test_vector.py`.
- **Prohibited:** provider/network adapter, embedding identity contract, NumPy/dependency version changes, bundle compatibility, readiness policy.
- **Smallest falsifiers:** wrong dimension, NaN/Inf, zero vector, non-normalized vector, duplicate scores, empty matrix, shape mismatch.
- **Gates:** numerical unit tests; Main integration loads real bundle blobs and rejects identity/dimension/prefix mismatch before query.
- **References:** Technical Spec 5.4, 6–7; ADR-004, ADR-006; AC-008, AC-009.

### P2-05 — Retrieval fixtures (`WORKER ELIGIBLE WITH BLIND ORACLE SEPARATION`)

- **Do:** create named public fixture files containing exact symbols/paths, bilingual paraphrases, overlaps, owner assertions, negative content, and malicious instructions.
- **Owned paths:** exact files enumerated below one campaign-specific fixture repository. No wildcard ownership in the dispatch.
- **Prohibited:** `evals/expected_evidence.yml`, benchmark thresholds, scorer, hidden evaluator probes, production retrieval code.
- **Smallest falsifiers:** fixture expected answer visible only in hidden/controller material; same question duplicated under two IDs; unsupported person claim accidentally supported by an owner assertion.
- **Gates:** fixture schema/licence/secret scan; Main or human separately reviews expected evidence and language pairs.
- **References:** Acceptance Criteria section 1 and AC-007–AC-013, AC-033; Implementation Plan section 12.

### P2-06 — Index database, bundle, updater, and publication (`MAIN`)

- **Do:** implement schema-v1 SQLite creation/read-only loading, embeddings, manifests/checksums, safe `tar.zst`, GitHub Release publication-last flow, ETag polling, staging, validation, atomic activation, in-flight handles, retention, pinning, rollback, and last-known-good behavior.
- **Main-owned paths:** index writer/schema, bundle serializer/verifier/updater, runtime bundle state, GitHub publication workflow, CLI/public status seams.
- **Smallest falsifiers:** traversal, symlink/hardlink/device, duplicate path, zip/archive bomb, checksum mismatch, unknown/missing file, corrupt SQLite, incompatible app/schema/embedding, failed smoke query, crash before pointer swap, concurrent reader during activation, publication failure before manifest update.
- **Gates:** real producer-to-consumer bundle; rollback fault injection; application lifecycle polling; atomic activation with in-flight reader; Actions mock publication order; outer/internal checksum negatives.
- **References:** Technical Spec 6, 14, 15.1, 17; AC-029–AC-032; ADR-003–ADR-006; Security 4, 6, 9; Operations 6, 10–12.

### P2-07 — Phase 2 aggregate and evaluator gate (`MAIN + EVALUATOR`)

- **Do:** run deterministic build twice, retrieval benchmark, bilingual parity, malicious bundle matrix, activation/rollback, safe logging, and new independent probes.
- **Exit:** AC-003–AC-009 and bundle negative cases pass; Recall@8 >=85%, paired-language parity >=90%, and warm retrieval p95 <=750 ms on the documented reference host, or an owner-reviewed blocker stops dependent answer work.
- **Independent probes:** at least one new probe each for input scope, FTS injection, embedding mismatch, producer/consumer bundle compatibility, last-known-good rollback, and concurrent activation.

## 7.2 Delivery Phase 3 — Grounded chat and visitor experience

**Implementation mapping:** Milestones 3 and 4, plus the frontend/tooling/mock prerequisites carried from Milestone 1.  
**Primary requirements:** FR-008–FR-016, FR-022, FR-023; NFR-001, NFR-002, NFR-005, NFR-007–NFR-009, NFR-012, NFR-014.  
**Acceptance focus:** AC-010–AC-023, AC-032–AC-035.  
**Read first:** Technical Spec 7–10, 12–13, 15.2–17; Acceptance Criteria 3–5 and AC-032–AC-035; ADR-002, ADR-006–ADR-008, ADR-011, ADR-013, ADR-014; Security 2–8, 11–12; Operations 5, 7–9, 14–15; Sprite Format 1–7.

| Package | Frozen input | Produced output | Stable failure boundary | Consumer |
| --- | --- | --- | --- | --- |
| P3-00 | Approved API/provider/frontend contracts and locked tool choices | Frontend workspace, mocks, same-origin serving, capability interfaces | Build/setup/capability/secret-safe failure | P3-01–P3-07 |
| P3-01 | Server-only provider config and bounded provider request | Normalized result/health/usage/timing or provider failure category | Auth/rate/timeout/unavailable/invalid/context errors; no fallback | Retrieval and chat orchestration |
| P3-02 | One frozen mock scenario contract | Deterministic mock request/response fixture | Fixture schema failure without changing adapter policy | Provider contract tests |
| P3-03 | Validated chat request, retrieved evidence, complete provider result | Validated answer/citations/SSE or localized abstention/error | Stable validation/provider/timeout/readiness errors; no partial unsafe output | Public chat client |
| P3-04 | Request metadata, HMAC key, limits, runtime state | Admission/rejection, counters, safe logs/status | Stable 429/503/error state before provider cost | P3-03 and public status |
| P3-05 | Frozen typed API fixture and localized display strings | Semantic feature component and focused tests | Explicit loading/empty/error/offline states; no network ownership | Main-owned visitor composition |
| P3-06 | Canonical sheet plus semantic state/reduced-motion flag | Deterministic accessible rendered frame/state | Invalid frozen state/asset rejection | Main-owned lifecycle controller |
| P3-07 | Integrated provider/chat/visitor system | Browser/a11y/quality/security evidence and phase state | Precise failed invariant/gate | Phase 4 readiness decision |

### P3-00 — Frontend and provider foundations (`MAIN`)

- **Do:** create the pnpm/TypeScript/Vite workspace and locked gates, same-origin built-asset integration, provider mock servers, capability/identity contracts, server-only secret loading, and public status state ownership.
- **Smallest falsifiers:** browser receives provider secret/base URL; unsupported provider capability is sent anyway; frontend builds from an unlocked second package manager; API and UI require broad CORS.
- **Gates:** locked install/build/type/lint/unit checks, mock capability matrix, same-origin production asset route, secret canary scans.
- **Stop:** new browser/API contract, dependency manager, hosted dependency, provider fallback, or frontend origin.

### P3-01 — Provider adapters and orchestration (`MAIN`)

- **Do:** implement OpenAI-compatible, Ollama, and local embedding adapters; explicit capability/identity behavior; bounded retries/timeouts; normalized failures; and no silent fallback.
- **Smallest falsifiers:** Ollama outage calls a cloud host; invalid output shape reaches retrieval; unsupported structured/streaming parameter is sent; provider URL/response body leaks; retry exceeds request deadline.
- **Gates:** both provider families through the same real adapter contract and mock servers; documented small live matrix before release.
- **References:** Technical Spec 13 and 17; AC-015, AC-016; ADR-006; Security 5–7; Operations 5.

### P3-02 — Provider fixtures (`WORKER ELIGIBLE`)

- **Do:** add one exact mock scenario or response fixture behind a frozen mock-server API.
- **Default candidate owned paths:** one named fixture file and one exact mock contract test.
- **Prohibited:** provider adapter, capability schema, retry/fallback policy, network host validation, secrets, live credentials/output.
- **Smallest falsifiers:** unsupported capability silently present; malformed usage; context overflow; timeout; partial/malformed envelope; private URL in error.
- **Gate:** Main runs the real adapter against the fixture.

### P3-03 — Answer, citation, and SSE boundary (`MAIN`)

- **Do:** own prompt construction, request-local IDs, complete buffering, one repair, claim/evidence validation, person-claim policy, inference dependencies, Markdown/URL sanitization, immutable permalink construction, safe abstention, and exact SSE order.
- **Smallest falsifiers:** forged ID/URL, missing marker, inference cycle, unsupported person claim, repository prompt injection, script-bearing Markdown, percent-encoding edge, provider stops mid-generation, disconnect/timeout, partial output before validation.
- **Gates:** production chat entrypoint with real retrieval records and mock provider; exact SSE sequence; adversarial output corpus; immutable link resolution; no unvalidated byte reaches the client.
- **References:** Technical Spec 7–10, 17; AC-010–AC-014, AC-017, AC-033, AC-034; ADR-007, ADR-013; Security 4–5, 8.

### P3-04 — Public limits, runtime state, and diagnostics (`MAIN`)

- **Do:** implement HMAC IP buckets, global concurrency, UTC daily budget, timeout/input/history/output caps, pre-provider rejection, safe metrics/logging, and independent index/embedding/chat states.
- **Smallest falsifiers:** raw IP persisted; limit checked after embedding/chat call; two process-local counters represented as global; cancellation leaks a slot; midnight rollover wrong; status reflects private diagnostics.
- **Gates:** real endpoint with provider call counter at zero for every rejection; same-process concurrent owners; cancellation around semaphore/provider boundary; runtime persistence/restart; safe-log canary.
- **References:** Technical Spec 9.4, 15, 17; AC-016–AC-018, AC-032, AC-035; NFR-002, NFR-012, NFR-014.

### P3-05 — Visitor presentation leaves (`WORKER ELIGIBLE AFTER API SNAPSHOT`)

- **Do:** implement one semantic, presentational feature from a frozen typed API fixture, such as profile/projects, suggested questions, status panel, or citation panel.
- **Default candidate owned paths:** one component file and its exact test file below `apps/web/src/features/<feature>/`. A separate package may own one CSS/module file only when ownership remains disjoint.
- **Prohibited:** API types/schema, fetch/SSE client, app router/lifecycle, i18n source contract, security sanitizer, shared auth, build/dependency files.
- **Smallest falsifiers:** keyboard inoperable control; citation marker without focus target; content available only in canvas/animation; mobile overflow; unsafe raw HTML; missing loading/error/offline semantics.
- **Gates:** component tests and accessibility checks; Main wires through real API/SSE lifecycle.
- **References:** Technical Spec 16; AC-019, AC-023, AC-034; NFR-009.

### P3-06 — Character-state presentation leaf (`WORKER ELIGIBLE`)

- **Do:** render the frozen seven-state canonical sheet and reduced-motion first frames. This package does not choose application lifecycle transitions.
- **Default candidate owned paths:** one character renderer component/module and one exact test file.
- **Prohibited:** state controller, sprite validation/upload, canonical dimensions/order, card generation, app lifecycle.
- **Smallest falsifiers:** wrong row/order, nondeterministic transition column, smoothing enabled, reduced-motion still animates, visible state lacks an accessible text equivalent.
- **Gates:** deterministic frame-coordinate tests and Main lifecycle integration from listen -> think -> talk -> success/offline.
- **References:** Technical Spec 12.1, 16; Sprite Format 1–7; AC-020, AC-023; ADR-014.

### P3-07 — Visitor integration and phase gate (`MAIN + EVALUATOR`)

- **Do:** integrate typed fetch/SSE, conversation-preserving locale switch, responsive routes, character lifecycle, error recovery, semantic content, focus, screen-reader announcements, contrast, touch targets, and reduced motion.
- **Exit:** provider contract suite, answer quality thresholds, injection/forgery/no-fallback/limits, desktop/mobile bilingual Playwright flows, automated accessibility, and manual keyboard/screen-reader review pass.
- **Independent probes:** forged source ID, unasserted person claim, model tool/network instruction, SSE terminal race, limit-before-cost, locale switch with visible history, reduced-motion lifecycle, citation focus/URL safety.

## 7.3 Delivery Phase 4 — Owner administration, assets, and publication

**Implementation mapping:** Milestone 5 plus character/card/publication portions of Milestones 2 and 4.  
**Primary requirements:** FR-015–FR-021, FR-024; NFR-001–NFR-003, NFR-009, NFR-012.  
**Acceptance focus:** AC-020–AC-032, AC-034, AC-035.  
**Read first:** Technical Spec 4, 10–12, 14–17; Acceptance Criteria 5–8; ADR-002, ADR-005, ADR-008–ADR-011, ADR-014; Security 2–4, 6–10, 12; Operations 3–13, 15; Sprite Format all sections.

| Package | Frozen input | Produced output | Stable failure boundary | Consumer |
| --- | --- | --- | --- | --- |
| P4-00 | Approved admin/asset/card/GitHub/publication contracts | Frozen interfaces, errors, paths, mutation policy | Owner escalation for any public/security/permission change | P4-01–P4-08 |
| P4-01 | Credential attempt, HTTP origin/cookie/CSRF, runtime state | Rotated/revoked session state or stable auth error | Generic auth, CSRF, expiry, revocation, backoff failures | Admin API dependencies |
| P4-02 | Valid session, validated content/asset, fixed repo/branch/path, expected SHA | GitHub read/commit/workflow result and safe audit | Auth/allowlist/conflict/upstream errors with no unauthorized mutation | Admin save/dispatch/status |
| P4-03 | Frozen asset manifest, allowlisted IDs/colors | Deterministic canonical RGBA/PNG candidate | Unknown ID/color or composition invariant failure | P4-04 canonical validator |
| P4-04 | Bounded candidate bytes and exact filename | Canonical PNG bytes, hash, preview metadata or stable asset errors | Named sprite validation codes; no mutation | Preview, GitHub writeback, bundle/card build |
| P4-05 | Validated profile/card/character data and public base URL | SVG/GIF/PNG, ETags, sanitized copy-ready Markdown | Stable validation/variant failure; never active content | Public endpoints and admin snippet UI |
| P4-06 | Frozen typed admin responses and localized field errors | Semantic form/preview/status component | Explicit auth/conflict/validation/loading state | Main-owned admin route/session composition |
| P4-07 | Valid config/source commits and verified build result | Immutable Release asset then stable manifest | Failed stage leaves prior manifest unchanged | Runtime updater and owner status |
| P4-08 | Integrated owner update journey | End-to-end gate/evaluator evidence and phase state | Precise failed invariant/gate | Phase 5 release audit |

### P4-00 — Admin/publication contract freeze (`MAIN`)

- **Do:** freeze session/CSRF API, config/preview/write endpoints, GitHub allowlist/conflict contract, sprite error codes, card variants/cache validators, README snippet, workflow dispatch, and publication/activation status.
- **Smallest falsifiers:** browser selects target branch/path; preview mutates GitHub/model; draft contains a secret field; API returns token/hash/private URL; unknown asset filename is accepted.
- **Stop:** any change to endpoint, cookie, error code, env var, GitHub permission, sprite layout, bundle/publication sequence, or card size.

### P4-01 — Authentication, session, and CSRF (`MAIN`)

- **Do:** Argon2id verification, generic errors/backoff, 256-bit server-side sessions, secure cookie, origin/Referer and CSRF checks, idle/absolute expiry, rotation, logout, logout-all/session epoch, and safe audit.
- **Smallest falsifiers:** timing/user enumeration; forged/absent CSRF; cross-origin same-cookie request; old ID after refresh; revoked/expired session; logout-all without password; raw tokens/hashes in DB/log/API.
- **Gates:** real HTTP/cookie/runtime DB tests including restart and concurrent refresh/revocation.
- **References:** Technical Spec 11.1–11.2, 15.1; AC-024, AC-035; ADR-009; Security 7–8, 10.

### P4-02 — GitHub read/write and workflow dispatch (`MAIN`)

- **Do:** server-only fine-grained client, fixed repository/branch/workflow, exact path allowlist, blob-SHA conflict, validated/re-encoded body, bounded commit message, safe audit, and Actions dispatch.
- **Smallest falsifiers:** traversal/nested/delete/rename/arbitrary path; stale SHA overwrite; redirect/host escape; token exposed; accidental wider token scope bypasses app allowlist; preview causes network mutation.
- **Gates:** real adapter against GitHub mock with mutation counter; 409 conflict; allowlist security matrix; no external call on validation/preview.
- **References:** Technical Spec 11.2–11.3; AC-025–AC-027, AC-035; ADR-009, ADR-010; Security 6–7, 10; Operations 4, 6.

### P4-03 — Pure built-in sprite composer (`WORKER ELIGIBLE AFTER ASSET MANIFEST FREEZE`)

- **Do:** deterministically compose allowlisted layers/colors into the canonical 128x224 RGBA sheet.
- **Default candidate owned paths:** `src/reponpc/cards/sprite_composer.py`; `tests/unit/test_sprite_composer.py`.
- **Prohibited:** uploaded-file decoder/re-encoder, asset registry contract, config model, endpoints, GitHub writeback, card/SVG serializer, dependency/asset files not explicitly owned.
- **Smallest falsifiers:** unknown ID/color, wrong layer order, wrong dimensions/grid, non-deterministic bytes, smoothing/fractional placement, missing state/frame.
- **Gates:** pixel-coordinate/golden test; Main passes composed bytes through the same canonical validator used for custom assets.
- **References:** Technical Spec 12.1; Sprite Format 1–6, 8; AC-020; ADR-014.

### P4-04 — Upload validation and canonical re-encoding (`MAIN`)

- **Do:** enforce byte/decode/pixel bounds, reject APNG/polyglot/unsafe modes, exact dimensions/grid/row content/transparency, remove metadata, deterministically re-encode, hash, and reuse identical bytes for preview/writeback/bundle.
- **Smallest falsifiers:** MIME-only PNG, decompression bomb, trailing polyglot, APNG, ancillary text/profile, empty first frame, no transparency, invalid filename, preview/writeback byte mismatch.
- **Gates:** golden valid/invalid assets, resource bounds, metadata scan, identical consumer bytes, no GitHub mutation on failure.
- **References:** Technical Spec 12.1; Sprite Format 4, 8; AC-020, AC-027, AC-034; Security 4, 9.

### P4-05 — Card and README outputs (`MAIN`)

- **Do:** generate sanitized self-contained 600x180 SVG, GIF, PNG, complete static first frame, restrictive headers/CSP, ETags, revisioned URLs, and copy-ready snippets.
- **Smallest falsifiers:** XML breakout, script/handler/foreignObject/remote URL, unsafe scheme, unescaped/truncated locale text, animation-disabled empty card, stale ETag, malformed Markdown target.
- **Gates:** XML/image validation, injection corpus, deterministic image comparison, endpoint headers, real README snippet parser, dated real GitHub/browser check at release.
- **References:** Technical Spec 9.3, 12.2; AC-021, AC-022, AC-028, AC-034; ADR-002, ADR-008; Sprite Format 7.

### P4-06 — Admin presentation leaves (`WORKER ELIGIBLE AFTER API SNAPSHOT`)

- **Do:** implement one typed form/preview/status/snippet component using frozen mock responses and field-level localized errors.
- **Default candidate owned paths:** one component and one test below `apps/web/src/features/admin/`.
- **Prohibited:** auth/session store, CSRF/fetch client, API schemas, raw-YAML parser, sanitizer, GitHub mutation, route guard, i18n contract, dependency/build files.
- **Smallest falsifiers:** secret field displayed/accepted; stale draft retained after logout; save enabled after conflict; preview presented as saved; mobile/keyboard/focus failure; missing locale message.
- **Gates:** component/a11y tests; Main real-session and real-mock-GitHub Playwright integration.
- **References:** Technical Spec 11, 16; AC-023–AC-028, AC-034.

### P4-07 — Actions publication (`MAIN`)

- **Do:** validate, index, test, upload immutable Release asset, verify availability/checksum, and update stable manifest last with least workflow permission.
- **Smallest falsifiers:** stable manifest changes after failed validation/upload/verification; asset overwritten in place; workflow accepts private/arbitrary repository; credentials/body leak; unpinned release action.
- **Gates:** mocked failed stage matrix and successful order trace; bundle consumer activation; workflow permission review.
- **References:** Technical Spec 14; AC-029–AC-032; ADR-005; Security 4, 6, 10, 12; Operations 6.

### P4-08 — Owner journey and evaluator gate (`MAIN + EVALUATOR`)

- **Do:** exercise login -> validate/preview -> conflict-safe save/asset -> dispatch -> publish -> runtime activation -> README snippet, while preserving rollback.
- **Exit:** all session/CSRF/backoff/revocation, allowlist/conflict, preview side-effect, asset/card injection, publication-last, activation/rollback, bilingual/mobile/admin browser tests pass; no secret/private provider data enters any forbidden location.
- **Independent probes:** unknown side effect denied, cross-origin CSRF, concurrent SHA conflict, malicious PNG, card injection, manifest publication fault, end-to-end previous-bundle preservation.

## 7.4 Delivery Phase 5 — Release hardening

**Implementation mapping:** Milestone 6 and every incomplete earlier exit gate.  
**Primary requirements:** all FR/NFR.  
**Acceptance focus:** AC-001–AC-037.  
**Read first:** every repository instruction and source in section 2.2, especially Technical Spec 19, Acceptance Criteria 1, 9, 10, Security 12–13, Operations 7–16, and Sprite Format 8.

| Package | Frozen input | Produced output | Stable failure boundary | Consumer |
| --- | --- | --- | --- | --- |
| P5-00 | Repository, prior campaign artifacts, FR/NFR/AC matrix | Complete traceability and unfinished-obligation ledger | Missing/contradictory evidence is visible, never inferred passed | All release gates |
| P5-01 | Frozen command/environment/oracle | Raw hashed gate artifact and exact result | `pass|fail|not-run|blocked`, never repair or omitted failure | Main acceptance report |
| P5-02 | Frozen corpus/rubric/reference host | Quality/performance measurements | Threshold miss; owner escalation before any threshold/corpus change | Release decision |
| P5-03 | Integrated system and named security canaries | Trust-boundary/scanning evidence | Any critical deterministic failure blocks release | Release decision and security docs |
| P5-04 | Owner-authorized live provider/domain/GitHub/host access | Sanitized dated compatibility evidence | Exact manual AC remains blocked/not-run without real environment | Acceptance report |
| P5-05 | Verified commands/results/assets/licences | Final operational/security/sprite/release documentation | Unverified command/topic/licence remains explicit | Operators and AC-037 |
| P5-06 | All required passing evidence and release inputs | Tagged v1 artifacts and full acceptance report | Any failed/not-run required AC blocks completion | Owner and users |

### P5-00 — Traceability and unfinished-obligation audit (`MAIN`)

- **Do:** create a row for every FR/NFR/AC with implementation owner, automated/manual verification, artifact, result, and unresolved decision. Reconcile Delivery Phases against Implementation Milestones and the carry-forward table in section 3.2.
- **Smallest falsifier:** one requirement has code but no acceptance artifact; a manual criterion is called automated; a skipped/failed case is omitted; a Delivery Phase pass is represented as full Milestone completion.

### P5-01 — Independent gate-running packages (`GATE RUNNER/EVALUATOR ELIGIBLE`)

- **Do:** execute one frozen test domain without production writes: Python, TypeScript/build, API/schema/config, retrieval evaluation, security, browser/accessibility, Docker/Compose, bundle lifecycle, upgrade/rollback, or clean-host installation.
- **Owned paths:** only the campaign artifact/evaluation area; production is read-only.
- **Prohibited:** repairs, contract edits, fixture expectation changes after observing failures, completion declaration.
- **Handoff:** exact environment, command, exit code, raw artifact hash, observed oracle, and any blocked record.

### P5-02 — Performance and quality (`MAIN + EVALUATOR`)

- **Do:** measure reference-corpus warm retrieval p95, Recall@8, bilingual evidence parity, citation resolution, entailment, unsupported abstention, memory, concurrency, and validated-stream timing. Correct measured bottlenecks without weakening controls.
- **Stop:** threshold change, corpus/question removal, hardware-reference change, or scorer/rubric change needs owner approval and governing-document update.
- **References:** NFR-004–NFR-008; AC-009, AC-011–AC-013, AC-017; Owner Review OR-003, OR-007.

### P5-03 — Security and privacy (`MAIN + FRESH EVALUATOR`)

- **Do:** run the complete named trust-boundary matrix: secrets, prompt injection, FTS, XSS/Markdown/SVG/URL, SSRF/redirect, archive/path traversal, forged evidence, sessions/CSRF/backoff, GitHub allowlist/conflicts, provider leakage, logs, budgets/timeouts, image bombs, and last-known-good recovery.
- **Exit:** every critical invariant has a real boundary probe and deterministic pass; dependency/secret/container scans are recorded.
- **References:** Security 1–13; AC-004, AC-014, AC-016, AC-018, AC-021, AC-024, AC-027, AC-030, AC-033–AC-037.

### P5-04 — Live/manual compatibility (`MAIN; OWNER INPUT MAY BE REQUIRED`)

- **Do:** test one representative OpenAI-compatible service, one Ollama model, current Chrome/Firefox/Safari, real GitHub Profile/image proxy, and supported clean x86_64 Docker host. Store sanitized metadata/logs/screenshots, not credentials or prompt/output bodies.
- **Stop:** missing owner-provided service/domain/credentials, external spend, repository permission, or public publication authority. Report the exact blocked criterion rather than substituting a mock.
- **References:** Technical Spec 19; AC-015, AC-016, AC-022, AC-036, AC-037; Operations 2, 5–9, 16.

### P5-05 — Operations, security, sprite, and release documents (`MAIN; REVIEWER ELIGIBLE`)

- **Do:** replace draft assumptions with verified commands/output; complete provider compatibility, backup/restore, upgrade/downgrade, rollback, rotation, incident/disclosure, template/example asset, licence/provenance, contribution, release, version, and security-reporting guidance.
- **Reviewer role:** may return findings with exact section/evidence gaps; may not silently rewrite public contracts.
- **Exit:** every topic required by Technical Spec 15–16 and AC-037 is present and linked to evidence.

### P5-06 — Build and release closure (`MAIN`)

- **Do:** produce locked production image, SBOM/scans/notices, clean-host Compose install, tagged MIT v1 release, application image, immutable sample bundle, release notes, and full acceptance report.
- **Exit:** all 37 ACs pass or the owner explicitly changes the governing requirement before release. Only then may RepoNPC v1 be called complete.

## 8. Gate design requirements

Every gate records exact setup, fault injection, production trigger, oracle, anti-oracle, command, expected exit code, artifact, linked invariants, claim-boundary scope, and blocking state.

Use the strongest applicable boundary:

| Claim | Required evidence |
| --- | --- |
| Production component is used | Invoke the real CLI, HTTP route, workflow, or application entrypoint |
| Background worker lifecycle | Start the application; observe registration, work, cancellation, bounded shutdown |
| One owner in a process | Race two independent owners against one shared source |
| Durable exclusion/claim | Use the real production-compatible store, not an in-memory mutex/fake |
| Crash/replay safety | Crash immediately before/after acknowledgement, restart, and replay |
| Producer/consumer compatibility | Send the real produced bytes unchanged to the real consumer |
| Cancellation safety | Cancel immediately before and after the side-effect commit boundary |
| Metric/log provenance | Trigger a nonzero real event and inspect the configured sink |
| Unknown side effect is denied | Submit an unknown plausible operation through the real approval boundary |
| Rollback works | Fail after the first durable mutation and inspect all participating state |

`run tests`, `check manually`, `looks correct`, and model approval are not valid commands/oracles.

## 9. Failure, repair, and escalation

Classify only rate limits, service/network outage, child launch failure, repository lock, or pre-delta timeout as transient. Retry the same worker at most once.

Use this response matrix:

| Condition | Action |
| --- | --- |
| Malformed dispatch | Main repairs once before work |
| Noncritical focused gate failure | At most two precise bounded repairs |
| Critical gate failure | One precise repair, then Main takeover/fail closed |
| Unowned/prohibited path required | Worker returns `blocked`; Main does not auto-expand scope |
| Two packages fail one contract | Invalidate the contract and replan its reachable subgraph |
| Main rewrites most worker code | Record routing failure and stop delegating that class |
| More than two integration repair rounds | Main takeover or human-controlled stop |
| Deterministic evidence conflicts with approval | Mark blocked |
| Public/security/schema/cost/scope choice required | Escalate to owner with evidence, options, recommendation, impact |

Record `rework_ratio = main_changed_lines_in_worker_owned_scope / max(1, worker_changed_lines)`. A ratio above 0.60 is a provisional routing warning.

## 10. Required artifact templates

The JSON below shows required semantics. Campaign schemas may add validated fields but may not omit required ones.

### 10.1 Capability card

```json
{
  "requested_selector": null,
  "resolved_model_id": null,
  "verification": "unavailable",
  "context_limit": "unknown",
  "tool_access": ["verified-tool"],
  "repository_access": "exact verified scope",
  "evidence": [],
  "known_limits": ["identity and capability are unverified"],
  "routing_confidence": "degraded"
}
```

Use `verification: verified` only with authoritative model readback and comparable evidence. Unknown tool or repository access forbids delegation.

### 10.2 Dispatch brief

```json
{
  "schema_name": "agent-foreman/dispatch",
  "schema_version": "1.0",
  "profile": "full",
  "plan_id": "REPONPC-<CAMPAIGN>",
  "package_id": "PKG-WORKER-<LEAF>",
  "authorization_source": "exact user/host record",
  "requested_selector": null,
  "expected_model_verification": "unavailable",
  "objective": "one bounded outcome",
  "frozen_contracts": ["named input/output/error contract"],
  "owned_paths": ["exact/production.py", "exact/test.py"],
  "prohibited_paths": ["exact/shared_seam.py"],
  "read_first": ["docs/TECHNICAL_SPEC.md section X"],
  "invariant_ids": ["INV-..."],
  "gate_ids": ["GATE-..."],
  "commands": ["exact rtk-prefixed command"],
  "expected_artifacts": [".agent-foreman/<campaign>/artifacts/..."],
  "stop_conditions": ["stop when an unowned path is required"],
  "allowed_statuses": ["implemented", "blocked"]
}
```

### 10.3 Blocked record

```json
{
  "status": "blocked",
  "blocked_from": "in_progress",
  "invariant_id": "INV-001",
  "gate_id": "GATE-001",
  "location": "path/file.py:symbol",
  "actual": "exact observation or exit code",
  "expected": "exact observable result",
  "evidence_artifact": ".agent-foreman/<campaign>/artifacts/gate-001.txt",
  "next_action": "one permitted bounded action"
}
```

### 10.4 Worker handoff

```json
{
  "schema_name": "agent-foreman/handoff",
  "schema_version": "1.0",
  "profile": "full",
  "plan_id": "REPONPC-<CAMPAIGN>",
  "package_id": "PKG-WORKER-<LEAF>",
  "status": "implemented",
  "requested_selector": null,
  "resolved_model_id": null,
  "model_verification": "unavailable",
  "reasoning_effort": "unavailable",
  "changed_paths": ["exact/production.py", "exact/test.py"],
  "diff_artifact": ".agent-foreman/<campaign>/artifacts/pkg.diff",
  "test_artifacts": [".agent-foreman/<campaign>/artifacts/gate.txt"],
  "gate_results": [
    {"gate_id": "GATE-LEAF", "exit_code": 0, "observed": "exact result"}
  ],
  "summary": "bounded observed work",
  "blocked_record": null
}
```

### 10.5 Main integration record

```json
{
  "schema_name": "agent-foreman/integration",
  "schema_version": "1.0",
  "profile": "full",
  "plan_id": "REPONPC-<CAMPAIGN>",
  "phase_id": "PHASE-X",
  "actor_role": "main",
  "packages": ["PKG-MAIN", "PKG-WORKER"],
  "delta_guard": {"passed": true, "artifact": "exact artifact"},
  "focused_gates": ["GATE-LEAF"],
  "aggregate_gates": ["GATE-INTEGRATION"],
  "deterministic_result": "passed",
  "evaluator_recommendation": "pass",
  "status": "integrated",
  "rework": {"worker_changed_lines": 1, "main_changed_lines_in_worker_scope": 0}
}
```

If the delta is not attributable, `delta_guard.passed` is `false` and the limitation is recorded. Deterministic and evaluator results remain separate.

### 10.6 Evaluator probe and evaluation record

```json
{
  "schema_name": "agent-foreman/evaluation",
  "schema_version": "1.0",
  "profile": "full",
  "plan_id": "REPONPC-<CAMPAIGN>",
  "phase_id": "PHASE-X",
  "context_freshness": "fresh",
  "model_diversity": "same-model-fresh-context",
  "production_access": "read-only",
  "new_probes": [
    {
      "probe_id": "PROBE-001",
      "invariant_id": "INV-001",
      "setup": "exact setup",
      "fault_injection": "smallest failing input",
      "production_trigger": "real entrypoint",
      "oracle": "exact observation",
      "anti_oracle": "what does not count",
      "command": "exact rtk-prefixed command",
      "artifact_path": ".agent-foreman/<campaign>/evaluation/artifacts/probe.txt",
      "exit_code": 0
    }
  ],
  "recommendation": "pass",
  "deterministic_result": "passed",
  "findings": []
}
```

### 10.7 Final milestone report

```text
Outcome:
Delivery Phase / Implementation Milestone:
Files changed:
FR/NFR/AC/ADR addressed:
Checks run (command -> pass/fail/not-run, artifact):
Security/privacy/accessibility/benchmark/browser evidence:
Delta-guard result and limitations:
Remaining carry-forward work:
Risks and assumptions:
Owner decisions required:
```

## 11. Definition of ready and done

A worker package is ready only when the full plan is validated/frozen, contracts and exact paths are frozen, capability/access is known, gates and counterexamples exist, and authorization is recorded.

A worker package is done only when its owned delta and focused gates are accepted by Main. This means `implemented`, not integrated or verified.

A phase is done only when Main integrates the real seams, all blocking aggregate/security gates pass, fresh falsification probes pass, documents/examples match, and the phase report preserves every limitation.

RepoNPC v1 is done only when Phase 5 demonstrates AC-001 through AC-037 or the owner explicitly changes the governing requirements first.

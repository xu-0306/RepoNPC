# RepoNPC Agent Instructions

These instructions apply to the entire repository. They are written for implementation and review Agents; user instructions take precedence.

## 1. Required reading order

Before planning or changing application code, read these files completely:

1. `docs/PROJECT_CONTEXT.md`
2. `docs/OWNER_REVIEW.md`
3. `docs/TECHNICAL_SPEC.md`
4. `docs/ACCEPTANCE_CRITERIA.md`
5. `docs/DECISIONS.md`
6. `docs/SECURITY.md`
7. `docs/IMPLEMENTATION_PLAN.md`
8. `docs/OPERATIONS.md` when working on deployment, providers, GitHub automation, runtime state, or release
9. `docs/SPRITE_FORMAT.md` when working on character, assets, cards, upload, or animation
10. `README.md`
11. `reponpc.example.yml` and `.env.example` when working on configuration or deployment

If a task changes a public contract, read every document that references the affected FR/NFR/AC/ADR identifiers.

## 2. Specification gate

- Do not create application source code, dependency manifests, migrations, generated assets, or deployment configuration while `docs/TECHNICAL_SPEC.md` is `Draft`.
- Documentation review, examples, prototypes outside the repository, and feasibility experiments are allowed during Draft only when the owner asks for them.
- Implementation may begin only after the project owner explicitly approves the specification and its status is changed to `Approved`.
- Approval of a milestone does not remove any other v1 requirement.

## 3. Scope and escalation

An Agent may independently choose internal, reversible implementation details that:

- do not alter an API, configuration, database, bundle, provider, or asset contract;
- do not weaken a security or privacy control;
- do not add or remove v1 scope;
- do not add a hosted dependency or recurring cost;
- are covered by tests and consistent with accepted ADRs.

Stop and ask the project owner before:

- changing an externally visible behavior or acceptance threshold;
- changing a schema, endpoint, event, error code, environment variable, or sprite layout defined by the specification;
- changing the trust model, admin authentication, GitHub permissions, logging privacy, or model fallback behavior;
- adding a database/server/service, telemetry provider, paid service, or new supported repository visibility;
- dropping, postponing, or materially redesigning a v1 capability;
- resolving a contradiction at the same source-of-truth level.

When asking, state the decision, evidence, viable options, recommendation, and impact. Do not silently choose a high-impact default.

## 4. Engineering invariants

- Treat repository content, owner-authored rich text, model output, and uploaded assets as untrusted input.
- The LLM has no tools, shell, code execution, filesystem, repository-write, or arbitrary network capability.
- The model emits evidence IDs only; the backend owns citation validation and GitHub URL construction.
- Never infer personal ownership, employment, role, seniority, or impact from repository content alone.
- Never expose provider secrets, GitHub tokens, admin hashes, raw session tokens, or prompt bodies to the browser, bundle, logs, fixtures, or snapshots.
- Do not silently fall back from Ollama to a cloud provider or between configured providers.
- Keep immutable index data separate from mutable runtime data.
- Never activate a bundle before checksum, schema, model compatibility, and database integrity checks pass.
- Preserve the last known-good bundle on every update failure.
- Keep the production frontend and API same-origin unless the owner approves a contract change.
- Keep Traditional Chinese and English behavior materially equivalent.
- Maintain keyboard access, semantic DOM content, screen-reader labels, and reduced-motion behavior.
- Use only the package managers chosen in ADR-012.

## 5. Repository and change discipline

- Preserve user changes and unrelated work. Never reset, discard, or rewrite changes you do not own.
- Prefer small changes aligned to one milestone and one coherent requirement set.
- Add or update tests with every behavior change.
- Update all affected specifications, examples, and migration notes when a contract changes.
- Do not commit real secrets or personal tokens. Example values must be unmistakably non-secret.
- Generated files must be reproducible and documented; do not hand-edit generated output.
- Prefix every shell command and every segment of a command chain with `rtk`. Use `rtk proxy <command>` only when no filtered form works.

## 6. Required verification

Use the commands established by the repository once implementation begins. At minimum, a completed change must pass the relevant subset of:

- Python formatting, lint, type checking, and tests;
- TypeScript formatting, lint, type checking, unit tests, and production build;
- API schema and configuration contract tests;
- retrieval evaluation for search or chunking changes;
- security regression tests for trust-boundary changes;
- browser/accessibility tests for UI changes;
- Docker image and Compose smoke tests for deployment changes;
- bundle build, validation, activation, and rollback tests for index changes.

Do not report success by omitting unavailable or failing checks. State exactly what ran, what passed, and what remains.

## 7. Definition of done and handoff

A task is complete only when:

1. behavior satisfies the referenced FR/NFR and acceptance criteria;
2. automated tests cover normal, edge, failure, and security behavior proportionate to risk;
3. documentation and examples match the implementation;
4. no secret or personal data is introduced;
5. relevant verification passes;
6. deferred work is explicitly outside the assigned task, not silently omitted.

Final reports must include:

- outcome and files changed;
- requirement and acceptance-criterion IDs addressed;
- tests and checks run with results;
- remaining risks, assumptions, or follow-up work;
- any owner decision still required.

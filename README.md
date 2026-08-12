# RepoNPC

> Meet the NPC who knows your code.

RepoNPC is an open-source, self-hosted AI developer portfolio. It turns owner-selected public GitHub repositories and explicit owner claims into a searchable knowledge base, presents them through a pixel-art RPG character, and answers visitor questions with verifiable links to exact GitHub commits and line ranges.

中文定位：讓懂你程式碼的 NPC，替作品說話。

## Project status

RepoNPC completed initial specification approval on 2026-08-10. Phase 1 and the main Phase 2 retrieval/bundle foundation are implemented; an owner-approved Phase 2 closure campaign now addresses the production index CLI/local adapter, bilingual bundle profile, repository metadata producer, and isolated formal benchmark while retaining the complete v1 scope.

| Item | State |
| --- | --- |
| Product scope | Complete v1 defined; not a reduced MVP |
| Technical specification | Approved 0.1.1; Phase 2 closure amendment approved 2026-08-11 |
| Application code | Delivery Phase 2 closure in progress |
| License target | MIT |
| Estimated implementation | 8–12 weeks for one developer |

## What v1 will deliver

- A linked pixel-art NPC card for a GitHub Profile README.
- A full external RPG-style visitor page with idle, walk, listen, think, talk, success, and offline character states.
- Traditional Chinese and English visitor/admin interfaces and materially equivalent answers.
- Owner-curated indexing of public GitHub repositories at exact commits.
- Owner assertions, repository facts, and visibly labeled model inferences.
- SQLite FTS5 lexical search, multilingual embeddings, and RRF hybrid retrieval.
- Tree-sitter parsing for Python, JavaScript/TypeScript, Go, and Rust, plus bounded text fallback.
- Answers backed by server-validated immutable GitHub citations and safe abstention when evidence is insufficient.
- Explicit OpenAI-compatible and Ollama chat/embedding providers with no silent cloud fallback.
- A single-owner admin UI for configuration, character preview, README snippets, and conflict-safe GitHub writeback.
- Built-in character customization plus a documented custom sprite-sheet format.
- Immutable GitHub Actions index bundles, atomic activation, pin/rollback, and last-known-good recovery.
- Docker Compose self-hosting, security/cost controls, accessibility, tests, evaluation, and operations guidance.

## Product shape

```mermaid
flowchart LR
    A["GitHub Profile README<br/>Script-free NPC card"] -->|"Click"| B["RepoNPC visitor site<br/>RPG portfolio + chat"]
    B --> C["FastAPI application"]
    C --> D["Hybrid evidence retrieval<br/>FTS5 + embeddings + RRF"]
    D --> E["Immutable index bundle"]
    F["Selected public repositories<br/>+ reponpc.yml"] --> G["GitHub Actions indexer"]
    G --> E
    C --> H["Configured model<br/>OpenAI-compatible or Ollama"]
    C --> I["Validated answer<br/>+ immutable citations"]
```

The README and application are separate by design: GitHub Profile READMEs can render links and images but cannot run the JavaScript required for interactive chat. The SVG/GIF is therefore a safe visual entry point; the external HTTPS site provides the actual application.

## Trust model

RepoNPC never treats repository presence as proof of personal contribution:

- `OWNER_ASSERTION` — a role, achievement, responsibility, or context explicitly written by the portfolio owner;
- `REPOSITORY_FACT` — code, documentation, configuration, dependency, or metadata observable at an indexed commit;
- `MODEL_INFERENCE` — a conclusion that must name supporting assertion/fact evidence and remain labeled as inference.

Repository/configuration text and model output are untrusted. The model has no tools, shell, code execution, filesystem, repository-write, or arbitrary network access. It emits evidence IDs only; the backend validates those IDs and constructs GitHub links.

## Documentation for implementation Agents

Read in this order:

1. [Project context](docs/PROJECT_CONTEXT.md) — problem, users, journeys, goals, boundaries, vocabulary.
2. [Owner review](docs/OWNER_REVIEW.md) — the accepted implementation-level defaults and approval record.
3. [Technical specification](docs/TECHNICAL_SPEC.md) — normative requirements, contracts, schemas, security, and edge cases.
4. [Acceptance criteria](docs/ACCEPTANCE_CRITERIA.md) — Given/When/Then evidence required for every FR/NFR.
5. [Architecture decisions](docs/DECISIONS.md) — proposed decisions and their consequences.
6. [Security model](docs/SECURITY.md) — trust boundaries, threats, secrets, browser/admin/bundle controls.
7. [Implementation plan](docs/IMPLEMENTATION_PLAN.md) — dependency order, milestones, deliverables, and gates.
8. [Delivery phases](docs/DELIVERY_PHASES.md) — the owner-approved MVP-first sequencing of the complete v1.
9. [Subagent execution playbook](docs/SUBAGENT_EXECUTION_PLAYBOOK.md) — Main/worker ownership, per-phase work packages, gates, handoffs, and evaluator evidence.
10. [Current P2-00 handoff](docs/P2_FOUNDATION_HANDOFF.md) — live takeover steps, evidence tracker, and reviewer checkpoints for foundation closure.
11. [Operations](docs/OPERATIONS.md) and [sprite format](docs/SPRITE_FORMAT.md) — deployment/recovery and the canonical character asset contract.
12. [Agent instructions](AGENTS.md) — scope, escalation, invariants, verification, and reporting rules.
13. [`reponpc.example.yml`](reponpc.example.yml) and [`.env.example`](.env.example) — public configuration and deployment boundary.

The operations and sprite documents begin as pre-implementation contracts and must be finalized with verified commands/assets before release.

If these documents conflict, follow the source-of-truth order in `PROJECT_CONTEXT.md`. Application code must remain within the approved specification and its owner-approved changes.

## Planned stack

- Web: React, Vite, TypeScript, pnpm
- Application/indexer: FastAPI, Python, uv
- Search: SQLite FTS5, NumPy vector ranking, RRF
- Parsing: Tree-sitter
- Models: optional indexer-only local sentence-transformers adapter in Phase 2; OpenAI-compatible/Ollama and runtime query-provider integration in Phase 3
- Automation/artifacts: GitHub Actions, GitHub Releases, stable index manifest
- Deployment: one application image through Docker Compose
- Runtime state: persistent SQLite separate from immutable index SQLite

## Configuration model

Public, version-controlled portfolio content lives in `reponpc.yml`: profile, localized copy, selected repositories, owner claims, character, card, and retrieval settings. Deployment secrets and private provider details stay in environment variables or mounted secret files. The admin UI writes only `reponpc.yml` and validated PNG files below `assets/character/` using GitHub blob-SHA conflict protection.

## v1 boundaries

One owner, selected public repositories, and one NPC per deployment. Private repository indexing, multi-tenant SaaS, billing, GitHub OAuth onboarding, autonomous code tools, multiple NPCs, and a navigable RPG game are intentionally outside v1.

## Name

**RepoNPC** combines repository knowledge with the RPG character representing the developer:

> Your repositories are the world. Your work is the lore. Your NPC knows the evidence.

# RepoNPC v1 Delivery Phases

**Status:** Approved sequencing plan  
**Approved:** 2026-08-10  
**Scope rule:** These phases sequence the complete v1. The MVP phase is not a reduced product scope and does not waive any FR, NFR, AC, ADR, security, accessibility, bilingual, or operational requirement.

## Phase 1 — Core MVP vertical slice

Deliver the first runnable, contract-aligned slice:

- locked Python workspace and CI-ready test configuration;
- strict `reponpc.yml` validation with bilingual parity and secret-boundary checks;
- evidence classes, stable evidence IDs, bounded fallback chunking, and deterministic RRF;
- FastAPI lifecycle plus `/healthz`, `/readyz`, public status/profile setup behavior, request IDs, and stable safe errors;
- a small committed fixture path for deterministic integration tests only;
- focused unit, contract, and API integration tests.

This phase proves the foundation and the setup/degraded public boundary. It is not a v1 release and must not claim the complete visitor chat journey until later phases pass their gates.

## Phase 2 — Immutable evidence and retrieval

- GitHub source/ref resolution and mandatory exclusions;
- Tree-sitter adapters and text fallback;
- SQLite FTS5 plus declared external embedding-profile contract and NumPy vector search. The local sentence-transformers adapter is isolated to reproducibility benchmarks and is not a production default;
- executable `reponpc config validate` and `reponpc index build|publish|publish-manifest` commands while no arguments/`serve` retain application startup;
- line-addressable root manifest evidence classified as `repository_metadata` without conflating owner assertions;
- one verified bilingual `public/profile.json` producer consumed by the bundle verifier and locale-selecting public route;
- immutable bundle build, validation, activation, retention, pinning, and rollback;
- retrieval, reproducibility, bilingual parity, bundle-security, publication-last, and Docker-isolated formal benchmark gates with host-only oracle/scoring.

## Phase 3 — Grounded chat and visitor experience

- OpenAI-compatible, vLLM, and Ollama chat/embedding adapters plus runtime external-profile health/readiness integration;
- buffered answer validation, owner-assertion policy, immutable citations, abstention, and exact SSE contract;
- public limits, safe logging, model/index status, and no silent provider fallback;
- responsive bilingual visitor UI, suggested questions, citations, keyboard/accessibility, and character lifecycle states.

## Phase 4 — Owner administration, assets, and publication

- single-admin Argon2id sessions, CSRF, backoff, rotation, and revocation;
- configuration/character validation and side-effect-free previews;
- allowlisted GitHub writeback with blob-SHA conflicts;
- canonical sprite composition and custom upload validation;
- sanitized SVG/GIF/PNG cards, README snippets, and GitHub Actions publication.

The owner-approved 0.1.4 guided-onboarding extension adds FR-025 through FR-028 and AC-038 through AC-040 to the complete v1 scope. Its original implementation and focused suite have local evidence, but the later recoverable-capability review found mandatory-analysis and destructive-reset regressions. The 10.4 no-dead-end correction is therefore a Phase 5 blocker, not a completed release claim.

The owner-approved 0.1.6/0.1.7 GitHub extension adds FR-029 through FR-033 and AC-041 through AC-046. Milestones A–C were implemented and locally verified on 2026-08-16. Milestones D–E are implemented and their local automated suite passed on 2026-08-16: GraphQL/exact-SHA archive preflight, durable batches, safe event replay, caching, and fair provider permits are present. Milestone F remains in progress: an isolated current-source browser smoke passed, but real GitHub/OAuth, live-provider, full browser/accessibility, Docker/Compose, and clean-host evidence is still required.

The owner-approved 0.1.8 amendment adds FR-034 and updates AC-043 so unconfigured OAuth entry points open a safe setup guide rather than remaining disabled. The shared GitHub button/icon, guide API, bilingual accessibility behavior, and Windows launcher mapping work must be verified before the release-hardening gate.

The owner-approved 0.1.9 amendment adds FR-035 and FR-036 plus AC-047 through AC-050. It requires external embedding profile CRUD with one active profile, a provider-aware Ollama model center (vLLM/generic connect-only), deployment-aware password/private-admin access, local-password-first GitHub binding/recovery, and a bounded operations CLI. The local adapter, arbitrary model downloader, GitHub-only owner path, and public admin port remain outside the supported deployment path.

## Phase 5 — Release hardening

- full AC-001 through AC-050 evidence;
- security, evaluation, browser, accessibility, Compose, upgrade, recovery, and rollback suites;
- verified operations commands, clean-host deployment, provider compatibility, licensing, notices, and release artifacts.
- every P0 item in `SPEC_AND_ENGINEERING_REMEDIATION_PLAN.md` closed with deterministic evidence; every P1 release blocker either closed or explicitly deferred by the owner; and no UXD/ENGD decision silently resolved by implementation.

## Phase completion rule

Every phase reports exact files, requirement IDs, commands, pass/fail/not-run results, risks, and owner decisions. Only Phase 5 may declare RepoNPC v1 complete.

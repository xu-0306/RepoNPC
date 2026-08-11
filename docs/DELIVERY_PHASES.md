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
- SQLite FTS5 plus declared embedding contract and NumPy vector search;
- immutable bundle build, validation, activation, retention, pinning, and rollback;
- retrieval, reproducibility, bilingual parity, and bundle-security gates.

## Phase 3 — Grounded chat and visitor experience

- OpenAI-compatible, Ollama, and local embedding adapters;
- buffered answer validation, owner-assertion policy, immutable citations, abstention, and exact SSE contract;
- public limits, safe logging, model/index status, and no silent provider fallback;
- responsive bilingual visitor UI, suggested questions, citations, keyboard/accessibility, and character lifecycle states.

## Phase 4 — Owner administration, assets, and publication

- single-admin Argon2id sessions, CSRF, backoff, rotation, and revocation;
- configuration/character validation and side-effect-free previews;
- allowlisted GitHub writeback with blob-SHA conflicts;
- canonical sprite composition and custom upload validation;
- sanitized SVG/GIF/PNG cards, README snippets, and GitHub Actions publication.

## Phase 5 — Release hardening

- full AC-001 through AC-037 evidence;
- security, evaluation, browser, accessibility, Compose, upgrade, recovery, and rollback suites;
- verified operations commands, clean-host deployment, provider compatibility, licensing, notices, and release artifacts.

## Phase completion rule

Every phase reports exact files, requirement IDs, commands, pass/fail/not-run results, risks, and owner decisions. Only Phase 5 may declare RepoNPC v1 complete.

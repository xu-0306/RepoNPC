---
summary: "RepoNPC Delivery Phase 4 owner administration, character/card assets, GitHub writeback, and publication integration are verified; includes canonical evidence, attribution limitation, and Phase 5 starting point."
created: 2026-08-13
tags: [reponpc, phase-4, verified, admin, assets, cards, github, publication, agent-foreman]
related: [D:/RepoNPC/.agent-foreman/phase4-owner-assets-publication/plan.json, D:/RepoNPC/docs/P4_OWNER_ASSETS_PUBLICATION_HANDOFF.md, D:/RepoNPC/docs/OPERATIONS.md]
---

# RepoNPC Phase 4 verified handoff

## Authoritative status

- Repository baseline: `1b3d823a005cc8a8878b210b6d90656af47d1f18`; the Phase 3 and Phase 4 closure deltas were preserved and prepared for one cumulative closure commit.
- Canonical campaign: `.agent-foreman/phase4-owner-assets-publication/plan.json`; status `verified`, completed by Main.
- Main integration: `.agent-foreman/phase4-owner-assets-publication/integrations/integration-phase4.json`.
- Fresh evaluation: `.agent-foreman/phase4-owner-assets-publication/evaluation/evaluation-phase4.json`.
- Human-readable handoff: `docs/P4_OWNER_ASSETS_PUBLICATION_HANDOFF.md`.
- RepoNPC v1 is not complete. Delivery Phase 5 remains the release-hardening boundary.

## Implemented Phase 4 behavior

- Argon2id single-admin authentication with timing-resistant unknown-user verification, durable hashed session/CSRF rows, backoff, idle/absolute expiry, atomic rotation, logout, and logout-all epoch revocation.
- Same-origin Origin/Referer plus CSRF enforcement, secure `__Host-reponpc_session`, and in-memory browser CSRF/draft state cleared on logout.
- Config read/validate/preview/save; exact repository/branch/workflow/path GitHub policy; blob-SHA conflict protection; bounded no-redirect production transport; safe audit.
- Multipart character validation/writeback with strict PNG framing, 2 MiB and `128x224` limits, APNG/polyglot/decode rejection, and deterministic metadata-free RGBA canonicalization.
- Deterministic built-in sprite composer for all 28 frames and a shared canonical validator across preview, GitHub, card, and bundle consumers.
- Deterministic `600x180` SVG/GIF/PNG card variants, safe text/URL serialization, cache validators, and copy-ready README snippets.
- Bundled `NotoSansCJKtc-Regular.otf`, OFL, and font source notes; wheel contains the font and license.
- Index pipeline automatically generates character/card public assets and preserves immutable publication plus stable-manifest-last behavior.
- Code-split bilingual AdminPage/AdminWorkspace with locale-exact previews and valid-only/conflict-safe saving.

## Final evidence snapshot

- Aggregate Python: `461 passed, 3 skipped`, one upstream Starlette/httpx TestClient deprecation warning.
- Focused gates: admin auth 8 passed; GitHub/writeback 7; assets/producer-consumer 18; card 5; publication/card/bundle 23.
- Fresh evaluation: Python 7 passed plus AdminWorkspace 1 passed. Probes cover CSRF/origin, stale SHA/no overwrite, PNG polyglot/no mutation, composer-to-validator, parsed SVG active-content safety, publication failures/no stable mutation, admin locale/conflict/logout safety, and secret canaries.
- Web: formatting, ESLint with zero errors and five existing Fast Refresh warnings, TypeScript, 13 tests, and production build passed; a separate AdminPage chunk was emitted.
- Ruff check, Ruff format (140 files), mypy (54 source files), wheel/sdist packaging, font/OFL inclusion, and `git diff --check` passed.
- Fresh evaluator used Luna in a fresh context, so model diversity is `same-model-fresh-context`, not cross-family.

## Delegation and fallback outcome

- Luna max implemented the sprite composer leaf and the isolated AdminWorkspace presentation leaf.
- Main reviewed and repaired presentation semantics within the frozen leaf scope, then all focused, consumer, aggregate, and fresh probes passed.
- No reproducible Luna production quality defect remained, so the owner-authorized Terra fallback was not invoked.
- Evaluator execution had two timeouts and two false-positive assertions (raw escaped tokens treated as active SVG, and raw conflict SHA assumed visible). Main corrected only evaluator-owned probes; production did not change for those findings.

## Immutable attribution limitation

`GATE-DELTA` remains `failed` and `attribution-limited`. Main and workers shared a concurrently changing worktree, so fingerprints included Main dependencies, caches, pytest temporaries, and campaign writes. Never rewrite it as passed or claim that it proves Luna touched prohibited paths.

Product acceptance instead uses exact two-file leaf diffs, Main review, focused tests, and real producer-consumer/system gates. The canonical plan marks this noncritical gate nonblocking while preserving the failure.

## Requirements and remaining work

Phase 4 addresses FR-015 through FR-021 and FR-024 and the implemented portions of AC-020, AC-021, AC-023 through AC-032, AC-034, and AC-035.

AC-022 remains manual Phase 5 release evidence: commit generated snippets to a test GitHub Profile and verify GitHub's image proxy, static first frame, fallbacks, light/dark preferences, and click target in current Chrome, Firefox, and Safari. Phase 5 must also run current Docker/Compose, clean-host, final browser/accessibility, dependency/security, and release-documentation checks before declaring v1 complete.

# Phase 4 Owner, Assets, and Publication Handoff

**Status:** Delivery Phase 4 verified on 2026-08-13
**Baseline:** `1b3d823a005cc8a8878b210b6d90656af47d1f18` plus the preserved Phase 3 closure delta
**Canonical campaign:** `.agent-foreman/phase4-owner-assets-publication/`

## Outcome

Phase 4 implements the single-owner administration, canonical character assets, deterministic README card outputs, conflict-safe GitHub writeback, and generated-asset publication boundary. It does not complete RepoNPC v1; Delivery Phase 5 still owns final release hardening and manual release evidence.

Implemented behavior includes:

- Argon2id password verification, enumeration-resistant failures and backoff, durable hashed sessions/CSRF, idle and absolute expiry, atomic rotation, logout, and logout-all epoch revocation;
- same-origin Origin/Referer and CSRF enforcement with a secure `__Host-reponpc_session` cookie;
- validation and preview without mutation, exact-path GitHub writes with mandatory blob-SHA conflict protection, safe audits, bounded no-redirect transport, and allowlisted workflow dispatch;
- strict PNG framing, size, dimension, APNG/polyglot and decode checks followed by metadata-free canonical RGBA re-encoding;
- deterministic built-in `128x224` sprite composition and the same validator/bytes across preview, writeback, card, and bundle consumers;
- twelve deterministic `600x180` SVG/GIF/PNG card variants with safe text/URL serialization, cache validators, and copy-ready snippets;
- a code-split bilingual admin route whose CSRF token and drafts remain in memory and are cleared on logout;
- automatic character/card generation during index builds, with immutable publication and stable-manifest mutation still ordered last.

The raster renderer bundles `NotoSansCJKtc-Regular.otf` and its SIL Open Font License under `src/reponpc/cards/fonts/`. The built wheel includes both the font and license.

## Requirements covered

The implemented and automated evidence covers FR-015 through FR-021 and FR-024. It covers the Phase 4 portions of AC-020, AC-021, AC-023 through AC-032, AC-034, and AC-035. Existing Phase 2/3 gates continue to own unaffected bundle, visitor, provider, and chat behavior.

AC-022 remains a manual release check: commit generated snippets to a test GitHub Profile and verify the GitHub image proxy, static first frame, fallbacks, light/dark behavior, and click target in current Chrome, Firefox, and Safari. This evidence belongs in Phase 5 and must not be inferred from local renderer tests.

## Verification snapshot

- Python aggregate: `461 passed, 3 skipped`; the only warning is the upstream Starlette/httpx TestClient deprecation.
- Python quality: Ruff check and format passed; mypy passed for 54 source files.
- Focused publication/card/bundle matrix: `23 passed`.
- Web aggregate: Prettier, ESLint, TypeScript, 13 tests, and production build passed. ESLint reports five pre-existing Fast Refresh warnings and no errors. The build emits a separate admin chunk.
- Packaging: wheel and sdist build passed; the wheel contains the Noto font and OFL.
- Whitespace: `git diff --check` passed.
- Fresh evaluator: see `evaluation/evaluation-phase4.json` and its probe output in the canonical campaign.

The two Luna max leaves passed focused tests and Main consumer review. No deterministic quality failure justified a Terra fallback.

## Attribution limitation

`GATE-DELTA` is intentionally recorded as failed and attribution-limited. Main and both workers shared one concurrently changing worktree, so the dispatch/handoff fingerprint contains Main dependencies, caches, test temporaries, and campaign artifacts outside the worker package. That result does not prove Luna edited those paths, and it must never be rewritten as passed.

Worker acceptance instead relies on the actual two-file diffs, exact owned-path review, focused gates, Main review, and real consumer gates. This limitation is noncritical to product correctness but remains part of the immutable governance record.

## Phase 5 starting point

Begin Phase 5 from the canonical Phase 4 campaign and this handoff. At minimum, rerun the current Docker/Compose and clean-host gates, execute AC-022 against a real GitHub Profile, complete remaining browser/accessibility/release checks, validate documentation against the release candidate, and retain all prior failed or attribution-limited evidence without rewriting history.

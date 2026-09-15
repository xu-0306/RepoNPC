# RepoNPC GitHub push handoff — 2026-09-16

Status: current local verification completed. After the owner explicitly approved the exact GitHub destination and full two-commit payload on 2026-09-16, `origin/main` accepted both commits and was independently read back at `8af72e66395d7c563e662b4732bbc0277dbc3a78`. This tracked note carries the portable project-memory checkpoint; the detailed agent memory and `PROJECT_CONTEXT.md` remain intentionally local and gitignored.

## Scope

- Owner-approved Technical Specification 0.3.0 / ADR-034–037: independent analysis output budget and truncation diagnosis; same-service/same-origin path-only connection updates and operation-scoped accessible errors; one-call Chat probe with 10-second baseline plus 10-second grace; configurable analysis time, retry and output budgets with safety ceilings.
- Requirements and acceptance criteria touched: FR-027/033/038–041, NFR-003/011/014, AC-039/045/054–057/060/061. The AC-039 deadline wording is aligned with AC-061 rather than its retired fixed 120-second value.
- The local runtime migration 25 and last-known-good data preservation were checked on 2026-09-14. This does not establish a clean-host or live-provider release pass.

## Evidence boundary

The prior 2026-09-14 local verification recorded Python 944 passed / 2 skipped (non-Docker), Docker Compose smoke 1 passed, frontend 143 passed, and relevant formatting, lint, type-checking, build, audit and runtime-integrity checks. Re-run evidence for this push is recorded below only after completion. AC-061's controlled slow-provider browser run remains open; buffered-provider behavior must not be presented as token-streaming evidence. The earlier gateway analysis failure's raw response was not retained, so its exact cause remains unproven.

## Current publication verification

On 2026-09-16, `.venv\\Scripts\\pytest.exe -q --ignore=tests/smoke/test_container.py` passed with **944 passed / 2 skipped** and two non-fatal Starlette/cache warnings. `.venv\\Scripts\\ruff.exe format --check .`, `.venv\\Scripts\\ruff.exe check .`, and `.venv\\Scripts\\mypy.exe src` passed (190 formatted files; 69 typed source files). `pnpm run web:check` passed formatting, lint (12 existing Fast Refresh warnings, zero errors), typecheck, **143 tests**, and production build. The container smoke run was not repeated during this publication task; its 2026-09-14 result remains dated evidence.

The initial `git push origin main` to `https://github.com/xu-0306/RepoNPC.git` was rejected twice by the external-publication review. Read-only checks confirmed that origin matched the public repository and README, changed paths contained no runtime data, and the only `ghp_`-shaped string was a synthetic secret-detection test canary. The owner then explicitly approved this destination and the full `c97ef91` plus `8af72e6` payload. A fresh fetch showed no remote-ahead commit; the authorized push advanced `main` from `30bec31` to `8af72e6`, and `git ls-remote origin refs/heads/main` returned `8af72e66395d7c563e662b4732bbc0277dbc3a78`. This is publication evidence, not live-provider or full release acceptance.

Security: no real API key, stored provider URL, raw model response, prompt, runtime database or backup belongs in this tracked handoff. The unrelated `%SystemDrive%/` cache files were excluded from staging.

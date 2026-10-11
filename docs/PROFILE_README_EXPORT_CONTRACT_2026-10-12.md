# GitHub profile README export

Status: Owner-approved 2026-10-12 (OR-033 / ADR-059, Approved Specification 0.4.11).
Requirements: FR-016/024, FR-022, NFR-001/002/003/009; AC-028 and preservation
of AC-022/023/034. This is local implementation scope, not public-release evidence.

## Delivery and source

The final sharing primary action is **下載 README.md / Download README.md**.
The file contains the applied, confirmed public name/headline/bio, optional public
location/profile links, enabled project links/summary/role/tags/demo links, NPC
card and **與我的 NPC 對話 / Chat with my NPC** entry. The visitor link opens the
existing verified RepoNPC Pages site; GitHub README cannot execute chat.
No generated personal claim, unconfirmed suggestion or unapplied draft enters
the file. Empty optional sections do not invent content.

The adjacent **預覽 README 內容 / Preview README content** action displays the
exact complete UTF-8 file in a keyboard-accessible readonly textarea. It is a
content preview, not a claim about GitHub rendering. Preview state is memory-only
and bound to locale, verified Pages URL/digest and active bundle; a changed key
hides it. Download always rechecks the source, never trusts a cached preview.
Busy actions retain focus and use the existing duplicate-submission gate.

Both languages explicitly explain that README.md must be at the root of a
**public repository with the same name as the GitHub account** to appear on the
profile. The owner uploads it manually. Existing README content must be reviewed
and preserved; the existing copy-card-block and manual image-upload paths remain
available. No GitHub file, branch, repository or hosting service is created or
overwritten. Default-branch checks continue to use actual metadata, never `main`.

## Private download contract

`GET /api/admin/sharing/readme?locale=zh-TW|en` (default `zh-TW`) retains the
existing private Host/Origin and owner-session checks. It returns a readonly
`text/markdown; charset=utf-8` attachment named exactly `README.md`, with
`Cache-Control: no-store` and `X-Content-Type-Options: nosniff`. It performs no
model call, GitHub write, activation, database mutation or receipt update; as a
readonly GET it requires no mutation CSRF token.

The service rebuilds the existing deterministic Pages public snapshot and
requires its manifest digest to equal the saved successful verification digest.
The image URL is the exact verified Pages base path plus the existing exported
`card-light-{locale}.gif`, so uploading README alone needs no relative image.
The existing credential-free Pages transport checks this fixed image URL,
HTTP 200, `image/gif`, exact expected bytes, the existing public DNS/TLS/redirect
boundary, the 20-second deadline and a response cap equal to the expected GIF
size (within the existing transport cap). User text cannot select a fetch URL.
The receipt and rebuilt snapshot are checked again after the remote read.

Missing verification or changed local snapshot/receipt uses `SHARING_CONFLICT`;
missing/wrong remote image uses `SHARING_VERIFICATION_FAILED`; transport failure
uses `SHARING_VERIFICATION_UNAVAILABLE`. Other existing bounded export failure
codes remain. No broken README attachment or false download success is produced.
The UI explains how to return to section 3, upload the current Pages site and
verify again, with the existing manual card/copy path still available.

Public text is HTML/Markdown-escaped, link labels are single-line text and URL
destinations are percent-encoded. Rendering uses the existing validated public
profile schema and fixed application-owned card/visitor paths. The final escaped
UTF-8 document is limited to GitHub's 500 KiB profile display boundary; overflow
uses `SHARING_EXPORT_TOO_LARGE`, with guidance to shorten public content,
apply it and export/upload/verify again. No truncation loses the NPC entry.

GitHub documents the [same-name public repository and root README requirements](https://docs.github.com/en/account-and-profile/how-tos/profile-customization/managing-your-profile-readme)
and [500 KiB rendering limit](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes).

## Verification boundary

Regression tests cover both locales, root/project Pages paths, unapplied draft
isolation, text/URL injection, exact attachment bytes/headers, oversize escaping,
private access, unverified/stale/racing source, wrong/unavailable GIF, readonly
state and browser download/preview wiring including duplicate clicks and focus.
Remote resources in automated checks are synthetic. Real GitHub/Profile image
proxy rendering, real Pages/Gateway reachability and native browser download
completion require separate external/manual evidence.

## Local verification record (2026-10-12)

- `uv run --locked python -m ruff format --check` and `ruff check` on the four
  changed Python files: passed. `uv run --locked python -m mypy src/reponpc`:
  passed, 107 source files.
- `uv run --locked python -m pytest tests/security/test_profile_readme.py
  tests/security/test_a5_pages_api_review.py tests/security/test_pages_verification.py
  tests/security/test_a5_pages_transport_review.py -q
  --basetemp=.test-tmp/readme-20261012-final`: 49 passed; one upstream
  Starlette/httpx deprecation warning.
- `pnpm --dir apps/web format`, `lint`, `typecheck`, `test`, `build`: passed;
  full frontend suite 550 tests / 47 files. Lint reports 19 existing
  React-refresh warnings and zero errors. Build retains the existing classic
  `scene-mode.js` bundling warning.
- External fixture suites via `pnpm --dir apps/web exec vitest run --root ../..
  --config apps/web/vite.config.ts tests/web/GitHubShareGuide.test.tsx
  tests/web/LocalPublishingWorkspace.test.tsx`: 13 passed / 2 files.
- `uv run --locked python scripts/build_scene_assets.py --check`: passed.
  Visitor source guard: 15 runtime files passed; its self-test: 14 checks passed.
  `git diff --check`: passed (existing Windows line-ending notices only).

Commands use the already cached pinned pnpm 11.16.0 executable and the locked
uv environment. Sandbox cache/temporary-file restrictions required approved
local verification execution; no network/resource policy was bypassed.
An initial frontend fixture generic-mock failure and obsolete wording assertions
were corrected; the final complete frontend and external suites pass.

The official in-app Browser client file existed, but its import failed with
`EPERM realpath` before any navigation. Browser controls were not bypassed.
Native download completion, actual browser focus, GitHub image-proxy display,
real Pages/Gateway availability and assistive-technology walkthrough remain
unverified. Automated checks use synthetic resources and prove download/preview
content and event wiring, not native-browser or public-publication success.
No real owner runtime, provider, model, GitHub or public deployment was changed;
no commit or push was performed. This record does not close A5/A12 release gates.

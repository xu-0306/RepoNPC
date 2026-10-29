# Isolated UI and event checks

## Admin UX continuation (2026-10-11)

Build the web app, start a fresh disposable `tests.browser.a5_server` on loopback,
and sign in with its public fixture credentials. Wait for the saved fixture to
open the manual Profile step in Traditional Chinese. No real services are needed.
With the existing Playwright CLI session:

```powershell
npx --yes --package @playwright/cli playwright-cli -s=ux-fix-20261011 run-code --filename tests/browser/check-admin-ux.js
```

The script checks language changes without reloading the saved draft, keyboard
model detours, return focus/scroll, progress, sharing order, collapsed optional
content, keyboard service forms, first AI entry and reload. It uses 1024×768 and
390×844 in both languages and saves screenshots under
`output/playwright/ux-fix-20261011/`. It never enters a service URL/key or submits
a model call. Expected 503 responses from unconfigured fixture model-management
routes are not real-provider acceptance. Run against this disposable fixture only;
the test edits its in-browser public profile draft. Stop the host and close the
owned browser session afterward. Results and exclusions are recorded in
`docs/OPTIMIZATION_PLAN_2026-10-11.md`.

## Analysis highlights (updated 2026-10-14; cards 2026-10-07)

`analysis-card-review.tsx` mounts the production guided view and reducer with
synthetic in-memory analysis. Copy it to `apps/web/.analysis-card-review.tsx`
and create `apps/web/.analysis-card-review.html` using the existing fixture HTML
with its module URL set to `/.analysis-card-review.tsx`. Run Vite on an unused
loopback port and open that HTML with the documented Chrome browser runtime.
Import `check-analysis-cards.js` in that runtime and call
`checkAnalysisCards(tab, await chrome.capabilities.get("viewport"))`.
It checks both locales at 375/768/1024/1440px: keyboard expansion of highlight
rows, GitHub source links and `+n`, escaped statements, the partly-missing-source
note, the privacy popover (Escape closes it and returns focus), 44px controls,
overflow and confirmation isolation. Stop the owned Vite process and remove only
the two copied fixture files afterward. The 2026-10-07 results in
`release-evidence/analysis-cards-20261007/RESULT.zh-TW.md` describe the retired
card layout and remain a dated record only.

These fixtures mount production React components and styles. They use synthetic data only. `admin-events-review.tsx` and `visitor-ui-review.tsx` replace **all** fetch requests; unhandled routes never reach a real API. Do not remove that interception or reuse this harness with real credentials.

They intentionally live outside the production app and are not included in its Vitest suite or build. Use the project's documented browser tooling for interactive execution. The recorded matrix is dated evidence, not a test run performed automatically by CI.

## Run a fixture

From the repository root in PowerShell, choose `ui-system`, `admin-events`, `visitor-ui`, `access-theme`, or `endpoint-edit`:

```powershell
$reviewName = 'admin-events'
Copy-Item -LiteralPath "tests/browser/$reviewName-review.tsx" -Destination "apps/web/.$reviewName-review.tsx"
(Get-Content -Raw tests/browser/ui-system-review.html).Replace('/.ui-system-review.tsx', "/.$reviewName-review.tsx") | Set-Content "apps/web/.$reviewName-review.html"
& ./apps/web/node_modules/.bin/vite.ps1 apps/web --host 127.0.0.1 --port 5178 --strictPort
```

Open `http://127.0.0.1:5178/.ui-system-review.html` for the layout fixture. For the admin fixture, open `http://127.0.0.1:5178/.admin-events-review.html#local-launch=SYNTHETIC_FIXTURE_TOKEN`. Its mocked session endpoint authenticates only the isolated page; it grants no access to a real server. Use a fresh navigation with a different `?run=` value between full admin event runs to reset in-memory revision counters. The application may retain a synthetic draft through its normal UI continuity mechanism; the checker accommodates this without reading browser storage.

Once the documented browser runtime provides `tab`, import `check-admin-events.js` from this directory and run `await checkAdminEvents(tab)`. It throws on any failed assertion and returns seven completed checks on success. After editing an imported check script, reload its module in a fresh runtime or import a temporary copy to avoid the runtime's module cache.

## Layout and other events

- `endpoint-edit-review.tsx`: edit Service one and verify zero reads until checking Replace URL. Check its synthetic URL loads and remains editable. Use Read mode failure/delayed and Release URL to exercise manual entry, retry, cancel and switching to Service two before the old response arrives. Only the active service's response may fill the form; API key stays empty. Both languages use the same events. All callbacks and URLs are synthetic.

- `access-theme-review.tsx`: nine access states, both languages, 100%/200% root text size and 320/375/768/1440px widths. Check equal root/body/shell background, viewport-filling shell, exactly one main landmark, and no page/card/title overflow. Final observations are in `access-theme-matrix-2026-09-12.json`; public theme observations are included separately. This fixture has no authentication or network actions.

- `ui-system-review.tsx`: choose Model forms, open a service editor; repeat with Repository choices. Test both UI languages at 320/375/768/1024/1440px, then repeat using Toggle 200% text. This changes root font size, not native browser zoom.
- Pass the exported `measureUi` function to the browser tab's read-only `evaluate`. Require no page overflow or badge overlap, unique IDs, a nonempty checkbox result set, every checkbox associated/aligned/without overflow and at least 44px target height, and matching select/label font sizes. Expected dated results are in `ui-matrix-2026-09-12.json`.
- Test keyboard Space on replace-address, then remove-key → enter a synthetic new key → remove-key again. New typing clears removal intent; removal clears the typed key. Changing provider or replacement intent clears the prior credential intent. Changed provider requires a replacement address.
- Submit with synthetic URL/key. Check one action in the visible event log, cleared key, disabled controls, and no closing while pending. Resolve failure preserves the editor; refill, retry, resolve success closes it and returns focus. The log records intent/booleans only, never key/address values.
- Open display settings; select a size, press Escape, reopen and click outside. Check focus return and complete visibility at 375px. Click Contribution editors, open the second project and type: it must stay open.
- `visitor-ui-review.tsx`: test long project fields at the same five widths; click the suggested question and confirm textarea value and focus. This does not send a chat request.

After reviewing, stop Vite, close the test tab, reset the viewport override, and remove only the temporary copied app files:

```powershell
Remove-Item -LiteralPath "apps/web/.$reviewName-review.tsx", "apps/web/.$reviewName-review.html"
pnpm run web:check
```

The separate UI fixtures are useful for discovering presentation failures; they do not establish backend correctness, live-provider availability, full browser zoom/accessibility compliance, or a completed novice walkthrough.

## A1 visitor gateway

`a1-gateway-review.tsx` mounts the production `VisitorGatewayPanel` with synthetic
private snapshots. Copy it to `apps/web/.a1-gateway-review.tsx`, replace the script
path in `ui-system-review.html` with `/.a1-gateway-review.tsx`, save the copied HTML
as `apps/web/a1-gateway-review.html`, and open that page on the fixture Vite server.
It performs no provider, Tailscale, GitHub or real admin request.

Check both languages: start leaves the owner-report fact false; all four checks
are required before recording it; stop/configure/start clear it and reset the
checklist. Bundle and local-readiness changes retain the dated report.
Run `checkGatewaySimplification(tab)` from `check-gateway-simplification.js`
against the fresh harness for 11 bilingual lifecycle, request-body, mutation
and revision checks. The harness report is synthetic, not an external check.
Exercise dirty-origin preservation after a
revision conflict, mutation controls while Hold/Release is active, recovery and
display-only scoped Funnel commands. Inspect labels and keyboard focus and repeat
at 375px. Clean up the two exact copied files after the run. Native ASGI, persisted
settings and real listener tests live in the Python suite; this fixture does not
establish external reachability or A12 release acceptance.

- `chat-response-review.tsx`: synthetic failed ChatProfilePanel with an application-owned HTTP-200 output-limit diagnostic. At 375px, switch Chinese/English and check the alert retains its source label, wraps without horizontal overflow, and contains text only. This fixture performs no provider calls.

## Service save confirmation

`admin-events-review.tsx` now offers Save result modes: Success, Failure, and Saved but refresh fails. From a fresh authenticated fixture navigation, run `checkServiceNotices(tab)` exported by `check-service-notices.js`. It exercises actual AdminPage writes through the synthetic fetch boundary, inline failure placement, repeated success timer cleanup, five-second disappearance, English copy, refresh-warning separation, and narrow viewport overflow. The checker waits only to measure the notice lifetime. The eight checks passed at 375px on 2026-09-12; see `docs/SERVICE_UPDATE_FEEDBACK_2026-09-12.md`. No request reaches a real API.

## Production-stack analysis recovery

`analysis_recovery_server.py` is a separate acceptance harness for R01-R07. It serves the production web build and real FastAPI admin routes. It also uses the production batch planner, durable runtime database, worker, archive parser, index builder, contribution service, result validator, idempotency receipts, YAML draft builder, and evidence renderer. Only the external GitHub and model-provider transports are deterministic fixtures; no live credentials or network access are used.

Build the frontend, create a disposable runtime outside the repository, and start the server from the repository root:

```powershell
pnpm run web:build
$runtime = Join-Path $env:TEMP "reponpc-analysis-recovery-$([guid]::NewGuid())"
uv run python tests/browser/analysis_recovery_server.py --runtime $runtime --port 8769
```

Open the printed `BROWSER_URL` only in the isolated browser used for the check. The local-launch value is an ephemeral credential: do not copy it into logs, screenshots, reports, or committed artifacts. Import `check-analysis-recovery.js` into the documented browser runtime. Run once with `await checkAnalysisRecovery(tab, {reconciliationMode: "running", releaseStaleSnapshot: true})`, then use a fresh runtime and origin for `await checkAnalysisRecovery(tab, {reconciliationMode: "completed"})`. The first mode reconciles while the provider barrier is still held, pauses an AdminPage-issued batch GET, applies a newer generation through the normal pause/resume controls, records every batch-status DOM transition, and only then releases the original request. A pass requires the observed sequence to remain exactly `running`, so a transient `running → paused → running` rollback cannot be hidden by a later SSE refresh. The second lets the server finish first and requires manual reconciliation to receive the current terminal snapshot directly from the production batch API. Both perform the entire visible AdminPage flow. They exercise a real same-round retry while discarding its accepted response and first reconciliation GET; verify disabled mutation controls by attempting the retry again and checking the POST count; verify running and completed reconciliation, a genuinely late original request, terminal counters, and stopped timing from two production batch API responses; request one contribution proposal through the production endpoint, edit and confirm it, edit it again, and prove the new version requires explicit reconfirmation; reject a stale current-model confirmation after a simulated second-tab selection; discard the accepted reanalysis response; and submit an equivalent second idempotency key. The visible, test-only observation panel exposes only secret-free hashes, lineage, model/archive/contribution call counts, production snapshot observations, and fault markers so the checker can directly prove one successor, same-key replay, no duplicate provider work, the frozen source commit, exact evidence, contribution confirmation invalidation/preservation, and Chinese/English keyboard operation.

The contribution portion uses the same production AdminPage, FastAPI route, and `GuidedOnboardingService`. It covers delayed-request invalidation, context admission, truncation, invalid schema, manual recovery, the 16,384-token allowance of ADR-073 (the fixture provider declares a 1,000-token maximum, so every request must carry exactly 1,000), closed response schema, previous-version restore, explicit edit/reconfirmation, and the confirmed-only YAML draft boundary.

Run both modes with a new runtime directory and port each time. Stop the server after every run and delete only the disposable runtime you created. A run passes only when the checker returns without throwing. Record the mode, browser user agent, secret-free observations, and worktree fingerprint in `analysis-recovery-evidence.json`; never record the printed URL.

The evidence fingerprint is computed from the sorted per-file SHA-256 manifest embedded in that JSON. The evidence file itself and unrelated user-owned untracked directories are excluded, so the evidence does not claim its own hash. Recreate each manifest entry with PowerShell's `Get-FileHash -Algorithm SHA256 -LiteralPath <path>` and hash the UTF-8 text formed by joining each `path`, one space, its lowercase digest, and a newline. Any content change in scope requires a new pair of clean browser runs and a regenerated manifest.

## Production-stack visitor chat

`visitor_chat_server.py` serves the production web build and the real FastAPI public profile, status, character, and chat-stream routes. Only the external validated-answer boundary is deterministic. The test-only controls expose safe request-history metadata, release barriers, readiness toggles, and disconnect observation; they do not contain credentials, raw provider payloads, private URLs, or production data.

Build the frontend and start each mode with a fresh disposable runtime and origin:

```powershell
pnpm run web:build
uv run python tests/browser/visitor_chat_server.py --runtime <fresh-temp-directory> --port <unused-port>
```

In the documented browser runtime, import `check-visitor-chat.js` and run `checkVisitorChat(tab, {baseUrl, reducedMotion: false})` for the normal-motion flow. It validates real React and public API behavior for progressive SSE delivery, citations, bounded contiguous history, long-answer isolation, failed/incomplete delivery recovery, synchronous duplicate-submit prevention, unmount cancellation, locale continuity, status degradation/recovery, focus, and the character-state sequence. Run `checkVisitorChat(tab, {baseUrl, reducedMotion: true})` against a second fresh runtime; repeat at 375px and a desktop viewport. The reduced-motion path must expose its semantic state while computed sprite animation remains disabled and the page has no horizontal overflow.

The harness does not call a live model, GitHub, or any external network. It does not validate the still-open card text/layout, character setup guidance, protected custom-preview, or publication workflows. Record only safe counts, roles, code-point lengths, state transitions, runtime identifiers, browser/version, viewports, verification results, and a per-file SHA-256 manifest in `visitor-chat-evidence.json`; do not record the local launch URL or full conversation bodies.

## A5 production page and static transport

`a5_server.py` creates a fresh runtime, canonical character, activated local bundle
and reviewed bilingual FAQ through production services. Only embedding and chat
providers are synthetic. It serves the production build and real authenticated
admin/public routes. The disposable credentials are `a5-fixture` / `A5 disposable
browser fixture 2026`; they grant access only to this synthetic runtime.

Run it as a module from the repository root, so its test-package imports resolve:

```powershell
pnpm run web:build
$a5Runtime = Join-Path $env:TEMP "reponpc-a5-$([guid]::NewGuid())"
uv run python -m tests.browser.a5_server --runtime $a5Runtime --port 8780 --gateway-port 8782 --static-origin http://127.0.0.1:8781 --export-directory .test-tmp/a5-browser-sites
```

`a5_transport.py` serves a supplied exported site from a separate loopback origin.
Pass the actual extracted site with `--site`, and use `--base-path /project/` to exercise
a project Pages path. Open `/__a5-test/start` and select **Connect fixture
transport**, then **Check fixture gateway**. The test-only service worker maps
only `https://fixture.ts.net` to the real stoppable gateway on port 8782. It
requires credential-free requests, forwards real responses and fails when that
listener stops. Host/Origin and matching CORS headers are mapped by the test
wrapper; production controllers and API payloads remain intact. The worker streams
the real response through a new `Response` so its loopback transport URL does not
leak into the page's production CSP checks; status, headers and body are preserved.
Returning the mapped fetch response directly makes production status/chat reads
fail even when the no-CSP transport readiness probe succeeds.

```powershell
uv run python -m tests.browser.a5_transport --site <extracted-site-directory> --base-path /project/ --port 8781 --gateway-port 8782
```

Add `--map-pages` to check a downloaded site through the real static listener.
It maps only `https://fixture.github.io` to the `--static-origin` loopback listener
and requires `--gateway-port`. The fixture supplies no response: stopping the
listener fails the check. This is not evidence of real DNS, TLS, GitHub Pages or
Funnel reachability.

1. Start a fresh disposable admin fixture:

   ```powershell
   $a5Runtime = Join-Path $env:TEMP "reponpc-a5-$([guid]::NewGuid())"
   uv run python -m tests.browser.a5_server --runtime $a5Runtime --port 8780 --gateway-port 8782 --static-origin http://127.0.0.1:8781 --map-pages
   ```

2. Sign in at `http://127.0.0.1:8780/admin`, save
   `https://fixture.github.io/project/`, download the site ZIP and extract it.
   Serve the extracted directory in a second terminal:

   ```powershell
   uv run python -m tests.browser.a5_transport --site <extracted-site-directory> --base-path /project/ --port 8781 --gateway-port 8782
   ```

3. Run the admin site's check. With the listener running and the same export
   bytes, the state becomes verified. Stop the static listener and check again:
   it reports `SHARING_VERIFICATION_UNAVAILABLE` and clears verification. Restart
   the listener with a changed `export-manifest.json` (even one added space) and
   check again: it reports `SHARING_VERIFICATION_FAILED` and stays unverified.

An optional `--axe-script <local-axe.min.js>` on either fixture adds same-origin
audit controls through HTML responses; saved build/export bytes and CSP remain
unchanged. `a5-acceptance.js` exposes the audit results without DOM text or
credentials, including computed profile-initial colors and a 4.5:1 contrast
check for the decorative initial that axe may skip. Require every reported
`profileInitialContrast` entry to pass; admin results also include hidden gallery
and layout instances, so record the visible preview mode separately.
`?a5-reduced=1` simulates the reduced-motion media query and provides
a UI control to change it. Record this as a simulated media environment, not an
operating-system preference or native browser emulation.

These mapped checks establish local page/controller integration only. A transport
probe with a placeholder manifest is not export validation. Actual export closure,
identity, base-path and offline behavior require a verified exported artifact.
External TLS, Pages publication, Funnel reachability and clean-host acceptance
remain A12. At the end, select **Disconnect fixture transport**, stop both owned
fixture processes and reset the viewport. Preserve the ChatGPT planning tab.

The optional audit controls also expose **Delay next scene preview**. On the
primary disposable host it delays one production preview by 750ms without
replacing its payload/response, allowing a newer form edit to prove that the
late response cannot enable application. This control is not included in the
exported artifact.

Native background checks use the documented filechooser event and `setFiles`,
then the actual preview/apply/remove/cancel buttons. Check cancel after changing
the background radio or resetting settings, in both locales: the private draft
must be deleted and published revision/model-call observations must stay fixed.
For ZIP download, save a valid Pages URL, then arm the native download event
before clicking either Download static site or Download site archive. Both links
use the authenticated read-only export GET directly. A visible download link
alone does not prove a completed file download. The optional fresh
`--export-directory` creates root/project exports from the exact fixture bundle
using the production exporter and checks every manifest record before extraction;
it is independent of the native download check. Validate the downloaded archive's
manifest/file hashes before using its extracted site. An
unchanged viewport after Control++ is not evidence of actual 200% zoom.

For the backend-to-browser exact FAQ contract, run the production admin/API and
export regression, then check its captured public payload with the actual
TypeScript matcher. The checker uses the already installed TypeScript compiler;
it does not copy the matcher or require Node's native TypeScript support.

```powershell
uv run pytest tests/security/test_a5_sharing_review.py::test_question_variant_export_and_matcher_inputs -q -p no:cacheprovider --basetemp=.test-tmp/a5-faq-parity
node tests/browser/a5-faq-match.mjs .test-tmp/a5-faq-parity/test_question_variant_export_a0/faq-matcher-cases.json
```

This covers both locales, CSRF and stale revision rejection, withdrawal on edit,
pending export exclusion, explicit reapproval, public/export equality, exact
variant admission, unapproved-input rejection and Unicode normalization parity.
The chat admission suite also sends real Node Fetch requests to an ephemeral
loopback HTTP server: 307/308 must not reach their target on the initial POST
or after a 413 admission retry. This is transport evidence, not a native browser
redirect observation. All providers and credentials in these checks are synthetic.

For A7 model-card keyboard regression, use the production Web distribution and
the disposable synthetic catalog fixtures recorded in
`release-evidence/a7/parallel-20261003/`. Check both locales at desktop and375px:
choosing preserves draft input and service choice, explicit fill changes only the
model name, and no profile is saved/tested/selected. With no service, each choice
must focus `chat-profile-heading`; press Tab to reach the existing Refresh action.
Move focus away and select the same card again, including after changing locale:
the heading must receive focus again. Repeated choices must not be ignored because
the catalog row has the same JavaScript object identity. The supplemental receipt
stores actual DOM assertions and screenshot hashes. These synthetic rows do not
admit any real model to the production catalog or prove screen-reader/200%zoom
acceptance. A native-confirm fixture deletion stalled the in-app CDP focus API;
retain that failure, and use a fresh empty-service fixture rather than replacing
browser APIs or touching an owner's service settings.

# Isolated UI and event checks

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

- `chat-response-review.tsx`: synthetic failed ChatProfilePanel with an application-owned HTTP-200 output-limit diagnostic. At 375px, switch Chinese/English and check the alert retains its source label, wraps without horizontal overflow, and contains text only. This fixture performs no provider calls.

## Service save confirmation

`admin-events-review.tsx` now offers Save result modes: Success, Failure, and Saved but refresh fails. From a fresh authenticated fixture navigation, run `checkServiceNotices(tab)` exported by `check-service-notices.js`. It exercises actual AdminPage writes through the synthetic fetch boundary, inline failure placement, repeated success timer cleanup, five-second disappearance, English copy, refresh-warning separation, and narrow viewport overflow. The checker waits only to measure the notice lifetime. The eight checks passed at 375px on 2026-09-12; see `docs/SERVICE_UPDATE_FEEDBACK_2026-09-12.md`. No request reaches a real API.

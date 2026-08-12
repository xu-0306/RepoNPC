# Phase 3 post-repair fresh closure evaluation

## Recommendation

**PASS for the scoped fresh Phase 3 closure invariants.** All newly executed deterministic probes passed. This does not claim a full repository release verification beyond the requested Phase 3 scope.

## Post-repair deterministic results

### Fresh backend — PASS, exit 0

Exact command:

`rtk proxy uv --cache-dir D:\RepoNPC\.uv-cache run --python C:\Python314\python.exe --no-managed-python .agent-foreman/phase3-grounded-visitor/evaluation/fresh/fresh_backend_probe.py`

All 6 probes passed:

- SSE success, abstention, pre-stream timeout, and post-start internal failure preserved exact terminal rules, request-ID correlation, and no secret canary.
- The prior client-disconnect counterexample is closed. Direct ASGI `http.disconnect` produced `app_task_done=true`, no response messages, and still no messages after evaluator release.
- Retrieved prompt injection, forged source/URL/HTML, named-person claim on repository evidence, and mismatched owner assertion all failed closed.
- Explicit Ollama assembly constructed no cloud adapter; missing local embedding dependency degraded safely; configured message limit rejected before chat service/provider cost.
- Shared deadline passed: after 0.35 seconds of embedding work, chat received about 0.1497 seconds remaining rather than a new 0.5-second budget.
- Quality scorer negative controls rejected duplicate/wrong citations and kept the factual denominator limited to reviewed supported claims.

The run emitted one expected safe structured log for the deliberately injected post-start internal SSE failure and one third-party Starlette deprecation warning; neither contained the canary.

### Production web build — PASS, exit 0

Exact command:

`rtk proxy pnpm --dir apps/web run build`

Vite transformed 32 modules and produced the production bundle successfully.

### Fresh Microsoft Edge — PASS, exit 0

Fixture command:

`rtk proxy D:\RepoNPC\.venv\Scripts\uvicorn.exe --app-dir .agent-foreman/phase3-grounded-visitor/evaluation/fresh fresh_browser_fixture_app:app --host 127.0.0.1 --port 8876`

The fixture is a long-running process, so it has no natural exit code; it served successfully and was explicitly terminated after browser completion.

Probe command:

`rtk proxy node .agent-foreman/phase3-grounded-visitor/evaluation/fresh/fresh_browser_probe.mjs`

Microsoft Edge `151.0.4129.78` passed all 6 probes:

- Pure-ASGI boundary preserved `X-Request-ID`, `Cache-Control: no-store`, restrictive CSP, and `X-Content-Type-Options: nosniff`.
- Desktop `1440×900` preserved semantic content, `zh-TW` document language, named controls, and zero horizontal overflow/console/network errors.
- Edited suggestion produced an SSE answer, immutable SHA citation, safe `rel`, `_blank` target, and character `success` state.
- Locale switch updated both `html` and `main` to `en`, loaded English profile content, and preserved conversation text and citation href.
- Populated mobile `390×844` had `scrollWidth == clientWidth == 390`.
- Reduced-motion context reported `true`, pinned frame start to `0px`, and produced no console error.

## Findings

No P0, P1, or P2 finding was reproduced on the post-repair production HEAD within this fresh closure scope.

## Artifacts

- `artifacts/fresh-backend-probe.json`
- `artifacts/fresh-browser-probe.json`
- `artifacts/fresh-browser-mobile.png`
- `artifacts/fresh-evaluation-summary.json`
- `evaluation/fresh/evaluation.json`

Only evaluator-owned `evaluation/fresh/**` and `artifacts/fresh-*` paths were written. Production, existing tests, docs, fixtures, package/lock files, oracle, and prior browser artifacts were not modified by this evaluation.

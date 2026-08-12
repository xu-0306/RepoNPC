# Fresh Phase 3 falsification probes

This evaluator-owned directory is the only source location written by the fresh review. Production, existing tests, fixtures, docs, package files, locks, and the prior browser probe remain untouched.

Commands:

1. `rtk proxy uv --cache-dir D:\RepoNPC\.uv-cache run --python C:\Python314\python.exe --no-managed-python .agent-foreman/phase3-grounded-visitor/evaluation/fresh/fresh_backend_probe.py`
2. `rtk proxy pnpm --dir apps/web run build`
3. `rtk proxy uv --cache-dir D:\RepoNPC\.uv-cache run --python C:\Python314\python.exe --no-managed-python uvicorn --app-dir .agent-foreman/phase3-grounded-visitor/evaluation/fresh fresh_browser_fixture_app:app --host 127.0.0.1 --port 8876`
4. `rtk proxy node .agent-foreman/phase3-grounded-visitor/evaluation/fresh/fresh_browser_probe.mjs`

Artifacts are written as `artifacts/fresh-backend-probe.json`, `artifacts/fresh-browser-probe.json`, and `artifacts/fresh-browser-mobile.png`. Every structured probe result records setup, fault injection, production trigger, oracle, anti-oracle, and observed result.

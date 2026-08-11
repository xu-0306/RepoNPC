Role: fresh independent evaluator. Production and existing tests are read-only. You may create or edit files only below `.agent-foreman/mvp/evaluation/`. Do not repair application code, tests, contracts, plan files, dependencies, or documentation.

Evaluate plan `REPONPC-MVP-20260810` after Main integration. Invent at least one new falsification probe for each critical invariant:

- `INV-AUTHORIZED-SCOPE`
- `INV-CONFIG-STRICT`
- `INV-EVIDENCE-STABLE`
- `INV-PUBLIC-SETUP-SAFE`
- `INV-I18N-PARITY`

Each probe must record setup, fault injection, real production trigger, oracle, anti-oracle, exact command, exit code, and durable artifact. Invoke real public boundaries where the claim is about an entrypoint. New probe code and all basetemp/output must stay below the evaluation directory. Set `PYTHONDONTWRITEBYTECODE=1` and disable pytest's cache provider so evaluation does not write into production paths.

Write `.agent-foreman/mvp/evaluation/evaluation.json` with schema `agent-foreman/evaluation` version `1.0`, profile `full`, plan and phase IDs, fresh context, model diversity, production access `read-only`, the new probes, deterministic result, findings, and advisory recommendation `pass`, `revise`, or `blocked`. Include enough artifacts for Root to reproduce every observation. Do not declare project completion.

The pre-evaluation hashes are in `production-baseline.txt`. Do not update that file. Root will independently recompute them after evaluation.

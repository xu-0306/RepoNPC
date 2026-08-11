# Phase 2 Foreman closure correction

Date: 2026-08-11

The Agent Foreman skill was corrected on 2026-08-11.  A read-only evaluator
that writes only evaluation probes is now explicitly distinct from a worker
delegation.  Therefore a `minimal` / `main_direct` plan may record its
`evaluations` section and enter `verified` when all blocking gates and fresh
critical-invariant probes pass.

The original implementation did not retain genuine worker dispatch or
handoff artifacts.  It correctly remains a `minimal` plan: converting it to
`full` would have required inventing historical delegation records.  The
canonical `plan.json` is now `verified`, and every contained evaluation has
the matching `minimal` profile.  The earlier pre-fix attempt is preserved at
`artifacts/plan-attempted-verified-20260811.json` for audit context.

The original append-only `evidence-ledger.jsonl` is also retained unchanged.
Its line 15 has a 65-character SHA-256 value for
`EVID-P2-07-REPEAT-BUILD-20260810-02`.  The actual JUnit artifact hashes to
`8122f1dabe3803038daf8b82f0aa11a01d08de48463f615c6c2bfeb868dec24a`.
`evidence-ledger-validated-20260811.jsonl` is a separate, mechanically
migrated ledger that corrects only that malformed value, so the validator can
audit the same evidence without rewriting history.

This is a governance-tool constraint only.  It does not convert the
evaluation evidence into a Foreman `verified` declaration and does not alter
the Phase 2 requirement or acceptance evidence.

# Legacy code archive

Owner decision: 2026-10-20. This directory is historical source, outside the application.
Whole files were moved with the filesystem and retain their original bytes.

## Code

| Original path | New path | Reason | Owner decision date |
| --- | --- | --- | --- |
| `tests/integration/test_github_public_read_retirement.py` | `legacy/tests/integration/test_github_public_read_retirement.py` | A2 tests removed GitHub public-read tombstones | 2026-10-20 |
| `src/reponpc/bundles/updater.py` | `legacy/src/reponpc/bundles/updater.py` | A1 remote polling and GitHub Release publication | 2026-10-20 |
| `src/reponpc/indexing/github_publication.py` | `legacy/src/reponpc/indexing/github_publication.py` | A1 remote polling and GitHub Release publication | 2026-10-20 |
| `src/reponpc/indexing/publication.py` | `legacy/src/reponpc/indexing/publication.py` | A1 remote polling and GitHub Release publication | 2026-10-20 |
| `tests/integration/test_bundle_updater.py` | `legacy/tests/integration/test_bundle_updater.py` | A1 remote polling and GitHub Release publication | 2026-10-20 |
| `tests/integration/test_bundle_updater_lifecycle.py` | `legacy/tests/integration/test_bundle_updater_lifecycle.py` | A1 remote polling and GitHub Release publication | 2026-10-20 |
| `tests/integration/test_github_publication.py` | `legacy/tests/integration/test_github_publication.py` | A1 remote polling and GitHub Release publication | 2026-10-20 |
| `tests/integration/test_publication_last.py` | `legacy/tests/integration/test_publication_last.py` | A1 remote polling and GitHub Release publication | 2026-10-20 |
| `src/reponpc/admin/github.py` | `legacy/src/reponpc/admin/github.py` | A6 GitHub-only writeback | 2026-10-20 |
| `tests/integration/test_admin_github.py` | `legacy/tests/integration/test_admin_github.py` | A6 GitHub-only writeback | 2026-10-20 |
| `tests/security/test_admin_writeback.py` | `legacy/tests/security/test_admin_writeback.py` | A6 GitHub-only writeback | 2026-10-20 |

## Documents

| Original path | New path | Reason |
| --- | --- | --- |
| docs/A11_BACKUP_BOUNDARY_DECISION_2026-10-03.md | legacy/docs/A11_BACKUP_BOUNDARY_DECISION_2026-10-03.md | historical handoff |
| docs/A1_A4_COMPLEXITY_AUDIT_2026-10-02.md | legacy/docs/A1_A4_COMPLEXITY_AUDIT_2026-10-02.md | historical handoff |
| docs/A5_CHATGPT_PLAN_2026-09-29.md | legacy/docs/A5_CHATGPT_PLAN_2026-09-29.md | historical handoff |
| docs/A5_HANDOFF_2026-09-30.md | legacy/docs/A5_HANDOFF_2026-09-30.md | historical handoff |
| docs/A5_PAGES_SHARING_SIMPLIFICATION_HANDOFF_2026-10-02.md | legacy/docs/A5_PAGES_SHARING_SIMPLIFICATION_HANDOFF_2026-10-02.md | historical handoff |
| docs/A7_TWO_FACTS_FIXTURE_REVIEW_2026-10-03.md | legacy/docs/A7_TWO_FACTS_FIXTURE_REVIEW_2026-10-03.md | historical handoff |
| docs/A9_MAN_DEFAULT_DECISION_2026-10-03.md | legacy/docs/A9_MAN_DEFAULT_DECISION_2026-10-03.md | historical handoff |
| docs/ACCEPTANCE_CRITERIA.md (AC-026, AC-027, AC-029, AC-041–043, AC-051) | legacy/docs/ACCEPTANCE_SUPERSEDED.md | archived by ADR-071 |
| docs/ADMIN_WORKSPACE_UI_IMPROVEMENT_PLAN.md | legacy/docs/ADMIN_WORKSPACE_UI_IMPROVEMENT_PLAN.md | historical handoff |
| docs/ANALYSIS_JSON_FAILURE_DIAGNOSIS_2026-09-13.md | legacy/docs/ANALYSIS_JSON_FAILURE_DIAGNOSIS_2026-09-13.md | historical handoff |
| docs/CHAT_PROBE_RESPONSE_CHECKS_2026-09-12.md | legacy/docs/CHAT_PROBE_RESPONSE_CHECKS_2026-09-12.md | historical handoff |
| docs/CONTINUATION_HANDOFF_2026-10-03.md | legacy/docs/CONTINUATION_HANDOFF_2026-10-03.md | historical handoff |
| docs/DECISIONS.md (ADR-005, ADR-010, ADR-020, ADR-022) | legacy/docs/DECISIONS_SUPERSEDED.md | superseded by later ADRs / ADR-071 |
| docs/DELIVERY_PHASES.md | legacy/docs/local/DELIVERY_PHASES.md | historical handoff |
| docs/GITHUB_LOGIN_AND_BATCH_ANALYSIS_PLAN.md | legacy/docs/local/GITHUB_LOGIN_AND_BATCH_ANALYSIS_PLAN.md | historical handoff |
| docs/GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_HANDOFF.md | legacy/docs/GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_HANDOFF.md | historical handoff |
| docs/GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_PLAN.md | legacy/docs/GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_PLAN.md | historical handoff |
| docs/GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_REVIEW_HANDOFF.md | legacy/docs/GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_REVIEW_HANDOFF.md | historical handoff |
| docs/GITHUB_PUSH_HANDOFF_2026-09-16.md | legacy/docs/GITHUB_PUSH_HANDOFF_2026-09-16.md | historical handoff |
| docs/IMPLEMENTATION_BACKLOG_2026-09-26.md | legacy/docs/IMPLEMENTATION_BACKLOG_2026-09-26.md | historical handoff |
| docs/LOCAL_ADMIN_ACCESS_HANDOFF.md | legacy/docs/LOCAL_ADMIN_ACCESS_HANDOFF.md | historical handoff |
| docs/LOCAL_ADMIN_ACCESS_IMPLEMENTATION_HANDOFF.md | legacy/docs/LOCAL_ADMIN_ACCESS_IMPLEMENTATION_HANDOFF.md | historical handoff |
| docs/LOCAL_PUBLICATION_VERIFICATION_2026-09-23.md | legacy/docs/LOCAL_PUBLICATION_VERIFICATION_2026-09-23.md | historical handoff |
| docs/MANAGED_URL_EDITING_2026-09-12.md | legacy/docs/MANAGED_URL_EDITING_2026-09-12.md | historical handoff |
| docs/MOCHI_PROVIDER_COMPARISON_2026-09-12.md | legacy/docs/MOCHI_PROVIDER_COMPARISON_2026-09-12.md | historical handoff |
| docs/MODEL_ONBOARDING_IMPLEMENTATION_REVIEW_2026-09-10.md | legacy/docs/MODEL_ONBOARDING_IMPLEMENTATION_REVIEW_2026-09-10.md | historical handoff |
| docs/MODEL_SETUP_IMPLEMENTATION_HANDOFF.md | legacy/docs/MODEL_SETUP_IMPLEMENTATION_HANDOFF.md | historical handoff |
| docs/NEXT_ROUND_HANDOFF_2026-10-15.md | legacy/docs/NEXT_ROUND_HANDOFF_2026-10-15.md | historical handoff |
| docs/OFFLINE_ATTRIBUTION_MAN_HANDOFF_2026-10-03.md | legacy/docs/OFFLINE_ATTRIBUTION_MAN_HANDOFF_2026-10-03.md | historical handoff |
| docs/ONBOARDING_FLOW_IMPLEMENTATION_HANDOFF.md | legacy/docs/ONBOARDING_FLOW_IMPLEMENTATION_HANDOFF.md | historical handoff |
| docs/OPTIMIZATION_PLAN_2026-10-11.md | legacy/docs/OPTIMIZATION_PLAN_2026-10-11.md | historical handoff |
| docs/OUTPUT_SCRIPT_AND_CACHE_REPAIR_PLAN_2026-10-14.md | legacy/docs/OUTPUT_SCRIPT_AND_CACHE_REPAIR_PLAN_2026-10-14.md | historical handoff |
| docs/P1-04_REFACTOR_HANDOFF.md | legacy/docs/local/P1-04_REFACTOR_HANDOFF.md | historical handoff |
| docs/P2_FOUNDATION_HANDOFF.md | legacy/docs/local/P2_FOUNDATION_HANDOFF.md | historical handoff |
| docs/P4_OWNER_ASSETS_PUBLICATION_HANDOFF.md | legacy/docs/local/P4_OWNER_ASSETS_PUBLICATION_HANDOFF.md | historical handoff |
| docs/PARALLEL_IMPLEMENTATION_HANDOFF_2026-10-03.md | legacy/docs/PARALLEL_IMPLEMENTATION_HANDOFF_2026-10-03.md | historical handoff |
| docs/PARALLEL_IMPLEMENTATION_PLAN_2026-10-03.md | legacy/docs/PARALLEL_IMPLEMENTATION_PLAN_2026-10-03.md | historical handoff |
| docs/PROJECT_CONTEXT.md (dated checkpoints) | legacy/docs/local/PROJECT_CONTEXT_HISTORY.md | historical handoff |
| docs/PROVIDER_ERROR_MESSAGES_2026-09-12.md | legacy/docs/PROVIDER_ERROR_MESSAGES_2026-09-12.md | historical handoff |
| docs/PUBLISHING_UX_OPTIMIZATION_PLAN_2026-09-22.md | legacy/docs/PUBLISHING_UX_OPTIMIZATION_PLAN_2026-09-22.md | historical handoff |
| docs/REMAINING_WORK_EXECUTION_2026-10-03.md | legacy/docs/REMAINING_WORK_EXECUTION_2026-10-03.md | historical handoff |
| docs/REPAIR_PROGRESS_2026-09-17.md | legacy/docs/REPAIR_PROGRESS_2026-09-17.md | historical handoff |
| docs/SECURITY.md (retired identity history) | legacy/docs/SECURITY_HISTORY.md | superseded by ADR-028 / ADR-071 |
| docs/SERVICE_UPDATE_FEEDBACK_2026-09-12.md | legacy/docs/SERVICE_UPDATE_FEEDBACK_2026-09-12.md | historical handoff |
| docs/SPEC_AND_ENGINEERING_REMEDIATION_PLAN.md | legacy/docs/local/SPEC_AND_ENGINEERING_REMEDIATION_PLAN.md | historical handoff |
| docs/SUBAGENT_EXECUTION_PLAYBOOK.md | legacy/docs/local/SUBAGENT_EXECUTION_PLAYBOOK.md | historical handoff |
| docs/TECHNICAL_SPEC.md (history and superseded sections) | legacy/docs/TECHNICAL_SPEC_HISTORY.md | archived by ADR-071 |
| docs/UI_SYSTEM_EVENT_AUDIT_2026-09-12.md | legacy/docs/UI_SYSTEM_EVENT_AUDIT_2026-09-12.md | historical handoff |
| docs/UI_THEME_STATE_AUDIT_2026-09-12.md | legacy/docs/UI_THEME_STATE_AUDIT_2026-09-12.md | historical handoff |
| docs/UI_UX_REVIEW_2026-09-12.md | legacy/docs/UI_UX_REVIEW_2026-09-12.md | historical handoff |
| docs/UX_SPEC_REVIEW.md | legacy/docs/local/UX_SPEC_REVIEW.md | historical handoff |
| docs/WINDOWS_LICENSE_REVIEW_2026-10-03.md | legacy/docs/WINDOWS_LICENSE_REVIEW_2026-10-03.md | historical handoff |

Stubs retain the original heading and point to the archived full text so historical references continue to resolve.

Code removed from files that stay live (partial edits) is in the diff of the commit that added this README: `git log --diff-filter=A -p -- legacy/README.md` names it.

Retrieve a file as it was before the archive with:

```text
git show legacy-archive-2026-10-20:<path>
```

The restore tag is `378af5b`, the commit before Stage A (it includes W1).

## Retained database columns

- `bundle_state.safe_update_error`: unused; existing stored values are left intact.
- `bundle_state.manifest_etag`: no new polling ETags; retained state still round-trips it.
- `bundle_state.last_checked_at`: no polling writer; existing timestamps still appear in status.
- `admin_audit`: `audit_id`, `occurred_at`, `action`, `target_path`, `result_commit_sha`, `request_id`, `outcome`, `session_hash` have no new GitHub-writeback writer. Historical records remain; backup session sanitization remains.
- Retired OAuth/public-read credential tables and columns were already unused before Stage A; all migrations remain unchanged.

## Existing .env migration

Delete these lines from existing `.env` files (including empty assignments). Removed names now fail the existing unknown-variable validator:

- `REPONPC_CONFIG_REPOSITORY`
- `REPONPC_INDEX_MANIFEST_URL`
- `REPONPC_INDEX_POLL_SECONDS`
- `REPONPC_GITHUB_TOKEN`
- `REPONPC_GITHUB_TOKEN_FILE`
- `REPONPC_CONFIG_BRANCH`
- `REPONPC_INDEX_WORKFLOW`
- `REPONPC_CONFIG_PATH`
- `REPONPC_GITHUB_OAUTH_CLIENT_ID`
- `REPONPC_GITHUB_OAUTH_CLIENT_SECRET`
- `REPONPC_GITHUB_OAUTH_CLIENT_SECRET_FILE`
- `REPONPC_GITHUB_OAUTH_CALLBACK_URL`
- `REPONPC_CREDENTIAL_ENCRYPTION_KEY`
- `REPONPC_CREDENTIAL_ENCRYPTION_KEY_FILE`

`REPONPC_GITHUB_API_URL` and local bundle size/retention limits remain supported.
Existing bundle manifests (including real configuration repository slugs) and SQLite migrations are unchanged.
Reindex takes the repository and immutable commit from the active manifest. Local publication keeps its shared local identity.
The raw YAML editor, local save/download, validation and builtin preview remain. A custom sprite is previewed through the character upload; the raw editor preview reports `custom_sprite_preview_needs_upload`.
Retained local admin tests and their shared fixtures live in `tests/security/test_admin_assets.py`.

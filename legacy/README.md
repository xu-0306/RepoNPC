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

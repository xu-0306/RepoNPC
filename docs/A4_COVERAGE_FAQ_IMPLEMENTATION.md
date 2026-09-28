# A4 coverage and reviewed FAQ

**Contract:** FR-046 / AC-067 / ADR-048, completion direction §3 and §4.3. Implementation uses Approved Technical Specification 0.4.5. These details realize the approved requirement; no new owner decision or dependency is introduced.

## Owner flow

The Preview, try and share workspace offers an explicit **Check six standard questions with models** action against the actual prepared active local bundle. The bilingual finite registry is `src/reponpc/admin/faq_registry.py`: responsibility, built work, duration, team/context, outcomes and technologies. Checking initializes all registry and current profile suggested questions, deduplicating identical localized questions. It generates six registry answers sequentially; suggested candidates remain **Not checked** until explicitly generated.

Answers use the same retrieval, envelope-v2 prompt/schema and validator as ordinary chat. Owner generation uses the existing `ADMIN_SINGLE` fair scheduler without consuming public daily admission. Validated retained citations determine answered; retained citations plus insufficiency or dropped segments determine partially answered; a validated reply without retained citations determines no relevant content. Unchecked/provider failures remain unchecked with an actionable retry message. Dropped segment indexes are zero-based on the wire, shown one-based in the owner UI, with fixed reason codes. Coverage never participates in save, prepare, activation or sharing eligibility.

The gap shortcut selects an enabled repository and opens the existing contribution editor with a new bilingual owner statement and its claim kind selected. Responsibility and built work map to responsibility; duration/team/technologies map to context; outcomes map to achievement. Existing claims and editable contribution text remain available. Manual contribution editing supports adding/removing owner statements.

FAQ actions are approve, reject, regenerate and rewrite as an owner statement. Generated answer text has no edit endpoint or editable answer control. A consciously reviewed generated no-match reply may be approved. Ungenerated, failed and rewrite-pending candidates cannot be approved.

Rewrite saves the owner's bilingual text as a uniquely identified claim in the public local draft using the existing revision-checked store, then explicitly invokes existing local preparation with the selected model-pair generation and confirmation. Once the real new index is ready, generation verifies the exact saved claim ID, repository and bilingual content in the leased index, and packs that evidence within existing record/per-repository/token limits. The source bundle cannot satisfy this step. Missing evidence or inadequate context fails explicitly and preserves the saved rewrite association for a **Continue** action after interruption/reload. Successful regeneration remains pending review. Brief runtime/draft mutations use one sole-owner process lock; provider work runs outside it.

## Runtime and bundle identity

Migration **29**, `bundle_bound_reviewed_faq`, adds `faq_entries` to the existing runtime SQLite database. Bundle index/public bytes are never edited by review. Normal SQLite backup/reopen includes the FAQ rows and pending rewrite association.

Each locale/question key retains one latest candidate, with an optimistic revision and exact generated bundle ID. Reinitializing a queue preserves candidates and approvals. A changed/removed suggested question does not delete earlier owner work; earlier rows remain visible. Regeneration replaces the candidate and withdraws its approval before generation starts, including when generation fails. This is intentionally not an approval history: rollback only serves a candidate if its current stored approval is for the rolled-back bundle; regeneration of a newer bundle cannot restore an older approval automatically.

The bundle manager captures reader, manifest bundle ID and public directory atomically with one lease, releases its lock before provider work, and retains the reader throughout generation. Activation during generation cannot relabel citations with a newer bundle. Stale entries display **Needs reconfirmation** and require fresh generation/review; stale approval is never returned by public delivery/export.

## HTTP contract

All owner routes use the existing authenticated same-origin boundary; writes require CSRF. Responses use `Cache-Control: no-store`. IDs are opaque lowercase UUID hex32; revisions are positive integers; draft revisions are lowercase SHA-256 hex64. Locale is `zh-TW` or `en`.

| Method and route | Request / result |
| --- | --- |
| `GET /api/admin/portfolio/faq?locale=…` | Current bundle and owner queue, including coverage/review state, fixed diagnostics, revision and resumable rewrite association |
| `POST /api/admin/portfolio/faq/check` | `{locale}`; initializes all candidates without an implicit provider call |
| `POST /api/admin/portfolio/faq/{id}/regenerate` | `{revision}`; runs the normal validated answer pipeline, requires matching new indexed claim when a rewrite is pending |
| `POST /api/admin/portfolio/faq/{id}/review` | `{revision,bundle_id,action:"approve"|"reject"}`; exact revision/current bundle binding |
| `POST /api/admin/portfolio/faq/{id}/rewrite` | `{revision,expected_draft_revision,repository,kind,statement:{"zh-TW":…,en:…}}`; returns saved local draft and pending entry |
| `GET /api/admin/portfolio/faq/export?locale=…` | Downloads `faq-{locale}.json` using the same public allowlist as visitor delivery |
| `GET /api/public/faq?locale=…` | Credential-free approved-current payload below; unavailable index returns the existing safe index error |

Public/export payload: `{bundle_id,locale,entries:[{question,answer_markdown,citations}]}`. Citation fields are explicitly allowlisted: `id,evidence_id,evidence_class,repository,commit_sha,path,start_line,end_line,title,excerpt,url`. There are no review states/reasons, drafts, rewrite associations, prompts, usage, provider metadata or secrets. Empty approved sets export a concrete empty `entries` array.

Owner conflicts/staleness/not-ready/not-indexed/context-capacity failure return 409 with `FAQ_CONFLICT`, `FAQ_STALE`, `FAQ_NOT_READY`, `FAQ_REWRITE_NOT_INDEXED` or `FAQ_CONTEXT_INSUFFICIENT`. The context failure advises shortening the owner statement or adjusting the answer model. Missing service/generation failure returns safe 503; invalid repository returns 422 `FAQ_REPOSITORY_INVALID`; unknown entry returns 422 `FAQ_NOT_FOUND`. Existing portfolio/configuration/auth validation errors remain in use. Raw exception/provider text is never reflected or stored by these routes.

## Visitor use and verification boundary

Approved-current entries appear as suggestion chips in the existing visitor page. Selecting one rechecks current approval through the public FAQ route and displays its validated answer/citations without a model call. Request identity/cancellation protects language switches and duplicate clicks. Bundle mismatch refreshes the profile instead of displaying stale content; rejected entries disappear from the refreshed chips.

Local synthetic verification covers actual build/save/new-index/validator regeneration in both locales, all four API actions, fixed dropped indexes/reasons, failures, zero-budget rewrite, activation during generation, immutable bytes, migration rollback/backup/reopen, a concurrent rewrite/save/review regression, authenticated boundaries, approved-only export and real browser controls. Full Python/Web, 19 browser checks and Docker results are recorded in [local verification](../release-evidence/a4/local-checks.md). No live provider/GitHub/Funnel call or public deployment was made. A5 owns the full static site/Pages export, offline question matching and gateway/public-layout work.

Engineering note: natural-language coverage is open-world input decided by validated generation structure, never a keyword classifier. Only six closed product topics and finite claim/status/error controls are registry data. Bilingual text variants, missing evidence, rejected claims and injected unsafe outputs are exercised by tests.

### Final local verification (2026-09-28)

| Check | Result |
| --- | --- |
| Full Python, `.venv/Scripts/python.exe -m pytest --ignore=tests/smoke/test_container.py -p no:cacheprovider --basetemp .test-tmp/a4-full-final -q` | **1,163 passed, 2 skipped**; 90.39 seconds; existing Starlette/httpx deprecation warning |
| FAQ integration, independent security and runtime migration tests, per-run basetemp without cache provider | **37 passed**, including canonical Unicode/CRLF rewrite, concurrent saved-claim association and approved/pending backup/reopen |
| `ruff check src tests`, `ruff format --check src tests` | Passed; **179 files** already formatted |
| `mypy src/reponpc` | Passed; **75 source files** |
| `pnpm run web:check` | Prettier, ESLint, TypeScript, **226 tests / 29 files**, production build passed; **0 ESLint errors**, 16 existing Fast Refresh warnings |
| Main's real browser checks | **19 passed**: owner actions/locale/staleness/export/continuation 10, actual visitor App approval freshness/cancellation 7, 375px layout and bilingual keyboard order 2 |
| Separate Docker smoke, run by Main | **1 passed** |
| `git diff --check` | Passed |

No stored provider credentials/URLs were inspected, no provider/GitHub network call was made, and no deployment/Funnel/public-release acceptance is claimed.

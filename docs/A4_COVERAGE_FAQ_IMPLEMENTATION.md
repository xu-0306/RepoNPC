# A4 coverage and reviewed FAQ

**Contract:** FR-046 / AC-067 / ADR-048, completion direction §3 and §4.3. Implementation uses Approved Technical Specification 0.4.5. These details realize the approved requirement; no new owner decision or dependency is introduced.

## Owner flow

The Preview, try and share workspace offers an explicit **Check six standard questions with models** action against the actual prepared active local bundle. The bilingual finite registry is `src/reponpc/admin/faq_registry.py`: responsibility, built work, duration, team/context, outcomes and technologies. Checking initializes all registry and current profile suggested questions, deduplicating identical localized questions. It generates six registry answers sequentially; suggested candidates remain **Not checked** until explicitly generated.

Answers use the same retrieval, envelope-v2 prompt/schema and validator as ordinary chat. Owner generation uses the existing `ADMIN_SINGLE` fair scheduler without consuming public daily admission. Validated retained citations determine answered; retained citations plus insufficiency or dropped segments determine partially answered; a validated reply without retained citations determines no relevant content. Unchecked/provider failures remain unchecked with an actionable retry message. Dropped segment indexes are zero-based on the wire, shown one-based in the owner UI, with fixed reason codes. Coverage never participates in save, prepare, activation or sharing eligibility.

The gap shortcut selects an enabled repository and opens the existing contribution editor with a new bilingual owner statement and its claim kind selected. Responsibility and built work map to responsibility; duration/team/technologies map to context; outcomes map to achievement. Existing claims and editable contribution text remain available. Manual contribution editing supports adding/removing owner statements.

FAQ actions are approve, reject, regenerate and rewrite as an owner statement. Generated answer text has no edit endpoint or editable answer control. A consciously reviewed generated no-match reply may be approved. Ungenerated and failed candidates cannot be approved.

Rewrite opens the same contribution editor as the gap shortcut, with repository and claim kind selected. The owner saves the bilingual claim in the revision-checked local draft, prepares the NPC using the ordinary publication action, then regenerates and reviews the FAQ. New bundle activation marks earlier entries as needing reconfirmation. Normal retrieval does not guarantee citation of the new statement; the owner must review the generated answer. FAQ writes use SQLite transactions and conditional revision updates; provider work stays outside these transactions.

## Runtime and bundle identity

Migration **29**, `bundle_bound_reviewed_faq`, adds `faq_entries` to the existing runtime SQLite database. Bundle index/public bytes are never edited by review. Normal SQLite backup/reopen includes the FAQ rows. The shipped `rewrite_json` column remains unused: new writes clear it to NULL and reads ignore old values; the migration is unchanged.

Each locale/question key retains one latest candidate, with an optimistic revision and exact generated bundle ID. Reinitializing a queue preserves candidates and approvals. A changed/removed suggested question does not delete earlier owner work; earlier rows remain visible. Regeneration replaces the candidate and withdraws its approval before generation starts, including when generation fails. This is intentionally not an approval history: rollback only serves a candidate if its current stored approval is for the rolled-back bundle; regeneration of a newer bundle cannot restore an older approval automatically.

The bundle manager captures reader, manifest bundle ID and public directory atomically with one lease, releases its lock before provider work, and retains the reader throughout generation. Activation during generation cannot relabel citations with a newer bundle. Stale entries display **Needs reconfirmation** and require fresh generation/review; stale approval is never returned by public delivery/export.

## HTTP contract

All owner routes use the existing authenticated same-origin boundary; writes require CSRF. Responses use `Cache-Control: no-store`. IDs are opaque lowercase UUID hex32; revisions are positive integers. Locale is `zh-TW` or `en`.

| Method and route | Request / result |
| --- | --- |
| `GET /api/admin/portfolio/faq?locale=…` | Current bundle and owner queue, including coverage/review state, fixed diagnostics and revision |
| `POST /api/admin/portfolio/faq/check` | `{locale}`; initializes all candidates without an implicit provider call |
| `POST /api/admin/portfolio/faq/{id}/regenerate` | `{revision}`; runs the normal validated answer pipeline |
| `POST /api/admin/portfolio/faq/{id}/review` | `{revision,action:"approve"|"reject"}`; server compares the stored row's bundle with the active bundle |
| `GET /api/admin/portfolio/faq/export?locale=…` | Downloads `faq-{locale}.json` using the same public allowlist as visitor delivery |
| `GET /api/public/faq?locale=…` | Credential-free approved-current payload below; unavailable index returns the existing safe index error |

Public/export payload: `{bundle_id,locale,entries:[{question,variants,answer_markdown,citations}]}`. Variants are owner-approved under the A5 contract; no separate matcher configuration is returned. Citation fields are explicitly allowlisted: `id,evidence_id,evidence_class,repository,commit_sha,path,start_line,end_line,title,excerpt,url`. There are no review states/reasons, drafts, rewrite associations, prompts, usage, provider metadata or secrets. Empty approved sets export a concrete empty `entries` array.

Owner conflicts/staleness/not-ready return 409 with `FAQ_CONFLICT`, `FAQ_STALE` or `FAQ_NOT_READY`. Missing service/generation failure returns safe 503; unknown entry returns 422 `FAQ_NOT_FOUND`. Existing portfolio/configuration/auth validation errors remain in use. Raw exception/provider text is never reflected or stored by these routes.

## Visitor use and verification boundary

Approved-current entries load with the profile and appear as suggestion chips in the existing visitor page. Chips and offline question matching use this cached FAQ without another request or model call. The local FAQ bundle must match the profile version, and a known status bundle mismatch disables offline answers. Initial request cancellation protects language switches. Mid-session withdrawals remain visible until the visitor reloads the FAQ/profile; refreshed responses omit rejected entries.

Local synthetic verification covers actual draft-save/new-index/normal validator regeneration in both locales, FAQ API actions, fixed dropped indexes/reasons, failures, activation during generation, immutable bytes, migration rollback/backup/reopen, concurrent review/regenerate, authenticated boundaries, approved-only export and real browser controls. Historical pre-simplification Python/Web and browser results are recorded in [local verification](../release-evidence/a4/local-checks.md). B4 evidence records the simplified flow. No live provider/GitHub/Funnel call or public deployment was made. A5 owns the full static site/Pages export, offline question matching and gateway/public-layout work.

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

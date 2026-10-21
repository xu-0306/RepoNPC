# A5 visitor, appearance and export implementation contract

Date: 2026-09-29. Status: implementation of approved A5 / R08 scope.

The owner requested ChatGPT planning followed by `gpt-6-luna` with `max`
reasoning. The received plan is recorded in
`A5_CHATGPT_PLAN_2026-09-29.md`. Approved specification 0.4.6, ADR-048–053,
the completion direction contract §4 and the A1/A4 contracts take precedence.
This document fixes implementation seams; it does not change acceptance limits.
`rtk` remains optional. No agent-foreman is used, per the owner's preference.

## Execution and ownership

One Luna max implementer delivers the five implementation batches in sequence:

1. Scheme registry, scene resolver, strict configuration/profile contracts and
   reproducible fallback generation.
2. Protected preview assets, background drafts and atomic appearance publication.
3. Shared visitor page, live/static controllers, mode bootstrap and appearance UI.
4. Approved FAQ variants, deterministic site export and browser offline matching.
5. Pages verification, private sharing state and README card target.

Main owns this contract, integration decisions, independent review, negative
tests, production browser verification and documentation/evidence. Each batch
is reviewed before the next. Preserve user changes and the existing untracked
directories. Do not commit or push, activate Funnel, upload to GitHub, call live
models, inspect secrets or mutate live runtime data.

## 1. Scene producer and consumers

`character.scene` is additive. Defaults are `neutral`, `system`, visitor toggle
on, no accent/image, smooth scaling, 50/50 focus and automatic dim. Fields and
bounds are exactly those in completion contract §4.6. Unknown fields and retired
template/source/glow/pack scene fields fail validation. A background path is one
PNG/WebP immediately under `assets/scene/`.

The packaged registry uses `schemes` and `aliases` as its only top-level keys.
Each scheme has `id`, positive `version`, `label` with exactly `zh-TW`/`en`,
`light` and `dark`. Both variants have exactly the ten approved roles. Load
failures identify scheme, variant and role/pair without reflecting arbitrary
submitted data. Duplicate YAML keys must not be silently overwritten. Alias
cycles, dangling aliases and ID collisions fail. Authored scheme values are
never repaired at runtime. Registry validation runs before serving requests.

The shared Python resolver produces this exact public shape:

```text
{revision, scheme:{id,version}, color_mode, visitor_mode_toggle,
 themes:{light:{ten roles},dark:{ten roles}}, background_url,
 background_scaling, background_focus:{x,y}, background_dim}
```

Colors are lowercase six-digit hex. The resolver is deterministic and takes
validated settings, canonical sprite bytes and optional canonical image bytes.
Only the stage role depends on sprite pixels. Accent adjustment and stage/image
notices remain private preview data. No names, pack IDs, options or filenames
affect resolution. All authored contrast pairs and the sprite edge rule retain
the approved thresholds. Lightness adjustment uses OKLCH with hue preserved;
gamut handling must be deterministic. The solid stage backing is shared by hero
and avatars; no drawn backdrop or species-specific imagery is introduced.

The edge average includes all 28 canonical cells; transparency adjacency stays
inside each cell. It is the aggregate edge rule already approved, not a new
per-frame threshold. Stage candidates avoid equality with `surface`; the shared
disc/ring boundary uses the existing `border` role, already validated at 3:1
against surfaces. No new stage/surface contrast threshold is introduced.
Public scene parsing validates the same closed contrast pairs and requires
scene revision to equal its containing character revision. Private adjustment
notices name their variant.

Old configuration/profile bytes without a scene remain readable. They resolve
the default against the actual active sheet at the serving boundary. New bundle
bytes carry resolved tokens and are not recolored after a registry update. A
bundle containing an image declares its exact validated public asset and hash;
undeclared extra files remain forbidden. No existing immutable bundle is edited.

Frontend consumers use one closed role-to-CSS-variable mapping. They contain no
scheme ID branches or scheme literal colors. A generated default is the sole
exception, generated from the registry with a reproducible identity/check.
Generation is a real build gate, including Docker's Python-to-Node stage handoff.
No new package is needed.

## 2. Private previews and appearance publication

Existing session, authority/origin and CSRF rules apply. Asset IDs never grant
authorization. Protected assets are server-created, bounded canonical bytes,
not arbitrary paths or URLs; return no-store, nosniff and their exact media type.
This covers conversion candidates/cleanup versions, character/card previews and
background drafts. Retain canonical byte responses only where alignment,
download or explicit application needs them; displayed preview URLs are private
same-origin routes. Do not relax CSP.

The background and scene endpoints are the already approved §4.6 endpoints.
Background validation enforces complete PNG/WebP framing, extension agreement,
static single-frame content, 2 MiB input/canonical limits and 640×360 through
2560×1600 bounds before full decode. Metadata is stripped by deterministic
re-encoding. One draft per owner session; replacement/cancel/24-hour expiry makes
the old URL unavailable. Drafts never enter public paths or export.

Appearance publication uses immutable, content-addressed presentation artifacts
and one atomic pointer. Identity includes the source bundle, exact sprite hash
and source character/issued appearance revision. Public profile, background reads and
export all capture matching identity. A request for a stale background revision
returns 404 rather than newer bytes. A new evidence bundle invalidates the old
association; it does not carry old FAQ approval forward.

Preview/apply invokes zero providers. Applying changes only scene settings,
never other unapplied portfolio text, claims or character candidates. Apply uses
compare-and-swap against the expected source bundle, character/appearance and
saved-draft identities. Asset validation and complete candidate verification
precede pointer publication. Coordinate the saved scene settings and pointer
with a recoverable transaction/journal; failure and restart restore a complete
old or new state. Define and test lock ordering before adding cross-store writes.
Do not use full `LocalPublication.prepare()` for appearance changes. Main
allocates any required new migration; existing migrations are immutable.

### Batch 2 integration details

The existing process-wide reentrant portfolio lock is the single mutation lock
for saved portfolio drafts, appearance settings, recovery and appearance-pointer
reads. Reuse it rather than adding an independent lock with inverse ordering.
Acquire a bundle lease first; its acquisition releases the bundle-manager lock.
Do not acquire the portfolio lock inside a bundle activation hook. A captured
appearance must match the leased bundle and canonical sprite hash before it can
overlay that bundle. Recheck active source identity before committing an apply.
Binding prevents a concurrent evidence activation from receiving stale tokens.
The final saved-draft replacement and SQLite commit use the bundle manager's
existing lock through `guard_active_bundle()` so activation cannot occur between
the check and commit. Acquire that guard before beginning the SQL transaction;
never wait for the manager while holding a SQLite writer transaction.
Two concurrent applies must compare the current locked pointer as well as their
captured snapshot, including when there is no saved draft to supply a revision.

An apply request contains the approved proposed settings and required expected
source bundle, character revision, appearance revision and saved-draft revision
(nullable only when no saved draft exists). A mismatch returns HTTP 409 with
`SCENE_CONFLICT` and preserves both the public pointer and unrelated draft
content. The owner reads these expected identities from the authenticated
`scene_state` in the existing `GET /api/admin/portfolio/status` response. That
private state also includes the canonical source sprite SHA-256. Preview returns
`{scene, notices}` and no new public fields.
Neither preview nor apply accepts an arbitrary character, image path or URL.
The source character is always the already active canonical public character.

Use a bounded private recovery journal containing complete old/new saved-draft
and appearance-pointer identities. Persist and verify the candidate first, then
the journal, then the saved scene settings and atomic pointer. Recover under the
same lock before reads/writes. Before the committed pointer, rollback restores
the old draft/pointer; after it, recovery completes the new pair. Injected I/O
failure at each boundary must prove this rule. A monotonic appearance issuance
counter prevents a reused `rev` from naming different background bytes.

Mutation routes that create protected preview assets gain existing CSRF checks;
all callers are updated together. An asset response may retain canonical bytes
for conversion/alignment/download/application, but its displayed URL must be an
authenticated `/api/admin/assets/...` resource. Wrong-session, expired/revoked
session, replaced/deleted/expired draft and malformed ID return unavailable.
No file path can be supplied by the requester. SVG card previews keep the
existing card renderer's restricted SVG response policy; page CSP is unchanged.
The A1 gateway allowlist includes the exact `/api/public/scene-background` path
for GET, HEAD and existing credential-free OPTIONS/CORS. It shares the applied
revision check and bytes with the primary API; private drafts remain unavailable.
Expired background URLs fail immediately. The existing runtime cleanup lifecycle
also removes expired rows and unreferenced draft bytes at startup and on its
regular interval, including when no analysis batch service is configured. A
closed cleanup failure is retried on the next interval; appearance publication
and unrelated live runtime state are preserved.

Migration 31 (`bound_scene_appearance`) stores one `scene_appearance_state` row
and one `scene_background_drafts` row per session, with a session foreign key.
The stored `character_revision` binds the source bundle's character; the stored
`appearance_revision` is the effective public revision. An overlay sets both
public `character.revision` and `scene.revision` to that appearance revision.
Legacy source revision zero stays valid; issued appearance revisions are positive.
The owner's CAS character revision is the current effective public value.
Issuance starts above the saved counter, source character revision and saved
draft's character revision. Saving an applied scene also advances that saved
character revision without changing its mode, candidate or other authored data.
Subsequent full builds must not reuse a revision for different image bytes.
Scene and recovery-journal JSON are bounded to 65,536 characters; journals hold
server-derived identities/digests, with any complete draft backup kept privately.
The SQLite pointer commit is the apply linearization point. Cleanup or response
failure after that commit cannot restore the old pair. Main allocates later FAQ
and sharing migrations when their seams are fixed; no placeholder tables.

Reuse the existing bundle manifest's per-file records for the image declaration.
At most one additional `public/scene/<sha256>.png|webp` is allowed, exactly when
the validated profile scene declares a background. Its filename hash, manifest
hash and canonical bytes must agree. A missing declared image, an extra image
or any other extra file fails before activation. No new public scene field or
internal manifest top-level key is needed. Bundle verification also checks the
stored stage against the actual canonical sheet; it never recolors stored tokens.

`scene_state.settings` contains the exact applied raw settings, including the
authored accent and automatic dim choice. It must not read an unapplied draft or
invert resolved tokens. The private pointer stores a bounded `{public, settings}`
receipt. Full local builds/reindexes persist an immutable private source receipt
bound to bundle, source sprite and exact public scene before activation, outside
the activation hook. These receipts never enter public bundles or exports.
Older external bundles with a stored scene but no private receipt return null
settings; the UI shows the published result and requires explicit new settings.
Scene artifacts and receipts share the bundle manager's data root, even when a
test or embedded host keeps its runtime database elsewhere. The private state
projects reset defaults from `SceneConfig()` rather than duplicating constants.
Retired aliases use the selected registry's existing validation context. Stored
resolved scenes survive a later registry version or declared successor ID, even
when the successor has the same version number; reading never recolors them.
Exact re-resolution binds settings to tokens only when the stored scheme ID and
version still match the selected registry. Independent public contrast and
canonical sprite/image checks always apply. Editing exposes the declared
successor; an explicit Apply publishes its new tokens.

Public profile, image, entrance policy and export reuse
`app.state.scene_supplier` and its `published_profile()` context. Each snapshot
holds one bundle lease for the complete read and captures the matching pointer
under the portfolio lock. It supplies the complete bilingual document, effective
revision, sprite/image bytes and source identity. Missing/corrupt active data
fails closed with `PUBLIC_SCENE_UNAVAILABLE`; an empty setup may use defaults.

The publication status remains available before the first bundle: its private
`scene_state` is null. A corrupt active scene still fails closed. The primary
public entrance and gateway use the dedicated visitor build when present;
administration keeps its own entrance. Legacy builds remain readable on the
private primary host. Removed legacy global character scaling and scoped
conversation styles keep preview, live and export geometry/tokens consistent.

## 3. Shared page and mode policy

One pure visitor page is used by live, static export and owner preview. It has no
fetch/provider effects; external controllers supply data, state and callbacks.
Keep existing SSE events, cancellation, successful history limits, synchronous
duplicate admission and stale-response guards. Locale changes preserve turns.

Implement §4.0's sidebar/drawer, top bar, empty-conversation hero, chat bubbles,
collapsible sources and pinned input. All NPC positions use the same canonical
CharacterRenderer. Only the newest answer animates; old answers and reduced
motion show a static frame. Media-query listeners are cleaned up. Mobile drawer
supports keyboard, focus containment, Escape and focus return without overflow.
Preview instances have isolated IDs/tokens/focus and explicitly marked examples.

The admin guide reads the active canonical character and applied light stage,
never an unapplied character preview. Appearance uses the existing publication
status poll. UI drafts with unsaved edits must be saved before applying appearance;
after application, the UI reads the actual saved draft and revision without
overwriting edits made during that read. Apply waits for the displayed saved-draft
identity to agree. Preview settings remain editable, and stale preview responses
cannot authorize newer settings. Operation admission is synchronous; teardown,
locale and source changes abort requests and discard stale UI responses.

Both resolved variants are present. The external same-origin head script receives
the current owner mode/toggle policy before first paint and ignores stored mode
when toggling is forbidden. One localStorage key holds only visitor light/dark
choice. It is never sent, exported as a user preference or stored in a cookie.
The owner preview uses explicit controls, independent of that preference.

The dedicated visitor entry includes exactly one `data-owner-mode="system"` and
`data-visitor-toggle="true"` marker on its opening HTML element. The private
administrator entry has no visitor policy markers or bootstrap and remains
readable when the published appearance is unavailable. The shared
`render_visitor_document` replaces those closed values with published policy;
it never interpolates owner text. An external classic `scene-mode.js` runs in
the head before stylesheets. A1 serves that exact build asset. Local, gateway
and exported entry documents use the same marker contract.

Image placement is hero-only. Decorative alt is empty; text uses an opaque
surface. Focus, scaling and registry-derived dim behavior have the same result
in preview/live/export. The appearance controls include the five data-driven
half-light/half-dark miniature cards as a native radio group, mode/toggle,
advanced accent/reset, file selection and drag/drop, removal, and a focus
thumbnail operated by click, drag or arrow keys. Its simultaneous desktop/phone
crop outlines use natural image dimensions, focus and the real shared page's
hero geometry at the existing 1440px/375px reference widths.
Settings changes start a cancellable bounded debounce of the existing private
preview endpoint. Only the matching resolved proposal enables Apply. A late
response cannot overwrite newer settings or survive cancellation, teardown,
locale or source changes. Explicit Applied/Proposed comparison remains available.
The large preview can show empty welcome or conversation, available or resting,
character states, reduced motion, either viewport and either color variant.
Adjustment notices show the actual resolved value and a localized plain reason.
Answer avatars inherit published frame duration and movement; only the newest
answer animates, including idle, unless reduced motion is enabled.
Sidebar language/stars/forks come from fetched public snapshot metadata; missing
values are not invented. Do not proxy arbitrary avatar URLs or broaden img-src.
The producer carries nullable `language` (at most 100 characters), `stars` and
`forks` (integer 0–2,147,483,647) through both the existing GitHub resolver and
local archive metadata lane. Both locale DTOs contain the same snapshot values;
older bundles may omit them. No new metadata request is introduced.

## 4. FAQ and export snapshot

Reuse A4's validated answers and citation projection. Owner question variants
have bounded count/length and participate in optimistic revision and approval.
Changing variants withdraws approval until explicitly reviewed; answers cannot
be freely edited. The offline match policy is exact equality (owner decision B,
2026-09-30). The export manifest's `schema_version` identifies the static format;
FAQ payloads contain no separate matcher configuration. Input and each approved question or
approved variant are normalized only by NFKC, lowercase, whitespace collapse and
removal of trailing `? ？ ! ！ 。 . ， ,`. The existing answer is shown only when
the normalized input equals exactly one approved row; otherwise at most three
nearest questions are shown. Typos, reordering, respacing and paraphrases are
deliberately not answered offline. No embedding, generation or input upload
occurs offline.

The owner reaffirmed this exact rule for backend variant deduplication on
2026-10-01. The admin validator, public/export projection and browser matcher
use the same equality: internal spaces, separators and identifiers remain.
Whitespace means ECMAScript WhiteSpace/LineTerminator characters, matching
the browser's `\s`; Python-only NEL/control separators are not collapsed.
No phrase-specific exception or fuzzy acceptance is introduced.

The owner reaffirmed this exact rule for backend variant deduplication on
2026-10-01. The admin validator, public/export projection and browser matcher
use the same equality: internal spaces, separators and identifiers remain.
Whitespace means ECMAScript WhiteSpace/LineTerminator characters, matching
the browser's `\s`; Python-only NEL/control separators are not collapsed.
No phrase-specific exception or fuzzy acceptance is introduced.

On the Pages share site, live chat is available only when the gateway status
reports `chat_available` for the exported bundle; a bundle mismatch disables it.
The page POSTs `{message, locale, history}` (bounded successful history, same
limits and single 413 retry as the local site) with `credentials: "omit"` only to
the integrity-checked, CSP-matched manifest `gateway_origin` at
`/api/public/chat/stream` (owner decision A, 2026-09-30).
The shared POST rejects HTTP redirects before forwarding any body, including
the bounded 413 retry. A redirect is an ordinary failed delivery and cannot
admit a successful exchange or trigger an automatic replay.
The shared POST rejects HTTP redirects before forwarding any body, including
the bounded 413 retry. A redirect is an ordinary failed delivery and cannot
admit a successful exchange or trigger an automatic replay.

Both typed offline questions and FAQ chips revalidate through the existing locale-only public FAQ GET; the
visitor question is never included. A synchronous controller prevents duplicate
admission and discards responses after locale/profile changes. A known rejected,
withdrawn or revised FAQ observation survives later network failure; only the
initial unavailable gateway may use the integrity-checked export snapshot.
Known bundle mismatch remains latched until a successful authoritative status
check clears it. Public status and FAQ GETs have a 10-second read deadline
covering headers and the body. Parent cancellation stops pending reads; timers,
listeners and body readers are released. An initial static FAQ timeout may use
the integrity-checked export, while known withdrawal, rejection, empty FAQ and
bundle mismatch remain effective across later timeouts. No question or history
is sent in these locale-only reads.

GitHub-origin owner citations preserve their indexed immutable GitHub permalink,
bound to repository, revision, path and lines. Export verifies the full citation
against indexed evidence; only index-confirmed local-origin statements are copied.
Static live local-owner citations use the copied immutable statement when its exact
revision/evidence path occurs in the export manifest, otherwise the exact
validated gateway origin. During a subsequent network outage, answers requiring
a local-owner statement absent from the export are excluded. Invalid owner routes,
mismatched revisions and unsafe citation URLs are rejected. Root/project hosting
use the same relative copied-statement paths. Public profile parsing bounds all
nested data and closes scene token names, color values, revisions, image routes,
statistics and public links before those values reach DOM/CSS.

Migration 32, `reviewed_faq_question_variants`, adds `variants_json` to existing
`faq_entries`, with an empty-array default. Database constraints require valid
array JSON, at most eight items and 2–8,192 characters. Python validates each
trimmed, nonempty string at at most 200 characters and rejects normalized
duplicates or a variant equal to the primary question. Existing approved rows
keep their answer, citations, approval and revision during upgrade. Migration
failure rolls back both schema and rows.

`PUT /api/admin/portfolio/faq/{entry_id}/variants` accepts only
`{bundle_id,revision,variants}` through existing authentication, same-origin and
CSRF controls. It checks the current bundle and optimistic revision, replaces
only variants, increments revision and sets review state to pending. It cannot
edit an answer or implicitly approve. `FAQ_CONFLICT`, `FAQ_STALE` and
`FAQ_VARIANTS_INVALID` are the closed failure codes. The existing explicit
review action approves the resulting candidate. Public/export projection adds
only approved-current variants. Variant validation runs at the write boundary;
reads decode the stored JSON under migration 32's constraints without repeating
write-time validation. `FAQ_VARIANTS_INVALID` applies to invalid variant writes.

Export captures one bundle lease, both locales' approved-current FAQ in one
SQLite read transaction, exact appearance and sharing configuration. FAQ edits
after the first read belong to the next export; they cannot mix the two locales
or invalidate the captured snapshot. Recheck bundle, appearance and sharing
identities at completion or fail with conflict. Export only the dedicated visitor build dependency closure,
public JSON, canonical character/cards/applied image, actually cited public
owner assertions, .nojekyll and public export-manifest.json. Do not copy the
full dist, admin chunks, index SQLite, config YAML, providers, runtime receipts,
draft assets or the internal bundle manifest.

Canonical JSON, sorted safe relative paths and per-file SHA-256 hashes determine
the export identity. The manifest does not hash itself; archives use stable
timestamps/order. Check schemas, references, symlinks/traversal, secret canaries
and the 1 GB bound (1,000,000,000 bytes) before exposing download. Owner-assertion sources retain
their local revision/evidence identity and work from static hosting. Root and
project Pages use relative assets and the exact validated base path.

Known rejection or known bundle mismatch cannot become fallback after a failed
request. An offline downloaded export is an approved-at-export snapshot; it
cannot promise immediate remote revocation.

## 5. Pages, gateway and card target

A1's exact github.io origin remains the credential-free CORS authority. A5
stores the full HTTPS Pages URL/base path privately and requires its origin to
match A1. URL entered, matching exported content, and owner-reported A1 external
verification are separate facts. Export does not require a running model/Funnel.

Owner-triggered Pages verification accepts only the exact configured github.io
origin and normalized base path. Its bounded HTTPS transport validates DNS and
the actual connection address, rejects private destinations and redirect
expansion, and uses local expected export identity. Verify the entrance and
manifest, not a self-asserted remote hash. A changed Pages URL clears verification;
local bundle, appearance, FAQ or gateway-origin changes do not. Private
administration/model origins do not
enter the artifact. Static connect policy allows only the configured gateway;
requests use credentials omit. Administration CSP is unchanged.

The dedicated Pages read reuses provider DNS-set validation with private access
disabled and the existing pinned TLS context/original server name. Both the raw
and TLS peer must be public and match the pinned IP/443. Four pending OS DNS
calls are the maximum; their slots stay occupied until the resolver completes.
Entrance and manifest reads share one absolute operation deadline. A socket
shutdown timer covers slow headers and body chunks, including a response that
closes its HTTP connection after handing the socket to the response reader.
The primitive accepts at most 30 seconds remaining and 4 MiB per resource;
the service may impose smaller limits. Redirects, non-200 responses, compressed
or oversized responses fail closed. It sends no credentials, Cookie or
Authorization header and returns no remote body in an error.

The owner-approved 2026-10-12 [README export amendment](PROFILE_README_EXPORT_CONTRACT_2026-10-12.md)
makes complete README download the final sharing primary action. It uses the
verified snapshot and checked Pages GIF, while the manual card-image upload and
copy-block path remains available. A5 Markdown points to the corresponding
verified Pages URL only. No GitHub write or public activation occurs.

Migration 33, `pages_sharing_state`, stores the configured Pages URL and the
three fields describing the last successful remote verification. It has no
export receipt, settings revision or export timestamp. Export is deterministic:
it rebuilds the public files and manifest for the current snapshot, while
verification rebuilds the same expected bytes instead of trusting an
intermediate record. No conversation bodies, credentials or archive bytes are
stored.

The existing authenticated same-origin admin router owns these private routes;
writes require the existing CSRF token and closed request schemas:

- `GET /api/admin/sharing/state` returns current private settings and the
  verification fields with `no-store`; it builds no ZIP and performs no public
  fetch.
- `PUT /api/admin/sharing/pages` accepts `{pages_url}` and normalizes only a
  safe HTTPS path under A1's exact configured github.io origin. A changed URL
  clears the three verification fields. This is last-write-wins; no revision
  CAS is used.
- `GET /api/admin/sharing/export` requires the admin session, has no side
  effects, and returns the checked `reponpc-site.zip` as a no-store attachment
  with `Content-Disposition`, `nosniff`, and (optionally) the public export
  digest. The frontend uses a native `<a download>` link; it does not create a
  Blob URL and the endpoint has no CSRF requirement because it is a read-only
  GET.
- `POST /api/admin/sharing/verify` accepts an empty body; it fetches only the
  configured entrance and sibling manifest under one 20-second absolute
  deadline. The entrance is at most 1 MiB and the manifest at most 4 MiB. The
  expected manifest bytes and the entrance bytes must match the local
  deterministic export. A match writes `verified_pages_url`,
  `verified_content_sha256`, and `verified_at`; a mismatch clears verification
  and returns `SHARING_VERIFICATION_FAILED`; transport failures return
  `SHARING_VERIFICATION_UNAVAILABLE`. The write is conditional on the URL still
  being unchanged, which is the only required mutation race; a changed URL
  returns the retained `SHARING_CONFLICT` error.

The export digest is the public manifest's canonical file-record identity, not a
remote assertion. Local bundle, appearance, FAQ, or gateway-origin changes do
not automatically clear verification; the owner re-exports and verifies when
the published snapshot should change. Only the current verified URL selects the
A5 card target. A prepared ZIP is offered through a visible localized native
download link; preparing the link does not prove that the browser saved it.

## Verification and completion

Requirements: FR-047/050/051/052, applicable FR-015/018, NFR-001/009/011;
AC-068/072/073/074/075/079, preserving A1 AC-071 and A4 approval boundaries.
Each batch reports changed paths, commands/exit codes and limitations. Main
reviews the actual diff and runs independent tests before continuation.

Run relevant focused tests, then Python format/lint/mypy/full tests, frontend
format/lint/type/unit/build, registry generation/source guard, deterministic
export/security/bundle rollback checks and both isolated Docker smoke cases.
Use fresh build output if the old dist has ACL problems. Browser checks use real
production components/API plus a separate static server and stoppable synthetic
gateway; cover bilingual desktop/mobile, zoom, keyboard, modes, reduced motion,
preview parity and offline transition. Record all unavailable/failed checks.

Only local A5/R08 implementation and verification may be marked complete here.
The local static browser fixture maps its exact synthetic HTTPS gateway to a real
stoppable loopback listener with a test-only service worker. Original controllers,
payloads, SSE and exported files are preserved; only fixture Host/Origin transport
and corresponding CORS response headers are mapped. Optional same-origin audit
scripts instrument HTML responses without changing saved artifacts or their CSP.
These mapped local checks do not establish external HTTPS transport. Unregister
the test worker, stop fixture processes and reset the viewport after the run.
Real Pages upload, external Funnel/Profile flow, clean-host and full release
acceptance remain A12 and must be reported as not run.

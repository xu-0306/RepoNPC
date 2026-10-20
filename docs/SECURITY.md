# RepoNPC Security Model

**2026-10-12 README approval (OR-033 / ADR-059):** The [README export contract](PROFILE_README_EXPORT_CONTRACT_2026-10-12.md) preserves FR-016/022/024 and NFR-001/002/003/009 boundaries. The private readonly download uses the confirmed public snapshot and fixed verified Pages card URL through the existing bounded, credential-free transport. Owner text and links are escaped; stale or mismatched content and oversized output are rejected. No provider call, GitHub write, database mutation or public-release acceptance is implied.

**2026-10-03 A11 approval (ADR-054 / OR-028):** Web maintenance downloads are
password-encrypted ciphertext, not an exception permitting browser access to
admin hashes or raw SQLite. See §23 and Specification §11.7. The owner approved
same-original-data-directory restoration; real runtime/external activation is
outside the verification work.

**2026-10-03 built-in model boundary (FR-049 / AC-070):** private authenticated,
same-origin/CSRF-protected download requests require exact boolean consent. Only
the packaged eight-file official manifest is accepted. HTTPS redirects remain on
Hugging Face/CDN hosts; every hop validates public DNS addresses, pins TLS to the
validated destination, limits redirects/deadlines and rejects duplicate headers.
No credential, proxy environment or arbitrary destination is used. Streaming
size/range/hash checks, private staging, link/alias checks, cancellation and atomic
publication precede provider loading. Failures preserve the existing active
bundle. Signed CDN URLs, model paths and upstream bodies are never returned/logged.
The CPU adapter loads lazily after explicit owner choice, disables ONNX telemetry,
is shared under a lock and closes after model/reindex work on shutdown. Device
checks return numeric nullable hardware observations and authored packaged catalog
facts only, and make no network requests. Catalog source/license links are public
authored data, never saved provider addresses. The owner-only model cards and form
handoff expose no key, host identifier, prompt or raw output and cannot download,
test, save or activate a model automatically. See the
[A7 card contract](A7_MODEL_CARDS_IMPLEMENTATION_2026-10-03.md).

The private administrator HTML is independent of published appearance parsing.
Missing image files, invalid appearance wrappers and invalid recovery journals
must not prevent the private admin entrance or authenticated session resume.
Public scene/profile reads still fail closed with safe existing error codes;
the last bundle pointer and private Host/Origin boundary remain intact.

**2026-09-29 A5/R08 implementation boundary (in progress):** Character and card
preview responses use session-scoped `/api/admin/assets/previews/{asset_id}`
resources. Creation uses existing same-origin authorization and CSRF; reads
require the creating live session and return `no-store`/`nosniff`. Asset IDs grant
no authority. SVG previews retain the shared restricted SVG policy. Canonical
bytes remain available only for explicit conversion/alignment/download/apply
flows; displayed assets use protected URLs. Background drafts use the same
authority boundary, one per session with a 24-hour expiry. PNG/WebP framing and
dimensions are checked before decoding; canonical character/background pixels
are re-encoded without source metadata. Runtime migration 31 binds the appearance
pointer to the leased bundle, canonical sprite hash and issued revision. Public
reads capture one complete bilingual snapshot; stale image revisions cannot
return newer bytes. Private source receipts, recovery copies and unapplied drafts
stay outside bundles and public exports. See the [A5 integration contract](A5_VISITOR_APPEARANCE_EXPORT_CONTRACT.md)
and dated local checks; this partial checkpoint does not close A5 or A12.

A5 public exports contain only the visitor dependency closure, bounded public
JSON and canonical applied assets, plus actually cited immutable owner
statements. FAQ/profile/manifest input is validated before DOM/CSS use; known
withdrawal or mismatch survives a later disconnection. Pages verification uses
the saved exact github.io origin/base path, public-only DNS and pinned TLS peer,
one bounded deadline and the locally expected manifest/entrance bytes. An
owner-triggered README preview/download additionally reads only the fixed
locale GIF under that verified base path and requires its exact expected bytes.
The private receipt is bound to settings, export, bundle, appearance, FAQ and origins;
it is never exported. Static chat POST implementation is stopped pending the
explicit payload/destination authorization requested after automatic review;
FAQ-only output does not constitute completed A5 scope.

**2026-09-28 approved gateway freeze (OR-027 / ADR-053, Specification 0.4.6):** [A1/F0](A1_FUNNEL_GATEWAY_CONTRACT.md) is normative. The production-only visitor listener binds loopback, shares existing services and admits only canonical exact routes and validated visitor build dependencies. Admin/unknown/model routes and credential-bearing requests are 404; no admin dynamic chunk, SPA fallback or Set-Cookie is allowed. Pages CORS is exact, credential-free and public-API-only. Explicit private admin origins bind to request scheme/Host and use a different hostname from Pages/Funnel even across ports. Proxy trust is separate for private/main and visitor listeners; visitor identity defaults to aggregate daily/provider/in-flight protection. Explicit verified loopback-proxy trust requires one strict XFF IP and rejects missing/invalid identities before admission. Actual body bytes and shared intake/generation deadline are bounded; worker slots survive cancellation until actual completion. Visitor status/errors/SSE reveal no provider/model/usage diagnostics. Owner-reported external checks are dated. Configure/start/stop/resume/restart clear all five persisted report fields; bundle/local-readiness changes do not invalidate the observation. The badge requires verified_at and a ready listener, and is never reinstated after restart/restore. Gateway origins are captured at listener creation; visitor requests do not read or mutate owner settings. This closes the former pending F0 contract gate; implementation/tests are in progress and public activation remains unauthorized.

**A4 FAQ boundary (2026-09-28, FR-046 / AC-067 / ADR-048):** Owner queue/review/export routes use existing authenticated same-origin authorization and CSRF for writes, with `no-store`. Runtime migration 29 holds mutable review rows outside immutable bundles; its unused rewrite_json column is cleared on writes and ignored on reads. Regeneration immediately withdraws previous approval and visible candidate bytes; failed/unchecked/stale items cannot be publicly delivered. Public FAQ and JSON export share explicit top-level/entry/citation allowlists and never expose owner diagnostics, drafts, associations, prompts, usage or provider metadata. Visitor chips and offline matching use the FAQ loaded with the profile, with local bundle equality and known status mismatch checks. Mid-session approval withdrawals take effect after FAQ/profile reload. See [A4 contract](A4_COVERAGE_FAQ_IMPLEMENTATION.md).

**2026-09-26 character scene (ADR-049, Technical Specification 0.4.1, AC-073):** The optional owner scene background is a new untrusted upload path.

- It accepts PNG or WebP only (no SVG, no animation, ≤ 2 MB, 640×360 to 2560×1600).
- It is decoded under the existing image guards, then re-encoded server-side with metadata stripped.
- It is stored directly below `assets/scene/` and served only through `GET /api/public/scene-background` with `nosniff`.
- (ADR-050, 0.4.3) An upload first becomes a private draft in runtime data: owner session required, `no-store`, one per session, deleted on cancel or after 24 hours. Drafts are never served by public routes or exported. Only 「套用」 promotes a draft to a content-hashed file under `assets/scene/`. The scene preview endpoint persists nothing and makes no provider call.
- Scene tokens are validated `#rrggbb` values mapped to fixed CSS custom properties; no configuration or pack can supply CSS text or property names.
- (ADR-051, 0.4.4) The visitor light/dark choice is stored only in the visitor's browser `localStorage`, under one key. It is never sent to the server, exported or set as a cookie. The pre-paint mode script is a same-origin file, not inline, so the CSP is unchanged. Scheme colours come only from the packaged `color_schemes.yml`.

**2026-09-26 completion direction (ADR-048, Technical Specification 0.4.0, AC-068/AC-071):** The Funnel visitor-only gateway is MVP scope. It grants credential-free CORS to exactly the configured GitHub Pages origin for visitor APIs; admin, model and unknown paths return 404 through it. The static Pages export carries only the gateway origin, passes a secret scan and contains no credential or host detail. Visitor responses never include host, hardware, provider, model or cost information. The built-in `bge-m3` artifact is downloaded only after owner consent from a pinned source and activated only after checksum verification. The Windows installer is unsigned; SHA-256 checksums are published.

**2026-09-24 planned Tailscale Funnel ingress (ADR-047):** [The deployment plan](TAILSCALE_FUNNEL_DEPLOYMENT_PLAN_2026-09-24.md) selects a future `*.ts.net` visitor URL through a visitor-only gateway. Until its route, admin-origin, proxy trust and credential contracts are approved and tested, the current private-admin boundary remains unchanged. A Funnel pointed at the complete application listener is not an approved public deployment.

**2026-09-22 local-publication amendment (ADR-046):** The owner authorized implementation of the local-first NPC and guided GitHub card journey. [Local publication contract](LOCAL_PUBLICATION_CONTRACT_2026-09-22.md) supersedes GitHub-only configuration/build/activation transport; all validation, attribution, privacy and last-known-good requirements remain. Implementation/acceptance evidence must distinguish local tests from actual public deployment.

**Automatic alignment amendment (2026-09-22, ADR-045; FR-015/018, AC-020):** Only a chosen, already canonical owner preview is analyzed. Repeated cross-state alpha-geometry agreement may trigger automatic browser-side composition, but its bytes become downloadable/writeable only after the existing authenticated same-origin canonical validator returns them. Per-frame integer X/Y input is constrained to the original cell's opaque bounds; invalid drafts cannot be applied. Failure preserves the chosen unaligned asset, and source files, cleanup alternatives, CSP, authorization, and ordinary GitHub writeback remain unchanged. This supersedes ADR-043's opt-in timing, not its validation boundary.

**Edge-spill cleanup amendment (2026-09-22, ADR-044; FR-015/018, AC-020):** The server proposes an alternative only for an authenticated, bounded structural grid whose shallow top fragment is continuous with the preceding row and separated from current-frame content. The original result remains unchanged; the alternative is independently re-encoded and canonical-validated. Both remain response-only until the owner explicitly chooses a version, and ordinary GitHub writeback revalidates it. No source persistence, arbitrary image URL, extra endpoint, silent deletion, or relaxation of upload/archive/CSP limits is introduced.

**Frame-position repair amendment (2026-09-22, ADR-043; FR-015/018, AC-020):** Alignment analysis and compositing operate only on an already canonical, authenticated preview. Browser-side edits remain drafts; adjusted download and GitHub writeback are blocked until the composed PNG passes the existing same-origin protected `/assets/character/validate` route and the server returns canonical bytes. Opaque pixels cannot be cropped or shifted into another cell. No uploaded source is persisted or overwritten, and CSP, authentication, image limits, and writeback checks are unchanged.

**Novice material discovery amendment (2026-09-21, ADR-041; FR-015/018, AC-020):** PNG, ZIP, and browser-folder inputs normalize into one bounded server-side bundle model. Manifestless bundles are scanned only for the closed 4-by-7 structural shape; filenames, paths, species, and visual content are not semantic signals. Candidate IDs bind normalized path and bytes and are recomputed for selection. Entry/member/expanded-byte/path/pixel/candidate ceilings, path normalization, static-image validation, authenticated same-origin access, and the no-write inspection boundary apply equally to ZIP and folder uploads.

**64px sprite and material-conversion amendment (2026-09-21, ADR-040; FR-015/018, AC-020):** The protected converter accepts bounded static structural grid PNGs or strict manifest ZIPs and emits only a preview/report plus canonical re-encoded PNG bytes. It normalizes archive paths, rejects traversal/backslashes/absolute paths/links/encryption/duplicates/animation/unsafe framing/missing mappings/resource excess, treats extra bounded members as warnings, never executes pack content or infers filenames, and performs no write until a separate owner action revalidates the canonical output.

**Species-neutral character-pack amendment (2026-09-21, ADR-039; FR-015/018, AC-020):** Public YAML may select only a registered pack ID/version and bounded pack-owned string options. Pack renderers are trusted application code and cannot be registered or referenced by path/URL/code through configuration. Unknown identities/options fail closed without fallback, and compiled output passes canonical sprite validation. Custom sheets remain untrusted uploads subject to the existing image controls.

**Owner-approved URL editing exception (2026-09-12, ADR-029; FR-038/040, AC-055/057):** The owner explicitly requested that replacing a managed service URL prefill its saved value. Only `POST /api/admin/model-connections/{connection_id}/edit-endpoint`, guarded by the existing owner session, same-origin check and CSRF, may return `{connection_id, revision, base_url}` with `Cache-Control: no-store`. It accepts no arbitrary URL, reads the exact current encrypted revision, rejects host-managed/unknown connections with 404 and unavailable secret storage with 503, and makes no provider request or mutation. List/detail metadata remains URL-free; API keys, secret references and environment values are never returned. The UI fetches only on the explicit Replace URL action, keeps the result in the active form only, clears it on cancel/toggle-off/teardown, and ignores responses after a form or revision change. Loading disables URL editing/submission; failure permits retry or manual entry. No readback URL may enter browser storage, public drafts, exports, logs or snapshots. This narrow exception supersedes earlier blanket stored-URL readback prohibitions; stored-key prohibitions and destination-change credential rules remain unchanged.

**Owner-approved environment-connection control amendment (2026-09-12, ADR-031; FR-039/040, AC-055/056/057):** Authenticated owners may replace or delete host-managed connection cards. The environment URL/key remain unreadable. Replacement requires a complete new URL and promotes the protected revision to owner-managed; a stored key requires explicit replacement/removal before a destination change, while no-key may remain no-key. Reference-safe deletion persists only a connection ID, `disabled` state, and timestamp so startup cannot recreate the deleted default. Override/suppression state contains no endpoint or credential.

**Owner-approved connection-rebinding amendment (2026-09-13, ADR-032; FR-039/040/042, AC-055/056/057/060):** Effective connection updates rebind only directly referencing editable candidates in the same transaction, clear their old probe evidence, and invalidate affected analysis selection generations. Public-active, previous last-known-good, reindexing, and frozen batch work retain historical revisions. Historical secret rows store only the safe provider label beside encrypted endpoint/key material so pinned work can restore the correct protocol; no endpoint/key becomes readable. Saving does not make a provider request.

**Owner-approved session-resume amendment (2026-09-13, ADR-033; FR-017/029/031, AC-049/050):** An authenticated reload may recover only a still-valid session through empty-body strict same-origin `POST /api/admin/session/resume`. The HttpOnly cookie remains the session credential; the response contains only no-store expiry metadata and a domain-separated session-bound CSRF token held in browser memory. Resume consumes no grant, creates no owner/session, and preserves generic failure, expiry, revocation, Host/Origin, forwarded-header, and deployment-profile controls.

**Owner-approved same-service URL amendment (2026-09-14, ADR-035; FR-039/040, AC-055/057):** Retaining a stored provider key during URL replacement is permitted only when provider plus normalized scheme, case-insensitive hostname, and effective port remain unchanged. Path-only edits such as adding `/v1` stay within that origin. Provider/origin changes still require explicit key replacement/removal. All effective endpoint edits invalidate probe evidence and require explicit retest without automatically contacting the provider. Failed writes preserve existing settings, clear newly typed key text, and return only stable safe errors plus an optional request ID; the initiating form displays one accessible recovery-oriented alert and never exposes secret/private endpoint data.

2026-09-12 novice setup refinement (ADR-029/030, AC-055/058): endpoint retention is an explicit authenticated update intent; URL readback is separate under the owner-approved edit-endpoint exception above. Renaming a service without changing its effective provider/endpoint/key does not rotate credentials or invalidate model tests. ADR-035 clarifies that a same-provider, same-origin path edit may retain the key; provider/origin replacement still forbids implicit transfer. Optional embedding dimensions are discovered only by explicit bounded synthetic query and passage tests; malformed/nonfinite/mismatched samples cannot establish readiness or overwrite a known identity. Runtime migration 19 keeps foreign-key enforcement enabled and rolls back the entire parent/child table rebuild on failure. Installed-model listing is scoped to the selected stored Ollama connection and never accepts arbitrary browser URLs.

Independent fault injection also identified and repaired the existing master-key rotation rollback path: database rollback now runs before its connection closes, and any write failure restores the prior master key before returning `MODEL_SECRET_STORAGE_UNAVAILABLE`. Historical and current encrypted revisions must remain decryptable after failed BEGIN, ciphertext UPDATE, or COMMIT. Synthetic regression probes cover these three failure points; this does not claim crash-atomic file/database rotation across process termination.

**Status:** Security contract aligned with approved Technical Specification 0.3.8; ADR-045 adds validated automatic alignment and bounded pixel inputs without changing writeback trust boundaries
**Audience:** implementation Agents, operators, reviewers, security researchers

## 1. Security goals

RepoNPC must let anonymous visitors ask questions about public portfolio evidence without allowing repository content, visitors, model output, uploaded assets, or upstream services to:

- execute code or tools;
- read or alter server files outside defined data paths;
- write repositories except through the authenticated allowlisted admin path;
- make arbitrary network requests;
- reveal model/GitHub/admin secrets or private service locations;
- invent or redirect evidence links;
- exhaust unbounded model cost or local capacity;
- replace a valid index with an unverified bundle;
- execute active content in the visitor/admin page or README SVG.

RepoNPC cannot make already-public repositories secret, prove the truth of owner assertions, eliminate all model mistakes, or protect an operator who intentionally publishes credentials. It must make these limits visible and fail safely.

## 2. Data classification

| Class             | Examples                                                                                       | Allowed locations                                                                                                     |
| ----------------- | ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Public            | profile, claims, selected repository text, card/character, immutable citations                 | Git, bundle, API, browser, public cache                                                                               |
| Operational       | bundle status, counts, latencies, request IDs, token totals                                    | runtime database, sanitized logs, admin status                                                                        |
| Sensitive         | pseudonymous IP HMAC values, session/CSRF hashes, admin audit metadata                         | protected runtime database/secret mounts                                                                              |
| Secret            | GitHub token, provider key, Argon2id password hash, IP HMAC key, raw setup/session/CSRF tokens | environment, protected runtime database, or secret files as specified; memory as needed; never bundle/browser/log/Git |
| Ephemeral private | visitor question/history, provider prompt/output, uploaded draft before save                   | request memory only by default; not persisted/logged                                                                  |

Owner assertions are public statements, not verified facts. The UI and answer policy must keep that label.

**0.2.2 ingress exception:** A provider key/private URL newly typed by the authenticated owner may exist transiently in the isolated model form and its same-origin request. Stored keys/private URLs are never returned to the browser. This narrow exception does not authorize browser storage, public export, logging, or direct browser-to-provider calls. Section 21 governs it; the older blanket `never browser` wording means no disclosure of stored secrets.

## 3. Trust boundaries

```mermaid
flowchart LR
    V["Anonymous visitor<br/>untrusted input"] --> A["RepoNPC public API"]
    O["Authenticated owner<br/>still untrusted content"] --> B["RepoNPC admin API"]
    R["Public GitHub repositories<br/>untrusted data"] --> I["Actions indexer"]
    I --> U["Untrusted candidate bundle"]
    U --> X["Bundle verifier"]
    X --> D["Read-only active index"]
    A --> D
    A --> M["Configured model<br/>untrusted output"]
    B --> G["GitHub API<br/>allowlisted mutation"]
    S["Server secrets"] --> A
    S --> B
    S --> I
```

Crossing a boundary requires schema validation, size/time bounds, context-specific escaping, and safe error mapping. Authentication does not make configuration, filenames, or images intrinsically safe.

## 4. Threats and required mitigations

| Threat                                                                      | Required controls                                                                                                                                                                                                                                                                                                                                                     | Acceptance evidence    |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| Repository prompt injection                                                 | Evidence delimiters; policy outside evidence; no LLM tools/network/filesystem; output/citation validation; adversarial fixtures                                                                                                                                                                                                                                       | AC-033                 |
| Forged citations/person claims                                              | Request-local IDs only; backend mapping; exact commit/path validation; owner-assertion rule; buffer before public output                                                                                                                                                                                                                                              | AC-011–AC-014          |
| Secret ingestion                                                            | Mandatory path/type exclusions; high-confidence scan; no body in skip logs; public-only repositories                                                                                                                                                                                                                                                                  | AC-004                 |
| SSRF/open redirect                                                          | No fetching repository URLs; configured GitHub/provider/manifest allowlists; redirect and final-host revalidation; private provider URL never returned                                                                                                                                                                                                                | AC-016, AC-030, AC-034 |
| XSS/Markdown/SVG injection                                                  | Conservative Markdown sanitizer; DOM escaping; safe link schemes; SVG XML escaping and element/attribute allowlists; strict headers/CSP                                                                                                                                                                                                                               | AC-014, AC-021, AC-034 |
| Path/archive traversal                                                      | POSIX normalization, no `..`/absolute paths; archive regular-files-only policy; exact asset path allowlist                                                                                                                                                                                                                                                            | AC-027, AC-030         |
| Malicious image/decompression bomb                                          | Byte/pixel/dimension caps; real decode; APNG rejection; metadata removal; safe re-encode                                                                                                                                                                                                                                                                              | AC-020, AC-027         |
| Character-pack configuration injection or unsafe fallback                   | Trusted in-process registry only; bounded opaque string options; exact ID/version resolution; no YAML renderer/path/URL/code hooks; canonical output validation; no fallback                                                                                                                                                                                          | AC-020                 |
| Malicious character material archive, folder, selection, or conversion bomb | Authenticated bounded preview endpoint; strict manifest when present, otherwise structural-only discovery; normalized member paths and content-bound candidate IDs; no links/encryption/duplicates; compressed/member/expanded/path/pixel/count/candidate limits; static PNG framing/decode; no filename/species guessing; no automatic write; canonical revalidation | AC-020, AC-027         |
| First visitor claims or exhausts an uninitialized deployment                | No open registration; loopback uses a host-minted 256-bit fragment-only grant with SHA-256 at rest, two-minute expiry, strict loopback/no-proxy validation, one-use atomic owner/session creation, and relaunch recovery; production retains the 15-minute host setup code and password                                                                               | AC-024, AC-049         |
| Admin credential/session attack                                             | Loopback host capability or production 15–128-character password; common/compromised-password blocklist and Argon2id in production; generic errors; backoff/rate limit; 256-bit sessions; HttpOnly/Secure/SameSite; CSRF + origin/host; idle/absolute expiry; rotation/revocation                                                                                     | AC-024, AC-049         |
| Localhost attack, DNS rebinding, or accidental remote exposure              | Validate deployment profile, bind, public base URL, peer, Host, and Origin as loopback; disable trusted-proxy interpretation; never accept forwarded headers for local launch; refuse unsafe startup; keep grant out of request URL/log/referrer and clear fragment immediately                                                                                       | AC-024, AC-049         |
| OAuth state/token or GitHub connection abuse                                | Existing authenticated RepoNPC session; one-use hashed state; PKCE S256; connection-intent Lax transaction cookie; fixed callback; server-side exchange; numeric account metadata; encrypted credential records; no owner-session issuance                                                                                                                            | AC-041, AC-042         |
| GitHub overreach/conflict                                                   | Fine-grained repo token; fixed branch; exact app path allowlist; expected blob SHA; no auto-merge/delete                                                                                                                                                                                                                                                              | AC-026, AC-027         |
| Cost/availability exhaustion                                                | input/history/output caps; per-IP bucket; concurrency; daily budget; timeouts; check before provider                                                                                                                                                                                                                                                                  | AC-018                 |
| Bundle supply-chain/tampering                                               | immutable release; SHA-256 inside/outside; schema/app/model checks; SQLite integrity/smoke; atomic activation; previous bundle                                                                                                                                                                                                                                        | AC-029–AC-031          |
| Dependency/build compromise                                                 | lockfiles; minimal trusted Actions; pinned action revisions for release; dependency/image/secret scans; SBOM/notice                                                                                                                                                                                                                                                   | AC-037                 |
| Privacy leakage through logs/status                                         | request-ID diagnostics only; HMAC IP identifiers; no bodies/secrets/private URLs; safe public errors                                                                                                                                                                                                                                                                  | AC-035                 |

## 5. Model isolation and prompt construction

- System/developer policy is constructed solely by RepoNPC code and is never loaded from repositories.
- Each evidence record is wrapped in unmistakable data delimiters with source ID, evidence class, and metadata.
- The prompt states that instructions, role markers, JSON, Markdown, or quoted system messages inside evidence have no authority.
- Conversation history is untrusted and cannot introduce system messages.
- The model receives no tokens, server paths, environment values, admin state, or unrestricted URL-fetch/tool interface.
- Model output is a proposal: it is buffered, parsed, sanitized, checked against selected IDs and person-claim policy, and only then streamed to the browser.
- Fixed owner-only INFO event names `chat.answer.no_match.<closed reason lowercased>` are permitted under ADR-064, with no content, identifiers or additional fields and no public exposure.
- For envelope v2, a failed segment is dropped and only a fixed reason code reaches the server's owner-only safe log; rejected text, questions and prompts are never logged or sent to visitors. An envelope integrity failure returns the localized no-match reply without regeneration. Validation failure must not become a reason to expose raw model output.

## 6. Network policy

The application may initiate only configured traffic needed for:

- the stable manifest and bundle asset on the configured GitHub repository/allowed hosts;
- GitHub API calls for authenticated admin reads/writes/workflow dispatch;
- the explicitly configured chat/embedding provider.

It never fetches visitor URLs, repository links, `avatar_url` from the server, Markdown images, citation URLs, or model-requested destinations. Redirects are bounded and every hop/final address is revalidated. Production operators should enforce equivalent egress policy where their platform supports it.

Ollama and vLLM should be reachable through private Docker/network addresses and must not be published to the Internet merely for RepoNPC. For vLLM, a network proxy must allowlist only RepoNPC's required `/v1/models`, `/v1/chat/completions`, and `/v1/embeddings` routes because provider API-key enforcement does not protect every operational endpoint. Public status shows the normalized adapter/health only, not base URLs.

The admin listener follows the same private-network rule. A high/non-standard port is not an access control and does not prevent Internet exposure. Bind the host port to loopback for local use, then use an SSH local-port tunnel (`ssh -N -L 8090:127.0.0.1:8000 user@host`) or a firewall-restricted LAN/VPN (such as Tailscale/WireGuard). When a reverse proxy serves a public visitor site, it MUST deny `/admin` and `/api/admin/*` to public networks and allow them only from the private management network. The proxy may expose visitor routes and the fixed OAuth callback only according to the configured origin and state/PKCE checks.

## 7. Secret and credential handling

- Prefer mounted secret files over `.env` for GitHub/provider/IP-HMAC secrets.
- If both value and `_FILE` are supplied for one secret, startup fails rather than choosing precedence.
- Secret files must be regular files, within configured secret mounts, not group/world readable where the platform exposes modes, and bounded in size. On Windows (ADR-070) the same owner-only rule is checked on the DACL: only the current user, SYSTEM and Administrators may have allow entries, whether explicit or inherited. Windows enforces this in `production` only, so trial data keeps working.
- Setup-code plaintext is returned once to the host CLI and exists only in operator/request memory. Runtime SQLite stores its SHA-256 digest, expiry, and no raw code; reissue invalidates the prior code and successful owner creation deletes it.
- Password plaintext exists only during setup, optional local hash generation, and login verification. Dynamic owners persist only an Argon2id hash in protected runtime SQLite.
- Session and CSRF raw values exist only in request/browser memory; the database stores hashes.
- Error formatting and structured logging apply deterministic redaction to known secret fields and credential patterns.
- Tests use recognizable canary values and assert absence from logs, APIs, bundles, snapshots, and exceptions.
- The `vllm` preset accepts a private HTTP origin only after explicit server-side selection, normalizes to `openai_compatible` for bundle/public compatibility, and keeps both chat and embedding base URLs out of object representations and diagnostics.
- Embedding profile records keep provider/model labels and encrypted credential references separate from public configuration. Probe responses are reduced to safe capability/identity metadata; raw provider bodies, model paths, download URLs, and progress payloads are not persisted or returned.
- Ollama pull/delete is restricted to a curated model ID allowlist and the provider's native API. vLLM and generic OpenAI-compatible profiles have no RepoNPC download path. Arbitrary URLs, local paths, shell commands, and unverified archives are rejected to prevent SSRF, supply-chain injection, and disk exhaustion.
- Managed model keys may enter only through the protected form in section 21. Their encrypted storage is separate from the retired GitHub OAuth/PAT lifecycle; prefer existing mounted secrets for host-managed configurations.

## 8. Web and browser policy

Production is same-origin. Broad CORS is disabled. State-changing admin requests require valid session, `X-CSRF-Token`, and matching HTTPS Origin/Referer. Recommended application headers include:

- `Content-Security-Policy` with self-only scripts/styles/connect sources plus narrowly configured model connections only from server, never browser;
- `X-Content-Type-Options: nosniff`;
- `Referrer-Policy: strict-origin-when-cross-origin`;
- `Permissions-Policy` disabling unused capabilities;
- clickjacking protection through `frame-ancestors 'none'`;
- HSTS at the HTTPS terminator after domain verification.

External GitHub/demo/profile links accept `https` only, render with safe `rel="noopener noreferrer"`, and are never inserted as raw HTML. Admin drafts are treated the same as public content even before save.

## 9. Bundle and filesystem policy

- The application runs non-root with code/read-only assets not writable by the web process.
- Only the configured persistent data directory and temporary staging directory are writable.
- Archive extraction does not follow links or preserve owner/permission metadata.
- Candidate download/extraction has compressed and uncompressed size/file-count limits.
- `index.sqlite` opens in read-only/query-only mode; mutable state uses `runtime.sqlite`.
- Atomic activation never deletes the active/previous bundle before the candidate passes checks and serves a smoke request.
- In-flight requests hold an immutable bundle handle; cleanup waits until it is unused.

## 10. Admin and GitHub permissions

Admin authentication and GitHub authorization are separate capabilities. In `loopback_evaluation`, possession and successful same-origin exchange of a fresh host-minted local-launch grant creates the normal protected session; production uses setup proof plus a local password. A missing GitHub token or OAuth configuration leaves authentication plus local YAML validation, built-in-character preview, character upload validation, README snippet generation, embedding-profile CRUD/probe, and local bundle status available. Only the affected GitHub-backed operations fail closed with `SERVICE_NOT_READY`.

Embedding profile management is owner-authenticated and server-side. Exactly one external profile may be active; a changed profile cannot replace the last-known-good bundle until probe, reindex, checksum, schema, model/dimension, and smoke checks pass. Model pull/delete is available only for curated Ollama IDs and is never a browser-to-provider direct request.

The production fine-grained GitHub token is scoped to the single configuration repository. It needs only:

- Contents: read/write for `reponpc.yml` and character assets;
- Actions: write only if the admin dispatch endpoint is enabled;
- Metadata: read (implicit).

It does not need organization administration, issues, pull requests, packages, secrets, workflows-file write, or access to unrelated repositories. The index-building Action uses its workflow-scoped `GITHUB_TOKEN` and public read access for selected repositories.

Admin audit entries record action/path/commit/outcome/request ID but no body. The application allowlist is enforced even if the GitHub token itself has wider accidental scope.

The reverse proxy/firewall is part of the admin trust boundary: public visitor routes may be exposed, but `/admin` and `/api/admin/*` are private-management routes. SSH/VPN/LAN access is preferred; a non-standard port is not considered an authorization control.

## 11. Privacy and retention defaults

- Conversation persistence is unsupported/disabled in v1.
- Rate identifiers are HMAC-SHA-256 pseudonyms and expire with their windows; raw IPs are not stored by RepoNPC.
- Safe operational/audit retention defaults should be documented and configurable, with 30 days recommended for a personal deployment.
- Active and previous valid bundles remain; older bundles may be cleaned locally, while GitHub Release retention is an operator policy.
- Owners must understand that public profile configuration, claims, selected source excerpts, generated cards, and release bundles are publicly downloadable.

Environment startup diagnostics (ADR-069) may print only deduplicated, sorted issue names and codes. Names must fully match `[A-Z][A-Z0-9_]*`, codes `[a-z][a-z0-9_]*`; invalid fields become `UNKNOWN_VARIABLE` / `unknown_code`. Never print `EnvironmentIssue.message`, values or paths.

## 12. Security verification and disclosure

Before release, CI and manual review must include dependency/secret/container scanning; hostile repository fixtures; FTS injection; XSS/Markdown/SVG payloads; URL/redirect/SSRF cases; archive/path traversal; forged evidence; login/session/CSRF/backoff; GitHub allowlist/conflicts; provider error leakage; safe-log canaries; budgets/timeouts; and last-known-good recovery.

Operators should enable GitHub private vulnerability reporting or Security Advisories for their fork and publish that route in the repository's `SECURITY.md`. Reports should include affected version, reproduction, and impact without placing live secrets or exploit data in a public issue.

On suspected compromise: disable public chat, revoke/rotate GitHub and provider credentials, rotate admin hash and IP-HMAC key as appropriate, revoke all sessions, preserve sanitized logs, inspect configuration/release history, restore a known-good bundle/image, and document cause before re-enabling service.

## 13. Production checklist

- [ ] HTTPS and trusted-host/proxy configuration verified.
- [ ] Admin routes are loopback/private/VPN-only; public visitor routing denies `/admin` and `/api/admin/*`; no unusual-port-only exposure is used.
- [ ] No default credential exists; loopback owner access used a fresh two-minute launcher grant, or production owner creation used a fresh host setup code/pre-provisioned Argon2id hash.
- [ ] Deployment profile is explicit: loopback evaluation has only loopback bind/base URL/peer/Host/origin and no trusted proxy; production/non-loopback setup enforces the 15-character minimum and blocklist.
- [ ] IP-HMAC key generated uniquely; profile-appropriate grant/setup issuance, replacement, expiry, replay denial, and atomic sole-owner behavior verified.
- [ ] GitHub/provider secrets supplied through protected files and least privilege reviewed.
- [ ] Windows production (ADR-070): the data directory, `private\` and `model-secrets` pass the owner-only DACL check; administration stays on loopback.
- [ ] The explicitly chosen external or pinned built-in embedding profile is probed and active; bundle identity matches; no arbitrary model downloader or provider fallback is relied on.
- [ ] Ollama/private services are not publicly published.
- [ ] vLLM is private; any proxy denies non-allowlisted operational routes and chat/embedding models are independently verified.
- [ ] Same-origin/CSP/security headers verified.
- [ ] Public rate, concurrency, timeout, token, and daily budget set.
- [ ] Selected repositories and public owner claims reviewed for sensitive content.
- [ ] Bundle host/repository/redirect validation tested.
- [ ] Active/previous bundle and runtime backup/restore tested.
- [ ] Safe logging canary test passes.
- [ ] Full AC-033 through AC-037 and ENGD-001/002/003/006 release evidence recorded.

## 14. Guided-onboarding security extension (0.1.4)

This section is normative under the owner-approved OR-010 and Technical Specification 0.1.4 amendment.

ADR-021 and Technical Specification 0.1.7 supersede only this section's original synchronous/ephemeral execution lifecycle. The selected-only source boundary, explicit owner action, untrusted-input handling, no-fallback rule, owner-confirmation boundary, and raw-data cleanup remain normative. Current lifecycle and durable-safe-state rules are in section 16.

- Public repository listing is authenticated admin functionality but uses unauthenticated GitHub public metadata requests. The configured writeback token is never sent for discovery and its repository scope is not broadened.
- Username/profile and manual repository inputs normalize only GitHub.com identities. Every API URL, redirect, final host, response size, page number, and request deadline is server-validated. Missing/private/inaccessible repositories share one non-disclosing result.
- Metadata listing is not consent to fetch source. Only exact checkbox-confirmed slug/ref/include/exclude identities may cross into source resolution. A batch contains 1–50 confirmed repositories; the legacy compatibility route accepts one and delegates it to a one-item batch.
- Each item creates unique bounded staging, reuses mandatory exclusions/secret detection/symlink and binary rules, and removes staging after every terminal or recovery path. Runtime SQLite stores no archive, repository body/tree, prompt, provider body, incomplete output, or staging path. It may store only the bounded safe batch metadata/events/cache identities and validated normalized terminal results defined by section 16.
- Failed batch items may additionally retain one application-owned reason from the closed set `NO_ELIGIBLE_CONTENT`, `PROVIDER_OUTPUT_SCHEMA_INVALID`, `PROVIDER_EVIDENCE_ID_INVALID`, `PROVIDER_PERSONAL_INFERENCE_REJECTED`, or `PROVIDER_OUTPUT_LIMIT_REACHED`. These values interpolate no provider text or repository data. Unknown reasons are dropped before persistence; the authenticated no-store snapshot and UI expose only allowlisted code/reason values and fixed bilingual explanations. ADR-034 / migration 24 adds only the fixed output-limit reason, not raw termination metadata or provider text.
- Authenticated repository analysis uses its own positive output policy (default and hard maximum 16,384 under ADR-055), configurable active-work/provider/archive/source ceilings, and shared provider admission. Capacity waits do not spend active work. Transient rate-limit/timeout/unavailable failures may retry only the same frozen provider/model up to three total attempts; authentication, context, validation and output-limit failures do not retry, and fallback remains forbidden. Reserve complete prompt/evidence/ID/schema/framing input together with output before generation. Context shortage fails safely. Visitor chat/probe output is independently bounded at 16,384-default / 16,384-maximum; explicit lower settings remain valid. Reject output-limit termination before parsing and never publish/cache truncated content, even when it forms valid JSON. Analysis cache identity includes the budget, reasoning controls and generation/validation policy, preserving incompatible old results only under their old identity. Oversized individual archive files remain body-free and become `FILE_TOO_LARGE` skips; total archive limits, path/type validation and decompression-bomb defenses remain fail-closed.
- ADR-055 keeps supported Ollama reasoning ON and combines reasoning plus answer within one finite generation ceiling. Unknown controls retain the backend default without a guessed capability or silent reasoning disable. Native context is a capability upper bound, not permission to allocate it in full: the configured context (default 32,768), any smaller verified native cap, complete UTF-8 input/schema, framing reserve and output govern admission. Context estimation without the model tokenizer is not measured usage. `message.thinking` is untrusted private provider material and is discarded; it MUST NOT enter answers, SSE, diagnostics, logs, caches, runtime rows, browser storage, bundles or exports. Only final content crosses the existing envelope/evidence validation boundary. Existing deadlines and no output-limit retry/fallback rules remain mandatory.
- Repository content remains delimited untrusted evidence. The model still has no tools, GitHub/network/filesystem access, credentials, or arbitrary URLs. Only the configured provider/model may run; failure never triggers fallback.
- Provider-consuming analysis and contribution suggestion require authenticated same-origin intent plus CSRF and share the global generation semaphore. The UI must identify the action as capacity/provider-consuming before the request.
- Contribution suggestion keeps its fixed 700-token output policy independently of visitor and analysis request budgets. Before generation, admission reserves the complete bilingual messages, exact contribution schema, effective output allowance and framing margin; insufficient context fails before any provider call. Output-limit termination is rejected before parsing with the closed safe reason `PROVIDER_OUTPUT_LIMIT_REACHED`, including syntactically valid partial JSON, while a complete invalid shape uses `PROVIDER_OUTPUT_SCHEMA_INVALID`. Neither path retries, falls back, records raw output or promotes partial content.
- A model result cannot cross the owner-assertion boundary by type conversion alone. The browser displays the original owner statement beside each proposal and records a separate accept/edit/reject action. Unconfirmed or rejected text is excluded from YAML generation.
- The browser validates the exact contribution response shape and binds each asynchronous request to the current request generation, selected repository and original owner statement. Selection or statement changes invalidate pending results. Editing a confirmed proposal creates a new unconfirmed version; it cannot enter YAML until the owner confirms that version again.
- Browser `sessionStorage` may contain only selected public slugs, owner-entered public draft statements, and confirmed suggestions for authenticated-session resume. Logout and successful save clear it. Session/CSRF tokens, credentials, raw repository bodies, raw prompts/outputs, and private provider URLs are prohibited.
- Copy/download is local and non-mutating. The generated file receives the same config validation as a saved draft and must never include deployment secrets or inferred unconfirmed claims.
- Security verification adds SSRF/redirect/account pagination, selected-only source access, no-token discovery, staging cleanup on cancellation/restart/expiry, one-active-owner-batch enforcement, compatibility-route delegation, prompt injection, no-fallback, owner-confirmation, Web Storage canaries, and no-model ordinary preview cases from AC-038 through AC-046.

## 15. Legacy GitHub identity and connection extension (0.1.6–0.2.0; superseded by 0.2.1)

This section records the migration source. ADR-028 removes these reachable OAuth/PAT behaviors; section 20 is normative for the replacement.

- OAuth Web Application Flow uses a fixed allowlisted GitHub authorization/token/user endpoint set, a random one-use state hash, PKCE S256, server-side code exchange, an existing RepoNPC session binding, and a connection-intent short-lived cookie. The normal session cookie is not the sole proof during GitHub's cross-site return.
- OAuth state, PKCE verifier, local session binding, and connection metadata are encrypted or hashed at rest. Tokens and PATs use a dedicated authenticated-encryption key that is independent of IP hashing, provider keys, OAuth client secret, and writeback token.
- OAuth requests no repository scope. Reported broad scopes, token/user endpoint errors, invalid user IDs, redirects, expiry, replay, wrong intent, missing RepoNPC session, and legacy login/setup starts all fail closed without issuing a session or consuming production setup/local-launch proof.
- The browser receives an authorization redirect and safe connection state only. It never receives access/refresh tokens, PATs, encryption keys, client secret, transaction verifier/state, token fingerprints, or raw upstream payloads.
- `identity_public_read`, `public_read`, and `writeback` are distinct credential purposes. A revoked/401 read credential requires explicit reconnection and cannot trigger selection of another credential. The configured writeback token is never copied into runtime credentials or used for identity/read preflight.
- GitHub is connection-only. It cannot create, authenticate, or recover the RepoNPC owner. Disconnecting it affects only public-read work. Production recovery uses host-only `reponpc admin set-password --data-dir <dir>`; loopback recovery mints a new local-launch grant through the launcher.

## 16. Bounded GitHub resolver and batch extension (0.1.7)

- Batch analysis is public-repository-only. Bounded unauthenticated REST metadata is an eligibility gate, not merely a hint: missing, private, inaccessible, unconfirmed, duplicate, or policy-disallowed archived repositories are rejected before archive access.
- Discovery, resolution, and archive requests carry no OAuth/PAT/writeback authorization. The separate writeback credential is structurally unavailable to the resolver and cannot be selected as a fallback.
- Resolver archives are requested only by a validated full commit SHA. Every redirect and final URL must match the exact allowlisted codeload owner/repository/archive-format/full-SHA identity; unrelated repositories, SHAs, malformed paths, query/fragment/userinfo, hostile hosts, and second redirects fail before body consumption. Archive readers also reject absolute/parent/backslash paths, duplicate normalized paths, non-regular entries, symbolic/hard links, devices, oversized compressed/expanded streams, excessive entries/files, and deadline/cancellation violations. No raw archive or staging path is included in an API response, event, log, or runtime row.
- GitHub rate metadata is sanitized and stored centrally. Anonymous REST/core budgets, reset timestamps, `Retry-After`, and secondary-limit pauses govern admission; the scheduler does not spin, repeatedly probe rate endpoints, or leak upstream headers to the browser.
- Durable batch state and the bounded resolution cache store only safe IDs/metadata, immutable commits, stage/state, bounded counts/timestamps, retry reason, event payloads, expiry, and validated normalized terminal results. They never store repository bodies, archive bytes, prompt bodies, provider bodies, credentials, or raw incomplete model output. Cached exact-SHA resolution permits forward progress across anonymous rate resets without ref drift.
- Each item owns a unique bounded staging directory. Cancellation, expiry, startup recovery, validation failure, and terminal transitions remove it. A restart can repeat immutable local work, but a generation already dispatched becomes `needs_retry_confirmation` and cannot be automatically resent.
- Cache records are checksummed before reuse and include the complete identity vector: commit, include/exclude policy, parser/exclusion version, embedding identity, chat model, prompt version, output-schema version, and validation version. Cache eviction is TTL/LRU only and cannot delete active/previous immutable bundles.
- Provider permits are acquired around the actual embedding/generation call, not archive/download/local work. Public chat has weighted-fair admission ahead of batch work so admin analysis cannot turn into a denial of service.

## 17. Legacy GitHub OAuth setup (0.1.8–0.2.0; removed in 0.2.1)

This historical section is retained only to explain migration scope. OAuth setup, callback, connection, and browser-entered public-read PAT controls are removed; compatibility routes return `410 GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED` and never process credentials.

## 18. External embedding and private-admin extension (0.1.9)

- ADR-048/052 supersede the former external-only requirement: a ready deployment may use the explicitly chosen checksum-verified built-in CPU embedding profile or an external embedding provider. Chat and embedding identities are independent; a chat model or `/v1/models` response alone does not prove embedding capability. Probe must include a bounded sample embedding and verify dimension, normalization, prefixes, and model identity before activation.
- Only one profile may be active. Profile changes trigger an explicit reindex state and atomic last-known-good switch; a failed/cancelled probe or reindex cannot deactivate the known-good bundle.
- Ollama model operations are constrained to a curated model-ID catalog and native provider endpoints. vLLM/OpenAI-compatible profiles are connect/probe-only. Arbitrary URL/local-path downloads and provider-supplied shell commands are forbidden.
- Admin routes are private-management routes. Loopback plus SSH tunnel or a firewall-restricted VPN/LAN is the default; a non-standard port does not reduce exposure. Public reverse proxies must deny `/admin` and `/api/admin/*` to Internet clients.
- Security tests cover profile CRUD/single-active races, probe/reindex rollback, model-download allowlists, SSRF/path traversal/disk exhaustion, password profile boundaries, SSH/proxy route ACLs, and absence of provider secrets/private URLs in all outputs.

## 19. Passwordless loopback launch (0.2.0)

- The local launcher creates a random 256-bit grant only after readiness. It stores only a SHA-256 digest, expires it after two minutes, replaces any prior unused grant, and opens it only in the `#local-launch=` fragment. The grant is never placed in a query string, request/access log, cookie, persistent browser storage, diagnostic payload, screenshot, or fixture.
- The frontend exchanges the fragment exactly once through same-origin `POST /api/admin/session/local-launch`, calls `history.replaceState` before rendering any external navigation, and retains only the returned CSRF value in memory. Failed/replayed values are cleared and produce one safe relaunch instruction.
- Without a fragment, the frontend first calls empty-body `POST /api/admin/session/resume`. The endpoint requires the valid HttpOnly cookie and the same strict host/origin/private-admin boundary, returns only `Cache-Control: no-store` CSRF/expiry metadata, and never consumes or recreates a launch grant. The 256-bit pseudorandom CSRF is derived from the session token with a domain-separated server HMAC, so reload can reissue it without browser persistence or invalidating another tab. Existing stored random CSRF remains accepted only for its original session lifetime.
- The backend enables this endpoint only for `loopback_evaluation` after validating loopback bind, loopback public base URL, loopback peer, allowlisted `Host`, same-origin request, and disabled trusted-proxy interpretation. `Forwarded` and `X-Forwarded-*` cannot upgrade a request to local. Any unsafe combination fails startup or returns one generic denial.

## 20. GitHub public-read credential retirement (0.2.1)

- The product accepts no GitHub OAuth authorization code, OAuth token, public-read PAT, client secret, callback configuration, or browser-entered GitHub read credential.
- Legacy OAuth/PAT endpoints are non-redirecting and non-mutating during their bounded `410` compatibility window. They never parse/decrypt credential bodies, issue owner sessions, or disclose whether legacy encrypted state existed.
- Runtime migration deletes OAuth transactions, GitHub connection identities, and `identity_public_read` / `public_read` credential rows without decrypting or logging them. Authentication, local-launch, password, session, draft, bundle, and independent writeback state are preserved transactionally.
- Public discovery and analysis use only fixed-origin unauthenticated REST metadata and immutable-full-SHA archives. Redirect/SSRF, response-size, timeout, path, link, archive-bomb, staging-cleanup, selected-only, and untrusted-content controls remain mandatory.
- No discovery, resolution, preflight, or archive request may contain an authorization header or receive the writeback credential. Tests use writeback-secret canaries across every normal, retry, error, and cancellation path.
- Anonymous primary/secondary rate exhaustion produces only sanitized capacity/retry state, never a credential prompt. Manual authoring, validation, preview, copy, and download remain available immediately.
- Pre-migration backups may contain encrypted legacy records and remain protected by the existing backup-retention and destruction policy.
- Grant consumption, sole-owner creation/reuse, session creation, and competing-grant invalidation are one transaction. The durable owner may have no password in loopback mode. Moving that runtime to production fails readiness until the operator uses the host-only password command.
- Session, CSRF, expiry, rotation, revocation, and safe-audit controls are unchanged. A local logout does not expose a login form; access resumes only through a new launcher grant.

## 21. Owner-managed model connections (0.2.2)

ADR-029 authorizes a write-only provider-key/API-address input on authenticated Web Admin. The owner-approved edit-endpoint exception above permits managed URL readback only; it does not authorize key readback, a network proxy, a public credential form, or a new inference runtime.

ADR-031 makes host-managed cards controllable without disclosing their environment values. The first edit must submit a complete replacement URL; only after that value is stored as owner-managed may the existing edit-endpoint rule read it back. Deletion writes a secret-free durable suppression marker in the same transaction before removing an unreferenced connection. Startup must honor both replacement and suppression instead of importing the environment again.

- Enforce body-size limits, valid session, CSRF, same-origin/private administration and safe validation before any provider call. Public YAML/editor/preview endpoints continue rejecting secrets. Return only server IDs, display labels, configured booleans and sanitized capability/status metadata. No key suffix, fingerprint, previous private URL, raw upstream body or rejected request body is returned.
- A newly entered key is ephemeral form state, cleared after submission and on cancel/logout/expiry/unmount. Do not serialize it or the private address with the guided draft. Disable request-body recording for this boundary; synthetic canaries must prove absence from app/proxy logs, snapshots, traces, browser stores, exports and validation exceptions. Showing a freshly typed key is not permission to fetch a stored key.
- Use vetted authenticated encryption with an independent host-protected key, or an equivalent supported OS secret store. Never store plaintext keys in SQLite or reuse OAuth/PAT encryption settings. Bound stored entries and cleanup unreferenced revisions. Protect encryption keys separately from runtime backups; test permissions, unavailable keys, ciphertext tampering, backup/restore and rotation. Missing protection fails closed while manual work remains possible.
- Connection revisions bind protocol, exact normalized endpoint and credential reference. Historical revision rows retain the provider label as non-secret metadata and keep endpoint/key encrypted. Effective changes atomically rebind only directly referencing inactive candidates that are neither previous last-known-good nor reindexing, clear their old probe evidence, and invalidate affected analysis selection generation; unrelated profiles are untouched. Public-active, previous last-known-good, reindexing and frozen work retain their revision and resolve only its historical provider/secret. Endpoint/protocol replacement requires a fresh credential choice; never probe a changed host/path with a retained secret. The first host-managed replacement may retain a proven absent-key state, while ordinary managed edits keep the explicit key-intent rule. A blank key is not a delete instruction. Explicit no-key authentication is allowed for suitable private services; errors cannot select another key or service. No automatic retest or provider request follows a save.
- Server egress accepts only fixed operations on a validated chosen service. Enforce HTTPS for public endpoints and explicit private-target policy for local/private services. Reject userinfo, query/fragment credentials, traversal, forbidden address classes and metadata endpoints; validate all IPv4/IPv6/DNS resolutions when connecting, constrain transport to those addresses, and reject credential-bearing redirects. Model listing, health, chat, embedding and Ollama operations use the same policy.
- Optional listing never substitutes for bounded synthetic capability tests. Apply provider capacity/time/response limits; test failures cannot cause automatic downloads, repository uploads, reindexes or publication. User-selected destinations receive only the intentionally configured role's requests.
- AC-055/AC-056 cover attack and recovery paths. Retain AC-024/AC-033/AC-035/AC-051/AC-052 to prevent regressions in authentication, evidence isolation, privacy, and GitHub retirement.

Model probe diagnostics (owner correction, 2026-09-12, AC-054/AC-055): validated upstream HTTP status (100–599) or a fixed provider failure category refines authenticated profile `last_error_code`. The owner explicitly requested the original provider error instead of inferred/localized explanations. `last_error_message` is a narrow exception allowing sanitized message text from failed synthetic model probes in the authenticated profile response/runtime row. Follow Technical Specification 11.5's structural extraction and bounds: JSON error/message/detail strings or explicit plain text, at most 65,536 input bytes and 2,000 output characters, configured key/private URL/encoded-value/hostname and URL-span redaction before truncation, and display-control removal. Do not persist or return entire response bodies, metadata, headers, arbitrary exception text, or credentials. HTML pages and unsupported shapes yield no message; accepted text is escaped by React, never rendered as HTML. This parser does not identify arbitrary unknown secrets belonging to a provider; only configured sensitive values and URL spans can be redacted structurally. Message fields are excluded from exception/profile representations and remain behind existing session/same-origin/no-store boundaries; public diagnostics, logs, analysis jobs, exports and bundles do not receive them. Timeout/network errors without an HTTP response must not fabricate one. Successful retest or test-invalidating changes clear old message text.

## 22. Model-first analysis selection (0.2.3)

ADR-030 permits an explicitly selected tested chat/embedding pair to power authenticated owner analysis before public bundle activation. It does not make model setup public, grant the LLM tools, relax source confirmation, or turn temporary analysis data into a published index.

- Analysis readiness is authenticated safe metadata owned by the server. Never trust sessionStorage/local state, model-list presence, `/api/public/status.model.ready`, or a public `active` profile flag as sole authority. Role selections bind server IDs, exact connection revisions, tested model/embedding identity and a selection generation. Read responses remain secret-safe under section 21.
- Merely opening/resuming the wizard, listing metadata, saving a candidate, testing a model or returning from settings cannot fetch repository source or generate analysis. One explicit Start analysis intent enters existing preflight/admission/idempotency controls. Network loss/reload checks the active server job before retry; it must not duplicate provider work.
- The analysis pair is distinct from public-serving state. Selecting/testing it must not mutate public bundle pointers, activate an incompatible profile, start a reindex, publish a temporary derived index or replace last-known-good service. Public visitors continue to use only the verified active bundle/model pair.
- The current analysis algorithm requires both embedding and chat. Use the selected embedding revision for passages/query and selected chat revision for generation. A missing or invalid role fails before source/model work and offers the manual route. Do not introduce lexical/chat-only fallback or select another role/provider automatically.
- Preflight and execution freeze repository selection plus both model revisions. A model/connection/repository change invalidates a stale plan and incompatible cache identity. In-flight work retains the frozen pair or fails safely if its referenced secret/revision cannot be resolved; it never retargets the newest model. Generation interruption retains explicit retry confirmation.
- Same-round retry uses the same persisted/current-policy state, attempt and active-time eligibility in both snapshots and mutation. Cancellation or a lost lease rejects generation dispatch admission. A successor reanalysis round accepts only server-owned failed item IDs from a terminal source batch, transactionally prevents a source item from feeding multiple direct successors, copies immutable commit and selection policy, and defaults to the source frozen pair. A current-pair switch requires explicit confirmation bound to the expected selection generation. Migrations 26/27 and API payloads retain only secret-free lineage, round, failure stage, source-consumed marker and hashed bounded request binding; source bodies, prompts, provider bodies, endpoints, keys and arbitrary exceptions remain excluded. Reanalysis aliases reserve their opaque key across both reanalysis and ordinary batch creation, and runtime/read-path expiry cleanup prevents terminal results or receipts from remaining usable past their TTL.
- ADR-052 recovery lookup returns only an active batch or a recent actionable terminal batch for the authenticated owner. Migration 28 stores the owner's dismissal in runtime SQLite; `POST /api/admin/onboarding/analysis-batches/{id}/dismiss` requires the same owner session, same-origin check and CSRF token as other batch mutations. Dismissal changes lookup visibility only and returns no batch contents.
- Reuse global provider admission/fairness and per-provider limits even if implementation separates analysis and public runtimes. Creating a second runtime object must not double the effective generation allowance. Probe and analysis requests retain bounds, synthetic/content separation, redaction, request IDs and no raw upstream persistence.
- Clean startup can have no provider runtime or public bundle. Later authenticated setup must construct analysis dependencies safely in the same process. Avoid callbacks that report selected/active while leaving runtime execution unavailable. Failure preserves connection/profile data, manual drafts and public last-known-good service.
- Browser-state migration preserves only allowed public draft fields and navigation intent. It may record a safe return destination but not capability proof, profile secrets, private endpoints or raw results. Legacy progress cannot cause automatic tests or analysis. Session expiry/logout retains existing clearing controls; newly typed key/URL state is always ephemeral.
- Security regression adds AC-058 through AC-060: clean no-model/no-bundle first analysis, existing-public-A versus analysis-B isolation, stale-plan and rotation races, duplicate Start/reload, old guided-state recovery, secret canaries, and absence of temporary index/provider bodies from runtime rows, logs, exports and bundles.

Chat parse follow-up (2026-09-12): the authenticated `last_error_message` exception also permits fixed application-owned `RepoNPC response check:` diagnostics. `ResponseIssue` is a closed set of parser checks; no response content, reasoning, unknown field name, header, request id value, URL or key is interpolated. They retain the same no-store/authenticated boundaries and clear-on-success semantics. HTTP provider error quotations remain separate and redacted. No public diagnostic or logging expansion is authorized.

## 23. Password-encrypted maintenance backups (0.4.7)

- The same-origin private admin boundary authenticates before bounded JSON or
  multipart parsing. State changes require the existing session-bound CSRF;
  confirmation is strict boolean true. Reject ambiguous length/transfer headers,
  excessive actual bytes, duplicate multipart fields and unknown fields.
- Only version-one Scrypt/AES-256-GCM ciphertext crosses the download boundary.
  KDF cost is application-fixed; random salts/nonces and authenticated headers
  protect format/metadata. The complete format and limits are in Specification
  §11.7. The host-only raw backup command retains its existing restrictions.
- Native encrypted-file download uses an owner-authenticated GET with the same
  private Host and same-origin Origin/Referer check. Its timestamp/random file ID
  is not a bearer credential; knowing it cannot bypass authentication. A validated
  relative Content-Location connects backup creation to that existing saved
  ciphertext. Native GET is read-only and never generates another snapshot.
- Newly entered backup passwords exist only in UI input memory until submission
  and in the host's one session-bound ten-minute preview. Never persist them to
  SQLite, browser storage, logs, exported content or snapshots. Clear UI inputs
  after submit; clear private decrypted staging/password on cancellation, expiry,
  replacement, normal shutdown and failed preparation. A process crash can leave
  protected staging; operators follow the stopped-service cleanup procedure.
- Treat decrypted SQLite as hostile. Use read-only immutable input, trusted
  schema/migration inventory, bounded query progress, integrity/FK validation and
  parameterized row copying into a trusted new schema. Never execute uploaded
  triggers, views, migration SQL or extensions. Clear sessions, grants, setup
  proofs, audit session digests and transient jobs before activation.
- Restore requires matching owner identity and the original host resources.
  Verify stored connection ciphertext with the retained master key and validate
  referenced bundles, active/selected built-in artifacts, appearance and local
  portfolio assets. Reject links/junctions, non-regular or hard-linked database
  resources. Do not create replacement keys, download resources or fall back.
- Drain real admitted writers, including work detached from a cancelled HTTP
  request; stop listeners/pollers/provider/model jobs and close index resources
  before replacement. Save an encrypted current-state backup first, retain a
  private rollback copy until fresh startup, and keep service unavailable if a
  stop or rollback cannot be made safe. The replacement cannot revive closed
  provider instances. Successful restore disables the gateway and empties its
  external observation; reopening requires new admin authentication.
- Private staging and local ciphertext inherit the protected data-directory
  boundary. POSIX directories/files require 0700/0600; Windows deployments must
  keep that directory restricted to the owner and required system accounts.
  Clean-Windows permissions and installer walkthrough remain release gates.
- Backup verification covers wrong password, tampering, malformed/foreign
  schema, retained-resource failure, preview expiry/session binding, unsafe
  request cancellation, partial write/fsync, startup failure and pointer rollback.
  API success or local ciphertext retention cannot stand in for a completed
  browser file download or a clean installed-deployment restore.

## ADR-057 visitor progress (2026-10-04)

The processing contract permits only closed stage and nonnegative elapsed_ms
before final answer validation. Native thinking presence may select a fixed
thinking label; text itself remains discarded under ADR-055. All unknown generic
API reasoning fields remain private. No public raw-text exception, model tools,
endpoint/model detail, provider prompt, credential or diagnostics is authorized.
Sockets close on cancellation or absolute deadline; activity never extends it.
No progress data persists in runtime/cache/logs/browser storage/bundles/exports.

## Approved public summary amendment (2026-10-04)

OR-032 / ADR-058 / Specification 0.4.10 adopts the [public summary contract](CHAT_PUBLIC_SUMMARY_CONTRACT_2026-10-04.md). FR-040/043/044/047, NFR-005/009/014 and AC-019/023/057/062/063/064/068/071 retain their thresholds. Explicit Responses selection, legacy/revision compatibility, bounded untrusted plain text, prompt/secret negative tests, final-answer separation, cancellation and bilingual keyboard-accessible display require verification. No real provider invocation, publication, catalog admission or release acceptance is implied. Previous pending-summary notes are historical and superseded by this approval.

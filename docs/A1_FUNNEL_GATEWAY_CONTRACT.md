# A1 / F0 approved visitor gateway contract

Date: 2026-09-28. **Status: Approved for implementation (OR-027 / ADR-053).**
After reviewing the design explanation, the owner approved the recommended
contract and requested gpt-6-luna max implementation with Main review and
permission for Main to take over corrections. This closes the focused F0
contract approval; no public activation, live-provider spending or GitHub write
is authorized. Technical Specification 0.4.6 adopts this document as normative.
This document freezes the remaining F0 contracts for ADR-047 / ADR-048,
FR-047 and AC-071 (the live transport part of AC-068). Local implementation and
verification are complete locally (2026-09-29); external acceptance remains not-run.

## 1. Approved decisions and scope

Already approved: a visitor-only Funnel gateway; manually uploaded GitHub Pages
hosting; CORS for exactly the configured Pages origin without credentials;
private administration and models; bounded chat; distinct local / configured /
externally checked facts; Windows installation with owner-controlled official
Tailscale operations. A5 owns the static shell, offline FAQ matching, export
manifest and Pages-link verification. A8 owns the packaged launcher. A11 owns
the full maintenance workspace. A12 owns real external acceptance.

The owner approved this minimal F0 realization:

1. A second loopback listener in the same application process, controlled by the
   authenticated owner, with the lifecycle and runtime state below. An independent
   reverse proxy remains a viable alternative, but would introduce a second
   configuration/deployment surface and is not selected here.
2. Explicit private admin origins and Host binding, the three new environment
   fields, runtime migration and private endpoints below.
3. Gateway-specific public projections and buffered-answer SSE heartbeats;
   local chat shares the heartbeat handler and generic chat errors while retaining its own identity and response projection.
4. Aggregate abuse protection by default. Optional per-IP identity requires
   explicit loopback-proxy trust and verification of the actual deployed Funnel
   forwarding behavior; a loopback socket address is never a visitor identity.
5. The existing visitor `/` entry plus its exact reproducible build-manifest
   dependencies, without the admin dynamic chunk or SPA fallback. The existing
   same-origin visitor page remains available on the application listener for
   local preview and existing operator-managed ingress. A5 still supplies the
   separately exported Pages shell and its offline functionality.

Approved MVP Pages origins: exactly `https://<validlabel>.github.io`,
with one valid DNS label before `github.io`. Custom domains require a later
owner decision. Origin alone cannot prove Pages ownership/hosting; A5 performs
its existing manifest verification. No wildcard, path, credential, port, query,
fragment or extra subdomain is accepted.

## 2. Environment and configuration

| New environment field | Default / validation | Meaning |
| --- | --- | --- |
| `REPONPC_ADMIN_ORIGINS` | CSV; empty resolves to the existing `REPONPC_PUBLIC_BASE_URL`; exact normalized origins | Explicit private production administration origins. HTTPS, or direct HTTP loopback for existing local administration. No wildcards, user information, query, fragment or path. |
| `REPONPC_VISITOR_GATEWAY_PORT` | `8001`; integer 1–65535; different from the application port | Visitor listener always binds `127.0.0.1`; no configurable public bind. |
| `REPONPC_VISITOR_TRUSTED_PROXY_CIDRS` | Empty; optional canonical loopback-only CIDRs | Explicit trust for the direct local proxy's single-address `X-Forwarded-For`. Empty means aggregate identity protection. |

The gateway is available only in `production`. The evaluation launcher cannot
start it. There is no public YAML, immutable bundle, provider, credential or
Tailscale-setting addition. Enter gateway and Pages origins in the private GUI;
store them only in mutable runtime SQLite. Configuring a gateway requires
explicit `REPONPC_ADMIN_ORIGINS`; every private admin hostname must differ from
both the gateway and Pages hostname, even when ports differ. Host-only
`__Host-` session cookies are not scoped to a port. SSH loopback or another
private hostname remains a valid administration path.

The main listener passes the existing `REPONPC_TRUSTED_PROXY_CIDRS` explicitly
to Uvicorn instead of relying on its implicit production default. Those CIDRs
apply only to the private application's proxy and never grant gateway trust. The gateway
always uses `proxy_headers=False`, preserving the actual socket peer for its
own narrow trust check. Existing `REPONPC_ALLOWED_ORIGINS` never grants admin
CORS and does not control Pages CORS.

Private admin requests must bind the validated Origin/Referer to the request's
exact scheme and Host authority, both in the configured admin-origin set. A
spoofed Host, unrelated allowed Origin, or untrusted forwarded authority cannot
pass. This boundary includes login, owner setup, setup-status and session reads,
as well as authenticated operations. Existing Secure / HttpOnly / SameSite cookies, session rotation, setup
code, password, CSRF and local-launch rules stay mandatory. The actual private
HTTPS endpoint remains the operator's responsibility; this task does not add a
certificate service or weaken Secure cookies for remote HTTP.

### B5 origin-rule comparison (approved simplification)

| Rule | Environment canonicalizer | Former admin normalizer | Shared rule |
|---|---|---|---|
| Scheme/host case; default ports | Normalize | Normalize | Normalize |
| Trailing slash, path, query, fragment, userinfo | Reject | Reject | Reject |
| Unicode IDN, trailing-dot or ambiguous numeric host | Reject | Accepted in some cases | Reject; ASCII punycode remains valid |
| IPv6 | Validate and compress | Lowercase only | Validate and compress; reject zones |
| HTTP | Loopback only | Any host | Loopback only for private admin; HTTPS only for gateway/export |
| Whitespace, backslash, invalid port | Reject | Reject | Reject; maximum 2048 characters |

## 3. Runtime schema and lifecycle

Migration 30 adds one singleton `visitor_gateway_settings` row:

| Field | Type / bounds |
| --- | --- |
| `id` | INTEGER primary key, exactly 1 |
| `revision` | INTEGER, positive optimistic mutation revision |
| `enabled` | INTEGER, 0 or 1, default 0; persisted explicit owner intent |
| `gateway_origin`, `pages_origin` | Nullable TEXT, normalized origins, max 2048 characters |
| `verification_gateway_origin`, `verification_pages_origin`, `verification_bundle_id` | Nullable TEXT; historical write-only configuration and active-bundle association; origin bounds as above, existing validated bundle ID with maximum 128 characters |
| `verified_at` | Nullable canonical UTC ISO-8601 timestamp, max 32 characters |
| `verification_method` | Nullable TEXT; only `owner_reported` |

The five verification fields must be all null or all present, enforced by a
database CHECK; configuration origins must be both null or both present.
Use existing SQLite transactions and positive-revision optimistic updates;
write all five fields together from current configuration and BundleManager, preserving the shipped CHECK. Only verified_at determines the active report. Configure/start/stop/resume/restart clear all five fields together; bundle activation does not clear them. Migration 30 is unchanged.

No source IP, Tailscale identity, account, token, prompt or model connection is
stored. Existing runtime backup includes the table. Listener state and errors
are live facts, not persisted proof of reachability.

After the main application's services initialize, an enabled persisted intent
may resume the visitor listener. One Uvicorn server shares the application's
existing service suppliers and lifespan; it must not initialize or close the
database/providers a second time. Fresh installation stays disabled. Port/bind
failure leaves administration, local work and the last-known-good bundle usable
and reports a safe error. Start is idempotent for the same revision/configuration;
configuration changes while running require explicit stop first.

Stop immediately rejects new admissions, signals cancellation to all gateway
chat workers, closes the listener and waits only the existing configured
shutdown grace. Provider work remains within existing deadlines even when a
thread cannot be forcibly interrupted. A canceled request keeps its in-flight
permit until its actual worker exits. Application shutdown closes the gateway
before releasing shared resources. An explicit stop persists `enabled=0`;
ordinary process exit preserves the last explicit enabled intent.

Tailscale remains external. Guidance uses current official CLI syntax, requires
Tailscale 1.52 or later, and shows commands containing only the configured port:

```text
tailscale funnel --bg --https=<https-port> http://127.0.0.1:<visitor-port>
tailscale funnel --https=<https-port> off
```

`<https-port>` is the port of the entered visitor origin (443 when it has no
explicit port). The GUI fills it in only for Funnel's 443, 8443 or 10000 and
otherwise keeps the placeholder, so it never suggests a port already used on
the host. Under `loopback_evaluation` the GUI states that public sharing needs
the production profile and disables the origin form and gateway start
(2026-10-18).

The owner performs installation/login/authorization/enable/disable in the
official flow. RepoNPC does not invoke those commands, install Tailscale, read
its configuration or retain its credentials. `--bg` can persist across reboot;
stopping RepoNPC's gateway therefore must not claim that Funnel itself is off.
Use scoped `off`, never `reset`, which could remove unrelated configuration.

## 4. Private API and GUI

Every route uses the existing owner authentication and same-origin checks;
mutations require CSRF. Strict bodies reject unknown fields. All responses use
`Cache-Control: no-store`; no endpoint accepts Tailscale credentials.

| Endpoint | Strict request |
| --- | --- |
| `GET /api/admin/visitor-gateway` | No body |
| `PUT /api/admin/visitor-gateway` | `{revision, gateway_origin, pages_origin}` |
| `POST /api/admin/visitor-gateway/start` | `{revision}` |
| `POST /api/admin/visitor-gateway/stop` | `{revision}` |
| `POST /api/admin/visitor-gateway/verify` | `{revision, external_checks_confirmed: true}` |

Allowlisted response schema:

```json
{
  "revision": 1,
  "gateway_origin": null,
  "pages_origin": null,
  "enabled": false,
  "listener_ready": false,
  "error_code": null,
  "local_ready": false,
  "entry_configured": false,
  "external_verified": false,
  "verified_at": null,
  "verification_method": null,
  "active_bundle_id": null,
  "client_identity_mode": "aggregate"
}
```

`client_identity_mode` is `aggregate` or `trusted_proxy`. `local_ready` comes
from actual current bundle/runtime/model readiness. `entry_configured` means
both validated origins are stored and the listener is actually ready; it does
not assert that Funnel is authorized or reachable. `external_verified` means `verified_at is not null and listener_ready`. Configure,
start, stop, listener recovery and process restart clear the five persisted report
fields together. Bundle activation does not clear this dated observation. Local
readiness is a separate fact; it does not bind or invalidate the report. The GUI
explicitly labels an owner-reported observation, never continuous reachability.

The verification action requires a native checklist: use an independent
non-tailnet network; open the public status/profile; exercise chat and its
citations; confirm admin/model/unknown routes are unavailable. There is no
automatic external probe and no provider request caused by this endpoint.
Configuration/start/stop/resume/restart clears the report. A failed listener
displays external_verified false and clears the report on the next private
snapshot; recovery requires starting the listener and a new report. Verify
rejects an unavailable listener with GATEWAY_UNAVAILABLE and a stale mutation
revision with GATEWAY_CONFLICT. Unobserved Funnel or internet outages are not
detected. Bundle and local readiness changes do not invalidate this dated report.

New closed admin error codes:

| Code | HTTP / reason |
| --- | --- |
| `GATEWAY_CONFLICT` | 409; optimistic revision changed |
| `GATEWAY_CONFIGURATION_INVALID` | 422; origin, profile or running-state requirements not met |
| `GATEWAY_UNAVAILABLE` | 503; listener unavailable/start or stop operation failed safely |

The public boundary adds `GATEWAY_IDENTITY_INVALID` (400) for malformed or
missing identity in explicitly trusted mode; its message is generic and contains
no IP, host or header value. Section 7 adds two generic request failure codes.

Existing validation/auth/CSRF codes retain their current meanings. The private
panel in the publication workspace uses native controls and equivalent zh-TW/en
labels. It presents the three facts separately, enable/stop controls, configuration
and official Funnel instructions, and actionable failures. Owner-only copy explains
host/model availability, Funnel beta/limits and plan eligibility. Local prepare,
preview, FAQ review and ordinary manual work stay usable while sharing is disabled.
This task does not issue a Pages/card verification or publication-success badge.

## 5. Closed route and credential boundary

The gateway registers only the existing public router using shared suppliers
and the visitor build-manifest entry; it never mounts the full app or forwards
arbitrary paths to it. A narrow boundary
checks both raw and decoded paths before routing. Encoded paths, backslashes,
dot segments, repeated separators, case variants, trailing slash variants,
unexpected methods and unknown routes fail with 404, without redirects. The
closed route table is:

| Method | Exact path |
| --- | --- |
| GET, HEAD | `/healthz`, `/readyz` |
| GET, HEAD | `/` and exact visitor entry dependency filenames selected from the validated Vite manifest |
| GET, HEAD | `/api/public/status`, `/api/public/profile`, `/api/public/faq` |
| GET, HEAD | `/api/public/character.png` |
| GET, HEAD | `/api/public/scene-background?rev=N` (A5 integration, FR-050/052; current applied image only) |
| GET, HEAD | `/api/public/card.svg`, `/api/public/card.gif`, `/api/public/card.png` |
| GET, HEAD | `/api/public/owner-statements/{revision}/{evidence_id}` with existing full-SHA/evidence-ID validation |
| POST | `/api/public/chat/stream` |
| OPTIONS | Only the listed `/api/public/...` paths, for supported methods |

Projects are part of the existing public profile. There is no new projects API.
HEAD handlers are registered explicitly and suppress response bodies; FastAPI
GET decorators alone do not supply this contract.
The A5 multi-entry build serves the dedicated `visitor.html` at `/`, with only
that entry's closure. Legacy builds without this entry retain `index.html`;
an invalid dedicated entry fails closed and cannot fall back to the admin entry.
The build must produce a reproducible dependency manifest. Starting at the
visitor entry, follow static `imports`, `css` and `assets`; exclude
`dynamicImports` unless explicitly declared visitor dependencies. The existing
lazy AdminPage import must never enter this dependency closure. Validate relative
regular file paths, existence and bounded manifest content; a missing/invalid
manifest fails closed for visitor assets. Do not serve the manifest itself or
unlisted files from a broad directory mount. No asset body may come from runtime
secrets. `/admin`, `/api/admin/...`, unlisted `/assets/...`, provider paths,
data directories, OpenAPI/docs and every unlisted route are 404.

Host accepts only the configured public gateway authority or the precise
`127.0.0.1:<visitor-port>` listener authority. `Forwarded` and
`X-Forwarded-Host` never expand it. Current Tailscale implementation details
must be checked against supported release/external behavior before claiming
full ingress acceptance; installation version alone is not that evidence.
The source baseline is Tailscale 1.102.2: its HTTP proxy preserves the inbound
Host ([official release source](https://github.com/tailscale/tailscale/blob/v1.102.2/ipn/ipnlocal/serve.go#L895-L915))
and overwrites forwarded source address from the serve context while clearing
identity headers ([official forwarding source](https://github.com/tailscale/tailscale/blob/v1.102.2/ipn/ipnlocal/serve.go#L996-L1018)).
Local installation reports that version; no actual transport was tested.

Reject `Cookie`, `Authorization` and `X-CSRF-Token` on the gateway before
dispatch, with 404 and no credential processing. Do not echo or log these values.
Strip/prevent `Set-Cookie` from gateway responses. Accepted Pages CORS requests
use exactly the configured Origin, `GET/HEAD/POST` as appropriate and
`Content-Type` only; never `Access-Control-Allow-Credentials`. Preflight asking
for credentials/unknown headers or unsupported methods gets no grant. Unknown
Origins receive no CORS grant; direct requests without Origin remain possible
because CORS does not authenticate public callers. CORS never bypasses the
route allowlist and no wildcard is used.

## 6. Identity, cost and request bounds

Default aggregate mode ignores all forwarded identity headers. Do not charge
all visitors to `127.0.0.1`, a missing-IP string, or a fabricated identity. The
shared chat service accepts a missing public identity and skips only the per-IP
bucket: the existing transactional daily budget and provider permits still apply.

Optional trusted mode accepts a single syntactically valid IP address from
`X-Forwarded-For` only when the unmodified socket peer is in an explicitly
configured loopback CIDR. In enabled trusted mode, an untrusted peer, missing,
duplicate, chained or malformed address fails closed before admission with
`GATEWAY_IDENTITY_INVALID` (400), rather than bypassing the per-IP bucket through
aggregate fallback. Never use `Forwarded`, Tailscale user headers or
untrusted sender values. Tailscale's supported reverse proxy must overwrite the
header from its connection context, verified against release behavior and an
external test before operational per-IP acceptance. The operator must explicitly
confirm the tested 1.102.2 forwarding semantics before enabling trust. The
generic minimum 1.52 concerns CLI syntax only; later Tailscale versions need the
same overwrite contract independently checked before operational per-IP
acceptance. A local trusted-proxy
configuration trusts that host boundary; it does not authenticate processes
sharing the host. The UI states which protection mode is configured.

Before decoding JSON or scheduling a worker, enforce a 65,536-byte total request
body ceiling (including streamed/chunked bodies and regardless of declared
Content-Length). Body intake and generation share the existing total chat
deadline; slow or unfinished body reads cannot wait indefinitely.
Existing message/history limits and output budget continue to
apply. Use the existing global chat concurrency setting also as the gateway's
bounded in-flight worker ceiling, with immediate existing `CONCURRENCY_LIMIT`
rejection; canceled workers retain their slots until they finish. Daily admission
occurs before retrieval/provider work exactly once. No new per-IP fallback
bucket, scheduler, provider policy, dependency or hosted service is added.

## 7. Public projections and SSE

Gateway status has this strict allowlist, independent of the existing local
`PublicStatus` model:

```json
{"status":"resting","chat_available":false,"index":{"ready":false,"version":null}}
```

`status` is `ready | resting`. Do not return provider/model readiness objects,
provider names, timestamps with diagnostics, host/hardware/cost fields, private
review state or runtime configuration. Profile and FAQ use their existing
validated public serializers; citations remain backend-owned. The gateway's
complete SSE event sets existing `usage` to null, never returning model token/cost
information. Assets use the
existing byte-validation paths. Public responses retain safe security headers.
Gateway errors retain the existing envelope shape and safe limits/validation
codes, but map provider failures to generic `SERVICE_NOT_READY` (503),
`REQUEST_TIMEOUT` (504 / terminal SSE) and `REQUEST_FAILED` (502 / terminal SSE),
with neutral bilingual service messages. These two new generic request error
codes are part of the requested F0 approval. No private diagnostic is serialized.

Both chat paths use the same heartbeat/worker handler, grounded service and validator. The private application retains its existing socket identity and complete-event projection; the gateway retains aggregate/trusted-proxy identity, bounded worker retention and the visitor projection. Error mapping is passed explicitly and follows the generic gateway codes on both chat routes. The local FastAPI body validation and limit details remain unchanged; the gateway retains bounded streamed intake. Configured gateway/Pages origins are captured when the listener app is created; visitor boundary and chat requests never read or mutate owner settings in SQLite. It may send
SSE headers and comment heartbeats while awaiting a buffered answer, using
`REPONPC_SSE_KEEPALIVE_SECONDS` and the existing total chat deadline. It never
streams unvalidated provider text or claims truthful provider first-token
progress. Successful validated events remain `metadata`, `token`, `citations`
(when present), `complete`; a failure after headers yields one terminal `error`
with the existing error-envelope schema. Pre-stream route, CORS, credential,
body, validation, readiness and in-flight-capacity failures retain HTTP JSON.
Daily/rate/provider failures discovered during the worker produce terminal SSE
errors. The gateway never retries; local chat retains its bounded retry policy.
Neither path falls back to another provider.

Disable proxy buffering; reuse `no-store` and `X-Accel-Buffering: no`. Disconnect,
total deadline or owner stop signals the existing worker cancellation flag.
The deadline remains 45 seconds by default, configured by the existing setting;
heartbeats do not extend it. No additional upstream timeout configuration is
invented. Tests must observe headers/heartbeats before the synthetic provider
finishes and test disconnect/stop accounting; a fully buffered TestClient
response alone cannot prove transport behavior.

### B5 chat-path comparison (approved simplification)

| Boundary | Former local chat | Gateway chat | Shared result |
|---|---|---|---|
| Intake | FastAPI parsed body; field details | Bounded streamed body and intake deadline | Retain each intake boundary |
| Readiness/errors | INDEX/MODEL/PROVIDER errors, worker failures before headers | Generic service/request codes, terminal worker error | Both generic gateway codes; worker errors terminal SSE |
| Events | Validated metadata/token/citations/complete; local usage | Same validated events; usage null, safe finish reason | Parameterized projection retains each |
| Heartbeat | No comments while waiting | Connected and periodic keepalive | Both heartbeat handler; no unvalidated text |
| Identity/admission | Socket identity and service limits | Aggregate or explicit loopback proxy; worker retention | Retain each identity/admission boundary |
| Cancel/deadline/retry | Disconnect and total deadline; bounded provider retry | Disconnect/stop/deadline; no retry | Shared cancellation/deadline, explicit retry policy |

The deadline permits a retry within the remaining time, so allow_retry remains.
Only the gateway forbids retries. No new admission state is added to local chat.

## 8. Verification, rollback and boundaries

Implementation gates: environment defaults/invalid cases; migration preservation,
transaction rollback, backup/reopen; start/stop/restart/bind failure; strict
Host/Origin and credential/CORS negatives; canonical-path variants; public
allowlist canaries; true ASGI SSE heartbeat/deadline/disconnect tests; identity
trust/aggregate daily/concurrency limits; private API concurrency/auth/CSRF;
bilingual real browser actions and state facts; complete Python/Web/static gates.
Use synthetic providers and no live Funnel/provider/GitHub calls.

Before upgrading real runtime storage, use existing backup. Migration failure
rolls back transactionally; rollback to an older application requires restoring
its pre-upgrade runtime SQLite and matching protected secret files. Never mutate
bundle bytes or rewrite unrelated deployment settings. A failed gateway start,
Funnel outage or stop leaves local data, owner editing and last-known-good
bundle intact. Restoring runtime state never constitutes new external proof;
the owner must repeat the independent checklist after restore/deployment change.

Linux/Windows direct-host code supports the same loopback listener mechanics.
Container loopback is not host loopback, so an ordinary published port does not
make a container's loopback-only gateway reachable from host Tailscale.

Approved Linux Docker option: an opt-in `compose.funnel.yml` override sets
`network_mode: host`, clears inherited `ports` with `ports: !reset []`, and sets
`REPONPC_HOST=127.0.0.1`. Both the private application (default 8000) and visitor
gateway (default 8001) bind host loopback; host-installed Tailscale points only to
the latter. The default Compose recipe stays separate. There is no new proxy
service or public bind. Require Docker Compose 2.24.4 or later as the supported
baseline and reject older versions at preflight; this is a project baseline,
not a claim about the first release implementing `!reset`. The official
[Compose merge documentation](https://docs.docker.com/reference/compose-file/merge/#reset-value)
documents resetting inherited ports; the official
[host network driver documentation](https://docs.docker.com/engine/network/drivers/host/)
documents Linux host networking. Host networking is the Linux reference,
not a Windows Docker Desktop deployment claim. Windows native packaging is A8.

A1 includes Compose resolution and local Docker smoke proving
both loopback binds, gateway route isolation and shared readiness, without
enabling Funnel. Clean-host packaging and real external reachability remain
F1/A8/A12 acceptance. A1 supplies concrete local gateway controls and tests,
not a public deployment claim.

## 9. Expected implementation ownership

Implementation: minimal gateway service/boundary modules; hooks in main entrypoint,
environment loading, private/public router factories, chat admission and runtime
migration; a private gateway panel in the publication workspace; proportionate
contract/lifecycle/security/SSE/storage/frontend/browser tests; affected normative
specification, security, operations, examples, Funnel plan and backlog updates.
Main retains independent security tests, final review, commits and memory.
No new dependency or speculative abstraction is proposed.

## 10. Local implementation checkpoint (2026-09-29)

The source implements this contract: `api/visitor_gateway.py` owns the second
listener, `api/visitor_ingress.py` owns its closed ASGI boundary and bounded SSE,
`runtime/visitor_gateway.py` plus migration 30 persist owner intent and dated
reports, and `VisitorGatewayPanel.tsx` provides private bilingual controls.
The main entrypoint shares its current bundle, providers, FAQ and readiness;
the existing chat limits and provider permits remain in use. Production private
reads, auth/setup routes and built HTML require the configured private authority,
including when the admin service cannot initialize.

Historical pre-B5 checkpoint: Main reviewed and corrected startup isolation, Windows exclusive port binding,
verification lifecycle, actual worker retention and UI response
ordering. Full Python: **1,260 passed / 2 Windows skips**; Web: **230 passed in
30 files**; Ruff lint/format (188 files), mypy (78 source files), frontend
format/lint/type/build and Git whitespace passed. ESLint reports 17 Fast Refresh
warnings, with no errors. The standalone frontend build used a fresh output
directory because the existing dist directory had a Windows ACL error; the
Docker frontend build also passed. Both temporary output and browser mounts
were removed.

Two isolated Docker smoke checks passed: the normal entrypoint's health/runtime
volume restart and real image primary/gateway loopback binds, shared readiness,
visitor manifest, private-path denial and stop. Eight native-browser groups
covered bilingual controls, revision conflicts, held mutations, report
invalidation, keyboard focus and mobile layout; final 375/1180px measurements
showed no horizontal overflow. Responses and owner reports were synthetic.
Detailed local evidence is `release-evidence/a1/local-checks.md` (gitignored).

No Funnel activation, public deployment, live model call, GitHub write or push
was performed. The complete Pages export/offline/layout is A5, Windows packaging
is A8, and real external/provider/clean-host/release acceptance remains A12.
No additional A1 owner decision is pending.

## 2026-10-04 approved progress amendment — ADR-057

The processing contract supersedes §7's buffered-provider-only waiting and
45-second default: public chat may observe native NDJSON/Chat Completions SSE,
default 180/max 300, and optional progress events before validated delivery.
Progress contains closed stage plus elapsed_ms only, never provider text.
Complete adds elapsed_ms; usage projection and private boundary remain intact.
Streamed generation does not retry; buffered paths retain their existing policy.
Raw thinking stays private and requested thinking-text display remains pending.

## Approved public summary amendment (2026-10-04)

OR-032 / ADR-058 / Specification 0.4.10 adopts the [public summary contract](CHAT_PUBLIC_SUMMARY_CONTRACT_2026-10-04.md). FR-040/043/044/047, NFR-005/009/014 and AC-019/023/057/062/063/064/068/071 retain their thresholds. Explicit Responses selection, legacy/revision compatibility, bounded untrusted plain text, prompt/secret negative tests, final-answer separation, cancellation and bilingual keyboard-accessible display require verification. No real provider invocation, publication, catalog admission or release acceptance is implied. Previous pending-summary notes are historical and superseded by this approval.

# Visitor chat processing and waiting experience

**2026-10-04 follow-up:** OR-032 / ADR-058 / Approved 0.4.10 implements the
[approved public-summary contract](CHAT_PUBLIC_SUMMARY_CONTRACT_2026-10-04.md).
It supersedes the pending-summary section below. Raw thinking remains private.
The bounded queue now holds 16 shared stage/summary events.

Owner-authorized implementation, 2026-10-04: OR-031 / ADR-057.
Requirements: FR-043/044/047, NFR-005/009/014; AC-019/023/062/063/064/068/071.

The owner requested the supplied screenshots' expandable processing history,
elapsed time and model thinking, using mature implementations researched by
Luna Max. Implement 180-second default within the existing 300-second maximum;
explicit deployment values remain choices. No extra provider calls, tools,
fallback, publication or relaxed final validation is authorized.

## Public projection and implementation

Optional SSE `progress` events before validated delivery contain exactly
`{"stage":"thinking","elapsed_ms":1234}`. The closed stages are `searching`,
`evidence_ready`, `waiting_model`, `thinking`, `generating`, `validating`.
Elapsed is a nonnegative integer measured from accepted handler work using
monotonic time. No provider text, command, prompt, endpoint, model identity,
cost/usage or diagnostics are allowed. At most eight labels await delivery,
with repeated activity coalesced.

Stages are actual service boundaries. Native Ollama thinking requires a real
thinking chunk; generation requires a content chunk. Generic API reasoning
extensions are discarded. SSE comments are keepalive only. Activity never
restarts the total deadline. Answers remain private until the unchanged
envelope/evidence/person/citation validator passes. Validated delivery order
remains metadata, token, optional citations, complete. Complete adds elapsed_ms;
failure sends one safe terminal error. Incomplete/output-limited streams fail
closed. Streamed generation calls one selected adapter once, without retries.
Buffered admin/probe paths retain existing behavior.

Use native Ollama NDJSON and standard Chat Completions SSE. Transport retains
pinned origins, no redirects, 64-KiB lines and 2-MiB responses, closing blocked
sockets on cancel/deadline. No separate inactivity setting or Responses request
is invented. Adapters without streaming methods retain one buffered call and
cannot claim model activity before return.

Each live assistant turn uses native details/summary with real phase history
and elapsed waiting time. Completion, failure and cancellation freeze duration.
Browser timing starts at submission, includes connection/network overhead, and
differs from backend accepted-work timing; neither is pure generation time.
Only time advances on the timer. Both locales, keyboard disclosure, polite phase
announcements and reduced motion are preserved; ticking time is outside alerts.
Stop aborts fetch/body, restores focus and excludes the cancelled reply from
successful model history. No durable history or new storage is added.

## Unfinished text display and automatic review

Automatic approval review rejected the proposed raw thinking callback into
public SSE: it might expose prompts, secrets and unvalidated claims. That raw
projection was removed. Only closed activity labels are integrated; showing
the contents of model thinking remains unfinished.

Concrete next choices:

1. Recommended: explicitly add/select a Responses adapter and consume only
   public `response.reasoning_summary_text.*`; bounded plain text, transient
   memory only. Never silently switch an existing Chat Completions service.
   Models without summary support show actual stages.
2. Native raw third-party drafts: requires explicit authorization and reviewed
   secret/prompt-copy rules and negative tests before any public callback.
   Label unvalidated, bound input, keep ephemeral. Collapse and literal masking
   alone cannot prove privacy. No prompt/credential exception is proposed.

Reference: mature NDJSON/SSE, native HTML disclosure and AbortController.
Primitive: existing request + parser + bounded phase queue + turn timing.
Concept budget: one progress projection and transient metadata, no database,
job, service or dependency. Replaces fully buffered public-provider waiting;
keeps the necessary final-validation trust boundary. No release ledger promoted.

[Official-source Luna Max research](../release-evidence/a7/waiting-ux-20261004/RESEARCH.zh-TW.md).

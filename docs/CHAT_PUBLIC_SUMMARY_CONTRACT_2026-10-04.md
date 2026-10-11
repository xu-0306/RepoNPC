# Public model summaries

Owner approval 2026-10-04: OR-032 / ADR-058 / Approved 0.4.10.
FR-040/043/044/047; NFR-005/009/014; AC-019/023/057/062/063/064/068/071.

The protected connection write request and safe DTO add `chat_api`, either
`chat_completions` (legacy default) or `responses`. Omitted create input means
the legacy interface; omitted update input retains the existing selection when
the provider is unchanged. Responses requires `openai_compatible`. Embeddings
continue using their existing interface. No environment variable is added.
Migration 35 adds `model_connections.chat_api`; immutable encrypted revision
payloads also store this selection. Legacy ciphertext without the field means
chat_completions. Protocol edits create a revision and require profile probing;
active/frozen profiles retain their original connection revision.

Responses uses the owner's selected endpoint/model with `store:false`, no tools,
background mode or implicit fallback. The live request opts into public
`reasoning.summary:auto`; admin/probe requests verify that same option but never
expose summaries. A service rejecting it fails its profile probe; no silent
protocol/parameter retry is made. Successful providers may return no summary.
Final answer content remains buffered for the unchanged envelope, evidence,
person, citation and safety validation. Stream EOF without completion, refusal,
unknown output items or incomplete output fails closed. One selected request,
existing 180/300-second total deadline and socket cancellation remain in force.

Only complete `response.reasoning_summary_text.done` paragraphs belonging to
known reasoning items can be considered public. Raw thinking, encrypted traces,
unknown fields and partial summary deltas are discarded. Before publication,
reject controls, URLs, known keys/private endpoint variants and normalized
32-character copies of the actual request prompt. Reject before truncation;
never expose a secret prefix from partial deltas. This is defense in depth,
not a proof against arbitrary paraphrased leakage. Failure suppresses summaries
while preserving real activity and final-answer checks.

Optional `reasoning_summary` SSE precedes validated metadata and contains exactly
`{text,elapsed_ms}`. Text is nonempty plain text; at most 8 paragraphs and 4,096
Unicode characters in aggregate per turn. No provider IDs, endpoints, model,
prompt or usage fields are public. Summary delivery never resets a deadline.
Ingress uses a bounded 16-event queue shared with stage events. No logging or persistence
of summaries or prompt bodies is permitted.

The existing native disclosure displays summaries labelled as unverified model
public summaries, separate from backend stages and final answers. Render text
literally, never HTML, Markdown or commands. Keep only transient turn memory;
exclude model history, browser storage, export and durable chat data. Maintain
Traditional Chinese/English, keyboard disclosure, reduced motion, frozen timing
and stop. A model may provide no summary or only provide it near completion;
the UI must not fabricate content or promise token-level thinking progress.
Ollama and legacy Chat Completions retain actual stages/time only.

No real inference, model download, hosted dependency, tools, release promotion
or extra summary-generation call is authorized by this implementation.

[Provider reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)
and [completed summary events](https://developers.openai.com/api/reference/resources/responses/streaming-events)
define the selected interface; the prior raw-thinking rejection remains binding.

Local integration completed with [scoped verification and browser evidence](../release-evidence/a7/waiting-ux-20261004/PUBLIC_SUMMARY_RESULT.zh-TW.md).
This does not establish real-provider compatibility or release acceptance.

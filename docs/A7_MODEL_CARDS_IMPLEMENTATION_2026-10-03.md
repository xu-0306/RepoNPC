# A7 model cards and explicit setup

Owner authorization: the owner approved the described device-check → reviewed
catalog → model cards → existing setup/test/explicit selection flow, then asked
on 2026-10-03 to execute the previous three-way GPT-6.1 Sol assignment.

This implements the reviewed-card and form portion of FR-040 / AC-057. The existing protected
`POST /api/admin/model-guidance/device-check` keeps its hardware and models
response. Each existing model/quantization row additionally returns the authored
parameter count, bits, download and overhead bytes, review date, public source
and license links, and its live envelope-v2 evidence. No saved service address,
key, host identifier, prompt, raw model output or automatic provider call is
returned. The existing CPU estimate remains explicit; observed GPU capacity is
not a claim that a model or provider will use it.

Cards render all four existing resource grades with reasons and unknown values,
show the dated bilingual evidence and distinguish it from the owner's required
runtime test. Choosing a card opens the existing Chat model setup. A separate
explicit “Fill model name” action copies only the authored model identifier into
the current create form. It preserves service choice and existing edit forms;
adding, testing and selecting remain the existing separate owner actions. There
is no automatic download, connection, probe or activation.

Every explicit card choice requests form focus, including choosing the same row
again after moving away or changing locale. The parent stores a fresh copy of
the existing row for each click; it adds no operation identifier or state machine.
This prevents React's same-object state bailout from silently ignoring repeat
keyboard choices. The real in-app supplemental regression covers both locales
with no service configured, alongside draft/fill checks from the first fixture.

Reference: the existing RepoNPC ChatProfilePanel and ModelEditor already own
create, test and selection. Guidance composes those with the existing strict
catalog and estimator. Concept budget: zero new tables, services, endpoints,
configuration fields or operation states. The count-only presentation is
replaced by the per-model cards; the existing empty-catalog explanation remains.

Catalog admission still requires actual dated zh-TW/en envelope-v2 results and
public source/license provenance. Synthetic card fixtures demonstrate rendering
and navigation only; they do not certify any real model or close release ACs.

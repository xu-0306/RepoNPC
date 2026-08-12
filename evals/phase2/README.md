# Phase 2 formal benchmark

`run_benchmark.py` is the host controller. It creates a minimal Docker build context containing
only the application sources, lockfiles, the candidate runner, and this Dockerfile. At runtime it
mounts only the public fixture/config/questions at `/input` and a result directory at `/output`.

The candidate uses the production `local_sentence_transformers` adapter with its model cached in
the image and runs with `--network=none`, four CPUs, and 8 GiB memory. It emits retrieved IDs/paths,
raw timing samples, build digests, provider identity, and provenance. It never receives expected
evidence or emits pass/threshold fields.

The host retains the reviewed expectations, inspects the stopped candidate container and image,
runs a filesystem access probe, and derives repeatability, Recall@8, bilingual parity, warm p95,
all provenance booleans, blockers, and final acceptance. Raw evidence is written beside the final
report under `formal-benchmark/`.

Formal mode is hard-bound to `public/questions.json` and
`controller/expected-evidence.json`; callers cannot replace either input. The report records both
canonical relative paths and SHA-256 digests so reviewers can bind measured results to the reviewed
question and oracle bytes. Run it with only the output selection, for example:

```text
python evals/phase2/run_benchmark.py --artifacts artifacts/formal-benchmark.json
```

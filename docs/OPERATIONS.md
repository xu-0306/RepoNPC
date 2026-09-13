# RepoNPC v1 Operations Guide

**Owner-approved URL editing exception (2026-09-12, ADR-029; FR-038/040, AC-055/057):** The owner explicitly requested that replacing a managed service URL prefill its saved value. Only `POST /api/admin/model-connections/{connection_id}/edit-endpoint`, guarded by the existing owner session, same-origin check and CSRF, may return `{connection_id, revision, base_url}` with `Cache-Control: no-store`. It accepts no arbitrary URL, reads the exact current encrypted revision, rejects host-managed/unknown connections with 404 and unavailable secret storage with 503, and makes no provider request or mutation. List/detail metadata remains URL-free; API keys, secret references and environment values are never returned. The UI fetches only on the explicit Replace URL action, keeps the result in the active form only, clears it on cancel/toggle-off/teardown, and ignores responses after a form or revision change. Loading disables URL editing/submission; failure permits retry or manual entry. No readback URL may enter browser storage, public drafts, exports, logs or snapshots. This narrow exception supersedes earlier blanket stored-URL readback prohibitions; stored-key prohibitions and destination-change credential rules remain unchanged.

**Environment-connection control amendment (2026-09-12, ADR-031):** The authenticated model-service panels can replace or delete startup-environment defaults. Replacement asks for the complete new URL because the environment value is never displayed; the resulting owner-managed revision takes precedence on later starts. If the old connection has a key, explicitly replace or remove it; a no-key Ollama connection may remain no-key. Delete dependent model profiles first. Successful connection deletion persists a secret-free suppression marker, so leaving the environment variable unchanged does not recreate the card. Back up and restore runtime SQLite together with the model-secret key; the override table is part of runtime migration 21.

**Connection-rebinding amendment (2026-09-13, ADR-032):** Changing an effective service setting now updates directly referencing editable model candidates in the same transaction, clears their prior test evidence, refreshes their cards, and asks for one explicit retest; do not edit-save each model again. Public-active, previous last-known-good, reindexing, and frozen batch work stay on their historical provider revision. Migration 22 repairs safe candidates stranded by earlier updates and adds no endpoint/key readback or automatic model call.

**Session-resume amendment (2026-09-13, ADR-033):** Reloading `/admin` now resumes a still-valid HttpOnly-cookie session through strict same-origin `POST /api/admin/session/resume`; it does not require another launcher grant. CSRF remains in browser memory and is reissued only for the valid session. Expired, revoked, or boundary-invalid sessions continue to show the launcher/password recovery surface.

**Status:** Draft operational contract through approved Technical Specification 0.2.6; connection/profile implementation is present, model-first guided integration and release evidence remain pending
**Audience:** a single owner self-hosting RepoNPC

Technical Specification 0.2.1 and ADR-015 through ADR-028 freeze the index CLI, external embedding profiles, deployment-aware private administration, profile-specific owner access, guided owner-onboarding, vLLM provider preset, anonymous public GitHub resolution, and bounded GitHub batch-analysis contracts. The 0.2.0 local-launch implementation and 0.2.1 OAuth/public-read PAT removal are integrated. Phase 5 still owns the final clean-host, live-provider, real GitHub Profile/browser, Compose, CLI, backup/restore, and release-document checks.

This guide defines the operating experience the implementation must provide. Implemented commands are exercised at their delivery-phase gates; prospective commands must still be exercised and corrected against the release candidate before this document is marked complete.

The 0.1.9 amendment makes external embedding profiles mandatory and keeps administration private through SSH/VPN or route allowlisting. The 0.2.0 amendment separates access by deployment profile: `loopback_evaluation` uses a passwordless one-use launcher grant, while `production` and every non-loopback administration path retain local password setup/recovery. The 0.2.1 amendment removes GitHub OAuth and browser-entered public-read PATs; public discovery/analysis uses anonymous REST capacity. A non-standard port is not a security control.

The 2026-08-30 audit and ordered release fixes are tracked in `SPEC_AND_ENGINEERING_REMEDIATION_PLAN.md`. In particular, a command shown as a planned release contract below is not an assertion that the current CLI implements it.

## 1. Deployment topology

The supported production shape is:

- one RepoNPC application container serving built React assets and FastAPI under one origin;
- one persistent data volume containing runtime SQLite, downloaded bundles, active/previous pointers, and safe update state;
- a public HTTPS reverse proxy/load balancer supplied by the operator;
- an explicitly configured external OpenAI-compatible service, private vLLM service, or private Ollama service;
- GitHub Actions/GitHub Releases providing immutable index bundles.

The application listener is private to the host/container network. The reverse proxy may publish visitor routes, but `/admin` and `/api/admin/*` MUST be denied to public Internet networks and exposed only through loopback, a private LAN/VPN, or an allowlisted management network. For a headless host, the preferred path is an SSH tunnel to the same Web Admin; do not publish a second management port.

No PostgreSQL, Redis, vector database, or indexer process is required in the public deployment. Multiple application replicas are outside v1.

## 2. Prerequisites

- A public GitHub account/profile and repository containing `reponpc.yml`.
- Owner-selected public GitHub repositories.
- Docker Engine with Compose v2 on x86_64 Linux (reference host: 4 CPU cores, 8 GB RAM plus chat-model needs).
- A public domain and HTTPS termination.
- A supported chat model plus at least one external embedding provider (`ollama`, `vllm`, or generic `openai_compatible`) compatible with the built index. The local sentence-transformers runtime is not a production prerequisite.
- For GitHub-backed admin configuration/custom-asset reads, writeback, and dispatch only: a fine-grained GitHub token scoped to the configuration repository. It is not required to create the owner, sign in, validate pasted YAML or character uploads, preview a built-in character, generate README snippets, or inspect local bundle status.
- For bundle publication: GitHub Actions enabled with workflow `contents: write` permission in the configuration/deployment repository.

## 3. Prepare public configuration

1. Copy `reponpc.example.yml` to `reponpc.yml` in the configured repository.
2. Replace placeholder profile, repository slugs, owner claims, links, and character/card values.
3. Keep only public information. Never add tokens, password hashes, API keys, internal URLs, or private-repository names.
4. Validate the same file through the index workflow/CLI before publication.
5. Review every owner claim as a public statement that may be cited verbatim by visitors.

The default configuration repository may be the GitHub Profile repository (`owner/owner`) or a separate public deployment repository.

### Guided setup (0.1.4)

An authenticated new owner normally uses the guided flow instead of authoring YAML first:

1. Enter a GitHub username/profile URL or manually add a public repository slug/URL.
2. Select from public metadata. Discovery uses unauthenticated GitHub API capacity, does not use the fine-grained writeback token, and may ask the owner to retry after GitHub rate limiting.
3. Confirm the exact selected repositories before any source is downloaded or model capacity is consumed.
4. Choose either `Analyze for suggestions` or `Continue manually`. Analysis is optional and consumes GitHub/provider capacity; the manual action is available before preflight and on every blocker/failure, without requiring a failed request. The current 0.1.7 implementation may analyze the confirmed set as one durable bounded batch.
5. Explain personal contribution and review facts, model inferences, and proposed owner assertions separately. Confirm or edit role/summary/claims before draft generation. Model unavailability never blocks manual contribution entry.
6. Use Back/Edit selection when needed. Changing a repository/ref/include/exclude identity invalidates only its selection-bound plan/result; removed repositories lose only their own contribution data, while profile and unaffected repository input remain. `Start over` is a separate confirmed destructive action.
7. Validate and preview with the existing model-free local operations. With no GitHub writeback token, copy or download `reponpc.yml`; with the token, review the exact configured repository/branch/path before saving and separately dispatching publication.

Existing saved configuration is loaded into the guided editor for return editing. Unsaved guided state is limited to the current authenticated browser session and clears on logout or successful save. Saving or downloading does not make private data safe: the resulting configuration is intended to become public. Raw repository bodies, provider prompts/outputs, credentials, tokens, and private provider URLs are never saved in browser storage; guided draft generation preserves configuration fields outside the guided surface.

Version 0.1.7 supersedes the earlier synchronous one-repository execution lifecycle with one owner-scoped durable batch and bounded item stages. Each repository retains an active-execution deadline of 120 seconds and the configured provider deadline (45 seconds by default); queue, owner pause, and GitHub rate waiting do not spend active execution time. Under 0.2.1, analysis uses only the selected provider/model plus anonymous REST capacity, has no credential/provider fallback, shares generation capacity fairly, and does not consume the anonymous public daily-chat counter. These constraints do not make analysis mandatory: manual authoring, validation, preview, copy, and download remain available.

Treat connections as independent capabilities rather than one global ready flag:

- **Sign in:** local-launch or production password access is independent of GitHub.
- **Read public repositories for analysis:** anonymous REST capacity affects discovery/analysis; no OAuth or public-read PAT is requested.
- **AI analysis:** provider readiness affects suggestions, not owner-entered contribution text.
- **Save to GitHub:** writeback readiness affects remote save, not validate/preview/copy/download.
- **Publish portfolio:** workflow/publication readiness affects dispatch/activation, not the local draft.

Every unavailable primary action must state which capability is missing, how to configure/recheck it, and which unaffected local action remains available. Cache hits, semaphore counts, rate-budget internals, and predictive estimates belong in Advanced diagnostics rather than the first-run critical path.

## 4. Create deployment secrets and the owner session

Generate a unique IP pseudonymization key (example operator command):

```bash
openssl rand -base64 48
```

Store GitHub/provider/IP-HMAC values in separate files in the repository-local `secrets/` directory
(which is excluded from the image build context), mounted read-only below `/run/secrets/` by
`compose.yml`. Point the corresponding `_FILE` variables at `/run/secrets/<name>` in `.env`; do not
set both direct and file forms. Create the directory and files before starting Compose, and restrict
their permissions to the deployment operator.

For `production`, start the application after configuring the IP-HMAC key, then issue a setup code against the persistent runtime volume:

```bash
docker compose exec app reponpc admin setup-code
```

The command prints one random 256-bit code. It expires after 15 minutes, a new invocation invalidates the prior unused code, and runtime SQLite stores only its SHA-256 digest. Open `/admin` through loopback/SSH/VPN and enter that code with your chosen local username/password. Production passwords must contain 15–128 Unicode code points; no uppercase, number, or symbol composition rule applies, but common/compromised passwords are rejected. Owner creation, Argon2id hashing, code consumption, and the initial session commit atomically; after success, setup cannot be reopened.

For the local Windows `loopback_evaluation` launcher, do not run setup-code and do not create an account. After readiness the launcher runs the equivalent of `reponpc admin launch-token`, stores only a two-minute one-use grant digest, and opens `/admin#local-launch=<grant>`. The browser exchanges it for the normal protected session and removes the fragment immediately. Refreshing or reopening `/admin` in that browser resumes the still-valid session without another grant; a direct visit with no valid session shows the relaunch instruction. If any bind/base URL/host setting is non-loopback or trusted-proxy handling is enabled, environment validation must reject this profile before startup.

There is no RepoNPC default username or password. For automated/pre-provisioned legacy deployments only, the non-echoing `docker compose run --rm app reponpc admin hash-password` command may be used to set both `REPONPC_ADMIN_USERNAME` and `REPONPC_ADMIN_PASSWORD_HASH`. Providing that pair disables the Web first-owner flow.

Restarting preserves the durable owner plus only hashed session and CSRF values in runtime SQLite. Refresh rotates the session and CSRF token, logout revokes the current session, and logout-all verifies the local password before incrementing the durable session epoch.

### GitHub token permissions

Create a fine-grained token for exactly `REPONPC_CONFIG_REPOSITORY`:

- Metadata: read;
- Contents: read/write;
- Actions: write only when admin workflow dispatch is enabled.

No organization, issue, pull-request, package, secret, or unrelated repository access is needed.

### GitHub public-read credential removal (0.2.1)

GitHub OAuth and browser-entered public-read PATs are retired. Do not create OAuth Apps or configure the retired client, callback, or encryption-key variables. Legacy routes return `410 GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED`. Existing runtimes apply migration 14, which removes OAuth/public-read rows without decrypting them; protected backups may still contain encrypted legacy bytes. Migration 15 adds only bounded anonymous metadata/exact-SHA resolution cache rows and contains no token, archive, repository body, prompt, or provider body.

Public repository discovery and analysis use anonymous, fixed-origin REST requests and exact full commit SHA archives. Completed immutable resolution is reused after a rate reset, so a large 1–50 selection makes durable forward progress instead of restarting at repository one. Anonymous rate limits can pause work; the UI reports a safe retry time and permits manual continuation. `REPONPC_GITHUB_TOKEN` and `REPONPC_GITHUB_TOKEN_FILE` remain independent writeback credentials for explicit config/material writes and workflow dispatch only.

### Headless/private administration

Do not publish an admin listener to `0.0.0.0` on the public Internet, and do not treat a high or unusual port as protection. Bind the host port to loopback when possible. For a remote Linux host, forward the existing Web Admin through SSH and open it locally:

```bash
ssh -N -L 8090:127.0.0.1:8000 user@host
```

Then browse to `http://127.0.0.1:8090/admin`. Headless/SSH/VPN operation uses the `production` profile and its password even though the browser-facing end of an SSH tunnel is localhost; the passwordless launcher grant is reserved for a directly loopback-bound evaluation process with no trusted proxy. SSH is only the transport and does not create another authentication protocol. For a persistent GUI, use Tailscale/WireGuard or a LAN interface restricted by a firewall. If a public visitor site is required, configure the reverse proxy to allow only `/`, static assets, and `/api/public/*`; deny `/admin` and `/api/admin/*` except from the private management network.

### Local password recovery

If the owner forgets the password while the runtime volume is intact, run the host-only recovery command from the same release image:

```bash
docker compose exec app reponpc admin set-password --data-dir /var/lib/reponpc
```

The command creates or updates only the local Argon2id hash and applies the production policy. It does not reopen first-owner setup, alter writeback credentials, or print the password. Use it before moving a passwordless loopback runtime to production, or when a production password is forgotten. If the runtime database is lost, restore the protected backup first.

## 5. Configure the provider

### Provider-neutral setup and guided order (0.2.3 target)

The owner chooses chat and content-finder (embedding) models independently in Web Admin. No provider/model is preselected on a clean deployment. Enter the service protocol, API base URL, optional write-only API key and model name, explicitly test, then explicitly use the profile. Model lists are optional assistance; an unsupported list endpoint does not prevent testing a typed model ID. Tests use small synthetic inputs and may consume provider capacity.

The first-run AI path must complete both role selections before repository analysis: models -> repositories -> analysis -> contributions -> profile -> preview/draft. Welcome is not counted. The alternative manual path is available immediately and omits model setup/analysis rather than presenting them as completed. Model controls must be available from guided mode and contextual recovery, not only the advanced/raw-YAML surface.

Public gateways use HTTPS and a base path such as `https://api.example.com/v1`; append no operation path manually. Ollama native URLs use the private service base such as `http://127.0.0.1:11434`. Addresses are resolved from the RepoNPC host/container, not the visitor browser: container loopback points at the container, not the owner's desktop. Existing private-network validation still applies. Never expose a local model publicly to make an index runner reach it.

Host-managed environment/secret-file settings remain supported. Managed connections store keys through protected server storage and return only configured status, never their stored value or private address. Changing a destination requires an explicit credential choice. Preserve and test the secret store plus its separate host protection material during backup/restore; losing it must not silently create an empty store over existing encrypted data. Exact packaging/key-store setup is an implementation contract-preparation deliverable in `MODEL_SETUP_IMPLEMENTATION_HANDOFF.md`.

In Web Admin, a host-managed card may be edited or deleted. Editing requires the full replacement API address (for example `http://127.0.0.1:22434` when Ollama is not listening on 11434); RepoNPC does not reveal or prefill the environment URL. After saving, the card is owner-managed and later environment changes do not overwrite either the connection or its owner-edited model profile. Deletion fails safely while a Chat/Embedding profile still refers to the connection; move or delete those model settings first. Once deletion succeeds, restart does not recreate the environment card until runtime state is deliberately reset/restored by the operator.

When a saved connection's provider, URL, or key changes, RepoNPC automatically moves only its editable, inactive candidate model settings to the new revision and marks them as requiring a fresh model test. The model cards refresh after the save, so a second model edit-save is not part of recovery. Retest remains explicit because it sends synthetic provider requests. Public-active, previous last-known-good, currently reindexing, and already running analysis work keep the old protected revision; unrelated model settings do not change.

No-model startup must still reach health and protected administration. Manual drafting/preview/export remains usable. A tested chat service does not imply embeddings. Admin project analysis requires an explicitly selected tested chat/embedding pair but does not require a published bundle; it uses bounded temporary derived-index work and must not publish or activate that index. Public visitor chat remains unavailable until the separately validated compatible bundle and public model lifecycle are ready. A runtime connection does not imply the index runner can reach it. Index-builder credentials are provisioned independently; no UI export contains them. Figma and a managed GGUF/Hugging Face runtime are outside this implementation package.

**Current-source status (2026-09-10):** Managed connection, Chat profile and Embedding profile code/panels exist, so earlier text saying the form is wholly absent is obsolete. The guided flow still hides those panels, goes from repository confirmation to analysis, and projects public model status into the analysis step. Clean no-model startup can leave no usable provider runtime after later selection. Do not advertise the model-first flow, same-process first analysis, or full 0.2.2/0.2.3 acceptance until AC-053 through AC-060 pass. Use `ONBOARDING_FLOW_IMPLEMENTATION_HANDOFF.md` for the correction.

### Private Ollama

Set `REPONPC_CHAT_PROVIDER=ollama`, its private base URL, model name, and honest context/output limits. Do not publish Ollama's port to the Internet. If Ollama runs on the Docker host, use the platform's documented private host gateway rather than a public address.

RepoNPC uses Ollama's native `GET /api/tags`, `POST /api/chat`, and `POST /api/embed` routes. Chat requests set `stream: false`, structured requests use `format`, and output limits use `options.num_predict`.

Official references: [Ollama API introduction](https://docs.ollama.com/api/introduction), [chat](https://docs.ollama.com/api/chat), [embeddings](https://docs.ollama.com/api/embed), and [structured outputs](https://docs.ollama.com/capabilities/structured-outputs).

The embedding profile/model used to build the bundle must exactly match runtime. After choosing Ollama, an optional recommendation is `qwen3-embedding:0.6b`; other curated choices include `bge-m3` and `embeddinggemma:300m`. None is a product default under 0.2.2. The local sentence-transformers adapter is benchmark/build-fixture-only. Model load or encode failure is explicit and never falls back to another provider/model.

#### Embedding model center

The Web Admin model center is provider-aware and keeps the primary path small:

- Ollama: show the curated catalog and models already installed on the configured Ollama host; an owner may explicitly pull or delete a bounded model ID, watch progress, and cancel. Pulls run on Ollama, not in the RepoNPC web process.
- vLLM: show models returned by the private `/v1/models` endpoint and let the owner probe/select one. The operator installs and serves the model on the vLLM host.
- Generic OpenAI-compatible: accept an explicit provider model ID and probe `/v1/embeddings`; there is no RepoNPC download action.

The catalog must show language coverage, context notes, license, approximate memory, and whether the provider supports pull/delete. RepoNPC never accepts arbitrary model URLs, local filesystem paths, shell commands, or unverified archives. After selecting a model, the UI shows probe result and reindex progress; it does not claim the profile is ready until a sample embedding and bundle identity check pass.

### OpenAI-compatible service

Set provider to `openai_compatible`, HTTPS base URL, model, and secret file. Confirm actual support for system role, structured output, usage, context, and timeout; RepoNPC capability configuration must not claim features the server lacks.

RepoNPC uses `GET /v1/models`, `POST /v1/chat/completions`, and `POST /v1/embeddings`. A successful model-list check verifies connection, authentication, response shape, and selected-model presence only; it does not prove model-specific chat, embedding, or structured-output behavior.

RepoNPC never silently moves between local and cloud providers. Operators should test health/status before sharing the public page.

Official references: [OpenAI API overview](https://developers.openai.com/api/reference/overview), [Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), [embeddings](https://developers.openai.com/api/reference/resources/embeddings/methods/create), and [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

### Private vLLM service

Set `REPONPC_CHAT_PROVIDER=vllm`, use the server's `/v1` base URL, and configure the exact served chat model. The model must support chat and have a valid chat template. The preset reuses RepoNPC's OpenAI-compatible transport but permits an explicitly configured private HTTP address; it does not create a third protocol or fallback path.

For embeddings, run an embedding/pooling model with the OpenAI-compatible `/v1/embeddings` endpoint and set `REPONPC_EMBEDDING_PROVIDER=vllm`. A generative chat model does not imply embedding support, so chat and embedding may use different vLLM instances, base URLs, models, and server-only API-key files. The embedding bundle identity remains `openai_compatible` and must exactly match at build/runtime.

Do not expose vLLM directly to the Internet. vLLM API-key enforcement does not protect every operational endpoint. Put it on a private network and, when a reverse proxy is required, allowlist only `GET /v1/models`, `POST /v1/chat/completions`, and `POST /v1/embeddings`; deny all other paths. Readiness fails safely when the selected capability test fails. Never place provider keys or private URLs in `reponpc.yml` or browser storage; only the protected write-only model form may accept newly entered values under 0.2.2.

The model-list readiness check cannot prove that the chat model has a valid template, that the embedding model was served with the correct task, or that the selected model supports structured output. Validate those capabilities explicitly before production traffic.

Official references: [vLLM OpenAI-compatible server](https://docs.vllm.ai/en/stable/serving/online_serving/openai_compatible_server/), [structured outputs](https://docs.vllm.ai/en/stable/features/structured_outputs/), [embedding/pooling models](https://docs.vllm.ai/en/stable/models/pooling_models/embed/), and [API server security](https://docs.vllm.ai/en/stable/usage/security/).

## 6. Publish the first index

The installed entrypoint is intentionally dual-purpose:

```bash
reponpc                         # start the application
reponpc serve                   # explicit equivalent
reponpc config validate reponpc.yml
reponpc index build --config reponpc.yml --output dist
reponpc index publish --bundle-dir dist
reponpc index publish-manifest --bundle-dir dist
```

Help and index/config commands do not load unrelated deployment startup settings. `index build` generates `public/profile.json`, the canonical character PNG, and all twelve locale/theme/format card variants from validated configuration. Built-in character composition and custom uploads both pass the same canonical `128x224` sprite validator before the exact bytes reach preview, GitHub writeback, card rendering, or bundle production. Missing or invalid inputs fail the build; production placeholders are never fabricated.

The `build-index.yml` workflow must:

1. validate configuration and repository allowlists;
2. resolve exact commits and index within limits;
3. run database/bundle/retrieval smoke checks;
4. publish immutable release asset `reponpc-index-{bundle_id}.tar.zst`;
5. verify asset reachability/checksum;
6. update `stable-manifest.json` on `reponpc-index` last.

The workflow may be run manually for first setup and is triggered by relevant configuration changes. A failed run must leave the prior stable manifest untouched. Do not hand-edit an immutable release asset under the same tag/name.

The final two commands enforce publication-last across separate workflow steps. `index publish` creates/uploads/verifies the Release asset and writes a local pending manifest below `dist`; it cannot update the remote pointer. `index publish-manifest` refuses to run without that verified pending artifact and performs the sole stable-branch mutation.

### Phase 2 formal benchmark

The formal gate builds a dedicated candidate image, then runs it with four CPUs, 8 GiB memory, and only the repository fixture/public questions mounted. The reviewed expected-evidence oracle remains on the host controller and is not copied into the candidate image. The controller records Docker inspect data, an oracle access probe, image digest, Docker/host/Python/library provenance, warm-up rounds, raw timing samples, Recall@8, bilingual parity, and warm p95. It derives acceptance from those observations; there is no supported flag for callers or the candidate to assert a pass.

## 7. Start the application

### Local Windows evaluation launcher

For a repository checkout on Windows, double-click `start-reponpc.cmd`, or run:

```powershell
.\scripts\start-reponpc.ps1
```

The launcher reads existing `REPONPC_*` overrides from `.env`, adapts container secret-file paths to ignored files below `secrets/`, forces and validates `loopback_evaluation`, binds only `127.0.0.1`, uses same-origin `http://localhost:8090`, builds stale Web assets, starts the server in the background, and waits for `/healthz`. It then creates a fresh two-minute one-use launch grant and opens `/admin#local-launch=<grant>`; re-running replaces any prior unused grant. It never prints or creates a username/password and never requires GitHub configuration to enter settings. On startup it compares the managed process state with the latest backend/frontend inputs; a stale process is stopped through its recorded process tree and replaced. Before stopping, it verifies the recorded PID and configured RepoNPC Python executable. If Windows rejects tree termination because of an elevation-context mismatch, the launcher falls back to directly stopping that same verified PID. An unknown process occupying the port is never terminated automatically.

The default local chat model is `qwen3.5:9b` when `.env` does not select another model. Provider readiness requires an external embedding profile compatible with the active bundle. The launcher never installs or downloads a local embedding runtime; use the Ollama model center/provider host or configure vLLM/OpenAI-compatible embeddings explicitly. It never fabricates a bundle or silently falls back to another provider. Logs and mutable state are kept below ignored `runtime-data/local/`. Use `-Port`, `-DataDir`, `-ChatModel`, `-SkipBuild`, `-NoBrowser`, or `-NoPause` for terminal-driven evaluation. This launcher is a development/evaluation convenience only; the supported production topology remains Docker Compose on x86_64 Linux behind HTTPS.

### Production Compose startup

The preceding launcher defaults describe the existing code, not the 0.2.2 target. The implementation must remove implicit model defaults in the launcher and environment loader together; deleting `.env.example` values alone would still leave hidden defaults. Explicit overrides and existing working profiles must survive.

Prepare `.env` from `.env.example`, mount secrets, verify the exact manifest/public base URLs, then:

```bash
docker compose build --pull
docker compose up -d
docker compose ps
```

The release implementation must document image name/tag pinning. Avoid `latest` in production. The container starts as non-root, owns only its data directory, and reports setup-required until a valid compatible bundle activates.

Check:

```bash
curl --fail https://portfolio.example.com/healthz
curl --fail https://portfolio.example.com/readyz
curl --fail https://portfolio.example.com/api/public/status
```

`healthz` proves only process response. `readyz` requires active index/runtime/model compatibility. Status explains safe setup/degraded/offline states without secrets.

## 8. HTTPS reverse proxy

- Forward the original HTTPS host/proto and client address only from a trusted proxy included in `REPONPC_TRUSTED_PROXY_CIDRS`.
- Reject unknown hosts; redirect HTTP to HTTPS.
- Do not buffer `text/event-stream`; allow request duration beyond `REPONPC_CHAT_TIMEOUT_SECONDS` plus a small margin.
- Preserve application CSP, `nosniff`, referrer, and cookie headers.
- Set HSTS only after confirming the domain/subdomains are permanently HTTPS.
- Do not add wildcard CORS or expose admin through a different unapproved origin.

## 9. Publish the README card

After readiness:

1. sign in at `/admin`;
2. preview both locales/themes and character states;
3. select SVG, GIF, or PNG fallback in README snippet generation;
4. copy the Markdown into the GitHub Profile README;
5. test through the actual GitHub image proxy and click target;
6. increment `card.revision` after visible asset changes when cache invalidation is needed.

The image is not interactive. It links to the public HTTPS site.

The raster card renderer uses the bundled Noto Sans CJK TC font to keep Traditional Chinese output deterministic. Its SIL Open Font License and source notes ship beside the font under `src/reponpc/cards/fonts/`; preserve both files when redistributing a source or wheel build.

## 10. Updates, pinning, and rollback

The application polls the stable manifest with ETag at the configured interval. It downloads into staging, validates everything, smoke-tests, and atomically activates. It retains the active and previous valid bundle.

Admin index status must show active/previous/pinned/candidate version, last check, publication time, and a safe failure reason. An owner can pin a locally retained compatible bundle by ID; while pinned, newer versions are reported but not activated. Unpinning resumes normal activation.

Required v1 CLI equivalents for recovery:

```bash
docker compose exec app reponpc bundle status
docker compose exec app reponpc bundle verify <bundle-id>
docker compose exec app reponpc bundle pin <bundle-id>
docker compose exec app reponpc bundle unpin
```

Implementation must require explicit bundle IDs and refuse unknown/incompatible targets. Never repair a release asset in place; publish a new bundle.

## 11. Backup and recovery

Back up:

- `reponpc.yml` and character assets through Git (already versioned);
- the protected secret source/vault, outside RepoNPC data backups;
- persistent data directory or at minimum `runtime.sqlite` plus active/previous bundles/pointers.

`runtime.sqlite` contains the sole owner record, optional production Argon2id hash, hashed session/proof state, and profile metadata. Before the 0.2.1 migration it may also contain encrypted legacy OAuth/PAT connection records; older protected backups retain those encrypted bytes under the normal retention policy. Losing the database removes local authentication and embedding-profile continuity. The product intentionally has no unauthenticated Web password reset or setup reopening path. Protect and test this backup.

Before copying SQLite, use the verified online backup command or stop the application cleanly and back up the protected persistent data directory as one unit. The backup command refuses to overwrite an existing target and runs SQLite integrity verification before publishing the copy.

```bash
docker compose exec app reponpc runtime backup /var/lib/reponpc/backups/runtime.sqlite
docker compose exec app reponpc runtime check
```

Recovery order: restore secrets with correct permissions, restore/verify runtime database, start the pinned application version, validate local bundles, fetch manifest if necessary, and check health/readiness/admin access/card/chat plus the active embedding profile. Since configuration and immutable releases are in GitHub, runtime conversation data does not need recovery. Loopback evaluation restores access by minting a new launcher grant. Production uses host-only `reponpc admin set-password --data-dir <dir> [--username <owner>]`; it does not reopen setup or alter GitHub connections. Recovery readiness is established by clean-host tests for both profile paths.

## 12. Upgrades

1. Read release notes for application/index/runtime schema compatibility.
2. Back up runtime state and record current image/bundle IDs.
3. Pull a specific immutable image tag/digest.
4. Run the documented preflight/config/bundle checks.
5. Start the new image and verify health, readiness, status, admin, card, bilingual chat, and citations.
6. Keep the old image and prior compatible bundle until observation succeeds.

If the application fails before a migration commits, restore the old image. Runtime migrations must be transactional and have an explicitly documented downgrade/restore path. An incompatible index stays inactive until rebuilt; it must never be auto-mutated by the web process.

## 13. Credential rotation

- GitHub/provider key: create replacement, update secret file atomically, restart/reload as documented, verify health/writeback, then revoke old key.
- Pre-provisioned admin password: generate a new hash, update the paired username/hash secret, restart, use logout-all/session epoch revocation, verify login.
- An unauthenticated Web password reset or setup reopening path is not exposed. The host-only `reponpc admin set-password --data-dir <dir> [--username <owner>]` command is the approved break-glass procedure; it must be run on the host and tested against a production-like backup. Do not delete `admin_owner` or reopen `admin_setup` manually.
- IP-HMAC key: rotate during a maintenance window; existing pseudonymous rate rows no longer match and may be cleared safely without touching audit/bundle data.
- Suspected compromise: follow `SECURITY.md`, disable chat/writeback if needed, rotate all affected secrets, inspect Git/release/audit history, restore known-good image/bundle.

## 14. Capacity and cost controls

Start with `.env.example` defaults: 10 requests/minute/IP, two concurrent generations, 200 accepted chats/UTC day, 2,000-character questions, six history messages, and 1,000 output tokens. Lower them for expensive providers or small hardware.

Monitor safe aggregate accepted/rejected counts, retrieval/model latency, provider status, nullable token usage, and configured cost estimates. RepoNPC does not guarantee the provider's invoice; provider-side quotas/billing alerts remain recommended defense in depth.

## 15. Troubleshooting matrix

| Symptom | Check | Safe action |
| --- | --- | --- |
| `setup_required` | manifest URL/host, first workflow, bundle state | publish/fix a new bundle; do not bypass validation |
| `readyz` 503, profile works | model/embedding status and compatibility | fix configured provider/model; no cloud fallback |
| Update failed | checksum/schema/model/SQLite/smoke safe error | keep active bundle, republish corrected immutable bundle |
| GitHub save 409 | current blob SHA and recent Git change | reload/reapply manually; never force overwrite |
| Card seems stale | bundle/card revision, GitHub image proxy | confirm new asset, increment revision, use fallback |
| Chat 429 | IP bucket/concurrency/daily budget | wait or deliberately adjust operator limit |
| Citation opens old code | inspect commit in URL | expected: citations are immutable; publish new index for new code |
| Ollama unreachable | private network/DNS/model availability | restore private route; do not expose it publicly |
| vLLM unavailable/model absent | private route, `/v1/models`, served model, chat template or embedding model | restore the selected instance/model; do not switch providers silently |

## 16. Release completion items

Before this guide changes from Draft to complete, the release owner must run every shown RepoNPC/Compose command against a clean release candidate, replace assumptions with actual output, document image/version support and backup consistency behavior, and attach AC-036/AC-037 evidence.

The Phase 5 gate also requires every P0 item in `SPEC_AND_ENGINEERING_REMEDIATION_PLAN.md` to close, including provider-neutral model setup with an explicitly selected working embedding profile, deployment-aware password/recovery behavior, batch compatibility-route conformance, and no-dead-end owner journeys. AC-053 through AC-060 are unverified model-setup/model-first gates.

### 16.1 Current Milestone D–F verification record (2026-08-16)

| Check | Result | Release meaning |
| --- | --- | --- |
| Python format, lint, type, contract, integration, security, migration, cache, batch, and retrieval suites | Pass — `607 passed, 2 skipped` with Compose smoke excluded | D–E local automated evidence is complete; two skips remain part of the suite result. |
| Web format, lint, type, unit, and production build | Pass — Prettier/typecheck/build and `53` Vitest tests; ESLint exits zero with 8 existing Fast Refresh warnings | D–E frontend implementation has local build/test evidence. |
| Current-source browser smoke | Historical pass for the superseded 0.1.9 first-owner/login/admin flow | Must be rerun for the 0.2.0 local-launch, production-password, authenticated GitHub-connection, full viewport, and assistive-technology paths. |
| Docker image, Compose smoke, runtime-volume restart, and clean host | Blocked | Docker configuration and engine named-pipe access were denied on this host. |
| Windows launcher smoke | Partial / blocked | Launcher contract passed 5 tests; the stale `reponpc.exe` lock was cleared and frozen dependency sync plus environment validation completed. Full health smoke remains blocked by host-denied Hugging Face network access during embedding startup. |
| Ollama, vLLM, and generic OpenAI-compatible live capacity/timeout matrix | Not run | No owner-authorized live provider endpoints/models were available. |
| Real anonymous GitHub public-repository resolution, rate exhaustion, and exact-SHA archive run | Not run | Required by 0.2.1 after the anonymous REST resolver lands; OAuth/reconnect evidence is no longer a release gate. |

These results deliberately do **not** complete Milestone F. Keep the operations status Draft until every blocked or not-run release item has dated, safe evidence. AC-036's clean x86_64 Linux host gate is explicitly owner-directed deferred/not-run in this Windows worktree; the Windows launcher smoke and local test suite are not substitutes for that evidence and must remain a release blocker until a clean Linux run is attached.

**Latest rerun correction:** the non-Docker total is `607 passed, 2 skipped`; release-audit coverage is `13 passed` after adding the release-input gate test.

**Repair addendum (2026-08-16):** The non-Docker suite was rerun after the D-E repairs with `606 passed, 2 skipped`. The launcher contract passed 5 tests. A real launcher smoke cleared the stale `reponpc.exe` lock, completed frozen `uv sync`, and validated the environment, but startup health could not complete because this host denies outbound Hugging Face socket access while loading the local embedding model. Docker/Compose remains unavailable, live providers and real GitHub credentials remain unconfigured, and AC-036 remains deferred/not-run.

**0.2.1 correction addendum (2026-09-09):** The current Docker Desktop x86_64 Linux engine passed `tests/smoke/test_container.py` (`1 passed in 25.84s`), including image build, health/public-status checks, runtime-volume restart persistence, and isolated teardown; `docker compose config --quiet` also passed. This local Docker smoke does not replace AC-036 clean-host evidence.

## Novice model setup migration 19 (2026-09-12)

Latest follow-up: migration 20 adds nullable, at-most-2,000-character `last_error_message` columns to chat and embedding profiles in one transaction. Existing rows, selections and identities remain intact; historical records have no original message until an explicit retest. The new backend runs this migration during normal initialization, following the stopped-service runtime backup procedure. Use the matching frontend/backend together. Provider messages are structurally extracted and redacted under Technical Specification 11.5, not translated or inferred from HTTP codes. Failure rolls back both column additions. This correction did not restart the owner's service, call real providers, or modify its runtime database.

Migration 21 adds `host_managed_connection_overrides`, containing only a bounded connection ID, `managed|disabled` state, and timestamp. It preserves all existing connections/profiles/secrets. Back up stopped-service runtime SQLite and the separate model-secret key before upgrade; start the matching backend once to apply the migration. A migration failure rolls back the table creation. Restoring runtime SQLite without its matching secret key remains unsupported, and restoring an older runtime backup also restores the prior override/deletion choices.

Migration 22 records the non-secret provider label on each protected connection revision and transactionally rebinds safe inactive candidates that still point at an older revision. It clears their old probe observations/errors, increments an affected analysis selection generation, and preserves public-active, previous last-known-good, reindexing, frozen batch, and unrelated state. After upgrade, explicitly retest the affected model once; no migration or startup action calls Ollama/gateway automatically. Restore the pre-upgrade runtime SQLite and matching model-secret key together if migration fails.

Migration 23 adds nullable `analysis_batch_items.error_reason` with a database-enforced closed set of application validation outcomes. Existing batch rows receive null and remain readable. New failed items retain a safe reason across restart/reload; no upstream body, repository content, prompt, URL, key, or arbitrary exception text is stored. Start the matching backend and frontend together after the normal stopped-service backup. A failed migration rolls back the column addition; restore the pre-upgrade runtime SQLite if startup cannot complete.

Owner approved the twelve findings in UI_UX_REVIEW_2026-09-12.md for implementation with Luna max and Main integration. This supersedes the earlier pending-approval notes for those findings only.

Runtime migration 19 makes embedding_profiles.dimension nullable for untested settings and retains the 1–65536 bound for known dimensions. Active profiles require a concrete dimension. The migration transaction copies and restores analysis_model_selection and embedding_switch_intent with their original rows and foreign keys; it preserves the single-active index and rolls back all DDL/data changes on failure. Bundle schema and concrete embedding identities are unchanged. Follow the normal stopped-service runtime backup procedure before upgrading; start the new backend to load the code and run initialize. This development task did not restart the owner's running service or migrate its real runtime.

Compatibility: embedding create/update may omit dimension; old clients supplying valid dimensions still work. Connection writes default endpoint_action to replace; update clients may explicitly retain with an omitted/null base_url. Keys remain write-only with independent retain/replace/remove intent; renamed display labels do not rotate the connection revision. The installed Ollama list accepts an optional selected connection ID, with omitted-ID legacy behavior preserved. No configuration environment variables, dependencies or public bundle format were added.

Independent novice-setup fault evaluation additionally repaired model-key rotation error recovery: rollback runs while the database connection is live; failed BEGIN/UPDATE/COMMIT restores the old master key and preserves decryptable historical revisions. Tests use only synthetic keys in temporary stores. Process-kill atomicity across the key file and database remains outside this fault-path verification.

Chat probe parser follow-up (2026-09-12): load the matching rebuilt frontend/backend and explicitly retest old failures to obtain parser evidence. This change needs no new runtime migration. Tests now use the configured chat output cap (existing default 1,000, configuration maximum 2,000) rather than 32; actual billed generation depends on the provider. The existing 10-second probe deadline and one-call behavior remain. This implementation did not call the owner's provider, restart its process, or alter its settings.

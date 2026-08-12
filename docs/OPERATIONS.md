# RepoNPC v1 Operations Guide

**Status:** Draft operational contract; exact command output must be verified during implementation  
**Audience:** a single owner self-hosting RepoNPC

Technical Specification 0.1.1 and ADR-015 freeze the Phase 2 index CLI and build-time local-adapter boundary. Commands below remain Draft until their real closure gates pass.

This guide defines the operating experience the implementation must provide. Commands are the intended stable interface; because application code does not exist yet, they must be exercised and corrected against the release candidate before this document is marked complete.

## 1. Deployment topology

The supported production shape is:

- one RepoNPC application container serving built React assets and FastAPI under one origin;
- one persistent data volume containing runtime SQLite, downloaded bundles, active/previous pointers, and safe update state;
- a public HTTPS reverse proxy/load balancer supplied by the operator;
- an explicitly configured external OpenAI-compatible service or private Ollama service;
- GitHub Actions/GitHub Releases providing immutable index bundles.

No PostgreSQL, Redis, vector database, or indexer process is required in the public deployment. Multiple application replicas are outside v1.

## 2. Prerequisites

- A public GitHub account/profile and repository containing `reponpc.yml`.
- Owner-selected public GitHub repositories.
- Docker Engine with Compose v2 on x86_64 Linux (reference host: 4 CPU cores, 8 GB RAM plus chat-model needs).
- A public domain and HTTPS termination.
- A supported chat model and embedding provider compatible with the built index.
- For admin writeback: a fine-grained GitHub token scoped to the configuration repository.
- For bundle publication: GitHub Actions enabled with workflow `contents: write` permission in the configuration/deployment repository.

## 3. Prepare public configuration

1. Copy `reponpc.example.yml` to `reponpc.yml` in the configured repository.
2. Replace placeholder profile, repository slugs, owner claims, links, and character/card values.
3. Keep only public information. Never add tokens, password hashes, API keys, internal URLs, or private-repository names.
4. Validate the same file through the index workflow/CLI before publication.
5. Review every owner claim as a public statement that may be cited verbatim by visitors.

The default configuration repository may be the GitHub Profile repository (`owner/owner`) or a separate public deployment repository.

## 4. Create deployment secrets

The implementation must provide a non-echoing password hash command:

```bash
docker compose run --rm app reponpc admin hash-password
```

It prompts twice and prints one Argon2id PHC hash. Store the hash as `REPONPC_ADMIN_PASSWORD_HASH`; never store the plaintext password.

Generate a unique IP pseudonymization key (example operator command):

```bash
openssl rand -base64 48
```

Store GitHub/provider/IP-HMAC values in separate files in the repository-local `secrets/` directory
(which is excluded from the image build context), mounted read-only below `/run/secrets/` by
`compose.yml`. Point the corresponding `_FILE` variables at `/run/secrets/<name>` in `.env`; do not
set both direct and file forms. Create the directory and files before starting Compose, and restrict
their permissions to the deployment operator.

### GitHub token permissions

Create a fine-grained token for exactly `REPONPC_CONFIG_REPOSITORY`:

- Metadata: read;
- Contents: read/write;
- Actions: write only when admin workflow dispatch is enabled.

No organization, issue, pull-request, package, secret, or unrelated repository access is needed.

## 5. Configure the provider

### Private Ollama

Set `REPONPC_CHAT_PROVIDER=ollama`, its private base URL, model name, and honest context/output limits. Do not publish Ollama's port to the Internet. If Ollama runs on the Docker host, use the platform's documented private host gateway rather than a public address.

The embedding adapter/model used to build the bundle must exactly match runtime. Phase 2 installs the default `local_sentence_transformers` model only through the locked optional indexer dependency used by GitHub Actions and the formal benchmark image; the normal application runtime image is not enlarged solely for indexing. Phase 3 supplies runtime query-provider health/readiness integration. Model load or encode failure is explicit and never falls back to another provider/model.

### OpenAI-compatible service

Set provider to `openai_compatible`, HTTPS base URL, model, and secret file. Confirm actual support for system role, structured output, usage, context, and timeout; RepoNPC capability configuration must not claim features the server lacks.

RepoNPC never silently moves between local and cloud providers. Operators should test health/status before sharing the public page.

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

Help and index/config commands do not load unrelated deployment startup settings. `index build` generates `public/profile.json` from validated configuration/index data and, until Phase 4 integrates the card/character producer, requires all non-profile public assets in the documented `public/` input directory. Missing or invalid assets fail the build; production placeholders are never fabricated.

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

## 10. Updates, pinning, and rollback

The application polls the stable manifest with ETag at the configured interval. It downloads into staging, validates everything, smoke-tests, and atomically activates. It retains the active and previous valid bundle.

Admin index status must show active/previous/pinned/candidate version, last check, publication time, and a safe failure reason. An owner can pin a locally retained compatible bundle by ID; while pinned, newer versions are reported but not activated. Unpinning resumes normal activation.

Required CLI equivalents for recovery:

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

Before copying SQLite, use the implementation's online backup command or stop the application cleanly. The release must provide and verify:

```bash
docker compose exec app reponpc runtime backup /var/lib/reponpc/backups/runtime.sqlite
docker compose exec app reponpc runtime check
```

Recovery order: restore secrets with correct permissions, restore/verify runtime database, start the pinned application version, validate local bundles, fetch manifest if necessary, and check health/readiness/admin login/card/chat. Since configuration and immutable releases are in GitHub, runtime conversation data does not need recovery.

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
- Admin password: generate a new hash, update secret, restart, use logout-all/session epoch revocation, verify login.
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

## 16. Release completion items

Before this guide changes from Draft to complete, the release owner must run every shown RepoNPC/Compose command against a clean release candidate, replace assumptions with actual output, document image/version support and backup consistency behavior, and attach AC-036/AC-037 evidence.

# RepoNPC Architecture Decision Log

**Document status:** Accepted on 2026-08-10  
**Approval rule:** These records were accepted together when the project owner approved `TECHNICAL_SPEC.md` 0.1.0. A later incompatible change requires a new ADR; do not silently rewrite an accepted decision.

## ADR-001: Use a modular monolith

- **Status:** Accepted
- **Decision:** The React application, FastAPI API, retrieval orchestration, provider adapters, admin service, bundle manager, and card renderer are modules in one deployable application image. The indexer is a CLI from the same Python package and runs in GitHub Actions.
- **Why:** One-owner self-hosting benefits from a single release, shared schemas, and low operational overhead. Module boundaries preserve the option to split services later.
- **Consequences:** Internal interfaces must remain explicit. CPU-heavy indexing does not run in the public web process.

## ADR-002: Separate the GitHub card from the interactive site

- **Status:** Accepted
- **Decision:** GitHub receives a script-free linked SVG/GIF card. All chat and interactive RPG behavior runs on an external RepoNPC deployment.
- **Why:** GitHub Markdown cannot execute the JavaScript required for a secure interactive application.
- **Consequences:** The card must communicate value without interaction, and deployment requires a public HTTPS URL.

## ADR-003: Use SQLite for bundle search and runtime state

- **Status:** Accepted
- **Decision:** Each immutable index contains one read-only SQLite database with FTS5 tables and vector blobs. Mutable sessions, revocations, rate counters, update status, and audit records live in a separate runtime SQLite database on a persistent volume.
- **Why:** SQLite is portable, inspectable, supports atomic replacement and FTS5, and avoids operating a database server for a single portfolio.
- **Consequences:** Runtime state must never be written into an index bundle. Multi-replica deployment is outside v1 unless operators provide affinity and an external rate-limit store.

## ADR-004: Store normalized float vectors as blobs and rank them in process

- **Status:** Accepted
- **Decision:** Embeddings are normalized `float32` arrays stored with their dimension and model ID. At load time they are read into NumPy; query similarity uses an in-process matrix product. RRF is implemented in Python.
- **Why:** The expected curated corpus is small enough for brute-force vector search and does not justify a vector server or platform-specific SQLite extension.
- **Consequences:** The corpus has explicit chunk/vector limits. A future approximate index requires a new bundle schema and ADR.

## ADR-005: Publish immutable bundles through GitHub Releases

- **Status:** Accepted
- **Decision:** GitHub Actions publishes a versioned `tar.zst` bundle as a GitHub Release asset. A stable manifest on the dedicated `reponpc-index` branch points to the active release asset and its checksum.
- **Why:** Readers need a stable discovery URL while citations and bundle contents remain immutable.
- **Consequences:** Publication writes the immutable asset before changing the stable manifest. Runtime activation is checksum-verified and atomic, with rollback to the last known-good bundle.

## ADR-006: Abstract both chat and embedding providers

- **Status:** Accepted
- **Decision:** Model integrations implement RepoNPC-owned interfaces and declare capabilities. v1 includes OpenAI-compatible HTTP adapters and Ollama adapters. The index manifest records the exact embedding provider/model/dimension contract.
- **Why:** OpenAI-compatible servers and Ollama differ in endpoints, streaming, roles, structured output, context limits, and error behavior.
- **Consequences:** There is no silent provider fallback. An embedding mismatch makes a bundle not ready rather than producing corrupt ranking.

## ADR-007: Separate evidence classes and let the server own citations

- **Status:** Accepted
- **Decision:** All evidence is classified as `OWNER_ASSERTION`, `REPOSITORY_FACT`, or `MODEL_INFERENCE`. The model emits only evidence IDs. The backend validates IDs, enforces person-claim policy, and constructs immutable GitHub links.
- **Why:** Repository presence does not prove personal responsibility, and free-form model URLs are not trustworthy.
- **Consequences:** Owner claims need stable IDs in configuration. Unsupported person-level claims are rejected or qualified. Citation rendering never trusts model-supplied URLs.

## ADR-008: Use SVG with a static first frame and provide GIF fallback

- **Status:** Accepted
- **Decision:** The primary README card is a self-contained, script-free animated SVG whose first frame is complete. The service also renders a GIF compatibility asset and a static PNG preview.
- **Why:** SVG offers crisp themes and lightweight animation, while GitHub image caching and client behavior can suppress animation.
- **Consequences:** Card output is sanitized, contains no remote assets, has strict response headers, and is verified on a real GitHub Profile.

## ADR-009: Use single-admin password sessions and least-privilege GitHub writeback

- **Status:** Accepted
- **Decision:** v1 has one configured admin identity. The server verifies an Argon2id password hash and issues revocable, short-lived server-side sessions in secure cookies with CSRF protection. A fine-grained GitHub token may write only to the configured configuration repository, and the application allowlists `reponpc.yml` plus `assets/character/`.
- **Why:** GitHub OAuth adds unnecessary onboarding and permission complexity for a single-owner deployment.
- **Consequences:** The operator must generate a password hash and token, terminate HTTPS, protect runtime storage, and rotate credentials. The browser never receives the GitHub token.

## ADR-010: Keep public presentation configuration in Git

- **Status:** Accepted
- **Decision:** `reponpc.yml` and approved character assets are the source of truth. The admin UI edits them through GitHub's contents API using blob-SHA conflict detection; it does not maintain a competing configuration database.
- **Why:** Git provides reviewability, rollback, and a natural trigger for index rebuilding.
- **Consequences:** Concurrent edits return a conflict for manual resolution. Secrets are environment-only and cannot be written through the admin UI.

## ADR-011: Serve the built web application from FastAPI under one origin

- **Status:** Accepted
- **Decision:** The production image builds the Vite application and serves its static output with the FastAPI application. Public and admin APIs use the same origin. Broad CORS is disabled by default.
- **Why:** Same-origin deployment simplifies self-hosting, cookies, CSRF, headers, and documentation.
- **Consequences:** Development may use Vite proxying to FastAPI. A separately hosted frontend is unsupported unless the operator deliberately configures a narrow origin allowlist.

## ADR-012: Use pnpm and uv with locked dependencies

- **Status:** Accepted
- **Decision:** Frontend dependencies use pnpm and `pnpm-lock.yaml`; Python uses a PEP 621 `pyproject.toml`, uv, and `uv.lock`.
- **Why:** Both support reproducible, fast local and CI workflows.
- **Consequences:** Agents must update lockfiles in the same change as dependency declarations and may not introduce a second package manager.

## ADR-013: Validate the complete answer before streaming it publicly

- **Status:** Accepted
- **Decision:** RepoNPC buffers the provider's complete answer envelope, validates evidence IDs, person-claim rules, inferences, links, and Markdown, then emits the accepted text as SSE token chunks.
- **Why:** True pass-through token streaming can expose an invented citation or unsupported personal claim before the backend knows the complete structure and cannot retract it.
- **Consequences:** Time to first visible token includes the full provider generation. The UI still receives a streaming rendering contract and must show a thinking state during generation/validation. Future speculative streaming needs a new security design and ADR.

## ADR-014: Use one canonical 4-by-7 character sheet

- **Status:** Accepted
- **Decision:** Built-in composition and custom uploads both produce a transparent `128x224` PNG consisting of four `32x32` frames for each of seven ordered states: idle, walk, listen, think, talk, success, and offline.
- **Why:** One fixed format keeps animation, validation, card generation, preview, reduced motion, and custom assets interoperable.
- **Consequences:** Custom artists must follow the documented grid. Changing dimensions, rows, or state order is a versioned asset-contract change.

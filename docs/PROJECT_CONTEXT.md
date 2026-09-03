# RepoNPC Project Context

**Document status:** Maintained product context; implementation/design-review status current through Technical Specification 0.1.9 on 2026-08-30
**Audience:** product owner, implementation Agents, reviewers, contributors  
**Canonical product name:** RepoNPC  
**Tagline:** Meet the NPC who knows your code.

## 1. Why this project exists

A conventional GitHub profile can show pinned repositories, contribution graphs, and a decorated Profile README, but it still asks a visitor to inspect many repositories and infer what the developer built, why decisions were made, and what the developer personally contributed. Recruiters and other visitors often do not have the time or technical context to perform that investigation.

RepoNPC turns a curated set of public repositories into an interactive, evidence-backed portfolio. A pixel-art RPG character gives the profile a memorable identity; the character's answers give visitors a fast way to explore the owner's work; immutable GitHub citations let them verify important claims.

The product is not merely a decorative README widget and is not a general-purpose coding Agent. It is a self-hosted portfolio presentation and question-answering system whose answers are bounded by evidence selected by the owner.

## 2. Current project state

As of the recoverable-capability UX/specification review and ENGD-001/002/003/006 decisions on 2026-08-30:

- `TECHNICAL_SPEC.md` 0.1.9 is approved and application implementation is authorized;
- Delivery Phases 1 through 4 have substantial local automated evidence for the production index CLI, immutable bundle lifecycle, hybrid retrieval, runtime model adapters, grounded chat, immutable citations, cost controls, bilingual visitor experience, owner administration, character/card assets, GitHub writeback, and publication integration. This is not a complete release claim, and the later P0 regressions listed below reopen their affected gates;
- Delivery Phase 5 (release hardening, current Docker/clean-host evidence, and remaining manual checks) is the next implementation boundary;
- the guided owner-onboarding amendment in version 0.1.4 was owner-approved, implemented, and verified on 2026-08-14; it replaces raw-YAML-first administration with a guided default while retaining raw YAML as advanced mode;
- the version 0.1.5 vLLM amendment names vLLM as a private-network-capable OpenAI-compatible preset while preserving the existing transport, bundle identity, browser, secret, and no-fallback boundaries;
- the version 0.1.6 amendment adds GitHub OAuth Web Flow with PKCE as an alternative sign-in/link method for the same sole owner, encrypted public-read credential records, and a dual-authentication admin surface; Milestones A–C were implemented and locally verified on 2026-08-16;
- version 0.1.7 adds the exact-SHA archive resolver and durable bounded batch engine; D–E local automated verification is complete while external/live release evidence remains incomplete;
- version 0.1.8 makes unconfigured OAuth entry points actionable through a safe host-side setup guide rather than leaving them disabled;
- the 2026-08-30 implementation/specification walkthrough found that optional analysis could still become a mandatory gate, repository selection could be changed only through destructive reset, and several unavailable actions lacked a complete recovery/alternative path. Existing FR-025/FR-027/FR-028/NFR-003 and AC-019/AC-025/AC-032/AC-040 wording now explicitly forbids those dead ends; application regressions remain to be implemented and verified;
- the same walkthrough found additional P0/P1/P2 engineering risks in the default embedding image/profile, production password policy, recovery-readiness signal, legacy analysis compatibility path, unimplemented operations commands, unused configuration contracts, oversized modules, and duplicated acceptance evidence. ENGD-001/002/003/004/006 and UXD-006 are now owner-approved and their implementation gates are tracked in `SPEC_AND_ENGINEERING_REMEDIATION_PLAN.md`; the remaining UXD/ENGD decisions and release evidence work remain open in `OWNER_REVIEW.md`;
- v1 remains the complete product described here, not a reduced MVP;
- milestones are delivery and verification boundaries, not permission to remove later v1 features.

### 2.1 Handoff implementation ledger (working tree)

This ledger records what is actually present after the previous Agent handoff. It is not a new requirement. The working tree contains substantial **uncommitted** changes from earlier work; documentation approval must not be mistaken for release completion.

| Area | Implemented or partially implemented now | Still incomplete / must not be claimed as done |
| --- | --- | --- |
| Existing v1 baseline | Index/build and publish flows, immutable bundles, retrieval/chat/provider runtime adapters, citations, limits, owner/admin surfaces, assets, GitHub writeback, and batch-related code have local evidence from the existing test suite. | Phase 5 clean-host, Docker, live-provider, OAuth, browser/accessibility, and release evidence is not complete. |
| Owner authentication | Setup-code flow, local-owner/session primitives, GitHub OAuth/link endpoints, and host-side password commands exist in code. | Local-first setup is not yet enforced end-to-end; GitHub-only compatibility branches remain; deployment-aware password policy, common-password blocking, and full recovery proof are missing. |
| ENGD-001 embedding | Ollama/OpenAI-compatible (including vLLM preset) runtime adapters and identity/probe helpers exist. Examples default to an external Ollama profile. | Profile registry CRUD, one-active enforcement, provider-aware model center, database migration, and index-builder wiring are not complete. A local embedding default/fallback still exists in code and is not acceptable for the approved production contract. |
| ENGD-006 operations | `serve`, `admin`, `config`, and `index` CLI groups exist; Web Admin is the intended daily interface. | The bounded `runtime` and `bundle` command groups are not all implemented or verified. No second public administration protocol has been added. |
| Deployment boundary | Compose host mapping defaults to loopback while the container listener may bind internally; SSH/VPN guidance is documented. | Runtime enforcement and clean-host topology verification remain release gates; a non-standard port must not be treated as protection. |

**Handoff rule:** use source code and test evidence for implementation status, and the approved specification/ADRs for intended behavior. In particular, do not report ENGD-001/002/003/006 as fully implemented until the gaps in the last column are closed. This section is the memory checkpoint for subsequent Agents and prevents a documentation-to-code drift from being hidden by optimistic status wording.

**Verification snapshot:** the 2026-08-30 handoff audit updated the four stale 0.1.9/external-embedding contract expectations, extended release-audit coverage through AC-050, and recorded a non-Docker `pytest` run of **612 passed, 2 skipped**. The Docker health/restart smoke remains unavailable on this host because Docker Desktop engine access fails, so this is not a clean release gate.

If `TECHNICAL_SPEC.md` returns to `Draft`, or an owner decision reopens an affected contract, implementation of that affected scope MUST stop until the project owner approves it again.

## 3. Intended users

### 3.1 Portfolio owner

A developer who wants a distinctive, self-hosted GitHub portfolio. The owner selects repositories, writes explicit claims about their role and achievements, chooses the visual character, configures a model provider, deploys the service, and controls costs and privacy.

### 3.2 Visitor

A recruiter, hiring manager, engineer, collaborator, or other GitHub visitor who wants to learn what the owner has built. The visitor is not expected to understand the repository layout or know which questions to ask.

### 3.3 Maintainer

The person operating RepoNPC. In v1 this is normally the portfolio owner. The maintainer updates configuration, publishes indexes, monitors service status, rotates credentials, upgrades versions, and rolls back invalid index bundles.

## 4. End-to-end journeys

### 4.1 Visitor journey

1. A visitor opens the owner's GitHub Profile README.
2. The README displays a static-safe, animated RepoNPC card with the pixel character and a clear call to action.
3. The visitor clicks the card and arrives at the separately hosted RepoNPC site.
4. The site shows a bilingual RPG-style scene, project overview, suggested questions, and model/index availability.
5. The visitor asks about projects, technologies, architecture, or the owner's stated contribution.
6. RepoNPC searches owner assertions and repository evidence, streams an answer, and attaches immutable GitHub citations.
7. The visitor opens a citation to verify the exact commit, file, and line range.
8. If the selected evidence cannot support the question, RepoNPC says so instead of inventing an answer.

### 4.2 Owner setup journey

1. The owner forks or clones RepoNPC and creates a configuration repository or uses the deployment repository as the configuration source.
2. The owner copies `reponpc.example.yml` to `reponpc.yml`, selects public repositories, and records owner-authored claims.
3. The owner configures character appearance, locale, retrieval settings, chat provider, and at least one external embedding profile. The model center recommends Ollama `qwen3-embedding:0.6b`; the owner may use Ollama pull/delete or connect a vLLM/OpenAI-compatible service. GitHub credentials are needed only for GitHub-backed admin operations.
4. GitHub Actions validates the configuration, indexes the selected commits, and publishes an immutable index bundle.
5. The owner starts the application with Docker Compose and runs `reponpc admin setup-code` on the deployment host.
6. The owner opens `/admin` through loopback/SSH/VPN, enters the 15-minute one-time code, and creates a local administrator username/password. After signing in, the owner may optionally bind GitHub OAuth for alternative sign-in/public-read access. RepoNPC stores the local Argon2id hash, encrypted GitHub credential material where linked, and signs the sole owner into the same local session.
7. The application verifies and activates the latest compatible bundle.
8. The owner previews the visitor page and README card, then pastes the generated snippet into the GitHub Profile README.

### 4.3 Owner update journey

1. The owner edits configuration in the admin UI or directly in Git.
2. Admin writeback validates the change and commits only allowlisted files with conflict protection.
3. GitHub Actions publishes a new immutable bundle.
4. The running service discovers the stable manifest using an ETag, downloads the bundle, verifies it, and atomically activates it.
5. If validation fails, the application keeps serving the last known-good bundle and reports the failure to the owner.

### 4.3.1 Headless owner access and recovery

Linux/headless operators use the same Web Admin through an SSH local-port tunnel, or a firewall-restricted private LAN/VPN. A high or unusual port is not a security boundary. Public visitor routes may be reverse-proxied separately, but admin routes remain private. If the owner forgets the password, the host-only `reponpc admin set-password --data-dir <dir>` command restores local access without reopening setup or changing the GitHub link; the local password is deliberately retained even when GitHub OAuth is enabled.

### 4.4 Guided owner-onboarding journey (0.1.4, approved)

This approved amendment replaces the blank raw-YAML-first post-login experience while preserving raw YAML as an advanced mode:

1. The owner enters a GitHub username/profile URL or manually supplies a public `owner/name` slug.
2. RepoNPC lists public repository metadata only; it does not download source or call a model yet.
3. The owner explicitly selects repositories and confirms the selected set; Back/Edit selection preserves unaffected work and invalidates only changed selection-bound plans/results.
4. The owner may immediately continue with manual contribution entry or explicitly analyze the confirmed set for suggestions under the existing indexing, provider, security, batch, and no-fallback boundaries. Model/GitHub readiness never makes manual authoring unavailable.
5. The owner explains personal contribution in natural language. Generated role, responsibility, achievement, and context text remains an unconfirmed proposal until the owner accepts or edits it.
6. The UI separates repository facts, model inferences, and proposed owner assertions, then generates a complete bilingual draft.
7. Existing validation and side-effect-free preview run before optional GitHub save and index publication.
8. Without GitHub public-read/writeback readiness, the owner may still author manually, validate, preview, copy, or download the generated YAML. Each unavailable integration states its cause, recovery, and unaffected alternative.

The flow does not add private repositories, whole-account source analysis, broader writeback-token permissions, model tools, or silent provider fallback. OAuth is an identity/public-read connection only; it never changes the selected-only analysis boundary. Existing saved configuration hydrates the guided editor for return editing, while unsaved onboarding state may resume only within the current authenticated browser session. Guided edits preserve fields outside the guided surface; saved configuration resumes from `reponpc.yml`.

## 5. Product goals

- Make a developer portfolio memorable through a polished pixel-RPG presentation.
- Let non-expert visitors understand selected projects through natural-language questions.
- Make factual answers verifiable with immutable repository citations.
- Clearly distinguish owner statements, repository facts, and model inferences.
- Support hosted OpenAI-compatible models plus privately reachable vLLM and Ollama models, with at least one external embedding profile and provider-aware model management.
- Let one owner self-host and configure the complete experience without editing application source; daily settings live in Web Admin, while bootstrap/recovery/backup/rollback remain bounded host CLI tasks.
- Treat security, prompt-injection resistance, cost control, accessibility, and bilingual behavior as v1 requirements.

## 6. Non-goals for v1

- A multi-tenant hosted SaaS, team workspace, billing system, or marketplace.
- Indexing private repositories.
- Visitor accounts, OAuth device flow, or multi-user GitHub onboarding.
- Autonomous code execution, repository modification by the LLM, or tool use by the LLM.
- A general repository coding assistant or replacement for source browsing.
- A generic model marketplace/downloader; model installation is provider-owned, with only curated Ollama pull/delete exposed by the admin UI.
- Multiple owners or multiple NPCs in one deployment.
- A navigable RPG world, combat, inventory, quests, or keyboard-controlled gameplay.
- Proving employment, authorship, seniority, or business impact from Git history alone.
- Making the GitHub README itself interactive; GitHub does not allow the application JavaScript needed for chat.

## 7. Product principles

1. **Evidence before eloquence.** A shorter supported answer is better than a persuasive unsupported answer.
2. **Owner claims remain owner claims.** Repository access does not prove the owner's personal role or impact.
3. **The model is replaceable.** Product contracts belong to RepoNPC, not to one model vendor.
4. **Repository content is untrusted.** Source files and documentation can contain prompt injection and never become instructions.
5. **The index is reproducible and immutable.** Every citation must resolve to the exact indexed commit.
6. **The last known-good state stays available.** A failed update must not take down a working portfolio.
7. **Configuration is version controlled.** Public presentation choices are reviewable and recoverable.
8. **RPG style serves comprehension.** Animation and character design cannot replace accessible text, citations, or status feedback.
9. **Chinese and English are equal product surfaces.** Traditional Chinese is not a partial translation layered on an English-only system.
10. **Self-hosting must remain understandable.** Operators should not need a vector database cluster or several separately deployed services for one portfolio.
11. **Optional capabilities cannot create dead ends.** An unavailable integration must explain why, offer recovery, and leave unrelated local/public work usable; owners must not trigger a failure to discover a fallback.

## 8. Why the README card and application are separate

GitHub Profile READMEs support rendered Markdown and images but do not run arbitrary application JavaScript. Therefore RepoNPC uses two intentionally separate surfaces:

- the README card is a script-free SVG or GIF image and a hyperlink;
- the external site owns chat, streaming, animation state, accessibility behavior, admin functions, and model access.

The first SVG frame must be a complete static card because GitHub or its image proxy may suppress animation. The card must never contain model credentials, visitor data, or code that attempts to bypass GitHub restrictions.

## 9. Evidence vocabulary

| Term | Meaning |
| --- | --- |
| `OWNER_ASSERTION` | A biography, role, responsibility, result, or contribution explicitly supplied by the owner. |
| `REPOSITORY_FACT` | A directly observable fact from a selected repository file or GitHub metadata at an exact commit. |
| `MODEL_INFERENCE` | A conclusion produced from one or more cited assertion/fact records and labeled as an inference. |
| Evidence record | A normalized searchable unit with stable ID, evidence class, content, and source metadata. |
| Chunk | A repository-derived evidence record, normally a symbol or bounded line range. |
| Citation | A server-validated reference from an answer to an evidence record and immutable GitHub permalink. |
| Index bundle | A checksummed, immutable package containing the searchable database, public configuration, assets, and manifest. |
| Stable manifest | A small mutable document that points to the latest published immutable bundle. |
| Last known-good bundle | The most recent bundle that passed compatibility and checksum validation and was activated successfully. |
| Suggested quest | A prewritten visitor question; it is a usability aid and not RPG gameplay. |

## 10. Source-of-truth order

When documents appear to conflict, use this precedence:

1. an explicit, recorded decision from the project owner;
2. `TECHNICAL_SPEC.md` and its requirement IDs;
3. `ACCEPTANCE_CRITERIA.md`;
4. `DECISIONS.md`;
5. `SECURITY.md`, `OPERATIONS.md`, and `SPRITE_FORMAT.md` within their documented domains;
6. `IMPLEMENTATION_PLAN.md`;
7. `SPEC_AND_ENGINEERING_REMEDIATION_PLAN.md` and `UX_SPEC_REVIEW.md` as non-normative review/execution guidance;
8. `README.md` and examples.

An implementation Agent must stop and ask the owner when a conflict would change externally visible behavior, security posture, data compatibility, or v1 scope. It may resolve purely internal and reversible details using the bounded-autonomy rules in the root `AGENTS.md`.

# RepoNPC Project Context

**Document status:** Maintained product context; implementation status current through 2026-08-13
**Audience:** product owner, implementation Agents, reviewers, contributors  
**Canonical product name:** RepoNPC  
**Tagline:** Meet the NPC who knows your code.

## 1. Why this project exists

A conventional GitHub profile can show pinned repositories, contribution graphs, and a decorated Profile README, but it still asks a visitor to inspect many repositories and infer what the developer built, why decisions were made, and what the developer personally contributed. Recruiters and other visitors often do not have the time or technical context to perform that investigation.

RepoNPC turns a curated set of public repositories into an interactive, evidence-backed portfolio. A pixel-art RPG character gives the profile a memorable identity; the character's answers give visitors a fast way to explore the owner's work; immutable GitHub citations let them verify important claims.

The product is not merely a decorative README widget and is not a general-purpose coding Agent. It is a self-hosted portfolio presentation and question-answering system whose answers are bounded by evidence selected by the owner.

## 2. Current project state

As of the Phase 4 closure based on commit `1b3d823` on 2026-08-13:

- `TECHNICAL_SPEC.md` 0.1.1 is approved and application implementation is authorized;
- Delivery Phases 1 through 4 are implemented and verified, including the production index CLI, immutable bundle lifecycle, hybrid retrieval, runtime model adapters, grounded chat, immutable citations, cost controls, bilingual visitor experience, owner administration, character/card assets, GitHub writeback, and publication integration;
- Delivery Phase 5 (release hardening, current Docker/clean-host evidence, and remaining manual checks) is the next implementation boundary;
- v1 remains the complete product described here, not a reduced MVP;
- milestones are delivery and verification boundaries, not permission to remove later v1 features.

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
3. The owner configures character appearance, locale, retrieval settings, model provider, admin authentication, and GitHub credentials.
4. GitHub Actions validates the configuration, indexes the selected commits, and publishes an immutable index bundle.
5. The owner starts the application with Docker Compose.
6. The application verifies and activates the latest compatible bundle.
7. The owner previews the visitor page and README card, then pastes the generated snippet into the GitHub Profile README.

### 4.3 Owner update journey

1. The owner edits configuration in the admin UI or directly in Git.
2. Admin writeback validates the change and commits only allowlisted files with conflict protection.
3. GitHub Actions publishes a new immutable bundle.
4. The running service discovers the stable manifest using an ETag, downloads the bundle, verifies it, and atomically activates it.
5. If validation fails, the application keeps serving the last known-good bundle and reports the failure to the owner.

## 5. Product goals

- Make a developer portfolio memorable through a polished pixel-RPG presentation.
- Let non-expert visitors understand selected projects through natural-language questions.
- Make factual answers verifiable with immutable repository citations.
- Clearly distinguish owner statements, repository facts, and model inferences.
- Support both hosted OpenAI-compatible models and privately reachable Ollama models.
- Let one owner self-host and configure the complete experience without editing application source.
- Treat security, prompt-injection resistance, cost control, accessibility, and bilingual behavior as v1 requirements.

## 6. Non-goals for v1

- A multi-tenant hosted SaaS, team workspace, billing system, or marketplace.
- Indexing private repositories.
- GitHub OAuth onboarding or visitor accounts.
- Autonomous code execution, repository modification by the LLM, or tool use by the LLM.
- A general repository coding assistant or replacement for source browsing.
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
7. `README.md` and examples.

An implementation Agent must stop and ask the owner when a conflict would change externally visible behavior, security posture, data compatibility, or v1 scope. It may resolve purely internal and reversible details using the bounded-autonomy rules in the root `AGENTS.md`.

# Superseded architecture decisions

## ADR-005: Publish immutable bundles through GitHub Releases

- **Status:** Accepted
- **Decision:** GitHub Actions publishes a versioned `tar.zst` bundle as a GitHub Release asset. A stable manifest on the dedicated `reponpc-index` branch points to the active release asset and its checksum.
- **Why:** Readers need a stable discovery URL while citations and bundle contents remain immutable.
- **Consequences:** Publication writes the immutable asset before changing the stable manifest. Runtime activation is checksum-verified and atomic, with rollback to the last known-good bundle.

## ADR-010: Keep public presentation configuration in Git

- **Status:** Accepted
- **0.2.2 amendment:** ADR-029 supersedes only the prohibition on authenticated entry of model connection credentials. Public presentation stays in Git; model credentials remain deployment-local and cannot be written into public YAML.
- **Decision:** `reponpc.yml` and approved character assets are the source of truth. The admin UI edits them through GitHub's contents API using blob-SHA conflict detection; it does not maintain a competing configuration database.
- **Why:** Git provides reviewability, rollback, and a natural trigger for index rebuilding.
- **Consequences:** Concurrent edits return a conflict for manual resolution. Secrets are environment-only and cannot be written through the admin UI.

## ADR-020: Add GitHub OAuth identity without broadening ownership or writeback (legacy; superseded by ADR-028)

- **Status:** Accepted on 2026-08-16.
- **Supersedes:** ADR-009/ADR-016 only where they require password-only authentication, and ADR-018 only where it excludes OAuth/public-read credentials. The GitHub-only first-owner/recovery clause is superseded by ADR-025.
- **Decision:** GitHub OAuth Web Application Flow with PKCE is an alternative authentication method for the sole RepoNPC owner. Setup still requires the host-issued code followed by local username/password creation; an authenticated local owner may then link GitHub. Login/link use distinct one-time transactions; the GitHub numeric user ID is the stable link. OAuth requests no repository scope, supports public-read only, and its encrypted credential is never reused for writeback. Explicit fine-grained PAT public-read credentials are a non-login fallback. Writeback remains the configured separate fine-grained credential.
- **Why:** The owner needs a familiar sign-in and a safe public-read connection without creating open registration, multi-user accounts, or broader repository permissions.
- **Consequences:** Runtime schema adds authentication methods, encrypted credentials, and OAuth transactions. Password/pre-provisioned login remains compatible and is always retained as break-glass recovery; removal of the local method is rejected. Later GraphQL/archive and durable batch work are explicitly outside this amendment.

## ADR-022: Keep GitHub OAuth entry points actionable before host configuration (legacy; superseded by ADR-028)

- **Status:** Accepted on 2026-08-30.
- **Supersedes:** ADR-020 only where its dual-authentication UI is described as disabled before OAuth configuration.
- **Decision:** GitHub setup, sign-in, link, and reauthentication entry points remain keyboard-operable when the deployment has not configured OAuth. Activating one opens a same-origin host-side setup guide dialog and does not submit an OAuth start request or redirect to GitHub. Once the server reports OAuth as configured, the same shared GitHub button performs the existing top-level Authorization Code Flow with PKCE S256. A public `GET /api/admin/github/oauth/setup-guide` returns only configured state, the canonical fixed callback URL, the fixed GitHub OAuth-App documentation URL, and a next-step label, with `Cache-Control: no-store`.
- **Why:** A disabled button gives ordinary users no actionable explanation and makes a deployment-only setup prerequisite look like a user-registration failure. An actionable guide preserves the security boundary while making the next safe step discoverable.
- **Consequences:** AC-043 and FR-031 gain the unconfigured-button/dialog behavior; frontend tests must cover icon/label uniqueness, focus management, bilingual copy, responsive layout, and no-secret rendering. The guide never accepts or returns client secrets, encryption keys, tokens, secret-file paths, or owner identity. OAuth token lifecycle/refresh remains a separate follow-up until explicitly implemented.

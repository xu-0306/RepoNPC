# Security history

## 15. Legacy GitHub identity and connection extension (0.1.6–0.2.0; superseded by 0.2.1)

This section records the migration source. ADR-028 removes these reachable OAuth/PAT behaviors; section 20 is normative for the replacement.

- OAuth Web Application Flow uses a fixed allowlisted GitHub authorization/token/user endpoint set, a random one-use state hash, PKCE S256, server-side code exchange, an existing RepoNPC session binding, and a connection-intent short-lived cookie. The normal session cookie is not the sole proof during GitHub's cross-site return.
- OAuth state, PKCE verifier, local session binding, and connection metadata are encrypted or hashed at rest. Tokens and PATs use a dedicated authenticated-encryption key that is independent of IP hashing, provider keys, OAuth client secret, and writeback token.
- OAuth requests no repository scope. Reported broad scopes, token/user endpoint errors, invalid user IDs, redirects, expiry, replay, wrong intent, missing RepoNPC session, and legacy login/setup starts all fail closed without issuing a session or consuming production setup/local-launch proof.
- The browser receives an authorization redirect and safe connection state only. It never receives access/refresh tokens, PATs, encryption keys, client secret, transaction verifier/state, token fingerprints, or raw upstream payloads.
- `identity_public_read`, `public_read`, and `writeback` are distinct credential purposes. A revoked/401 read credential requires explicit reconnection and cannot trigger selection of another credential. The configured writeback token is never copied into runtime credentials or used for identity/read preflight.
- GitHub is connection-only. It cannot create, authenticate, or recover the RepoNPC owner. Disconnecting it affects only public-read work. Production recovery uses host-only `reponpc admin set-password --data-dir <dir>`; loopback recovery mints a new local-launch grant through the launcher.

## 17. Legacy GitHub OAuth setup (0.1.8–0.2.0; removed in 0.2.1)

This historical section is retained only to explain migration scope. OAuth setup, callback, connection, and browser-entered public-read PAT controls are removed; compatibility routes return `410 GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED` and never process credentials.

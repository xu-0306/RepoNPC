# RepoNPC 0.2.0 本機管理員存取實作交接

**更新時間：** 2026-09-08（Asia/Taipei）  
**狀態：** 0.2.1 OAuth／公開讀取憑證退場已整合至根工作樹；clean-host／live release evidence 待完成  
**分支：** `codex/local-admin-access-0.2.0`  
**基底提交：** `f6a7829`  
**隔離工作樹：** `D:\RepoNPC\.agent-foreman\worktrees\local-admin-0-2`

> 2026-09-08 completion update: this implementation was independently reviewed and applied to `D:\RepoNPC`. The integration adds an explicit production recovery state when a migrated passwordless owner has no usable password, so the UI instructs the operator to run `reponpc admin set-password --data-dir <dir>` instead of rendering an unusable login form. It also makes an unspecified service profile default to production, preventing existing password-authenticated admin consumers from being silently treated as loopback. The detailed sections below remain the implementation worklog.
>
> 2026-09-08 0.2.1 follow-up: the owner approved removal of GitHub OAuth and browser-entered public-read PATs. OAuth work below is now legacy migration context. Continue from `docs/GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_PLAN.md` and ADR-028; preserve local-launch/production-password behavior and the independent writeback credential.

## 2026-09-09 0.2.1 implementation update

- Batch preflight now uses `GitHubRESTMetadataResolver` with fixed-origin anonymous REST calls. Repository metadata and explicit/default refs resolve to a validated 40-character commit SHA before archive retrieval. Requests use GitHub API headers only and never send `Authorization`; writeback credentials are not supplied to discovery or analysis.
- `UrllibGitHubArchiveTransport` now fetches exact-SHA archives anonymously while retaining redirect, size, archive, traversal, symlink, cancellation, and staging cleanup protections.
- GitHub OAuth/PAT setup-guide, callback, connection, and PAT routes return `410 GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED` without state mutation. Admin workspace no longer renders the connection card or PAT controls.
- Environment loading no longer reads OAuth/client-secret/callback or credential-encryption secret pairs. Legacy variable names remain recognized for one compatibility release but values/files are ignored. `REPONPC_GITHUB_TOKEN(_FILE)` remains writeback-only.
- Runtime migration 14 transactionally deletes OAuth transactions and `identity_public_read`/`public_read` credential rows while preserving owner, sessions, drafts, batches, bundles, and writeback configuration. Migration 15 persists bounded anonymous metadata/exact-SHA resolution for resumable rate-reset continuation. Existing protected backups may still contain encrypted legacy bytes.
- Review corrections and deterministic gates are complete: focused backend `109 passed, 2 skipped, 1 warning`; release-audit contracts `20 passed`; frontend `65 passed` plus external LocalLaunch `6 passed`; Ruff/mypy/Prettier/ESLint/typecheck/build/diff checks pass. See `docs/GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_HANDOFF.md` for the final full-suite rerun and outstanding browser/Docker/live-GitHub evidence.

## 1. 交接摘要

目前已完成 loopback 部署設定防線、SQLite migration 13、本機啟動 grant 的核心 auth service、嚴格 loopback API 交換端點，以及 GitHub OAuth 設定引導對話框的第一個 connection-only UI 葉節點。

變更已於 2026-09-08 套用至 `D:\RepoNPC` 根工作樹，且保留原始工作區既有的未提交文件與測試變更。變更目前仍未提交；最終 clean-host、真實瀏覽器／OAuth、Compose 與 release evidence 仍由 Phase 5 負責。

## 2. 已完成項目

### 2.1 loopback 部署設定防線

變更：

- `src/reponpc/config/environment.py`
- `tests/contract/test_environment.py`

行為：

- `loopback_evaluation` 僅接受 IPv4/IPv6 loopback bind 與 loopback public URL。
- 拒絕 wildcard、非 loopback、DNS-rebinding 形狀與不一致端點。
- loopback 模式拒絕任何 `trusted_proxy_cidrs`；production 仍保留既有 proxy 設定能力。

驗證：`29 passed, 2 skipped`。

### 2.2 SQLite migration 13

變更：

- `src/reponpc/runtime/database.py`
- `tests/integration/test_runtime_database.py`

行為：

- `admin_owner.password_hash` 可為 `NULL`，保留非空值必須是 Argon2id 的限制。
- `admin_auth_methods` 僅保留 `local_password`，移除舊 GitHub 登入身分資料。
- OAuth transaction 僅保留 authenticated connection intent；舊 `link` 轉成 `connection`，login/setup transaction 被丟棄。
- 清空舊 OAuth handoff。
- 新增只有一列 current state、只保存 digest 與時間戳的 `admin_local_launch_grants`。
- 既有 owner/session epoch/session、local password method 與加密 GitHub credential bytes 均有 migration preservation 測試。
- migration 失敗時有 rollback 測試，會維持 v12 schema 與資料。

驗證：`9 passed`。

### 2.3 本機啟動 grant auth service

變更：

- `src/reponpc/admin/auth.py`
- `tests/integration/test_admin_auth.py`

行為：

- `issue_admin_local_launch_grant(...)` 只在 `loopback_evaluation` 可用。
- grant 使用 32-byte 隨機值、兩分鐘 TTL，資料庫只保存 SHA-256 digest。
- 新 grant 會取代舊 grant。
- `consume_local_launch(...)` 使用 `BEGIN IMMEDIATE` 原子消耗 grant、建立或重用唯一 owner，再建立正常管理員 session。
- 併發消耗只有一個請求成功，且只會產生一個 owner 與一個 session。
- loopback 模式不再提供 setup code owner 建立或 password login。
- loopback `logout_all` 已改成需要新鮮 local-launch grant；production 仍需要密碼。
- nullable password owner 不會被舊 credential loader 誤處理。

驗證：`19 passed`。

### 2.4 本機啟動 grant API 與 request 邊界

變更：

- `src/reponpc/api/admin.py`
- `tests/security/test_local_admin_launch_security.py`
- `tests/security/test_admin_security.py`

行為：

- 新增 `POST /api/admin/session/local-launch`，成功後回傳既有 session body，並設定 `Secure`、`HttpOnly`、`SameSite=Strict` 的 `__Host-reponpc_session` cookie。
- grant 不會出現在回應 body 或 cookie。
- 端點要求：
  - deployment profile 必須是 `loopback_evaluation`；
  - ASGI request peer 必須是 loopback；
  - `Origin` 必須明確存在且符合已設定的 loopback origin；
  - `Host` 必須符合 allowlist 且 hostname 本身是 loopback；
  - 任何 `Forwarded` 或 `X-Forwarded-*` header 都會拒絕。
- 過期、未知、已消耗 grant 與 request-boundary 拒絕都使用 `401 / LOCAL_LAUNCH_DENIED` 的一般化錯誤，不反射 grant。
- `GET /api/admin/auth/methods` 已改成 `{mode, password, setup_required}`，不再宣告 GitHub 登入方式。
- 舊 `POST /api/admin/session/github/start` 與 `POST /api/admin/setup/github/start` 已固定回傳 `410 / GITHUB_LOGIN_REMOVED`。
- 既有 security test helper 已明確改用 production profile，測試密碼更新成符合 production 長度的值。

目前相關聯合驗證：`39 passed, 1 warning`。warning 是既有 Starlette TestClient/httpx deprecation。

### 2.5 Terra 實作的 GitHub OAuth 設定引導 UI 葉節點

變更：

- `apps/web/src/features/admin/GitHubOAuthSetupGuideDialog.tsx`
- `apps/web/src/features/admin/AdminPage.test.tsx`（主控撰寫／強化測試）

分工與審查：

- 實作由指定的 `gpt-5.6-terra` subagent 完成。
- 對話框新增必要的 `onContinue` callback。
- OAuth 已設定時顯示「Continue to GitHub」connection 動作；pending 時 disabled。
- OAuth 未設定時仍顯示 recheck。
- 英文與繁體中文已移除 GitHub sign-in／關閉即繼續的舊語意。
- 獨立 reviewer 曾指出舊登入文案；強化紅燈測試後由原 Terra implementer 修正，再審查通過。

驗證：聚焦 Vitest `14 passed`。

注意：`AdminPage.tsx` 尚未把 `onContinue` 接到 authenticated connection-only OAuth 流程，因此整體 TypeScript build 目前預期尚未通過。

## 3. 目前變更清單

已修改：

- `apps/web/src/features/admin/AdminPage.test.tsx`
- `apps/web/src/features/admin/GitHubOAuthSetupGuideDialog.tsx`
- `src/reponpc/admin/auth.py`
- `src/reponpc/api/admin.py`
- `src/reponpc/config/environment.py`
- `src/reponpc/runtime/database.py`
- `tests/contract/test_environment.py`
- `tests/integration/test_admin_auth.py`
- `tests/integration/test_runtime_database.py`
- `tests/security/test_admin_security.py`

新增：

- `tests/security/test_local_admin_launch_security.py`
- `docs/LOCAL_ADMIN_ACCESS_IMPLEMENTATION_HANDOFF.md`
- `.superpowers/sdd/local-admin-access-0-2/progress.md`（工作流程記錄，尚未決定是否納入版本控制）

目前約有 772 行新增、67 行刪除；此統計尚未包含未追蹤檔案。

## 4. 尚未完成，不能宣告完成

依建議順序：

1. **完成 local-launch auth/API 安全契約**
   - 新增獨立失敗 backoff/rate limit，不能與 production password login 混用。
   - 決定並測試 malformed/missing body 是否也必須收斂成相同 generic error；目前 FastAPI validation 仍可能回 400。
   - 把 loopback `logout-all` 的 HTTP request contract 改成 fresh grant，並補 request-boundary 與 replay 測試。
   - 檢查 `AdminAuthMethods` 簽名變更造成的所有呼叫端與測試影響。

2. **完成 launcher/CLI**
   - readiness 成功後才 mint grant。
   - 使用預設瀏覽器開啟 `/admin#local-launch=<grant>`。
   - 支援 `--no-browser` 的明確受控輸出，不把 grant 寫入 log、檔案、argv 或 query string。
   - loopback Uvicorn 必須停用 proxy-header trust；production 行為不得被破壞。
   - 更新 Windows one-click launcher contract tests。

3. **完成前端 local-launch bootstrap**
   - 只從 URL fragment 讀取 grant。
   - 立即用 `history.replaceState` 清除 fragment。
   - 呼叫 `POST /api/admin/session/local-launch`。
   - CSRF token 只留在記憶體。
   - loopback 未登入頁不得顯示註冊、密碼登入、setup code 或 GitHub 登入。
   - production setup/password 流程仍需維持。

4. **把 GitHub OAuth 完整轉成 authenticated connection-only**
   - `GET /api/admin/github/oauth/setup-guide` 改成需要 session。
   - 新增／轉換成 `POST /api/admin/github/connections/oauth/start`，需要 session、CSRF 與 same-origin。
   - OAuth service intent、transaction schema、callback 與測試統一使用 `connection`。
   - callback 不得建立 admin session 或 owner，不得走舊 handoff。
   - 移除或停用 `login_github`、`link_github`、`unlink_github` 等與 migration 13 不相容的舊 auth-method 路徑。
   - 把 Terra 對話框的 `onContinue` 接到這個 authenticated endpoint。

5. **全面回歸、文件與整合**
   - 修正所有仍依賴舊 GitHub-login auth-method response 的測試與前端型別。
   - 跑 Python formatter/lint/type/test、TypeScript format/lint/type/unit/build、安全回歸與相關 browser/accessibility tests。
   - 合併原始工作區中的 0.2.0 規格、README、examples 與 contract test 變更，避免覆寫擁有者工作。
   - 更新 campaign plan、progress 與 integration record。
   - 完成獨立 code/security reviewer 審查後才可提交或整合。

## 5. 已知風險與目前假設

- **尚未執行全測試套件。** 目前只證明聚焦測試綠燈，其他 OAuth、API schema、CLI 與 frontend tests 很可能仍因契約轉換失敗。
- **OAuth service 舊路徑與 migration 13 尚未完全對齊。** 若現在直接走舊 link/login callback，可能碰到新 schema 不接受的 intent 或 method。
- **setup guide 目前仍是 unauthenticated GET。** 這不符合 0.2.0 connection-only 最終契約。
- **local-launch rate limit 尚缺。** grant entropy、TTL、one-use、transaction 與 request boundary 已有，但抗連續猜測／濫用的獨立 backoff 還未落地。
- **對話框 prop 尚未完成上層 wiring。** 聚焦元件測試通過不代表 production build 通過。
- **未提交。** 工作樹內任何變更都尚未形成可恢復的 checkpoint commit。
- **原始工作區文件是另一組 dirty changes。** 整合時不可用 reset、checkout 或覆寫方式處理。

## 6. 可重現的聚焦驗證命令

Python 必須明確把工作樹 `src` 放入 `PYTHONPATH`，因為原始 `.venv` 的 editable install 指向 `D:\RepoNPC`：

```powershell
rtk proxy powershell -NoProfile -Command "[Environment]::SetEnvironmentVariable('CLAUDE_CONFIG_DIR','C:\Users\xu\.claude','Process'); [Environment]::SetEnvironmentVariable('PYTHONPATH','D:\RepoNPC\.agent-foreman\worktrees\local-admin-0-2\src','Process'); rtk proxy D:\RepoNPC\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/security/test_local_admin_launch_security.py tests/integration/test_admin_auth.py tests/security/test_admin_security.py -q"
```

前端工作樹透過 junction 重用原始 `node_modules`；Vitest 需使用 runner config loader 避免 Vite temp file 的 Windows EPERM：

```powershell
rtk proxy D:\RepoNPC\apps\web\node_modules\.bin\vitest.cmd run --configLoader runner --root D:\RepoNPC\.agent-foreman\worktrees\local-admin-0-2\apps\web src\features\admin\AdminPage.test.tsx
```

## 7. 原始工作區保護提醒

建立隔離工作樹前，原始 checkout 已有以下擁有者變更：

```text
 M .env.example
 M README.md
 M docs/ACCEPTANCE_CRITERIA.md
 M docs/DECISIONS.md
 M docs/OPERATIONS.md
 M docs/SECURITY.md
 M docs/TECHNICAL_SPEC.md
 M reponpc.example.yml
 M tests/contract/test_phase2_closure_spec.py
?? docs/LOCAL_ADMIN_ACCESS_HANDOFF.md
```

後續 Agent 必須保留這些變更，先比較再整合，禁止 reset、discard 或整批覆寫。

## 8. 規格追蹤

目前工作針對：

- FR-017、FR-029、FR-031、FR-034、FR-036
- AC-024、AC-041、AC-042、AC-043、AC-049、AC-050
- ADR-027

只有在第 4 節所有必要工作與第 5 節風險均關閉、相關驗證完整通過後，才能宣告這些 requirement/acceptance criteria 已由實作滿足。

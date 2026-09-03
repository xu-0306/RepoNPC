# P1-04 重構分析交接文件

**文件用途：** 提供下一位 implementation/review agent 進行 P1-04（高變更耦合）重構分析與分階段實作。

**目前狀態：** 僅完成分析與交接規劃；本文件不代表已開始重構，也不代表 P1-04 已關閉。

**來源要求：** `docs/PROJECT_CONTEXT.md`、`docs/TECHNICAL_SPEC.md`、`docs/ACCEPTANCE_CRITERIA.md`、`docs/DECISIONS.md`、`docs/SECURITY.md`、`docs/SPEC_AND_ENGINEERING_REMEDIATION_PLAN.md` 與目前測試/程式碼。

## 1. 問題背景

P1-04 的問題是多個模組同時握有 UI 狀態、HTTP 邊界、業務編排、外部連線和資料庫狀態，因此小改動也可能影響登入、批次分析、草稿產生、CSRF、憑證隔離或錯誤處理。

目前主要集中點（規格中的盤點數字，實際行數應在每次切片前重新量測）：

| 模組 | 規格盤點大小 | 主要耦合風險 |
| --- | ---: | --- |
| `apps/web/src/features/admin/AdminPage.tsx` | 約 2,558 行 | 同時負責登入/設定、GitHub、embedding、索引、導覽流程、批次輪詢、草稿保存和錯誤狀態。 |
| `apps/web/src/features/admin/GuidedOnboardingView.tsx` | 約 2,065 行 | 一個檔案包含導覽步驟、repository 選取、分析、貢獻編輯、profile、review、draft 和雙語文案。 |
| `apps/web/src/features/admin/BatchAnalysisPanel.tsx` | 約 959 行 | 批次狀態呈現、進度、事件、動作按鈕和錯誤展示集中在同一個 UI 模組。 |
| `src/reponpc/api/admin.py` | 約 1,549 行 | Pydantic request schema、授權/session、OAuth、GitHub、config、asset、index、onboarding、batch routes 和錯誤映射混在一起。 |
| `src/reponpc/admin/batch_resolver.py` | 約 1,624 行 | GitHub HTTP transport、GraphQL metadata、rate limit、archive staging/inspection、安全規則和 preflight planner 同檔。 |
| `src/reponpc/admin/batch_runtime.py` | 約 1,195 行 | SQLite schema 操作、批次狀態機、item lease、事件、cache、recovery 和 cleanup 同檔。 |
| `src/reponpc/admin/onboarding.py` | 約 1,008 行 | metadata discovery、source analysis、provider 呼叫、suggestion、draft 組裝、YAML 和安全錯誤轉換同檔。 |

這些大小只是風險訊號，不是重構目標。禁止為了降低行數而改變已接受的 API、狀態、資安規則或 v1 範圍。

## 2. 範圍與非目標

### 2.1 本次重構範圍

- 在既有行為測試鎖定後，逐步抽出 cohesive capability（單一責任且有明確輸入/輸出）。
- 為前端 container、feature reducer、presentational component 和 API client 建立清楚邊界。
- 為後端 routes、request/response schema、application service、domain policy、外部 adapter 和 persistence 建立依賴方向。
- 保留目前錯誤碼、認證/CSRF、批次狀態機、無 fallback、選取 repository 邊界、owner confirmation 和敏感資料不落地規則。
- 每一個切片均記錄測試、coverage/complexity 變化和回滾方式。

### 2.2 明確非目標

- 不以檔案行數、class 數量或「看起來更漂亮」作為完成條件。
- 不刪除或簡化 P2 功能（durable batch、cache、rate/fairness、exact-SHA、rollback 等）。
- 不新增 endpoint、修改既有 response/schema/state 名稱、改變 status/error code 或改變資料保存政策。
- 不把前端改成直接連線 provider/GitHub；provider secrets、token、private URL 仍只能留在 server。
- 不順便處理 P1-03、P1-05、P1-06 或 embedding/operations 等其他工作包。
- 不在 characterization tests 尚未建立前進行大型搬移或全面改名。

## 3. 現有責任盤點

### 3.1 前端

`AdminPage.tsx` 是目前的 authenticated admin composition root。它擁有 session、setup/login/logout、GitHub connection、embedding profile、config read/validate/preview/write、index dispatch/status、guided reducer、analysis batch 輪詢/SSE、contribution suggestion、draft persistence 和 GitHub setup guide 的副作用。它也把大量型別、API payload、錯誤轉換和 callback 傳入子元件。

`GuidedOnboardingView.tsx` 主要是呈現層，但同檔包含每個步驟的局部互動邏輯與文案：intro、repository discovery/selection、provider/analysis、contribution proposal、profile、review、draft。狀態轉移與序列化本身已在 `guidedOnboarding.ts`，應優先視為既有 seam，不要在第一次切片重寫 reducer。

`BatchAnalysisPanel.tsx` 應保持純呈現/事件回呼導向；批次資料取得與 action dispatch 應由 container 或 feature hook 擁有。

### 3.2 後端

`src/reponpc/api/admin.py` 應是薄 HTTP adapter：解析 request、驗證 session/CSRF/origin、呼叫 application service、把安全錯誤映射成公開 response。它目前還直接組合太多 request model、supplier 和 domain orchestration。

`src/reponpc/admin/onboarding.py` 的 `GuidedOnboardingService` 同時處理 discovery、resolve、分析、suggestion 和 draft。公開方法與錯誤碼是目前重要的行為邊界。

`src/reponpc/admin/batch_resolver.py` 可以按下列責任觀察，但不要一次全部拆完：

1. GitHub transport/URL/redirect/response 限制。
2. GraphQL metadata 和 credential selection。
3. rate budget/admission/persistence protocol。
4. archive staging、inspection、path/symlink/size 安全規則。
5. preflight plan、cache prediction、duration/capacity estimation。

`src/reponpc/admin/batch_runtime.py` 應分辨 persistence gateway 與 batch domain state machine。`BatchRuntimeStore` 的公開方法（create/get/active/transition/retry/claim/advance/complete/fail/cancel/events/recovery/cache）目前是 integration tests 直接使用的 seam，拆分時先保留 facade 或相容 adapter。

## 4. 目標依賴方向

建議採用下列單向依賴，避免 feature 互相 import 或 route 反向掌握資料庫細節：

```text
HTTP route / React page container
        |
        v
application service / feature controller
        |
        v
domain policy + typed contracts
        |
        +--> external adapters (GitHub/provider)
        +--> persistence ports --> SQLite/runtime database
```

前端建議方向：

```text
AdminPage (composition root)
  -> auth feature / config feature / onboarding feature / batch feature
  -> API client functions
  -> presentational components
```

- presentational component 不直接 `fetch`、不讀 sessionStorage、不決定 auth/CSRF。
- API client 集中 request、response decode 和 safe error code；不要把 raw response body 傳進 UI。
- reducer/serializer 保持純函式，所有副作用放在 feature controller/hook。

後端建議方向：

- route layer 不直接操作 `sqlite3`、archive path、provider transport 或 token。
- service 依賴 protocol/port，實作由 composition root 注入。
- 安全 policy（URL、archive、credential purpose、owner confirmation）屬 domain/application 層，不能因拆檔被繞過。
- persistence 只保存目前規格允許的 safe metadata；不可為了方便跨層傳遞 raw archive、prompt、provider body 或 credential。

## 5. 建議拆分順序

每一階段都應是可單獨 review、測試和回滾的小變更。下一階段只有在上一階段的 characterization、回歸和 dependency check 通過後才能開始。

### Stage 0：凍結基線

1. 記錄目前 commit/tree identity、Python/Node 版本、測試總量和各大模組行數。
2. 產生前端 reducer/state transition matrix、後端 route contract snapshot、批次狀態轉移表。
3. 確認目前 dirty worktree 中哪些變更屬於其他工作；不得將其回退或混入重構意圖。

### Stage 1：前端 API client 與 auth/connection 邊界

先從 `AdminPage.tsx` 抽出純型別、request helper、auth/setup/session、GitHub connection、embedding profile 的 client/controller。保留 `AdminPage` 作為 composition root，讓所有既有 callback 先透過 facade 轉接。

入口/出口：UI 行為與 API payload 不變；session、CSRF、logout-all、OAuth setup guide、provider credentials 均由既有測試保護。

### Stage 2：前端 guided feature

把 guided state controller（discover/resolve/analyze/batch/suggest/draft persistence）與 `GuidedOnboardingView` 的步驟呈現分開。優先重用 `guidedOnboarding.ts` reducer/serializer，將 `RepositoriesStep`、`AnalysisStep`、`ContributionsStep`、`ProfileStep`、`ReviewStep`、`DraftStep` 分成檔案時，不改 action 或 state shape。

`BatchAnalysisPanel` 在本階段只抽 presentation subcomponents；批次輪詢/SSE/action 仍由 feature controller 負責。

### Stage 3：後端 admin API 薄化

先分離 request/response models，再依 capability 建立 route router：auth/session、GitHub connection/OAuth、config/assets/index、onboarding、analysis batches。`create_admin_router` 可保留為組合入口，避免主程式的 router wiring 變更。

錯誤 mapping、`same_origin`、`authorize/protected` 行為必須集中到共用 dependency/helper，避免拆分後某一組 route 漏掉 CSRF 或 private-route policy。

### Stage 4：onboarding service 分層

保留 `GuidedOnboardingService` 相容 facade，內部再抽：

- metadata discovery/selection service；
- selected-only source analysis orchestrator；
- provider suggestion/response validation；
- contribution confirmation與 profile/draft assembler；
- YAML validation/serialization utility。

先搬純函式與 typed model，再搬副作用。任何 model output 必須繼續經 evidence ID、claim policy 和 owner confirmation 驗證。

### Stage 5：batch resolver 分層

建議順序為 transport/URL guard -> archive safety -> rate/credential -> metadata resolver -> preflight planner。每次只搬一個 cohesive boundary，並保留原 import path 的 re-export 或 facade，避免測試與 service 同時大改。

### Stage 6：batch runtime 分層

先抽 persistence port/repository，再抽 state transition/domain service，最後抽 event/cache/recovery helpers。`BatchRuntimeStore` 應暫時作 facade，確保既有 API route 和 worker 不需要同步改寫。

### Stage 7：移除相容層（可選）

只有在至少一個完整 release cycle、所有 caller 已遷移、coverage 和 contract snapshot 穩定後，才評估移除 facade/re-export。這不是 P1-04 第一階段的必要工作。

## 6. Characterization tests 與必要新增測試

### 6.1 既有測試入口

- 前端：`apps/web/src/features/admin/GuidedOnboardingView.test.tsx`、`tests/frontend/AdminPage.test.tsx`、`apps/web/src/features/admin/BatchAnalysisPanel.test.tsx`（若檔案存在，先確認目前名稱）。
- reducer/序列化：`apps/web/src/features/admin/guidedOnboarding.test.ts`。
- onboarding：`tests/unit/test_guided_onboarding.py`、`tests/integration/test_admin_onboarding.py`、`tests/security/test_admin_onboarding_security.py`。
- admin API/auth：`tests/integration/test_mvp_api.py`、`tests/integration/test_admin_auth.py`、`tests/security/test_admin_security.py`、`tests/integration/test_github_oauth.py`。
- batch API：`tests/integration/test_analysis_batch_api.py`、`tests/unit/test_batches.py`。
- resolver：`tests/unit/test_batch_resolver.py`、`tests/unit/test_batch_execution.py`。
- runtime：`tests/unit/test_batch_runtime.py`。

測試檔名可能隨工作樹變更；下一位 agent 必須先用 `rtk proxy rg --files` 和 `rtk proxy rg -n` 確認實際現況。

### 6.2 抽取前必須鎖定的行為

- 每個 admin route 的 method/path/status/error code、session/CSRF/origin 條件。
- guided reducer 每個 action 的 state transition，包括 Back、Edit selection、Reset、batch active 時的 navigation lock。
- sessionStorage 草稿的 key、size/sensitive-field 限制、save/logout 清除行為。
- batch 的 idempotency、唯一 active job、stale preflight、cancel/retry/restart recovery、event replay 和 cleanup。
- resolver 的 exact commit、credential purpose、no-fallback、redirect/URL/archive/path/size 安全限制。
- onboarding suggestion 的 evidence ID 驗證、owner assertion confirmation 和 bilingual YAML output。
- API response 絕不包含 token、provider URL、archive、prompt、raw model output、staging path。

### 6.3 建議新增的 characterization 輸出

- 可讀的 route contract JSON snapshot（只含公開 schema/status/error，不含 secrets）。
- guided state transition table test，而非只測單一 happy path。
- batch state transition matrix test，涵蓋每個非法 action。
- import/dependency direction check，禁止 route import persistence internals、component 直接 import provider client。
- public response redaction canary test，搬檔後仍確認敏感資料不會跨層流出。

## 7. 主要風險與防護

| 風險 | 可能結果 | 防護 |
| --- | --- | --- |
| React state/callback 閉包被拆壞 | 重新整理、locale、批次事件或 draft hydration race 回歸。 | 先抽純 client，再抽 controller；保留現有 reducer tests 和 browser smoke。 |
| route 分拆漏掉 auth/CSRF | admin endpoint 變成未保護或錯誤碼改變。 | 共用 dependency；逐 route contract/security tests；禁止直接複製 auth decorator。 |
| API model import circular dependency | 啟動失敗或 schema drift。 | models -> services -> routes 單向；共用 contracts 放低層模組。 |
| Batch facade 遺失 lease/transaction 邊界 | 重複生成、狀態遺失、runtime DB race。 | 先保留 `BatchRuntimeStore` facade；每個 SQL transaction 有 integration test。 |
| resolver 安全 policy 被移到錯誤層 | SSRF、archive traversal、敏感內容落地。 | security policy 由 domain service 擁有；保留 hostile fixture/security tests。 |
| 相容 re-export 過早移除 | 隱藏 caller 或 plugin 失效。 | 先搜完整 import graph，至少保留一個相容週期。 |
| dirty worktree 混入驗收 | 無法知道回歸來自重構或其他 agent。 | 每個切片記錄 diff ownership、測試命令、tree identity；不可宣稱 clean release。 |

## 8. 驗收條件

P1-04 只能在下列條件全部有證據時宣稱完成：

1. characterization tests 在第一次抽取前通過，所有切片後仍通過。
2. Python/TypeScript format、lint、typecheck、unit/integration/security/frontend tests 通過；失敗或未執行項目明確記錄。
3. 公開 API 的 method/path、schema、status/error code、session/CSRF 行為沒有未核准變更。
4. guided state shape、batch state/event semantics、draft storage policy、owner-confirmation policy 沒有未核准變更。
5. import graph 符合目標依賴方向；沒有 route->SQLite、component->provider 等越層依賴。
6. coverage 不得因重構下降；若新增檔案導致整體百分比變化，需提供前後 absolute covered lines 和原因。
7. 量測並記錄模組 cyclomatic complexity、public symbols、import fan-in/fan-out；改善應以耦合和可測試性為主，不以行數為唯一指標。
8. 安全 regression tests 確認 secrets/private URLs/raw bodies/staging paths 不會出現在 response、logs、browser storage、fixtures 或 snapshots。
9. 至少完成一輪瀏覽器 admin smoke：登入/登出、guided back/edit、draft save/resume、batch failure/retry、locale switch、keyboard focus。
10. 交接文件、測試報告和 acceptance ledger 指向同一個 source identity；不得沿用其他 dirty tree 的 pass total。

## 9. 下一位 agent 的交接問題

開始實作前，請在分析報告中回答：

1. 第一個切片要負責哪一組檔案，哪些檔案明確不碰？
2. 哪些現有 public symbols 必須保留相容 import？相容層預計保留多久？
3. 前端是否採 feature hooks，或採明確 service/controller class？請以目前 React pattern 和測試成本為依據。
4. 後端 request/response models 要集中於 `api/contracts`，還是按 capability 分檔？如何避免 circular imports？
5. `GuidedOnboardingService` 和 `BatchRuntimeStore` 的 facade 由誰維護，何時才允許移除？
6. 如何在重構期間量測 coverage、complexity、fan-in/fan-out，並把結果寫入 P1-05 ledger？
7. 哪些測試只能在 Docker/clean host/browser/live provider 執行？這些不能被本地重構測試冒充完成。
8. 若發現拆分需要改 API、schema、state 或 security contract，是否先停下來請 owner 建立新決策/ADR？答案應為是。

## 10. 建議起始命令

以下僅是分析/驗證起點；執行時應遵守 repository 的 `rtk` 前綴要求，並依當時工作樹調整測試範圍：

```text
rtk proxy rg --files apps/web/src/features/admin src/reponpc/admin src/reponpc/api tests
rtk proxy rg -n "AdminPage|GuidedOnboardingView|BatchAnalysisPanel|BatchRuntimeStore|GuidedOnboardingService" apps/web/src src tests
rtk proxy powershell -NoProfile -Command "Get-Content docs/SPEC_AND_ENGINEERING_REMEDIATION_PLAN.md | Select-Object -Skip 137 -First 35"
rtk proxy powershell -NoProfile -Command "Get-ChildItem apps/web/src/features/admin,src/reponpc/admin,src/reponpc/api -File -Recurse | Sort-Object Length -Descending | Select-Object -First 20 FullName,Length"
```

任何實作前，下一位 agent 必須重新閱讀根目錄 `AGENTS.md` 和本文件，確認目前規格狀態與其他 agent 的 ownership；不得因本文件而自動取得修改 API 或安全邊界的授權。


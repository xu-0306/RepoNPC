# 模型設定與引導流程實作審核

審核基線：2026-09-10；文件完成：2026-09-11（Asia/Taipei）。結論：**已有實作，但尚不符合兩份 handoff 的完成條件；應先修正下列缺陷，再進行整合驗收。**

本次依擁有者要求審核目前 working tree，沒有修改應用程式、正式 runtime、既有測試或 Terra 的變更，也沒有把 handoff 裡的實作指令當成本次開發授權。UI 建議另見 [管理工作區 UI 改善計劃](ADMIN_WORKSPACE_UI_IMPROVEMENT_PLAN.md)。

## 1. 基線與證據範圍

- 基準 commit：`f6a7829abc07e6ad58614f3b15dfb652bca69239`，包含審核當時未提交的 working-tree 內容；這不是僅對該 commit 的審核。
- 依據：Approved Technical Specification 0.2.3、AC-053～060、ADR-029/030、SECURITY，以及 `MODEL_SETUP_IMPLEMENTATION_HANDOFF.md`、`ONBOARDING_FLOW_IMPLEMENTATION_HANDOFF.md`。
- 已先讀取項目記憶與核心文件；歷史測試數字不算本次證據。
- 來源快照：`.tmp/review-model-ui-20260910/source-start.json`。報告的行號屬於此 working-tree 版本，後續修改可能位移。
- 2026-09-11 04:05 +08:00 再核對快照中的 216 個檔案，內容 hash 均未改變；本次新增的兩份文件不在初始快照內。
- 檢查方式：程式與文件交叉檢閱、範圍內現有測試、五項獨立故障重現、格式／lint／型別／production build，以及本機頁面的唯讀存取。
- 無法僅憑 working tree 將每一項變更歸屬 Terra；以下描述「目前實作」，不推測作者或任務是否已宣告完成。

## 2. 需要修正的發現

### R1 · P1：禁止的 provider 目的地仍能進入實際 HTTP transport

**位置：** `src/reponpc/admin/model_connections.py:521`、`:550`；`src/reponpc/providers/http_transport.py:76`、`:123`；production adapter 組装在 `src/reponpc/main.py:961`。

新連線入口只做 URL 結構及部分 HTTP 私有主機檢查；`validate_resolved_provider_addresses()` 沒有 production 呼叫者。`UrllibProviderHttpTransport` 直接交給 urllib 解析／連線，沒有受驗證位址綁定。`https://169.254.169.254/v1` 可通過連線建立與 `ProviderOrigin`，並抵達 opener。拒絕 redirect 已存在，但不能替代目的地與 DNS 防護。

**影響：** 經新管理表單輸入的位址可繞過規格禁止的 metadata/link-local 目的地邊界；DNS 變更也未由實際連線路徑約束。這不是已證實的未登入攻擊；入口仍需管理員授權。

**獨立重現：** 以合成 connection 建立上述位址，用假的 opener 截止請求，結果 `forbidden_destination_reached_opener: true`。沒有真的連線到 metadata 服務、發出網路請求或使用真實 key。

**修正方向：** 在所有模型 request/stream/list/pull 的實際 transport 邊界套用相同 egress policy；解析、驗證與實際連線使用同一受允許目的地，處理 IPv4/IPv6、mapped addresses、private opt-in、public-to-private rebinding、redirect 與 proxy 行為。補 transport 層測試，不能只直接測 helper。

**對應：** FR-039、AC-055、Technical Specification 11.5、SECURITY 21。

### R2 · P1：合法的空前綴 embedding 會讓批次建立失敗

**位置：** `src/reponpc/admin/analysis_selection.py:175`；呼叫端 `src/reponpc/admin/batch_runtime.py:424`。

`AnalysisModelPair.safe_dict()` 正常保存空字串 `query_prefix`／`passage_prefix`；`from_safe_dict()` 卻以必須非空的 `_required_text()` 還原。空前綴是合法 embedding 語意，並非缺少模型設定。

**影響：** 使用無需任務前綴的已測模型時，持久化 pair 驗證拒絕建立 batch，阻斷主要分析流程。

**獨立重現：** 相同 fixture 的空前綴 roundtrip 得到 `ANALYSIS_MODEL_PAIR_INVALID`，真正 `BatchRuntimeStore.create_batch()` 回 `VALIDATION_ERROR`；只改成非空前綴的對照組可建立批次。這是 deterministic storage／domain 重現，不是 live provider E2E。

**修正方向：** 前綴驗證要求字串且有界，允許空字串；保留實際 identity，不替換為猜測的前綴。補空／非空前綴的 pair roundtrip、preflight/create、restart/cache 一致性測試。

**對應：** FR-042、AC-059/060，以及 AC-054/056 的 embedding 語意。

### R3 · P1：既有密文遇到遺失主密鑰時會自行產生新密鑰

**位置：** `src/reponpc/admin/model_connections.py:182`～`:205`。

解密和加密共用 `_read_or_create_key()`。主密鑰遺失後，讀取舊密文會先產生一把新 key，再因解密失敗回傳安全錯誤。

**影響：** 雖然沒有洩漏明文、也未在此重現中覆寫舊密文，系統已把錯誤的新 key 安裝到正式位置；後續儲存可能形成由不同 key 加密的資料，破壞預期的復原流程。符合 handoff 明確禁止的情境。

**獨立重現：** 在暫存 fixture 中加密 → 刪除該 fixture key → 解密；得到 `MODEL_SECRET_STORAGE_UNAVAILABLE`，同時 `missing_key_silently_recreated: true`。

**修正方向：** 將首次受信任初始化與既有 store 解密分開；有既存密文而缺 key 時只報錯，不能自動建立替代 key。補遺失、還原、tamper、rotation 中斷及 Windows/Linux 權限測試。現有 `_restrict_file()` 僅處理 POSIX mode，Windows 保護亦需實際 ACL／OS store 證據，不能以本機測試通過代替。

**對應：** FR-039、AC-055；model-setup handoff §6、SECURITY 21。

### R4 · P1：Chat runtime 切換失敗後，DB 仍記錄新模型為 active

**位置：** `src/reponpc/admin/chat_profiles.py:245`～`:254`。

`activate()` 先 commit active profile，再執行 `_on_activated()`。callback 失敗只丟出 `CHAT_RUNTIME_SWITCH_FAILED`，沒有恢復資料庫中的舊 active profile。

**影響：** API 回失敗，但 active metadata 已改為候選模型，與仍運作的舊 runtime 不一致；重啟亦可能採用錯誤的 active 紀錄。這違反原子切換與 last-known-good 保留。

**獨立重現：** 先啟用 `old-model`，再讓 `new-model` 的切換 callback 合成失敗；回錯誤後 `profiles.active().model_id` 仍為 `new-model`。

**修正方向：** 以可回復的 runtime transition／durable activation intent 協調 DB 與 runtime，涵蓋 callback、DB failure、競爭與 crash recovery；不只把 callback 調到 commit 前而忽略反方向失敗。分析 selection 應繼續與公開 active 分離。

**對應：** FR-039、AC-056；Technical Specification 11.5/11.6。

### R5 · P2：手動路線返回 repository 後仍鎖住選擇

**位置：** `apps/web/src/features/admin/guidedOnboarding.ts:442`；表單鎖定見 `GuidedOnboardingView.tsx:783`、`:1422`。

手動路線的 `CONFIRM_SELECTION` 會設 `selectionConfirmed=true`；從 contributions 執行 `GO_BACK` 回 repositories 時沒有解除。repository 表單依此停用，而 reducer 拒絕修改。

**獨立重現：** `START_MANUAL → ADD_REPOSITORY → CONFIRM_SELECTION → GO_BACK → TOGGLE_REPOSITORY`；仍在 repositories，但結果為 `ONBOARDING_SELECTION_ALREADY_CONFIRMED`。

**修正方向：** 回到可編輯的選擇狀態，保留 profile、未受影響的 contribution／結果；只有實際 identity 變更才失效相關分析資料。補手動路線前進、返回、修改與匯出的互動測試。

**對應：** FR-040/041、AC-057/058/060。

### R6 · P2：preflight 失敗後缺少可用的重試入口

**位置：** `apps/web/src/features/admin/AdminPage.tsx:1923`、`:2374`、`:2389`；`GuidedOnboardingView.tsx:1637`；`BatchAnalysisPanel.tsx:478`。

首次 Start 的 preflight 若拋錯，狀態變為 `failed` 且 `batchPlan` 仍為 null。此時畫面切入 batch panel，但 `batchCanCreate` 要求已有 ready plan，故 Start 被停用。panel 的 retry control 只存在於已建立 job；失敗的 preflight 本身沒有 retry callback。blocked plan 亦沒有直接重新 preflight 的動作。

**影響：** 短暫 GitHub／網路錯誤解除後，使用者仍需繞回編輯選擇或重載等方式才有機會重新開始；頁面顯示「請重新檢查」卻不能直接操作。

**證據等級：** 已追蹤完整 state/props/render 分支；本次沒有在已登入瀏覽器實際注入 preflight failure，勿記為 browser pass。

**修正方向：** 同一個 Start/Retry 意圖在沒有 active batch 時能重新執行 preflight；loading、blocked、failed 各有具體下一步，並遵守 retry-after。重試前 reconcile active job；不能靠自動 retry、清空草稿或重複 generation 解決。

**對應：** FR-041/042、AC-058/060、既有 AC-045。

## 3. 兩份 handoff 的落實情形

此表為證據狀態，非完成百分比，也不是 release approval。

| 工作面 | 已看到的實作 | 尚未收斂的部分 | 判定 |
| --- | --- | --- | --- |
| M0／H0 契約 | Spec 11.6 已明列 analysis-selection endpoint、body、generation、safe view；runtime 有獨立 selection/pair | 連線與 secret revision 的完整限制／清理／復原契約、舊瀏覽器 state recovery 證據仍需補齊 | 部分落實 |
| M1 連線基礎 | Fernet、safe metadata、connection revision、write-only create/update、auth/CSRF 測試 | R1/R3；Windows key 保護與故障／還原證據 | 尚不可驗收 |
| M2 角色生命週期 | 獨立 Chat/Embedding profile、probe、public activation、analysis selection | R4；各 provider 真正能力／錯誤矩陣、兩個不同 endpoints/keys、in-flight/restart 覆蓋不足 | 部分落實 |
| M3／H1 無模型啟動 | provider-neutral loader/launcher；analysis runtime supplier 可在選模型後組裝；analysis 與 public 狀態分離 | clean production wiring 的 configure/test/select/analyze 全程證據；R2；首次 public candidate 的組裝問題見下文 | 未證明端到端完成 |
| H2 固定批次模型 | pair snapshot、selection generation、cache identity、frozen resolver 已接入 | R2；完整 stale/rotation/cache/restart/race 情境 | 部分落實 |
| M4／H3 引導介面 | welcome、models step、AI/manual route、角色確認面板、Start 串接 preflight/create | R5/R6；contextual return、舊 state migration、primary model form 尚有缺口 | 部分落實 |
| M5／H4 驗收交接 | release auditor／ledger validator 已要求 AC-001～060；相關測試通過 | 新 AC 的 dated 整合、live、browser/accessibility 證據未齊 | 未完成 |

另有三項需要在整合驗收中明確收斂：

1. **首次 public candidate 組裝仍有循環依賴的程式證據。** `main.py:856` 的 `_configure_embedding_reindex()` 在 `provider_runtime is None` 時直接返回；`:1041` 的 `_replace_runtime_chat()` 只替換既有 runtime。這不能當作無模型啟動後已可準備首個公開候選的證明。需走真實啟動 wiring，檢查之後是否能建立 coordinator/runtime；不能注入預先存在的 runtime 來通過測試，也不能因此擅改發布拓撲。
2. **Contextual return 與 readiness 恢復未完成。** `guidedOnboarding.ts` 尚無 return destination；`COMPLETE_MODEL_SETUP` 固定到 repositories。`:601`／`:686` 仍持久化並讀回 `modelsConfigured`；伺服器會另行刷新，但 browser boolean 不能成為可信完成狀態。需覆蓋所有舊 step、manual 轉 AI、取消、回到原稿與失效模型修復。這不是已證實的 backend 授權繞過。
3. **技術面板直接嵌入 models step。** `AdminPage.tsx:2396` 目前將 `AnalysisSelectionPanel` 與既有 `modelPanels` 串列呈現，尚未形成附圖的工作區層次。不能用 source 中已有模型 component 推論 UI 已符合 AC-057。

舊 handoff 中「未開始」與「auditor 只到 AC-052」是歷史 inventory；目前程式已前進，不應照抄為現況。同樣地，auditor 已涵蓋新 ID 也不等於新 AC 已通過。

## 4. 本次執行結果

| 檢查 | 結果 | 限制 |
| --- | --- | --- |
| 範圍內 Python tests，16 個測試檔 | **127 passed、2 skipped、1 warning** | 兩個 skip 是 Windows 不提供 POSIX mode/no-follow 語意；warning 是 Starlette/httpx 棄用提示 |
| 範圍內 Vitest，8 個測試檔 | **58 passed** | 主要為 reducer/render 測試，不是完整瀏覽器行為證據 |
| 獨立 domain/storage/transport/reducer 重現 | **R1～R5 皆重現** | 合成資料與受阻斷 transport；不代表 live provider 測試 |
| Ruff lint／format：`src tests tools` | **通過** | format 153 files；未使用 auto-fix |
| `mypy src` | **通過** | 66 source files |
| Web Prettier／ESLint／TypeScript | **通過** | 檢查 apps/web |
| Vite production build | **通過** | 輸出到 `.tmp`，未替換正在服務的 dist；有外部 outDir 不清空的提示 |
| `tests/contract/test_phase2_closure_spec.py` | **5 passed** | 文件完成後另跑；不計入前述 127 |
| 本機瀏覽器 `http://localhost:8090/admin` | **只確認本機啟動器授權提示** | 未取得 launcher session，未重啟、修改 runtime 或越過登入；完整流程未跑 |
| `git diff --check` | **通過** | 既有 working tree 有 LF/CRLF 提示；另檢查新增文件的連結與空白 |
| 新增兩份文件檢查 | **通過** | 無失效本機 Markdown 連結或行尾空白 |

測試命令與本機輸出：

```powershell
uv --cache-dir .tmp/uv-cache run --no-sync pytest tests/unit/test_model_connections.py tests/unit/test_chat_profiles.py tests/unit/test_analysis_selection.py tests/unit/test_batch_execution.py tests/unit/test_batches.py tests/unit/test_batch_runtime.py tests/integration/test_model_connections_api.py tests/integration/test_provider_lifecycle.py tests/integration/test_embedding_profiles.py tests/integration/test_embedding_reindex.py tests/integration/test_analysis_batch_api.py tests/integration/test_runtime_database.py tests/contract/test_environment.py tests/contract/test_local_launcher.py tests/security/test_admin_onboarding_security.py tests/unit/test_release_audit.py -q -p no:cacheprovider --basetemp .tmp/review-model-ui-20260910/pytest --junitxml .tmp/review-model-ui-20260910/backend.xml
pnpm --dir apps/web exec vitest run src/features/admin/AdminPage.test.tsx src/features/admin/AdminWorkspace.test.tsx src/features/admin/GuidedOnboardingView.test.tsx src/features/admin/guidedOnboarding.test.ts src/features/admin/ModelConnectionPanel.test.tsx src/features/admin/ChatProfilePanel.test.tsx src/features/admin/EmbeddingProfilePanel.test.tsx src/features/admin/BatchAnalysisPanel.test.tsx --reporter=default --reporter=json --outputFile.json=../../.tmp/review-model-ui-20260910/frontend.json
uv --cache-dir .tmp/uv-cache run --no-sync python .tmp/review-model-ui-20260910/reproduce.py
node .tmp/review-model-ui-20260910/reproduce-reducer.mjs
uv --cache-dir .tmp/uv-cache run --no-sync ruff check src tests tools
uv --cache-dir .tmp/uv-cache run --no-sync ruff format --check src tests tools
uv --cache-dir .tmp/uv-cache run --no-sync mypy src
pnpm --dir apps/web run format
pnpm --dir apps/web run lint
pnpm --dir apps/web run typecheck
pnpm --dir apps/web exec vite build --outDir D:/RepoNPC/.tmp/review-model-ui-20260910/web-build
uv --cache-dir .tmp/uv-cache run --no-sync pytest tests/contract/test_phase2_closure_spec.py -q -p no:cacheprovider --basetemp .tmp/review-model-ui-20260910/doc-pytest
git diff --check
```

現有測試綠燈不抵銷獨立重現的失敗行為。重現腳本與 JSON 位於忽略的 `.tmp`，供本機交接使用；跨 clone 應依各 finding 的步驟補入正式回歸測試。

本次沒有重跑全庫 pytest/Vitest、Docker/Compose/clean-host、retrieval evaluation、live Ollama/gateway/vLLM、完整 browser/keyboard/讀屏、多 viewport/zoom、production 備份還原演練。不得把未執行項目記為 pass。

## 5. 建議交回實作者的順序

1. 修 R1/R3 安全與 secret recovery，及 R2 批次主要流程；加入會捕捉上述失敗的正式測試。
2. 修 R4 原子啟用，完成無 public runtime 的首次組裝與 A-public/B-analysis 隔離整合測試。
3. 修 R5/R6、contextual return、server-owned readiness 與舊 state migration；保留單一明確 Start 意圖和 manual/export。
4. 依 UI 計劃逐步重整管理工作區，避免整包重寫 AdminPage 或重造 batch engine。
5. 補真實 application wiring、可重現 browser、live-provider／部署證據後，逐條更新 AC-053～060 ledger；review 不能代替 acceptance。

本次不需要新的擁有者決策才能交付審核與 UI 提案。已批准的 0.2.3 缺陷修正不應再次詢問方向；若實作另外涉及新增 runtime、改發布拓撲、放寬保密或增減 v1 範圍，才應另列具體決策。本報告不代表已修復或已批准 UI 實作。

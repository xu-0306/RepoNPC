# RepoNPC 修復進度（更新：2026-09-19）

## 目前總覽

本文件追蹤擁有者提供的《RepoNPC 修復與體驗完善計畫》（2026-09-16）。R09 核心與部分 R14 已整合至 `main`；R01–R07 的目前限定批次已在修復分支完成實作、完整自動化驗證及 production-stack 瀏覽器驗收；R10 的人物歸因誤判修正亦已完成並通過獨立複核；R14 卡片長文字／靜態版面子批次已完成本機實作、完整回歸與獨立複核。**整份修復計畫尚未完成。**

- 已發布基準：`c643affcead613db19f2f388fffe95341e541fdb`，包含 R09 核心與部分 R14。
- 目前分支：`codex/r01-r04-r07-analysis-recovery`，HEAD 仍為 `c643aff`；R01–R07 目前限定批次的變更尚未 commit、push、合併或部署。
- R01–R04／R07 已由 ChatGPT 透過 RepoNPC connector 獨立複核，C2C 任務 `c2c_9a3d` 在 iteration 10 回傳 `STATE: DONE`、`CODE_REVIEW_RESULT: REVIEW_ACCEPTED`、`BROWSER_ACCEPTANCE: ACCEPTED`。
- R05–R06 限定修正批次已由 ChatGPT 透過同一 connector 獨立複核，C2C 任務 `c2c_b47e` 在 iteration 2 回傳 `STATE: DONE`、`CODE_REVIEW_RESULT: REVIEW_ACCEPTED`、`BROWSER_ACCEPTANCE: ACCEPTED`；B1–B6 均接受，未發現新的 blocking finding。
- 未呼叫真實 GitHub/provider、未使用正式資料或付費服務；Docker smoke 已通過。
- 不得 stage 使用者所有的未追蹤 `%SystemDrive%/` 與 `RepoNPC_R09_R14_REPAIR_2026-09-17/`。

| 項目 | 目前狀態 |
| --- | --- |
| R01–R04 | 完成實作、自動化測試與 production-stack 瀏覽器驗收 |
| R05–R06 | 限定修正批次已完成實作、完整 regression、production-stack 驗收與獨立複核 |
| R07 | 完成 `excerpt` 契約、邊界驗證、UI 與瀏覽器驗收 |
| R08、R13 | R08 尚未完成；R13 的物種中立 64px 契約、PNG／一般 ZIP／資料夾探索轉換與管理員預覽／下載／寫入流程已完成，final art review 與發布仍未完成 |
| R09 | 核心歷史裁切、成功問答隔離及真實 React／完整 API 瀏覽器驗收完成；獨立複核已接受 |
| R10 | 人物主體與受保護敘述的保守關聯檢查已完成實作、完整 regression、兩個 fresh runtime 瀏覽器驗收與獨立複核 |
| R11 | 尚未完成；近期可操作終止批次的 reload recovery 需要擁有者決定 server discovery 契約 |
| R12 | R12-A 已完成 validated-result cache 的完整性、重啟重用、identity/privacy 與工作量封口；真正可重開 derived index 的 R12-B 仍需擁有者決定受保護儲存設計與容量政策 |
| R14 | 已實作的訪客聊天／NPC 狀態／傳輸／減少動態部分已通過正式瀏覽器驗收與獨立複核；卡片長文字／靜態版面子批次已完成完整回歸與獨立複核；角色設定引導、發布流程及 AC-022 手動 GitHub proxy 驗證仍待完成 |

## 已整合基準：R09 與部分 R14

### R09：模型歷史與畫面對話分離

畫面保留原本的長回答、失敗訊息與重試入口。模型歷史只在收到完整、成功的 SSE 回覆後，才記錄一組 question／answer；失敗、取消及缺少 `complete` 的傳輸不會留下孤立的 user 訊息。

依同一版本 `src/reponpc/api/public.py` 的 `PublicChatRequest`／`PublicChatHistory`，模型歷史保留最近且連續的完整問答組，最多 10 則訊息、每則 4,000 Unicode code points、合計 12,000 code points。**不截斷或自行摘要單則內容**；碰到超長問答就從該處切斷上下文。最新回答過長時，下一次模型歷史為空，但畫面上的完整回答不會刪除。這是明確的保守取捨，不代表模型仍保有整段畫面對話。

新增同步請求鎖，防止 React 尚未更新畫面前連點造成重複請求；卸載時取消仍在進行的請求。只有成功回覆會進入後續模型上下文。

### R14：部分 NPC 狀態與傳輸清理

- 收到實際文字事件才切換「說話」，不在收到 HTTP response 時就切換。
- 成功後短暫展示，再回到待機；新的輸入或請求會清除舊計時器。
- 一般請求失敗不直接推論整個模型服務離線，而是重新讀取公開服務狀態。
- 解析失敗時取消未完成的 SSE reader，正常或失敗結束都釋放 reader lock。
- 這仍是後端驗證後的分段傳輸，不是模型原生 token streaming。

卡片長文字、格式差異、角色設定引導、完整取消操作及無障礙／動畫瀏覽器驗證不在本次完成範圍。

## R09／部分 R14 的歷史驗證

早期隔離驗證環境為 Linux、Node.js `22.16.0`、TypeScript `5.8.3`。整合至完整工作副本後，另完成正式 Web 與 API regression。全程未使用付費模型、正式資料或外部發布服務。

| 檢查 | 結果與限制 |
| --- | --- |
| 基準歷史處理邏輯隔離測試 | 2 個預期失敗：第六組成功對話超量；失敗 assistant 留下孤立 user。執行的是 SHA 已核對的 `App.tsx` 內原始歷史運算式，不是啟動整個應用程式。 |
| 修復後共用測試案例 | 23 passed，0 failed，透過 Node 內建 test runner 執行。含 200 組確定性混合長度案例、Unicode、失敗重試、取消、缺少完成事件、JSON 損毀、讀取鎖與逐 byte 分段。 |
| React-free 核心 TypeScript strict 編譯 | 通過；只包含 `sse.ts`、`visitorChat.ts` 與共用測試案例。 |
| `App.tsx` 隔離 TSX 轉譯 | 0 syntax diagnostics；**不是**全專案 typecheck、Vite build 或 React 行為測試。 |
| Targeted Vitest | `visitorChat` 共用案例 23/23 passed。 |
| 完整 Web 檢查 | `pnpm run web:check` 通過 formatting、typecheck 與 production build；166 個 frontend tests passed；ESLint 0 error、12 個既有 Fast Refresh warnings。 |
| API regression | `tests/integration/test_chat_sse_api.py` 11/11 passed，另有一個 Starlette/httpx deprecation warning。 |
| 瀏覽器／Docker／真實 provider | R09 的真實 React／完整 API 瀏覽器驗收仍待完成；Docker 與真實 provider 未執行。 |

可用下列命令重跑同一組隔離案例：

```bash
node tools/test_visitor_chat_contract.cjs
```

完整工作副本的對應回歸命令如下；上列結果已執行，後續變更仍須重跑相關子集：

```bash
pnpm --dir apps/web exec vitest run src/app/visitorChat.test.ts
pnpm run web:check
uv run pytest -q --ignore=tests/smoke/test_container.py
```

另需瀏覽器確認：多輪聊天、長回答、失敗後重試、快速連點、導覽卸載、開始／成功／輸入交錯時的 NPC 狀態，以及中英文與減少動態效果設定。

## 2026-09-19 後續修復：R10 人物歸因誤判

R10 將分析模型輸出的裸關鍵字封鎖改為可稽核的雙語人物主體／受保護敘述關聯檢查。`模組負責轉換音訊`、`設定影響記憶體使用`、英文非人物 technical subject 與責任／影響分析等技術用語不再被誤判；`我負責轉換音訊`、`本人完成全部功能`、`作者主導架構`、`I led this project`、作者責任／成就／影響及被動人物歸因仍會 fail closed。

本批沒有增加模型呼叫、分類器、依賴、schema、migration、API、環境變數或新的錯誤代碼。`PROVIDER_PERSONAL_INFERENCE_REJECTED`、證據 ID 驗證、`MODEL_INFERENCE` 分類及 owner assertion 邊界保持不變。允許／拒絕矩陣直接覆蓋 `_parse_analysis()`，另以正式 `GuidedOnboardingService` 路徑證明合法技術敘述與拒絕人物歸因都只產生一次 provider call，不會暗中 retry 或 fallback。

驗證結果：R10 焦點測試 `65 passed`；Python `1007 passed, 2 skipped`；Web 24 files、`188 passed`；Ruff format/lint、mypy 69 source files、Prettier、TypeScript、production build、Docker smoke 與 `git diff --check` 均通過。Production-stack analysis recovery 的 running／completed 兩個隔離 fresh runtime 各通過 `37/37`；測試腳本另等待語系切換後受控貢獻輸入完成重新掛載，以消除舊驗收流程的時序不穩定。全程未使用 live provider、GitHub credential、正式資料、付費服務或外部網路。

C2C 任務 `c2c_8943` iteration 2 回傳 `STATE: DONE`、`CODE_REVIEW_RESULT: REVIEW_ACCEPTED`、`R10_ACCEPTANCE: ACCEPTED`。獨立複核確認角色／僱傭關係缺口已補齊、技術用語正例仍不會被裸關鍵字阻擋、service path 維持單次 provider call，且沒有新增 reason、schema、API、migration、環境變數、分類器或 fallback。

## 2026-09-19 後續修復：R14 卡片長文字／靜態版面子批次

公開卡片渲染現在以 repository 內附的 Noto Sans CJK TC 字型，分別量測顯示名稱、標語、行動按鈕與 repository count 的固定文字區域。超出區域時依 Unicode code point 確定性截短並加上可見刪節號；同一次計算結果共用於 PNG、每個 GIF frame 與 SVG。SVG 另記錄量測後的 `textLength`／`lengthAdjust`，使瀏覽器缺少同一字型而使用 fallback 時，仍不會重新超出既定區域。短文字維持原樣，完整且已清理的名稱／標語仍保留於 SVG 的 `<title>`／`<desc>`，可見文字則安全逸出並使用同一截短結果。

單元與整合案例覆蓋超長繁體中文、英文、無空格 URL、混合 CJK／Latin、長 CTA、長 repository count、惡意 markup、重複渲染確定性，以及 `zh-TW`／`en`、light／dark 的 SVG/GIF/PNG 全組資產。焦點 public-route／安全回歸為 `31 passed`，包含 `600x180`、格式、ETag、內容類型、SVG CSP 及安全標頭；完整 Python（排除獨立 Docker smoke）為 `1017 passed, 2 skipped`，僅保留既有 Starlette/httpx deprecation warning；Docker smoke `1 passed`。Web check 的 24 個 files、`188 passed`、Prettier、TypeScript 與 production build 均通過，ESLint 為 0 errors、16 個既有 Fast Refresh warnings。Ruff format/lint、69 個 Python source files 的 mypy 與 `git diff --check` 均通過。未呼叫 live provider、GitHub credential、正式資料、付費服務或外部網路。

本批的版面不變量皆由 server-side renderer 與真實 public API 路徑確定性驗證，因此沒有另造瀏覽器截圖當作功能證據，也不宣稱完成 AC-022。GitHub image proxy、目前 Chrome／Firefox／Safari、動畫停用與實際 README 點擊行為仍是 release 前手動驗證；R08 受保護預覽／CSP、R11 恢復語意、R12-B 真正可重用索引、R13 角色設定／發布流程及 R14 其餘角色體驗仍維持後續批次。

C2C 任務 `c2c_f428` iteration 1 回傳 `STATE: DONE`、`CODE_REVIEW_RESULT: REVIEW_ACCEPTED`、`R14_CARD_LAYOUT_ACCEPTANCE: ACCEPTED`。獨立複核確認四個文字區域的量測邊界、CTA／repository count 間隔、跨格式共用 fitted copy、SVG fallback-font 寬度限制、惡意文字安全邊界與全套驗證結果，沒有 blocking finding。

## 2026-09-19 後續修復：R12-A 快取完整性、真實重用與量測

R12-A 封住目前已受支援的 `validated_analysis` 快取邊界，但不把 `derived_index` marker 冒充成可重開索引。`analysis_cache_entries.payload_sha256` 的實體欄位維持不變，內容改為綁定 cache key、kind、derived key、canonical metadata 與 canonical payload 的完整 logical-entry digest；舊 payload-only checksum、metadata／payload／derived-key 竄改、畸形 JSON 或非法 logical fields 都會刪除該列並視為 cache miss。這是可重建的 ephemeral derived state，因此沒有為舊 hit 增加 migration。

Runner 只接受 kind、derived linkage、完整 generation metadata、repository immutable identity 與 bounded normalized result 全部一致的 validated-result hit。持久化 payload 僅允許 repository identity、最多六項 `MODEL_INFERENCE`、雙語 bounded statement、1–8 個合法 evidence IDs，以及 bounded skipped summary；`facts`、repository excerpt、archive body、prompt/context、provider raw body、credential/private endpoint canary 均不會進入 durable cache。完整性通過但結構損毀的列會被刪除，接著走正常 immutable source/index/generation path，不會把可執行批次永久判為失敗。

確定性案例記錄下列工作量，不以 CI wall-clock 冒充效能 benchmark：

| 情境 | archive/source work | index/analysis/generation work |
| --- | ---: | ---: |
| cold | 1 | 1 |
| compatible validated-result warm（含重建 store/process-equivalent） | 0 | 0 |
| generation failure 後同 identity 再執行，即使已有 derived marker | 1 each run | 1 each run |

Identity matrix 明確覆蓋 immutable commit、include/exclude policy、parser、embedding、chat model、prompt、output schema、validation、analysis-output policy、output budget、token estimator、termination validation 與 effective provider capability；任何相關改變都不會沿用不相容 validated result。TTL cleanup 與 valid-hit `last_accessed_at` refresh 保持有效，沒有自行發明未經核准的 row／byte LRU ceiling。

驗證結果：R12-A 焦點測試 `53 passed`；完整 Python（排除獨立 Docker smoke）`1023 passed, 2 skipped`，僅保留既有 Starlette/httpx deprecation warning；Web 24 files、`188 passed`、production build 通過；Docker smoke `1 passed`；Ruff、mypy、Prettier、TypeScript 與 `git diff --check` 均通過。Production-stack analysis recovery 的 running／completed 兩個全新 runtime 各通過 `37/37`，running 的延遲舊快照狀態序列維持單一 `running`；安全 observations 與更新後 manifest 記錄於 `tests/browser/analysis-recovery-evidence.json`。全程未使用 live GitHub/provider、credential、正式資料、付費服務或外部網路。

完整 R12 仍未完成。真正能在 generation failure 或 restart 後省略 source/index work 的 artifact 是 staging `index.sqlite`，其中包含 repository-derived evidence content 與 embeddings；把它 base64 或直接塞入目前 metadata／validated-output-only 的 runtime cache 會違反既有 privacy/storage boundary。

### R12-B 需要的擁有者決定

建議優先選擇 **Option A：`REPONPC_DATA_DIR` 下的受保護 content-addressed file cache**。SQLite 只保存不含路徑的 server-generated identifier、hash、size 與 expiry；檔案採 atomic write、完整性驗證、嚴格權限、永不由 API/static route 暴露，並排除 backup/export。替代方案是定義允許持久化哪些 evidence text 的 sanitized derived-corpus 契約（privacy 變更更大），或明確選擇不提供 durable derived-index cache、只保留 validated-result cache。

無論選哪種真正 derived cache，擁有者仍需指定最大總 bytes／entries、是否保留 24 小時 TTL、是否允許跨 process restart，以及部署資料刪除與 backup/export 規則。R12-A 不猜測這些值，也沒有改 schema、migration、API、環境變數或安全邊界。

## 原計畫項目狀態

- [x] R09 核心歷史裁切與成功問答隔離：已實作並通過上述單元案例。
- [x] R09 真實 React／瀏覽器與完整 API 整合驗收：本機正式堆疊驗收與 C2C 獨立複核均已接受。
- [x] R01–R04：重試資格、受控新輪次、批次診斷、完成狀態、數量與 ETA；完整證據見下方 2026-09-17～18 後續修復章節。
- [x] R05–R06 限定修正批次：貢獻潤飾、固定獨立輸出預算、截斷／結構診斷、重新確認與過期回應隔離已完成完整 regression、production-stack 驗收與獨立複核。可設定的更大貢獻預算仍需擁有者另行決策。
- [x] R07：`excerpt` 契約、API 邊界驗證、UI 顯示與 production-stack 瀏覽器驗收。
- [ ] R08：受保護預覽與 CSP 契約。
- [ ] R13：物種中立版本化 pack schema、64px canonical、grid／manifest／一般 ZIP／資料夾探索 converter、第一級「角色與動畫」管理入口、七狀態播放預覽、下載／寫入與舊人形欄位移除已完成；技術細節採漸進揭露，final art review 及發布仍待完成。
- [x] R10：非人物技術主體不再被裸關鍵字誤判；明確雙語人物責任、角色、僱傭、成就與影響仍沿用既有安全理由拒絕。完整回歸、production-stack 瀏覽器驗收與獨立複核均已接受。
- [ ] R11：草稿／近期終止批次恢復的 server discovery 契約仍待擁有者決定。
- [ ] R12：R12-A validated-result cache 封口已完成；R12-B 真正 reusable derived-index persistence 仍待上述擁有者決定。
- [ ] R14：卡片長文字／靜態版面子批次已完成完整回歸與獨立複核；角色設定引導、發布流程、其餘角色體驗及 AC-022 手動驗證仍待完成。

「生成嘗試耗盡後建立新分析輪次」已由 R01–R04 修復並通過驗收；這不代表其餘修復項目或整體發布驗收完成。

## 套用與回復注意事項

已整合的 R09／部分 R14 沒有資料庫 migration。尚未提交的 R01–R04／R07 會新增 runtime migration 26 與 27，用於秘密安全的 lineage、失敗階段、來源使用標記及有界冪等收據；不得將舊的「沒有 migration」說明套用到這一批。評估、提交或回復時必須保留使用者未追蹤目錄與其他無關修改，不得重設或覆蓋整個工作樹。

## 2026-09-17～18 後續修復：R01–R04、R07

分支 `codex/r01-r04-r07-analysis-recovery` 已完成受控批次恢復實作。Migration 26 新增秘密安全的批次／項目 lineage、分析輪次與失敗階段，並清除 v25 已停止項目的殘留 active-clock 起點；migration 27 新增來源使用標記與有界冪等收據。同輪重試的快照與交易改用同一有效政策；每次生成 dispatch 先交易式保留額度，取消或租約失效會拒絕 dispatch。

`POST /api/admin/onboarding/analysis-batches/{batch_id}/reanalyze` 只接受終止來源中已耗盡的失敗項目，複製原 commit 與 include/exclude，預設沿用凍結模型。每個來源項目只能建立一個直接後繼；不同分頁／不同 idempotency key 不會建立重複工作。改用目前模型時，確認綁定 `expected_selection_generation`，陳舊確認回傳 409。

前端將 `completed_with_errors` 視為正常終止、分開顯示已處理／成功／失敗／待確認／取消，暫停、等待、超出估時或終止後不再顯示不可靠 ETA。後繼輪次保留成功兄弟結果，隔離舊批次延遲快照，合併 pending SSE refresh，並用同一冪等鍵處理未知寫入結果。R07 正式採用 `excerpt`，API 邊界會拒絕舊 `text` 或畸形 nested payload。

### 驗證證據

- Python：`970 passed, 2 skipped`（排除 Docker smoke）。
- Web：24 files、`183 passed`；Prettier、ESLint（僅 14 個既有 Fast Refresh warnings）、TypeScript、production build 通過。
- Ruff format/lint、mypy 69 source files、`git diff --check` 通過。
- FastAPI 路由整合驗收通過：三個假專案中只為失敗項目建立後繼；第二個不同鍵回傳同一後繼；來源 commit 與成功結果保持不變。使用暫存 runtime 與假 GitHub/provider，未連正式資料或付費服務。
- Docker smoke 未執行：本工作階段無 Docker API 權限。

第三輪複核另補上：快照分離歷史限制與目前恢復限制；冪等識別完整綁定模型選擇、確認與 selection generation，且已接受的建立請求不依賴記憶體中的 preflight；來源項目一旦有後繼就不能回到同輪重試；過期來源可依 24 小時 TTL 清除而不刪除仍有效的後繼；操作錯誤只呈現封閉代碼與符合安全格式的 request ID。FastAPI 整合案例使用三個假專案驗證兩個成功結果保持不變、只重做一個失敗項目，且同鍵或不同鍵的重複恢復請求都只取得同一後繼批次。

第四輪複核補上 migration 27：來源項目的 `successor_batch_id` 在子批次結果先到期後仍阻止重複重試／重分析；每個成功接受或去重到既有後繼的冪等鍵都會綁定完整請求雜湊，並隨後繼結果 TTL 清理。應用啟動會先執行逾期清理再做 lease recovery。前端同輪操作若遺失 HTTP 回應，會先 GET 原批次 ID；核對也失敗時顯示可操作的重新檢查按鈕。模型變更確認已改讀後端 `safe_dict()` 的巢狀 `chat.profile_id`／`embedding.profile_id`，前後端共用契約 fixture 驗證形狀。

第五輪複核再封住三個交錯邊界：結果仍待核對時，面板與事件 handler 都禁止依舊快照再次送出 retry／reanalyze，只保留原批次核對；重新分析的別名冪等鍵在一般 create 的預查與交易內建立都會衝突；逾期清理除了啟動恢復外，另有可停止的運行期 task，讀取已過期終止快照也會立即拒絕並清理。生命週期測試在不重啟、也不直接呼叫 store cleanup 的情況下驗證過期結果／事件被刪除且活動批次保留。

第六輪補上可重跑的 production-stack 瀏覽器驗收。`tests/browser/analysis_recovery_server.py` 提供正式 frontend build、FastAPI admin routes、批次規劃器、durable runtime database、worker、archive parser、index builder、結果驗證、冪等收據與證據 UI；只有 GitHub 與模型的外部傳輸以決定性 fixture 取代。`check-analysis-recovery.js` 從 AdminPage 完成模型選擇、三專案探索與批次建立，先驗證 2 成功／1 失敗；同輪 retry 的已接受回應及第一次精確 GET 核對都被 test-only service worker 捨棄，畫面鎖住變更、只允許手動核對，實際再次操作後伺服器仍只收到一個 POST。兩個全新 runtime 分別驗證 provider 仍執行時取得 running，以及 provider 已終止時手動核對直接取得 completed。Running 情境會保持一個由 AdminPage 發出的原始 GET 未完成，經正常暫停／繼續操作套用較新 generation 後才釋放原請求；從釋放前到補抓完成會記錄每次批次狀態 DOM 轉換，序列必須維持單一 `running`，因此短暫的 `running → paused → running` 也會失敗。Completed 情境不重播舊內容。第二次生成耗盡後，驗收先經 UI 確認貢獻，再模擬另一分頁更新模型選擇；取消確認不送請求，舊 generation 被拒且不建立後繼，新確認則以目前模型建立第二輪。重新分析的第一個成功回應也被捨棄，前端用同一冪等鍵重送；另一個等價鍵取得同一後繼且不增加 provider work。瀏覽器直接核對 lineage、來源 commit、收據雜湊、模型呼叫次數、`src/main.py:1-2`／`:4-5`、evidence ID、excerpt、失敗項目跨兩次正式 batch API 回應的終止計時／completed_at、批次區 ETA、連線狀態、貢獻保留與中英文鍵盤切換。最終兩個全新 runtime、不同 origin 各通過 31 項斷言；無敏感值的結果、瀏覽器版本、兩次正式 API 觀測及逐檔 SHA-256 manifest 記錄於 `tests/browser/analysis-recovery-evidence.json`。

ChatGPT 結案複核接受上述程式與瀏覽器證據。最後一項延遲舊回應觀測以 `MutationObserver` 記錄完整 `data-batch-status` 序列，實際為單一 `["running"]`，可攔截短暫的 `running → paused → running` 倒退。證據 manifest 共 36 檔，驗證指紋為 `3b2e27459666ecb75481b999c3a52693d19faec9a7369be059f975d4ec6f8f6f`。

### 範圍狀態

- [x] R01–R04 完整驗收：重試資格、受控新輪次、診斷、終止狀態、數量與 ETA 的程式、自動化測試及可重跑的 production AdminPage＋FastAPI 瀏覽器驗收均已完成。
- [x] R07 完整驗收：`excerpt` 契約、邊界驗證、UI 顯示及上述瀏覽器驗收均已完成。
- [x] R05–R06 限定修正批次：固定 700-token 貢獻建議預算、獨立 runtime 能力、完整 context admission、截斷／schema 診斷、確認版本恢復、延遲回應隔離、手動恢復與 confirmed-only YAML 邊界均已通過測試及 production-stack 瀏覽器驗收。可設定的更大貢獻預算仍是需要擁有者決策的後續契約變更，不在本批範圍。
- [x] R05–R06 獨立複核：C2C 任務 `c2c_b47e` iteration 2 接受 B1–B6、程式碼審查與瀏覽器驗收。最終證據為 schema 3、41 檔 manifest，指紋 `46059ce92b653b91b6cc46177f346e294030656ad1cfd7f8fee7020f30f8f32e`；Python `977 passed, 2 skipped`、Web `187 passed`、兩個 fresh runtime 瀏覽器流程各 `37/37`、Docker smoke `1 passed`，靜態檢查、型別檢查與 production build 均通過。
- [x] R09 正式瀏覽器驗收與獨立複核：production React＋FastAPI 公開 profile/status/chat routes 已在 fresh normal-motion runtime 通過 25 項、fresh reduced-motion runtime 在 1280px 與 375px 各通過 6 項。驗收發現並修正失敗後輸入框仍 disabled 時過早 focus 的時序缺陷；單元測試固定於 pending 清除後才聚焦。C2C 任務 `c2c_9590` iteration 1 回傳 `STATE: DONE`、`CODE_REVIEW_RESULT: REVIEW_ACCEPTED`、`BROWSER_ACCEPTANCE: ACCEPTED`。
- [x] R10 完成並接受：人物主體／受保護敘述關聯檢查、雙語允許／拒絕矩陣、正式 service-path 單次呼叫驗證與兩個 analysis-recovery fresh runtime 均通過；C2C 任務 `c2c_8943` iteration 2 已獨立複核接受。
- [x] R14 卡片長文字／靜態版面子批次：確定性字寬適配、跨 SVG/GIF/PNG 共用截短文字、雙語 light/dark 整合、public-route 安全回歸與 C2C 獨立複核均已完成。
- [x] R12-A 快取完整性／真實重用／量測子批次：logical-entry digest、結構 fail-closed rebuild、restart reuse、identity/privacy matrix 及 cold/warm/failure work count 已完成。
- [x] R13 角色契約子批次：Technical Specification 0.3.2 / ADR-039 將未部署的人形 public fields 直接替換為 `pack_id`、`pack_version` 與 pack-owned `options`；核心無 species enum／humanoid slots，非人形 fixture 不修改核心即可編譯，舊欄位與未知 pack/version/options 均 fail closed。
- [x] R13 64px／轉換子批次：Technical Specification 0.3.4 / ADR-040/041 將 canonical frame 直接改為 `64x64`／sheet `256x448`，以結構支援未見過的方格來源尺寸、strict 28-frame manifest ZIP、一般 ZIP 與瀏覽器資料夾選擇；提供 deterministic pixel-exact／pixelize、多候選視覺選擇、品質警告及 conversion/write 分離，不保留 32px 相容層。
- [ ] R08、R11、R12-B、R13 與剩餘 R14：維持後續批次；包含受保護自訂預覽、reload recovery、真正 reusable derived-index storage、角色設定／發布流程及 AC-022 release 手動驗證。
- [ ] Git 交付：R01–R04／R07 仍在未提交工作樹；尚未 commit、push、合併或部署。

## 2026-09-22 角色上傳預覽破圖修正

管理頁原本將 API 回傳的 PNG base64 放進 `data:image/png` 圖片網址，但正式頁面的 CSP 保持 `img-src 'self'`，因此候選圖、轉換後動畫／完整圖，以及進階管理頁的角色／卡片預覽會被瀏覽器阻擋。這次將預覽改為從 PNG bytes 解碼後直接繪於 canvas；沒有放寬 CSP、沒有新增對外圖片 URL，也沒有改動轉換／下載／GitHub 寫入契約。解碼失敗時顯示雙語錯誤，動畫仍依七個狀態、四格及系統減少動態設定運作。

已用正式 build 與本機管理頁將 `PixelNPC/Orange` 的 10 個檔案實際選取並轉換：四張候選縮圖、選定後動畫與完整圖均可見；瀏覽器錯誤記錄為空。Web 192 項測試、TypeScript、ESLint（只有既有 Fast Refresh 警告）及 build 通過。這是 R13 管理預覽的局部修復，不代表 R08 的受保護預覽／CSP 契約或 R13 的最終美術檢查與發布已結案。

## 2026-09-22 影格位置跳動修正

in-app browser 實際查看 Orange 後確認畫布位置固定，但待機四格轉換圖的左邊界依序為 17、12、10、6 像素；3 倍預覽放大了素材本身的水平位移。ADR-043 / OR-024 採用可逆、選擇性的位置校正：依每格 alpha 佔用分布提出左右對齊建議，允許不裁切的逐格 X/Y 微調；原檔、原始轉換結果與未套用的下載／寫入均不變。只有按下套用且既有受保護驗證端點回傳 canonical PNG 後，修正版才可下載或寫入。游離像素與創作者刻意設計的動作仍需人工檢查。

實測以 `PixelNPC/Orange` 資料夾上傳，從四張候選圖選第一張，預覽建議對齊、選擇待機第 2 格，確認邊界微調按鈕會停用；未套用時下載停用，套用後既有驗證端點成功，下載重新啟用。英文切換亦確認有對應控制文字；狀態／錯誤訊息改為依當前語言即時呈現。Web 196 項測試、TypeScript、格式、ESLint（0 錯誤／16 個既有 Fast Refresh 警告）、build，以及相關 Python 24 項測試均通過。視覺建議不保證辨別刻意的動作位移或修復原圖游離像素，因此仍需創作者預覽確認。

## 2026-09-22 素材格線殘影清理

Orange 第一張 4×7 原圖的移動列四格，在來源格頂都有從上一列底邊延續的半透明棕色短線，與本格角色之間有透明間隔。ADR-044 / OR-025 在原格裁切後、縮圖之前以來源尺寸相對的淺帶、相鄰列像素連續性與透明間隔提出清理版，保留原版；兩版各自通過既有 canonical 驗證，前端同格比較並要求使用者選版，後續位置校正以選定版本為底圖。其他來源尺寸、無相鄰支援的獨立特效、連到本格主體的像素、manifest 與空影格均不得因 Orange 例子被誤刪。

實測 Orange 資料夾的第一張候選圖：移動列四格都有建議，來源格頂共移除 999 個像素；轉換後原版四格頂端仍各有 15–17 個非透明像素，清理版均為 0。in-app browser 呈現同格原版／清理版比較，選版前下載停用，選任一版後啟用；清理版再做位置校正時，套用前下載再次停用，既有驗證成功後恢復。英文切換、375px 無水平溢出、瀏覽器錯誤記錄為空。Python 全套件排除無權連線的 Docker smoke 後為 1054 通過、2 跳過；Docker daemon pipe 權限不足，容器 smoke 未驗證。Web 與靜態檢查另行記錄於本次交付回報。

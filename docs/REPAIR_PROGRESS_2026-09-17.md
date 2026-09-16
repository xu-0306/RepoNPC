# RepoNPC 修復進度：訪客聊天歷史與狀態生命週期

## 範圍與狀態

本次依據擁有者提供的《RepoNPC 修復與體驗完善計畫》（2026-09-16），先交付 R09 與 R14 的部分程式修復。**不是第一批全部完成，也不是整份計畫完成；目前只適合以 Draft PR 審查。**

- 基準 commit：`94d881a4d1dda2e1362722a8b10f9cd26584bd69`。
- 獨立分支：`fix/recovery-and-portfolio-20260916`；本輪建立成功，先前文件記錄的 403 不再代表本輪寫入結果。
- 未直接修改 `main`，未合併、部署或呼叫真實模型。
- 工作環境不能解析 `github.com`，完整 clone／依賴安裝及專案基線未完成。透過 GitHub connector 讀取必要檔案；`App.tsx` 的完整本地基準以 Git blob SHA 驗證，與 `6ece2c744ef94f42055f669c5dc02b2b41a11582` 一致。沒有把零散片段宣稱為完整 checkout。

## 已實作

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

## 實際測試

環境：Linux；Node.js `22.16.0`；TypeScript `5.8.3`（與 apps/web/package.json 宣告的版本一致）。未使用付費模型、正式資料或外部發布服務。

| 檢查 | 結果與限制 |
| --- | --- |
| 基準歷史處理邏輯隔離測試 | 2 個預期失敗：第六組成功對話超量；失敗 assistant 留下孤立 user。執行的是 SHA 已核對的 `App.tsx` 內原始歷史運算式，不是啟動整個應用程式。 |
| 修復後共用測試案例 | 23 passed，0 failed，透過 Node 內建 test runner 執行。含 200 組確定性混合長度案例、Unicode、失敗重試、取消、缺少完成事件、JSON 損毀、讀取鎖與逐 byte 分段。 |
| React-free 核心 TypeScript strict 編譯 | 通過；只包含 `sse.ts`、`visitorChat.ts` 與共用測試案例。 |
| `App.tsx` 隔離 TSX 轉譯 | 0 syntax diagnostics；**不是**全專案 typecheck、Vite build 或 React 行為測試。 |
| Vitest | 已新增共用案例入口，但未實際啟動 Vitest。不可把 Node runner 的結果寫成 Vitest 通過。 |
| 完整檢查／瀏覽器／Docker／Windows／真實 provider | 尚未執行。 |

安裝原專案鎖定的 Web 依賴後，可執行同一組隔離案例：

```bash
node tools/test_visitor_chat_contract.cjs
```

完整工作副本上仍須執行以下檢查，不能由上述 23 個單元案例取代：

```bash
pnpm --dir apps/web exec vitest run src/app/visitorChat.test.ts
pnpm run web:check
uv run pytest -q --ignore=tests/smoke/test_container.py
```

另需瀏覽器確認：多輪聊天、長回答、失敗後重試、快速連點、導覽卸載、開始／成功／輸入交錯時的 NPC 狀態，以及中英文與減少動態效果設定。

## 尚未完成的原計畫項目

- [x] R09 核心歷史裁切與成功問答隔離：已實作並通過上述單元案例。
- [ ] R09 真實 React／瀏覽器與完整 API 整合驗收。
- [ ] R01–R04：重試資格、受控新輪次、批次診斷、完成狀態、數量與 ETA。
- [ ] R05–R06：貢獻潤飾、獨立輸出預算與截斷診斷。
- [ ] R07：`excerpt`／`text` 契約與 UI 顯示。
- [ ] R08、R13：受保護預覽與角色／卡片引導。
- [ ] R10–R12：歸因誤判、草稿／批次恢復與可重用索引快取。
- [ ] R14：剩餘角色／卡片體驗與瀏覽器驗收。

尤其「生成嘗試耗盡後建立新分析輪次」尚未修好。不可把這個 PR 宣稱為批次失敗恢復方案。

## 套用與回復

這次沒有資料庫 schema 或 migration 變更，不需要清空 runtime 資料、刪除索引或重設模型。先保留使用者尚未提交的修改，再檢出修復分支進行評估；不要直接覆蓋本機整個目錄。回復時只回復本次來源／測試／文件變更，保留使用者資料不動。

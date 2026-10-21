# 服務更新提示與 CC Switch 連通檢查對照

## 已完成的介面修改

- `apps/web/src/features/admin/AdminPage.tsx`：只有服務新增/更新寫入成功後才發出成功提示。每次成功有獨立事件 ID；再次提交或刪除會清除舊提示。清單刷新失敗仍維持獨立提示，不把已完成寫入說成失敗。
- `TransientNotice.tsx`、`styles.css`：使用既有成功色彩，提示固定於視窗頂部、無阻擋點擊或移動焦點；一般動態設定下先保持可見再淡出，5 秒後移除；重複更新重新計時，unmount 清理 timer。減少動態效果設定停用動畫，保留 5 秒閱讀時間。使用 `role=status` / polite / atomic 宣告。
- `ModelEditor.tsx`、`ModelConnectionPanel.tsx`：編輯器開啟時，把更新失敗原因放在送出按鈕旁；編輯器關閉時保留面板層級錯誤。失敗保留表單，不顯示成功提示，不重複宣告兩個相同 alert。

對應 FR-039/040、AC-055/057 與 AC-023 的服務編輯回饋部分。沒有改動服務 credential policy、API/資料庫契約、啟用門檻或自動切換模型。

截圖中若將原網址改為新網址，同時 API key 留白且未選擇移除金鑰，既有後端會拒絕 `CREDENTIAL_REPLACE_REQUIRED`。這是既有目的地變更保護；本次改善的是就近顯示原因與明確確認成功，沒有繞過該保護。未讀取現有私密設定，因此不能聲稱知道擁有者資料庫目前儲存哪個網址。

## 真實請求結果

擁有者明確提供本次服務、`claude-sonnet-5` 模型與金鑰並要求測試。三次請求的狀態與內容類型如下，沒有自動重試：

| 操作 | HTTP | Content-Type | 結果 |
| --- | --- | --- | --- |
| GET 基礎網址 `/`，不帶金鑰 | 200 | text/html | 網站可回應 |
| POST `/v1/chat/completions`，RepoNPC JSON probe | 503 | application/json | 上游原文 `No available accounts: no available accounts` |
| POST `/chat/completions`，相同 JSON probe | 200 | text/html | 1166-byte HTML 本文，重現「HTTP 200 本文不是 JSON」這條失敗路徑 |

因此，此次實測的服務需使用含 `/v1` 的 Chat Completions 路徑才能取得 API 回應；任意服務是否需要 `/v1` 仍由其公開 API 基礎網址決定，沒有增加依 hostname 猜測/補路徑的程式。正確端點本次仍被服務商以 503 拒絕，未取得模型回答。這次重現的是提供未帶 `/v1` 的基礎網址時的行為，不等同直接讀取並證實先前執行中的設定。

金鑰使用不回顯的暫時程序輸入，僅在記憶體中使用；原始碼、設定、fixture、文件及測試日誌沒有金鑰。診斷只顯示固定 MIME/本文形狀、長度、狀態及既有遮蔽器處理的上游錯誤；未輸出完整 HTML、完整 JSON 或 headers。沒有修改擁有者服務設定、充值、啟用模型或重啟其程序。

CC Switch 官方 `src-tauri/src/services/stream_check.rs` 目前的實作是 GET 基礎網址，任何 HTTP 回覆（包含 4xx/5xx）都代表 reachable；不傳模型請求、不檢查金鑰或模型。其成功提示不能作為模型生成成功的證據。[官方原始碼](https://github.com/farion1231/cc-switch/blob/main/src-tauri/src/services/stream_check.rs)

## 驗證

- `pnpm run web:check` 通過：Prettier、ESLint、TypeScript、129 tests / 21 files、production build；保留 12 項既有 Fast Refresh warnings。日誌 `.tmp/service-save-toast-web.log`。
- 新增 `TransientNotice.test.tsx` 的雙語 status/焦點語意檢查。
- 真實瀏覽器 375px、合成資料、production AdminPage/ModelConnectionPanel：`tests/browser/check-service-notices.js` 的 8 項檢查全通過，包含拒絕儲存、成功關閉表單、重複更新不受舊 timer 影響、5 秒後移除、英文提示、成功寫入後刷新失敗分離、無水平溢出。fixture 為 `admin-events-review.tsx`，攔截所有網路請求，沒有真實模型或設定操作。
- 既有 `check-admin-events.js` 7 項共用模型/草稿事件回歸全通過。
- 分散工具呼叫的首次人工時間取樣跨過 5 秒，不能用來判定 timer 有誤；後以單一具精確時間控制的可重跑 checker 驗證重複提示與移除，通過。減少動態設定僅驗證 CSS 規則，未另作該偏好下的 browser emulation；不宣稱完整 WCAG/螢幕閱讀器驗收。
- `git diff --check` 通過。本次沒有 Python production 修改，未重跑後端套件。Live API 結果依上表如實記錄，不計入單元測試通過數。

沒有提交或部署；需載入更新的管理頁才有新提示。上游 503 的可用性仍是未解決的外部狀態。

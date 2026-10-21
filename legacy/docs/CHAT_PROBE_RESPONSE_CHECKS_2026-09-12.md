# 模型測試解析錯誤追查

截圖中的 `PROVIDER_INVALID_RESPONSE` 不能證明 API key 或網址錯誤。原程式把 HTTP 200 回應的 JSON、choices、message、content、finish reason、usage 和 id 檢查失敗合併成同一錯誤，沒有保存失敗位置；測試另外寫死 32 tokens 和 10 秒。無實際回應留存，因此這次不能聲稱已確定 coderelay 的真正失敗原因。

## 修正

- `src/reponpc/admin/chat_profiles.py`：測試使用既有 provider capability 的輸出上限；保留一次呼叫與 JSON 驗證，期限於 2026-09-14 經 owner 核准改為基準 10 秒加一次 10 秒寬限，單一請求總上限 20 秒。若收到 `length` 終止，指出輸出上限，避免把部分 JSON 視為成功。
- `src/reponpc/providers/openai_compatible.py`、`ollama.py`、`response_diagnostics.py`：按解析階段提供固定診斷，包括空白回答伴隨 `length`；不根據服務商名稱、模型名稱或自然語言猜原因。一般生成流程仍可回傳非空的部分內容及其 finish reason，由上層處理。
- `apps/web/src/features/admin/modelProbeError.ts`：顯示既有欄位中的應用程式診斷。`RepoNPC response check:` 明確標示來源；真正的 HTTP 錯誤仍顯示服務商原文。沒有詳細原因的舊資料不補造 HTTP 狀態或原因。
- 更新規格、驗收、安全、決策及操作說明；API 錯誤碼、資料庫 schema、供應商切換規則均未增加。

相關需求：FR-038/040、AC-054/055/057、雙語 AC-023 的此次診斷部分。這不是整組驗收通過聲明。由 Main 直接處理跨層共同流程，沒有新增代理派工。

## 驗證

- 後端聚焦回歸：125 passed，含新添 22 項 OpenAI-compatible/Ollama adapter → profile 實際儲存的解析與輸出額度反例；現有 authenticated API 測試涵蓋重新讀取、無權限拒絕、成功清除與 HTTP 原文保留。日誌：`.tmp/chat-parser-backend.log`。保留一項既有 Starlette/httpx deprecation warning。
- 前端 `pnpm run web:check`：127 tests / 20 files passed，Prettier、ESLint、TypeScript 和 production build 通過；保留 12 項既有 Fast Refresh 警告。日誌：`.tmp/chat-parser-web.log`。
- Ruff lint/format、mypy（4 個變更的 Python 模組）通過。
- 實際瀏覽器使用 `tests/browser/chat-response-review.tsx` 的合成資料，在 375px 驗證繁中與英文 alert、來源標籤、純文字顯示及無水平溢出。不是完整螢幕閱讀器或所有裝置驗收。
- 首輪測試 106 passed / 1 failed：既有測試將 HTTP 錯誤的金鑰遮蔽 suffix 錯加到新增的本機診斷期望值；修正判斷後上述聚焦回歸全通過。Import 排序檢查也已修正並重跑通過。

反硬編碼分類：adapter 邊界與開放回應資料。固定值只描述封閉的解析檢查；不反映 body 值。反例使用不同協定、任意模型名稱、空白/部分/畸形內容和不同設定上限；不存在針對截圖模型的條件分支。

## 實際限制

原 2026-09-12 修正未讀取真實 key/URL、未呼叫真實模型、未重啟既有服務、未提交或部署。2026-09-14 實測確認 coderelay 的模型清單約 0.9 秒回覆、Chat 約 11.6 秒回覆，超過原 10 秒期限但落在新增寬限內。若仍達到 20 秒總上限或其他檢查失敗，仍會誠實失敗；不自動加額度、重送請求或換模型。用量欄位的既有型別驗證仍保留。

推理 tokens 可能先消耗輸出額度，是有協定依據的可能性，不是本次 live failure 的證明：[OpenAI token 說明](https://help.openai.com/en/articles/4936856)。

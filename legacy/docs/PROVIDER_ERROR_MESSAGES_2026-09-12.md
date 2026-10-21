# 模型測試錯誤原文修正

擁有者指出原先的 HTTP 402 付款說明是 RepoNPC 依狀態碼補上的推測，要求直接顯示服務商錯誤原文。本次移除 HTTP 原因翻譯對照表，中英文介面均顯示實際狀態碼與相同原文。沒有可顯示文字時，明確顯示「未提供可顯示的錯誤文字」，不猜測原因。

涉及 FR-038／039／040、AC-054／055／057 與雙語 AC-023 的診斷部分；不代表完整 v1 或整組 AC 驗收。擁有者本次已授權修正，不需再決定修改方向。

## 實作與契約

- `src/reponpc/providers/error_messages.py` 集中解析回應結構：`error.message`、字串 `error`、`message`、`detail` 或明確標示的純文字回應。不依服務商名稱、語言或訊息關鍵字列舉原因。
- 四個 Chat／Embedding adapter 傳遞解析後的文字；`ProviderError` 的一般例外文字維持固定安全訊息。註冊表與已登入管理 API 增加 nullable `last_error_message`，重新讀取仍保留失敗原文，成功重測與使測試失效的修改會清除。
- Runtime migration 20 在 Chat／Embedding 表新增欄位，交易失敗回復全部欄位變更。舊資料與選用保留；舊版從未儲存的原文無法還原，需明確重新測試。
- 前端兩個模型面板與 `modelProbeError.ts` 顯示原文、保留換行、長字串換行並以文字跳脫 HTML。新增按鈕仍為「新增模型 / Add model」。
- 原文只做必要處理：先遮蔽已知設定金鑰、私人網址、編碼形式、主機名稱與 URL，再移除不安全顯示控制字元和無效 Unicode，最多保留 2,000 字元；解析輸入上限 65,536 bytes。完整 JSON、HTML 頁面、額外 metadata、headers 不傳回或儲存。無法保證辨認服務商任意未知的秘密文字，因此不擴大到公開診斷、日誌、分析結果或 bundle。

狀態碼是有限協定值，錯誤文字是開放資料；抽象設於 adapter 回應解析邊界。保留的固定值是訊息欄位契約、HTTP 有效範圍與資源／儲存上限。反例包含不同語言、未知詞彙、不同輸出結構、缺少訊息、無效格式、過長輸入、URL 編碼金鑰、HTML 文字與截斷邊界，並非只覆蓋截圖中的 402。

## 驗證

完整後端執行：833 passed、2 skipped、1 failed。失敗是 Docker 容器煙霧測試；目前環境無法讀取 Docker 設定或存取 Docker named pipe，引擎連線遭拒，不能宣稱 Docker 通過。保留一項既有 Starlette/httpx 相容性警告。後續新增無效 Unicode／URL 外觀金鑰的反例與設定金鑰完整傳遞檢查，最終聚焦結果見下方補記。

最終聚焦回歸：112 passed，包含原文解析、多語言／格式反例、四條 adapter → registry → 已登入 API 傳遞／重新讀取／成功清除流程、設定金鑰遮蔽、last-known-good 與 migration 19／20 保留／回復檢查。

文件更新後另跑 8 項規格／文案契約測試，全數通過；最終 Ruff format 和 mypy 也通過。

前端 `pnpm run web:check` 通過：Prettier、ESLint、TypeScript、118 項測試與 production build；保留 12 項既有 Fast Refresh 警告。Python Ruff lint／format 通過，mypy 檢查 68 個來源檔案通過。

實際瀏覽器以現有兩個 React 模型面板和 CSS、375px 寬容器及隔離合成資料驗證：英文／法文原文在繁中和英文介面相同；換行保留、長文字無水平溢出；`<img ...>` 保留為文字、沒有子元素或執行事件；錯誤文字出現在可及性樹中。這不是完整螢幕閱讀器或真實服務商相容性驗收。臨時頁已移除，驗證服務與瀏覽器分頁已關閉。

證據在 `.tmp/provider-messages-backend.log`、`.tmp/provider-messages-web.log`、`.tmp/provider-messages-focused.log`；隔離介面來源為 `.tmp/provider-message-review.html` 和 `.tmp/provider-message-review.tsx`。套件執行工具第一次遇到快取權限問題，改用工作區快取；過長測試參數名稱造成 Windows 環境限制，改為短測試識別名稱後通過。這些環境／測試工具問題均未隱藏。

本次沒有呼叫真實模型、產生模型費用、修改擁有者設定、重啟既有後端、遷移正式 runtime、提交或部署。要在目前執行中的服務看到新行為，需載入配套前後端並重新測試舊失敗模型。

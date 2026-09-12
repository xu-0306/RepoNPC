# Mochi 模型測試對照與實際請求結果

## 對照來源

擁有者指定的參考專案實際位於 `D:/mochi_agent/mochi`，本次僅讀取，沒有修改該專案。

- `agents/engine.py:6537` 的 `test_model_connection`：透過 temporary backend 呼叫 generate，提示 `Reply with exactly OK.`，傳入 `max_tokens=16`、`stream=False`；呼叫返回後直接取得模型資訊，不檢查產生文字是否等於 OK。
- `backends/openai_compat.py:531` 的 `_blocking_generate`：呼叫 `resp.json()` 後依 API 模式解析。Mochi 的非串流回應同樣需要 JSON，並非接受任意 HTTP 200 本文。
- 同檔案 `:1145`：解析 Chat Completions 時允許缺少 choices/content 等欄位，並處理文字區塊、reasoning 與 optional usage。
- 同檔案 `:1170` 附近：串流流程另行解析 SSE/JSON lines；不應把這段誤認成非串流測試一定會接受 SSE。
- 同檔案 `:2635`：網址正規化辨識完整 `/chat/completions`、`/responses` 與基礎 `/v1`；依能力建立參數、協定選擇與 fallback 是 Mochi 額外的行為，不等同 RepoNPC 現有契約。

RepoNPC 的 `response body is not a JSON object` 指的是 HTTP 本文解碼/解析，發生在 choices、message 與模型回答 JSON 檢查之前。因此，先前調整輸出 token 額度不能證明已解決這次失敗。

## 已驗證並修正的差異

`src/reponpc/providers/openai_compatible.py` 的 `_json_object` 原先先 `decode('utf-8')` 再呼叫 JSON parser；帶 BOM 的合法 JSON 會被拒絕。Mochi 使用的 httpx JSON 方法則把 response bytes 交给標準 JSON parser。

現改為 `json.loads(body)`，由標準 parser 處理 BOM / Unicode encoding detection。保留 JSON object 根節點與各 adapter 結構驗證，不把 HTML、SSE 或任意純文字假裝成模型回答。OpenAI-compatible Chat 與引用該 helper 的 Ollama Chat 都受此修正涵蓋。未擴充新 API 模式、URL fallback、放寬啟用條件或改寫原有模型測試目的。

新增 `tests/unit/test_chat_adapters.py` 的 8 個 adapter × encoding 反例（UTF-8、UTF-8 BOM、UTF-16、UTF-32）。修正前 6 failed / 2 passed；修正後連同 adapter、profile persistence、authenticated diagnostic API 回歸共 **108 passed**。Ruff lint/format 與 mypy 通過，保留一項既有 Starlette/httpx 警告。記錄在 `.tmp/mochi-encoding-before.log`、`.tmp/mochi-compare-after.log`。沒有前端變更，本次未重跑前端/build/browser。

分類為 adapter 解析邊界：使用標準 JSON byte parser，沒有依服務商、模型名稱或錯誤文字寫特例。對應 FR-038、AC-054/055/057 的解析診斷部分，不代表整組驗收。

## 擁有者授權的 live 比較

擁有者提供基礎 `/v1` 位址、指定模型與金鑰並明確要求測試。本次只發出兩次 POST 至該基礎網址下的 `/chat/completions`：

1. RepoNPC 形式：實際 pinned HTTP transport、既有 JSON-schema probe payload、輸出上限 1000、10 秒 timeout。
2. Mochi 形式：httpx 非串流請求、簡單 OK 提示、輸出上限 16、10 秒 timeout。這是請求形式比較，不是啟動整套 Mochi，也不包含其 capability discovery/fallback。

兩者都回傳 **HTTP 400、application/json、JSON object**；服務商訊息同為 `credit insufficient balance: balance=0 required=102`。未重現先前 HTTP 200 非 JSON 本文，無法用此次回應證明原始故障是 BOM、SSE、HTML 或網址重複追加。餘額字樣是上游回覆，不是 RepoNPC 翻譯或獨立查帳結果。兩次遭拒後沒有再呼叫。

金鑰透過不回顯的暫時程序輸入，只在記憶體中使用；未寫入原始碼、設定、fixture 或測試日誌。輸出僅有狀態、已知 MIME 分類、本文長度/形狀，以及既有遮蔽器處理的服務商錯誤文字；沒有回傳完整 body 或金鑰。第一次管線輸入不可用，在發出任何網路请求前結束，改用不回顯輸入後完成兩次測試。

## 尚未確認

此組憑證目前被上游拒絕，無法取得成功回應來定位原先的 HTTP 200 解析失敗。BOM 修正有合成測試證據，但不宣稱是原始問題根因。純連通測試與回答能力測試的分離尚未實作；目前模型測試仍要求既有 JSON 能力，沒有把任意 HTTP 200 當成可啟用模型。沒有重啟、提交或部署。

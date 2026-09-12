# 已儲存服務網址的編輯（2026-09-12）

擁有者明確要求：「更換網址」應顯示原網址，方便直接修改。這項授權修正 ADR-029 原本禁止任何已儲存網址回傳的限制；API key 仍不可讀回。無需再次確認相同授權。

## 行為與範圍

- 開啟服務編輯仍預設保留網址；勾選「更換服務網址」才向後端讀取，並把目前儲存值放入可編輯的網址欄位。
- 載入中停用網址欄位及送出；失敗有重新讀取按鈕，也可直接輸入新網址。取消、更換服務、切換連線方式、取消勾選或表單卸載，會作廢未完成的回應。服務 revision 更新也會清除舊值；身分／版本不符的回應不會帶入。
- 新增 `POST /api/admin/model-connections/{connection_id}/edit-endpoint`，要求現有管理員工作階段、同源及 CSRF；只返回 `{connection_id, revision, base_url}`，`Cache-Control: no-store`。它只讀取 managed 服務的指定目前加密 revision，不呼叫服務商，不修改設定。host-managed 或未知 ID 回 404，金鑰庫不可用回 503，錯誤不包含私有值。
- 一般 GET 清單／詳情仍不含網址；任何回應都不包含 API key。網址只留在當前表單記憶體，不進入 browser storage、公開草稿、匯出或記錄。取消等既有表單清理機制仍生效。
- 實際變更目的地，仍須明確輸入新金鑰或選擇移除金鑰；沒有取消「禁止將舊金鑰自動傳到新目的地」的規則。只是帶入而未改網址時，既有保留金鑰／不變更 revision 的規則仍適用。

## 檔案與契約

程式：`src/reponpc/admin/operations.py`、`src/reponpc/api/admin.py`、`apps/web/src/features/admin/AdminPage.tsx`、`ModelConnectionPanel.tsx`。

驗證：`tests/integration/test_novice_model_setup.py` 新增三項授權／回應範圍／故障測試；`tests/browser/endpoint-edit-review.tsx` 提供可切換成功、失敗與延遲回應的隔離瀏覽器頁。`tests/browser/README.md` 的執行方式適用，reviewName 使用 `endpoint-edit`。

規格／安全更新：`TECHNICAL_SPEC.md`、`SECURITY.md`、`ACCEPTANCE_CRITERIA.md`、`DECISIONS.md`、`OWNER_REVIEW.md`、`MODEL_SETUP_IMPLEMENTATION_HANDOFF.md`、`OPERATIONS.md` 與根目錄 `AGENTS.md`。本次沒有 migration、環境變數、公開 API／公開設定格式變更。對應 FR-038／040、AC-055／057，及 AC-023 雙語呈現的部分行為。

## 執行證據

- 最終 `pnpm run web:check`（2026-09-12 15:27，Asia/Taipei）：格式、lint、型別、125 tests／20 files 與正式建置通過。12 個既有 Fast Refresh warnings；本輪新增的 Hook dependency 警告已修正。

- `uv --cache-dir .tmp/uv-cache run --no-sync pytest tests/integration/test_novice_model_setup.py tests/integration/test_model_probe_diagnostics.py tests/contract/test_novice_copy.py -q -o cache_dir=.tmp/pytest-endpoint`：65 passed。
- `uv --cache-dir .tmp/uv-cache run --no-sync pytest tests/unit/test_model_connections.py tests/integration/test_model_connections_api.py tests/security/test_admin_security.py -q -o cache_dir=.tmp/pytest-endpoint`：32 passed。兩組皆有既有 Starlette TestClient 的 httpx 棄用警告。
- Ruff 格式／lint 與 mypy（operations／admin API）通過。檢查發現的重複方法宣告已移除，重新 lint／型別檢查通過。
- 瀏覽器正式元件＋合成資料：開啟編輯不讀取、勾選後帶入、修改後的提交值、金鑰保持空白、載入停用、切換服務拒絕舊回應、失敗後手動輸入／重讀成功、中英文取消及晚到回應隔離均確認。沒有使用實際網址或金鑰；此證據不等同真實啟動器到伺服器的端到端驗收。

本次包含後端新端點；已執行中的應用程式需要重新啟動才能使用。沒有替擁有者重啟服務、讀取真實網址／API key 或改動實際模型設定。測試伺服器、頁籤與暫時入口已清除。無待批准的產品決策。

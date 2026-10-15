# 下一輪交接：UI 小修、Docker 修復、瀏覽器實測與 commit（2026-10-15）

> **本輪續作已完成（2026-10-15）**：UI 1a–1d 與首次草稿還原競態已修；web:check 587 tests / lint 20 warnings、兩項 Docker smoke 與最終映像建置通過。Owner 同意由 Codex 完成真實瀏覽器檢查及重啟；一次雙 repo 分析 2/2 成功、58 秒、各生成一次，雙語/桌面/375px/鍵盤/RESET 通過。已正常登出並只關閉測試 session，owner 草稿 checksum 不變。Owner 已確認完整檔案清單，依序分三個本機 commit，不 push；後續請先看 OUTPUT_SCRIPT_AND_CACHE_REPAIR_PLAN_2026-10-14.md 最後的「本輪續作結果」與 output/playwright/ui-e-f-20261014/REVIEW_2026-10-15.md。以下保留原始交接要求與步驟作為歷史。


給接手的 agent。這份文件可以單獨閱讀，不必先看先前的對話。
動手前請依 `AGENTS.md` 第 1 節的順序閱讀規格。
上一輪的完整紀錄在 `docs/OUTPUT_SCRIPT_AND_CACHE_REPAIR_PLAN_2026-10-14.md`，請特別看「實作進度與交接」一節。

## 目前狀態

- A–F（模型輸出的文字系統檢查、短標題、快取版本、出處形狀、Highlights 改版、React Aria）已經實作並驗證，**全部尚未 commit**。工作樹的改動清單見下方「Commit 分批」。
- C 項（舊草稿補上 `profile.github_login`）已經套用，portfolio API 回 200。
- 驗證結果：
  - 前端：format、typecheck、lint 為 0 error、20 warning；581 項測試通過，build 正常。
  - Python：2737 passed、2 skipped、2 failed。失敗的兩項是 Docker smoke（見步驟 2）。
- 規格版本為 TECHNICAL_SPEC 0.4.12，對應 AC-080、ADR-060 與 ADR-061。

## Owner 已確認的順序（2026-10-15）

1. 步驟 1、2 先修，然後才做步驟 3 的瀏覽器實測。
2. Dockerfile 的修正放進這一輪。
3. 實測通過後分三個 commit，commit 前先讓 owner 看檔案清單，**不 push**。
4. G 輪（引導流程其他步驟減字）另外安排，先做 mockup。

## Owner 偏好與限制

- 不喜歡文字太多、看起來像 AI 寫的 UI，要白話。這一輪不要順手加說明文字。
- 不要重設或覆寫 owner 的草稿與設定；sessionStorage 各分頁獨立，owner 原分頁有還原的手動路線草稿。
- 重啟伺服器前先問 owner。
- 呼叫模型的授權只有一次：一批、兩個 repo 的分析。失敗也不要自行重試，先回報。
- 不 commit、不 push、不部署，除非 owner 另外說。
- 中文文件用 UTF-8 寫入，寫完確認沒有 U+FFFD。

## 步驟 1：UI 小修（前端）

### 1a（高）「重新開始」後模型步驟卡住

- **現象**：在引導流程按「重新開始」後，回到模型步驟時「完成模型設定並選擇專案」一直是停用狀態，提示要求按「確認用於分析」。但那顆按鈕也是停用的，因為伺服器上的選擇早已確認。只有重新整理頁面才能繼續。
- **原因**：
  - `apps/web/src/features/admin/guidedOnboarding.ts` 的 reducer 中，`case "RESET"` 回傳 `initialGuidedOnboardingState()`，把 `modelsConfigured` 設成 false。
  - 這個值其實是伺服器狀態，來源是 `AdminPage.tsx` 的 `refreshAnalysisSelection`，它用 `/api/admin/analysis-selection` 的 `eligible` 派發 `SET_MODELS_CONFIGURED`。這個重讀只在載入時、以及選擇失敗時執行。
  - `GuidedOnboardingView.tsx` 的 `ModelsStep` 用 `state.modelsConfigured` 決定按鈕是否停用。
- **建議修法（最小）**：`RESET` 改成回傳 `{ ...initialGuidedOnboardingState(), modelsConfigured: state.modelsConfigured }`，因為這不是草稿內容。
- **測試**：在 `guidedOnboarding.test.ts` 加一個案例：先 `SET_MODELS_CONFIGURED: true`，接著 `RESET`，再走 `START_AI`、`COMPLETE_MODEL_SETUP`，應該進入 repositories 步驟。
- 若決定改用「RESET 後呼叫 `refreshAnalysisSelection`」，要說明理由，並補上對應的 AdminPage 測試。

### 1b（中）模型步驟的狀態與提示互相矛盾

- **現象**：`AnalysisSelectionPanel.tsx` 的 `role="status"` 依伺服器的 `eligible` 顯示「兩個模型已選用，可開始分析。」，但 `ModelsStep` 的停用原因同時顯示 `copy.modelsRequired`：「請先測試回答模型與資料查找模型，再於選擇區按「確認用於分析」。」
- **判斷**：兩者矛盾的根本原因就是 1a，前端 state 和伺服器 state 不同步。修好 1a 後，請先重現確認矛盾是否消失。若仍有其他路徑造成不一致，再讓 `ModelsStep` 改用同一個伺服器來源。
- 不要新增說明文字。減字屬於 G 輪。

### 1c（低）ⓘ 的 aria-label 與可見文字重複

- **位置**：`GuidedOnboardingView.tsx` 的 Highlights 區塊（搜尋 `guided-analysis__info`）。按鈕的 `aria-label` 和 `Dialog` 的 `aria-label` 都用了 `copy.inferenceDescription`，而這段文字就在旁邊的 `<p>` 裡顯示，所以螢幕閱讀器會讀兩次。
- **修法**：按鈕和 Dialog 改用一個短的專用標籤，例如「隱私說明」／「Privacy details」，中英文都要加到 copy。
- **測試**：同步更新 `GuidedOnboardingView.test.tsx` 中相關的斷言。只能等價替換或加強，不可刪除或放寬。

### 1d（低）Ollama 安裝和刪除共用同一段確認文字

- **位置**：`EmbeddingProfilePanel.tsx` 的兩個 `ConfirmButton`，都用 `description={copy.modelConfirm}`：「此動作會變更 Ollama 的模型儲存。確定繼續嗎？」
- **修法**：分成兩個 copy key，各一句白話，中英文對等。方向如下：
  - 安裝：會下載到這台電腦，需要時間與空間。
  - 刪除：會從這台電腦移除，之後要用需重新下載。
- 實際大小沒有可靠來源，所以不要寫數字。

### 步驟 1 驗證（repo 根目錄）

```powershell
pnpm run web:check
```

這個指令依序執行 format、lint、typecheck、vitest 和 build（含 visitor guard）。
lint 目前有 20 個 warning，基準是 0 error。回報時要說明 warning 數量有沒有變動。
Codex 的 sandbox 無法寫入 `apps/web/src/styles.css`，也無法執行 vitest/vite（spawn EPERM）。這些要在 sandbox 外執行。

## 步驟 2：Docker smoke 修復

- **原因**：`apps/web/src/features/admin/PagesSharePanel.tsx:2` 匯入 `../../../../../docs/PAGES_SHARING_GUIDE.md?url&no-inline`，但 `Dockerfile` 的 web-build 階段（第 19–25 行附近）沒有複製這個檔案，所以映像建置失敗。
- **修法**：在該階段 `COPY apps/web apps/web` 的附近加上 `COPY docs/PAGES_SHARING_GUIDE.md docs/PAGES_SHARING_GUIDE.md`。只複製這一個檔案，不要複製整個 `docs/`。
- **驗證**：

```powershell
uv run pytest -q tests/smoke/test_container.py tests/smoke/test_visitor_gateway_container.py
```

  這兩項需要本機 Docker。另外跑 `docker build --tag reponpc:ci .`。

## 步驟 3：真實瀏覽器實測與 UI/UX 審查（owner 指定 Sonnet 5.5）

1. 先執行 `pnpm run web:build`，讓伺服器提供的是新版前端。
2. **先問 owner 可不可以重啟**，得到同意後再執行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-reponpc.ps1 -NoBrowser -NoPause
```

   啟動腳本會印出一次性 Admin 網址，2 分鐘內有效，格式是 `http://localhost:8090/admin#local-launch=…`。如果有舊版伺服器還在執行，腳本會替換掉它。
3. 瀏覽器工具：上次內建 Browser 在 import 時遇到 EPERM。已經驗證可用的是快取中的獨立 Playwright CLI 真實 Chromium session，參考 `output/playwright/readme-flow-20261012/RESULT.md`。登入後要確認網址中的 `#local-launch` 已被清除，才可以截圖。
4. 用**新分頁或新 session** 走 AI 路線：選 GitHub 帳號 xu-0306，勾選 engineering-guardrails 和 live-subtitle，跑**一次**批次分析（會呼叫 gpt-6.1-sol）。
5. 檢查項目：
   - Highlights：短標題列、展開後是完整句子加 GitHub 來源連結、`+n`、缺漏來源的提示。中英文都要看，桌面與 375px 寬度都要看。
   - ⓘ popover：鍵盤開啟，Esc 關閉，焦點回到觸發按鈕；並確認 1c 的標籤已經修好。
   - 確認框：**只開啟再取消**，不可以按下確認。
   - 顯示設定 popover。
   - 1a：在**測試分頁**完成分析檢查後，按「重新開始」並確認。模型步驟不應卡住。
     - `RESET` 只在前端處理（`AdminPage.tsx` 的 `applyGuidedAction`），會清除該分頁的引導狀態與批次畫面，不會呼叫伺服器 API。
     - 所以要先把分析結果截圖，再按「重新開始」。
     - 絕對不要在 owner 的原分頁按。
6. 截圖存到 `output/playwright/ui-e-f-20261014/`。目前已有 01、02，請從 03 接著編號。
7. 產出一份 UI/UX 問題清單，依嚴重度排序，每項附上截圖與重現步驟。不要宣稱已驗證完整瀏覽器矩陣或螢幕閱讀器。
8. 結束時用 UI 登出，只關閉自己開的 browser session。

## 步驟 4：結果整理與 commit（需要 owner 授權）

- 把結果寫回 `docs/OUTPUT_SCRIPT_AND_CACHE_REPAIR_PLAN_2026-10-14.md` 的交接段，以及專案記憶 `.claude/skills/agent-memory/memories/reponpc/current-state-2026-10-15.md`。
- 分三個 commit，訊息結尾依 repo 慣例加上 attribution：
  1. **A–F 與文件**：目前工作樹裡全部已修改的 tracked 檔案，加上以下新檔：
     - `apps/web/src/features/admin/ConfirmDialog.tsx`
     - `apps/web/src/features/admin/ConfirmDialog.test.tsx`
     - `apps/web/src/features/admin/guidedAnalysis.css`
     - `packaging/windows/licenses/client-only-0.0.1-LICENSE.txt`
     - `docs/OUTPUT_SCRIPT_AND_CACHE_REPAIR_PLAN_2026-10-14.md`
     - 本文件
  2. **UI 小修**：步驟 1 的改動。改到同一個檔案時，用 `git add -p` 分開。如果分不乾淨，告訴 owner，並提議併入第 1 個 commit。
  3. **Dockerfile**。
- **絕對不要加入**：`%SystemDrive%/`、`PixelNPC/`、`RepoNPC_R09_R14_REPAIR_2026-09-17/`、`output/`、`runtime-data/`、任何密鑰，以及被 git 忽略的本機文件（`PROJECT_CONTEXT.md`、`OWNER_REVIEW.md`、`IMPLEMENTATION_PLAN.md`、memory）。
- 先把檔案清單交給 owner 確認，再 commit。不 push。

## 仍待 owner 決定（不阻擋上面步驟）

- client-only@0.0.1 授權補充檔的出處（從已安裝的 react 19.1.1 MIT 複製），發布前需要 owner 審查。
- 「描述貢獻」是否帶入分析推論。這屬於規格變更。
- 貢獻建議 180 秒逾時：是否先量測 gpt-6.1-sol 的實際回應時間。
- README：需要 owner 套用草稿，並提供 Pages URL。

## 若交給 Codex

照 `C:\Users\xu\.claude\CLAUDE.md` 的方式呼叫 `codex exec`：
- 加上 `-c 'windows.sandbox="unelevated"'`。
- 每個工作拆小。大型 brief 曾遇到 relay 503。
- 要求 Codex 保留每個檔案原本的換行格式，並逐項列出「原 → 新」的斷言變更。

Codex 曾兩次誤寫 RAC `DialogTrigger` 按鈕有 `aria-haspopup="dialog"`，實際輸出是 `aria-expanded`。

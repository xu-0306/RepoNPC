# 模型輸出文字系統檢查、分析結果改版與舊草稿修復計畫

狀態：Job 1–2 已實作 A、B、D、E、F；Job 3 文件已完成。C 尚未實作，完整驗證尚未完成。Owner 於 2026-10-14 同意 A–F，並確認 E 採用範本
`output/mockups/ui-e-f-2026-10-14.html` 的「改版後」方向（含推論短標題）；
G 為之後另一輪。
需求：FR-008（證據分類）、FR-022（雙語）、FR-027/FR-033 與 AC-078（分析快取重用）、
FR-045（`profile.github_login`）、NFR-001、NFR-009（無障礙）。
本次實作登記 OR-034 / ADR-060（A–E）與 OR-035 / ADR-061（F），規格升為 0.4.12。

## 觀察到的問題

2026-10-13 實際操作 `xu-0306/engineering-guardrails`、`xu-0306/live-subtitle`：

1. 分析結果的中文句子夾了俄文「предназнач」。來源是模型輸出，而且是快取命中
   （預測快取命中 2，模型呼叫 0）。`_parse_analysis` 只驗證 schema、證據 ID
   與個人歸因，沒有檢查文字系統。
2. 快取命中時畫面顯示「查看專案依據（0 個來源）」。原因是 `_cached_result`
   刻意回傳 `facts: []`，快取不存專案原文。
3. 作品集 API 一直回 422 `PORTFOLIO_CORRUPT`。舊草稿建於 09-23，
   而 `profile.github_login` 在 09-28（`1e82ee8`）才改成必填，
   當時沒有升 `schema_version`，也沒有遷移既有草稿。
4. 「AI 推論」區塊字太多：長句、每張卡重複安全聲明、原始 Markdown 摘錄、
   三層巢狀外框，且掛著「尚未確認」卻沒有確認動作。這些推論只用來顯示：
   貢獻建議只送 owner 說明與 slug（`onboarding.py:799`），草稿與作品集也不收推論。

`profile.github_login` 不是舊殘留：它是站主自己的 GitHub 帳號，每位使用者
在引導流程填自己的。索引用它判斷哪些 commit 屬於站主（FR-045），聊天用它
辨認「在問站主」。

## A. 模型輸出的文字系統一致性

### 規則

不禁止任何語言，只拒絕「無中生有」的文字系統。模型輸出的每個在地化欄位，
其中每個「詞」所屬的文字系統必須滿足其一：

1. 屬於該欄位語言的基本文字系統；
2. 出現在這次請求的原始資料裡。

| 欄位語言 | 基本文字系統 |
|---|---|
| `zh-TW` | 漢字（CJK）、注音、拉丁字母（技術名詞） |
| `en` | 拉丁字母 |

原始資料：

- 分析：`packed.text`（實際送給模型的專案內容）與 repo slug。
- 貢獻建議：owner 輸入的說明與 repo slug。

| 情況 | 結果 |
|---|---|
| 中文專案，中文句子冒出俄文詞 | 原始資料沒有俄文，判定為模型口誤並拒絕 |
| 俄文專案，中文句子引用俄文檔名 | 原始資料有俄文，放行 |
| 英文句子引用中文檔名 | 原始資料有漢字，放行 |
| 句子裡出現 `μs`、`λ` 這類單一符號 | 不算詞，放行 |
| owner 自己輸入的文字 | 不檢查 |

基本文字系統表放在 `onboarding.py` 的同一處。將來新增介面語言時，在同一處
補一列；俄文介面就是加 `ru: {CYRILLIC}`。規則本身不列舉任何被禁止的語言。

### 文字系統判定

只用標準函式庫 `unicodedata`，不新增依賴（`regex` 只是間接依賴）。

- 先做 NFKC 正規化，讓全形字母、`µ`（MICRO SIGN）併入一般字母。
- 只看一般類別 `Lu/Ll/Lt/Lo` 的字母。`Lm`（修飾字母、`々`）、數字、標點、
  符號和 emoji 都不檢查。
- 文字系統取 Unicode 字元名稱的第一個字，例如 `CYRILLIC`、`LATIN`、`HANGUL`、
  `HIRAGANA`；`CJK UNIFIED/COMPATIBILITY IDEOGRAPH` 歸為 `CJK`。
  原始資料和輸出用同一個函式判定，因此近似誤差兩邊一致。
- 「詞」：同一文字系統的連續字母達 2 個以上。單一外來字母多半是符號用途
  （`μ`、`π`、`Ω`），所以不算詞。

參考：Unicode UTS #39 的 mixed-script 偵測（ICU `SpoofChecker`）也是用文字
系統集合判斷，而不是判斷語言。本計畫只取「集合比對」這一點，不引入
confusable 偵測或語言辨識。

### 套用位置與錯誤

- `_parse_analysis` 新增 `source_text` 參數，兩個呼叫點
  （`onboarding.py:565`、`:743`）傳入 `packed.text` 與 slug。檢查每條推論的
  `title` 與 `statement`（`title` 見 E1）。
- `_parse_contribution` 新增 `source_text` 參數（`:820`），傳入 owner 說明與 slug。
  檢查角色、摘要與每個 claim。
- 違反時沿用 `PROVIDER_ERROR` / `PROVIDER_OUTPUT_SCHEMA_INVALID`。
  不新增錯誤代碼或原因，所以不需要第 25 號 runtime 遷移
  （原因欄位在 `database.py:892` 有 CHECK 白名單）。
  處理方式與目前格式錯誤相同：不重試、不儲存原始輸出、不寫入快取。
- `BatchAnalysisPanel.tsx` 對這個原因的中英文訊息目前寫「不符合分析 JSON 格式，
  請確認模型支援結構化輸出」。改為「模型回覆沒有通過輸出檢查（格式或語言
  不一致），結果未被採用；可直接重新分析」。貢獻建議的訊息本來就是通用說法，不用改。
- 不套用在 `LocalizedSuggestion` 本身。它也承載 owner 輸入的個人資料與專案草稿。

## B. 讓舊的分析快取作廢

- 分析的版本常數集中在 `onboarding.py:52-54`。`"validation-v1"` 卻在
  `batch_execution.py:56` 與 `batches.py:146` 各寫一次預設值。把它移到同一處，
  成為 `ANALYSIS_VALIDATION_VERSION`，兩處都引用。這樣快取鍵
  （`batch_execution.py:233`）和預檢快取預測（`batches.py:647`）一定一致。
- 本計畫改變了提示、輸出格式與驗證，所以三個版本都升級：
  `ANALYSIS_PROMPT_VERSION` → `onboarding-prompt-v3`、
  `ANALYSIS_OUTPUT_SCHEMA_VERSION` → `analysis-schema-v3`、
  `ANALYSIS_VALIDATION_VERSION` → `validation-v2`。
- 舊項目在讀取時會因版本不同而被刪除（`batch_execution.py:113`），
  剩下的由既有的 24 小時 TTL 與定期 `cleanup_expired` 清除。
- **不新增快取清理機制。** 版本鍵、讀取時刪除、TTL 三者已涵蓋。
- 影響：下次分析這兩個 repo 會重新呼叫模型（每個 repo 至少一次生成）。

## C. 套用舊草稿修復

只改這一份本機資料，不改程式、不加遷移程式。只有 09-28 之前建立的草稿缺這一欄，
新草稿在引導流程一定會填（FR-045）。也不從 repo 內容自動推斷帳號
（AGENTS.md：不可從 repo 內容推斷個人歸屬）。

步驟：

1. 確認 `runtime-data/local/local-portfolio/draft.json` 的 SHA256 仍是
   `f8915a4748d6d75429f9fd56348c12c965bfab3ab275fa7fbb97c6985a6d6f32`
   （2026-10-14 已確認未變）。不符就停止並回報。
2. 停止啟動器管理的伺服器，避免同時寫入。
3. 以 `LocalPortfolioStore.restore_raw_locked` 寫入
   `runtime-data/readme-flow-20261012/recovery/candidate-draft.json`，它會先跑
   完整的 `_decode_draft` 驗證再原子替換。
   候選稿 SHA256：`16bbb39e4bb6ceb7c50cb084998d46805a01ef4bbf4be4a65453e35b083d78f7`；
   唯一差異是加入 `profile.github_login: xu-0306` 並重算 revision。
4. 驗證：檔案 SHA256 等於候選稿、`read()` 成功；保留 `original-draft.json` 作為備份。
5. 用啟動器重啟，確認 `GET /api/admin/portfolio` 與 `/portfolio/status` 不再回 422。

修復後草稿 revision 改變，會顯示為尚未套用的變更。README 匯出仍需要 owner
套用草稿，以及提供並驗證 Pages 網址，這兩項不在本計畫內。

## D. 快取與即時結果使用同一份出處資料

新介面只顯示出處連結，不顯示原文摘錄（見 E2），所以 API 也不再回傳摘錄。
這讓快取和即時結果的出處形狀完全一樣，不需要「快取時摘錄為空」的特例。

- `_fact_payload`（`onboarding.py:1170`）改為只回傳 `evidence_id`、
  `evidence_class`、`path`、`start_line`、`end_line`、`url`。刪除 `excerpt`
  與 `title`。`url` 是後端組出的 GitHub 永久連結（`github_permalink`），
  不是 repo 內容。
- `_cacheable_result` 一併保存 `facts`，形狀與上面相同。快取仍不存任何 repo 原文。
- `_parse_cached_payload` 驗證 `facts`：數量上限、`EVIDENCE_ID_RE`、
  `evidence_class == "REPOSITORY_FACT"`、路徑長度、行號為正整數或 null、
  `url` 必須以 `https://github.com/{slug}/blob/{commit_sha}/` 開頭，
  且 key 集合完全相符。任何一筆不符就整筆快取作廢。
- `_cached_result` 直接回傳快取裡的 `facts`，刪除 `facts: []` 的特例與其註解。
- 前端：`RepositoryFact` 刪除 `excerpt`、新增 `url`；`repositoryFact` 解析器
  同步修改，並只接受 `https://github.com/` 開頭的網址。

## E. 「AI 推論」區塊改版（依範本「改版後」）

### E1. 資料：每條推論加短標題

- `AnalysisInference` 新增 `title`（zh-TW 與 en）。提示要求 zh-TW 不超過 16 字、
  en 不超過 8 個英文字；驗證上限放寬為 zh-TW 24 字、en 80 字元，
  避免為了幾個字就整批拒絕。
- 回應 schema（`_analysis_response_schema`）與提示範例（`_analysis_messages`）
  加入 `title`。
- `title` 與 `statement` 一樣要通過個人歸因檢查（`_contains_personal_inference`）
  與 A 的文字系統檢查。
- 快取的推論驗證（`_valid_cached_inference`）接受並檢查 `title`。
- API 的每條推論多一個 `title`；前端 `ModelInference` 同步新增並驗證。
- 由 B 的版本升級讓舊快取失效。

### E2. 畫面

只改 `GuidedOnboardingView.tsx`、`styles.css` 與相關測試，流程不變。

- **專案列：** repo 名稱加小標籤（語言、星數、短 commit）。語言與星數來自探索步驟
  已取得的資料；沒有就不顯示。
- **標題與說明：** 「專案重點」/“Highlights”，下方只有一行淡色小字
  「AI 整理，僅供你參考」/“AI summary, for your reference”。旁邊的 ⓘ 按鈕開啟
  小提示「不會公開，也不會自動寫進作品集。」/“Never public, never added to your
  portfolio automatically.”，用 F 的 React Aria `DialogTrigger` + `Popover` 實作。
- **重點清單：** 每條推論一列，顯示短標題，右側是第一個出處的連結標籤
  （檔名 ↗，在新分頁開 GitHub 永久連結）。有多個出處時加淡色「+n」。
  點標題（`button` + `aria-expanded`）展開，只顯示完整句子與所有出處連結。
  窄螢幕時連結標籤移到標題下方，不擠壓標題。
- **下一步：** 區塊結尾放既有的「下一步：描述我的貢獻」主按鈕與「重新分析」次要
  按鈕。移動既有動作的位置，不新增動作。
- **刪除：** 「AI 整理・尚未確認」徽章、每張卡重複的安全聲明、原始摘錄 `<pre>`、
  「技術識別資訊」（證據 ID）、未被引用出處的「其他可核對的專案內容」區塊、
  長句超過 240 字才出現的「閱讀完整解讀」，以及依據區的淡紫底色與巢狀外框。
- 樣式：中性色，只用既有 `--admin-primary` 一個強調色，圓角不超過 8px，
  不再有框中有框。支援 `prefers-reduced-motion`，中英內容一致。
- 規格中 2026-10-07 owner 核准的分析呈現方式（`TECHNICAL_SPEC.md` 約第 1128 行、
  `ACCEPTANCE_CRITERIA.md` 第 436 行）由本項取代，兩處一併改寫。

## F. 導入 React Aria Components（只用在管理介面）

Owner 於 2026-10-14 同意採用。原則：只替換「手寫、且有實際缺點」的互動元件，
以及 E2 新增的 ⓘ 提示。已經可用的原生元素不為了一致而全面改寫。

現況盤點（管理介面，非測試檔）：

| 元件 | 數量 | 處理 |
|---|---|---|
| `window.confirm` 確認框 | 5 處（`AdminPage.tsx:2839`、`DeleteSettingButton.tsx:30`、`EmbeddingProfilePanel.tsx:468/511/522`） | **替換。** 原生確認框的按鈕文字跟著瀏覽器語言，不跟介面語言，違反中英一致；也無法套用樣式。改用一個共用的 `ConfirmDialog`（RAC `Modal` + `Dialog`，role `alertdialog`）：標題一句、說明一句、「取消」預設取得焦點、破壞性按鈕用警示色。 |
| 顯示設定彈出面板（`AdminWorkspace.tsx:420`，`<details>` + 手寫 Escape 關閉與焦點回復） | 1 | **替換**為 RAC `DialogTrigger` + `Popover`，刪除手寫的鍵盤處理。 |
| E2 的 ⓘ 提示 | 新增 1 | RAC `DialogTrigger` + `Popover`。 |
| `<details>` 展開區 | 34 | 保留。原生元素已支援鍵盤與輔助技術。 |
| `<select>` | 14 | 保留。之後若有樣式需求再個別評估。 |
| 語言切換（`aria-pressed` 按鈕組） | 1 | 保留。目前寫法正確。 |
| 場景焦點方向鍵（`ScenePreview.tsx:427`） | 1 | 保留。這是專用的拖曳／微調行為，不是通用元件。 |

範圍與限制：

- 新增相依 `react-aria-components`，實作時鎖定當下穩定版的確切版本（repo
  慣例），並確認支援 React 19.1。由 pnpm 安裝（ADR-012）。
- 管理介面是 lazy-load 的獨立 chunk（`App.tsx:14`），訪客頁是另一個入口
  （`visitor.html`）。以 `check_visitor_source.mjs` 與建置後的 manifest 確認
  訪客 bundle 不含此套件。
- 授權：Apache-2.0。更新 Windows 安裝包的第三方授權清單
  （參照 `WINDOWS_LICENSE_REVIEW_2026-10-03.md` 的收集流程）。
- 樣式沿用 `styles.css` 的既有 CSS 變數，不引入 Tailwind 或其他樣式框架。
- 測試：目前 vitest 環境是 `node`，以字串渲染測試為主。確認框以「開啟狀態
  的渲染結果」與「確認／取消呼叫正確回呼」驗證。真實焦點行為以瀏覽器實測，
  不為此新增 jsdom 等測試相依（除非 owner 另行同意）。

## G. 之後另一輪：引導流程其他步驟減字（不在本輪）

Owner 同意另外安排。等 A–F 完成後進行，避免同時修改相同檔案。

- 範圍：連接模型、探索與選取專案、批次分析、描述貢獻、檢視、預覽與分享。
- 規則沿用 E2：每段最多一句說明；次要資訊收進 ⓘ；用標籤、圖示、數字取代句子；
  每個畫面一個主要動作；不框中有框。
- 做法：先為每個步驟做「改版前／改版後」範本給 owner 看，核准後才實作。

## 待決定（不在本計畫內）

- **讓推論真的被使用：** 在「描述貢獻」步驟可帶入某條推論當起點，或讓貢獻建議的
  模型也參考推論，仍需 owner 確認才進草稿。這會改變貢獻建議的輸入與信任規則，
  屬於規格變更。若決定不做，應評估分析步驟的模型成本與耗時是否值得只換來參考用的文字。

## 不做的事

- 貢獻建議逾時（180 秒）：先量測 `gpt-6.1-sol` 實際回應時間再決定。
- 無原因的 502 `PROVIDER_ERROR` 補安全原因：需要另一個契約變更。
- 快取管理介面或手動清除按鈕：等到真的需要在不改程式碼的情況下強制重新分析時再加。
- 語言辨識或 confusable 偵測：這次觀察到的問題只需要文字系統集合比對。

## 測試

後端（`tests/unit/test_guided_onboarding.py`、`tests/unit/test_batch_execution.py`、
`tests/integration/test_analysis_cache_reuse.py` 與相關 API 契約測試）：

- 文字系統：中文句子夾俄文詞被拒；原始資料含俄文時放行；英文句子引用中文檔名放行；
  `μs`、`λ`、全形英數、`々`、emoji、程式識別字（`snake_case`、`getUserID`）放行；
  日文假名、韓文詞在原始資料沒有時被拒。zh-TW 與 en 欄位、`title` 與 `statement`
  分別驗證。
- 貢獻建議：角色、摘要、claim 任一欄違規都拒絕；owner 說明含俄文時放行。
- 錯誤：原因為 `PROVIDER_OUTPUT_SCHEMA_INVALID`，結果不寫入快取。
- 短標題：缺少、超過上限、含個人歸因時拒絕；提示與回應 schema 含 `title`。
- 出處：即時結果不含 `excerpt`/`title`，含 `url`；快取命中回傳相同形狀與數量的
  facts；facts 竄改、缺漏、多出 key、網址不屬於該 repo/commit 時整筆快取作廢。
- 版本：舊版本快取項目不命中並被刪除；快取鍵與預檢預測使用同一組版本常數。

前端：

- `batchAnalysisResult` 要求 `title` 與 `url`，拒絕非 GitHub 網址。
- E2：雙語文案、短標題列、展開只顯示完整句子與出處、「+n」、
  不再出現徽章／安全聲明／摘錄／證據 ID／其他可核對內容、下一步按鈕位置。
- ⓘ 提示與 `ConfirmDialog`：開啟狀態渲染、雙語、確認與取消呼叫正確回呼。
- `BatchAnalysisPanel` 新訊息的雙語內容。

驗證指令：Ruff format/check、mypy、相關 pytest；前端 format、lint、typecheck、
完整 vitest、build；訪客 bundle 檢查；`git diff --check`。C 項另以 SHA256
與 API 狀態碼驗證。

最後用瀏覽器實測：

- 確認框、顯示設定面板、ⓘ 提示的鍵盤操作（Tab、Esc、焦點回到觸發按鈕）。
- 重新分析兩個 repo（會實際呼叫模型），確認文字與出處正常。
- E2 畫面的中英文與窄螢幕。

## 文件更新

- `docs/TECHNICAL_SPEC.md`：版本 0.4.12、開頭註記；分析／貢獻輸出驗證段落
  （約第 544、1116、1147 行）；分析結果的推論 `title` 與 facts 形狀；
  2026-10-07 分析呈現段落（約第 1128 行）；快取 payload 內容（約第 1591 行）。
- `docs/ACCEPTANCE_CRITERIA.md`：改寫第 436 行的呈現說明；新增 AC-080，涵蓋
  無根據的外來文字系統被拒、有根據的放行、快取命中與即時結果出處一致。
- `docs/DECISIONS.md`：ADR-060（A–E）、ADR-061（F）。
- `docs/OWNER_REVIEW.md`（本機、git 忽略）：OR-034、OR-035。

## 執行順序

1. A + B + E1（後端：文字系統檢查、短標題、版本常數）與測試。
2. D（後端與前端的出處形狀）與測試。
3. F（相依、`ConfirmDialog`、顯示設定面板、授權清單、訪客 bundle 檢查）。
4. E2（畫面；用到 F 的 Popover）。
5. 文件更新。
6. 完整驗證。
7. C：停止伺服器、套用、驗證、重啟。
8. 瀏覽器實測。

不 commit、不 push，除非 owner 另外要求。

## 實作進度與交接（2026-10-14）

Owner 已於 2026-10-14 核准 A–F；本節記錄工作樹實際存在的 Job 1–3，不把未實作的計畫內容寫成完成。

### Job 1 — A、B、E1 後端輸出與快取

- `src/reponpc/admin/onboarding.py` 已加入 NFKC 後的 writing-system 判斷、`title` 結構、analysis/contribution source-grounding 檢查，以及 `ANALYSIS_VALIDATION_VERSION = "validation-v2"`；analysis prompt/schema 已升為 v3。
- `src/reponpc/admin/batch_execution.py` 與 `src/reponpc/admin/batches.py` 已共用 validation version；analysis cache 會保存經驗證的 facts 與 inference，並拒絕舊形狀、excerpt、錯誤 repo/commit URL 或不合規 title。
- 相關 unit/integration 測試已補上拒絕未落地 writing-system、接受來源中出現的文字系統、title 邊界、無 retry，以及 live/cache source 形狀。

### Job 2 — D、E2、F 前端與依賴

- `guidedOnboarding.ts`、`AdminPage.tsx` 與 `GuidedOnboardingView.tsx` 已改用 `url` facts、localized inference `title`，並呈現 repository 語言/短 commit、Highlights 摺疊列、GitHub 來源連結、隱私 popover，以及「描述我的貢獻」和「重新分析」動作。未被 inference 引用的 facts 目前沒有獨立顯示。
- `ConfirmDialog.tsx` 已取代現有 admin `window.confirm`；`AdminWorkspace` 的顯示設定與 Highlights 隱私說明使用 React Aria `DialogTrigger`/`Popover`。`react-aria-components@1.21.1` 及 `client-only` Windows license supplement/source hash 已存在。
- 前端與 backend assertion fixtures 已改成 title/URL 形狀；仍有未隨本輪更新的瀏覽器 fixture/script 使用舊 `excerpt` 形狀，且完整 browser/accessibility/build 驗證尚未形成證據。

### Job 3 — 文件

- `TECHNICAL_SPEC.md` 已升至 0.4.12，補上 A–F 實際契約、AC-080 對應、快取 payload 與 owner note。
- `ACCEPTANCE_CRITERIA.md` 已改寫 2026-10-07 presentation note 並新增 AC-080。
- `DECISIONS.md` 已加入 ADR-060（A–E）與 ADR-061（F）；本機 `OWNER_REVIEW.md` 已加入 OR-034/OR-035。

### 主代理審查與後續（2026-10-15 更新，取代 Job 3 寫的「尚未完成」段）

- **審查修正：** 補回缺失來源提示（展開後一行淡色字，雙語，含測試）；規格恢復被誤刪的「in a draft」；ADR-061/OR-035 改正 client-only 授權出處說明（發布前需 owner 審查）；AC-080 對應改為 FR-008/022/027/028、NFR-001；兩處 Codex 新增的 `aria-haspopup` 斷言改為 RAC 實際輸出的 `aria-expanded`；`tests/browser` 的 analysis fixture、檢查腳本與 README 已改為新介面（腳本未在其 Chrome runtime 實際執行）。
- **驗證：** 前端 format/typecheck/lint（0 error、20 warning）/581 tests/build 通過，訪客 bundle 不含 react-aria。Python 完整測試 2737 passed、2 skipped、2 failed；兩個失敗都是 Docker smoke，原因是既有問題：Dockerfile 的 web-build 階段沒有複製 `docs/`，但 `PagesSharePanel.tsx` 匯入 `docs/PAGES_SHARING_GUIDE.md`（與本計畫無關，另案處理）。
- **C 已完成（2026-10-15）：** 草稿 SHA256 `f8915a47…` → `16bbb39e…`，經 `restore_raw_locked` 寫入；原檔保留於 recovery/original-draft.json；`GET /api/admin/portfolio` 與 `/status` 皆回 200。
- **未完成：** 真實瀏覽器實測與 UI/UX 檢討（owner 指定由 Sonnet 5.5 執行）。交接時伺服器未運行；重啟前先問 owner。測試必須在新分頁進行（sessionStorage 每分頁獨立），不得重設 owner 原分頁的草稿；只授權一次兩個 repo 的批次分析。已存截圖：output/playwright/ui-e-f-20261014/01、02。
- **已發現 UI/UX 問題：** （高，既有）「重新開始」後模型步驟卡住：RESET 清掉 `modelsConfigured`，只在載入頁面時重讀，而「確認用於分析」因已確認而停用，需重新整理才能繼續；（中）模型步驟文字過多，狀態寫「可開始分析」但按鈕提示要先測試確認；（低）ⓘ 的 aria-label 與可見文字重複；Ollama 安裝／刪除共用同一段確認文字；分析步驟開頭說明仍偏長（G）。

## 複雜度帳

- 參考：UTS #39 mixed-script 偵測 = 「字元 → 文字系統」＋「集合比對」，
  本計畫只取這兩個概念。
- 對應既有機制：用既有的錯誤原因、既有的快取版本鍵與 payload 驗證、
  既有的「下一步」與「重新分析」動作。
- 概念：+1 文字系統一致性檢查（含每個語言的基本文字系統表）；+1 推論 `title`
  欄位；F +1 相依（React Aria）與 +1 共用元件（`ConfirmDialog`）。
  -1 重複的 validation-version 預設值。
- 刪除：facts 的 `excerpt`/`title` 欄位與快取的 `facts: []` 特例；5 處
  `window.confirm`；顯示設定面板的手寫鍵盤處理；E2 列出的徽章、重複聲明、
  摘錄、證據 ID、其他可核對內容區塊、「閱讀完整解讀」與巢狀外框。
- 根本層：口誤發生在模型輸出，`_parse_analysis` 是信任邊界，屬於 boundary，
  在原地補強。「0 個來源」發生在快取這個衍生層，修法是讓快取與即時結果
  使用同一份出處形狀。快取本身有量測依據（AC-078），所以保留。

### 下一輪（2026-10-15）

Owner 已確認下一輪的順序：先做 UI 小修與 Dockerfile 修復，再做瀏覽器實測，最後分三批 commit，不 push。
這一輪交給其他 agent，完整交接見 `docs/NEXT_ROUND_HANDOFF_2026-10-15.md`。

## 本輪續作結果（2026-10-15，取代上方未完成狀態）

- Owner 已明確要求開始依序實作、同意由目前 Codex 取代 Sonnet 5.5 做相同真實瀏覽器檢查，並同意重啟。模型資料與目的地另獲明確授權後，只執行一次兩個 repo 的分析。
- UI 1a–1d 完成。除 RESET 保留模型狀態外，實測重現首次登入載入草稿覆寫就緒狀態；內部 RESTORE_DRAFT action 統一三個還原入口，保留伺服器狀態。回歸測試涵蓋 ready/unready 與兩種回應順序。
- 最終 `pnpm run web:check` 完整通過：587 tests，lint 0 error/20 warnings（基準不變），typecheck/build/visitor guard 通過；使用 repo 內 UV_CACHE_DIR。
- Dockerfile 只複製 PAGES_SHARING_GUIDE.md 到 web-build；最終兩項 Docker smoke 2 passed（70.73 秒），`docker build --tag reponpc:ci .` 通過。先前 sandbox/pytest 暫存權限失敗已以 sandbox 外執行和新的測試暫存目錄解決，未改測試門檻。
- 真實分析 2/2 成功、58 秒、每 repo 生成一次、無 retry。12 條 Highlights 的中英文與 1440/375px 檢查、+n、pinned GitHub 連結、隱私/顯示設定鍵盤與焦點、確認框取消通過。顯示互動 0 額外 POST。
- 結果截圖後只在測試分頁確認 RESET；中英文下一步可用且能進專案選擇，0 POST。原草稿 SHA256 前後皆為 16bbb39e4bb6ceb7c50cb084998d46805a01ef4bbf4be4a65453e35b083d78f7。已經 UI 登出（readonly revocation boolean 補確認）並只關閉自己的 session；服務保留運行。
- 截圖接續 03–37。完整驗證、限制與依嚴重度排序的問題清單：`output/playwright/ui-e-f-20261014/REVIEW_2026-10-15.md`；機器結果為同目錄 browser-checks.json / reset-checks.json。
- Owner 已確認完整 commit 清單，授權三個本機 commit、不 push。三批保留：A–F 與文件、UI 小修、Dockerfile；6 個重疊檔案有修改前快照，可只在 index 分開原有 A–F 與本輪改動，無須回寫或覆蓋工作樹。提交依 owner 確認的清單執行；GitHub push 不在本輪授權內。
- 後續候選（不擴入本輪）：完成後過長的批次診斷（手機結果起點 4557px）、英文長模型名稱擠壓狀態徽章、分析前「已連線：尚未設定」文案、CSP inline-style console error 的來源定位。未放寬 CSP。G 與 client-only 授權出處審查仍另行安排。
- 未重跑完整 Python 套件、未宣稱完整 browser/screen-reader/200% zoom/public release；實際結果未觸發缺漏來源提示，該提示由既有雙語 unit tests 驗證。

## 主代理審核與中等問題修正（2026-10-15，未 commit）

- 審核三個 commit（a7144a0、96da18a、50cf6d5）：範圍、斷言與驗證說法成立。重跑 `pnpm run web:check`，587 項測試通過；後端相關 5 個測試檔 124 passed，ruff format、ruff check、mypy 通過。後端測試第一次出現 63 個 setup 錯誤，原因是 pytest 預設暫存目錄 `C:\Users\xu\AppData\Local\Temp\pytest-of-xu` 無權限讀取，屬於環境問題；改用 `--basetemp` 後全部通過。
- 修正一：`PROVIDER_ERROR` 訊息刪掉「不是本機服務問題」。這個代碼也涵蓋本機 Ollama 錯誤，以及前端未知例外的預設值，所以這句沒有根據。測試新增雙語否定斷言。
- 修正二：React Aria 在執行時插入的 `<style>` 被 CSP `style-src 'self'` 擋下。pressable 的 `touch-action` 規則改寫在 `styles.css`；CSP 不變。ADR-061 已加註兩項殘留：每次載入 admin 頁面有一則 console CSP 訊息；iOS Safari 開啟確認框時沒有 overscroll 限制。要改變這兩項，都需要 owner 核准的 CSP 契約變更。
- 由 Codex gpt-6.1-sol high 實作，驗證由 Haiku 5.5 在 sandbox 外執行：web:check 通過（587 tests，lint 0 error，build 正常），build 後的 CSS 含該規則，`git diff --check` 通過，換行格式不變。未做瀏覽器或 iOS 實測。
- 低優先後續（未做）：草稿序列化仍保存 `modelsConfigured`，但還原時已不採用；重點展開後來源顯示兩次（G 輪）。

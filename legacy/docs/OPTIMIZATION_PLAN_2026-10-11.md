# 優化計劃 — 2026-10-11

狀態：第 1 批的焦點／返回位置缺陷已補修，第 2、3 批與本次授權的分享頁階段重排已完成；雙語桌機／手機瀏覽器回歸通過。實際結果與限制見最後的「UX 接續完成紀錄」。真實模型目錄、公開部署及正式發布驗收仍未完成。本文件不改變規格、驗收門檻或任何 API／設定契約。

來源：

- 2026-10-06 中文零結果檢索修正的 anti-hardcode 審查（本次會話）。
- Codex 走查報告 `output/playwright/ux-20261011/UX_REVIEW.zh-TW.html` 與 `observations.json`。
- 本次獨立複核：全新資料目錄啟動 `reponpc.windows_launcher`（loopback，port 18790，`.test-tmp/ux-claude-20261011-clean`），用內建瀏覽器以 800×600、1024×768 與 390×844 走過歡迎頁、AI 設定和預覽與分享頁，並逐條對照原始碼。沒有呼叫模型、沒有讀取 GitHub、沒有修改程式。測試服務已停止，port 已關閉。

---

## 第一部分：檢索零結果補救的啟動條件

### 問題

`src/reponpc/retrieval/fts_query.py` 的 `_compile_fallback_fragments` 規定：問題中只要出現任何一個 ASCII 英數字，就完全不產生補救片段。實測：

| 問題 | 補救片段數 |
|---|---|
| 請比較這三個專案的架構與資料儲存方式 | 32 |
| 請比較live-subtitle和framefit的架構與資料儲存方式 | 0 |
| 比較 RepoNPC 的架構與資料儲存方式 | 0 |
| 這3個專案的架構與資料儲存方式 | 0 |

作品集訪客很常直接打英文的 repo 名稱或數字。這幾種寫法意思相同，卻得不到補救，所以目前的修正只對純中文的原題有效。現有測試只涵蓋「中文加路徑」這種不該放寬的情況，沒有涵蓋「中文加名稱」。

### 要守住的規則

1. 精確搜尋結果為 0 時，問題裡任何連續的非 ASCII 段落，不論旁邊有沒有 ASCII 字，都要能用片段補救。
2. 路徑形式的 ASCII 詞（含 `/`，或像 `name.ext` 的檔名）仍然是必要條件，補救不得放寬。`請說明繁體中文 src/not-present.py` 必須維持 0 筆。
3. 不新增設定、資料表、API 欄位或語言、詞彙清單。上限沿用 `MAX_FTS_TERMS`。

### 做法（建議）

只動 `fts_query.py` 與 `index_reader.py` 現有的補救函式，不新增層級：

1. **逐段判斷**：在 `_compile_fallback_fragments` 移除整句 ASCII 判斷，改成只對非 ASCII 段落產生 2 字和 3 字片段。這部分沿用現有的 `_non_ascii_spans`。
2. **ASCII 詞分兩類**：判斷只看結構（是否含路徑分隔符號或副檔名形式的點），不看詞的內容：
   - 路徑形式：當作必要條件，補救候選必須同時符合這些詞的 FTS 比對。
   - 其他 ASCII 詞（例如 repo 名稱）且長度 ≥ 2：各自當作一個獨立排名，加入現有的 RRF 合併，但不是必要條件。這樣問兩個 repo 時，不會要求同一段證據同時包含兩個名稱。
3. **錄取規則不變**：仍需至少兩個獨立命中（2 個 trigram，或兩個不重疊的雙字片段）。ASCII 詞的命中可以算其中一個。
4. 這些片段資料仍由程式產生、透過參數綁定送進 SQL；問題本身的 FTS 語法永遠不會被執行。

### 測試（必須能擋住「只寫死某個例子」的修法）

- 中文加 repo 名稱（無空格和有空格兩種）：能補救，並且能找到含該名稱或中文片段的證據。
- 中文加數字：能補救。
- 中文加不存在的路徑：維持 0 筆。
- 中文加存在的路徑：候選只限於該路徑。
- 兩個 repo 名稱加中文：不要求同一段證據同時包含兩者。
- 只命中一個片段的誘餌資料：仍不錄取。
- 用一組沒出現在任何現有測試、也不是擁有者原題的人造問題做回歸。
- 保留現有 82 項檢索測試與 22 項索引／基準契約檢查。

### 效能

雙字片段目前用 `instr` 全表掃描，最多 16 次。實作前後在較大的合成索引上量測延遲。只有量測顯示這是瓶頸時，才另外提案（例如雙字索引）。本計劃不預先加索引。

### 不在這項範圍內

候選集中在 live-subtitle、其他 repo 進不了前 8 名，是「先全域截斷，再套每個 repo 上限」造成的範圍問題，和中文怎麼切詞無關。要確保每個 repo 都有候選，需要依 repo 分組召回或讓訪客明確選擇比較對象（先前的 B 方案）。B 方案會改 API 和介面，需要擁有者決定，本項不處理。

對應：FR-005／007／022，AC-007／008／013／023。不提升任何驗收狀態。正式 Recall@8 仍須另外重跑。

---

## 第二部分：Codex UX 報告複核

### 總評

報告的證據邊界寫得誠實：清楚區分全新環境、預建合成環境和下載站，沒有把合成回覆當成模型品質，也沒有宣稱任何驗收通過。7 項我都確認成立。我補充了適用範圍的修正，另外新增 3 項。

| 編號 | Codex 等級 | 複核結果 | 補充 |
|---|---|---|---|
| UX-01 缺少前往模型設定的直達入口 | 高 | 成立 | `LocalPublishingWorkspace.tsx:433-438` 停用原因旁沒有任何連結。上方進度條（`nav.onboarding-stepper`）和工作區狀態卡都沒有可點元素，唯一的路就是一路按「返回」。 |
| UX-02 沒有可直接採用的起始模型 | 高 | 成立，但要拆成兩件事 | `model_catalog.yml` 是刻意留空的。介面文案可以先改；目錄內容需要真實模型證據和擁有者授權，不能用文案假裝有推薦。 |
| UX-03 分享頁混合多個階段和技術詞 | 高 | 成立 | 全新狀態下，外觀、FAQ、Gateway、Pages、GitHub 全部同時出現，即使前置條件都沒完成。畫面上確實出現「A1 設定」「Listener」「Visitor Gateway」，Gateway 和 Pages 區塊各有一個「GitHub Pages 網址」。 |
| UX-04 首屏被導覽和狀態占滿 | 中 | 成立，需要補充 | 切換步驟時頁面會自動捲到步驟標題，所以操作中途沒有 Codex 量到的那麼糟。但重新整理或首次載入時，390 px 手機上步驟標題在 y≈1525，裝置檢查按鈕在 y≈1936，大約是兩個螢幕以下。狀態卡每張把「尚未設定」重複 3 次，而且不能點。 |
| UX-05 手動路線顯示 AI 字樣 | 中 | 成立 | 手動輸入（`BEGIN_MANUAL_CONTRIBUTION`）會建立一個空的 `proposal`，所以顯示「AI 建議（尚未確認）」標題。「確認選取並繼續分析」對手動路線也不正確。 |
| UX-06 使用說明連到不存在的位置 | 中 | 成立，範圍比報告大 | `AdminWorkspace.tsx:439-447` 只對 advanced 和 character 指定目標，其他模式都退回 `#guided-onboarding-heading`。所以「預覽與分享」和「維護」兩個模式都會失效。實測目標不存在（1024×768）。 |
| UX-07 README 主入口以開發者流程為主 | 中 | 成立 | README 第 3 行寫「45s 公開聊天期限維持」，但 `environment.py:932` 與 `.env.example:67` 的預設已經是 180 秒、上限 300 秒。 |

### 本次新增

| 編號 | 等級 | 問題 | 證據 |
|---|---|---|---|
| N-1 | 低 | 預覽與分享頁在狀態還沒載入完時，顯示「目前無法確認本機發布狀態；請稍後重新檢查」。 | `LocalPublishingWorkspace.tsx:321-324` 把載入中（`status === null`）和讀取失敗當成同一種狀態。實際 API 回 200、狀態是 idle。 |
| N-2 | 低 | 進度數字不一致：狀態卡寫「已完成 0/6」，步驟區卻寫「引導設定進度: 1/6」和「目前第 1 步，共 6 步」。 | 390×844 實測畫面。 |
| N-3 | 低 | 狀態卡同一個狀態重複 3 次（標題、說明、標籤），在手機上占了大量高度。 | 會併入 UX-04 一起處理。 |

---

## 第三部分：執行順序

依「不改契約、風險最小、最能減少迷路」排序。每一批都附上測試，並跑相關的前端格式、lint、型別檢查、單元測試和建置；有 UI 變更時，也要跑雙語瀏覽器與鍵盤檢查。

### 第 1 批：小修正，不需擁有者決定

1. **檢索補救逐段判斷**（第一部分）。
2. **UX-06**：每個工作區模式都連到該頁存在的說明標題。用測試列舉所有模式，確認每個目標都存在，避免以後新增模式又漏掉。
3. **UX-05**：前端狀態記錄貢獻的來源（手動或模型建議），標題和按鈕依來源顯示。手動路線改成「手動填寫的貢獻」「確認專案並填寫貢獻」。確認和編輯的邊界不變。
4. **N-1**：區分載入中和讀取失敗兩種狀態。
5. **UX-01**：在停用原因旁加上「前往設定模型」，切到引導設定的 AI 模型步驟，並說明草稿會保留。完成後提供回到「準備 NPC」的入口。測試要確認來回切換後草稿沒有遺失。

### 第 2 批：文件與文案

6. **UX-07**：README 改成一般使用者路徑優先，開發和歷史進度移到後面。修正 45 秒的舊說法，不把候選安裝包寫成已通過驗收。
7. **UX-02 的文案部分**：模型目錄空白時，直接說明需要自己準備回答服務、手動路線能做到哪一步。不新增任何「推薦」項目。
8. **UX-03 的用詞部分**：「A1 設定」「Listener」改成白話。兩個「GitHub Pages 網址」欄位要寫清楚各自代表什麼（網域和完整網址）。連到現有的 `docs/PAGES_SHARING_GUIDE.md`。

### 第 3 批：版面

9. **UX-04、N-2、N-3**：縮小頁首，狀態卡收合成一行摘要。目前步驟的標題和主要操作要出現在首屏。進度數字統一一種算法。鍵盤操作和螢幕閱讀器標籤保持不變。

### 需要擁有者決定後才做

10. **UX-03 分階段重排**：原計劃待擁有者決定；本次使用者要求「按你建議的順序修正這些 UX 問題」，已授權這項介面重排。完成「本機準備 → 訪客連線 → 上傳與核對網站 → 分享卡片」，外觀和 FAQ 標成選填。兩個 Pages 欄位繼續各自輸入與驗證；合併欄位／推導來源仍未授權，也未實作。
11. **UX-02 的模型目錄**：需要擁有者授權用真實模型跑資格測試並記錄證據，才能加入目錄。
12. **跨 repo 檢索範圍**（先前的 B 方案）：會改 API 和介面，需要擁有者決定。

### 不在本計劃內

真實模型完整主線、GitHub Pages／Funnel 公開上線、乾淨 Windows 安裝、200% 縮放與螢幕閱讀器、Man 角色權利。這些都還在既有交接文件中列為未完成，本計劃不改變它們的狀態。


## 第 1 批實作紀錄（2026-10-11）

五項程式修正已實作，未變更 API、設定、資料庫或資產契約，未提升正式驗收狀態。

- 檢索：連續非 ASCII 段落可與 repo 名稱／數字共存；ASCII 名稱為獨立 RRF 排名，路徑為必要 FTS 條件，且在每個排名截斷前套用。保留兩個獨立命中門檻；一個 ASCII 與一個中文片段可構成兩個命中，單一片段不錄取。所有值均參數綁定，所有補救通道共用 MAX_FTS_TERMS 預算。
- UX-06：guided、advanced、character、publish、maintenance 均有各自的現存標題；維護標題改用穩定 ID。
- UX-05：前端 proposalSource 區分手動與模型提案；手動按鈕／標題雙語修正，確認後仍保留來源，編輯已確認內容仍需再確認。不將來源或未確認提案寫入續接儲存。
- N-1：首次狀態回覆前顯示載入中，讀取失敗才顯示無法確認。
- UX-01：停用原因旁提供模型設定入口與草稿保留說明。既有引導 reducer 處理完成、返回與取消；保留 profile、repository、確認狀態及既有 AdminPage 草稿。臨時返回位置只在記憶體，序列化仍使用原本步驟與路線。

修改檔案：

- 後端：src/reponpc/retrieval/fts_query.py、src/reponpc/bundles/index_reader.py。
- 前端：AdminPage.tsx、AdminWorkspace.tsx、MaintenancePanel.tsx、LocalPublishingWorkspace.tsx、GuidedOnboardingView.tsx、guidedOnboarding.ts（皆位於 apps/web/src/features/admin）。
- 測試：tests/unit/test_fts_query.py、tests/integration/test_fts_query.py、tests/web/LocalPublishingWorkspace.test.tsx，以及 apps/web/src/features/admin 下的 AdminWorkspace.test.tsx、GuidedOnboardingView.test.tsx、guidedOnboarding.test.ts、LocalPublishingWorkspace.test.tsx。
- 文件：本計劃的狀態與實作紀錄。

對應既有需求：檢索 FR-005／007／022、AC-007／008／013／023；管理引導 FR-025／028／040／041、NFR-003／009、AC-040／057／058／060。本紀錄不表示這些完整 AC 已驗收。

### 自動檢查

- Python：tests/unit/test_fts_query.py、tests/integration/test_fts_query.py、tests/integration/test_retrieval_policy.py、tests/integration/test_index_build.py、tests/integration/test_phase2_benchmark.py 合計 **128 項通過**。包含原有檢索、索引與基準測試，以及新的混合語句、數字、兩個名稱、必要路徑、截斷前過濾、單片段誘餌與 FTS 注入形狀測試。
- 修改的 4 個 Python 檔案 Ruff lint／format 通過；2 個來源檔案 mypy 通過。
- 前端 Vitest **519 項通過**；額外執行 tests/web/LocalPublishingWorkspace.test.tsx **3 項通過**。
- 前端 Prettier、TypeScript 通過；ESLint 無錯誤，19 項 Fast Refresh 警告。
- build_scene_assets.py --check、check_visitor_source.mjs 與 Vite production build 通過。Vite 仍提示 scene-mode.js 非 module script 無法打包；建置退出碼為 0。
- git diff --check（涉及的來源與測試）通過。

本機找不到 pnpm 可執行檔，因此直接用已安裝的 Node 執行 apps/web/node_modules 中的 Prettier／ESLint／tsc／Vitest／Vite，以及原建置指令檔；未安裝依賴或更換 package manager。Python 使用 uv run --locked，快取指定為工作區 .uv-cache。

### 一萬筆合成索引量測

使用 SQLite 記憶體資料庫、現有 unicode61／trigram FTS 表、10,000 筆合成證據；每 100 筆一筆含 QuartzRepo 與中文片段，其餘為重複的無關英文資料。每查詢預熱一次、量測 7 次，limit=30。這是本機 lexical SQL 測量，不包含向量、模型、網路或正式 Recall@8。

| 查詢 | 修改前中位／最大 ms | 修改後中位／最大 ms | 修改前／後結果數 |
|---|---:|---:|---:|
| 請說明繁體中文架構與資料儲存方式 | 349.87／355.75 | 370.53／383.88 | 30／30 |
| 請說明QuartzRepo繁體中文架構與資料儲存方式 | 0.07／0.09 | 342.78／352.75 | 0／30 |
| 請說明QuartzRepo繁體中文 docs/not-present.py | 0.09／0.13 | 0.16／0.19 | 0／0 |

混合查詢現在實際執行補救，不能將修改前的零結果延遲當成有效搜尋的效能優勢。雙字全表掃描仍是可見成本；此批未新增索引，這組測量也不代表所有真實資料的延遲門檻已通過。可重跑腳本保留於 .tmp/optimization-batch1/benchmark.py（本機測量檔）。

### 尚未完成的驗證

瀏覽器安全檢查拒絕開啟隔離本機測試頁，回覆理由為該網址的存取權限遭拒；未以替代瀏覽器或底層控制繞過。測試伺服器已停止，暫存前端入口已移除。因此雙語真實瀏覽器、鍵盤焦點、延遲／失敗狀態切換與 AdminPage 完整往返仍待補驗證；狀態機與靜態呈現測試不能取代這些檢查。補跑需允許存取隔離本機測試頁，無其他產品決策待擁有者確認。

第 2、3 批、跨 repo B 方案、真實模型、公開部署與正式 Recall@8 均未執行。

---

## 第 1 批複核與瀏覽器驗證交接（2026-10-11，Claude）

因額度接近上限，本次停在 UX-01 往返的檢查段落。程式碼未修改；以下為複核結果與待辦。

### 已重跑

- Python 檢索相關 5 檔：**128 passed**（`uv --cache-dir .uv-cache run --locked --offline python -m pytest tests/unit/test_fts_query.py tests/integration/test_fts_query.py tests/integration/test_retrieval_policy.py tests/integration/test_index_build.py tests/integration/test_phase2_benchmark.py -q -p no:cacheprovider --basetemp=.pytest-tmp/claude-verify-20261011`）。
- 前端 Vitest：**45 檔／519 passed**。本機 shell 可直接使用 `pnpm`（Codex 環境找不到而已）。
- `pnpm --dir apps/web run build` 通過，`apps/web/dist` 為第 1 批版本。
- 後端程式審閱：逐段補救、ASCII 名稱獨立排名、路徑必要條件在每個排名截斷前套用，邏輯與計劃一致，所有值均參數綁定。

### 瀏覽器實測（內建瀏覽器；乾淨 launcher `127.0.0.1:18790`，資料目錄 `.test-tmp/claude-verify-20261011-clean`）

| 項目 | 結果 | 說明 |
|---|---|---|
| UX-06 使用說明 | 通過 | 5 種模式 × 中英文共 10 組，目標都存在；實際點擊後跳到 `#local-publication-heading`。 |
| N-1 載入／失敗文案 | 通過 | 延遲狀態 API 時顯示「正在讀取本機發布狀態…」，回應後改為「尚未準備本機 NPC。」；模擬 503 時顯示「目前無法確認本機發布狀態」。 |
| UX-01 入口與文案 | 通過 | 中文「前往設定模型」與草稿保留說明；英文「Set up models」與 “Your content draft is kept…”。 |
| UX-01 往返路線 | 通過 | Enter 後切到引導設定的「設定 AI 模型」；有「完成設定並返回準備 NPC」（未設定時停用，附 aria-describedby 原因）與「返回準備 NPC」，後者能切回預覽與分享。 |
| UX-01 鍵盤焦點 | **未通過** | 兩個方向切換後，`document.activeElement` 都是 `BODY`，鍵盤使用者失去位置（NFR-003）。 |
| UX-01 返回位置 | **未通過** | 按「返回準備 NPC」後 `scrollY=2506`，「準備 NPC 並套用」在視窗上方 1916 px 外，畫面停在 Gateway／Tailscale Funnel 區塊，沒有回到準備 NPC 的位置。 |
| 小問題 | 待確認 | 停用的「準備 NPC 並套用」沒有 `aria-describedby` 指向停用原因（可能是既有狀況）。 |

### 尚未驗證

- **UX-05 手動路線文字**：需要走到選擇專案和貢獻步驟。乾淨環境要讀取真實 GitHub；A5 fixture（`python -m tests.browser.a5_server --runtime <新目錄> --port 18791`，帳密見 `tests/browser/a5_server.py` 的 FIXTURE 常數）已能登入，但尚未走到該步驟。
- **UX-01 草稿保留**：乾淨環境沒有草稿可比對；A5 fixture 的模型已就緒，不會出現「前往設定模型」。需要一個「有草稿但模型未就緒」的環境（例如在 fixture 中清掉分析模型選擇，或在乾淨環境用手動路線先建立草稿）。
- 手機寬度（390 px）與 200% 縮放下的新按鈕版面。

### 下一步建議

1. 修 UX-01 的兩個缺陷：切換工作區後把焦點移到目標標題（引導設定用既有的 `#guided-onboarding-heading`；返回時聚焦並捲到「準備 NPC」區塊或其停用原因）。補對應的元件測試與瀏覽器檢查。
2. 補驗 UX-05 與草稿保留，再做第 2 批。
3. 效能提醒：Codex 的 1 萬筆合成量測顯示雙字 `instr` 全表掃描約 340–370 ms，純中文和混合問句都一樣。依計劃，在真實索引規模量測確認是瓶頸前，不先加索引，但這個數字已值得追蹤。

### 環境清理

兩個測試伺服器已停止，瀏覽器分頁已關閉。測試資料留在 `.test-tmp/claude-verify-20261011-{clean,ready}`，可安全刪除。

---

## UX 接續完成紀錄（2026-10-11，Codex）

本次從上述 Claude 交接續做。保留另一位 agent 的檢索與第 1 批實作；未改後端檢索、API、儲存格式、模型選用規則或發布驗收狀態。

### 已完成

- **UX-01**：在工作區共同邊界處理焦點與捲動。前往模型設定和返回準備 NPC 都聚焦目標標題並捲到頂端；停用的準備按鈕用 `aria-describedby` 關聯原因。返回、取消及手動草稿仍沿用既有 reducer。
- **草稿保留補修**：實測發現切換語言會重跑 AdminPage 的草稿載入，覆蓋未確認的個人資料。移除該載入 effect 對語言的依賴，錯誤訊息使用當前語言；雙向語言切換保留未確認姓名，草稿讀取 API 次數為 0。
- **UX-02**：模型目錄為空時明說尚無通過完整測試的推薦項目，需要自行準備回答服務；說明手動路線可填寫、預覽、儲存、備份，而準備 NPC 和聊天仍需要模型。裝置檢查只做容量估算，沒有加入虛構推薦或自動下載。
- **UX-03**：分享頁依本機準備、訪客連線、上傳／核對、分享卡片排列，提供四個跳轉入口；外觀與 FAQ 收入選填區。主要文案移除 A1／Listener；Pages 網域與含專案路徑的完整網址各有範例。管理頁提供現有雙語分享指南的同源下載。
- **UX-04、N-2、N-3**：縮小頁首；將次要導覽、模型說明、狀態卡改為可用鍵盤展開的區塊。狀態卡移到步驟內容後方；新增服務入口提前。進度與狀態卡共用同一個算法，明確區分「目前第幾步」與「已完成幾步」。首次載入、重整及步驟切換都把標題捲到頂端，避免焦點到了標題但操作仍在首屏外。
- **UX-05 補驗**：實際走過手動專案確認、編輯貢獻及再次確認。雙語皆顯示手動來源；未確認時不能前進。另修正已確認貢獻仍顯示「待確認／尚未進入 YAML」的矛盾文字。
- **UX-07**：README 以一般使用者的手動／AI／分享路徑開頭，開發與歷史紀錄移後；改為 180 秒預設、300 秒上限；清楚區分 Windows 候選安裝包與正式驗收。

需求對應：FR-025／028／040／041／047、NFR-003／009、AC-040／057／058／060／068 的相關管理介面行為；以上不是完整 AC 或正式 v1 驗收。

### 修改檔案

- `apps/web/src/features/admin/`：AdminPage、AdminWorkspace、AdminStatusCards、GuidedOnboardingView、OnboardingStepper、guidedOnboarding、LocalPublishingWorkspace、ModelSetupWorkspace、ModelConnectionPanel、ModelGuidancePanel、VisitorGatewayPanel、PagesSharePanel、GitHubShareGuide，以及對應元件測試。
- `apps/web/src/styles.css`、`tests/web/LocalPublishingWorkspace.test.tsx`。
- `tests/browser/check-admin-ux.js` 與 `tests/browser/README.md`：可重跑的真實瀏覽器回歸與前提。
- `README.md` 與本文件。既有未提交修改均保留；沒有提交、推送或公開部署。

### 實際瀏覽器證據

使用現有 `tests.browser.a5_server` 的隔離合成資料，正式前端 build 與真實 FastAPI／store；GitHub／模型 transport 為 fixture。站點 `127.0.0.1:18794`，資料目錄 `.test-tmp/ux-fix-20261011-ready`。本輪內建瀏覽器 runtime 在載入工具時發生 EPERM（尚未連線到測試頁），改用既有 Playwright CLI；不是網址安全檢查拒絕後的重試。

`check-admin-ux.js` **65 個檢查通過**，涵蓋繁中／英文 × 1024×768／390×844、Enter 導航、焦點與準備按鈕可見、草稿與手動進度保留、首次 AI 入口與重整、服務表單鍵盤開啟／取消後焦點返回、停用原因關聯、分享順序及無水平溢出。

以下是視窗內頂端座標（px；介面預設 Comfortable 112.5%，非瀏覽器 200% 縮放）：

| 語言／視窗 | 從準備頁進入：新增服務 | 返回：準備按鈕 | 首次 AI 入口：新增服務 |
| --- | ---: | ---: | ---: |
| 繁中 1024×768 | 544 | 150 | — |
| 英文 1024×768 | 544 | 176 | — |
| 繁中 390×844 | 588 | 353 | 640 |
| 英文 390×844 | 668 | 445 | 746 |

額外操作：雙語手動貢獻編輯後前進按鈕停用，明確確認後恢復；實際下載分享指南，SHA-256 與 `docs/PAGES_SHARING_GUIDE.md` 相同。Fixture 最終 `model_calls=2`，對應啟動時兩種語言 FAQ 的合成生成；沒有額外模型生成或真實模型連線，`gateway_requests=0`。未勾選外網驗收或核對虛構的公開網站。

證據位於 `output/playwright/ux-fix-20261011/`：`results.json`、`browser-regression.txt`、雙語桌機／手機截圖及下載的指南。既有 `ux-20261011` 原始走查報告保持不變。

### 自動檢查與限制

- 前端 Vitest：**45 檔／525 項通過**；另有 `tests/web/LocalPublishingWorkspace.test.tsx` **5 項通過**。
- TypeScript、Prettier 通過；ESLint **0 error／19 個既有 Fast Refresh warning**。
- Vite production build、場景資產一致性、visitor source guard（14 個正反例、15 個 runtime 檔案）通過。保留既有 `scene-mode.js` 非 module script 建置警告。
- 本次相關檔案的 `git diff --check` 依 repository 換行設定通過；新回歸腳本與本文件無行尾空白。
- 本輪使用已安裝的 Node 工具與 `.venv`；pnpm shim 嘗試取得固定版本時受 DNS 限制，沒有安裝依賴或更換 package manager。
- 合成 host 未配置真實分析選用／回答服務管理，相關請求為預期的 503；這些畫面不作為真實模型連線成功的證據。Python 檢索未改動，本輪未重跑前一批 128 項後端測試。
- 真實回答模型資格測試／目錄收錄、完整真實模型主線、Pages／Funnel 外網部署、乾淨 Windows、200% 縮放與螢幕閱讀器、Man 素材權利及正式 Recall@8 仍沿用既有未完成狀態。跨 repo B 方案與合併 Pages 欄位未實作；本次 UX 修正沒有待決定的產品事項。

隔離瀏覽器 session 已關閉；本輪測試程序已停止，18794／18795 埠確認無 listener。保留合成 runtime 與截圖供複核，沒有刪除既有工作。

---

## 修正後再次走查（2026-10-11，Codex）

依擁有者要求重新操作流程，這次只做 UX 分析，未再修改應用程式。結論：內容編輯與訪客使用的下一步已較清楚，但仍不能判定外行能從零獨立完成公開分享。本輪是單一評估者的認知走查，沒有招募外行受試者；也未完成無中斷的新作品集端到端驗證。

### 實際操作與結果

- 使用正式前端 build、既有 `tests.browser.a5_server` 與 `a5_transport`；主站 18795、gateway 18796、匯出站 18797，合成資料位於 `.test-tmp/ux-rewalk-20261011-ready`。模型與 GitHub 是 fixture transport；本輪沒有真實模型或公開部署。
- 正常帳密登入 → 歡迎頁 → AI 新增服務表單 → 裝置檢查 → 手動路線 → 確認既有合成專案 → 修改雙語貢獻 → 切換語言 → 再確認 → 基本資料 → 檢閱。未確認的修改會阻擋前進；語言切換保留輸入。
- 「完成內容並預覽」回 503 `SERVICE_NOT_READY`，重試仍相同。確認 A5 的 `AdminOperations` 未配置 `onboarding`；因此這是環境限制，不是已證實的正式產品故障。新內容未交接到預覽。模型連線／回答模型／分析選用的其他 503 同樣是 fixture 未配置。
- 後半段改用 fixture 原有已準備版本：預覽作品與卡片 → 儲存成功（200）→ 模型設定往返 → Pages 網址儲存 → 原生下載網站 ZIP 與卡片 GIF。沒有宣稱新草稿已建立 NPC，也沒有核對虛構的遠端 Pages 或勾選外網驗收。
- 使用本輪下載 ZIP 原檔啟動靜態站：建議問題與來源可開啟；停止 gateway 後重整顯示休息中，已核准 FAQ 可讀；英文手機導覽可開啟，Escape 可關閉；重啟後按重新檢查恢復，送出非 FAQ 新問題得到 `Answer complete`。模型計數由啟動 FAQ 的 2 增為 3，gateway 請求共 5；全部是合成服務。
- 手機 390×844 下，模型往返均聚焦 H2；新增服務頂端 y=587.875、返回後準備按鈕 y=352.90625，無水平溢出。這些是本輪重測，沒有沿用前一輪的 65 項結果充數。

### 目前仍會卡住的地方

| 編號／嚴重度 | 實際觀察 | 下一步修正方向 |
| --- | --- | --- |
| R-01／高 | 模型表單仍要求自行取得連線方式、服務網址、key、模型名稱；裝置檢查沒有通過完整驗證的推薦回答模型。 | 提供一條實測過的最小服務準備教學，清楚分開取得服務、建立模型、測試、選用。不得以未驗證模型充當推薦。 |
| R-02／高 | 公開分享要求先取得 Funnel／Pages 網址，再處理命令、解壓、repository 與發布來源。下載指南有部分步驟，但畫面缺少「還沒有網址」的起點。 | 將取得網址、外部操作及返回核對串成就地指引；保留手動外網確認與安全邊界。 |
| R-03／中 | 儲存本機草稿成功訊息顯示在第四段 GitHubShareGuide；1280×900 視窗中訊息頂端 y=4173.14，儲存按鈕在第一屏。 | 本機預覽、儲存與準備的回饋放在第一段操作旁；卡片下載、GitHub 核對與 README 複製的回饋留在第四段。依操作區分通知，避免錯置或重複播報；儲存成功不表示 NPC 已套用或已公開。詳見下方 R-03。 |
| R-04／中 | Pages 尚未核對時，README 末步顯示舊版網址欄位，提示「先填入可公開連線的 HTTPS 訪客網址」。 | README 預設路線在 Pages 尚未核對時，提供「前往第 3 段核對 Pages 網站」入口，聚焦並捲到現有核對區；只有既有核對狀態有效時才提供 Pages Markdown。舊版網址、Markdown 與複製操作一併收進選填進階區，保留獨立驗證。詳見下方 R-04。 |
| R-05／中 | 服務未就緒的草稿失敗只說「請檢查內容後重試」。故障由 fixture 觸發，但通用錯誤呈現屬產品。 | 依既有錯誤碼及失敗操作區分草稿服務未就緒、輸入問題與連線失敗，保留輸入並提供恢復動作。草稿的 SERVICE_NOT_READY 不等同模型未設定，不得一律導向模型設定或要求修改內容；未知錯誤也不推定為輸入錯誤。詳見下方 R-05。 |
| R-06／中 | 歡迎頁兩個路線入口尚未就地說明：手動可以編輯／預覽／儲存，但聊天仍需模型。 | 兩個入口旁直接說明：AI 路線先設定、測試並明確選用回答／分析與資料查找模型；手動路線不需模型即可編輯、確認、預覽、儲存及匯出草稿，但準備 NPC 與即時聊天仍需模型。進入任一路線不代表已發布，也不自動呼叫模型或下載。詳見下方 R-06。 |

建議先處理 R-03 → R-04 → R-05 → R-06 的局部介面問題，再補 R-01 → R-02 的完整新手準備路徑。訪客端離線 FAQ 與需連線問題的分類可列較低優先改善；空白輸入的送出停用是正常行為，不列故障。本次只列建議，未新增產品承諾或改變既有驗收門檻。

### R-03～R-06 文件修訂與後續驗證條件

本次只修訂這四項的修正方案與判定方式，沒有修改應用程式或重跑瀏覽器；上表的觀察仍是修正前證據，四項產品問題不得因此標為已修復。以下沿用既有需求，不新增 API、錯誤碼、儲存欄位或驗收門檻。

- **R-03｜操作回饋就地呈現。** 原始碼依據：`LocalPublishingWorkspace.tsx` 的 `run`、`save`、`downloadCard` 和複製操作共用 `notice`，目前只有 `GitHubShareGuide.tsx` 呈現它。因此應按操作歸屬呈現通知，不能把整個共享通知直接搬到第一段；外觀套用／草稿讀回的既有通知也須留在相應操作附近。成功狀態與失敗警示須可由輔助技術取得，避免同一訊息在兩處播報。儲存與準備是兩次請求；若儲存成功但準備失敗，應分別交代結果，不聲稱草稿未儲存或 NPC 已更新。
  **驗證：** 在繁中／英文桌機與手機操作本機儲存成功、儲存失敗、儲存後準備失敗，當下操作區可見正確回饋，失敗不清除輸入；下載與複製回饋仍在分享區可見，鍵盤／輔助技術可取得訊息。對應 NFR-003／009；保留 AC-040 的焦點、錯誤與狀態可存取要求。

- **R-04｜Pages 主線與舊版路線分開。** 原始碼依據：`LocalPublishingWorkspace.tsx` 以 `pagesSharingState.verified` 決定 `verifiedPagesUrl`，並在未核對時退回 `cardMarkdown(publicUrl)`；`GitHubShareGuide.tsx` 目前直接顯示舊版欄位。主線應明說「先到第 3 段上傳並核對 Pages 網站」，連到現存 `#pages-share-panel-heading`，且返回後保留草稿及已輸入網址。舊版獨立部署的輸入、產生 Markdown 與複製能力在進階區保留；Pages 核對有效時，主線沿用 `verifiedPagesMarkdown`。網址格式合格、儲存成功或 ZIP 下載均不等於遠端核對成功，不合併 Gateway 的 Pages origin 與完整 Pages URL，也不代勾手動外網確認。
  **驗證：** 覆蓋未設定、尚未核對、核對失敗、核對成功與既有核對失效狀態；只有有效核對可產生主線 Pages 連結。鍵盤能開啟進階區、輸入合法／不合法舊版網址並依原規則複製；主線跳轉焦點及雙語文案正確。對應 FR-047、NFR-009、AC-068；保留 ADR-047／048 的手動發布及進階部署邊界，不表示外網驗收完成。

- **R-05｜草稿錯誤要能恢復。** 原始碼依據：`AdminPage.tsx` 的 `createGuidedDraft`／`performGuided` 將錯誤送入 `guidedErrorMessage`；後者缺少 `SERVICE_NOT_READY`，而現有 `VALIDATION_ERROR` 文案只適用 GitHub 帳號。`AdminOperations._onboarding()` 在草稿服務未配置時確實會拋出 `SERVICE_NOT_READY`，不能用這個碼推論是哪個模型壞了。草稿情境應說明「草稿建立服務尚未就緒；目前輸入仍保留。請確認本機服務啟動完成，再重試；若持續發生，回報此錯誤碼」，不指示使用者重新填內容。草稿的 `VALIDATION_ERROR`／`CONFIG_INVALID` 應引導回檢閱相關必填、雙語內容與確認狀態；其他操作保留原有帳號／模型錯誤語意。瀏覽器連線失敗應提示檢查本機服務與連線後明確重試；無法分類的錯誤使用中性提示，不把原始例外或回應內容直接顯示給使用者。不自動重試、切換 provider 或重設草稿。
  **驗證：** 對上述服務、輸入、連線及未知錯誤逐一檢查雙語訊息、恢復動作與輸入保留；失敗維持檢閱狀態，修復服務後明確重試才可前進。沿用現有錯誤摘要焦點，確認帳號驗證與模型錯誤提示未退化。A5 缺少 onboarding 的 503 只作錯誤呈現證據，成功流程需使用已配置草稿服務的環境，不得把 fixture 改成永遠成功來宣稱修復。對應 FR-025／028、NFR-003／009、AC-040。

- **R-06｜入口即說明可做範圍。** 原始碼依據：`GuidedOnboardingView.tsx` 的歡迎頁只有 `startAi`／`startManual` 按鈕，模型前置條件目前在後續模型步驟才出現。將等義雙語短說明放在各入口旁，並以可存取描述關聯按鈕；保留既有 `START_AI`／`START_MANUAL` 路由與草稿續接。手動路線不因沒有模型而停用，也不把略過模型視為模型已就緒；「不需模型」只描述內容建立能力，不宣稱已完成公開分享或可離線生成新回答。
  **驗證：** 在無模型、只有一種模型、已測試但未選用及已選用狀態下，雙語入口說明均可見；手動入口直接進入既有手動流程，AI 入口遵守既有測試與選用門檻，點入／返回沒有額外模型呼叫或下載，且保留無水平溢出與鍵盤操作。對應 FR-025／028／040／041、NFR-003／009、AC-040／057／058、ADR-030。

四項文件修訂無新增待擁有者決定事項。R-01／R-02、真實模型、公開部署與正式驗收狀態均維持原記錄；上列是後續實作的局部回歸條件，不取代完整 AC。

### 證據與限制

- 報告與原始觀察：`output/playwright/ux-rewalk-20261011/UX_REWALK.zh-TW.html`、`observations.json`；同目錄保留操作 snapshots、截圖、`site.zip`、`reponpc-card.gif` 與可重跑的 `render_report.py`。
- ZIP 中 **23 個宣告檔案**的大小與 SHA-256 全部符合 manifest；卡片檔頭為 GIF。報告資料與圖片存在性自我檢查通過。CLI 不允許 `file:` 協定，報告的 HTML 瀏覽器渲染未驗；未改用其他路由重試。
- 乾淨 launcher 的一次性啟動登入未完成驗證。自動審核拒絕新增一次性測試登入入口，理由為未授權額外驗證入口；臨時腳本已刪除，沒有繞過。後續使用既有 fixture 的原本帳密登入。
- 沒有重跑整套單元測試；沒有測真實 GitHub 探索／上傳、真實模型品質、乾淨 Windows、Funnel／Pages 外網、200% 原生瀏覽器縮放或完整螢幕閱讀器。對應 FR-025／028／040／041／047、NFR-003／009、AC-040／057／058／068 的部分 UI 證據，不代表完整 AC 或正式發布通過。
- 本輪瀏覽器已關閉，專用測試程序已停止，18794–18797 確認無 listener。既有工作樹修改均保留。此分析沒有新增待擁有者決定的產品變更。

---

## R-03～R-06 程式修正與檢查紀錄（2026-10-11，Codex）

依擁有者後續要求，這次已修改管理介面原始碼與測試。前述「只修訂文件」及走查觀察保留為歷史紀錄；本節記錄四項程式修正，不代表完整 AC、真實瀏覽器或公開發布驗收通過。R-01／R-02 與其他既有修改未變動；未修改 API、schema、後端、依賴或模型選用規則。

### 實作結果

| 項目 | 修正與回歸範圍 |
| --- | --- |
| R-03 | LocalPublishingWorkspace 將通知依本機、分享、外觀操作區分。本機預覽、儲存與準備的成功／失敗回饋在第一段按鈕旁呈現；GitHubShareGuide 只接收分享通知，外觀讀回警告留在外觀區。儲存成功但準備請求失敗時明說草稿已儲存、NPC 準備結果尚無法確認，提示檢查狀態與模型後再重試。繁中／英文測試涵蓋儲存成功、儲存失敗、儲存後準備失敗、預覽失敗及複製成功／失敗，確認通知只有一處、輸入保留、不洩漏原始例外。 |
| R-04 | README 主線在 Pages 未有效核對時提供前往第 3 段的連結，聚焦並捲到現存 pages-share-panel-heading；有效核對時才顯示 Pages Markdown。舊版網址、Markdown 與複製按鈕一起移入預設收合的選填進階區，保留原有網址驗證。修正複製 handler，複製各自欄位實際顯示的 Markdown。雙語元件測試覆蓋未核對／已核對分支、進階區收合、合法／不合法舊版網址、兩種 Markdown 複製及跳轉焦點／捲動呼叫；既有核對狀態來源與失效規則不變。 |
| R-05 | guidedErrorMessage 加入既有 SERVICE_NOT_READY、REQUEST_FAILED 的雙語恢復提示；檢閱步驟的 VALIDATION_ERROR／CONFIG_INVALID 提示檢查草稿必填、雙語內容與確認狀態，其他步驟維持原本錯誤語意。AdminPage 將 fetch 的 TypeError 對應既有 REQUEST_FAILED；未知錯誤使用中性提示，不回顯原始內容。服務未就緒不推定模型故障或要求重填，不自動重試。單元與呈現測試檢查各類恢復文案、原有帳號驗證語意、檢閱資料保留及錯誤摘要焦點屬性。 |
| R-06 | 歡迎頁兩個入口旁加入等義雙語說明，以 aria-describedby 關聯按鈕。AI 路線說明測試並明確選用兩種模型角色；手動路線說明可無模型編輯、確認、預覽、儲存與備份草稿，但準備 NPC／即時聊天仍需模型，草稿不等於發布。沿用既有路由與續接狀態。雙語元件測試確認說明直接可見、描述關聯正確，呈現入口不呼叫分析或其他 action；既有狀態機測試一併通過。 |

需求對應：R-03 為 NFR-003／009、AC-040；R-04 為 FR-047、NFR-009、AC-068、ADR-047／048；R-05 為 FR-025／028、NFR-003／009、AC-040；R-06 為 FR-025／028／040／041、NFR-003／009、AC-040／057／058、ADR-030。以上只涵蓋相關管理介面行為，不提升完整驗收狀態。

修改檔案：

- apps/web/src/features/admin/：LocalPublishingWorkspace.tsx、GitHubShareGuide.tsx、guidedOnboarding.ts、GuidedOnboardingView.tsx、AdminPage.tsx。
- 同目錄測試：新增 LocalPublishingWorkspace.actions.test.tsx、GitHubShareGuide.test.tsx；更新 guidedOnboarding.test.ts、GuidedOnboardingView.test.tsx。
- tests/web/GitHubShareGuide.test.tsx：更新進階區收合後的結構預期並確認收合狀態。
- 本文件：僅追加本節，保留其他 R 項與先前紀錄。

### 本輪檢查結果

依 ADR-012 使用已安裝的 pnpm 11.16.0；因 shell 工具初始化失敗，以 Node 執行既有 Corepack 的 pnpm.js 入口，未安裝依賴或更換 package manager。下表以等價 pnpm 指令表示，全部最終退出碼為 0。

| 指令 | 最終結果 |
| --- | --- |
| pnpm --dir apps/web run format | 通過，Prettier 全部符合格式。 |
| pnpm --dir apps/web run lint | 通過，0 errors；保留 19 個既有 Fast Refresh warnings。 |
| pnpm --dir apps/web run typecheck | 通過，tsc --noEmit。 |
| pnpm --dir apps/web run test | 通過，47 檔／540 項。 |
| pnpm --dir apps/web run build | 通過，visitor source guard 檢查 15 個 runtime 檔案，Vite production build 97 modules；保留既有 scene-mode.js 非 module script 警告。 |
| pnpm --dir apps/web exec vitest run --root ../.. --config apps/web/vite.config.ts tests/web/LocalPublishingWorkspace.test.tsx tests/web/GitHubShareGuide.test.tsx | 通過，另 2 檔／13 項。 |

另外，修改的外部 tests/web 測試通過 Prettier；本次來源、測試與文件差異的空白檢查通過。新增測試首次執行曾因 React HTML 跳脫預期與新增 details 的舊計數預期失敗，修正測試預期後重跑通過；最後格式檢查亦已重跑通過。最終五項前端輸出及額外測試輸出保留於 output/playwright/r03-r06-20261011/。本輪未重跑 Python、場景資產產生器或正式 Recall@8；後端與資產未改。

### 驗證限制與待決定事項

元件測試包含靜態呈現與直接事件 handler 檢查；LocalPublishingWorkspace 的操作測試使用受控 hooks 狀態，未掛載真實瀏覽器。這些證據不能取代實際版面、鍵盤往返與輔助技術驗證。

曾啟動隔離 A5 fixture（127.0.0.1:18803，.test-tmp/r03-r06-20261011），但既有 Playwright／Chromium 在載入頁面前即啟動失敗（Session closed；診斷顯示 GPU 子程序 access denied）。因此本輪未完成雙語桌機／手機瀏覽器回歸，不沿用舊輪瀏覽器結果宣稱通過。未增加驗證入口或修改 fixture 成功條件，未連線真實模型、GitHub 或公開部署；測試程序已停止。

四項修正沒有新增待擁有者決定的產品事項。真實瀏覽器、200% 縮放／螢幕閱讀器及既有真實模型／公開部署驗收仍維持未完成狀態。

---

## R-03～R-06 複核與瀏覽器驗證（2026-10-12，Claude）

### 重跑

`pnpm --dir apps/web run typecheck`、`test`（47 檔／540 項）、`build`，以及 `tests/web` 兩檔 13 項，全部通過。

### 瀏覽器實測

使用內建瀏覽器。乾淨 launcher 在 `127.0.0.1:18790`，資料目錄 `.test-tmp/claude-verify-20261012-clean`；A5 fixture 在 `127.0.0.1:18791`，資料目錄 `.test-tmp/claude-verify-20261012-ready`。結束後兩個伺服器都已停止，分頁已關閉。

| 項目 | 結果 | 觀察 |
|---|---|---|
| R-06 | 通過 | 中英文兩個入口的說明都直接可見，並以 `aria-describedby` 關聯按鈕。步驟標題會自動捲到頂端；狀態卡收成底部一行摘要。 |
| R-03 | 通過 | 桌機：儲存按鈕頂端 y=359，成功訊息 y=426。手機 390×844：按鈕 y=397，訊息 y=528，沒有水平溢出。 |
| R-04 | 通過 | Pages 未核對時，第 4 段第 3 步提供「前往第 3 段」連結；按 Enter 後焦點落在 `#pages-share-panel-heading`，標題在 y=18。舊版路線收在預設關閉的「選填進階」。 |
| R-05 | 通過 | 檢閱步驟按「完成內容並預覽」，fixture 回 503 `SERVICE_NOT_READY`。錯誤摘要取得焦點，位置在 y=349，顯示具體的中文恢復提示。 |

### 仍有的缺口

| 編號 | 等級 | 問題 | 建議 |
|---|---|---|---|
| G-01 | 中 | 按「儲存本機草稿」後焦點掉到 `BODY`。按鈕在處理中被停用，焦點因此遺失；鍵盤使用者必須從頁首重新找位置。 | 處理中改用 `aria-disabled`，或完成後把焦點還給按鈕或訊息。 |
| G-02 | 低 | 成功訊息「已儲存在本機」用 `role="alert"` 和黃色警告樣式，螢幕閱讀器會當成警示，視覺上也像出錯。 | 成功用 `role="status"` 和中性或成功樣式；只有失敗才用 alert。 |
| G-03 | 低 | 模型未就緒時，「準備 NPC」下方同時出現兩段意思相同的說明（`LocalPublishingWorkspace.tsx:356` 的 `prepareReason`，以及 :495 的那段）。 | 合併成一段，保留「前往設定模型」按鈕。 |
| G-04 | 中 | 「上次準備未完成：{error_code}」直接顯示原始錯誤碼（:508–512）。R-05 只修了引導流程，預覽與分享頁的錯誤仍沒有轉成可行動的說明；`run()` 的失敗訊息也仍是通用的「檢查輸入內容或服務狀態」。 | 沿用 R-05 的錯誤碼對照方式，把發布頁的錯誤也轉成具體恢復提示。 |
| G-05 | 低 | R-05 文案「若持續失敗，回報錯誤碼」沒有說明回報給誰、去哪裡回報。這是自架工具，使用者通常就是管理者本人。 | 改成具體動作，例如重新啟動 RepoNPC，或到維護頁查看狀態。 |
| G-06 | 低 | 入口說明仍使用「回答／分析模型」「資料查找模型」等術語，外行不一定懂差別。 | 用一句話白話說明兩者用途，或連到說明。 |

既有的 R-01（實測過的模型服務教學）與 R-02（取得公開網址的就地指引）仍是外行獨立完成公開分享的主要阻礙，需要擁有者先做決定。新內容從草稿、準備 NPC 到試聊的完整新手路線，仍然因為 fixture 沒有設定分析服務而無法走完。


---

## G-01～G-05 程式修正與檢查紀錄（2026-10-12，Codex）

本次依擁有者要求實作前述複核缺口，G-06 明確不做。只修改兩個前端來源檔、四個既有測試檔與本節紀錄；不修改 API、schema、後端或依賴。原走查及複核內容保留，其他未提交變更未還原。以下是局部程式與自動測試結果，不提升正式 AC 驗收狀態。

### 各項處理

| 項目 | 實作與測試 |
| --- | --- |
| G-01 | 儲存本機草稿按鈕在處理中改用 aria-disabled，保留可聚焦的原按鈕；沒有草稿時仍以原生 disabled 禁止操作。run 使用同步 ref 閘門阻擋處理中的重複送出，包含同一次 render 的快速連按。雙語測試確認處理中不原生停用、重複按下只有一次寫入、完成或網路失敗後解除忙碌狀態。真實瀏覽器焦點本輪未驗證，原因見下方。 |
| G-02 | 本機成功通知改為 role=status 並使用一般段落中性樣式；失敗及儲存後準備失敗保留 role=alert 與警告樣式。雙語操作測試核對訊息角色、樣式及第一段通知位置。 |
| G-03 | 模型前置條件、前往設定模型按鈕與草稿保留說明合併到同一個 local-prepare-reason 段落，移除重複的模型說明；準備按鈕保留 aria-describedby。雙語元件測試確認單一說明、按鈕及描述關聯。 |
| G-04 | 發布操作例外、儲存後準備例外與上次準備的 error_code 共用 publicationErrorMessage。依 repo 既有錯誤碼提供版本衝突、忙碌、模型變更／需測試、內容／素材驗證、大小限制、草稿讀寫、取消／中斷、逾時與準備失敗的恢復動作；服務／連線提示沿用 guidedErrorMessage。未知錯誤採中性維護指引，不直接顯示原始碼或例外內容。保留部分成功時「草稿已儲存」與既有訪客版本。雙語錯誤矩陣涵蓋 17 種輸入、三種呈現路徑，另測原生 TypeError；不自動重試、切換模型或覆蓋草稿。 |
| G-05 | guidedErrorMessage 的 SERVICE_NOT_READY 及未知錯誤，不再要求向不明對象回報；改為先保留未儲存內容，再到「維護」查看服務狀態。雙語單元與 GuidedOnboardingView 元件測試確認恢復動作可見、未回顯未知例外，輸入與錯誤摘要可存取屬性保留。 |

錯誤分類採既有封閉錯誤碼的 switch，未知值安全退回中性提示；不是比對原始例外文字中的關鍵字。測試包含繁中／英文、原生網路例外、版本衝突及未知值 canary，避免只修單一走查案例。

修改檔案：

- apps/web/src/features/admin/LocalPublishingWorkspace.tsx。
- apps/web/src/features/admin/guidedOnboarding.ts。
- 同目錄 LocalPublishingWorkspace.actions.test.tsx、LocalPublishingWorkspace.test.tsx、guidedOnboarding.test.ts、GuidedOnboardingView.test.tsx。
- docs/OPTIMIZATION_PLAN_2026-10-11.md：僅追加本節。

沿用 FR-025／028、NFR-003／009、AC-040 的可恢復操作與無障礙要求，以及 ADR-030／046 的模型選用、本機儲存與最後可用版本邊界；沒有新增能力、錯誤碼或驗收門檻。G-06 的入口說明原文未修改，無新增待擁有者決定事項。

### 實際執行的檢查

使用 ADR-012 指定的 pnpm（既有 Corepack pnpm.js，由 Node 呼叫）；shell 工具初始化失敗，因此改用現有程序執行介面，未安裝工具或更換 package manager。

| 指令 | 結果 |
| --- | --- |
| pnpm --dir apps/web run format | 通過。 |
| pnpm --dir apps/web run lint | 通過；0 errors、19 個既有 Fast Refresh warnings。 |
| pnpm --dir apps/web run typecheck | 首次失敗：新增測試替身簽章少了 path 參數（TS2352）。補正簽章後重跑通過；未用 unknown 轉型略過檢查。 |
| pnpm --dir apps/web run test | 通過；47 檔、545 項。 |
| pnpm --dir apps/web run build | 通過；visitor source guard 15 個 runtime 檔案、Vite 97 modules。保留既有 scene-mode.js 非 module script 警告。 |
| pnpm --dir apps/web exec vitest run --root ../.. --config apps/web/vite.config.ts tests/web/LocalPublishingWorkspace.test.tsx tests/web/GitHubShareGuide.test.tsx | 通過；另外 2 檔、13 項。 |

修改檔案的 git diff --check 通過；本節無行尾空白。最終指令輸出保留於 output/g01-g05-20261012/。後端未改，本輪未執行 Python 或正式 Recall@8。

### 瀏覽器限制與剩餘風險

Browser 工具已連接，但安全檢查拒絕開啟隔離 A5 fixture 的 http://127.0.0.1:18804/admin，明確回覆使用者未授予此網址存取權限。本輪未透過其他瀏覽器、代理或底層指令繞過，未宣稱真實焦點、版面或螢幕閱讀器回歸通過。元件操作測試沿用受控 hooks 與直接事件 handler，不能取代原生 DOM 的焦點測試；仍需在允許存取的測試環境補驗。

合成測試服務已停止，18804 確認無 listener；沒有操作擁有者 runtime、真實模型、GitHub 或公開部署。G-06、R-01／R-02 與正式發布驗收維持原狀。

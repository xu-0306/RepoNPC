# 像素 UI 實作計劃（ADR-072 草案，2026-10-23）

**狀態：** 擁有者在 2026-10-23 核准，第 4 節 D1–D8 全部採用建議選項（ADR-072 Accepted）。第 6 節已套用為 Technical Specification 0.4.14 與 AC-082。P0–P4 尚未實作。

## 1. 目標

把現有介面換成擁有者在 2026-10-23 選定的像素 RPG 風格：

- 訪客對話頁：原型 Set C「Pixel Guild」，訪客可切換配色與明暗模式。
- 擁有者設定頁與角色頁：原型 Set F「Pixel Workshop」，與對話頁同一家族。

原型與截圖：`output/mockups/ui-pixel-2026-10-23/`（`index.html` 為入口；`screenshots/` 為 1440 與 375 寬的截圖）。

## 2. 現況（已在程式碼與文件核對）

- 前端：React 19、Vite 7、`react-aria-components`（只用於管理介面，ADR-061）。沒有 CSS 框架。樣式在：
  - `apps/web/src/styles.css`（2147 行）；
  - `visitor.css`（911 行）；
  - `features/character/CharacterRenderer.css`（81 行）。
- 管理介面元件：`features/admin/` 共 34 個 `.tsx`（不含測試）。
- 訪客頁：`app/VisitorPage.tsx`、`VisitorConversation.tsx`、`VisitorApp.tsx`。
- 配色已依 ADR-051 實作：
  - `src/reponpc/scene/color_schemes.yml` 收 5 組（`neutral` 預設、`ocean`、`forest`、`sunset`、`lavender`），每組有 10 個角色色的明暗兩版；
  - `registry.py` 在載入時驗證對比；
  - `resolve.py` 由伺服器解析；
  - `apps/web/public/scene-mode.js` 在首次繪製前套用訪客的明暗選擇。
- ADR-051 與 FR-051 目前明文規定：
  - 「Visitors MUST NOT choose a scheme」；
  - 「no scheme draws a backdrop」；
  - 版面只用平面色。
- `scripts/check_visitor_source.mjs` 在建置時禁止訪客原始碼出現字面顏色、外部樣式表與未列管的相依。
- CSP：
  - 主程式是 `style-src 'self'; font-src 'self'`（`main.py:151`）；
  - 匯出的 Pages 網站相同（`sharing/export.py:329`）。

  因此正式版不能用原型裡的 CDN Tailwind、CDN daisyUI 或 Google Fonts。
- FR-047 要求專案卡片顯示星數與 fork 數；`publicTypes.ts` 已有 `stars` 與 `forks`。原型沒有顯示，實作時要放回專案抽屜。
- 與 CSS 或版面直接相關的測試：
  - `tests/browser/` 中 10 支 review 腳本；
  - `tests/unit/test_guided_onboarding.py`；
  - `tests/security/test_a5_review.py`。

## 3. 提議設計

### 3.1 視覺系統（D1 建議做法）

不新增 UI 套件，在專案 CSS 內建一套小型像素設計系統：

- **Token：** 沿用 `--scene-<role>`，新增場景角色色（3.2）。字級最小值依原型審查結果：
  - 內文與輸入框 15–16px；
  - 按鈕與標籤 14px 以上；
  - 輔助文字 13px 以上。
- **元件：** 像素面板（階梯邊框＋硬陰影、0 圓角）、像素按鈕（主要／次要／危險）、標籤、狀態徽章、RPG 對話框（名牌＋▼）、任務清單、經驗條、裝備欄卡片、像素場景。
- **行為：** 管理介面仍用 React Aria（Dialog、Popover、FileTrigger 等）。訪客頁維持原生 HTML，不引入 React Aria。
- **動畫：** NPC 動畫沿用 `CharacterRenderer`；`prefers-reduced-motion` 時顯示靜止畫格。

### 3.2 配色與場景（D2、D3、D4）

- **配色組：** `color_schemes.yml` 換成 4 組像素配色：`meadow` 草原（預設）、`sunset` 黃昏、`coast` 海岸、`sakura` 櫻花。每組有白天（light）與夜晚（dark）兩版，夜晚版另外設計星星、月亮與較暗的山。
- **場景角色色（新增，明暗兩版都要有）：** `sky`、`horizon`、`hill_far`、`hill_near`、`grass`、`ground`、`wood`、`celestial`。
  - 相鄰圖層對比至少 1.5:1，避免場景糊成一片；
  - 原有的文字 4.5:1 與非文字 3:1 規則不變。
- **舊組 id 別名：** `neutral`、`forest`→`meadow`，`ocean`→`coast`，`lavender`→`sakura`；`sunset` 升版。既有設定不需遷移，但外觀會改變，擁有者需重新匯出分享網站。
- **場景繪製：** 只用 CSS 繪製一個與角色無關的像素場景，顏色全部來自 token。
  - 不用圖片檔，不依配色 id 分支；
  - 擁有者上傳的背景圖（FR-052）存在時，取代場景，放在同一個場景框內。
- **NPC 與背景分離：** 檢查改成對 NPC 正後方的場景色（`sky`、`hill_near`）。不足 3:1 時畫像素底座；文字顏色永遠不變。
- **訪客切換：** 新設定 `visitor_scheme_choice`（預設開啟）。訪客可選任一組，擁有者的 `color_scheme` 是預設值。
  - 選擇只存在該瀏覽器的 `localStorage`（新增一個 key），由現有 `scene-mode.js` 在首次繪製前套用；
  - 選擇不送出、不匯出、不寫 cookie；
  - 匯出檔包含所有配色組的解析結果。

### 3.3 訪客對話頁（Set C）

- **桌面版：**
  - 左側：場景框，NPC 以 4 倍整數縮放站在草地上；下方是 RPG 對話框，顯示 NPC 名稱、狀態與開場白。
  - 右側：對話紀錄，包含提問捷徑（帶專案名稱）、訪客訊息、NPC 回答與來源編號。
  - 輸入框固定在底部。
- **頂部列：** 品牌、「專案」抽屜（個人資料與專案卡片，含名稱、描述、語言、星數、fork 數）、語言切換、配色、明暗或跟隨系統。
- **手機版：** 場景縮成一條，對話紀錄佔剩餘高度並自己捲動；配色與明暗收進一個「外觀」按鈕。
- **狀態：**
  - 線上：idle 與 talk 動作；
  - 查找中：think 動作，加等待指示；
  - 休息中：offline 動作，停用輸入框，改列已核准的 FAQ（FR-047 既有行為）。

### 3.4 擁有者頁（Set F）

- **共用外框：** 品牌列（含一條小像素場景）、主選單（引導設定／角色與動畫／預覽與分享／進階 YAML／維護），左側是任務清單與經驗條（六個設定步驟）。
- **連接模型：** 兩個裝備欄（回答模型、資料查找模型），各有狀態、測試按鈕與可展開的設定細節。底部「確認配對並繼續」不用捲動就看得到。
- **角色與動畫：** 角色創建畫面，包含：
  - 大型預覽台；
  - 7 個動作按鈕；
  - 角色名片（名稱、開場白）；
  - 上傳 PNG（React Aria FileTrigger，取代原生「Choose File」）與驗證結果；
  - 「套用角色」。
- **其他頁面：** 探索與選取專案、批次分析、描述貢獻、檢視、預覽與分享、外觀、YAML、維護、登入，都用同一套元件改版（D7）。外觀頁加入 `visitor_scheme_choice` 開關。

### 3.5 字型（D5）

- **像素字：** 自帶 Press Start 2P（SIL OFL 1.1，只含拉丁字元，woff2 約數十 KB），用於品牌、英文標題、數字與按鈕。
- **中文與內文：** 用系統字型（PingFang TC、Microsoft JhengHei、Noto Sans CJK TC），不下載 CJK 網路字型。
- **授權：** 字型與授權條文放在 `THIRD_PARTY_NOTICES.md` 與 Windows 安裝版的授權清單。

### 3.6 不做

- 不新增端點、錯誤碼、模型行為或訪客資料欄位。
- 不改 CSP，不改訪客相依閉包規則，不在訪客頁使用 React Aria。
- 不出貨原型的「設計狀態」切換器、CDN 載入與示範資料。
- GitHub README 名片（`card.themes`）不在這輪；要不要改成像素風格，之後另議。

## 4. 擁有者決定

每項的第一個選項為建議。

**D1 樣式技術**

- (a) **不新增套件**，在專案 CSS 內建像素設計系統。
  - daisyUI 的主題會寫入字面顏色，並自帶主題切換，與 `color_schemes.yml` 重複，也會被顏色守門擋下；
  - 它的類別名稱會和專案撞名（原型的 `.stack` 重疊就是例子）；
  - 它的元件多是圓角，像素風格大多要覆寫。
- (b) **Tailwind v4 + daisyUI 5**，以 `devDependencies` 經 `@tailwindcss/vite` 在建置時產生 CSS。需要：
  - 更新 pnpm lockfile（ADR-012）與授權清單；
  - 關掉 daisyUI 內建主題，改接 `--scene-*`；
  - 擴充顏色守門以檢查建置後的 CSS；
  - 把約 40 個元件的 class 改成 utility 寫法。
- (c) **只用 Tailwind v4**，不用 daisyUI，工作量介於 a 與 b 之間。

**D2 訪客切換配色**

- (a) 新增 `visitor_scheme_choice`（預設開啟），訪客可選所有配色組。
- (b) 擁有者勾選開放哪幾組。
- (c) 維持只由擁有者選（訪客只能切明暗）。

**D3 場景繪製與擁有者背景圖**

- (a) 允許 CSS 像素場景；擁有者背景圖存在時取代場景。
- (b) 允許 CSS 像素場景，移除擁有者背景圖功能（FR-052）。可刪掉草稿與預覽流程，但屬於刪除既有 v1 功能。
- (c) 場景只用平面色塊（不畫山、草與告示牌）。

**D4 配色組**

- (a) 換成 `meadow`／`sunset`／`coast`／`sakura` 四組，舊 id 用別名對應。
- (b) 保留原 5 組 id，只重新調色並加場景角色色。

**D5 字型**

- (a) 只自帶拉丁像素字，中文用系統字型。
- (b) 另外自帶繁體中文像素字（例如「俐方體 11 號」Cubic 11，OFL）的子集。字型檔可能數百 KB 到數 MB；擁有者自訂的文字可能缺字，要有缺字回退。

**D6 訪客頁版面**

- (a) 依 Set C 修改 FR-047 的版面句（3.3）。
- (b) 保留 FR-047 版面，只換像素外觀。

**D7 其他擁有者頁的審查方式**

- (a) 不另做 mockup，直接用同一套元件改版，每批頁面完成後給擁有者看真實截圖，核可後才 commit。
- (b) 每頁先做 mockup 給擁有者核可，再實作。

**D8 G 輪文字精簡**

- (a) 改版各頁時一併套用已核准的 G 輪規則：每塊最多一句說明、次要資訊放 ⓘ、每畫面一個主要動作。
- (b) G 輪仍另外做。

## 5. 實作與測試計劃（核准後）

工作方式沿用先前輪次：

- Codex gpt-6.1-sol xhigh 一次只跑一個工作（兩個 xhigh 工作同時跑曾用完額度）。
- 主代理寫完整需求說明，在沙箱外建置、驗收與審查。
- pytest、lint、型別檢查交給 Haiku 子代理跑，主代理審查結果。
- 每階段一個 commit；不 push。

**P0 配色資料與後端（約 1 個 Codex 工作）**

- 新 `color_schemes.yml`：4 組 × 明暗，18 個角色色；別名表。
- `registry.py`：新增場景角色色與相鄰圖層對比驗證，產生對比報告。
- `resolve.py`：
  - NPC 分離檢查改對場景色；
  - 公開資料與匯出包含所有配色組；
  - 新設定 `visitor_scheme_choice` 加入設定模型、管理 API 與 YAML 範例。
- 測試：registry 對比矩陣、別名、未知 id 失敗、匯出內容、設定預設值。

**P1 像素設計系統與字型（1 個工作）**

- 自帶 Press Start 2P woff2 與 OFL 條文，加入授權清單。
- 建立共用 token 與像素元件 CSS；顏色守門照常通過。
- `scene-mode.js` 加配色選擇（一個 `localStorage` key、try/catch、首次繪製前套用）。

**P2 訪客對話頁（1 個工作）**

- `VisitorPage`、`VisitorConversation`、`CharacterRenderer` 改成 Set C 版面與狀態：
  - 專案抽屜（含星數與 fork 數）；
  - 外觀選單；
  - 休息中的 FAQ；
  - 手機版。
- 測試：
  - vitest；
  - 更新 `tests/browser/visitor-ui-review.tsx` 等；
  - Playwright 截圖矩陣（4 組 × 明暗 × 1440/375 × 三種狀態）；
  - 鍵盤操作、減少動態效果、中英文對等。
- 匯出的分享網站重新驗證：CSP、雜湊清單、無秘密。

**P3 擁有者外框、連接模型、角色與動畫（1 個工作）**

- 依 Set F 改版：任務清單與經驗條、裝備欄、角色創建畫面（FileTrigger）、外觀頁加入訪客配色開關。
- 測試：管理介面 vitest、`test_guided_onboarding.py`、相關 browser review 腳本、截圖。

**P4 其他擁有者頁（1–2 個工作，依 D7／D8）**

- 探索與選取專案、批次分析、描述貢獻、檢視、預覽與分享、YAML、維護、登入。
- 每批完成後把截圖給擁有者，核可後才 commit。

**每階段的驗收**

- 全套 pytest 與 vitest；ruff、mypy、TypeScript 型別檢查、eslint、`vite build`（含訪客守門）。
- Playwright 截圖由主代理檢查，送擁有者審查。
- 測試斷言只能等價替換或加強，不能刪除或放寬；每處改動以「原 → 新」列出。

## 6. 核准後套用的規格與驗收文字（草稿）

- **Technical Specification 0.4.14：**
  - FR-047 版面句改成 3.3 的 Set C 版面（D6）。
  - FR-050：角色色清單加入場景角色色；NPC 分離檢查改對場景色並使用像素底座（D3）。
  - FR-051：
    - 刪除「Visitors MUST NOT choose a scheme」與「no scheme draws a backdrop」；
    - 改成 `visitor_scheme_choice` 規則（D2）與「一個與角色無關、只用 token 上色的 CSS 場景」規則（D3）。
  - §12.3 與 §16 同步改寫。
- **新 AC-082「像素介面」：**
  1. 每組配色 × 明暗都通過 registry 對比驗證（含相鄰圖層 1.5:1）。
  2. 訪客可切換配色與明暗，重新整理後保留；`localStorage` 不可用時頁面仍正常；選擇不出現在任何網路請求、cookie 或匯出檔。
  3. 1440 與 375 寬：
     - 沒有橫向捲動；
     - 主要動作（送出、確認配對並繼續、套用角色）不用捲動就看得到；
     - 手機第一次載入就看得到最新訊息。
  4. 三種訪客狀態使用正確的動作列；減少動態效果時為靜止畫格。
  5. 像素字只用於標題、品牌、數字與按鈕；內文與輸入框使用可讀字型，最小字級符合 3.1。
  6. 原始碼沒有字面顏色或配色 id 分支；CSP 未變；沒有外部字型或樣式表請求。
- **修訂：**
  - AC-068：版面描述；
  - AC-072：分離檢查；
  - AC-074：訪客配色切換；
  - AC-075：背景圖取代場景。
- **ADR-051：** 平面色、不畫背景、只有擁有者選配色這三條改為「被 ADR-072 取代」；其餘仍有效。

## 7. 風險

- **NPC 與場景對比：** 像素場景比平面色複雜，深色角色在夜景上可能不明顯。靠分離檢查與底座處理，要用內建角色和上傳角色各測一次。
- **工作量：** 約 3000 行 CSS 與 40 個元件會被改動，與 G 輪、AC-081 實測的檔案可能重疊。建議 AC-081 實測先收尾，或兩者不要同時改同一批檔案。
- **擁有者既有設定：** 舊配色 id 會對應到新配色，外觀改變，需重新匯出分享網站才會生效。
- **英文像素字可讀性：** 長英文標題用像素字可能太寬。英文版標題超過寬度時改用一般字型，實作時用截圖確認。

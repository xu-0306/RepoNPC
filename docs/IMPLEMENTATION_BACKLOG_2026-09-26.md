# RepoNPC 完整實作待辦與分派計劃（2026-09-26）

狀態：**實作中**。本文件彙整 ADR-046 之後所有尚未實作或尚未驗收的工作，作為交給其他 agent 的單一入口。決策依據以 [完成方向契約](COMPLETION_DIRECTION_CONTRACT_2026-09-26.md)、`TECHNICAL_SPEC.md` 0.4.5、`DECISIONS.md` ADR-046～ADR-052 與 `ACCEPTANCE_CRITERIA.md` 為準；本文件只負責排序、相依與分派，不新增產品決策。

## 0. 目前基準

- 本機 `main` 包含 ADR-052 與後續本機實作工作；**尚未 push**，push 需擁有者另行授權。提交數與工作樹狀態以當次 `git status` 為準。
- 已完成並有本機證據：ADR-046 本機草稿／索引啟用／本機試聊／三步驟 GitHub 卡片引導；R01–R07、R09、R10、R12-A、R14 訪客聊天與卡片長文字子批次；R13 的 64px canonical、converter 與「角色與動畫」工作區。
- ADR-048～ADR-052（規格 0.4.0～0.4.5、FR-043～FR-053、AC-062～AC-079）已開始實作：A2 回答政策 v2 與擁有者端固定丟棄原因碼、A10/R11 近期批次恢復、A10/R12-B 既有 passage cache 重用量測與公開路由／bundle 匯出／runtime backup 排除測試已取得本機證據。A2 的參與事實端到端回答仍待 A3，coverage 報告待 A4；正式驗收帳本與發布閘門待 A12。
- 驗收帳本 `release-evidence/acceptance-ledger.json` 只涵蓋 AC-001～AC-061（3 pass、6 blocked、52 not-run），`source_identity` 仍是 2026-09-10 的髒工作樹。不得以它計算完成百分比。

## 1. 全部待辦總表

| # | 階段 | 範圍 | FR／AC | 相依 | 需擁有者決定 |
|---|---|---|---|---|---|
| A1 | Funnel 訪客閘道 F0／F2 | 預設拒絕的訪客專用閘道、Pages origin CORS、代理後限流身分、真實 SSE、私人管理 Host／Origin、公開狀態三分（本機可用／入口已設定／外網已驗證）、啟用／停用引導 | FR-047、AC-071（AC-068 一部分）；沿用 AC-022／036／049 的入口安全要求 | 無 | Windows 安裝版主機上閘道與 Funnel 的責任邊界需在 F0 寫成契約（見 §3） |
| A2 | 回答政策 v2 | envelope v2 分段、`{{owner}}` 後端渲染、`inflation_terms.yml`、數字事實檢查、逐段丟棄、無匹配回覆、第三人稱、「來源」列、prompt 修改 | FR-043／044、AC-062～065 | 無（`participation` 段在 A3 前只接受「無此類證據」） | 無 |
| A3 | 參與事實 | `github_login` 必填並預填、`aliases`、owner flag、首次／最後 commit 月份與 permalink、`has_visible_commits`、`other_contributors_visible`；無次數；API 失敗記為 unavailable | FR-045、AC-066 | A2（驗證器需認得 `PARTICIPATION`） | 無 |
| A4 | 覆蓋檢查與 FAQ 審核 | 資訊性覆蓋檢查（不阻擋發布）、FAQ 核准／拒絕／重產／改寫成自述、只匯出核准項、綁定 bundle ID 並在變更時標「需要重新確認」 | FR-046、AC-067 | A2、A3 | 無 |
| A5 | 訪客頁、配色與外觀 | 聊天介面版面、`color_schemes.yml` 五套配色與對比報告、`color_mode`、訪客明暗切換、NPC 舞台分離、歡迎區選用圖片的草稿／預覽／套用、管理端「外觀」步驟與吉祥物、GitHub Pages 靜態殼匯出、離線「休息中」與瀏覽器內 FAQ 比對、卡片連到 Pages 網址 | FR-047／050～052、AC-068、AC-072～075 | A1（閘道 origin）、A4（核准 FAQ） | 無（六點已確認；色碼於實作時以對比報告定稿） |
| A6 | 內建 embedding | `builtin_onnx` bge-m3、首次使用三選一對話框、進度／取消／續傳、固定 checksum、重建索引警告、zh-TW／en 檢索品質量測 | FR-049、AC-070 | 無 | 已決定（ADR-052）：官方 `BAAI/bge-m3` 固定 revision 的 fp32 ONNX，約 2.29 GB，逐檔 SHA-256 見契約 §6.2 |
| A7 | 模型引導（僅管理端） | `model_catalog.yml`、裝置檢查與 適合／勉強可用／不建議、canirun.ai 連結（不抄資料、不呼叫 API）、Ollama 明確 pull、白話錯誤對照、一行狀態、雲端資料揭露 | FR-040 修訂、AC-057 修訂 | 無 | 目錄首批收錄哪些模型（只能收已實測 envelope 的模型） |
| A8 | Windows 安裝器 | PyInstaller onedir＋Inno Setup 個人安裝、捷徑、托盤或小視窗、未簽章與 SmartScreen 說明、SHA-256、解除安裝保留資料、以新安裝檔更新 | FR-048、AC-069 | A6（onnxruntime 打包）、A1（閘道隨安裝版運作） | 無 |
| A9 | 角色美術與內建角色（R13 剩餘） | Man／Orange 概念圖轉換與逐格審查、`core/humanoid` v1 pack 矩陣、授權與來源紀錄、接上 composer／manifest、真實 `public/character.png` 與 SVG／GIF／PNG 卡片 | AC-020／021；供 A5 的預設角色 | 無 | 美術最終審核由擁有者看圖決定 |
| A10 | 舊修復項收尾 | R11 近期終止批次的 reload recovery、R12-B 可重用 derived index（先量測 passage cache 是否已涵蓋）；R08 受保護預覽併入 A5 | AC-077、AC-078（R08 為 AC-079） | 無 | 已決定（ADR-052） |
| A11 | 日常維運介面 | 「維護」頁：狀態、建立並下載備份、還原（確認＋自動先備份）、回復上一版 bundle、立即停止訪客閘道、更新與關閉 Funnel 的說明（CLI primitive 已存在） | FR-053、AC-076 | A8 | 已決定（ADR-052）：列入本次發布；更新只提供說明，不在程式內下載安裝檔 |
| A12 | 發布驗收與帳本 | 帳本擴充到 AC-079 並更新 `source_identity`；乾淨 Windows 主機安裝；獨立外網實測；真實 GitHub Profile 點入（AC-022）；Chrome／Firefox／Safari、雙語、375／768／1024／1440、200% zoom、鍵盤、螢幕閱讀器、減少動態；補驗 UI GIF 下載落盤與瀏覽器開啟本人陳述來源；D8 新手／訪客實測（擁有者執行）；授權聲明與發布檔 | AC-001～AC-079 | A1～A11 | GitHub README 寫入、公開入口啟用、push 各需當次授權 |
| — | 選用 | P1-04 重構（`P1-04_REFACTOR_HANDOFF.md`）；更大的貢獻輸出預算 | — | — | 需擁有者決定是否要做 |

## 2. 建議順序與並行

主線（依序）：**A1 → A2 → A3 → A4 → A5 → A8 → A12**。

可與主線並行（各用獨立 worktree，互不改同一檔案群）：

- **A6** 與 **A7**：只動 provider／admin 模型設定區域，可在 A1 開始時同步進行；A8 需等 A6 合併。
- **A9**：美術與素材管線獨立；A5 的驗收以程式產生的角色 fixture 進行，不被 A9 阻擋，但發布前必須有預設角色。
- **A10**：R11 與 R12-B 可隨時開始（只動分析批次與快取區域）；R08 隨 A5 一起做。
- **A11**：等 A8 完成後開始。

每一階段合併前都須跑完整 Python 與 Web 測試、Ruff／mypy／Prettier／TypeScript、production build 與 `git diff --check`，並在本文件對應列標註完成提交與證據位置。

## 3. A1 的 F0 待定契約（實作前先寫入 Funnel 計劃與 SECURITY）

- 閘道形式：同一程序內的訪客專用 ASGI app 綁定獨立 loopback 埠，或獨立反向代理；Funnel 只能指向閘道埠，不能指向完整應用埠或 8090 評估啟動器。
- 路由白名單由目前前端資源與 `/api/public/*` 清單產生，測試路徑編碼、大小寫、尾斜線、未知路由與重導向；`/admin`、`/api/admin/*`、模型埠一律 404。
- CORS 只允許設定的 Pages origin，不帶憑證；無 Pages origin 時不送任何 CORS header。
- 限流身分：查明 Funnel 實際轉送的來源資訊，不信任可偽造的 forwarded header；無法取得可信身分時以總並行與每日上限保護。
- Windows 安裝版：閘道隨應用啟動，Funnel 啟用／停用由擁有者在 Tailscale 官方流程操作；Tailscale 憑證不進入 RepoNPC 表單、日誌或匯出。

## 4. 所有 agent 共同遵守的規則

- 工作目錄 `D:\RepoNPC`，以本機 `main`（含 ADR-052 提交或更新）為基底。**不要從 origin clone**，會缺少 9 個未 push 的提交。若用 worktree，必須從本機 `main` 建立。
- gitignored 檔案不會出現在 worktree，請用絕對路徑讀取：
  - `D:\RepoNPC\.claude\skills\agent-memory\memories\reponpc\completion-direction-adr048-2026-09-26.md`
  - `D:\RepoNPC\docs\PROJECT_CONTEXT.md`、`D:\RepoNPC\docs\IMPLEMENTATION_PLAN.md`
- 不得 push、不得寫入 GitHub README、不得啟用公開端點或 Funnel，除非擁有者當次明確授權。
- 不得讀取或印出已儲存的模型 URL 或金鑰；不得靜默切換 provider；不得自動下載模型。
- 保留無關的工作樹變更；不得處理未追蹤的 `%SystemDrive%/`、`PixelNPC/`、`RepoNPC_R09_R14_REPAIR_2026-09-17/`。只 stage 指定檔案，不做大範圍 add／reset／刪除。
- 文件與程式一律 UTF-8，寫入後檢查沒有 U+FFFD；Windows 主控台的中文亂碼只是顯示問題，以 Python 或 `git show` 驗證。
- 遵守 anti-hardcode 原則：詞表與登錄檔只能是後備或資料來源，需有雙語反例測試；前端不得出現配色 id 或字面色碼。
- 訪客可見的內容不得包含主機、硬體、模型、provider 或費用資訊。
- 可以直接在 `main` 提交；提交訊息結尾加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- 回報時列出修改檔案、對應 FR／AC、執行的指令與 pass／fail／not-run 結果、剩餘風險；未執行的驗收不得標為通過。

## 5. 各階段分派提示

以下每段可直接交給一個 agent，前面附上 §4 共同規則。

### A1 閘道

> 實作 RepoNPC 的 Tailscale Funnel 訪客專用閘道（ADR-047 F0／F2，ADR-048 §4.1–4.2，FR-047，AC-071）。先把 `docs/IMPLEMENTATION_BACKLOG_2026-09-26.md` §3 的待定項寫成契約並更新 `TAILSCALE_FUNNEL_DEPLOYMENT_PLAN_2026-09-24.md`、`SECURITY.md`、`OPERATIONS.md`，再實作：預設拒絕的路由白名單、Pages origin 限定且不帶憑證的 CORS、管理與模型路徑 404、代理後限流與每日上限、真實 SSE 逾時、訪客回應無主機／模型／費用欄位，以及管理端「本機可用／入口已設定／外網已驗證」三種狀態。不要實際啟用 Funnel。測試需涵蓋路徑編碼與大小寫變體、未知路由、非白名單 origin、帶憑證請求。

### A2 回答政策 v2

> 依完成方向契約 §1 實作 FR-043／044（AC-062～065）。取代 `src/reponpc/chat/answers.py` 的 `_PERSON_CLAIM_RE`、整段拒答與逐詞比對：envelope v2 分段 `person | participation | project | inference`、後端渲染 `{{owner}}`、`inflation_terms.yml` 詞表、數字事實檢查、逐段靜默丟棄、envelope 層級錯誤回無匹配回覆、沒有本人陳述時以專案與參與證據回答且不顯示缺口訊息、第三人稱、可收合的「來源」列；同步修改 `service.py` 的 policy prompt 與 SSE payload。測試需含中英文改寫、膨脹詞與編造數字、「其他」「開發工具」等 CJK 誤判反例。

### A3 參與事實

> 依契約 §2 實作 FR-045（AC-066）：新增 `PARTICIPATION` 證據類型與索引步驟、`github_login`（必填、預填）與選填 `aliases` 設定、owner flag、首次與最後 commit 月份及 permalink、`has_visible_commits`、`other_contributors_visible`；不記錄任何次數；API 失敗記為 unavailable 而非零；匿名 REST 需處理限流。讓 A2 的 `participation` 段能以此驗證。

### A4 覆蓋檢查與 FAQ

> 依契約 §3、§4.3 實作 FR-046（AC-067）：發布前的資訊性覆蓋檢查（絕不阻擋發布）；FAQ 產生與審核，動作只有核准／拒絕／重產／改寫成自述（不提供自由編輯）；只有核准項會被匯出或提供；綁定 bundle ID，bundle 變更時顯示「需要重新確認」。FAQ 回答必須通過 A2 驗證器。

### A5 訪客頁與外觀

> 依契約 §4.0–4.6 與 ADR-051 實作 FR-047／050／051／052（AC-068、AC-072～075）：側欄＋頂列＋置中聊天欄版面；`color_schemes.yml` 五套配色（neutral、ocean、forest、sunset、lavender）的明暗色碼，對比不合格即載入失敗並產出對比報告；`color_mode` 與訪客明暗切換（只存 localStorage、無 inline script、CSP 不變）；只有 NPC 跟隨角色並以 stage／plate 保持 3:1；歡迎區選用圖片的私人草稿、真實預覽、焦點／變暗／縮放、套用／取消／移除；管理端「場景」改名「外觀」並提供配色圖庫、模式、訪客切換、進階強調色、重設；GitHub Pages 靜態殼匯出（記錄閘道 origin、manifest hash）、閘道不可達時顯示「休息中」並在瀏覽器內比對已核准 FAQ；卡片連到 Pages 網址。R08（AC-079）：角色候選、卡片預覽與歡迎區圖片草稿只由需登入的同源管理路由提供並帶 `Cache-Control: no-store`，公開路由與匯出一律取不到，CSP 不變。

### A6 內建 embedding

> 依契約 §6 實作 FR-049（AC-070）：`builtin_onnx` adapter（ONNX Runtime CPU、無 PyTorch）服務 bge-m3（1024 維、無前綴）；首次需要索引時的三選一對話框（下載內建模型／改用其他服務／稍後再說，稍後會阻擋建置並說明原因）；來源固定為契約 §6.2 的官方 `BAAI/bge-m3` revision 與 `onnx/` 檔案清單（fp32，約 2.29 GB），對話框顯示的大小由該清單計算，下載需進度、取消、續傳與逐檔 SHA-256 驗證，未點擊不得下載；更換 embedding 前顯示需重建索引；在 zh-TW／en fixture 上量測檢索品質並記錄。不做本機量化。

### A7 模型引導

> 依契約 §7 實作 FR-040／AC-057 修訂（僅管理端）：`model_catalog.yml`（參數量、量化、記憶體估計、是否支援結構化 JSON、最後審核日期，只收錄已實測 envelope 的模型）；後端偵測 RAM／GPU／VRAM／磁碟並顯示 適合／勉強可用／不建議；canirun.ai 連結（不抄資料、不呼叫 API）；Ollama 偵測與明確點擊才 pull；白話錯誤對照；一行狀態摘要；選雲端時的資料揭露。訪客端不得出現任何相關資訊。

### A8 Windows 安裝器

> 依契約 §5 實作 FR-048（AC-069）：PyInstaller onedir（含 onnxruntime、uvicorn 與預建前端）、Inno Setup 個人安裝（免系統管理員權限、開始功能表與桌面捷徑、解除安裝時預設保留資料）、啟動器等待 health 後開啟管理頁並提供「開啟管理頁面」「結束」、使用者資料放在安裝目錄外、SHA-256 與 SmartScreen 說明頁。bge-m3 不打包。在乾淨 Windows 主機（無 Python、無 Docker）驗證安裝、啟動、更新與解除安裝。

### A9 角色美術

> 依 `current-state-2026-09-20` 記憶的「Remaining asset work」完成 R13 剩餘工作：以現有 converter 處理 `PixelNPC` 的 Man 與 Orange 概念圖，逐格檢查 64×64 的邊界、基線與減少動態姿勢；產出 canonical 256×448 PNG、預覽與對照表；補來源與授權紀錄；完成 `core/humanoid` v1 pack 矩陣並接上 composer／manifest，驗證 `public/character.png` 與卡片輸出。不要搬動或刪除 `PixelNPC/`；最終美術需擁有者看圖核可。

### A10 舊修復項

> 依 ADR-052 實作。R11（AC-077）：`GET /api/admin/onboarding/analysis-batches/active` 在沒有進行中批次時，回傳 7 天內結束、仍可重試或重新分析、且擁有者未關閉的最新終止批次並標示為恢復；關閉狀態存在伺服器端，不以 localStorage 為準。R12-B（AC-078）：先量測 ADR-046 passage-vector cache 是否已讓失敗或重啟後的重試免去主要工作，若是就以「已涵蓋」結案並記錄量測；若否，依 `REPAIR_PROGRESS_2026-09-17.md` 的 Option A 做受保護檔案快取，容量與 TTL 沿用 passage cache 機制，任何錯誤都視為未命中並重建。R08 不在此階段（隨 A5）。

### A11 日常維運介面

> 依 FR-053（AC-076）在管理端新增「維護」頁：顯示本機可用／入口已設定／外網已驗證、目前 bundle 與上次備份時間；以既有 `runtime backup` 建立備份並提供下載；從檔案還原前需確認並自動先備份；以既有 bundle pin 回復上一版；立即停止訪客閘道；說明如何以新安裝檔更新、如何在 Tailscale 官方流程關閉 Funnel。不在程式內下載安裝檔，不處理 Tailscale 憑證。

### A12 發布驗收

> 將帳本擴充到 AC-079、更新 `source_identity` 到候選發布提交，逐項以實際證據更新狀態；執行乾淨主機、獨立外網、真實 GitHub Profile、瀏覽器與無障礙矩陣；補驗 UI 卡片下載落盤與瀏覽器開啟本人陳述來源。需要公開入口、GitHub 寫入或 push 的步驟先取得擁有者當次授權；D8 使用者實測由擁有者執行並提供紀錄。

# ChatGPT A5 implementation plan

Retrieved from the in-app ChatGPT conversation on 2026-09-29. Advisory plan; approved specifications and Main integration decisions take precedence. `rtk` is optional by owner instruction.

> 2026-09-30: The remaining work is governed by the [revised resume plan](A5_HANDOFF_2026-09-30.md#revised-resume-plan-2026-09-30). This plan did not assign the FR-047 Pages live-chat request to a batch and left offline matching precision undefined.

[C2C]
STATE: PLAN
TASK_ID: c2c_3037
ITERATION: 0
WORKSPACE: RepoNPC
BASELINE: main@877c6d6
IMPLEMENTATION_OWNER: Luna max
CONTRACT_AND_REVIEW_OWNER: Main
SCOPE: Complete A5 + R08 / AC-079
EXECUTION: NOT_STARTED
NEXT_EXPECTED_STEP: WAIT_FOR_EXECUTION_HANDOFF

1. 本機基準與程式追查結果

目前 main 與 origin/main 同步，ahead=0 / behind=0，沒有 staged 或 tracked unstaged 修改。三個既存 untracked 目錄 %SystemDrive%/、PixelNPC/、RepoNPC_R09_R14_REPAIR_2026-09-17/ 不納入本次工作。

已依 AGENTS 規定順序讀取必要文件，並讀完完成方向契約 §4.0–§4.6。本計畫沿用規格 0.4.6、ADR-048～053，以及 A1／A4 的現有實作；不恢復已退休的角色衍生配色、pack scene hints 或插畫背景設計。

現有可重用能力與實際缺口
範圍	本機程式確認	本次處理
訪客頁	apps/web/src/app/App.tsx 同時包含管理入口判斷與訪客狀態控制；訪客請求使用固定 /api/public/...，離線時停用輸入。	分離可共用的訪客控制器、純呈現元件與資料來源，完成新聊天版面及離線輸入。保留現有取消、重複送出防護與成功對話歷史隔離。
角色與來源列	CharacterRenderer.tsx 已支援任意 canonical sheet、七個既有狀態與 reduced motion；VisitorConversation.tsx 已有可收合來源列。	重用 renderer 與來源呈現，增加舞台、頂列角色、回答 avatar、舊回答靜態影格，不重写角色轉換器或回答驗證器。
外觀資料	config/models.py::CharacterConfig 與 indexing/public_profile.py::CharacterMetadata 尚無 scene；訪客 CSS 仍使用共用 --ui-* 與固定色碼。	增加嚴格 scene 設定、後端解析的明暗 tokens、單一配色 registry 與訪客樣式作用域。
管理預覽	admin/operations.py::preview_config() 回傳角色及 SVG／GIF／PNG 卡片 base64；LocalPublishingWorkspace.tsx 使用此資料預覽與下載。	完成契約要求的受保護資產 URL，覆蓋既有角色候選、卡片，以及新背景草稿；不能只保護新增圖片功能。
公開版本與 FAQ	BundleManager.acquire_snapshot() 已能一起租用 reader、bundle ID、公開目錄；ReviewedFaq.public_payload() 已有 approved-current SQL 篩選及 citation 白名單，但每次呼叫自行取得快照。	匯出共用一份 bundle／FAQ／外觀快照，不能分別讀取中英文後假定版本一致。補上明確核准的問題變體，不開放自由編輯答案。
外觀套用	LocalPublication.prepare() 經過來源解析、完整索引建置及 embedding smoke。	不能把它當作每次外觀套用的實作。 外觀套用必須無模型呼叫、不改寫不可變 bundle，並保留 last-known-good。
靜態資產與分享	A1 的 visitor_ingress.py::_visitor_files() 已檢查 Vite 靜態依賴閉包；sharing.ts 目前只檢查網址形狀；後端 README snippet 仍以 public_base_url 為基礎。	重用 A1 的資產驗證原則，但建立獨立 Pages 訪客入口、公開 export manifest、內容核對及獨立卡片 target。
離線引用	api/public.py::owner_statement() 的本機作者自述來源依賴運行中的後端。	將核准 FAQ 所引用的公開作者自述，以原 revision／evidence ID 對應的靜態來源檔一起匯出；不匯出完整索引或原始設定。

以上是本輪程式查閱結果，不是本輪測試通過聲明。

2. 執行分工與必須先固定的整合原則

Luna max 是單一實作者，以下六批依序交付；不另開多個 worker 同時修改共用檔案。 Main 保留公開契約、認證、CSP、網路邊界、migration、原子切換、整合及驗收判定權。Luna 可以依 Main 凍結的介面實作跨檔 patch，但不能自行變更這些政策。

Main 在第一批建立 docs/A5_VISITOR_APPEARANCE_EXPORT_CONTRACT.md，記錄本計畫的資料形狀、錯誤碼、版本綁定與測試對應。這是既有需求的實作契約，不重新徵求已批准的產品選擇。

三個整合原則必須固定：

外觀版本與證據 bundle 分離。 採用「不可變外觀產物＋原子發布指標」，綁定來源 bundle、角色內容身分及外觀 revision。外觀套用只更新外觀，不連帶發布尚未套用的個人介紹、貢獻或角色候選，也不執行 reindex。真正切換證據 bundle 時，A4 的 FAQ 失效規則照常成立，不能自動搬移 approval。公開讀取、匯出及圖片讀取必須解析到相符快照；不得以舊 revision 假回新版資產。

Pages 網址與 A1 origin 分離但嚴格綁定。 A1 的 pages_origin 仍是精確 origin；A5 另保存完整 Pages URL／base path，以支援根網站及 project Pages。公開 export manifest 記錄必要公開身分，私人驗證 receipt 才保存設定 revision、核對時間等管理狀態。「網址已輸入」「Pages 內容相符」「A1 擁有者回報外網檢查」不能合成一個成功旗標。

三種訪客呈現共用同一組元件。 本機 live、Pages static、管理外觀 preview 共用訪客呈現元件；網路與狀態控制留在外層。管理 preview 不掛載會自行 fetch／呼叫模型的整個 App，也不使用 iframe、data URL 或放寬 CSP 來繞過隔離。

3. 六批實作順序、檔案與交付門檻
批次 1 — Scene 契約、五套配色與可重現解析

目的：先建立唯一資料來源及穩定的 producer／consumer 契約，再改畫面。

Luna 新增：

src/reponpc/scene/__init__.py
src/reponpc/scene/registry.py
src/reponpc/scene/resolve.py
src/reponpc/scene/color_schemes.yml
scripts/build_scene_assets.py

現有接線檔為 src/reponpc/config/models.py、src/reponpc/indexing/public_profile.py。Main 審核 pyproject.toml、apps/web/package.json、Dockerfile 的必要打包／建置接線；沒有實際需要就不改依賴或 lockfile。

實作內容：

五套 neutral / ocean / forest / sunset / lavender 僅在 registry 定義；完整保存十個 token roles、兩種 variant、雙語 labels、版本與 aliases。拒絕重複 ID、缺少 locale、未知欄位／role、非法色碼、alias cycle／dangling alias，以及任何不合格對比。Registry 原色不合格就是載入失敗，不在 runtime 偷修。

後端 resolver 處理自訂 accent、NPC 邊緣與 stage 的對比、必要的 lightness 調整及 plate。角色像素不變，頁面配色不從角色推導，不依 species、pack ID、檔名或 option 名稱分支。需要調整的 accent 必須在套用前回傳實際值與原因。

舊設定／舊公開 profile 缺少 scene 時提供契約預設；不能要求既有作品集先重建索引才能啟動。新 bundle 保存已解析 tokens，使既有產物不因之後 registry 改版而悄悄變色。

**交付門檻：**新增 tests/unit/test_scene_registry.py、tests/unit/test_scene_resolution.py，擴充 tests/contract/test_config.py。產生完整對比報告，包含失敗 pair 的定位。加入未出現在正式 registry 的測試 scheme，證明新增／移除配色不需前端改碼。

生成 fallback 必須接入本機與 Docker 建置。現有 Docker 前端階段是 Node-only，不能直接加入一個不存在的 Python 呼叫；由 Python 階段產生並交給前端，且建置驗證 registry／生成物身分，禁止手動維護第二份色碼。

批次 2 — 私有資產、背景草稿與無模型外觀套用；完成 R08 後端

Luna 新增：

src/reponpc/scene/images.py
src/reponpc/admin/preview_assets.py
src/reponpc/admin/scene.py

必要接線限於：

src/reponpc/admin/operations.py、src/reponpc/api/admin.py、src/reponpc/api/public.py、src/reponpc/api/visitor_gateway.py、src/reponpc/api/visitor_ingress.py、src/reponpc/main.py、src/reponpc/runtime/database.py、src/reponpc/admin/local_portfolio.py、src/reponpc/admin/local_publication.py、src/reponpc/admin/embedding_reindex.py、src/reponpc/indexing/pipeline.py、src/reponpc/cards/production.py、src/reponpc/bundles/archive.py。

先統一受保護預覽資產，再接新背景功能。 角色候選、清理前後版本、卡片各格式與背景草稿都由同源、需有效 owner session 的窄路由提供。不可把 opaque ID 當作授權；不能接受任意路徑。預覽建立／替換／刪除遵守現有同源與 CSRF 邊界，讀取帶 no-store、正確 Content-Type 與 nosniff。原始上傳及未核准候選不能因新增資產服務而進入公開目錄。

背景 routes 依 §4.6 接上：

純文字
POST   /api/admin/assets/scene/background-drafts
GET    /api/admin/assets/scene/background-drafts/{id}
DELETE /api/admin/assets/scene/background-drafts/{id}
POST   /api/admin/scene/preview
PUT    /api/admin/scene
GET/HEAD /api/public/scene-background?rev=N

上傳只接受靜態 PNG／WebP，執行 2 MB、640×360 至 2560×1600、完整容器結構、動畫／polyglot／副檔名與實際格式檢查，再於後端去 metadata、重新編碼。重用 cards/assets.py::inspect_png() 的適用邊界，不把 sprite 尺寸或透明度限制錯套到背景圖片。

一份新上傳替換舊草稿；取消及 24 小時到期會刪除，失效後 URL 也不可讀。套用前，公開 route、A1 gateway 與 export 都不能取得草稿。

PUT /scene 以預期 draft／appearance／bundle／character 身分做 compare-and-swap。驗證成功後才發布 content-hashed 圖片及新外觀 revision；失敗保留原公開版本及使用者其他草稿。草稿設定與發布指標需要可回復的一致性操作，不能「先寫其中一個，另一個失敗就算成功」。Main 固定鎖順序、崩潰恢復與 rollback 行為。

A1 只增加必要的精確公開 route 及對應 HEAD／OPTIONS，不開放 assets/scene/** 或整個 runtime 目錄。新索引建置／reindex 的素材供應路徑只攜帶已套用圖片，bundle 驗證器驗證宣告、hash 與實際內容的一致性。

**交付門檻：**新增 tests/unit/test_scene_images.py、tests/integration/test_scene_publication.py、tests/security/test_preview_assets.py；擴充 runtime、local publication、bundle validation、A1 gateway 測試。必須證明外觀 preview／apply 的模型呼叫數為零，舊 bundle bytes 不變，失敗／重啟不會半發布。Migration 由 Main 分配，不改寫既有 migration。

批次 3 — 共用訪客版面、明暗首屏與真實外觀預覽

Luna 新增：

apps/web/src/app/publicTypes.ts、apps/web/src/app/VisitorApp.tsx、apps/web/src/app/VisitorPage.tsx、apps/web/src/app/visitorData.ts、apps/web/src/app/visitorScene.ts、apps/web/src/app/visitor.css、apps/web/src/features/admin/AppearancePanel.tsx、apps/web/src/features/admin/ScenePreview.tsx、apps/web/src/visitor-main.tsx、apps/web/visitor.html，以及獨立的外部首屏 mode bootstrap。

現有修改檔：

apps/web/src/app/App.tsx、apps/web/src/app/VisitorConversation.tsx、apps/web/src/app/visitorChat.ts、apps/web/src/features/character/CharacterRenderer.tsx、apps/web/src/features/character/CharacterRenderer.css、apps/web/src/features/admin/AdminPage.tsx、apps/web/src/features/admin/AdminWorkspace.tsx、apps/web/src/features/admin/CharacterAssetConverter.tsx、apps/web/src/features/admin/Base64PngCanvas.tsx、apps/web/src/features/admin/LocalPublishingWorkspace.tsx、apps/web/src/i18n/messages.ts、apps/web/src/main.tsx、apps/web/src/styles.css、apps/web/vite.config.ts。

完成側欄／手機 drawer、NPC 頂列、首次提問前 welcome hero、左右訊息 bubbles、來源列與固定輸入列。沿用現有 SSE collector、成功歷史裁切、同步防重送、取消及 stale-response guards，不重寫 grounding。

所有角色位置使用 CharacterRenderer。頂列「休息中」映射既有 offline 狀態，串流回答映射 talk，不新增 sprite rows。只有最新回答 avatar 動畫；舊回答靜態。Reduced motion、模式媒體查詢變更及取消訂閱都要正確處理。

明暗 bootstrap 使用外部 script，在首次繪製前依當前 owner policy決定模式。visitor_mode_toggle=false 必須從首屏起忽略舊 localStorage，不是 React mount 後再改回。選擇不進入 request、cookie、export 或管理 preview 狀態。Main 負責本機入口 HTML 的安全 policy 供應及 A1 精確資產接線，不加 inline script、unsafe-inline 或 unsafe-eval。

外觀圖庫採真實元件的半明／半暗 miniature；preview 包含桌面／手機、角色狀態、reduced motion、前後比較、焦點移動與裁切框、dim／scaling，以及放大／強裁切／忙碌圖片提示。範例對話清楚標示「範例」，不呼叫模型。多個 preview 的 ID、focus、CSS tokens、語言及模式必須互相隔離。

背景只在 welcome hero，文字維持不透明 surface；reset 與移除背景分開。管理 mascot 改用 active character，沒有可用角色才保留 fallback。保留 converter 的必要影格運算，改其資產來源，不重寫轉換／對齊算法。

另外補齊側欄資料流：目前公開 repository DTO 缺少 language／stars／forks。於 src/reponpc/indexing/sources.py、src/reponpc/indexing/github.py、src/reponpc/admin/batch_resolver.py、src/reponpc/indexing/pipeline.py、src/reponpc/indexing/public_profile.py 傳遞既有解析流程取得的公開 metadata 快照；缺值不能偽造為零，不在每次預覽／開頁時新增 GitHub 查詢。Avatar 不得藉此引入任意 URL proxy 或放寬 img-src；沒有安全可用素材時使用明確替代顯示。

**交付門檻：**元件／狀態測試加上真實瀏覽器驗證。Source guard 覆蓋訪客依賴閉包，檢查 scheme ID、字面色碼、任意 CSS keys、管理 chunk 與已退休 scene 欄位；生成 fallback 是明確、可重建的例外，不掃到無關管理配色後迫使整站重寫。

批次 4 — 核准 FAQ 變體、公開靜態匯出及離線比對

Luna 新增：

src/reponpc/sharing/__init__.py
src/reponpc/sharing/manifest.py
src/reponpc/sharing/export.py
apps/web/src/app/offlineFaq.ts

接線修改 src/reponpc/admin/faq.py、src/reponpc/runtime/database.py、src/reponpc/api/admin.py、apps/web/src/features/admin/CoverageFaqPanel.tsx、apps/web/src/app/visitorData.ts、apps/web/src/app/VisitorApp.tsx。

FAQ 不另建第二套答案系統。 重用 A4 已驗證答案與 citation 白名單，增加有長度／數量界限的 owner-reviewed question variants。變體必須參與 revision／review 身分，不得讓變體修改偷偷帶著舊 approval 發布；生成答案仍不能自由編輯。

Exporter 取得同一份 bundle lease、兩種語言 FAQ、角色及外觀快照。FAQ 的內部公開投影應可接受這個已固定的 bundle 身分，避免兩次 public_payload() 讀到不同版本。建置期间 bundle、FAQ、外觀或分享設定變更時，依凍結契約重核對或回衝突，不能產生混合產物。

輸出包含獨立訪客 HTML／CSS／JS、雙語公開 JSON、角色、卡片、已套用背景、必要作者自述來源檔、.nojekyll 及公開 export-manifest.json。只追蹤 visitor entry 的允許依賴，不複製整個 dist、不使用原始 index bundle manifest、不輸出 SQLite、設定 YAML、模型身分或 runtime 資料。

Manifest 使用 canonical bytes、排序路徑與逐檔 hash；排除自我雜湊循環。相同輸入須得到相同 manifest，封裝檔也控制時間／排序等非決定性因素。匯出結束才提供下載，先完成公開 schema、秘密 canary、路徑／symlink、總量與參照完整性檢查。1 GB 為匯出大小上限；頻寬軟限只作說明，不能宣稱已量測。

本機作者自述只匯出核准答案實際引用的公開 evidence，保存原 revision／evidence ID，並由後端產生靜態連結。不能把本機來源偽裝成 GitHub commit，也不能整份匯出 reponpc.yml。

離線 matcher 以版本化資料與一般化 lexical／fuzzy 規則處理問題及核准變體；測試後固定 threshold／ambiguity margin。高信心只顯示既有核准答案；低分、歧義或無匹配只提供建議，不生成新文字、不呼叫 embedding、不上傳輸入。沒有核准 FAQ 時輸出空集合，不阻擋作品集發布。

保留線上 fresh-approval 檢查。已知被拒絕或已知 bundle 不相符的內容，不可在請求失敗後又當成有效 fallback。 對完全離線的既有匯出，只能保證它是匯出時核准的快照，不能聲稱能即時撤回已下載內容。

**交付門檻：**新增 tests/integration/test_site_export.py、apps/web/src/app/offlineFaq.test.ts，擴充 A4 FAQ／security 測試。驗證根網站及 project base path、空 FAQ、變體審核、Unicode／CJK／英文反例、歧義、tamper、切版競態，以及主機停止後作者自述來源仍可讀。

批次 5 — Pages 核對、origin 綁定與 README 卡片目標

Luna 新增：

src/reponpc/sharing/pages.py
apps/web/src/features/admin/PagesSharePanel.tsx

修改 src/reponpc/api/admin.py、src/reponpc/admin/operations.py、src/reponpc/cards/render.py、apps/web/src/features/admin/LocalPublishingWorkspace.tsx、apps/web/src/features/admin/GitHubShareGuide.tsx、apps/web/src/features/admin/sharing.ts。

在現有「預覽、試聊與分享」加入「設定 Pages URL → 匯出 → 手動上傳 → 核對 → 取得卡片 Markdown」流程。匯出不要求 Funnel 已啟用、模型正在運作或 FAQ 全部答得出來；但需要合法分享設定及可讀的公開快照。

Pages verifier 是明確 owner action，使用固定目的地主機與有界 HTTPS transport。限制精確配置的 github.io origin、正規化 base path、redirect、DNS／連線時位址、回應大小與期限；不接受私人網段、憑證、任意 host 或 redirect 擴權。Main 獨立審查，不借用允許私人模型服務的網路政策。

核對必須以本機保存的預期 export hash為基準，取得指定入口與 manifest，確認 URL／origin／base path／bundle／外觀／FAQ 內容綁定。不能把遠端自己回傳的 hash 當作預期答案。同 origin 的其他 project page、被修改的入口、錯誤 manifest、過期 receipt 都不能通過。

Pages 的連線政策只容許配置的 gateway，請求明確 credentials: "omit"。靜態站需要的精確 gateway 連線授權不得擴散成管理頁 CSP 放寬；靜態部署未實際交付的 header 也不得列成已驗證。

卡片影像與點擊目標分開：沿用 reponpc-card.gif 手動上傳引導，A5 Markdown target 使用相符的 Pages URL，不使用私人 public_base_url，也不指向會隨主機停止而消失的 Funnel 頁面。既有明確的 operator-managed 路線保留相容性，但不能冒充 A5 已核對路線。

**交付門檻：**新增 tests/security/test_pages_verification.py；擴充 sharing.test.ts、tests/web/GitHubShareGuide.test.tsx、tests/web/LocalPublishingWorkspace.test.tsx 及 README snippet 測試。測試僅使用合成 transport／loopback fixture，不上傳 GitHub、不啟用 Funnel、不寫 README。

批次 6 — Main 獨立整合、反例測試與證據收尾

Main 擁有並建立：

tests/security/test_a5_review.py
tests/browser/a5_server.py
tests/browser/check-a5.js
tests/browser/a5-visitor-evidence.json
release-evidence/a5/local-checks.md
release-evidence/a5/contrast-report.json

Luna 的 focused tests 不能取代 Main 的新反例。Main 透過真實 production factory、私有 API、runtime store、bundle lease、exporter、production 前端及靜態伺服器驗證；外部 GitHub／模型 transport 才使用 fixtures。

A5 browser harness 要啟動獨立靜態網站與可停止的 gateway，不是把所有 fetch 換成前端 mock。需要 origin／host mapping 時由測試環境處理，不能放寬 production Pages validator。

Main 同步更新 README.md、A5 實作契約、docs/IMPLEMENTATION_BACKLOG_2026-09-26.md、docs/TECHNICAL_SPEC.md、docs/ACCEPTANCE_CRITERIA.md、docs/SECURITY.md、docs/OPERATIONS.md、reponpc.example.yml、tests/browser/README.md。docs/DECISIONS.md、docs/A1_FUNNEL_GATEWAY_CONTRACT.md、docs/A4_COVERAGE_FAQ_IMPLEMENTATION.md 只補實際受影響的決策／整合說明，不改寫歷史證據或提前宣告正式驗收通過。

4. 必須通過的驗收矩陣
Gate	必須觀察到的結果
AC-072／074：配色與角色	五套 × 明暗 × 契約指定非貓 fixture；所有文字 pair ≥4.5:1、非文字 pair ≥3:1，NPC edge／stage ≥3:1 或按契約使用 plate。改檔名／option 名稱不改結果；未知測試 scheme 不需改前端；registry 載入失敗能精確定位。
AC-073／075：真實 preview	preview／live／export 的同設定 tokens 相等；圖片只在 hero；focus、dim、scaling、前後比較及裁切框有效。草稿未套用不改公開頁；替換、取消、到期、套用失敗、重啟／rollback 都沒有半發布。
AC-079：全部私有預覽	匿名、過期／偽造 session、跨 origin、猜 ID、公開主入口、A1 gateway 與 export 都取不到候選／卡片 preview／背景草稿。合法讀取 no-store，CSP 不因預覽放寬；對齊與下載仍可用。
AC-068：靜態／即時切換	靜態 server 在 gateway 停止後仍能顯示 profile、專案、角色及核准 FAQ；輸入可在瀏覽器比對，無模型呼叫。恢復後不重送舊問題、不混用 bundle、不把 429 或一般請求失敗一律解釋成離線。
A4 相容性與引用	四種審核動作、staleness、rewrite continuation 保持；variants 有核准身分；只匯出 approved-current。作者自述靜態來源與外部 exact-commit 引用正確，未引用／未核准內容與診斷 canary 不外洩。
Pages／manifest／target	根／project path 資源皆可讀；hash 與重複匯出一致；錯頁、錯 origin、redirect／DNS 攻擊、缺檔、tamper、過期設定全部拒絕。A5 Markdown 不含私人管理位址或 provider 資訊。
首屏與可及性	zh-TW／en；375／768／1024／1440；200% zoom；鍵盤、drawer focus／Escape／return、無重複 ID、無橫向溢出、來源列、status announcement、reduced motion。mode toggle 關閉時舊儲存選擇從首屏起無效。
A1 回歸	封閉路由、HEAD／OPTIONS、credentials rejection、精確 CORS、admin hostname 隔離、限流／預算、SSE heartbeat／取消／worker 保留及 start／stop／restart 原有保障維持。

若合法 fixture 顯示 stage／plate 條件或首屏／CSP 條件不能同時滿足，Main 必須保留最小反例處理契約實現問題；不能修改角色像素、降低對比、放寬 CSP 或刪掉反例取得通過。

執行閘門

由 Codex／Main 在隔離環境執行，沿用專案要求的 rtk 包裝：

純文字
rtk proxy uv run ruff format --check src tests scripts
rtk proxy uv run ruff check src tests scripts
rtk proxy uv run mypy src/reponpc

rtk proxy uv run pytest --ignore=tests/smoke/test_container.py --ignore=tests/smoke/test_visitor_gateway_container.py -p no:cacheprovider --basetemp .test-tmp/a5-full -q

rtk proxy pnpm run web:check

rtk proxy uv run pytest tests/smoke/test_container.py tests/smoke/test_visitor_gateway_container.py -p no:cacheprovider --basetemp .test-tmp/a5-container -q

rtk git diff --check

新增的 registry generation／source guard／Pages production build 必須實際接入上述檢查，不能只放一支未被執行的 script。瀏覽器另依新增 a5_server.py 與 check-a5.js 的文件化流程執行，記錄實際命令及結果。若既有 dist 有 ACL 問題，使用新建置目錄，不改使用者目錄權限或沿用舊產物冒充新 build。

5. 交付與停止條件

每批交付列出 exact changed files、對應 FR／AC、執行命令及 exit code、pass／fail／not-run、產物 hash、剩餘風險。Main 先比對實際 diff 與允許範圍，再跑自己的測試；不接受僅有「implemented」或 worker 自報全綠。

所有測試使用獨立臨時 runtime、合成來源／模型、可辨识 canary。禁止 push、GitHub／README 寫入、公開部署、Funnel 啟用、真實模型呼叫及 live runtime／資料庫修改。 不擴展到 A6／A8／A9／A11 或 P1-04 重構。

完成可記為 A5＋R08 本機實作與本機驗證完成；真實 Pages 上傳、獨立外網 Funnel、GitHub Profile 點入、乾淨主機及未執行的完整瀏覽器／輔助科技驗收仍由 A12 如實追蹤，不以這次 fixture 結果替代。

下一步：等待 Codex 的執行交接；收到 EXECUTED 後，重新透過 RepoNPC connector 讀取實際 diff、執行摘要與已釋出的輸出進行獨立審查。

## ChatGPT review 1 — 2026-09-29

The same actual ChatGPT conversation returned `[C2C] STATE: BLOCKED`, task
`c2c_3037`, iteration1, after read-only source/diff/execution-output inspection.
It ran no tests and made no edits. Main verified concrete findings before repair.

| Finding | Required correction | Owner |
|---|---|---|
| R1 | Preserve valid immutable GitHub owner-statement citations; copy only index-confirmed local-origin statements; reject forged identities. | Luna, Main independent boundary checks |
| R2 | Capture this export's receipt in its transaction; reject a different post-commit receipt before returning ZIP headers. | Main |
| R3 | Private admin HTML must remain readable when public appearance assets/wrapper/recovery are invalid; visitor stays fail-closed. | Main |
| R4 | Bound existing locale-only status/FAQ GET headers and body; cancel on teardown and never revive known-invalid FAQ after timeout. | Luna, Main independent checks |
| R5 | Complete already approved immediate preview, real miniature radio gallery, preview state controls, accent adjustment values, image/focus interaction and configured answer animation. | Luna, Main native review |
| R6 | Declared retired aliases preserve immutable historical scene tokens and expose current successor only to editing. | Luna, Main reopened profile/export check |

After all permitted repairs, freeze a per-file SHA-256 inventory including new
files and run fresh Python/Web/build/registry/source-guard/Docker gates on that
candidate. Browser evidence must distinguish actual observations, simulated
conditions and unavailable checks. Earlier counts remain evidence for their
recorded earlier candidate. Static chat POST remains stopped pending the owner's
explicit payload/destination answer; this review is no authorization for it.
No A5 push, deployment, Funnel activation, real provider/GitHub call or live
runtime mutation is permitted by this task.

## ChatGPT review 2 — 2026-09-30

The same in-app ChatGPT conversation returned `[C2C] STATE: REVIEW`, task
`c2c_3037`, iteration 2, verdict `CHANGES_REQUIRED`. It inspected current
source/diff and the 125-file SHA inventory, but ran no tests and did not
independently recompute every digest. Full local test logs were withheld after
automatic approval review rejected their external release; ChatGPT used only
the safe summary and repository source. R1/R2/R3/R4/R6 original counterexamples
were accepted as repaired. R5 remains open with F2/F3 below.

| Finding | Concrete boundary to repair | Owner |
|---|---|---|
| F1 | One approved FAQ must not answer a changed signed value, percent, unit or one-character technical identifier. Preserve exact/approved variants and safe typos. | Luna matcher; Main independent cases |
| F2 | Appearance profile must match source bundle, effective character revision and locale; refetch/cancel on source switch and disable Apply while unmatched. | Luna panel; Main browser/integration check |
| F3 | The 1440/375 preview probes must follow their own logical widths, unaffected by host `@media` or viewport units. Compare against real visitor geometry at both host widths. | Luna scene/visitor CSS; Main native check |
| F4 | Link text must use an existing role guaranteed at least 4.5:1, including custom accent `#898989`. | Luna visitor CSS; Main computed contrast |
| F5 | No-image hero uses scheme surface; NPC stage remains separate. Transparent background image compositing must match the resolver's surface assumption. | Luna visitor CSS; Main geometry/contrast check |

Main reproduced seven F1 English/Traditional Chinese single-FAQ negatives as
seven expected failures before the repair; the existing safe positives passed.
Static live-chat POST remains stopped pending explicit owner payload/destination
authorization. Native ZIP download, actual 200% zoom, browser-observed gateway
stop/recovery, pointer drag and manual contrast completion remain unverified.

## ChatGPT review 3 — 2026-09-30

The same in-app conversation returned `[C2C] STATE: REVIEW`, task `c2c_3037`,
iteration 3, verdict `CHANGES_REQUIRED`. This was an independent source review;
ChatGPT did not run tests or recompute the full 125-file inventory. It accepted
the source fixes for F2, F4 and F5. F1 and F3 remain open:

| Finding | Exact remaining counterexample | Owner |
|---|---|---|
| F1 | A single approved `這個上限是5%嗎？` incorrectly answers `這個上限是5嗎？`; `Does this project use C for data analysis?` incorrectly answers the R variant. Number extraction misses Han-adjacent digits, and the identifier guard omits one-letter uppercase terms. | Luna matcher; Main exact independent cases |
| F3 | The hidden 1440/375 geometry probes now match visitor geometry, but the visible desktop/phone preview still follows the admin panel width. At a 375px admin host, its selected desktop view becomes a phone layout. | Luna visible frame; Main native visible geometry check |

Main inserted both exact F1 cases into the single-row independent test. Before
repair, the focused run failed exactly these two cases (19 passed, 2 failed).
The candidate digest supplied for review 3 is a historical snapshot and must
be replaced after the F1/F3 repairs. Static live-chat POST remains stopped;
this review does not authorize its conversation payload or destination.

## ChatGPT review 4 — 2026-09-30

The same in-app conversation returned `[C2C] STATE: REVIEW`, task `c2c_3037`,
iteration 4, verdict `CHANGES_REQUIRED`. It accepted the previous exact F1
examples and the F3 fixed-width, scaled visible preview; it did not run tests
or independently rehash all 125 files. Two further source problems remain:

| Finding | Exact remaining counterexample | Owner |
|---|---|---|
| F1 continuation | A single approved `這個專案使用C進行資料分析嗎？` still answers the R variant; `Does this endpoint accept values <5?` still answers the `>5?` variant. The identifier parser merges Han/Latin text, while normalization erases comparison operators. | Luna matcher; Main independent exact tests |
| F3 continuation | A 375px logical phone preview in a 1440px admin host shows the menu, but opening it renders the sidebar as an in-flow sticky element instead of the real phone's overlay drawer. | Luna reference-layout CSS; Main native open/close/focus checks |

Main expanded the independent single-row FAQ test with these exact sentences,
spaced Chinese, `<`/`>`/`<=`/`>=` combinations and `user_id`/`userid`.
Before repair, six cases fail and 22 pass. A disposable native fixture
reproduced the drawer failure: opening the preview menu changed the hero's
position within its frame by the 704px in-flow sidebar height, while the real
375px visitor page keeps its hero stationary and uses a fixed overlay drawer.
The previous Web339/build results apply only to the review4 candidate.
ChatGPT also correctly noted that Docker includes the frontend build, so the
old Docker2 result cannot prove a fresh container image from changed Web input;
rerun the two container smoke checks on the final frontend candidate or report
them as not rerun. Static live-chat POST remains stopped pending explicit owner
authorization for the payload and destination.

The same Luna max worker repaired both source findings. Main independently
confirmed all 28 single-row cases, 353 whole-Web tests, format/lint/type/build,
registry/source guard, and the native frame-contained drawer at host widths
1440 and 375. A fresh Docker/Compose smoke run built the updated frontend and
passed both tests. The 62 backend Python input hashes remain unchanged. Review5
must inspect the new candidate; no source acceptance is inferred from local
checks. Static live-chat POST remains stopped pending the owner's exact
payload/destination authorization.

## ChatGPT review 5 — 2026-09-30

The same actual in-app ChatGPT conversation returned `[C2C] STATE: REVIEW`,
task `c2c_3037`, iteration 5, verdict `CHANGES_REQUIRED`. It accepted the
review4 exact FAQ counterexamples and phone-preview drawer source repair. It
ran no tests and did not independently rehash the 125-file inventory. One P1
FAQ source issue remains: comparing unordered operators and underscored
identifiers after punctuation removal loses their position. In a single-row
approved FAQ, `x<5 and y>5` incorrectly answers `x>5 and y<5`; likewise
`Does user_id override userid?` incorrectly answers the reversed operands.
Main added both exact pairs, their reverse directions and English/Chinese
endpoint-swapping controls to its independent corpus. Before repair, six
cases fail and 28 pass. The same Luna max worker owns only the shared offline
matcher and its tests; Main owns independent checks and integration. Preserve
safe exact/approved variant/typo behavior. Fresh Web353 and Docker2 metadata
belong to review5's historical candidate; rerun after source changes. Static
live-chat POST remains stopped pending explicit owner payload/destination
authorization, and A5 cannot be declared complete.

## ChatGPT review 6 — 2026-09-30

The same in-app ChatGPT conversation returned `[C2C] STATE: REVIEW`, task
`c2c_3037`, iteration 6, verdict `CHANGES_REQUIRED`. It accepted review5's
ordered comparison/underscored-identifier fix and the phone drawer. Its one
remaining source finding is an exact-admission bypass for other technical
separators: `src/config.py` incorrectly matches `srcconfig.py`, and
`user.name override username` incorrectly matches the reversed operands.
The source also permits `x<y` versus `y<x` through fuzzy transposition.
Main added the two exact source cases, reverse directions and related path,
dot and variable-comparison controls to the single-approved-row corpus. All
six new cases failed before repair; the 35 earlier cases passed. The same Luna
max worker owns the shared matcher and its tests; Main owns the independent
corpus and final checks. The repair must preserve case-insensitive technical
terms such as EngineC/enginec, approved variants and ordinary safe typos.
Review6's 364-Web/2-Docker result is a historical snapshot until the new
source passes fresh gates. Static live-chat POST remains stopped pending the
owner's explicit payload/destination authorization.

The same Luna max worker completed the shared matcher repair. Main independently
passed the six new negatives, 75 focused FAQ tests, 377 whole-Web tests,
format/lint/type/build, registry/source guard and a fresh 2-test Docker/Compose
smoke run. The owner then requested a pause and [full handoff](A5_HANDOFF_2026-09-30.md).
There is no iteration7 ChatGPT review of this final local change. Review6 is
the last independent source verdict; the final repair remains locally verified
and A5 remains incomplete pending the static-chat owner decision.

## Step 4 closing review 1/3 — 2026-10-01 (iteration 7)

After the owner-approved A/B implementation and profile contrast correction,
the owner deleted the expired connector and explicitly authorized rebuilding
and pairing its replacement with the original read-only scopes. Doctor and an
actual workspace_info call in the original Project conversation passed.
The same conversation's source review returned `CHANGES_REQUIRED`: one defect,
one design finding, zero scope additions. It did not run tests or independently
rehash the 130-path candidate inventory.

- **D1 / defect:** default Fetch redirect handling could forward a chat body
  after 307/308, including after the bounded 413 retry. The shared POST now uses
  native `redirect: "error"`; all local/static callers and the retry pass through
  that boundary. No new endpoint, payload field, header or destination is added.
- **E1 / design:** the backend's alphanumeric-only duplicate rule rejected
  distinct exact-v2 variants (internal spaces/separators), preventing explicit
  approval. As a recurring FAQ category this was escalated under the handoff
  stop rule. The owner selected **align the precise rule and fix it**. The
  existing backend normalizer now matches the approved browser v2 rule,
  including ECMAScript whitespace. Revision, bundle, CSRF, length/count limits
  and withdrawal/reapproval remain in place; no fuzzy answering is restored.

Both invoked skills were applied before editing: input language is open but
equality has an explicit contract; HTTP redirect policy and the normalization
character set are closed platform/protocol rules. Existing shared functions,
Python stdlib and native Fetch suffice. No dependency, keyword exception,
generic framework or configurable policy was added.

Before repair, four actual loopback 307/308 tests failed, the real admin variant
workflow returned 422, and 12 of 16 normalization/structure counterexamples
failed. After repair the focused Web45 and Python50 checks passed. A separate
checker uses the installed TypeScript compiler and actual exported API payload:
bilingual pending exclusion/reapproval/exact admission/negative input and 12
Python/JavaScript normalization cases passed. Full gates passed: Python1655/2
existing Windows skips, Web389/38, mypy91/Ruff219, frontend/guard/registry and
Docker2. Closing review 2/3 is next; A5 is still incomplete.

## Step 4 closing review 2/3 — 2026-10-01 (iteration 8)

The original ChatGPT conversation returned `SOURCE_VERDICT: ACCEPTED — D1/E1`,
zero new application findings, zero scope additions and zero design reopenings.
It closed both source findings and accepted the actual API/export-to-TypeScript
test design. It ran no tests/browser operations and independently rehashed no
files. A/B remain closed; no new owner decision is required.

M1 is a new P2 evidence defect: the 132-path inventory omitted
`apps/web/src/app/visitorChat.ts`, `apps/web/src/app/chatAdmission.test.ts` and
`docs/COMPLETION_DIRECTION_CONTRACT_2026-09-26.md`. Main confirmed these are the
only missing paths when comparing all owned tracked/untracked changes with the
inventory. Repair is limited to evidence: union the complete owned Git set with
explicit safe evidence/memory, reject missing/extra/duplicate paths, and hash
every expected file. Preserve unrelated user directories. Capture before/after
hashes around fresh affected frontend/container checks; no application or test
code changes are needed. Source acceptance is separate from this candidate
coverage check. No third source review is required for a metadata-only correction.
A5 remains incomplete pending native/manual/A12 acceptance.

Main completed M1 without source/test changes: 127 owned Git paths plus eight
explicit safe paths, 135 total, zero missing/extra/duplicate entries. A complete
pre-gate snapshot was captured; fresh Web389/38, format/lint/type/build93 and
Docker2/33.44s passed, then all135 file hashes and the owned path set matched.
Source/test files already captured in review2 also matched, so the full Python
result remains bound to unchanged inputs. The two newly covered frontend files
are directly covered by these new Web/container gates. Input/proof digests and
commands are recorded in resumed evidence. Subsequent edits only record this
result in documents/memory. Step4 is closed locally; no third source review or
new owner decision is needed for this metadata correction.

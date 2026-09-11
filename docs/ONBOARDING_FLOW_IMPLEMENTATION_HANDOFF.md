# RepoNPC 0.2.3：先接模型，再分析專案 — 實作交接

日期：2026-09-10（Asia/Taipei）  
狀態：具體流程與行為邊界已獲擁有者確認；本輪只更新文件，尚未實作本次修正。  
依據：Technical Specification 0.2.3 §2.9／§11.6、ENGD-011、ADR-030、FR-041／FR-042、AC-058～060。

## 1. 背景、批准與接手方式

RepoNPC 是自託管、單一擁有者的公開 GitHub 作品集。擁有者挑選專案、確認自己的貢獻；訪客向 NPC 提問時，回答必須有可核對的固定 commit 證據。繁體中文／英文、個人貢獻確認、無模型工具權限、公開 repository only、受保護管理入口、不可變索引與失敗保留上一個可用版本仍是必要條件。

前一包 0.2.2 已加入模型連線、Chat profile、Embedding profile 的程式，但使用者在一般引導仍直接走到「分析」，遇到模型不可用，畫面只給重新檢查／重新分析。2026-09-10 原始碼確認模型設定只顯示在進階模式；引導沒有模型步驟。這是整合問題，不能把已有三個管理面板視為首次使用流程完成。

擁有者在看過六步流程、手動路線、兩種模型需求及分析／正式索引分離說明後，明確回覆「好」。本包已批准該方向，不需再次詢問相同問題。當前授權是更新規格、記憶與交接文件；執行程式修正需在後續實作任務進行。Figma 仍略過；GGUF／Hugging Face runtime 不在本包。

接手先按 `AGENTS.md` 讀核心文件，再讀本文件。`MODEL_SETUP_IMPLEMENTATION_HANDOFF.md` 保留前一包設計及安全要求，但其 2026-09-09「尚未實作」表格不是最新程式狀態。以本文件的 2026-09-10 調查為起點，重新檢查 working tree，不重建已有 registry／秘密儲存／batch／reindex 模組。

工作樹有大量前人未提交變更，不 reset、刪除、覆蓋或順手格式化無關檔案。`rtk` 可選。`PROJECT_CONTEXT.md`、`OWNER_REVIEW.md`、`IMPLEMENTATION_PLAN.md` 及 local acceptance ledger 在本 checkout 被 Git 忽略；本交接文件與正式規格刻意保留必要上下文，使另一個 clone 不依賴對話或臨時截圖。新交接文件需隨文件變更提交；本輪沒有建立 commit。

## 2. 已核准的使用者流程

歡迎頁不計入進度，說明產品結果，提供「設定 AI 並開始」與「先手動建立作品集」。沒有選定 provider、模型或分析同意的預設值。

| AI 主流程 | 內容與主要操作 | 出口 |
| --- | --- | --- |
| 1. 設定 AI 模型 | 先「分析與回答模型」，再「搜尋模型」；選服務、填 API／需要時填 key／填模型名、測試、確認使用。 | 兩種角色皆有通過測試且明確選用的 revision；可改走手動。 |
| 2. 選擇展示專案 | GitHub 帳號或專案網址、公開 metadata 勾選、確認選取。 | 至少確認一個專案；確認不自動分析。 |
| 3. 分析專案 | 概覽專案數與選用模型；「開始分析」；各專案進度、成功／失敗、重試／取消。 | 可帶成功結果繼續，失敗項目手動補寫；不要求全部成功。 |
| 4. 確認我的貢獻 | 分清「程式碼可確認的資訊」、「AI 推測」與「我實際做的事」。 | 個人敘述經本人確認；沒分析也可手寫。 |
| 5. 完成基本資料 | 名稱、簡介、招呼語與既有雙語欄位。 | 既有必填與雙語驗證通過。 |
| 6. 預覽與完成草稿 | 編輯、驗證、預覽、複製／下載，列出發布尚缺能力。 | 完成草稿；不等於已儲存 GitHub、已發布、已啟用索引。 |

手動路線為「選專案 → 貢獻 → 基本資料 → 預覽／草稿」，顯示四個適用步驟。AI 步驟是略過，不能打勾成測試通過。之後隨時可補模型設定，保留原資料並返回來源位置。第一次 AI 主線先設定模型；這不禁止手動 discovery 或既有草稿使用者直接編輯專案。

模型用途白話說明：

- 分析與回答模型：理解專案、協助整理介紹，並回答訪客問題。
- 搜尋模型：把程式碼整理成可搜尋的資料，協助找到回答依據。

服務可相同，模型能力仍分開測試。現行分析會建立 passage embeddings、產生 query vector、檢索，再呼叫 chat，不能只測 Chat 就宣稱可分析。聊天模型能回應不代表支援 embeddings。

「測試」只送合成小樣本；「確認使用」選定角色；「開始分析」才允許已確認 repository 的 source/model 工作。這三種動作不可合併成開頁即執行。已有有效選擇時顯示安全名稱及選用狀態，允許沿用或編輯；不要求再次輸入已儲存 key，也不回顯私有 URL。

## 3. 目前程式證據與必修項

以下是閱讀程式的結論，並非 live provider／完整瀏覽器驗收。以路徑與符號定位，避免依賴容易漂移的行號。

| 現有位置 | 現況 | 實作責任 |
| --- | --- | --- |
| `apps/web/src/features/admin/AdminWorkspace.tsx` | `embeddingProfileView` 受 `(!guidedView || advancedMode)` 限制。 | 模型設定成為一般引導可到達的主要畫面，進階 YAML 不作為入口。 |
| `apps/web/src/features/admin/AdminPage.tsx` | 已組裝 `ModelConnectionPanel`、`ChatProfilePanel`、`EmbeddingProfilePanel`；引導 props 沒有模型設定視圖／返回動作。 | 共用受保護請求與表單能力，接入 model step／contextual recovery，避免複製第二套 secret 表單。 |
| `apps/web/src/features/admin/guidedOnboarding.ts` | 七個 step，`CONFIRM_SELECTION` 直接進 `analysis`；沒有模型步驟／AI 或手動 intent。 | 新增模型步驟、路線與安全返回位置；舊步驟名稱按語意遷移，不用陣列索引硬位移。 |
| `apps/web/src/features/admin/GuidedOnboardingView.tsx` | 歡迎算一步；技術文案仍有 facts／inference／repository；analysis 有單件與準備批次操作。 | 六步 AI／四步 manual；單一開始分析、直接修復入口、白話文案、窄螢幕當前步驟。 |
| `AdminPage.tsx::refreshProviderStatus` | 使用 `/api/public/status.model.ready` 作為 guided readiness。 | 改為 server-owned analysis capability，不拿公共 readiness 當首次分析必要條件。 |
| `AdminPage.tsx::prepareAnalysisBatch/createAnalysisBatch/analyzeRepository` | preflight/create 與單件路徑分開，單件操作未以前置模型設定作有效引導。 | 單一 UI intent orchestration；保留既有後端 batch／legacy adapter 契約與 idempotency。 |
| `AdminPage.tsx::refreshEmbeddingProfiles` | 開頁載入 installed list，失敗 catch 成空陣列。 | setup metadata 載入不得隱含探測／安裝；明確動作再列模型，錯誤不偽裝成空列表。此項是前包殘留義務。 |
| `src/reponpc/admin/model_connections.py` | 新增 connection registry、revision、受保護 secret store。 | 沿用並檢查既有 secret/egress/revision 規則，不恢復 retired OAuth vault。 |
| `src/reponpc/admin/chat_profiles.py`、`embedding_profiles.py` | 已有 CRUD/probe/activate；embedding public activation 綁 bundle。 | 增加邏輯上獨立的 analysis selection，不能把未建公開索引的 candidate 偽裝成 public active。 |
| `src/reponpc/main.py::_configure_provider_lifecycle` | 缺 Chat 或 Embedding 就把 runtime、chat service、limits 設 None。 | analysis 的依賴可在乾淨啟動後由選定模型動態建立，並保留全局 admission controls。 |
| `main.py::_replace_runtime_chat` | 只在已有 `ProviderRuntime` 時替換 chat。 | 首次接入不應只更新 DB／顯示已啟用但分析 runtime 仍 None。 |
| `main.py::_configure_embedding_reindex` | 需已有 registry、manager、runtime、operations、rate limiter。 | 拆除首次 public index 準備對「已有可用 public runtime」的循環依賴；保持既有驗證與原子切換。 |
| `main.py::_configure_admin` | batch readiness 只檢查 runtime/limits 存在；cache identity 從 settings 的 model 名建立。 | readiness、preflight、execution 使用同一 selected revision pair；cache 不再只讀啟動時環境值。 |
| `src/reponpc/admin/onboarding.py::_provider_dependencies/analyze_resolved_repository` | 分析要求 runtime + limits，建立 temporary index、embed、hybrid search、generate。 | 透過固定 pair 供應依賴；繼續重用 index/evidence trust rules；analysis index 不發布。 |
| `src/reponpc/admin/operations.py::activate_embedding_profile` | 有 coordinator 則 queue，否則只接受 registry compatible activation。 | 首次 analysis selection 不走 public activate；公開啟用仍走既有檢查。 |
| `src/reponpc/admin/batch_execution.py`、`batches.py`、`batch_runtime.py` | 已有 durable lifecycle 與 model/cache identity。 | 綁定 revision pair、stale plan、in-flight／retry／restart，不能每個階段解析「現在選的模型」。 |
| `src/reponpc/runtime/database.py` | 包含前包新增 migration。 | 重新查最大 migration，必要時 append；不改歷史 migration，不分配假定版本號。 |
| `tools/release_audit.py` | 文件 coverage 和 ledger validator 都仍只要求 AC-001～052。 | 實作時一併擴到 AC-060 並測缺漏／重複 ID；舊 auditor 綠燈不等於新功能驗收。 |

前包的缺口不是全部在本次逐項審核。避免宣稱 0.2.2 已完整驗收；本包主線若依賴它的未完成能力，需先修復並附證據。Figma／另造 runtime／重畫訪客 RPG 不得拿來取代主線驗收。

## 4. 能力與狀態：防止新的循環依賴

| 能力 | 必要條件 | 不需要 |
| --- | --- | --- |
| 管理與手動草稿 | 合法 owner session；各自的欄位／本機驗證 | 模型、公開 bundle、writeback token |
| 公開專案探索 | owner session；GitHub 匿名容量與固定來源政策 | 模型、公開 bundle、GitHub read token |
| 模型測試 | 明確角色與連線／模型；owner 點擊；安全 egress 與 bounded probe | repository、公開 bundle |
| AI 專案分析 | 經測試並明確選用的 chat/embedding pair；確認的 repository；runtime storage、limits、batch admission 與 GitHub 容量 | 公開 bundle、public active embedding、writeback、重新啟動 |
| 公開訪客問答 | 正式 active models、驗證相容的 active bundle、storage/provider/cost readiness | 引導所在步驟或瀏覽器保存的通過旗標 |
| GitHub 寫回／發布 | 既有配置與獨立授權、索引建置／發布路徑就緒 | 不可從 analysis 成功自動推定 |

**重點決策：analysis pair 與 public active pair 必須可區分。** 兩者可以明確引用相同 profiles，但改分析 pair 不應偷偷更換已公開網站的模型或 index。不得「為了解鎖分析」直接把 `embedding_profiles.active` 設為 true，跳過 bundle 檢查。

推薦 role view 語意：未設定 → 已儲存待測試 → 已測試待選用 → 已選用；必要時標示服務暫不可用。公開 index 的待建立／建置中／已啟用另行呈現。這是 view model 概念，不是授權直接改名既有 embedding status enum。既有 `reindex_required` 可與「此 revision 可供 analysis」並存。

Readiness 是可變的觀察：成功 probe 不保證未來請求成功。表單測試結果需綁定 revision、角色、模型與 embedding semantics。相關欄位改變則失效。UI 只讀取安全 metadata；真正工作前，後端仍驗證權限、pair 一致性、資源 admission 與可解析性。不要為每次開頁或返回設定而自動生成合成測試。

## 5. H0 必須先定稿的實作契約

以下是已核准方向內的準備交付，不是聲稱現有 API 已提供。先補入 normative spec 的具體 DTO／端點／錯誤／持久化與 migration，再寫依賴它的程式。不要只留下抽象「新增 readiness」給接手者猜。

1. **安全 capability view：** chat／embedding 各自 selected profile ID、connection revision、tested identity、safe reason、可採取 action；聚合 analysis eligibility；公共 bundle readiness 分開。不得回傳 saved endpoint、key、secret path 或 provider body。優先 additive authenticated admin contract，public status schema 不變。
2. **analysis selection：** 單一 owner 的兩個 role references，選擇必須指向仍有效的 probe revision。可各自選用，僅兩者有效才形成可執行 pair。規定 optimistic revision／atomic update、刪除所選 profile guard、清理 active/in-flight references、失去 key 的安全失敗。用途標籤清楚區分「用於分析」與「網站目前使用」。
3. **snapshot 與 plans：** 明確 selection generation / pair identity；preflight/create 的一致性檢查；UI 隱藏 prepare 不代表跳過它。原 `ANALYSIS_PLAN_STALE` 可否涵蓋模型變更需文件與契約測試一致。若 preflight 過期、pair／repo set 改變、另一 batch 啟動，停止並提示，不無限重建新 plan。
4. **依賴生命週期：** 可重用既有 `ProviderRuntime` 型別，但 analysis 供應者與 public 供應者生命週期不能繼續混為一個 mutable 全局選擇。共享必要的 global semaphore/fairness/limits，不能因拆 runtime 產生兩份各自放行的容量上限。running item 持有 frozen provider handles；credential rotation 後保留既有 reference 或安全失敗，不轉向新主機。
5. **durability：** 在既有 runtime SQLite 中持久化安全 references；不新增 DB service 或 server-side portfolio draft。migration 需兼容現有 host-managed、managed、public active profile/bundle。已有明確 pair 可沿用；無法證明舊設定是顯式選用時顯示待確認，不自動挑第一筆或隱含預設。沒有歷史 probe 證據就顯示待測試。
6. **瀏覽器狀態：** 定義新 serializable intent/step/return destination 與 migration version。只保存規格允許的公開草稿資料及必要 UI 導覽；模型能力與 credentials 不信任瀏覽器。舊 key 遷移成功前不先刪除；非法／未知內容不渲染、不整包回傳或記錄。詳見下節。
7. **錯誤與容量：** 沿用 bounded probes、API/response/input/並行限制與 stable errors；若需新增正式 error/DTO，先定稿。401/session expiry 走現有恢復、429 等待明確 retry，不藉「一鍵開始」做自動多次付費生成。

若任何選擇需要改變公開 schema、分析演算法、provider fallback、身份驗證、發布拓撲或新增費用，先列差異再提決策。本文件已批准的流程與 analysis/public 分離不需重複請示。

## 6. 返回、遷移與錯誤情境

| 起點／事件 | 目標行為 |
| --- | --- |
| 全新 AI 開始，兩個模型都無 | 留在模型步驟，從空白服務選擇開始；沒有 Ollama 不可用紅色錯誤。 |
| 只有 Chat 成功 | 明確指出搜尋模型還缺，提供該表單；AI 尚不可分析，手動仍可用。 |
| 測試成功但尚未選用 | 主要動作「確認用於分析」；不把 success probe 當 active/public ready。 |
| 舊 `intro` 或 `repositories` state | 保留 account／選取；顯示 AI／manual 路線選擇或缺模型補設，不能強迫清空重來。 |
| 舊 `analysis` state 且模型缺失 | 保留選取，顯示「設定模型」／「手動繼續」；設定完成返回分析待開始，不自動請求。 |
| 舊 `contributions`／`profile`／`review`／`draft` | 保留既有允許欄位、確認文字與進度；允許繼續手動完成，不因新增步驟倒退成全新流程。 |
| 返回修正模型／測試失敗／取消 | 保留先前選用與公開草稿，清理新 key；回來源位置，無破壞式 reset。 |
| 修改 repo/ref/include/exclude | 只失效相關 plan/result；移除專案才移除其 contribution；保留其他專案和 profile。 |
| 更換 model/connection revision | 新工作使用新 pair；舊 job 保持舊 pair 或安全失敗。舊結果標明來源；不覆蓋已確認個人敘述。 |
| 有 running batch 時去設定／重載 | 從 server reconcile 同一 job；返回不重建，不暗中取消。需要更換時等下一批；取消由明確動作發出。 |
| 部分成功、部分 provider/GitHub 失敗 | 成功結果可檢閱；失敗項目重試或手動補寫。generation 已派送而中斷仍需明確 retry confirmation。 |
| 舊 raw YAML 無法映射 | 保留 advanced 內容與錯誤，不能用空白 guided draft 覆寫。 |
| logout／session expiry | 遵守既有 draft/session 清理規則；清除 ephemeral key/URL。資料保留承諾不跨越既有 logout 安全邊界。 |

使用者按「開始分析」可自動串接同一次意圖下的 preflight 與 create；但不能在返回模型設定、model test、React effect 重跑或 browser reload 時重新消費該意圖。產生一次 idempotency key，並以相同有效 plan 重用以處理網路回覆遺失；先查 server active batch，不能再開第二份。

## 7. UI／文案與無障礙落點

- 一屏聚焦當前任務。模型設定放在第一步與常駐「模型設定」入口；不要把整套管理面板長頁塞在 wizard 上方。
- 每個角色顯示用途、safe model label、狀態、主要動作。API key 為獨立 write-only 控制，不進 guided serializer。Model listing 是可選輔助，不把 catalog 空清單當沒有可用模型。
- 分析頁將「準備批次分析」內部操作隱藏在 orchestration；一般使用者看到「開始分析」。保留進度、取消與需要時的重試／暫停恢復；此包沒有批准刪除既有 batch API 或 scheduler。
- 失敗不只給 `MODEL_UNAVAILABLE` 或「重新檢查」。使用角色與原因導向的文字，例如「搜尋模型尚未設定」／「已選模型目前無法連線」，旁邊直接提供設定／測試／重試與手動繼續。
- 小螢幕顯示「第 2 步，共 6 步：選擇展示專案」與可展開步驟列表；桌面可完整 stepper。不可用歡迎／略過步驟灌完成率。Back／Edit 與當前焦點需一致。
- 保留語意 heading、label、fieldset、button、aria-current、描述關聯、status/alert；切換步驟與返回表單後焦點可預期，失敗公告不連續打斷讀屏。新表單不能把 key 出現在錯誤或測試 snapshot。
- 繁中英文同時修改；長模型名／繁中文字體／375～1440 px／200% zoom／reduced motion 一起驗證。前包 source 有疑似亂碼字串，實作時以檔案編碼與實際畫面核對，不把 terminal 顯示誤差當作已證實瀏覽器問題。

## 8. 有序實作與出口

| 階段 | 工作 | 出口條件 |
| --- | --- | --- |
| H0 契約與基線 | 讀核心 docs，盤點實際 migrations/tests，定稿 §5，更新 normative spec。 | 角色 selection/public active、DTO/error、retention、舊 state migration 不再有未定義語意。 |
| H1 後端首次接入 | 獨立 analysis selection/runtime/admission，無模型起始可配置，保留 public reindex 安全。 | 從 production application wiring 跑 clean no-model/no-bundle -> 選兩模型 -> analysis，無 restart／DB 手改。 |
| H2 Batch 一致性 | preflight/create/cache/runtime 固定相同 pair，stale/rotation/restart/in-flight 檢查。 | 模型切換不可污染 current job/cache，無自動 retry／fallback，公共服務不變。 |
| H3 引導與恢復 | 模型 first-step、manual intent、一次開始分析、contextual return、safe persisted-state migration。 | 六步 AI／四步 manual 和舊 state 都走得通，未就緒不發出分析，表單秘密不進草稿。 |
| H4 整合驗收與文件 | 實際 browser flow、security、bilingual/accessibility、full relevant gates；auditor/ledger 覆蓋新 IDs。 | AC-058～060 有 dated evidence，AC-053～057 殘留義務已核對；不能僅有 registry unit pass。 |

所有階段保留可檢閱的小修改；不整包重寫 AdminPage 或另一套 batch engine。先確定 clean-bootstrap 問題已解，才以 UI 完成宣稱主線完成。

## 9. 必要測試與交接證據

| 情境 | 證據重點 | AC |
| --- | --- | --- |
| 乾淨首次啟動，不提供任何模型／public bundle | health/admin 可用、无預選／implicit model requests；同一程序完成 create/test/select/analyze。 | 053、058、059 |
| Chat only／Embedding only／已測未選／不支援 capability | 缺哪個角色清楚；AI 不誤放行，manual 無模型也可完整匯出。 | 054、058、059 |
| 同 gateway／不同 gateway／no-key Ollama | 各自模型與 credentials 正確，不能拷到別的 destination；listing unsupported 仍可測。 | 054、055、059 |
| 已有 public A，analysis 選 B | B 的成功／失敗不改 public A；public publish/activate 仍獨立驗證。 | 056、059 |
| Preflight 後切模型／connection revision／repo set | stale rejection；無 provider call 或 cache 錯用；需新的明確開始。 | 045、046、060 |
| Running batch 中切模型、輪替 key、重啟 | 原 revision 或安全失敗；不自動使用新 pair；已派送 generation 不重送。 | 045、046、055、060 |
| 每個舊 step 的 v1 storage fixture | 允許欄位保留，未知資料處理有界；已完成 draft 不強制再跑 AI。 | 040、060 |
| 返回／取消模型設定、partial failure、manual 切 AI | 正確 return target、保留公開資料、不重送分析、不丟成功結果。 | 058、060 |
| 同次 Start 雙擊／回覆遺失／重載 | 一個 durable job、一次 generation intent；與 legacy one-item 路徑共用 active guard。 | 039、045、058 |
| API session/CSRF/URL/secret canaries | 只接受已授權輸入；response/storage/log/export 無秘密；public YAML schema 1 不變。 | 024、025、035、055、060 |
| 真正瀏覽器操作與讀屏／keyboard | 從歡迎到預覽走完整主線、手動路線、missing-role recovery，附 viewport/locale/focus 證據。 | 023、040、057、058、060 |

沿用測試位置：

- `tests/integration/test_model_connections_api.py`、`test_provider_lifecycle.py`、`test_embedding_profiles.py`、`test_embedding_reindex.py`、`test_analysis_batch_api.py`、`test_runtime_database.py`。
- `tests/unit/test_chat_profiles.py`、`test_model_connections.py`、`test_batch_execution.py`、`test_batch_runtime.py`、`test_batches.py`、`test_release_audit.py`。
- `apps/web/src/features/admin/guidedOnboarding.test.ts`、`GuidedOnboardingView.test.tsx`、`AdminWorkspace.test.tsx`、`AdminPage.test.tsx` 及模型面板測試。
- 既有 auth/local-launch、source isolation、provider privacy/security regression；若改 bootstrap/Compose/launcher，同步相關 config/CLI/smoke tests。

可新增跨模組測試，但不能以 fixture 預先塞好 `ProviderRuntime`／public bundle 後聲稱證明了首次建立。Provider/GitHub transport 可用 deterministic fixtures；必須走真實 application factory、registry、selection、batch orchestration。另行記錄 live provider 與 clean-host 證據，不混用。

實作完成應執行 repository 選定工具鏈：

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
pnpm run web:check
git diff --check
```

Browser runner 先讀現有配置再決定實際指令；component render tests 不是瀏覽器證據。變更部署時另跑 Compose config、container smoke、clean-host；變更模型 semantics 時保留相應 retrieval 評估。沒有跑或失敗的項目必須明列。AC-058～060 初始 not-run，文件批准不是 pass。

## 10. 本次調查與文件驗證的界線

2026-09-10、修改本次文件前已跑：

```text
uv --cache-dir .tmp/uv-cache run --no-sync pytest tests/unit/test_chat_profiles.py tests/integration/test_model_connections_api.py tests/integration/test_provider_lifecycle.py -q --basetemp .tmp/onboarding-flow-review -p no:cacheprovider
pnpm --dir apps/web exec vitest run src/features/admin/GuidedOnboardingView.test.tsx src/features/admin/guidedOnboarding.test.ts src/features/admin/AdminWorkspace.test.tsx
```

結果為 backend **8 passed，1 個 Starlette TestClient/httpx 棄用警告**；frontend **33 passed**。這是當前既有功能的局部基線，未重跑完整 suite，未呼叫真實 provider／GitHub，也沒有啟動瀏覽器驗證本提案。使用者截圖是問題證據，不是另一本指令文件。

本次文件變更後的版本／引用／結構／diff 與文件契約檢查另記於最終交接結果；不得用上面的歷史基線冒充本次功能修復證據。0.2.2 與前包的大量未提交變更繼續保留。

## 11. 下一位實作者第一個工作

從 H0 開始，沿 `main.py` 啟動與 selection callbacks 畫出 analysis/public dependencies，定稿安全 capability view 與 analysis pair 持久化契約，然後做 H1 的 clean-bootstrap integration。只有這條鏈成立，再接六步引導才不會把使用者帶進另一個「測試成功但分析仍不能用」的死路。


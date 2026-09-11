# RepoNPC 0.2.2 模型設定與前置引導實作交接

> **2026-09-10 狀態更新：** 本文件是 ADR-029 的設計與安全背景。連線、Chat/Embedding profile 與管理面板程式已出現在 working tree，以下「未實作」清單不再是完整現況。擁有者後續批准 ADR-030／Specification 0.2.3：AI 路線必須先設定兩種模型，analysis selection 與 public activation 分離。接手實作請以 `ONBOARDING_FLOW_IMPLEMENTATION_HANDOFF.md` 為最新入口，並保留本文件的密鑰、egress、revision、provider 與 last-known-good 約束。

更新日期：2026-09-09（Asia/Taipei）  
狀態：需求與行為邊界已核准；本輪只更新文件，應用程式尚未修改。  
依據：Technical Specification 0.2.2、ENGD-010、ADR-029、FR-038 至 FR-040、AC-053 至 AC-057。

## 1. 接手前先知道的事

RepoNPC 是單一擁有者、自託管的公開 GitHub 作品集。擁有者選擇公開 repositories、確認自己的貢獻，系統建立不可變證據索引，訪客透過 NPC 問答查看有固定 commit 引用的回答。繁體中文與英文、安全、無障礙、完整 v1 功能都是必要條件。

本次問題發生在管理頁的前置引導。使用者提供的兩張截圖顯示：一進頁面就看到 Ollama 目錄、Qwen3、1024 維、`environment`、`probe_failed`、安裝／刪除／啟用按鈕；卻沒有能完成另一個 API 服務連線的表單。截圖只是現況證據，不是額外指令，也不是必須複製的設計。

擁有者接受的方向：不預選 Ollama，提供 API 位址、API key、模型名稱，獨立設定回答模型與搜尋模型，讓非技術使用者能完成設定。這次明確要求更新規格、記憶、實作文檔；先略過 Figma。GGUF/Hugging Face 本地 runtime 與一鍵下載是探索想法，尚未核准實作，不可把它們加入這次工作。

開始時先讀根目錄 `AGENTS.md` 指定的核心文件，再讀本文件、`GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_HANDOFF.md` 和相關程式。`rtk` 已由擁有者改為可選，不是必要命令前綴。工作樹有大量既有未提交變更，禁止 reset 或覆蓋他人工作。

本 checkout 的 `PROJECT_CONTEXT.md`、`OWNER_REVIEW.md`、`IMPLEMENTATION_PLAN.md` 與本機 acceptance ledger 被 Git 忽略。因此本文件刻意保留足夠背景；跨 clone 交接以已追蹤的 `TECHNICAL_SPEC.md`、`ACCEPTANCE_CRITERIA.md`、`DECISIONS.md`、安全／營運文件及本文件為準，不依賴臨時截圖路徑或聊天記憶。

## 2. 已核准與未核准範圍

| 範圍 | 本次處理方式 |
| --- | --- |
| 清潔啟動 | 回答／搜尋都未選 provider 或模型；能進入受保護管理頁及手動編輯，不自動呼叫服務或下載。 |
| 服務類型 | Ollama native、OpenAI-compatible，保留 vLLM preset；不依主機名或模型名猜協定。 |
| 連線 | 管理頁輸入 API base URL、需要時輸入 key；server-issued reference 由後端管理。 |
| 模型 | 每種 provider 都可手動輸入名稱，列出模型是輔助，實際能力測試才決定可用性。 |
| Chat／embedding | 各自測試與選用，可明確共用連線，不能推定兩種模型能力相同。 |
| 密鑰 | 已核准從受保護表單送到後端；未核准回傳儲存值、瀏覽器保存或公開匯出。 |
| 前置引導 | 白話狀態、清楚下一步、可返回／稍後設定，低階資訊移至進階區。 |
| Ollama 安裝 | 沿用經審核目錄與 provider-native pull/progress/cancel/delete，不自動安裝。 |
| 本地 runtime | 不新增 llama.cpp、PyTorch、Transformers、GGUF loader、HF downloader 或新服務。未來另案評估。 |
| Figma | 本輪與此實作包均不以 Figma 為前置依賴。 |
| 發布架構 | 不新增公開模型 port、雲端中繼或自動上傳 key 至 GitHub Actions。 |

ADR-029 是先前環境變數限定規則的窄幅修訂。其餘規則仍有效：公開 repository only、模型無工具／shell／檔案／任意網路權限、backend 產生引用、無 provider fallback、同源部署、私有管理入口、GitHub writeback token 與模型／匿名讀取隔離、bundle 驗證後才原子啟用。

## 3. 現有程式與實際缺口

以下是 2026-09-09 的程式閱讀結果，不是新功能通過測試的宣告。路徑相對 repository root；行號會隨既有變更移動，請依符號定位。

| 路徑／符號 | 現況與接手重點 |
| --- | --- |
| `apps/web/src/features/admin/EmbeddingProfilePanel.tsx` | 初始 `ollama`、`qwen3-embedding:0.6b`、1024、`environment`；submit 固定 `query: `／`passage: `。Ollama 只能從目錄選，其他 provider 雖有文字欄位，卻沒有 URL/key。直接顯示內部狀態；啟用按鈕只接受 `ready`，須核對是否擋住需重建索引的候選。 |
| `apps/web/src/features/admin/AdminWorkspace.tsx` | authenticated `embeddingProfileView` 放在 guided flow 前；需改成任務導向的模型設定入口，避免長技術面板佔據初始畫面。 |
| `apps/web/src/features/admin/AdminPage.tsx` | 擁有認證、profile requests、目錄／installed-model 載入、guided state 與 sessionStorage。既有安裝列表失敗被轉成空列表；需區分沒有模型與連線失敗。模型密鑰不可加入 guided draft serializer。 |
| `apps/web/src/features/admin/GuidedOnboardingView.tsx`、`guidedOnboarding.ts` | 延用選取、手動繼續、返回與選取變更局部失效機制；模型設定往返不得清掉貢獻文字。 |
| `apps/web/src/styles.css` | 有通用及 guided 樣式，模型面板缺少完整專用結構。先改善 admin 結構與元件樣式，不連帶重畫訪客 RPG。 |
| `src/reponpc/api/admin.py::EmbeddingProfileRequest` | 已有 CRUD/probe/activate/model operations；目前 dimension 必填，connection_reference 預設 environment。新增連線契約前先拆清 public DTO 與 private credential input。 |
| `src/reponpc/admin/embedding_profiles.py::EmbeddingProfileRegistry` | 已有 CRUD、probe、activation、reindex recovery 與目錄；不是空白模組。保留單一啟用、active delete guard、失敗回復測試。 |
| `src/reponpc/admin/embedding_reindex.py` | 已有重建／切換協調器；接入 candidate connection revision，不另寫一套 bundle lifecycle。 |
| `src/reponpc/admin/model_operations.py` | 已有 Ollama pull 背景作業；需將目標明確綁到所選 connection，不能抓列表中第一個 Ollama host。 |
| `src/reponpc/main.py::_environment_embedding_provider` | 只接受 `connection_reference == "environment"` 且 provider 等於 environment provider。這是「表單有多 profile，實際只有一組連線」的主要限制。 |
| `main.py::_configure_admin`、`_configure_provider_lifecycle`、`_configure_bundle_lifecycle` | 建立環境 profile，chat 由環境設定建構，多處寫死 E5 prefixes。需統一以選定 revision 建立 provider，不可只改 UI。 |
| `src/reponpc/providers/` | Ollama/OpenAI-compatible chat、embedding、HTTP transport、runtime interfaces 已存在。vLLM 沿用 OpenAI-compatible。先沿用契約，再修 listing/health 與連線解析。 |
| `src/reponpc/config/environment.py` | 有 `SecretValue`、secret-file collision／permission 驗證；embedding 仍預設 Qwen3/1024/localhost。需要明確 unconfigured 語意，不能用假模型值撐過啟動驗證。 |
| `scripts/start-reponpc.ps1`、`.env.example`、`compose.yml` | 有 provider/model defaults 與 secret mounts；無模型啟動必須同時修這些消費者與環境解析。保留 loopback grant、PID 驗證、未知 port owner 不終止等行為。 |
| `src/reponpc/runtime/database.py` | 目前已含 0.2.1 migrations 14/15。先重查最新 schema，再分配新 migration；不得改寫歷史 migrations。 |
| `src/reponpc/cli.py` | `runtime check/backup` 與 `bundle status/verify/pin/unpin` 已存在。需補新 connection/key-store restore 覆蓋，不要再次建立同名 command groups。 |
| `src/reponpc/admin/batch_runtime.py`、`batch_execution.py`、`batches.py` | 模型切換要保留每個批次的 model identity、cache key 與 generation retry boundary；不把舊請求切到新模型。 |
| `tools/release_audit.py`、`tests/unit/test_release_audit.py` | acceptance 範圍仍硬編到 AC-052；後續規格已擴到 AC-060。舊 audit 通過不代表新契約完成。 |

0.2.1 已移除 `admin/oauth.py` 與 `cryptography` 依賴。若採用受審核的加密套件，須用 uv 重新明確加入、鎖版與掃描；不能假設原本 OAuth vault 可用，也不能恢復舊 OAuth/PAT 表或設定。

## 4. 使用者流程與資訊架構

第一屏保留作品集設定主線與簡潔的模型狀態入口。模型狀態分成回答模型、搜尋模型，可各自設定，也能稍後處理。不要在未選服務前顯示 Ollama 目錄或安裝按鈕。

模型子流程：選服務 → 填 API／key／模型 → 測試 → 檢視結果 → 明確選用。每一步能返回；取消保留先前已儲存服務，清除新輸入 key；回作品集保留 public draft。設定未完成不能阻止手動撰寫／驗證／預覽／下載。

| 主流程文字 | 進階／診斷資訊 |
| --- | --- |
| 回答模型 / Chat model | chat provider capability、envelope、context limits |
| 搜尋模型 / Search model | embedding、dimension、normalization、task/prefix identity |
| 測試連線 / Test connection | bounded capability probe、safe error code、request ID |
| 可以選用 / Available to use | 測試成功，尚未改變 active selection |
| 建立搜尋索引 / Build search index | reindex_required / reindexing、候選與 active bundle |
| 目前使用 / In use | 已通過該角色啟用規則的 revision |
| 無法連線／重新測試／編輯設定 | authentication / network / timeout / unsupported capability 分類 |

不要把 probe 成功、模型下載完成、索引完成、公開發布完成合併成同一種「完成」。Chat 換模型不必重算 embeddings；embedding 換模型通常要重建。手動輸入模型名始終可用；model list 應是可編輯選擇器的輔助，而非限制可用模型的唯一來源。

UI 採安靜的工作區：穩定導覽、欄位對齊、適當間距、清楚的主要動作、失敗狀態旁的復原動作。優先用既有 React/CSS 模式；必要圖示使用既有或受支援圖示庫，不自行畫工具 SVG。不要用巢狀卡片、行銷 hero 或巨大標題裝飾管理頁。驗證中英、長模型名、窄螢幕、縮放、焦點、讀屏與 reduced motion。

## 5. API／資料契約準備

下列是供第一個實作步驟定稿的建議，不是已存在的端點或已部署 schema。已核准的是規格 11.5 的行為與信任邊界。先將完整 request/response/error/遷移／key-store 格式補入 normative spec，再修改依賴它們的程式。符合 ADR-029 的例行內部選擇不需重複取得同一授權；若超出本文件範圍則依 AGENTS.md 說明差異後提請決策。

### 5.1 建議資料分工

| 物件 | 建議欄位／責任 |
| --- | --- |
| Connection | server ID、display name、protocol/preset、source=host-managed/managed、revision；私有 endpoint 與 secret reference 留後端。 |
| Credential input | 顯式 retain / replace / remove；replace 才攜帶 write-only api_key；create 可明確 no-key。空白不等於刪除。 |
| Chat profile | ID、connection revision、model ID、已驗證 capability、候選／active 狀態、測試時間。 |
| Embedding candidate | 沿用 registry；尚未 probe 的 dimension 可未知，不填假 1024；正式 identity 只在 sample/preset 驗證後形成。 |
| Safe view | IDs、display labels、key_configured、endpoint_configured、safe status/reason、模型名；不含 stored key、URL、secret path。 |
| Activation record | expected revision、候選／先前 profile/bundle、完成或失敗狀態；能處理競爭與 crash recovery。 |

建議沿用 `/api/admin/embedding-profiles` 系列，新增有界的 `/api/admin/model-connections` 管理與模型列表，以及獨立 `/api/admin/chat-profiles` test/activate 功能。路徑與名稱在步驟 M0 定稿，勿讓這張建議表與 OpenAPI 成為不同來源。既有 API migration 要記載舊 request shape 接受／拒絕方式與相容窗口，不可默默把 `environment` 解讀成 URL。

### 5.2 必須定稿的語意

1. 所有寫入、測試、列模型與啟用必須有 owner session；會消耗上游容量或改變狀態的操作需 CSRF／same-origin。只有明確動作發出上游請求，開頁只讀安全 metadata。
2. 新 base URL 綁協定與完整 base path，`/v1` 只拼一次；key 只附加在經驗證目標的授權 header。不要接受任意 header 字典、shell command 或下載 URL。
3. HTTP 私有來源須有顯式選擇與 host egress policy。處理 IPv4/IPv6、DNS rebinding、metadata IP、redirect、timeout/bytes；不能只檢查 URL 字串後讓 transport 自己重新解析到另一個 IP。
4. Key/endpoint input 與 response DTO 分離。變更目的地不可沿用 stored key；共享 connection 的編輯建立新 revision，不直接修改其他 active profiles。清理等到沒有 active/previous/in-flight references。
5. 選 model list 不立即測試；沒有 listing 支援時仍可手動測試。401／429／timeout 不可轉成空清單掩蓋錯誤。能力測試可通過而 listing 不可用，但只有實際成功的能力可被標記可用。
6. Chat test 用固定合成提示及 bounded envelope validation，embedding test 涵蓋 query/passages。Dim 可量測，prefix／pooling／task semantics 不可由向量猜測；preset 或進階設定必須明確，unknown 模型不得強加 E5 prefixes。
7. Candidate save 不消耗模型容量、不下載、不重建、不發布。Test 不能 activate。Embedding activate 必須能從已測試但需要 reindex 的狀態進入既有 coordinator，失敗保留舊版本。
8. 定義列模型／連線數／secret input bytes／probe deadline／並行／revision retention 的有界限制，沿用現有 provider/global controls。數值及 stable errors 在 M0 記錄，不能只留在 UI。
9. 定義無設定、完整 host-managed、部分 host-managed、managed 已啟用與環境變更的優先序。持久化明確選擇優先，錯誤不 fallback；升級不能抹掉舊 profiles／bundles，未曾確認的隱含 default 不成為新下載同意。
10. 公開 YAML schema 1 仍要求 embedding descriptor。無模型的手動草稿可保留既有或明確標為示例的 template descriptor，以支援本機驗證／匯出；它不得成為 runtime provider 選擇或 readiness 證據。實際 build 前須以明確選定且驗證過的 identity 取代並檢查。不要擅自增加 null descriptor 或改 schema，也不要把示例偽裝成已設定模型。

## 6. 密鑰儲存、遷移與發布限制

推薦優先評估「受審核 authenticated encryption 套件 + 獨立 host-protected master key」，避免自製密碼學。必須能在 Windows 評估與 Linux/container 中運作；OS secret store 可用但不應成為未說明的跨主機備份障礙。M0 明確選定封裝、權限、key generation、持久化位置、rotation 與 recovery 程序。

初次本機啟動可以由受信任 launcher 建立保護材料；不可由 public browser endpoint 建立／取回 master key。既有 ciphertext 存在而 key 缺失時不得重生 key 覆蓋資料。正式部署的 key 保護與備份須能在 documented prerequisites 中完成，不將一般使用者卡在不明白的「encryption not configured」錯誤。失敗時 manual/host-managed 路徑仍可用。

遷移涵蓋乾淨資料庫、0.2.1 schema、現有 environment profile、active/previous bundles、無密碼 loopback owner 與 production owner。增加新 schema 前備份，故障需 transaction rollback；舊 schema 不能讀新資料時，rollback 使用舊 image + migration 前完整 backup，不任意刪表。新 managed connection secrets 不得併入 retired OAuth/PAT migrations。

index builder 和 runtime 必須共用 frozen public identity，但不能經 public YAML、release bundle 或 browser export 傳 key。GitHub-hosted runner 無法直接連接使用者 localhost；這是現有 UXD-003／發布拓撲決策，不是連線表單能解決的問題。現有程式含本地 reindex coordinator，但這不自動代表本地發布已核准。確認各路徑的邊界，維持既有發布流程；跨主機連線與 secret provisioning 未完成時，顯示明確 publishing blocker 並保留草稿／舊索引。不可為了通過測試偷偷把模型 port 公開或轉用雲端模型。

## 7. 執行順序與出口條件

| 步驟 | 交付 | 完成條件 | 目前狀態 |
| --- | --- | --- | --- |
| D0 文件交接 | 規格 0.2.2、ADR-029、記憶、此文件 | 需求、排除範圍、追蹤關係明確 | 已完成文件變更；不代表應用功能完成 |
| M0 定稿契約 | DTO、端點、狀態、錯誤、限制、key-store/egress、遷移與來源優先序 | 更新 normative spec 與相容說明；所有對外語意明確 | 未開始 |
| M1 安全連線基礎 | store、revision resolver、write-only API、host-managed bridge | AC-055 攻擊／故障／復原測試通過；未啟用新 UI 前先建立安全邊界 | 未開始 |
| M2 Provider 與角色生命週期 | optional listing、實際 probes、chat selection、embedding/reindex integration、cache identity | AC-054/056；兩個不同 endpoints/keys 同時可用，舊請求／bundle 不受失敗影響 | 未開始 |
| M3 無模型啟動 | loader、launcher、examples、health/admin、provider not-configured | AC-053；無預選／隱含 API call，保留顯式舊設定 | 未開始 |
| M4 引導介面 | 任務導向模型頁、欄位、狀態與 recovery、與 guided draft 整合 | AC-057；兩語、返回、key 清理、model failure/manual path | 未開始 |
| M5 完整驗證與交接 | migrations/security/browser/build/backup/live-provider evidence、文件與 ledger | AC-053 至 057 有實際結果，既有相關 AC 不退步 | 未開始 |

M0 可先整理 wire-contract 草案與 reversible internal decisions，不需重新問「是否同意 API 位址/key 表單」。只有新 runtime、hosted dependency/費用、公開管理／provider 網路、未批准發布拓撲、保密邊界放寬或規格同層矛盾才需要明確新決策。這份文件不要求啟動多 agent campaign。

## 8. 驗證矩陣

| 面向 | 至少驗證的案例 | AC |
| --- | --- | --- |
| Bootstrap | 無模型、有顯式 env、部分設定、舊 managed profile、重啟、local grant／production login | 024、049、053 |
| API gateway | `/v1`／自訂 prefix、model list 支援／404／405／501、typed model、chat-only、不同 chat/embed key | 015、054 |
| Provider errors | 401／403、429 retry、timeout、malformed payload、model missing、invalid vectors、無 fallback | 016、054 |
| 密鑰 | 建立、保留、替換、移除、換 host/protocol/path、shared revision、no-key、storage 不可用 | 055 |
| Network | private/public IPv4/IPv6、DNS rebinding、metadata target、redirect header 洩漏、userinfo/query/path | 055 |
| Migrations | clean／upgrade／fault rollback、active/previous/in-flight references、key 遺失／tamper／restore | 047、055、056 |
| Lifecycle | chat 原子切換、embedding reindex fail/cancel/race/restart、cache identity、private builder 不可達 | 030、031、046、056 |
| UX | 中英、375/768/1024/1440、200% zoom、keyboard/focus/screen reader/reduced motion、long labels | 023、040、057 |
| Privacy | response/log/error/DOM-after-submit/storage/YAML/bundle/export/snapshot 中 canary 不存在 | 025、035、055 |
| GitHub regression | 410 retirement、anonymous resolver 無 Authorization、writeback 隔離、manual continuation | 051、052 |

沿用並擴充：`tests/integration/test_embedding_profiles.py`、`test_embedding_reindex.py`、`test_provider_lifecycle.py`、`test_runtime_database.py`；`tests/contract/test_environment.py`、`test_local_launcher.py`、provider contracts；`tests/security/test_admin_security.py`、`test_local_admin_launch_security.py`；provider unit tests；`EmbeddingProfilePanel.test.tsx`、`AdminPage.test.tsx`、`AdminWorkspace.test.tsx`、guided reducer/component tests。

使用 repository 既定工具，不另換套件管理器：

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
pnpm run web:check
uv lock --check
docker compose config --quiet
uv run pytest tests/smoke/test_container.py
git diff --check
```

`apps/web` 的 `format` script 已是 `prettier --check .`，沒有 `format:check`。Browser scripts 需先查現有工具與可執行方式，再把實際命令／瀏覽器版本／viewport／結果記錄到 handoff；不得把 semantic DOM unit tests 當作 Playwright 或真人讀屏證據。Live gateway/Ollama/vLLM 只用擁有者指定服務與非敏感測試，不能用單一 mock 宣稱所有中轉站相容。

`tools/release_audit.py` 及 ledger validator 目前仍只驗 AC-001 至 AC-052。依 0.2.3 實作時擴充到 AC-060，維持 legacy AC-041 至 043 的退場標記，確保缺少新 AC 時會失敗。新 AC 初始為 not-run，不因文件批准或舊測試通過而改成 pass。

本輪已在本機 ledger 加入 AC-053 至 AC-057 的 not-run 列，沒有改寫歷史 source/environment 或把舊證據升格；這份 ledger 被 Git 忽略，接手 clone 若沒有它，必須依規格建立相同未驗收狀態。

## 9. 歷史證據與本次證據的界線

先前 assistant 回覆的 `612 passed, 2 skipped` 與 Docker 不可用是舊記憶。最新 credential-removal handoff 記錄 2026-09-09 Python `695 passed, 2 skipped, 1 warning`、Web Vitest `67 passed` 加獨立 local-launch `6 passed`、local Docker smoke `1 passed`、Compose config 通過。這些是前一工作包的記錄，本輪未重跑，不能證明 0.2.2。

Clean Linux host、live provider/GitHub、完整瀏覽器／無障礙仍是 release 工作；即使新模型設定完成，也不能直接宣稱 v1 released。歷史 ledger 的 environment/source identity 與個別 blocked reason 可能落後，必須依新 evidence 更新，不把舊環境測試改寫成新環境通過。

本文件更新只需做文件關聯、版本／ID／路徑、diff 與既有文件契約測試。應用功能測試要等 M1–M5 真正實作；最後交接附實際變更檔案、命令結果、AC 對應與 remaining work。

本輪文件驗證（2026-09-09）：

- `uv --cache-dir .tmp/uv-cache run --no-sync pytest tests/contract/test_phase2_closure_spec.py tests/unit/test_release_audit.py -q --basetemp .tmp/model-setup-doc-tests`：20 passed，1 個既有 pytest cache 目錄警告。預設 uv cache 存取被拒，改用 workspace cache 後完成；沒有重新安裝依賴。
- 對 `tests/contract/test_phase2_closure_spec.py` 的 Ruff lint／format check 通過；只更新其中兩個規格版本斷言，沒有改應用行為。
- 文件結構檢查通過：40 個 FR 與 57 個 AC 定義唯一；新增 ledger 列全為 not-run；交接列出的完整 source paths 與 README 文件連結存在。
- 應用功能、browser、live provider、Docker／clean-host 本輪未執行；舊 release-audit 測試通過只表示其既有規則未受文件改動破壞，不表示新 AC 已被自動驗收。

## 10. 本地 runtime 的後續研究，不屬於此實作包

GGUF 是模型檔案格式，Hugging Face 是模型託管與生態系，兩者不能當作可互換的執行引擎。建議下一案比較：既有 Ollama provider-native 管理、受管理 llama.cpp 子程序／獨立服務、以及選定架構的 HF runtime。能提供 embeddings 的 GGUF 仍需驗證 architecture、pooling、task instructions、量化與 retrieval quality；聊天模型能載入不代表可用於搜尋。

未來提出具體方案時至少提供：Windows/Linux/CPU/GPU 支援矩陣、RAM/VRAM/disk 估算、runtime binary 的版本／簽章／更新、模型 revision/hash/授權、受審核目錄、download resume/cancel/cleanup、quota、process 隔離與 crash recovery、禁止 remote code 執行、資源與 chat/reindex 排程、backup/upgrade 與 bundle compatibility、embedding 品質測試。先評估少量已驗證模型，不承諾任意 HF repo 或任意 GGUF 都能一鍵使用。

## 11. 下一位實作者的第一個動作

先讀最新 `ONBOARDING_FLOW_IMPLEMENTATION_HANDOFF.md`、`TECHNICAL_SPEC.md` 11.5/11.6 與 ADR-029/030。保留本文件的安全邊界，但不要依這份 2026-09-09 inventory 假定程式尚未存在，也不要再次要求擁有者批准已接受的 provider-neutral/model-first 方向。

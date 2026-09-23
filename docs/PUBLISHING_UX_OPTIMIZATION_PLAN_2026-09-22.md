# RepoNPC：本機 NPC 與 GitHub 卡片分享的 UX 優化計劃

日期：2026-09-22。狀態：擁有者已於同日明確授權 Luna Max 實作、Main 審核；依 ADR-046 與 LOCAL_PUBLICATION_CONTRACT_2026-09-22.md 分批實作中。

本文件取代同日稍早以 Actions／Release 為主要發布路徑的提案。擁有者明確指出：專案分析、首次與更新後的 embedding 都由本機使用者端完成；GitHub 的產品用途是展示卡片，讓外部訪客點進來與使用者主機上的 NPC 對話。本文件保留原分析；後續明確實作授權已啟動，對外部署與 GitHub 寫入仍依實際目標另行處理。

## 1. 核心結論

擁有者描述的架構成立。GitHub Actions 不需要連線本機 Ollama，也不需要在專案更新後替使用者重新 embedding。前版把既有 Actions 建置索引的實作方式當成必要條件，增加了不符合產品定位的操作負擔。

新的主要旅程應是：**本機整理作品與角色 → 本機預覽並試聊 → 讓訪客可以連到 RepoNPC → 把卡片放到 GitHub。** GitHub 不再是索引傳遞、啟用或問答的必要中繼站。

這是對已批准 ADR-001／005／010／030 等契約的架構調整方向，不是現在程式已經具備的能力。必須同步修正規格與驗收；不能只修改畫面而繼續暗中依賴 Release manifest。

## 2. 清楚的責任分工

| 元件 | 負責 | 不構成其必要工作 |
| --- | --- | --- |
| 使用者主機上的 RepoNPC | 讀取選定公開專案、處理與保存證據／索引、管理角色、預覽、接待訪客、查找資料與組織模型回答 | 等待 GitHub Actions 建好索引才能首次使用 |
| 使用者主機可連線的 embedding 模型 | 首次及更新時處理需要計算的資料；訪客提問時處理新問題的查詢向量 | 每次查看卡片或每次提問都重新 embedding 整個專案 |
| 使用者配置的回答模型 | 根據取回的證據回答訪客 | 操作 GitHub 或執行 repository 程式 |
| GitHub Profile README | 展示 NPC 卡片與連結 | 執行 NPC 後端、保存必要的私人運行狀態或提供模型 |
| GitHub Actions | 可供 RepoNPC 開發者執行 CI 測試，與使用者的使用流程分開 | 成為一般使用者分析、更新、啟用索引或聊天的必要步驟 |

本機端是使用者自己控制的 RepoNPC 程序／主機，不要求瀏覽器直接呼叫模型，也不代表將模型權重塞進前端。保留目前已選模型，不因這次架構修正而換模型或服務。

```text
使用者管理端
  選專案／更新 → 本機計算必要 embedding → 驗證並保存本機索引
  編輯介紹／角色 → 本機完整預覽與試聊 → 明確套用版本

外部訪客
  GitHub 卡片 → RepoNPC 公開訪客網址 → 使用者主機上的 RepoNPC
                                            ↓
                                將新問題轉成查詢向量
                                            ↓
                                查找已保存的專案資料
                                            ↓
                                NPC 根據證據回答
```

資料向量可以固定保存；訪客的新問題尚未預先計算。目前語意查找需要將該問題轉成相容查詢向量。兩者都能在使用者端完成，與 GitHub Actions 無關。

## 3. 目前程式為何沒有完成這條路

依 2026-09-22 真實瀏覽器走查與原始碼檢視：

| 證據 | 缺口 |
| --- | --- |
| `admin/onboarding.py` 在 `TemporaryDirectory` 建立分析用 `index.sqlite` | 分析用完整索引結束後清除，沒有直接交給正式問答 |
| `admin/batch_execution.py` 的 `derived_index` payload 只有 commit 與 validated 標記 | 這不是可重開的向量資料庫；已有的是 validated-result cache |
| `indexing/pipeline.py` 正式 build 重新呼叫 builder，builder 執行 `embed_passages` | 分析／正式建置尚未接通可重用向量與證據 |
| `chat/service.py` 呼叫 `embed_query_for` 後執行 `hybrid_candidates` | 已保存資料仍可重用；新問題的查詢 embedding 在後端執行 |
| 公開頁沒有 active bundle，作品集載入失敗 | 本機草稿、分析成功與公開服務啟用尚未接通 |
| Orange 預覽成功，但生成的 YAML 仍是 builtin | 角色工作區缺少「套用到目前作品集」 |
| 完成引導後只看到 YAML 匯出，完整預覽在進階模式 | 使用者不知道最後得到什麼、如何實際分享 |

此外，貢獻建議出現 503；獨立模型測試成功不能證明該功能 wiring 正常。模型選擇、手動內容與確認狀態有矛盾標籤。快取命中分支明確回傳空 `facts`，可解釋此路徑的空事實區，但不能據此推論所有新生成結果的品質。

證據保存在 `runtime-data/browser-check-2026-09-22/REPORT.md`。三個指定專案此次皆快取命中；Orange 下載未確認檔案落地；尚未做對外部署、GitHub 寫入或實際 Profile 驗收。此為一次走查與擁有者回饋，不是多位使用者研究。

## 4. 最小可理解的操作流程

### 4.1 建立內容與角色

保留目前六步 AI／四步手動內容引導，以及第一層「角色與動畫」。角色選好、校正通過後，主動作為「套用到作品集」；系統自己處理 validated PNG 與設定引用，使用者不需填路徑或改 YAML。

分析結果、本人確認的貢獻、角色、卡片與完整預覽使用同一份草稿版本。返回編輯不清空無關輸入；原始素材不改寫。

### 4.2 本機預覽並試聊

最後一步直接顯示完整作品集與 GitHub 卡片，提供「試聊」。一般預覽不呼叫模型；試聊是另外的明確動作，會使用已選模型。

若尚無正式索引，提供一個「準備 NPC」動作：重用已合格的資料向量、補齊新增的確認內容、組裝正式本機索引，通過完整性與相容性檢查後才能使用。缺模型、索引不完整或損壞時說明實際原因，不導向設定 Actions。

角色／主題等外觀修改只更新必要的素材，不重新 embedding 未變的專案。索引啟用不要求先把 YAML 或模型設定上傳 GitHub。

### 4.3 讓外部訪客連進來

本機可試聊與外部可連線是兩個真實狀態。`localhost:8090` 不能作為分享網址，因為訪客的 localhost 指向訪客自己的電腦。

一次性的「分享設定」應說清楚：卡片要連到哪個公開 HTTPS 訪客網址、使用者主機是否有可用的對外入口，以及主機／必要模型停止時訪客無法聊天。公開的是 RepoNPC 訪客頁面與受限 API；管理介面及 Ollama 保持私人連線。

先定義一條受支援、可以實測的對外接入配方，不讓新手一开始選多種代理、VPN、runner 或雲端平台。具體接入方式與是否支援 Windows 長期公開服務另作契約決定；不能把目前僅供 loopback 評估的啟動器直接當成正式公開部署。此計劃不默認採購服務或安裝 tunnel。

分享頁預設只呈現：

- NPC 在本機可用／需修復。
- 訪客連結已設定／尚需設定；本機檢查不能冒充已通過外部連線驗證。
- 主要下一步：「設定訪客連結」或「取得 GitHub 卡片」。

### 4.4 把卡片放到 GitHub

提供卡片預覽、下載 GIF／靜態替代圖、複製 Markdown，明確指出放置目標。對這個帳號，Profile repository 名稱應為 `xu-0306/xu-0306`，展示入口是根目錄 `README.md`；本次未確認該 repo 存在或預設分支。

推薦先用最少權限的手動路徑：將生成 GIF 放到 Profile repo 的說明路徑，再把帶有公開訪客網址的 Markdown 貼入 README。這樣卡片本身可由 GitHub 保存，不依賴本機主機在線才能顯示；點擊聊天仍需要主機在線。GitHub 實際動畫／圖片代理行為須完成 AC-022 驗證。

產品負責產生正確路徑的範例與清楚的「上傳圖片 → 貼入 README → 查看 Profile」指引，不要求使用者學 YAML、Release 或 Actions。自動改寫 Profile README 不屬目前寫入 allowlist，第一版不為此增加 token／OAuth 設定負擔。

#### 4.4.1 產品內必須提供「放到 GitHub」引導

這是分享頁內的必要功能，不能只交付一個 Markdown 複製按鈕，或把使用者送去讀操作手冊。用三個短段落逐步展開，每段只有一個主要下一步；已完成的準備直接略過。畫面以實際帳號、檔案名稱、圖片與訪客網址帶入，使用者不必替換模板變數。

**第一段：準備你的 GitHub 個人首頁。**

- 帶入先前選專案時的 GitHub 帳號，允許確認／修正；這不等於已登入 GitHub 或取得寫入權限。
- 以受限的 GitHub 公開 metadata 檢查同名公開 repo 與根目錄 README。已有時顯示「已找到個人首頁」，直接繼續；不能假設分支名稱為 main。
- 沒有時顯示「先建立你的個人首頁」與「開啟 GitHub 建立頁」：對 xu-0306 明確告知 Repository name 填 `xu-0306`、選 Public、開啟 Add README，再按 Create repository。已有 repo 但缺 README，只引導新增根目錄 `README.md`，不重建 repo。
- 檢查失敗、未登入、無權限、私人或不可見、限流必須分清楚能確定與不能確定的狀態；不能把所有查詢失敗都說成「不存在」。保留手動開啟與重新檢查入口，不索取 PAT。

Profile 同名公開 repository／README 的條件依 [GitHub 官方說明](https://docs.github.com/github/setting-up-and-managing-your-github-profile/customizing-your-profile/managing-your-profile-readme)。一般使用者看到的是「個人首頁介紹」，旁邊才補註 README，不要求先理解 Git 術語。

**第二段：把 NPC 卡片放進去。**

- 先顯示生成卡片與「下載卡片」；預設匯出單一 GIF，不先要求選格式或解壓 ZIP。進階操作才提供其他版本。
- 指引明確使用 repo 根目錄及建議檔名，例如 `reponpc-card.gif`，避免新手先建立多層資料夾；這是產品輸出命名慣例，不根據 Orange 等原始素材名稱判斷。
- 提供「開啟我的 GitHub 儲存庫」，在頁內附簡短操作：「Add file → Upload files → 選擇剛下載的卡片 → 儲存變更」。使用者切到 GitHub 前即可看到要按的位置；補註 Commit changes／Propose changes 依實際權限與分支設定顯示。
- 已有同名圖片時說明此次是更新；不可自動覆寫未知檔案。可下載另一個檔名並同步更新嵌入內容。若分支受保護，提示需完成 GitHub 的提案／合併流程；圖片尚未進入預設分支不能標記完成。
- 回到 RepoNPC 後可「檢查圖片是否已上傳」，失敗指出檔名、位置或分支不一致的可修復項目，不讓使用者猜 broken-image 原因。

上傳操作以 [GitHub 上傳檔案說明](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository) 為準；RepoNPC 引導不假裝已替使用者完成提交。

**第三段：加入介紹並查看成果。**

- 顯示「複製卡片嵌入內容」及「開啟 README」。分支／檔案已確認時可直達編輯位置；未知時開啟 repo 並指出 README 的編輯按鈕，不猜 URL 中的分支。
- 在旁邊直接寫：「把內容貼到你希望出現卡片的位置；保留原有介紹 → 按 Preview 確認 → 儲存變更。」不要求刪掉原 README。
- 嵌入內容包含實際下載的圖片相對路徑、可讀的替代文字與已設定的公開 NPC 網址；不能出現 localhost、TODO 或待替換 placeholder。相對圖片路徑依 [GitHub Markdown 說明](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax)。
- 「查看我的 GitHub 首頁」開啟 `https://github.com/<已確認帳號>`，提示使用者實際點一次卡片並試問。圖片可見、README 引用正確、NPC 外部連線成功是不同檢查；只有按過複製按鈕不代表已整合。
- NPC 公開網址尚未準備好時，可先保存圖片與編輯進度，但主要下一步返回「設定訪客連結」，不能生成宣稱可聊天的壞連結。外部連線實测保留第4.3節的界線。

返回 RepoNPC 後保留當前分享步驟與已填公開欄位，遵守既有登入／登出清除規則，不自動提交任何 GitHub 變更。後續換角色時，畫面說明是否只需替換同一路徑圖片；訪客網址或檔名改變才提示同步更新 README。

**完成標準：** 一位不知道 Profile README 的使用者，能只依 RepoNPC 頁內引導建立／找到自己的首頁、上傳卡片、保留原文貼入嵌入內容，最後從 GitHub 點入 NPC。无需設定 Actions、YAML、OAuth、PAT 或使用 Git 指令。若真實走查仍需口頭補充任何一步，就補入產品引導，不能把它算成使用者應自行知道的前置知識。

YAML 下載改為次要的「備份／搬移設定」。需要時連同角色一起匯出，清楚標明它不是已部署網站、向量資料庫或動畫成品。完整本機狀態／索引備份與秘密備份必須分清楚，不把秘密裝進公開匯出包。

## 5. 本機索引與更新設計

這一段是補齊功能，不是給新手看的設定清單。

1. 分析產生的合格資料向量／證據進入受保護、可重用的本機儲存，不能再只留下 marker。與 R12-B 合併設計容量、TTL／清理、權限、完整性、重啟恢復及失敗處理。
2. 本機公開作品集設定成為主要持久化來源；GitHub 不再是必要的設定來源。草稿與已啟用版本分開，明確套用後才改變訪客看到的內容。具體儲存格式、寫入原子性及備份契約先凍結，不預設新增資料庫服務。
3. 正式索引組裝需補齊本人已確認貢獻、正確來源 commit／路徑／行號與公開素材。分析使用的暫時設定引用不能直接當正式引用；不能將未確認推論升格為本人事實。
4. 專案更新後仍由使用者主機處理。向量重用核對內容、前處理／切分、模型語意、維度與完整性；來源引用另行更新。模型或切分策略改變、資料損壞或遺失時，明示必要重建。
5. 第一版使用明確的「檢查專案更新／更新 NPC」動作，顯示會更新的項目。是否自動輪詢是另一個選項，不必新增 scheduler 或 Actions。
6. 繼續保留不可變版本、checksum、schema、模型相容性、SQLite 檢查、smoke check、原子啟用與上一個可用版本；移除 GitHub transport 不等於移除驗證。
7. 重型工作在受控執行生命週期內完成，不阻塞公開 HTTP request。單一工作、取消、重複點擊、刷新恢復與秘密處理需先定義，優先重用現有機制。

已部署環境的舊 Release 更新來源需有明確遷移方案：切換到本機來源時停止自動覆蓋，保留原 active／previous 資料並能恢復。不維持兩個會互相覆寫的主來源。GitHub Release 是否保留為進階可選輸出後議，不列為主要旅程的必要條件。

## 6. 批次與驗收

| 批次 | 交付 | 完成證據 |
| --- | --- | --- |
| P0：契約與真實狀態 | 將本機持久化／索引啟用定為主要路徑；整理過期文件；診斷貢獻 503、修正矛盾標籤 | 精確儲存／API／執行／遷移／對外入口契約與需求映射；不再把草稿完成稱為上線 |
| P1：作品集編輯闭環 | 套用角色、同一份草稿、正常模式完整預覽、受保護素材預覽 R08 | Orange 同時出現在角色、卡片及設定引用；不需進入 YAML |
| P2：本機 NPC 可用 | R12-B 合格索引保留／重用、正式組裝、本機啟用、試聊、更新及恢復 | 沒有 GitHub token、Actions 或 Release 也能完整試聊；重啟後仍可用 |
| P3：訪客分享闭環 | 一條可驗證的公開接入配方、第4.4.1節三段式 GitHub 引導、卡片下載與外部訪客實測 | 沒有 Profile README 的新手也能依頁內說明完成；外部訪客能從真實 GitHub Profile 點入、提問、查看證據 |
| P4：故障與易用性 | 雙語／無障礙、更新失敗、模型中斷、恢復及備份、普通使用者走查 | 真實證據與未通過項目逐項記錄，不能以局部 UI 成功代表發布完成 |

具體測試場景：

- 使用 `live-subtitle`、`framefit-media-shrinker`、`anti-hardcode-engineering` 與 Orange，保留本人只確認「與 Codex 協作完成」的歸因界線。
- 完整本機索引已存在時，只換角色／卡片或重啟服務：專案 embedding 呼叫數為零；新問題只計算查詢 embedding，不重算專案。
- 在本機更新專案與索引，證明沒有 dispatch workflow，也不要求 GitHub 寫入憑證。公開專案讀取仍遵守匿名 REST、限流及明確選擇。
- 驗證索引損壞、模型不相容、更新失敗、取消與重複操作保留已知可用版本，不能誤報可聊天。
- 公開訪客可以存取頁面與聊天，但無法存取管理 API 或直接存取 Ollama；UI、卡片、公開 YAML 與匯出包均無秘密。
- 在真實 Profile 檢查圖片、GIF／靜態替代、點擊網址；Chrome／Firefox／Safari、繁中／英文、375／768／1024／1440 px、200% zoom、鍵盤及 reduced motion。GitHub 修改需當次明確目標與授權。
- 卡片真的下載落地；使用者可依頁面說明完成分享，不需閱讀 YAML／Actions 文件。易用性時間與求助次數實測後報告，不杜撰成功率。
- GitHub 分享走查至少涵蓋：首次沒有同名 repo、已有 README 且保留原文、已有 repo 但沒有 README、非 main 預設分支、同名圖片更新、錯誤上傳路徑、未登入／無權限／限流與受保護分支。檢查只做受限 GitHub 讀取，不把檢查或開啟編輯頁當作授權寫入。

沿用及修訂範圍：FR-006／012／015～FR-025／028／033／039～FR-042；AC-020～AC-032／034～AC-040／046／049／053／055～AC-060，按條文適用範圍驗證。FR-019～FR-021 與 GitHub-only 的 AC-026／029～AC-032 等須重新對應本機主路徑／可選整合，不可靜默刪除或以既有測試冒充新契約通過。

## 7. 實作前需定稿的決策

擁有者已澄清產品方向；以下為工程契約準備，不要求擁有者重複解釋 Actions 是否必要：

- 本機草稿／正式設定／角色／合格索引的儲存、容量、清理、備份與公開界線，整合 R08／R12-B。
- 本機索引組裝與啟用的 API／工作生命週期，以及從 GitHub manifest 主來源遷移的方式。
- 外部訪客如何連到使用者主機；正式部署與目前 Windows 評估啟動器的支援邊界。
- 卡片／設定匯出格式與實際 GitHub 放置引導。

這些細節先形成可審閱契約，再同步 TECHNICAL_SPEC、DECISIONS、SECURITY、ACCEPTANCE_CRITERIA、OPERATIONS、IMPLEMENTATION_PLAN、README 與交接文件。本段原為規劃階段界線；後續擁有者已授權實作，契約見 ADR-046。實際外部部署／GitHub 寫入仍需明確目標。

## 8. 原規劃階段證據（非目前實作狀態）

本次只修改此計劃文件，保留其他工作樹修改。核對 `admin/onboarding.py`、`admin/batch_execution.py`、`indexing/pipeline.py`、`indexing/index_database.py`、`chat/service.py` 與 `providers/runtime.py`；沒有呼叫真實模型或重跑應用程式測試。既有瀏覽器證據的限制見第3節。對此文件執行 no-index whitespace check，未報空白錯誤；比較新增檔案的 exit 1 不當成應用程式測試通過。

GitHub 官方背景來源：[Actions 用途](https://docs.github.com/en/actions/get-started/understand-github-actions)、[Profile README](https://docs.github.com/github/setting-up-and-managing-your-github-profile/customizing-your-profile/managing-your-profile-readme)。本計劃的核心結論依擁有者產品方向及本機程式分析，不以外部文件替代產品決策。

## 9. 實作範圍確認（2026-09-23）

擁有者確認目前沒有公開 HTTPS 網址，本次先完成本機並保留分享設定。P3 的 GitHub 指引與輸出屬於本機交付；真實公開入口／Profile 點入測試不列為本次完成條件，也不能宣稱已完成。實作契約以 ADR-046 為準；本機驗收記錄將單獨保留。

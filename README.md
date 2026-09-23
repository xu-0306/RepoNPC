# RepoNPC

> Meet the NPC who knows your code.<br>
> 讓懂你程式碼的 NPC，替你介紹作品。

RepoNPC 是一個開源、自託管的互動式 GitHub 作品集。你挑選想展示的公開儲存庫，補上自己確認過的角色與貢獻，RepoNPC 就會把它們整理成一個能回答訪客問題的像素 RPG 角色。

回答不只「聽起來合理」：重要內容會連回固定 commit、檔案與行號，讓訪客可以直接核對原始證據。

> [!IMPORTANT]
> RepoNPC 0.2.1 已完成 GitHub OAuth／公開讀取 PAT 退場與匿名 REST resolver；clean-host Docker、真實 provider、完整瀏覽器與無障礙驗證仍待執行，因此目前適合開發與評估，尚非正式 v1 發布版。
> Phase 5 remains the release-hardening boundary.

最後檢閱：2026-09-14

模型連線、回答模型與資料查找模型（技術上為 embedding model）的服務管理、測試與模型優先設定引導已整合至目前 working tree。**規格 0.2.5 / ADR-032** 讓服務網址／協定／金鑰更新同時重綁可安全修改的候選模型，清除舊測試結果並要求明確重測，不再要求使用者另外編輯儲存每個模型；公開使用中、上一個可用版本、重建中與已執行的分析仍保留原 revision。規格 0.2.4 / ADR-031 允許直接覆寫或刪除環境預設連線（例如改用非 11434 的 Ollama port），並讓選擇在重啟後保留；環境網址與 API key 仍不會被讀回。規格 0.2.3 / ADR-030 的「先設定兩種模型，再選專案並分析」與立即手動建立作品集路線維持不變。修正交接請讀 [模型優先引導實作交接](docs/ONBOARDING_FLOW_IMPLEMENTATION_HANDOFF.md)，前一版連線／秘密設計見 [模型設定實作交接](docs/MODEL_SETUP_IMPLEMENTATION_HANDOFF.md)。Figma 暫不處理；GGUF／Hugging Face 本地 runtime 仍是後續研究。

## 30 秒了解 RepoNPC

一般 GitHub Profile 告訴訪客「有哪些 repository」，卻常常無法快速回答：

- 這些專案解決了什麼問題？
- 為什麼採用這個架構？
- 作品擁有者實際負責了什麼？
- 哪一段程式碼可以證明這項說法？

RepoNPC 把這些資訊變成一段可對話、可驗證的作品集體驗：

[![RepoNPC 運作流程：使用者選擇公開 GitHub repository 並補充個人貢獻，系統建立證據索引，訪客向 NPC 提問，模型依證據回答並附上固定 commit、檔案與行號引用](reponpc-how-it-works.png)](reponpc-how-it-works.png)

最後你會得到兩個入口：

1. 放在 GitHub Profile README 的靜態 NPC 卡片。
2. 一個真正提供作品瀏覽、雙語問答與引用連結的 RepoNPC 網站。

GitHub README 不允許執行互動式 JavaScript，所以卡片負責吸引訪客並連到網站；聊天功能則在你自己架設的 RepoNPC 服務中執行。

## 它和一般 AI 聊天機器人有什麼不同？

RepoNPC 不讓模型自由搜尋、執行程式或自行拼湊 GitHub 連結。它先由後端找出允許使用的證據，再讓模型以證據 ID 回答，最後由後端驗證並產生引用。

系統也會分清楚三種內容：

| 類型 | 白話說明 |
| --- | --- |
| `OWNER_ASSERTION` | 你親自確認的角色、責任、成果或背景。 |
| `REPOSITORY_FACT` | 從指定 commit 的程式碼、文件或公開 metadata 直接看到的事實。 |
| `MODEL_INFERENCE` | 模型根據證據做出的推論，必須明確標示為推論。 |

「repository 裡有這段程式碼」不等於「你一定親自完成這段程式碼」。如果證據不足，RepoNPC 應該說明無法判定，而不是猜測。

## 主要功能

- 像素 RPG 風格的作品集網站與 GitHub Profile 卡片。
- 繁體中文（`zh-TW`）與英文（`en`）訪客／管理介面。
- 關鍵字搜尋、向量搜尋與 RRF 組成的混合檢索。
- 固定到 exact commit、檔案和行號的 GitHub 引用。
- Ollama、vLLM 與通用 OpenAI-compatible 聊天／embedding 服務。
- 引導式 repository 選擇、貢獻撰寫、預覽與設定匯出。
- 單一擁有者管理介面：本機啟動免註冊／免密碼，遠端部署保留密碼；公開 repository 的讀取不要求 OAuth 或 PAT。
- 版本化、物種中立的內建角色包，以及可容納任意物種／造型的自訂 sprite sheet；核心不以固定物種清單限制使用者設計。
- 不可變索引包、校驗、原子切換、保留上一個可用版本與 rollback。

## 建立前需要準備什麼？

要看到管理介面，Windows 本機評估只需要開發工具與一個可連線的模型服務。本機即可建立完整作品集並試聊；對外分享時再準備公開 HTTPS 訪客入口。

| 用途 | 需要準備 |
| --- | --- |
| Windows 本機評估 | Git、PowerShell、[uv](https://docs.astral.sh/uv/)、Node.js 24／Corepack，以及正在執行的 Ollama 或其他已設定 provider。 |
| 完整作品集 | 一個公開 GitHub 帳號、你要展示的公開 repositories、已測試的回答與資料查找模型。內容可由管理介面建立，Ollama 可在本機運行。 |
| 正式部署 | x86_64 Linux、Docker Engine、Compose v2、持久化磁碟、公開網域、HTTPS reverse proxy。參考主機為 4 CPU、8 GB RAM，另加模型所需資源。 |

RepoNPC 的 Compose 檔只啟動應用程式，不會順便啟動 Ollama 或 vLLM。模型服務必須由你另外部署，而且必須能從 `app` container 連線。

## 最快試跑：Windows 本機評估

這條路徑用來看看管理介面與設定流程，不代表完整的 production 部署。

1. 下載專案：

   ```powershell
   git clone https://github.com/xu-0306/RepoNPC.git
   Set-Location RepoNPC
   ```

2. 如果使用 Ollama，先啟動 Ollama 並準備聊天與 embedding 模型：

   ```powershell
   ollama pull qwen3.5:9b
   ollama pull qwen3-embedding:0.6b
   ```

3. 啟動 RepoNPC：

   ```powershell
   .\start-reponpc.cmd
   ```

啟動器會在需要時安裝鎖定的 Python／Web 依賴、建立前端、只監聽 `localhost:8090`，並以兩分鐘、僅能使用一次的本機授權開啟 `/admin`。瀏覽器會把它交換成受保護的管理 session 並立即清除網址片段；之後重新整理會恢復仍有效的 session，不需要再次執行啟動器。本機評估不需要註冊、帳號、密碼或 GitHub OAuth。若直接開啟 `/admin` 而沒有有效 session，重新執行啟動器即可。

如果你已建立 `.env`，本機 provider URL 必須能從 Windows 主機連線，例如 Ollama 通常是 `http://127.0.0.1:11434`。若服務使用其他 port，可在管理介面直接編輯環境預設連線並輸入完整新網址；可安全修改的關聯模型會一起更新為新 revision，之後只需明確按一次「測試模型」，不必再編輯儲存模型。轉為使用者管理後，重啟也不會再用 `.env` 的模型名稱覆寫已編輯的模型設定。也可在沒有模型引用後刪除該預設，兩種選擇都會跨重啟保留。管理介面的「預覽與分享 → 準備 NPC 並套用」會在本機建立並啟用相符索引；完成後即可試聊。

## 建立自己的 RepoNPC

1. 在管理介面選好並測試回答／資料查找模型，選擇公開專案，確認要展示的貢獻與雙語介紹。
2. 在「角色與動畫」匯入素材、檢查動畫，按「套用到作品集」。
3. 在「預覽與分享」檢查介紹、專案、角色與卡片，儲存本機草稿，再按「準備 NPC 並套用」。分析及索引都在你的主機完成，不需要 GitHub token、Actions 或 Release。
4. 準備完成後按「開啟目前版本並試聊」。更新專案時再按更新；相同內容的有效向量快取會重用，新問題仍需要查詢 embedding。
5. 要讓卡片出現在 GitHub 個人頁，先確認或建立與帳號同名的公開 repository（例如 `帳號/帳號`）；GitHub 帳號本身不等於這個 repository，也不需要另建卡片專用 repository。依頁內三步驟將下載的 `reponpc-card.gif` 上傳到同名 repository 根目錄，再把卡片 Markdown 貼進該 repository 的 `README.md`，保留原文並預覽、儲存。引導使用實際預設分支，不能連線時會顯示尚未確認。

沒有公開網址也能完成前四步。分享需要可對外連線的 HTTPS **訪客頁**網址；localhost 只供本機試用。公開入口只開放訪客頁與 API，管理頁及模型服務保持私人連線。GitHub 卡片不會執行模型，也不會替你啟動主機。

YAML 只供備份或搬移，不需上傳到 GitHub 才能使用 NPC。自訂角色要連同角色 PNG 備份；完整恢復請在停止服務後備份資料目錄（包含本機草稿、模型加密設定與已驗證 bundle），不要公開該目錄。詳見 [本機發布契約](docs/LOCAL_PUBLICATION_CONTRACT_2026-09-22.md)。

## 進階：既有 CLI／GitHub Release 整合

下列手動發布方式保留給既有部署；一般本機流程不需完成这些步驟。啟用本機模式後 Release 自動輪詢會停止，切回方式見 Operations。

### 1. 寫下你想展示的內容

先複製公開設定範例：

```bash
cp reponpc.example.yml reponpc.yml
```

編輯 `reponpc.yml` 中最重要的四個部分：

- `profile`：你的名稱、簡介、連結、招呼語與建議問題。
- `repositories`：只加入你明確選擇的公開 repository。
- `role`、`summary`、`claims`：寫下你願意公開並親自確認的貢獻。
- `character` 與 `card`：以 `pack_id`／`pack_version` 選擇內建角色包，或提供標準 `256x448` 自訂 sprite sheet；自訂角色不必宣告物種。管理工作區提供獨立的「角色與動畫」入口，無須進入 raw YAML：可直接拖放 PNG／ZIP 或選擇整個素材資料夾，系統依 4×7 結構找出可轉換圖片，單一候選自動預覽，多個候選讓使用者看圖選擇，並可切換七種動畫狀態後再下載或寫入。一般 ZIP 不必改檔名、宣告物種或手寫 manifest；若提供嚴格 manifest，仍會依其明確映射處理。

「角色與動畫」會在轉換時檢查影格站位；多個動作呈現一致欄位偏移且不會裁切時，會自動校正並驗證。其他情況可預覽建議，再用每格的 X、Y 像素輸入框或方向按鈕微調；手動修改需按「套用校正並驗證」。隨時可還原，原始素材不會改動。

若上傳的 4×7 素材在格線邊界有明顯殘影，轉換流程會在能安全辨識時提供「原版／清理版」同格預覽。請選擇要使用的版本，再下載或儲存；不確定的圖案不會被自動刪除，原始檔也不會被覆寫。

`reponpc.yml` 預期會公開，請勿放入 token、API key、密碼、內部 URL 或私人 repository 名稱。

### 2. 設定聊天與 embedding 服務

RepoNPC 將聊天模型與 embedding 模型視為兩個獨立能力。兩者可以來自同一台 Ollama，也可以分別使用 vLLM 或 OpenAI-compatible API。

選擇 Ollama 後，可參考 `qwen3-embedding:0.6b` 等模型；它不是規格 0.2.2–0.2.4 的預設服務或預選模型。正式環境仍使用外部 embedding profile；內建 sentence-transformers adapter 只供隔離測試與 benchmark。管理頁已有連線／模型面板，但一般引導與乾淨啟動後的首次分析仍在修正，因此目前可使用明確環境設定或進階管理面板評估，不能把引導畫面視為完成的首次使用流程。

先建立部署環境檔與 secret 目錄：

```bash
cp .env.example .env
mkdir -p secrets
openssl rand -base64 48 > secrets/reponpc_ip_hash_key
chmod 700 secrets
chmod 600 secrets/reponpc_ip_hash_key
```

接著至少修改 `.env` 中這些設定：

- `REPONPC_PUBLIC_BASE_URL`、`REPONPC_TRUSTED_HOSTS`
- `REPONPC_CONFIG_REPOSITORY`、`REPONPC_INDEX_MANIFEST_URL`
- `REPONPC_CHAT_PROVIDER`、`REPONPC_CHAT_BASE_URL`、`REPONPC_CHAT_MODEL`
- `REPONPC_EMBEDDING_PROVIDER`、`REPONPC_EMBEDDING_BASE_URL`、`REPONPC_EMBEDDING_MODEL`

正式 secret 建議寫入 `secrets/` 中的獨立檔案，再使用對應的 `*_FILE` 環境變數掛載；不要把真實 secret 提交到 Git。

### 3. 驗證設定並建立索引

在已安裝 [uv](https://docs.astral.sh/uv/) 的 source checkout 中：

```bash
uv sync --frozen
uv run reponpc config validate reponpc.yml
uv run reponpc index build --config reponpc.yml --output dist
```

索引建立器會把選定的 branch、tag 或 ref 解析成 exact commit，套用檔案與大小限制，產生證據、公開 profile、角色資產與 README 卡片，再建立不可變 bundle。

索引所使用的 embedding provider、模型、維度與前綴必須和 runtime 完全一致，否則 bundle 不會啟用。

### 4. 發布索引並啟動網站

建議在自己的部署 repository 建立 GitHub Actions workflow，驗證並發布 bundle 到 GitHub Release；確認資產可讀與 checksum 正確後，最後才更新 `stable-manifest.json`。公開 source 不附帶 `.github/workflows/`，手動執行相同兩階段發布的命令為：

```bash
uv run reponpc index publish --bundle-dir dist
uv run reponpc index publish-manifest --bundle-dir dist
```

這兩個命令需要先依 [操作手冊](docs/OPERATIONS.md) 設好 GitHub repository、權限與發布環境。不要覆寫既有 release asset，也不要在 bundle 尚未驗證前更新 stable manifest。

有可用 manifest 後，在正式 Linux 主機啟動應用程式：

```bash
docker compose build --pull
docker compose up -d
docker compose ps
```

檢查服務：

```bash
curl --fail http://127.0.0.1:8000/healthz
curl --fail http://127.0.0.1:8000/readyz
curl --fail http://127.0.0.1:8000/api/public/status
```

`healthz` 只表示程序有回應；`readyz` 成功才代表索引、runtime 與模型已相容並可服務。

### 5. 進入管理介面並分享卡片

本機 Windows 評估只要執行啟動器；它會自動簽發短效本機授權並直接開啟管理介面。以下 setup code 僅供 `production` 或任何非 loopback 的管理部署使用：

```bash
docker compose exec app reponpc admin setup-code
```

透過 loopback、SSH tunnel、私人 LAN 或 VPN 開啟 `/admin`，輸入 setup code，再建立本機帳號與密碼。正式環境的密碼至少 15 個 Unicode 字元。GitHub 公開 repository 分析使用匿名 REST 容量；OAuth 與瀏覽器輸入的公開讀取 PAT 已退場。

管理介面確認 index 與 provider 都 ready 後，即可預覽 NPC、產生 README Markdown，並貼到你的 GitHub Profile README。

> [!WARNING]
> 不要把 `/admin` 或 `/api/admin/*` 直接公開到 Internet。特殊或高編號 port 不是安全控制；正式環境應由 reverse proxy 只公開訪客路由，並把管理路由限制在私人網路。

完整的 HTTPS、GitHub 寫回權限、匿名讀取額度、備份、更新、rollback 與故障排除方式請參閱 [操作手冊](docs/OPERATIONS.md)。

## 常見疑問

### 一定要使用雲端 AI 嗎？

不用。你可以使用私人 Ollama 或 vLLM，也可以使用通用 OpenAI-compatible API。RepoNPC 不會在 provider 故障時偷偷切換到另一個服務。

### RepoNPC 會掃描我所有 GitHub repository 嗎？

不會。只有你明確選擇並確認的公開 repositories 會進入分析／索引範圍。v1 不支援私人 repository。

### 模型可以修改我的程式碼嗎？

不可以。LLM 沒有 shell、工具、檔案系統、repository 寫入或任意網路能力。GitHub 設定回寫由後端以獨立權限和衝突檢查處理。

### GitHub 匿名讀取額度或模型不可用時，還能編輯作品集嗎？

可以。你仍可手動輸入貢獻、驗證、預覽、複製或下載 YAML。模型分析是可選的建議功能，GitHub writeback 也不是本機編輯的必要條件；匿名 GitHub REST 達到限制時只需稍後重試分析。

### 更新索引失敗會讓網站壞掉嗎？

不應該。新 bundle 必須先通過 checksum、schema、模型相容性、SQLite 完整性與 smoke checks；失敗時會保留上一個可用版本。

## 文件導覽

| 想了解… | 請閱讀 |
| --- | --- |
| 完整安裝、HTTPS、備份、恢復與 rollback | [操作手冊](docs/OPERATIONS.md) |
| API、資料結構與功能契約 | [技術規格](docs/TECHNICAL_SPEC.md) |
| 先設定模型再分析的引導修正 | [模型優先引導實作交接](docs/ONBOARDING_FLOW_IMPLEMENTATION_HANDOFF.md) |
| 中立模型設定、API 金鑰安全與前置引導改版 | [實作交接](docs/MODEL_SETUP_IMPLEMENTATION_HANDOFF.md) |
| 每項需求如何判定完成 | [驗收標準](docs/ACCEPTANCE_CRITERIA.md) |
| 威脅、秘密管理與管理介面限制 | [安全模型](docs/SECURITY.md) |
| 重要架構選擇及其理由 | [架構決策](docs/DECISIONS.md) |
| 自訂 NPC 圖片格式 | [Sprite 格式](docs/SPRITE_FORMAT.md) |

要修改程式碼前，請先閱讀技術規格、驗收標準、安全模型與架構決策。公開文件發生衝突時，以已批准的技術規格與明確記錄的架構決策為準。

## 技術棧

- Web：React、Vite、TypeScript、pnpm
- API／indexer：FastAPI、Python、uv
- 搜尋：SQLite FTS5、NumPy、向量檢索、RRF
- 程式碼解析：Tree-sitter（Python、JavaScript／TypeScript、Go、Rust）
- 模型：Ollama、vLLM、OpenAI-compatible chat／embedding profiles
- 發布：本機驗證與啟用；GitHub Actions／Releases／stable manifest 為既有進階整合
- 部署：單一 RepoNPC application image、Docker Compose、持久化 SQLite

## v1 刻意不做的事

RepoNPC v1 是單一擁有者、單一 NPC，只處理擁有者選定的公開 repositories。它不是多租戶 SaaS、通用 coding agent 或完整 RPG 遊戲，也不包含私人 repository、billing、訪客帳號、OAuth device flow、多個 NPC 或可自由探索的遊戲世界。

## 參與開發

目前專案仍在 Phase 5 發布強化階段。請先閱讀受影響的規格，再使用鎖定的工具鏈安裝依賴：

```bash
uv sync --frozen
corepack enable
pnpm install --frozen-lockfile
```

常用檢查：

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
pnpm run web:check
```

每一項行為變更都必須補上相應測試，並同步更新受影響的規格、範例與驗收證據。

## 授權

`pyproject.toml` 目前宣告為 MIT。正式對外發布前仍應以 repository 根目錄中的 `LICENSE` 檔案為準。

## 新手模型設定修復（2026-09-12）

模型設定的操作順序為「新增服務 → 新增模型 → 測試模型 → 確認用於分析」。已有服務可直接新增模型；資料查找模型的維度留空即可，測試成功時才自動取得。測試不會自動啟用公開網站。失敗卡片顯示 HTTP 狀態或明確的逾時／連線說明，並保留設定供編輯或重試。

Repository AI 分析會同時使用兩個已選角色：Embedding 模型負責將來源與問題轉成向量並找出證據，Chat 模型再根據證據產生雙語分析。空白 include 會套用目錄、manifest 與常見程式碼副檔名的預設規則，因此只有根目錄檔案的平坦 repository 也能進入分析；秘密、二進位、產物與大小限制仍會先行排除。

規格 0.3.0 / ADR-037 將大型 repository 分析改為彈性 active-work 配置：每 repository 預設 1,800 秒、provider 無活動預設 300 秒、GitHub I/O 預設 60 秒，暫時性錯誤最多使用同一凍結 provider/model 三次；archive、index 與 provider 容量等待不消耗有效執行時間。管理分析輸出維持 `REPONPC_ANALYSIS_MAX_OUTPUT_TOKENS=8192`、最高 `16384`，訪客聊天改為 4,096／最高 8,192。Archive/source 限制可由 `.env` 調整；超過單檔 materialization 門檻會安全跳過並回報，只有不安全結構或總量天花板才終止。Migration 25 保留舊批次並擴大 durable budget。完整設定與安全界線見 `.env.example`、`docs/OPERATIONS.md` 與 ADR-037。

規格 0.3.1 / ADR-038 將「同輪重試」與「建立後繼分析輪次」分開：同輪重試只有在模型嘗試次數與有效執行時間都未用盡時可用；用盡後可由管理員明確選擇失敗項目重新分析。新輪次預設保留原 commit、include/exclude、凍結模型組合與來源結果，僅重設新輪次的計數；每個來源失敗項目只能建立一個直接後繼。若改用目前模型，確認會綁定畫面顯示的 selection generation，設定已變更時必須重新檢視。Migration 26 新增不含秘密的批次／項目 lineage、輪次與失敗階段；migration 27 讓來源使用標記與有界冪等綁定在一般清理後仍維持正確。

只改服務名稱時保留原網址與金鑰；更換網址是獨立選項。同一連線方式且協定、主機與有效連接埠不變時，只修正路徑（例如補上 `/v1`）可沿用已儲存的金鑰；更換 origin 或連線方式仍須替換或移除金鑰。所有服務新增、更新、刪除與清單更新失敗都會在實際操作的面板顯示單一錯誤摘要，說明安全原因、原設定是否保留及下一步，並在可用時提供診斷代碼。新輸入的金鑰會在送出或收合表單後清除，失敗重試時會明確提醒重新填入。

此次資料庫升級包含 runtime migration 19 與後續 migration 20，首次載入新版後端時交易式升級。保留舊資料與模型選擇，失敗會回復；正式 bundle 格式不變。完整修復清單與證據見 [UI／UX 修復紀錄](docs/UI_UX_REVIEW_2026-09-12.md)。

Runtime migration 22 會修復舊版在服務更新後仍停留於舊 revision 的安全候選模型，並保存歷史 revision 的 provider 資訊。升級本身不會呼叫模型；重新啟動新版後端後，受影響的模型會顯示需要重新測試，按一次「測試模型」即可驗證新服務。

Runtime migration 23 為失敗的批次項目新增安全、封閉集合的 `error_reason`。分析頁重新整理後仍會顯示錯誤代碼、原因與建議動作；原始 repository／prompt／模型回覆、私人網址與憑證不會寫入錯誤欄位。

模型測試失敗會顯示實際 HTTP 狀態碼與服務商錯誤原文，不翻譯或推測原因。原文會遮蔽已知金鑰及私人網址，並限制長度；無可顯示文字時會明確提示。舊版本未保存的原文需按「測試模型」重新取得。詳見 [錯誤原文修正紀錄](docs/PROVIDER_ERROR_MESSAGES_2026-09-12.md)。

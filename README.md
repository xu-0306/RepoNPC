# RepoNPC

> 讓懂你程式碼的 NPC，替你介紹作品。<br>
> Meet the NPC who knows your code.

RepoNPC 是自託管的 GitHub 作品集。你選擇公開專案、確認自己的貢獻，NPC 便能依據作品內容回答訪客，並附上可核對的程式碼引用。GitHub 個人頁上的卡片會連到你的作品集網站。

**目前是開發／評估候選版，尚未完成正式 v1 驗收。** Windows 安裝候選已有本機測試；乾淨 Windows、完整無障礙、素材權利與真實外網等發布檢查仍未完成。最新範圍見 [UX 優化與驗證紀錄](docs/OPTIMIZATION_PLAN_2026-10-11.md)，發布缺口見 [專案記憶](docs/PROJECT_CONTEXT.md)。

## 先選你要走的路

| 你現在的情況 | 從這裡開始 | 可以完成什麼 |
| --- | --- | --- |
| 還沒有模型，想先整理作品 | 開啟管理頁 →「先手動建立作品集」 | 選專案、撰寫雙語貢獻、預覽、儲存本機草稿、下載設定備份 |
| 已有 Ollama 或相容 API 服務，想讓 AI 協助 | 「設定 AI 並開始」 | 新增並測試兩種模型、確認選用，再選專案與分析 |
| 內容已完成，想試聊或分享 | 「預覽與分享」 | 準備 NPC → 本機試聊 → 訪客連線 → Pages 上傳與核對 → GitHub 卡片 |

**手動建立內容不需要模型。準備 NPC、AI 分析與實際聊天需要已測試並選用的回答模型及資料查找模型。** 目前推薦回答模型清單為空；你需要自行準備回答模型服務。裝置容量檢查不會安裝模型，也不代表模型品質已通過驗證。資料查找可明確選擇下載內建 bge-m3（約 2.29 GB，CPU 執行），或設定自己的服務。

RepoNPC 不會自動切換模型或替你下載、開啟公開連線。一般預覽不呼叫模型；明確測試、分析和試聊會使用所選服務，雲端服務可能產生費用。

## 開啟 RepoNPC

**已有 Windows 安裝候選：**從開始功能表開啟 RepoNPC，依管理頁引導操作。安裝候選的建置、校驗與未完成驗收見 [Windows 指南](packaging/windows/README.md)；目前不宣稱已有正式穩定安裝版。

**從原始碼在 Windows 評估：**先安裝 Git、PowerShell、[uv](https://docs.astral.sh/uv/) 與 Node.js／Corepack，使用專案鎖定的 pnpm 版本，uv 會自動準備 Python 3.14，然後執行：

```powershell
git clone https://github.com/xu-0306/RepoNPC.git
Set-Location RepoNPC
.\start-reponpc.cmd
```

啟動器會準備依賴與前端，開啟只供本機使用的管理頁。不必先設定模型、GitHub token、帳號或密碼。重新整理可延續有效登入；若工作階段過期，重新開啟 RepoNPC。既有 `.env` 設定會保留。

Windows 啟動器與安裝版只供本機試用；第 4–6 步的公開分享需要 Linux Compose 正式部署，目前不支援 Windows 正式模式。

Linux／自行管理 HTTPS 的部署與備份操作，請讀 [操作手冊](docs/OPERATIONS.md) 和下方進階整合。

## 從草稿到分享

1. **建立內容：**選 AI 或手動路線，挑選公開專案，填寫並確認自己的雙語貢獻與個人介紹。不會從程式碼推定你的職位或成果。
2. **本機預覽：**進入「預覽與分享」，預覽作品集與卡片、儲存草稿。角色可使用內建素材；自訂角色與外觀都是選填。
3. **準備並試聊：**兩種模型都已測試且選用後，按「準備 NPC 並套用」。缺少模型時按「前往設定模型」，草稿會保留；完成後返回準備。成功後開啟目前版本試聊。
4. **設定訪客連線（需 Linux 正式部署）：**準備 Tailscale Funnel 聊天入口與 GitHub Pages 網域，儲存後明確啟動訪客連線，並在 Tailscale 完成 Funnel 設定。管理頁及模型服務保持私人連線。
5. **上傳網站（需 Linux 正式部署）：**填 Pages 完整網址（例如 `https://account.github.io/project/`），下載、解壓縮靜態網站，依 [雙語分享指南](docs/PAGES_SHARING_GUIDE.md)手動上傳。發布後返回「核對已上傳網站」。
6. **下載 README.md（需 Linux 正式部署）：**核對完整 README 內容預覽，再下載包含已確認公開介紹、作品、NPC 名片與對話連結的檔案。README.md 必須放在「與 GitHub 帳號同名的公開儲存庫」根目錄，才能顯示在個人首頁。卡片使用已核對 Pages 的公開圖片，不必另上傳；已有 README 時先保留原文，也可用原有圖片上傳與複製區塊追加名片。再從 GitHub 點開網站確認。外觀、涵蓋檢查及 FAQ 可在選填區調整。

**Pages 網域與完整網址不同：**訪客連線欄位只填 `https://account.github.io`；網站上傳欄位要包含 `/project/` 等路徑。Pages 核對與外網聊天檢查各自記錄；儲存網址或本機準備成功，都不代表已經公開上線。

沒有公開網址仍能完成本機內容與試聊。主機和模型關閉時，已上傳的靜態網站可顯示公開內容及匯出時核准的 FAQ；即時問答需要主機、模型和公開連線可用。RepoNPC 不會自動上傳 GitHub。

聊天等待時間預設 **180 秒，最高 300 秒**，既有明確較低設定保留。畫面顯示實際處理階段並可停止；輸出仍須通過引用與內容驗證。兩種生成預算各自預設／最高 16,384 token，包含推理與答案，不等於 16k 個可見字元。

要把內容帶到正式主機，可下載 `reponpc.yml`、保存自訂角色 PNG，在正式管理頁的進階 YAML 編輯器貼上並驗證，再到「角色與動畫」上傳、套用 PNG。模型連線與金鑰需在新主機重新設定。維護備份只供相同版本、同一原資料目錄還原；完整資料搬移請讀 [備份說明](docs/OPERATIONS.md#11-backup-and-recovery)。

## English quick start

With a Windows installer candidate, open RepoNPC from the Start menu; see the [Windows guide](packaging/windows/README.md) for build/checksum instructions and pending acceptance. For source evaluation, install Git, PowerShell, [uv](https://docs.astral.sh/uv/) and Node.js/Corepack; use the pinned pnpm version. uv prepares Python 3.14 automatically, then run:

```powershell
git clone https://github.com/xu-0306/RepoNPC.git
Set-Location RepoNPC
.\start-reponpc.cmd
```

The launcher prepares dependencies and the frontend, then opens local administration. No model, GitHub token, account or password is needed to enter; existing `.env` settings are preserved. Refresh resumes a valid session; reopen RepoNPC after it expires. Windows launcher/installer use is local trial only. Visitor access, Pages sharing and the README with a public card (steps 4–6 above) require Linux Compose production deployment; Windows production mode is not supported yet.

Open RepoNPC and choose **Build manually first** to write, preview, save and back up content without a model. For AI analysis or live chat, bring your own Ollama or compatible API service, test both the answer and content finder models, then confirm the selection. The verified answer-model catalog is currently empty; the optional built-in bge-m3 content finder requires an explicit download.

In **Preview & share**, prepare and try locally, configure visitor access, download and manually upload the Pages site, verify it, then preview and **Download README.md**. The complete file uses the verified site's public card image. Upload README.md to the root of a public repository with the same name as your GitHub account to display it on your profile. Preserve existing README text or append the copied card block with the manual image-upload path. Use the domain without a path for visitor access and the full project URL for Pages. Follow the [bilingual sharing guide](docs/PAGES_SHARING_GUIDE.md). This is an evaluation candidate, not an accepted v1 release; no public connection or GitHub upload happens automatically.

To move public content to production, download `reponpc.yml`, keep custom character PNGs, paste and validate the YAML in the production admin's advanced editor, then upload/apply the PNGs in Character & animation. Set up model connections and keys again on the new host. Maintenance restore is for the same version and original data directory only; see [backup instructions](docs/OPERATIONS.md#11-backup-and-recovery) for full-data moves.

## 給開發者與自行部署者

## 進階：既有 CLI／GitHub Release 整合

下列手動發布方式保留給既有部署；一般本機流程不需完成這些步驟。啟用本機模式後 Release 自動輪詢會停止，切回方式見 Operations。

### 1. 寫下你想展示的內容

先複製公開設定範例：

```bash
cp reponpc.example.yml reponpc.yml
```

編輯 `reponpc.yml` 中最重要的四個部分：

- `profile`：你的名稱、必填且需確認的 `github_login`、選填的 `aliases`、簡介、連結、招呼語與建議問題。
- `repositories`：只加入你明確選擇的公開 repository。
- `role`、`summary`、`claims`：寫下你願意公開並親自確認的貢獻。
- `character` 與 `card`：以 `pack_id`／`pack_version` 選擇內建角色包，或提供標準 `256x448` 自訂 sprite sheet；自訂角色不必宣告物種。管理工作區提供獨立的「角色與動畫」入口，無須進入 raw YAML：可直接拖放 PNG／ZIP 或選擇整個素材資料夾，系統依 4×7 結構找出可轉換圖片，單一候選自動預覽，多個候選讓使用者看圖選擇，並可切換七種動畫狀態後再下載或寫入。一般 ZIP 不必改檔名、宣告物種或手寫 manifest；若提供嚴格 manifest，仍會依其明確映射處理。

「角色與動畫」會在轉換時檢查影格站位；多個動作呈現一致欄位偏移且不會裁切時，會自動校正並驗證。其他情況可預覽建議，再用每格的 X、Y 像素輸入框或方向按鈕微調；手動修改需按「套用校正並驗證」。隨時可還原，原始素材不會改動。

若上傳的 4×7 素材在格線邊界有明顯殘影，轉換流程會在能安全辨識時提供「原版／清理版」同格預覽。請選擇要使用的版本，再下載或儲存；不確定的圖案不會被自動刪除，原始檔也不會被覆寫。

`reponpc.yml` 預期會公開，請勿放入 token、API key、密碼、內部 URL 或私人 repository 名稱。

### 2. 設定聊天與 embedding 服務

RepoNPC 將聊天模型與 embedding 模型視為兩個獨立能力。兩者可以來自同一台 Ollama，也可以分別使用 vLLM 或 OpenAI-compatible API。

選擇 Ollama 後，可參考 `qwen3-embedding:0.6b` 等模型；它不是規格 0.2.2–0.2.4 的預設服務或預選模型。可選明確下載並驗證的內建 bge-m3（ONNX CPU）或外部資料查找模型；sentence-transformers adapter 僅供隔離測試。引導設定會要求分別測試兩種模型並確認選用，完整實機及發布驗收仍另行追蹤。

先建立部署環境檔與 secret 目錄：

```bash
cp .env.example .env
mkdir -p secrets
openssl rand -base64 48 > secrets/reponpc_ip_hash_key
chmod 700 secrets
chmod 600 secrets/reponpc_ip_hash_key
```

Windows Docker Desktop 從 Windows 檔案系統 bind mount 的 secret，在 Linux 容器內會呈現群組／其他使用者可讀權限，因而被拒絕為 `unsafe_secret_permissions`。支援的正式主機是 Linux；僅供本機 Docker Desktop 評估時，可用直接的 `REPONPC_GITHUB_TOKEN`、`REPONPC_CHAT_API_KEY`、`REPONPC_EMBEDDING_API_KEY`、`REPONPC_IP_HASH_KEY`，並清空各自的 `_FILE`，兩種形式不可並用。

接著至少修改 `.env` 中這些設定：

- `REPONPC_PUBLIC_BASE_URL`、`REPONPC_TRUSTED_HOSTS`
- `REPONPC_ADMIN_ORIGINS`：正式部署的私人管理 origin；啟用訪客 gateway 必須明確填寫。
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

索引建立器會把選定的 branch、tag 或 ref 解析成 exact commit，套用檔案與大小限制，產生證據、公開 profile、角色資產與 README 卡片，再建立不可變 bundle。每個啟用的 repository 會依 `github_login` 讀取 GitHub 可見的提交期間與其他貢獻者資訊；查詢失敗會標記為無法取得，不會當作零次參與，也不會顯示提交次數。

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

Compose 容器固定監聽 `8000`；主機發布埠由 `REPONPC_HOST_PORT` 設定（預設 `8000`），修改 `REPONPC_PORT` 不會改變 Compose 的監聽埠。

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

管理工作區的「維護」可建立密碼加密的 `.reponpc-backup`，檢查並確認還原、
回復保留的前一份網站資料，以及停止訪客 gateway。備份密碼每次輸入，送出後清除。
這只還原相同版本、同一原資料目錄的 SQLite 設定，不是跨主機搬移；請另外保留密鑰、bundles、模型與圖片／
本機作品集檔案。還原前會自動保存目前狀態的加密備份，完成後須重新登入，gateway
保持關閉。完整搬移與災難復原依 [備份操作說明](docs/OPERATIONS.md#11-backup-and-recovery)。
Windows 安裝包建置與仍待驗收項目見 [Windows packaging 指南](packaging/windows/README.md)。

### Linux：訪客 gateway 與主機 Tailscale

A1 使用 `production` 部署模式。私人管理主機名稱須和 Funnel、Pages 的主機名稱不同，並明確設定 `REPONPC_ADMIN_ORIGINS`；訪客 gateway 固定綁定 `127.0.0.1`，`REPONPC_VISITOR_GATEWAY_PORT` 預設為 `8001`。`REPONPC_VISITOR_TRUSTED_PROXY_CIDRS` 預設留空，保留共用每日額度與同時工作上限；要使用個別 IP 限制，必須另行確認實際 Funnel 的來源位址覆寫行為與外網測試。

主機 Tailscale 需要能連到容器的 loopback listener。Linux 可使用 opt-in `compose.funnel.yml`（Compose **2.24.4 以上**），以 host network 啟動；先設定私人管理入口與模型連線，再在管理頁儲存 Funnel／Pages 網址並明確啟動 gateway：

```bash
python scripts/funnel_compose_preflight.py
docker compose -f compose.yml -f compose.funnel.yml up -d --build
```

擁有者另外安裝、登入並授權官方 Tailscale，將下方 `<https-port>` 換成訪客網址的連接埠（443、8443 或 10000），`<visitor-port>` 換成 gateway port：

```bash
tailscale funnel --bg --https=<https-port> http://127.0.0.1:<visitor-port>
tailscale funnel --https=<https-port> off
```

RepoNPC 只顯示操作說明；關閉 gateway 不代表 Funnel 已停用。管理頁分開顯示本機就緒、入口已設定與擁有者確認過的外網檢查；重啟、停止或來源設定改變會清除外網確認；版本變更不會清除原本的時間紀錄，仍應依實際更新重新檢查。真實 Tailscale／Pages／模型與乾淨主機驗收尚未執行，Windows 安裝版與 Pages 靜態匯出分屬 A8、A5。

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

| 想了解…                                  | 請閱讀                                                                 |
| ---------------------------------------- | ---------------------------------------------------------------------- |
| 完整安裝、HTTPS、備份、恢復與 rollback   | [操作手冊](docs/OPERATIONS.md)                                         |
| API、資料結構與功能契約                  | [技術規格](docs/TECHNICAL_SPEC.md)                                     |
| 先設定模型再分析的引導修正               | [模型優先引導實作交接](docs/ONBOARDING_FLOW_IMPLEMENTATION_HANDOFF.md) |
| 中立模型設定、API 金鑰安全與前置引導改版 | [實作交接](docs/MODEL_SETUP_IMPLEMENTATION_HANDOFF.md)                 |
| 每項需求如何判定完成                     | [驗收標準](docs/ACCEPTANCE_CRITERIA.md)                                |
| 威脅、秘密管理與管理介面限制             | [安全模型](docs/SECURITY.md)                                           |
| 重要架構選擇及其理由                     | [架構決策](docs/DECISIONS.md)                                          |
| 自訂 NPC 圖片格式                        | [Sprite 格式](docs/SPRITE_FORMAT.md)                                   |

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

程式碼採用 [MIT 授權](LICENSE)。第三方程式與素材另見 [授權聲明](THIRD_PARTY_NOTICES.md)。

## 新手模型設定修復（2026-09-12）

模型設定的操作順序為「新增服務 → 新增模型 → 測試模型 → 確認用於分析」。已有服務可直接新增模型；資料查找模型的維度留空即可，測試成功時才自動取得。測試不會自動啟用公開網站。失敗卡片顯示 HTTP 狀態或明確的逾時／連線說明，並保留設定供編輯或重試。

Repository AI 分析會同時使用兩個已選角色：Embedding 模型負責將來源與問題轉成向量並找出證據，Chat 模型再根據證據產生雙語分析。空白 include 會套用目錄、manifest 與常見程式碼副檔名的預設規則，因此只有根目錄檔案的平坦 repository 也能進入分析；秘密、二進位、產物與大小限制仍會先行排除。

規格 0.3.0 / ADR-037 將大型 repository 分析改為彈性 active-work 配置：每 repository 預設 1,800 秒、provider 無活動預設 300 秒、GitHub I/O 預設 60 秒，暫時性錯誤最多使用同一凍結 provider/model 三次；archive、index 與 provider 容量等待不消耗有效執行時間。目前管理分析與訪客聊天各自預設／最高 16,384 token（ADR-055），明確較低設定保留。Archive/source 限制可由 `.env` 調整；超過單檔 materialization 門檻會安全跳過並回報，只有不安全結構或總量天花板才終止。Migration 25 保留舊批次並擴大 durable budget。完整設定與安全界線見 `.env.example`、`docs/OPERATIONS.md` 與 ADR-037。

規格 0.3.1 / ADR-038 將「同輪重試」與「建立後繼分析輪次」分開：同輪重試只有在模型嘗試次數與有效執行時間都未用盡時可用；用盡後可由管理員明確選擇失敗項目重新分析。新輪次預設保留原 commit、include/exclude、凍結模型組合與來源結果，僅重設新輪次的計數；每個來源失敗項目只能建立一個直接後繼。若改用目前模型，確認會綁定畫面顯示的 selection generation，設定已變更時必須重新檢視。Migration 26 新增不含秘密的批次／項目 lineage、輪次與失敗階段；migration 27 讓來源使用標記與有界冪等綁定在一般清理後仍維持正確。

只改服務名稱時保留原網址與金鑰；更換網址是獨立選項。同一連線方式且協定、主機與有效連接埠不變時，只修正路徑（例如補上 `/v1`）可沿用已儲存的金鑰；更換 origin 或連線方式仍須替換或移除金鑰。所有服務新增、更新、刪除與清單更新失敗都會在實際操作的面板顯示單一錯誤摘要，說明安全原因、原設定是否保留及下一步，並在可用時提供診斷代碼。新輸入的金鑰會在送出或收合表單後清除，失敗重試時會明確提醒重新填入。

此次資料庫升級包含 runtime migration 19 與後續 migration 20，首次載入新版後端時交易式升級。保留舊資料與模型選擇，失敗會回復；正式 bundle 格式不變。完整修復清單與證據見 [UI／UX 修復紀錄](docs/UI_UX_REVIEW_2026-09-12.md)。

Runtime migration 22 會修復舊版在服務更新後仍停留於舊 revision 的安全候選模型，並保存歷史 revision 的 provider 資訊。升級本身不會呼叫模型；重新啟動新版後端後，受影響的模型會顯示需要重新測試，按一次「測試模型」即可驗證新服務。

Runtime migration 23 為失敗的批次項目新增安全、封閉集合的 `error_reason`。分析頁重新整理後仍會顯示錯誤代碼、原因與建議動作；原始 repository／prompt／模型回覆、私人網址與憑證不會寫入錯誤欄位。

模型測試失敗會顯示實際 HTTP 狀態碼與服務商錯誤原文，不翻譯或推測原因。原文會遮蔽已知金鑰及私人網址，並限制長度；無可顯示文字時會明確提示。舊版本未保存的原文需按「測試模型」重新取得。詳見 [錯誤原文修正紀錄](docs/PROVIDER_ERROR_MESSAGES_2026-09-12.md)。

### Visitor chat processing (2026-10-04)

Live chat shows expandable real processing stages, elapsed waiting time and a
stop action. The total deadline defaults to 180 seconds (max 300; explicitly
configured lower settings remain valid). Native Ollama thinking activity is
visible as a phase; thinking text stays private. Generic APIs show only actual
supported activity. Answers still receive full citation/person validation.
See docs/CHAT_PROCESSING_CONTRACT_2026-10-04.md for the unfinished thinking-text
request and the separate public-summary option.

## Approved public summary amendment (2026-10-04)

OR-032 / ADR-058 / Specification 0.4.10 adopts the [public summary contract](docs/CHAT_PUBLIC_SUMMARY_CONTRACT_2026-10-04.md). FR-040/043/044/047, NFR-005/009/014 and AC-019/023/057/062/063/064/068/071 retain their thresholds. Explicit Responses selection, legacy/revision compatibility, bounded untrusted plain text, prompt/secret negative tests, final-answer separation, cancellation and bilingual keyboard-accessible display require verification. No real provider invocation, publication, catalog admission or release acceptance is implied. Previous pending-summary notes are historical and superseded by this approval.

<details>
<summary>歷史實作紀錄（以各日期範圍為準）</summary>

**2026-10-03 接續實作：**正式 builtin 檢索基準 AC-009 已通過；已補600組實際雙語／明暗browser對比與隔離已安裝版維護／資料保留證據。聊天與分析預設／最大生成預算為16,384 token，支援推理的Ollama保持推理開啟，並檢查輸入與生成額度的context空間；較低的明確舊設定保留。此日紀錄的公開聊天期限後來由 ADR-057 更新為預設 180 秒、最高 300 秒；20s 模型探測與 300s 分析 provider 期限維持。最終Python2613項通過／2項既有Windows略過，完整Windows候選已重建。擁有者批准只修正兩事實測題、保留判分；新12題重驗9/12，兩個修正案例均通過，另三題未通過，正式catalog維持空白。Man最終圖像／權利、clean Windows、完整無障礙與外部驗收仍未完成；16k包含推理與答案，不保證生成16k字。詳見[最新接續交接](docs/CONTINUATION_HANDOFF_2026-10-03.md)；下列舊進度保留原範圍。

**A5 本機檢查後暫停（2026-09-30）：**ChatGPT 第六輪接受先前修補，另指出 FAQ 技術路徑與點號可錯配；Luna max 已修正，Main 以六個失敗案例重測。最終 Web 377 項、格式、lint（0 錯誤／19 警告）、型別、正式建置、來源防護及新建映像的 Docker 2 項通過；62 個未改動的後端輸入沿用 Python 1,638 通過／2 項略過。最後修補尚未交 ChatGPT 再審；靜態聊天傳送仍待明確授權，A5 尚未完成。詳見[交接指南](docs/A5_HANDOFF_2026-09-30.md)。

**訪客頁與外觀（A5／R08，本機檢查中）：**共用聊天頁、五套雙版本配色、私人圖片草稿與預覽、無模型外觀套用／取消、已核准 FAQ 替代問法與離線比對，以及只包含公開內容的 Pages ZIP 已實作。管理頁保存 Pages 完整網址；匯出使用需登入且無副作用的原生下載，核對時重新建立本機 manifest 並逐位元組比對入口頁與 manifest，成功後才產生卡片連結。請依[雙語手動分享指南](docs/PAGES_SHARING_GUIDE.md)操作；[A5 契約與檢查範圍](docs/A5_VISITOR_APPEARANCE_EXPORT_CONTRACT.md)記錄進度。第六輪指出的 FAQ 技術片段碰撞已本機修正並重測；Pages 即時問答仍待明確的傳送內容／目的地授權，原生 ZIP 落盤與真正 200% zoom 未確認，A5 尚未結案。沒有公開部署。

**訪客專用公開入口（A1，本機完成）：**規格 0.4.6 / ADR-053 的第二個 loopback listener、封閉公共 API、私人管理入口與雙語管理控制已完成本機實作及審核。預設關閉，擁有者可設定、啟動並記錄外網檢查；尚未啟用 Funnel 或取得外網驗收。完整契約、驗證結果與後續 A5／A12 範圍見 [A1 gateway 契約](docs/A1_FUNNEL_GATEWAY_CONTRACT.md)。

**涵蓋檢查與 FAQ（A4，本機已實作）：**「預覽、試聊與分享」可明確使用模型檢查六個標準問題；缺口不會阻擋發布。FAQ 可核准、拒絕、重產或改寫成作者自述；自述保存後會先更新索引再生成，仍需審核。只有目前版本已核准的回答會提供給訪客或下載為 JSON。換版本須重新生成與確認；訪客問題按鈕直接顯示已核准回答，不呼叫模型。完整 Pages 靜態匯出與離線比對仍屬 A5。詳見 [A4 契約與驗證範圍](docs/A4_COVERAGE_FAQ_IMPLEMENTATION.md)。


</details>

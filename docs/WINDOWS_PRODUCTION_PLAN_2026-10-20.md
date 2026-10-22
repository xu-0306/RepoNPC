# Windows 正式模式計劃（ADR-070 草案，2026-10-20）

**狀態：** 擁有者在 2026-10-20 核准，第 4 節 D1–D7 全部採用建議選項（ADR-070 Accepted）。W1（378af5b）、W2（f2e1322）與 W3（2026-10-22）已完成；實測待完成。

## 1. 目標

讓擁有者在自己的 Windows 電腦上用 `production` profile 執行 RepoNPC，並透過 Tailscale Funnel 讓訪客使用即時聊天。管理介面維持只在本機。

ADR-048 與 [A1 閘道契約](A1_FUNNEL_GATEWAY_CONTRACT.md) §1 已核准「Windows 安裝＋擁有者自行操作官方 Tailscale」，A8 待辦也寫「閘道隨安裝版運作」。但現行程式與 README（ADR-069）只把 Windows 當本機試用。兩份同層級來源互相矛盾，需要擁有者裁定。

## 2. 現況（已在程式碼與本機核對）

- 兩個 Windows 入口都固定使用 `loopback_evaluation`：
  - 原始碼啟動器 `scripts/start-reponpc.ps1:444`；
  - 安裝版 `src/reponpc/windows_launcher.py:106-141`。
- 訪客閘道只在 `production` 啟動（`src/reponpc/api/visitor_gateway.py:451`）。所以 Windows 現在無法對外分享。
- Windows 上，所有私密檔權限檢查都被跳過，因為它們只在 POSIX 執行：
  - `config/environment.py:565`：secret 檔；
  - `admin/model_connections.py:832-839`：模型金鑰 `model-secrets/master.key`；
  - `windows_launcher.py:83`：IP 金鑰；
  - `local_portfolio.py`、`maintenance.py`、`scene.py`、`passage_cache.py`、`builtin_download.py` 的 0600/0700 在 Windows 沒有效果。
- 原始碼啟動器會把 secret 檔讀出來，直接放進環境變數（`Import-LocalSecretFiles`），因此繞過了檔案檢查。
- 本機 `icacls` 結果（2026-10-20）：
  - repo 內的 `D:\RepoNPC\runtime-data\local` 繼承了 `Authenticated Users:(M)` 和 `Users:(RX)`，同一台電腦的其他帳號都能讀到 `runtime.sqlite`（含擁有者密碼 hash）和 `master.key`；
  - `%LOCALAPPDATA%` 也有額外繼承的權限項目（沙箱群組、AppContainer SID）。
  
  所以正式模式不能依賴繼承來的權限，必須自己設定受保護的 ACL。
 - D6 已因 [ADR-071](DECISIONS.md#adr-071-archive-legacy-paths-and-documents) 失效：舊的索引變數已移除，設定了會被當成未知變數而無法啟動。
- 以下已經可以使用：
  - `production` 接受 `http://localhost:<port>` 這類 loopback 管理來源；
  - `reponpc admin setup-code`；
  - `reponpc admin set-password`。規格「Local-first owner and recovery」已規定：沒有密碼的本機擁有者，要先執行它才能轉為正式模式。
  - Funnel 指令與 Linux 相同，RepoNPC 不會替擁有者執行它。

## 3. 提議設計

### 3.1 拓撲

Windows 正式模式就是 `production` profile 加上以下設定，不新增 profile 名稱，也不新增公開綁定：

- 主程式綁定 `127.0.0.1:<port>`；
- 管理來源固定為 `http://localhost:<port>`，而且必須明確設定；
- 訪客閘道綁定 `127.0.0.1:<visitor-port>`；
- Funnel 只指向訪客閘道。

### 3.2 切換

切換只能由擁有者明確操作，不會自動升級；沒有設定時維持試用。兩個入口的設定方式見 D2。

### 3.3 首次登入

- **新的資料目錄：** 服務就緒後，啟動器在主控台印出一次性 setup code（主機證明，ADR-016），再開啟 `/admin`。擁有者輸入 setup code、帳號，以及至少 15 字的密碼（ADR-024）。
- **從試用轉過來、已有無密碼擁有者：** 啟動器偵測到這個狀態後，在主控台要求擁有者設定密碼，並呼叫現有的 `set-password` 流程。完成前不開啟瀏覽器。
- `production` 原本就不簽發 local-launch 授權。

### 3.4 私密檔與資料目錄（Windows ACL）

- 新增一個共用 helper，同時處理建立與檢查。它取代上述各處 `os.name == "posix"` 的判斷，不另開平行路徑。
  - POSIX：沿用 0600/0700。
  - Windows：以 ctypes 呼叫 advapi32，不新增相依套件（見 D4）。
- **允許的 SID：** 目前程序的使用者、SYSTEM（`S-1-5-18`）、Administrators（`S-1-5-32-544`）。
  - `OWNER RIGHTS`（`S-1-3-4`）只授權給物件擁有者；擁有者已限定為目前使用者或 Administrators，所以也允許。Python 3.13 以後的 `mkdir(mode=0o700)` 在 Windows 上就是用它（W1 實作時確認）。
  - 任何其他 SID 的允許 ACE 一律拒絕，包括 Everyone、Authenticated Users、Users，以及沙箱或 AppContainer SID。
  - 擁有者必須是目前使用者或 Administrators。
- **建立時：** 關閉繼承（protected DACL），只放上述三個 SID。
- **檢查範圍：**
  - secret 檔：沿用 `unsafe_secret_permissions`；
  - `model-secrets/master.key`：沿用 `MODEL_SECRET_STORAGE_UNAVAILABLE`；
  - 正式模式啟動時檢查資料目錄根：錯誤碼見 D4。
- **Windows secret root：** 預設為 `<REPONPC_DATA_DIR>\private`，與安裝版相同，不新增環境變數。在正式模式下，原始碼啟動器改為傳入 `_FILE` 路徑，交給 `environment.py` 統一檢查，不再把值放進環境變數。

### 3.5 Funnel（Windows）

1. 從 Tailscale 官方網站安裝 Windows 版並登入。
2. 在 tailnet 管理頁啟用 HTTPS 憑證，並允許這台機器使用 Funnel。
3. 在 RepoNPC 分享頁設定訪客來源 `https://<機器>.<tailnet>.ts.net`，然後啟動閘道。
4. 在 PowerShell 執行 `tailscale funnel --bg --https=443 http://127.0.0.1:<visitor-port>`。
5. 關閉時執行 `tailscale funnel --https=443 off`。

補充說明：

- 不需要 Windows 防火牆的入站規則，因為流量經由 tailscaled 進入 loopback。
- 一般權限的 PowerShell 能否執行 `tailscale funnel`，要在實測時確認。
- 電腦睡眠或 RepoNPC 結束時，Pages 頁面會顯示「休息中」並改用已核准的 FAQ（ADR-048 設計）。分享期間請在電源設定關閉睡眠。

### 3.6 仍不支援

- Windows Docker Desktop 正式部署：bind mount 的權限問題，以及容器的 loopback 不等於主機的 loopback。
- 以 Windows 服務方式執行，或開機自動啟動（之後另議）。
- 非 loopback 綁定，例如在區網開放管理介面。
- 有不可信系統管理員的多人主機：Administrators 永遠讀得到資料。
- RepoNPC 自動執行任何 tailscale 指令。

## 4. 擁有者決定

| # | 決定 | 選項 | 建議 |
|---|---|---|---|
| D1 | 哪些入口支援正式模式 | (a) 安裝版和原始碼啟動器都支援，共用同一套 Python 驗證與 ACL helper；(b) 只支援安裝版；(c) 只支援原始碼啟動器 | (a)：8090 目前跑在原始碼啟動器，AC-069 的新手路徑則是安裝版 |
| D2 | 切換方式 | (a) 原始碼啟動器讀取 `.env` 的 `REPONPC_DEPLOYMENT_PROFILE`，不再強制覆寫；安裝版新增捷徑「RepoNPC（正式模式）」，帶 `--profile production`；(b) 安裝版改在主控台選單切換並記住選擇，需要多一個設定檔 | (a)：不新增設定檔，兩種模式並列，擁有者看得見目前用哪一種 |
| D3 | 首次登入 | (a) 啟動器在主控台代為取得 setup code，並執行 `set-password` 流程；(b) 只寫文件，請擁有者自己執行 CLI | (a)：安裝版的 CLI 不在 PATH 上，新手不易操作 |
| D4 | ACL 實作與資料目錄錯誤碼 | 實作：(a) ctypes，不新增相依；(b) 新增 `pywin32` 相依。錯誤碼：(c) 在 `REPONPC_DATA_DIR` 上沿用 `unsafe_secret_permissions`；(d) 新增 `unsafe_data_directory_permissions`（新的錯誤碼需要核准） | (a)＋(c)：資料目錄本身就存放 `master.key` 與擁有者密碼 hash，不必新增錯誤碼 |
| D5 | 既有資料目錄的權限過寬 | (a) 啟動器停止並顯示一行 `icacls` 指令，由擁有者自己執行；(b) 啟動器先詢問，再代為收緊 | (a)：權限變更由擁有者明確執行；安裝版的新資料目錄建立時已受保護，不會遇到這個情況 |
| D6 | 舊的 GitHub 索引變數 | 已由 [ADR-071](DECISIONS.md#adr-071-archive-legacy-paths-and-documents) 封存；變數現在視為未知設定並必須刪除。 | 不適用 |
| D7 | `.env` 中的直接 secret 值 | (a) Windows 正式模式拒絕，改放 `private\` 檔；(b) 允許，但另外檢查 `.env` 的 ACL | (a)：只有一個需要檢查的位置；模型金鑰本來就從 GUI 輸入並加密保存 |

不需要另外決定、直接沿用的項目：

- 正式模式的密碼至少 15 字並套用封鎖清單（ADR-024）；
- 驗證、主機證明、cookie、CSRF、閘道規則不變；
- 沒有新的 API 欄位；
- 除了 D4(d) 之外，沒有新的錯誤碼。

## 5. 實作與測試計劃（核准後）

### W1 後端（Codex）

- 共用的 private-file helper（POSIX＋Windows），並替換上述所有呼叫點。
- 在 Windows 上，secret root 預設為 `<data_dir>\private`，因此要先解析 data_dir。
- 正式模式啟動時，在 Windows 上檢查資料目錄 ACL。
- 測試：
  - Windows 上用真實檔案測試：helper 建立的檔案可以通過；加入 Everyone、Users 或 Authenticated Users ACE 會被拒絕；繼承來的 ACE 會被拒絕；擁有者不符會被拒絕。
  - POSIX 維持原本的測試。
  - 環境驗證測試，以及 canary 不外洩。
  - ruff、mypy、完整 pytest。

### W2 啟動器（Codex）

- `start-reponpc.ps1` 在 production 分支中：
  - 不簽發 launch 授權；
  - 處理 setup code 與 set-password 的主控台流程；
  - 傳入 `_FILE` 路徑，並拒絕直接 secret 值；
  - 建立受保護的 `private\`；
  - ACL 檢查失敗時，停止並顯示指令。
- `windows_launcher.py` 支援 `--profile production`，使用相同流程；Inno Setup 新增第二個捷徑。
- 測試：擴充 `tests/contract/test_local_launcher.py` 與安裝版的單元測試。

### W3 文件與畫面文字

- 依第 6 節更新 README、OPERATIONS 與 `packaging/windows/README.md`。
- 分享頁在試用模式下原有的「需要正式模式」提示保留；正式模式下表單照常可用，不新增說明段落。

### 實測（主代理與擁有者）

1. 用新的資料目錄啟動正式模式，確認 setup code 與登入可用。
2. 用 8090 的備份複本啟動正式模式：
   - 重現 ACL 拒絕，並用顯示的指令修正；
   - 執行 set-password 後登入。
3. 用 `icacls` 證明 `private\`、`master.key` 與資料目錄只剩三個允許的 SID。
4. 擁有者執行 tailscale 指令後：
   - 用行動網路從外部開啟 Pages 頁面並即時聊天；
   - 透過 Funnel 存取 `/admin` 應回 404。
5. 關閉 Funnel 或讓電腦睡眠，確認頁面顯示「休息中」與 FAQ。
6. 8090 必須經擁有者同意才能重啟，重啟前要先備份。外部驗收依 A12 另行記錄。

## 6. 實作時套用的使用者文件文字（現在不改）

README 與 OPERATIONS 描述的是已出貨的行為。在實作完成前改動它們，會宣稱一個還不存在的功能，所以等 W3 再套用：

- 刪除「Windows 只供本機試用／不支援 Windows 正式模式」（README:36、:67；OPERATIONS:336、:364、:581）。
- 中文改為「要讓訪客使用，請以正式模式啟動（`.env` 設 `REPONPC_DEPLOYMENT_PROFILE=production`，或使用「RepoNPC（正式模式）」捷徑），再依 Funnel 步驟操作。」英文與中文對等。
- OPERATIONS 新增 Windows 正式模式小節：
  - 第 3.3 節的首次登入；
  - 第 3.4 節的 `icacls` 修正指令（W2 實作，啟動器依實際狀況印出其中一行）：
    - 資料目錄根：`icacls "<資料目錄>" /inheritance:r /grant:r "*<目前使用者 SID>:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F"`，若根目錄有其他帳號的明確項目，後面再加 `/remove:g "*<SID>" …`；
    - 根目錄已通過、但 `private\` 或其中的金鑰有明確的其他帳號項目：`icacls "<路徑>" /reset /T`（改為繼承已受保護的根目錄）。
    - 2026-10-22 實測：繼承來的過寬權限，修正根目錄後子項（含 `runtime.sqlite`、`master.key`）會一併更新；對檔案使用 `(OI)(CI)` 會讓授權失效，所以檔案一律用 `/reset`；
  - 第 3.5 節的 Funnel 步驟；
  - 第 3.6 節的不支援項目。
- README:118 與 OPERATIONS:172 的 Docker Desktop 說明維持不變（仍不支援）。

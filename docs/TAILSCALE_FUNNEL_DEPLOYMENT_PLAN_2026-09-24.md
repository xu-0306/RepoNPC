# RepoNPC：免購買網域的 Tailscale Funnel 公開部署計劃

日期：2026-09-24。狀態：**擁有者已選定公開入口方向；尚未實作或驗收**（ADR-047）。

本計劃接續 ADR-046 的本機草稿、索引啟用、試聊及 GitHub 卡片流程。擁有者選擇 Tailscale Funnel 作為一般個人使用者不購買網域時的預設公開入口。這項選擇不表示現有 Windows 本機啟動器、Compose 或分享頁已能安全公開，也不表示已建立 Tailscale 帳號、Funnel 或 GitHub Profile 連結。

## 1. 產品目標與邊界

- 使用者完成本機 NPC 後，可選擇「讓外部訪客連線」，取得由 Tailscale 管理的固定 `https://<device>.<tailnet>.ts.net` 訪客網址；訪客不需安裝 Tailscale。
- 本機建立、預覽、試聊和備份不依賴 Tailscale。公開連線是由擁有者明確啟用、可停用的額外步驟；連線失敗不撤銷已啟用的本機索引。
- Tailscale 提供入口與 HTTPS，不提供 RepoNPC 主機、Ollama、聊天模型或免費推論。主機和模型必須持續可用；不得自動改用其他 provider。
- 預設路徑不要求購買網域、開放路由器入站埠、GitHub Actions、Release 或 GitHub 寫入憑證。保留既有自行管理的 HTTPS 入口作為進階部署方式。
- Tailscale Funnel 目前為 beta，存在不可自行調整的頻寬限制；免費 Personal 方案有使用資格限制。引導不得保證永久免費、固定可用率或無限流量。[Funnel 官方文件](https://tailscale.com/docs/features/tailscale-funnel)、[方案](https://tailscale.com/pricing)。

## 2. 必須維持的拓撲

```text
外部訪客 → 公開 HTTPS *.ts.net → Tailscale Funnel → 僅允許訪客路由的閘道 → RepoNPC production
擁有者   → 本機 loopback／SSH／私人 Tailscale 連線 ──────────────→ 同一 RepoNPC 管理服務
RepoNPC  → 私人模型連線（Ollama／vLLM／已選 OpenAI-compatible 服務）
```

Funnel 不能直接指向可處理 `/admin` 的完整應用程式埠。公開閘道採預設拒絕，僅放行訪客頁所需靜態資源及 `/api/public/*` 等經測試的路由；`/admin`、`/api/admin/*`、模型埠、資料目錄和任何非訪客路由必須在公開入口不可達。閘道和應用仍維持同源的訪客頁與 API，不以瀏覽器直連模型、跨來源 CORS 或公開管理登入替代此隔離。管理者從私人路徑登入時仍須符合 `production` 的 setup code、密碼、Host／Origin、CSRF 和 session 契約。

在選定閘道設定前，先以目前前端資源路徑及 API 清單生成封閉路由表，並測試路徑編碼、大小寫、尾斜線、未知路由與重導向。還須查明 Funnel 轉送的實際來源資訊；不得未經驗證就信任用戶可偽造的 forwarded headers，或讓所有訪客共用一個錯誤的限流身分。若私人管理網址與 `REPONPC_PUBLIC_BASE_URL` 的現有同源驗證相衝突，先提出受控規格修訂並完成安全測試，不透過放寬 CORS 或 Origin 檢查繞過。

## 3. 安裝與引導工作批次

| 批次 | 交付 | 完成門檻 |
| --- | --- | --- |
| F0：契約與預檢 | 凍結支援的主機、Docker／Tailscale 版本、閘道、Host／Origin、來源 IP、秘密和備份契約；更新規格、驗收、操作文件 | 已有清楚的失敗與回復路徑；不將本計劃當成已通過的公開部署證據 |
| F1：可重現安裝 | 以鎖定映像、持久化資料卷與受保護密鑰啟動 RepoNPC；檢查 Docker、磁碟、模型可達性和 `production` 管理帳號；本機先可預覽／試聊 | 乾淨支援主機可安裝、重啟、備份、恢復；未啟用分享時無公開入口 |
| F2：Funnel 接入 | 擁有者登入／授權 Tailscale、明確啟用 Funnel；建立訪客專用閘道、固定 HTTPS URL 和停用操作 | 從非 tailnet 網路可存取訪客頁與聊天；公開管理及模型路由均被拒絕；停用後入口失效而本機資料保留 |
| F3：Web GUI 分享引導 | 顯示「本機可用」「入口已設定」「外網已驗證」三種不同事實；通過外網檢查後才提供可用的 GitHub 卡片連結 | 中英文、鍵盤、螢幕閱讀器、手機寬度與復原提示可用；沒有空白、localhost 或未驗證連結被當成上線成功 |
| F4：發布驗收 | 真實主機、外部網路、實際 GitHub Profile 點擊與瀏覽器矩陣 | 完成 AC-022／AC-036／AC-049 及本入口新增的安全與可用性驗收；分開報告本機、外網和 GitHub 實測 |

安裝器的第一階段以已安裝 Docker 與使用者可連線的模型為前提。自動安裝 Docker、將 Ollama 加入 Compose、替使用者挑選或下載聊天模型是各自的可選工作，不是 Funnel 的必要條件；模型下載需顯示資源需求並由擁有者明確啟動。不得把官方第三方執行環境暗中打包成 RepoNPC 自有 runtime。

## 4. 擬定的一般使用者配置流程

以下是 F1–F3 要實現的 Web GUI／安裝引導順序，**不是目前版本已可操作的安裝說明**。精靈必須讓使用者知道自己要準備什麼、目前完成到哪裡，以及出錯後如何回到本機可用狀態。正式支援的主機與安裝器形式仍由 F0 定稿；現有 Windows loopback 啟動器不能充當公開服務。

| 順序與畫面 | 使用者操作 | RepoNPC／安裝器應做的事 | 完成訊號與失敗處理 |
| --- | --- | --- | --- |
| 1. 環境檢查 | 在受支援的主機安裝並啟動 Docker，選擇受保護且有空間的資料位置；準備可從容器連線的模型服務 | 檢查 Docker、Compose、架構、磁碟與模型連線條件；建立鎖定版本的應用容器、持久化資料及必要秘密 | 顯示「本機服務已啟動」；缺少 Docker、權限或磁碟空間時給出具體修復步驟，不建立公開入口 |
| 2. 私人管理員啟用 | 只從本機 loopback、SSH 或私人 Tailscale 路徑取得一次性 setup code，設定管理帳號與密碼 | 使用 `production` 的既有 setup-code、Host／Origin、CSRF 和 session 保護；引導只在私人端顯示 | 管理介面可重新整理並維持有效登入；現行 setup code 由 CLI 產生，若改由 GUI 代辦，須先完成 F0 安全契約 |
| 3. 模型設定 | 選 Ollama、vLLM 或支援的 OpenAI-compatible 服務，分別選好聊天與資料查找模型並明確測試 | 檢查服務可達、模型能力與必要的 embedding 身分；只保存受保護的連線設定，不在公開頁讀回金鑰 | 兩種模型測試通過後才提示進入分析；模型未安裝或不可用時維持私人設定流程，不自動換 provider |
| 4. 建立 NPC | 選公開 GitHub 專案、確認自己的角色與貢獻、設定角色素材，建立索引並在本機試聊 | 保存草稿、分析及啟用通過驗證的 bundle，提供雙語預覽與引用檢查 | 顯示「本機可用」；即使尚無 Tailscale 帳號或公開網址，仍可編修、備份和試聊 |
| 5. 啟用外部訪客 | 主動選「讓外部訪客連線」，在 Tailscale 官方流程登入／授權並同意公開此 NPC | 檢查 Tailscale／Funnel 資格及狀態，啟動預設拒絕的訪客閘道，讓 Funnel 只連到該閘道；提供停用控制 | 取得 `https://<device>.<tailnet>.ts.net` 後只顯示「入口已設定」；未授權、DNS／憑證未就緒或啟用失敗時保留本機 NPC，且不宣稱已公開 |
| 6. 外網驗證 | 使用不在 tailnet 的裝置或獨立網路實際開啟網址、提問並查看引用 | 檢查訪客頁與 API、真實 SSE、管理／模型路由拒絕、限流及分享狀態；若無可信的獨立外網探測，就引導使用者手動驗證並如實標示未自動驗證 | 通過後才顯示「外網已驗證」與可分享連結；連線中斷、主機或模型離線時回報具體原因 |
| 7. 放到 GitHub Profile | 確認或建立與帳號同名的公開 repository，上傳卡片並把 Markdown 加到 `README.md`，從 Profile 實際點入 | 提供卡片檔、含已驗證訪客網址的 Markdown 和逐步檢查；沒有 GitHub 寫入憑證時不代替使用者提交 | Profile 卡片可顯示且連到問答頁；卡片可留在 GitHub，但聊天仍依賴主機、模型與 Funnel 在線 |

第一次安裝預期只要求使用者提供自己的 Docker 環境、可連線的模型、公開 GitHub 帳號，以及公開分享時的 Tailscale 帳號與授權。Tailscale 登入資訊不得填入 RepoNPC 表單；若使用者不分享，步驟 5–7 可以稍後再做。日後的「自動安裝 Docker／Ollama／模型」必須另列選用範圍，不能當成此流程已交付的能力。Funnel 官方啟用流程可能要求 MagicDNS、HTTPS 憑證與 tailnet Funnel 權限；精靈應顯示其實際檢查結果，不能以推測取代授權或外網測試。

## 5. 驗收情境與故障恢復

1. 在受支援的乾淨主機上啟動 `production`，先完成本機作品集和模型測試；Tailscale 未登入、未獲准使用 Funnel、DNS／HTTPS 未就緒、流量限制或主機離線時，本機工作仍可用，分享頁顯示具體原因與下一步。
2. 從獨立外網裝置驗證公開網址、靜態卡片資源、繁中與英文訪客頁、`/api/public/status`、真實 SSE 聊天、引用連結、取消及重新整理；不得只以 URL 格式或本機 `curl` 判定可分享。
3. 從同一外網裝置驗證 `/admin`、`/api/admin/*`、模型埠、未知路由、編碼變體及常見重導向皆無管理功能／秘密；私人管理路徑仍可登入、重新整理和登出。
4. 驗證公開訪客的限流身分、總並行與每日預算在代理後仍生效，且原始 IP、token、Funnel 憑證、模型 URL／key 不進入公開回應、卡片、日誌或可攜匯出。
5. 重啟、Funnel 中斷與復原、撤銷 Tailscale 裝置、停用分享、升級及還原資料後，確認 last-known-good bundle、本機管理和公開狀態顯示均符合真實情況。
6. 最後才將已驗證的 URL 放進 GitHub 卡片，從真實 Profile README 點入問答並驗證引用。任何 GitHub 寫入仍由擁有者另行明確執行。

## 6. 尚待 F0 定稿的實作契約

- 正式支援的安裝主機：現有規格以 x86_64 Linux Docker 為參考；Windows launcher 僅供 loopback 評估，不能原樣接到 Funnel。若增加 Windows 長期公開部署，需另訂生命週期、更新與安全驗收。
- Funnel connector 與訪客閘道在主機或 Compose 中的責任邊界，以及 Tailscale 登入／裝置憑證的最小權限、持久化與撤銷方式。憑證不得進入 RepoNPC 公開設定、瀏覽器儲存、日誌或映像檔。
- 私人管理網址與公開 `*.ts.net` 網址如何同時通過現有 Host／Origin／session 防護；代理後可靠的訪客限流來源如何取得與驗證。
- 實際 SSE、可用性、頻寬及 GitHub 圖片／連結驗收結果。Funnel beta 或免費資格變動時，保留本機使用並提示進階自行管理 HTTPS 入口，不自動切換到另一個公開服務。

本文件是已選方向的實作計劃，不是網路服務授權或發布報告。本次文件更新不啟用 Funnel、不變更 Docker 配置、不安裝 Tailscale，也不修改任何 GitHub repository。

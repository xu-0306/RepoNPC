# RepoNPC 完整實作待辦與分派計劃（2026-09-26）

**2026-10-03 最新接續：**以[接續交接](CONTINUATION_HANDOFF_2026-10-03.md)記錄本輪成果與未完成工作。正式builtin AC-009通過；推理開啟／16384預算及完整Python2613項／2既有略過通過。修正後雙語模型suite9/12，catalog維持空白；實際600views對比、已安裝加密還原與保留資料的解除安裝均有部分證據。Man最終圖像／權利、clean Windows、真正200%zoom／screen reader／完整互動矩陣與外部閘門仍未完成。下方原待辦保留當時範圍。

**2026-10-03 最新並行批次：** 三位 GPT-6.1 Sol 已交付 A6 真實固定模型與本機 Ollama 證據、A8 開發機隔離安裝／合成 patch 升級／移除／資料保留及已安裝 A11 API 還原、A9 私有 Man／A5 fixtures。Root 完成 A7 模型卡片與明確填入、LICENSE／notices／compiler 版本修復和整合驗證：Web484／42、affected Python226、Ruff258／mypy103、wheel／installer build、300 checksums 通過。見[最新交接](PARALLEL_IMPLEMENTATION_HANDOFF_2026-10-03.md)。正式 catalog 仍空，Man 仍需修圖和來源授權；formal AC009 baseline、clean Windows／installed native browser、完整 A5 輔助技術／真正200%zoom 及外部 A12 仍未驗收。下方舊「最新」紀錄是當時快照；沒有提升 ledger AC。

**2026-09-29 A1 本機完成：** [A1/F0 契約](../../docs/A1_FUNNEL_GATEWAY_CONTRACT.md)（OR-027／ADR-053，規格 0.4.6）由 gpt-6-luna max 實作，Main 審核並修正共用安全邊界與競態。Python 1,260 passed／2 skipped、Web 230 passed、Docker 2 項與原生瀏覽器 8 組檢查通過；詳見契約 §10 與[本機紀錄](../../release-evidence/a1/local-checks.md)。未啟用 Funnel，外網驗收仍屬 A12；下一主線是 A5。

狀態：**實作中**。本文件彙整 ADR-046 之後所有尚未實作或尚未驗收的工作，作為交給其他 agent 的單一入口。決策依據以 [完成方向契約](../../docs/COMPLETION_DIRECTION_CONTRACT_2026-09-26.md)、Approved `TECHNICAL_SPEC.md` 0.4.7、`DECISIONS.md` ADR-046～ADR-054 與 `ACCEPTANCE_CRITERIA.md` 為準；A11 選項 A 已由 OR-028 核准。本文件只負責排序、相依與分派，不新增產品決策。

## 0. 目前基準

- 擁有者授權的 A1～A4／formatter 提交已於 2026-09-29 推送，基準為 `main@877c6d6`。2026-10-03 本機 A5～A12 批次保留 dirty working tree，尚未以本文件宣稱 commit／push；新批次 push 需另行授權。提交數與工作樹狀態以當次 `git status` 為準。
- 已完成並有本機證據：ADR-046 本機草稿／索引啟用／本機試聊／三步驟 GitHub 卡片引導；R01–R07、R09、R10、R12-A、R14 訪客聊天與卡片長文字子批次；R13 的 64px canonical、converter 與「角色與動畫」工作區。
- ADR-048～ADR-052（規格 0.4.0～0.4.5、FR-043～FR-053、AC-062～AC-079）已開始實作：A2 回答政策 v2、A3 參與事實與 A4 覆蓋檢查／FAQ 已取得本機證據；A10/R11 近期批次恢復、A10/R12-B passage cache 重用量測與公開路由／bundle 匯出／runtime backup 排除測試亦已完成本機驗證。A3 已保存於 `1e82ee8`，實際 bounded 本機／reindex 建置的參與事實修正為 `cf948f8`（58 項 focused checks）；A4 已完成本機實作與 Main 審核；完成提交為新增 A4 實作文件的 `feat(admin): add coverage checks and reviewed FAQ`，驗證見[本機紀錄](../../release-evidence/a4/local-checks.md)。正式驗收帳本與發布閘門待 A12。
- 歷史驗收帳本 `release-evidence/acceptance-ledger.json` 保持 byte-identical：只涵蓋 AC-001～AC-061（3 pass、6 blocked、52 not-run），`source_identity` 仍是 2026-09-10 的髒工作樹。新的 [A11 候選快照](../../release-evidence/a11/acceptance-ledger-candidate-20261003.json)涵蓋 AC-001～AC-079，76 not-run、3 blocked（AC-020／037／069），保留 AC-041～043 退役歷史說明；列舉完整不代表實際 AC pass。Root 最終 source fingerprint 另記，不得以任一帳本計算完成百分比。

**2026-10-03 最新本機交接：** A6／A7 模型設定、A8 frozen host 與 A11 維護功能已有本機實作及 partial evidence；A11 選項 A（加密 SQLite-only、同主機同資料目錄還原）已獲 owner／ADR-054／OR-028 核准。最新 Web **480 tests／42 files passed** 並完成 production build；Python baseline **2,497 passed／2 existing Windows skips**（新增 protected native GET 前），其後 affected subset **181 passed／1 warning**，兩者不可相加；Ruff **260 files**、mypy **103 source files** 與最新 wheel build 通過。詳見 [Web](../../release-evidence/a6/web-a11-native-download-final-20261003.log)、[Python baseline](../../release-evidence/a6/python-a11-final-20261003.log)、[affected subset](../../release-evidence/a6/python-a11-native-root-final-20261003.log)、[Ruff](../../release-evidence/a6/ruff-a11-native-final-20261003.log)、[mypy](../../release-evidence/a6/mypy-a11-native-final-20261003.log)及 [wheel](../../release-evidence/a6/wheel-a11-native-final-20261003.log)。

完整 `build_windows.ps1 -SkipInstaller` 的 [A11 native-download build](../../release-evidence/a6/windows-build-a11-native-download-final-20261003.log)成功；outside-checkout frozen smoke **2.3415 秒／exit 0**，僅驗證無模型 health 與 owned shutdown，見 [JSON receipt](../../release-evidence/a6/windows-frozen-smoke-a11-native-final-20261003.json)及[摘要 log](../../release-evidence/a6/windows-frozen-smoke-a11-native-final-20261003.log)。EXE SHA-256 為 `12cb22f65be4a66fae8006f263452659be537a2a40e06c2c3f70407c29ced2ff`。中英文 in-app browser 均完成 protected native GET 的相同密文下載，下載檔 upload／inspect／cancel 成功，見 [download receipt](../../release-evidence/a11/browser-native-download-20261003.json)；Root 已保存 real Main／MaintenanceHost 還原與八組雙語 responsive profile 的局部本機證據，尚未關閉 AC-076。

[Restore state](../../release-evidence/a11/browser-native-restore-state-20261003.json)記錄 keyboard Space→Tab→Enter 經真實 host 將 synthetic CURRENT sentinel 還原為 BASELINE，sessions／previews 均為 0、gateway off、integrity ok，三份 host ciphertext backups 全部 authenticate；reload 確實要求 production login，保留 synthetic owner 帳密可重新登入。[Interactions](../../release-evidence/a11/browser-native-interactions-20261003.json)包含下載檔 upload／inspect／cancel、wrong password、password cleared、disabled confirm 與 error logs 空陣列；[responsive record](../../release-evidence/a11/browser-native-responsive-20261003.json)覆蓋 375／768／1024／1440 × zh-TW／en，八組 main language 正確且無橫向 overflow，手機與 final screenshots 已保存。仍未 actual 200% zoom、assistive technology／完整 browser matrix、installed retained-bundle／gateway browser 與 frozen restore walkthrough；這些局部結果不關閉 AC-076。

仍缺 ISCC／實際 installer、clean-account install／upgrade／uninstall／資料保留與 frozen restore walkthrough、root LICENSE／native notices 最終審核、真實模型品質及 reviewed catalog、A9 最終美術／授權與外部 Funnel／Pages／GitHub 驗收。無模型下載、公開入口或發布成功的推論；AC-069／076 仍未全面驗收。

## 1. 全部待辦總表

| #                   | 階段                           | 範圍                                                                                                                                                                                                                                                                                                             | FR／AC                                                                | 相依                                                 | 需擁有者決定                                                                                           |
| ------------------- | ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| A1（本機完成）      | Funnel 訪客閘道 F0／F2         | 預設拒絕的訪客專用閘道、Pages origin CORS、代理後限流身分、真實 SSE、私人管理 Host／Origin、公開狀態三分（本機可用／入口已設定／外網已驗證）、啟用／停用引導；提交為本次 `feat(gateway): add isolated visitor listener and private controls`                                                                     | FR-047、AC-071（AC-068 一部分）；沿用 AC-022／036／049 的入口安全要求 | 無                                                   | 無；F0 契約已由 OR-027／ADR-053 核准                                                                   |
| A2                  | 回答政策 v2                    | envelope v2 分段、`{{owner}}` 後端渲染、`inflation_terms.yml`、數字事實檢查、逐段丟棄、無匹配回覆、第三人稱、「來源」列、prompt 修改                                                                                                                                                                             | FR-043／044、AC-062～065                                              | 無（`participation` 段在 A3 前只接受「無此類證據」） | 無                                                                                                     |
| A3                  | 參與事實                       | `github_login` 必填並預填、`aliases`、owner flag、首次／最後 commit 月份與 permalink、`has_visible_commits`、`other_contributors_visible`；無次數；API 失敗記為 unavailable                                                                                                                                      | FR-045、AC-066                                                        | A2（驗證器需認得 `PARTICIPATION`）                   | 無                                                                                                     |
| A4                  | 覆蓋檢查與 FAQ 審核            | 資訊性覆蓋檢查（不阻擋發布）、FAQ 核准／拒絕／重產／改寫成自述、只匯出核准項、綁定 bundle ID 並在變更時標「需要重新確認」                                                                                                                                                                                        | FR-046、AC-067                                                        | A2、A3                                               | 無                                                                                                     |
| A5                  | 訪客頁、配色與外觀             | 聊天介面版面、`color_schemes.yml` 五套配色與對比報告、`color_mode`、訪客明暗切換、NPC 舞台分離、歡迎區選用圖片的草稿／預覽／套用、管理端「外觀」步驟與吉祥物、GitHub Pages 靜態殼匯出、離線「休息中」與瀏覽器內 FAQ 比對、卡片連到 Pages 網址                                                                    | FR-047／050～052、AC-068、AC-072～075                                 | A1（閘道 origin）、A4（核准 FAQ）                    | 無（六點已確認；色碼於實作時以對比報告定稿）                                                           |
| A6                  | 內建 embedding                 | `builtin_onnx` bge-m3、首次使用三選一對話框、進度／取消／續傳、固定 checksum、重建索引警告、zh-TW／en 檢索品質量測                                                                                                                                                                                               | FR-049、AC-070                                                        | 無                                                   | 已決定（ADR-052）：官方 `BAAI/bge-m3` 固定 revision 的 fp32 ONNX，約 2.29 GB，逐檔 SHA-256 見契約 §6.2 |
| A7                  | 模型引導（僅管理端）           | `model_catalog.yml`、裝置檢查與 適合／勉強可用／不建議、canirun.ai 連結（不抄資料、不呼叫 API）、Ollama 明確 pull、白話錯誤對照、一行狀態、雲端資料揭露                                                                                                                                                          | FR-040 修訂、AC-057 修訂                                              | 無                                                   | 目錄首批收錄哪些模型（只能收已實測 envelope 的模型）                                                   |
| A8                  | Windows 安裝器                 | PyInstaller onedir＋Inno Setup 個人安裝、捷徑、托盤或小視窗、未簽章與 SmartScreen 說明、SHA-256、解除安裝保留資料、以新安裝檔更新                                                                                                                                                                                | FR-048、AC-069                                                        | A6（onnxruntime 打包）、A1（閘道隨安裝版運作）       | 無                                                                                                     |
| A9                  | 角色美術與內建角色（R13 剩餘） | Man／Orange 概念圖轉換與逐格審查、`core/humanoid` v1 pack 矩陣、授權與來源紀錄、接上 composer／manifest、真實 `public/character.png` 與 SVG／GIF／PNG 卡片                                                                                                                                                       | AC-020／021；供 A5 的預設角色                                         | 無                                                   | 美術最終審核由擁有者看圖決定                                                                           |
| A10                 | 舊修復項收尾                   | R11 近期終止批次的 reload recovery、R12-B 可重用 derived index（先量測 passage cache 是否已涵蓋）；R08 受保護預覽併入 A5                                                                                                                                                                                         | AC-077、AC-078（R08 為 AC-079）                                       | 無                                                   | 已決定（ADR-052）                                                                                      |
| A11（本機部分驗收） | 日常維運介面                   | 「維護」頁：狀態、加密 SQLite-only 備份與 protected native GET 下載、同主機同資料目錄還原（確認＋自動先備份）、回復上一版 bundle、立即停止訪客閘道、更新與關閉 Funnel 的說明；已保存局部本機還原／八組 responsive 證據；installed retained-bundle／gateway／完整 browser matrix 待補                             | FR-053、AC-076                                                        | A8                                                   | 已決定（ADR-054／OR-028，Approved 0.4.7）：選項 A；更新只提供說明，不在程式內下載安裝檔                |
| A12                 | 發布驗收與帳本                 | 帳本擴充到 AC-079 並更新 `source_identity`；乾淨 Windows 主機安裝；獨立外網實測；真實 GitHub Profile 點入（AC-022）；Chrome／Firefox／Safari、雙語、375／768／1024／1440、200% zoom、鍵盤、螢幕閱讀器、減少動態；補驗 UI GIF 下載落盤與瀏覽器開啟本人陳述來源；D8 新手／訪客實測（擁有者執行）；授權聲明與發布檔 | AC-001～AC-079                                                        | A1～A11                                              | GitHub README 寫入、公開入口啟用、push 各需當次授權                                                    |
| —                   | 選用                           | P1-04 重構（`P1-04_REFACTOR_HANDOFF.md`）；更大的貢獻輸出預算                                                                                                                                                                                                                                                    | —                                                                     | —                                                    | 需擁有者決定是否要做                                                                                   |

## 2. 建議順序與並行

剩餘主線：**補齊 A11 installed retained-bundle／gateway 與完整 browser matrix → A8 clean installer／frozen restore walkthrough → A12 完整發布驗收**，並補齊 A5／A6／A7／A9 未關閉的品質、美術、外部與無障礙證據。A1～A11 的本機實作或 fixture 證據不移除任何發布必需工作；A8 已有包含 A6 runtime 的 onedir build，但 installer 與乾淨帳號驗收仍待執行。

可與主線並行（各用獨立 worktree，互不改同一檔案群）：

- **A6** 與 **A7**：只動 provider／admin 模型設定區域，可在 A1 開始時同步進行；A8 需等 A6 合併。
- **A9**：美術與素材管線獨立；A5 的驗收以程式產生的角色 fixture 進行，不被 A9 阻擋，但發布前必須有預設角色。
- **A10**：R11 與 R12-B 可隨時開始（只動分析批次與快取區域）；R08 隨 A5 一起做。
- **A11**：已與 A8 host 整合並取得雙語 native download 部分證據；Root 已保存局部本機還原與八組雙語 responsive 證據，最終仍須補完整無障礙矩陣並用 A8 安裝版本補齊 walkthrough。

每一階段合併前都須跑完整 Python 與 Web 測試、Ruff／mypy／Prettier／TypeScript、production build 與 `git diff --check`，並在本文件對應列標註完成提交與證據位置。

## 3. A1 的已核准 F0 契約

[A1/F0 契約](../../docs/A1_FUNNEL_GATEWAY_CONTRACT.md)（OR-027／ADR-053、規格 0.4.6）已定稿：同一程序內的第二個 loopback listener、明確封閉路由與 Vite 靜態 import 資源清單、唯一 Pages origin 的無憑證 CORS、私人管理 Host／Origin、預設共用額度與實際工作上限、選用且嚴格的 loopback proxy 身分、每次啟動重新確認的擁有者外網回報，以及選用 Linux host-network Compose。設定保存不代表 Pages 託管、GitHub 卡片或外網驗收通過。

Windows 安裝版由 A8 處理。Funnel 的安裝、登入、授權與啟用／停用仍由擁有者操作；RepoNPC 只顯示官方指令，憑證不進入表單、日誌或匯出。

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

本機狀態（2026-09-29）：[契約 §10](../../docs/A1_FUNNEL_GATEWAY_CONTRACT.md#10-local-implementation-checkpoint-2026-09-29)記錄完整實作與 Main 審核。設定／啟動／停止／擁有者回報可由私人管理頁操作；重啟、版本與就緒失效會撤銷目前回報。外網、真實 provider、乾淨主機與正式帳本由 A12 驗收；完整 Pages 匯出／離線比對由 A5 實作。

> 實作 RepoNPC 的 Tailscale Funnel 訪客專用閘道（ADR-047 F0／F2，ADR-048 §4.1–4.2，FR-047，AC-071）。先把 `docs/IMPLEMENTATION_BACKLOG_2026-09-26.md` §3 的待定項寫成契約並更新 `TAILSCALE_FUNNEL_DEPLOYMENT_PLAN_2026-09-24.md`、`SECURITY.md`、`OPERATIONS.md`，再實作：預設拒絕的路由白名單、Pages origin 限定且不帶憑證的 CORS、管理與模型路徑 404、代理後限流與每日上限、真實 SSE 逾時、訪客回應無主機／模型／費用欄位，以及管理端「本機可用／入口已設定／外網已驗證」三種狀態。不要實際啟用 Funnel。測試需涵蓋路徑編碼與大小寫變體、未知路由、非白名單 origin、帶憑證請求。

### A2 回答政策 v2

> 依完成方向契約 §1 實作 FR-043／044（AC-062～065）。取代 `src/reponpc/chat/answers.py` 的 `_PERSON_CLAIM_RE`、整段拒答與逐詞比對：envelope v2 分段 `person | participation | project | inference`、後端渲染 `{{owner}}`、`inflation_terms.yml` 詞表、數字事實檢查、逐段靜默丟棄、envelope 層級錯誤回無匹配回覆、沒有本人陳述時以專案與參與證據回答且不顯示缺口訊息、第三人稱、可收合的「來源」列；同步修改 `service.py` 的 policy prompt 與 SSE payload。測試需含中英文改寫、膨脹詞與編造數字、「其他」「開發工具」等 CJK 誤判反例。

### A3 參與事實

> 依契約 §2 實作 FR-045（AC-066）：新增 `PARTICIPATION` 證據類型與索引步驟、`github_login`（必填、預填）與選填 `aliases` 設定、owner flag、首次與最後 commit 月份及 permalink、`has_visible_commits`、`other_contributors_visible`；不記錄任何次數；API 失敗記為 unavailable 而非零；匿名 REST 需處理限流。讓 A2 的 `participation` 段能以此驗證。

本機狀態（2026-09-27）：實作與 fixture 驗證完成；包含索引、引導欄位、不可變引用、失敗／限流處理及中英文分段答案。正式發布與真實 GitHub 驗收仍由 A12 的驗收帳本追蹤。

### A4 覆蓋檢查與 FAQ

本機狀態（2026-09-28）：[A4 實作契約與驗證範圍](../../docs/A4_COVERAGE_FAQ_IMPLEMENTATION.md)記錄標準問題 registry、實際驗證回答的資訊性檢查、四種審核動作、保存 claim 後更新真實索引再生成、精確 bundle 綁定、runtime migration 29，以及核准項 JSON 匯出／訪客即時問題按鈕。完整 Pages 靜態殼與離線比對由 A5 處理；公開部署由 A12 追蹤。

> 依契約 §3、§4.3 實作 FR-046（AC-067）：發布前的資訊性覆蓋檢查（絕不阻擋發布）；FAQ 產生與審核，動作只有核准／拒絕／重產／改寫成自述（不提供自由編輯）；只有核准項會被匯出或提供；綁定 bundle ID，bundle 變更時顯示「需要重新確認」。FAQ 回答必須通過 A2 驗證器。

### A5 訪客頁與外觀

2026-09-29 狀態：依擁有者要求，ChatGPT 已先查閱 GitHub 上與本機相同的
`main@877c6d6`，再取得 A5 前後文並給出[分批計劃](A5_CHATGPT_PLAN_2026-09-29.md)。
單一 gpt-6-luna max 實作者依[整合契約](../../docs/A5_VISITOR_APPEARANCE_EXPORT_CONTRACT.md)
順序實作，Main 獨立審查與驗證。第一批已通過 Main 審查與 81 項相關測試，
第二批私人預覽、背景草稿與無模型外觀套用已通過 Main 審查；
另已驗證故障回復、兩次完整建置、工作階段隔離及過期檔案清理。
第三批共用訪客頁、外觀預覽與明暗首屏已通過 Main 的聚焦檢查；
375px 雙語輸入列、抽屜鍵盤操作、768px 聊天寬度、延遲提案丟棄和
儲存後再次套用均已在原生瀏覽器確認。第四批 FAQ 替代問法／離線比對與
靜態匯出已通過聚焦審查，第五批 Pages 驗證與精確下載收據已交付並通過 Main 檢查。
Python 1,614 passed／2 Windows skips、Web 293 passed、Docker 2 項及正式建置通過；
實際 root／project 匯出已逐檔核對並檢查 FAQ／來源控制器。ChatGPT 最終審查中，
原生 ZIP 落盤與真正 200% zoom 未確認，A5／R08 尚未結案；
Pages 即時問答因自動審核要求明確授權傳送內容與目的地而暫停，擁有者問題尚待答覆；
實際檢查結果記於 `release-evidence/a5/local-checks.md`。公開部署與正式驗收仍屬 A12。

> 依契約 §4.0–4.6 與 ADR-051 實作 FR-047／050／051／052（AC-068、AC-072～075）：側欄＋頂列＋置中聊天欄版面；`color_schemes.yml` 五套配色（neutral、ocean、forest、sunset、lavender）的明暗色碼，對比不合格即載入失敗並產出對比報告；`color_mode` 與訪客明暗切換（只存 localStorage、無 inline script、CSP 不變）；只有 NPC 跟隨角色並以 stage／plate 保持 3:1；歡迎區選用圖片的私人草稿、真實預覽、焦點／變暗／縮放、套用／取消／移除；管理端「場景」改名「外觀」並提供配色圖庫、模式、訪客切換、進階強調色、重設；GitHub Pages 靜態殼匯出（記錄閘道 origin、manifest hash）、閘道不可達時顯示「休息中」並在瀏覽器內比對已核准 FAQ；卡片連到 Pages 網址。R08（AC-079）：角色候選、卡片預覽與歡迎區圖片草稿只由需登入的同源管理路由提供並帶 `Cache-Control: no-store`，公開路由與匯出一律取不到，CSP 不變。

### A6 內建 embedding

2026-10-03 本機狀態：provider／manifest／明確同意下載操作及模型設定整合已有 deterministic 本機證據，onedir 包含所需 runtime 而不含權重；實際固定 artifact 下載與 zh-TW／en 真實模型品質仍待驗收，不以 fixture 宣稱 AC-070 完成。

> 依契約 §6 實作 FR-049（AC-070）：`builtin_onnx` adapter（ONNX Runtime CPU、無 PyTorch）服務 bge-m3（1024 維、無前綴）；首次需要索引時的三選一對話框（下載內建模型／改用其他服務／稍後再說，稍後會阻擋建置並說明原因）；來源固定為契約 §6.2 的官方 `BAAI/bge-m3` revision 與 `onnx/` 檔案清單（fp32，約 2.29 GB），對話框顯示的大小由該清單計算，下載需進度、取消、續傳與逐檔 SHA-256 驗證，未點擊不得下載；更換 embedding 前顯示需重建索引；在 zh-TW／en fixture 上量測檢索品質並記錄。不做本機量化。

### A7 模型引導

2026-10-03 本機狀態：純目錄 loader、資源估算、唯讀 device check、管理 UI 與安全錯誤接線已有本機證據。出貨 `model_catalog.yml` 保持空目錄，因尚無可收錄的真實 dated envelope 測試證據；unknown 硬體不當作零或保證適合，無 bandwidth／compute 證據不捏造速度。首批模型實測與 novice／accessibility 完整驗收待補。

> 依契約 §7 實作 FR-040／AC-057 修訂（僅管理端）：`model_catalog.yml`（參數量、量化、記憶體估計、是否支援結構化 JSON、最後審核日期，只收錄已實測 envelope 的模型）；後端偵測 RAM／GPU／VRAM／磁碟並顯示 適合／勉強可用／不建議；canirun.ai 連結（不抄資料、不呼叫 API）；Ollama 偵測與明確點擊才 pull；白話錯誤對照；一行狀態摘要；選雲端時的資料揭露。訪客端不得出現任何相關資訊。

### A8 Windows 安裝器

2026-10-03 本機狀態：[Windows 指南](../../packaging/windows/README.md)連結最新 A11 onedir build、outside-checkout frozen health／shutdown receipt、checksums 與 license gates。無 ISCC，實際 installer、clean-account launch、upgrade／uninstall 保留資料與 frozen restore walkthrough 未驗收，AC-069 不標 pass。

> 依契約 §5 實作 FR-048（AC-069）：PyInstaller onedir（含 onnxruntime、uvicorn 與預建前端）、Inno Setup 個人安裝（免系統管理員權限、開始功能表與桌面捷徑、解除安裝時預設保留資料）、啟動器等待 health 後開啟管理頁並提供「開啟管理頁面」「結束」、使用者資料放在安裝目錄外、SHA-256 與 SmartScreen 說明頁。bge-m3 不打包。在乾淨 Windows 主機（無 Python、無 Docker）驗證安裝、啟動、更新與解除安裝。

### A9 角色美術

2026-10-03 owner 決定：**預設 NPC 採用 Man**，見 [決定紀錄](A9_MAN_DEFAULT_DECISION_2026-10-03.md)。以 Man 完成正式素材、七種動畫、pack／bundle／卡片接線與來源授權紀錄；Orange 草稿保留。以下既有素材準備要求持續適用，預設角色方向已確定。

> 依 `current-state-2026-09-20` 記憶的「Remaining asset work」完成 R13 剩餘工作：以現有 converter 處理 `PixelNPC` 的 Man 與 Orange 概念圖，逐格檢查 64×64 的邊界、基線與減少動態姿勢；產出 canonical 256×448 PNG、預覽與對照表；補來源與授權紀錄；完成 `core/humanoid` v1 pack 矩陣並接上 composer／manifest，驗證 `public/character.png` 與卡片輸出。不要搬動或刪除 `PixelNPC/`；最終美術需擁有者看圖核可。

### A10 舊修復項

> 依 ADR-052 實作。R11（AC-077）：`GET /api/admin/onboarding/analysis-batches/active` 在沒有進行中批次時，回傳 7 天內結束、仍可重試或重新分析、且擁有者未關閉的最新終止批次並標示為恢復；關閉狀態存在伺服器端，不以 localStorage 為準。R12-B（AC-078）：先量測 ADR-046 passage-vector cache 是否已讓失敗或重啟後的重試免去主要工作，若是就以「已涵蓋」結案並記錄量測；若否，依 `REPAIR_PROGRESS_2026-09-17.md` 的 Option A 做受保護檔案快取，容量與 TTL 沿用 passage cache 機制，任何錯誤都視為未命中並重建。R08 不在此階段（隨 A5）。

### A11 日常維運介面

2026-10-03 本機狀態：owner 核准選項 A／ADR-054／OR-028，Approved 0.4.7 凍結加密 Web 備份與同主機同資料目錄還原界線。Protected native GET 讓瀏覽器實際下載 attachment；中英下載相同 authenticated ciphertext、upload／inspect／cancel 已有 disposable in-app browser 證據。SQLite validator、同 owner／host resource checks、session/grant 撤銷、gateway off、MaintenanceHost drain／replace／rollback 已有 automated fixture 證據；Root 已保存 real Main／MaintenanceHost keyboard 還原、重新登入與八組雙語 responsive 局部本機證據。完整 installed-deployment、active／previous bundle、pin、gateway stop、實際 200% zoom／assistive technology／full browser matrix 與 frozen-host walkthrough 仍須補齊，AC-076 尚未結案。

> 依 FR-053（AC-076）及 ADR-054 在管理端提供「維護」頁：顯示本機可用／入口已設定／外網已驗證、目前 bundle 與上次備份時間；以既有 online `runtime backup` 建立 password-encrypted SQLite-only artifact，透過受保護 native GET 下載；上傳後先驗證加密 metadata、schema／integrity／FK、same-owner 與 retained host resources，明確確認後自動先備份現況，在 owned host 停止舊 lifecycle 後替換並可 rollback。Host keys、models、bundles、appearance assets 與 local-portfolio 原檔另行保留，不下載 keys、不當作跨主機完整備份；成功還原撤銷舊 sessions／grants 且 gateway 維持 off。以既有 bundle pin 回復上一版；立即停止訪客閘道；提供安裝檔更新與官方 Funnel-off 說明，不在程式內下載安裝檔、不處理 Tailscale 憑證。

### A12 發布驗收

2026-10-03 狀態：[新候選帳本](../../release-evidence/a11/acceptance-ledger-candidate-20261003.json)已完整列舉 79 rows（76 not-run／3 blocked），[候選說明](../../release-evidence/a11/acceptance-candidate-notes-20261003.md)記錄局部證據與退役欄位。歷史 ledger byte-identical；局部 automated／browser／build 成功不提升為完整 AC pass。Root 應另記最後 source fingerprint 與更新後 evidence scope。

> 在新候選快照逐項以完整實際證據更新 AC-001～079 狀態與 `source_identity`，保留歷史 ledger；執行乾淨主機、獨立外網、真實 GitHub Profile、瀏覽器與無障礙矩陣；補驗 UI 卡片下載落盤與瀏覽器開啟本人陳述來源。需要公開入口、GitHub 寫入或 push 的步驟先取得擁有者當次授權；D8 使用者實測由擁有者執行並提供紀錄。

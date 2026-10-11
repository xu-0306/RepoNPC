# 並行實作交接 — 2026-10-03

**最新接續交接已另存：**請先讀[當前交接](CONTINUATION_HANDOFF_2026-10-03.md)。本輪正式builtin AC-009通過；16384與推理開啟政策完整Python2613項／2既有略過通過；actual600views對比、已安裝retained restore／relogin及isolated uninstall／資料保留均有新部分證據。修正two-facts題目後完整suite9/12、catalog空白。以下舊交接的baseline未切換／native walkthrough未執行等敘述保留當時快照；新結果不覆寫旧receipts，也不宣稱全部v1完成。

## 最新交接：三位 6.1 Sol 與 Root 模型卡片／實際模型／安裝器批次

擁有者要求「按照先前的分配把任務給幾個6.1 sol並行」。重用三位 Sol：`a6_inference` 擁有真實推論／模型測試，`a7_guidance` 擁有 A8 安裝器與已安裝 A11 驗證，`a9_assets` 擁有私有 Man／A5 fixtures；Root 擁有 A7 共用 UI／API、build／LICENSE／notices、瀏覽器驗收與本文件。Approved0.4.7／ADR-054／OR-028；main@877c6d6 與所有既有 dirty edits 保留。這次僅固定官方模型下載、本機 Ollama 合成資料及隔離 compiler／installer 操作；沒有 owner runtime、雲端、GitHub／Pages／Funnel、Git stage／commit／push 或發布。

### 本輪成果、需求及實際限制

- **A6／A7 模型證據（FR-049／040；AC-008／009／057／070 部分）**：真實固定官方 bge-m3 八檔、2,289,765,790 bytes／checksum 完整。production CPU ONNX 推論1024維、finite／normalized／順序／tokenizer overflow 通過；原20題雙語 corpus 的 semantic／hybrid Recall@8與配對一致性均1.0。實際隔離 Docker 為4CPU／8GiB、network none、唯讀 model/input、host-only oracle，暖機 p95 **118.999ms**、首次 process call16.766s、peakRSS1.737GB，兩次 build 可重現。正式 AC009 controller 仍綁定舊 E5／Torch provenance，**formal_ac009_accepted=false**；改 baseline 的最小提案已記錄，未改 oracle／題目／門檻。既有本機 Ollama qwen3.5:9b **5/12**、qwen3.8:27b **10/12**；後者兩題是嚴格多證據 oracle 與實際單證據回覆不一致，並未宣稱不安全或放寬。**正式 catalog 保持空白**。來源、環境、raw timing、失敗與重跑都在 [A6 report](../release-evidence/a6/real-model-20261003/README.md)；真實權重只留 disposable 路徑，不進 bundle／wheel／installer。
- **Root A7 UI／API（FR-040；AC-057 部分）**：既有 private device-check 回傳 authored metadata／日期／source／license／雙語 envelope-v2 摘要；四種 grade／reason／unknown、CPU記憶體與磁碟估算逐卡呈現，沒有速度猜測。選卡只展開既有 Chat 表單與焦點，保留 draft；另按「填入所選模型名稱」才修改名稱，新增／test／select 仍各自明確。沿用既有 registry/provider/form，零新 endpoint／DB／service／operation state。修正 ISO date 的 raw JSONResponse、無service時heading焦點、check完成 live status。變更含 `admin/operations.py`、`ModelGuidancePanel`、`LocalModelSetup`、`ModelSetupWorkspace`、`ChatProfilePanel`、`AdminPage`、CSS與相關 tests；[實作契約](A7_MODEL_CARDS_IMPLEMENTATION_2026-10-03.md)。合成卡片是 UI fixture，不是正式模型推薦。
- **A8／A11（FR-048／053；AC-069／076 部分）**：固定官方 Inno6.7.3 portable compiler 來源／checksum／Authenticode，Root改為 compiler 本身 `Ver` 檢查（PE metadata實為0.0.0.0），舊版fixture拒絕。完整 locked Windows build 產生真正 production installer；worker由最終輸入再編 exact recipe，SHA byte-identical。只安裝不同AppId／shortcuts／明確 disposable data-dir 的標示 derivative；install、installed health／A11、合成0.1.0→0.1.1 overlay、uninstall均exit0，七個資料檔byte-identical、registry／shortcuts清除。已安裝 binary A11 覆蓋密文GET、wrong-password／tamper／false-confirm400、CSRF403、cancel204、confirm202、CURRENT→BASELINE、sessions／grants0、gatewayoff、SQLite／FK與兩份加密先備份；quit0。這是開發機 API fixture（explicit synthetic localhost Secure-cookie replay），**不是 clean Windows、native browser、真實發布版本升級或 retained bundle acceptance**。見 [A8 report](../release-evidence/a8/parallel-20261003/README.md)、[final installer receipt](../release-evidence/a8/parallel-20261003/final-candidate/installer-result.json)、[installed A11 receipt](../release-evidence/a8/parallel-20261003/final-candidate-installed-maintenance/frozen-maintenance-result.json)。
- **A9／A5（FR-015／016／018及NFR-009；AC-020／021／022／068／072–075／079 部分準備）**：Man是已選定family；八個variants中僅完整衣裝人物適合預設草稿。交付28格contact sheet／七GIF／224frame report／deterministic private cards／既有alignment proposal；來源19files unchanged。仍有系統性位移、13/28碰邊、疑似腳部裁切與talk黑邊，alignment不能补畫缺失部位。**未正式替換production預設或推定授權**；已向owner詢問作者／來源連結／授權或自作聲明，尚待回覆。[Man審查](../release-evidence/a9/man-default-20261003/REVIEW.md)、[來源紀錄](../release-evidence/a9/man-default-20261003/PROVENANCE.md)。A5交付150配色×角色×背景cases、20PNG、300雙語public-consumerprofiles通過；[validated fixtures／walkthrough](../release-evidence/a5/accessibility-20261003/WALKTHROUGH.md)。這不是實際screen-reader／200%zoom／完整人工對比驗收。
- **軟體LICENSE／notices**：既有OWNER_REVIEW的MIT決定落為root `LICENSE`，補tqdm4.70.0對應MIT／MPL來源可取得notice，版本變更fail closed並保留舊輸出，重新generatednotices／wheel／frozen；[license review](WINDOWS_LICENSE_REVIEW_2026-10-03.md)。這不提供Man／模型授權，也不代表public/native release審核完成。

### 本輪整合驗證及artifact identity

| 檢查                   | 本輪結果／證據                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python受影響subset     | **226 passed／1既有Starlettewarning，12.87s**；[log](../release-evidence/a7/parallel-20261003/python-wave-final.log)，涵蓋guidance／hardware／admin DTO、notices／resources及兩種Windowscontracts。Earlier203／45 subsets有重疊，不相加；本輪沒有重跑完整2497suite。                                                                                                                                                                                 |
| Web                    | **484 tests／42 files**；[tests](../release-evidence/a7/parallel-20261003/web-tests-final.log)、[format](../release-evidence/a7/parallel-20261003/web-format-final.log)、[types](../release-evidence/a7/parallel-20261003/web-types-final.log)、[lint](../release-evidence/a7/parallel-20261003/web-lint-final.log)通過；19既有FastRefreshwarnings。完整Windowsbuild含最新productionWeb／15sourceguard，既有classic-scriptwarning保留。              |
| Python靜態             | [Ruffformat258files](../release-evidence/a7/parallel-20261003/python-format-final.log)、[lint](../release-evidence/a7/parallel-20261003/python-lint-final.log)、[mypy103sources](../release-evidence/a7/parallel-20261003/python-types-final.log)通過。                                                                                                                                                                                              |
| Wheel／Windows         | [wheel](../release-evidence/a7/parallel-20261003/wheel-build.log)、[full installer build](../release-evidence/a7/parallel-20261003/windows-build-release-candidate.log)成功；compiler初次PE誤判與compile-aborted失敗logs保留。                                                                                                                                                                                                                       |
| 首次 artifact snapshot | [焦點修復前verification](../release-evidence/a7/parallel-20261003/source-artifact-before-repeat-focus.json)：112wheel files、102frozen current-source modules／6namespace packages、8resources、15compiledWebfiles、300SHA256SUMS均一致，LICENSE／notices亦一致；沒有Torch／Transformers。EXE **17af37f0e35e84861608e6a476df6c9b94cb16b4f9cb687e7bd282b27480273f**；installer **a90a897afc09588425484c8d5ed71f8b8dfdc81bc601bf55206014194ad36210**。 |
| Worker獨立checks       | A6 guidance83、A9 assets79／scene176（401existingwarnings）／Web105均pass，工具format／lint／types及artifact receipts通過；詳各leaf reports，不與Root重疊tests相加。                                                                                                                                                                                                                                                                                 |

### 瀏覽器與接續工作

Root的in-app browser以production admin operations／authentication操作合成catalog：中文／英文三種容量grade、unknown GPU、keyboard選卡、draft保留、explicit fill、service仍未選、model profiles未新增。Desktop1280無橫向overflow；[primary checks](../release-evidence/a7/parallel-20261003/browser-primary-checks.json)、[無自動資料修改](../release-evidence/a7/parallel-20261003/browser-no-auto-mutation.json)、[first card screenshot](../release-evidence/a7/parallel-20261003/browser-en-cards.png)。額外native-confirm刪除fixture服務時，browser CDP焦點操作timeout，dialog API未回傳dialog；已保留限制並停止該fixture，未把刪除／該次cleanup冒充通過。

沒有service的獨立IP-originfixture成功接續：中英文375px無橫向overflow、選卡focus既有 `chat-profile-heading`、Tab到Refresh。實際重複同一卡片／切换locale測出React same-object bailout；Root只改兩處callback保存既有row的新copy，沒有新增operation ID／state。修正後四次keyboard DOM assertions（初次zh、repeatzh、localechange同卡、repeaten）均pass，console errors為空，temporary viewport已reset1280×720。[最新回歸收據](../release-evidence/a7/parallel-20261003/browser-repeat-focus.json)、[手機中文卡片](../release-evidence/a7/parallel-20261003/browser-zh-phone.png)；`tests/browser/README.md`保存可重跑步驟。最後重跑[Web484](../release-evidence/a7/parallel-20261003/web-tests-current.log)、[types](../release-evidence/a7/parallel-20261003/web-types-current.log)、[lint](../release-evidence/a7/parallel-20261003/web-lint-current.log)、[production build](../release-evidence/a7/parallel-20261003/web-build-current.log)均通過。

**最終重建身份：** [Windows build](../release-evidence/a7/parallel-20261003/windows-build-repeat-focus.log)成功；[current verification](../release-evidence/a7/parallel-20261003/source-artifact-verification.json)仍為112wheel／102modules／8resources／15Web／300checksums。EXE **d0170458eeefde6723acd5eb888fc49d042ffb4201096f05532de9f527715283**、installer **ff87ae23b55d3ada11ad96c2f230a987200d9a6822f7ac383412179b4e4e0b5f**。前表17af37／a90a89與final-candidate屬於同輪焦點修復前的有效snapshot；[old artifact receipt](../release-evidence/a7/parallel-20261003/source-artifact-before-repeat-focus.json)保留。Worker最終snapshot重跑使用freshlabel：[final-repeat-focus installer](../release-evidence/a8/parallel-20261003/final-repeat-focus/installer-result.json)與[installed A11](../release-evidence/a8/parallel-20261003/final-repeat-focus-installed-maintenance/frozen-maintenance-result.json)均通過；compile／install／smoke／A11／overlay／uninstall全exit0、七檔保留且fixture registry／shortcuts清除，沒有重寫舊receipt。

**收尾限制：** 18763–18766沒有殘留listener，成功的secondary／IP-origin驗收tabs已關閉，viewport已reset。Primary localhost fixture tab因native-confirm／CDP timeout未能經支援API關閉，保留失敗記錄。自動核准審查拒絕含三個暫存資料夾遞迴清理的指令，只回傳「blocked by policy」；因此保留 `.pytest-tmp/a7-cards-browser-cyi1cla2`、`a7-empty-browser-tz3e462w`、`a7-empty-ip-browser-z_vevn3h`，僅含合成資料。授權bge權重另保留供重現。沒有透過其他shell／OS／CDP繞過限制。

剩餘工作：formal AC009 controller需按核准的builtin identity同步並重跑（不改題目／oracle／門檻，本次leaf未分派controller檔案）；catalog需真正通過strict雙語cases與provenance；Man需原素材修圖／來源授權後production接線；A5完整實際assistive／zoom；clean Windows／native installed A11／retained bundle及外部Funnel／Pages／GitHub驗收。歷史ledger和79-row候選不改、不提升AC。所有舊sections／receipts保留原checkpoint身份，不重算為當前artifact。

## 前次交接：A6／A7／A8／A11 本機整合與原生瀏覽器驗證

**後續 owner 決定（2026-10-03）：預設 NPC 採用 Man。** [決定紀錄](A9_MAN_DEFAULT_DECISION_2026-10-03.md) 更新 A9 next-work pointer：以 Man 完成正式素材／動畫／pack／bundle／卡片，補齊來源與散布授權；Orange 草稿保留。本節既有測試／指紋／receipt 屬於角色選擇更新前的本機交付快照。

本節取代下方第一輪的「下一輪」指標；第一輪成果與當時驗證保留為歷史。擁有者要求繼續、允許 in-app browser 驗收，並明確批准 A11 選項 A。Approved Specification **0.4.7／ADR-054／OR-028**、[備份界線決定](A11_BACKUP_BOUNDARY_DECISION_2026-10-03.md)、SECURITY §23 與 OPERATIONS §11–12 已同步。仍使用 main@877c6d6 的既有 dirty working tree；沒有 stage／commit／push、真實模型權重、provider／GitHub／Pages／Funnel 操作或 owner runtime 修改。

### 本機已交付

- **A6（FR-049／006／012；AC-008／009／070 部分）**：`builtin_download.py` 的明確同意、固定八檔來源、有限串流、取消／續傳、大小／checksum 檢查與原子發布；`admin/operations.py`、embedding profile／analysis selection、`main.py` 與 runtime migration 34 接上選擇／持久化、active／analysis embedding 共用實例、有限工作排程與安全關閉。`LocalModelSetup.tsx`／`BuiltinModelPanel.tsx` 顯示下載、設定其他服務、稍後決定三選一及完整重建提醒。真實權重與雙語品質／RAM／延遲未執行，不能以合成 session 宣告 AC-070 完成。
- **A7（FR-040；AC-057 部分）**：`device_check.py` 有限唯讀裝置觀測，沿用模型中心／Ollama helper；`LocalModelSetup.tsx`／`ModelGuidancePanel.tsx` 顯示適合程度、unknown、管理端模型狀態與雲端資料揭露。正式 catalog 維持空白直到有 dated envelope-v2 實測證據，未捏造可用模型。先前原生首次使用／取消／續傳／完成畫面保存在 `release-evidence/a6/`。
- **A8（FR-048；AC-069 部分）**：`windows_launcher.py`、`main.py` 的 frozen resource 定位、`packaging/windows/` 與 `scripts/build_windows.ps1` 交付 onedir、native ONNX/tokenizers、預建 Web／registry、per-user Inno Setup recipe、獨立資料目錄、健康後的一次性管理 grant 與正常退出。不含模型權重或 owner data。最新完整 `-SkipInstaller` build 和專案目錄外 frozen health／shutdown 檢查通過；沒有產生 installer 或執行安裝／升級／解除安裝。
- **A11（FR-053；AC-076 部分）**：`backup_encryption.py`、`backup_validation.py`、`backup_resources.py`、`maintenance.py`、`maintenance_host.py`、private admin routes 與 `MaintenancePanel.tsx`／`MaintenanceSetup.tsx` 完成密碼加密下載、host-only SQLite 預檢／同一資料目錄確認還原、資源與身份檢查、停止及重建真實 Main application、還原前自動加密備份、rollback、撤銷 session／grant、gateway off、bundle pin／gateway stop 與雙語操作說明。Scrypt／AES-GCM 容器最多 128 MiB SQLite，還原預覽有效十分鐘且只屬於當前 session；上傳 SQLite 不可執行自帶 schema SQL。Main 等待實際背景 writer／request 完成，再停止舊 lifespan。

### 最新驗證與來源界線

| 檢查                 | 結果與證據                                                                                                                                                                                                                                                                                                                                                                                                                          |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 完整 Python 非 smoke | **2497 passed、2 既有 POSIX-only Windows skips、495 warnings，536.32s**：[log](../release-evidence/a6/python-a11-final-20261003.log)。此完整 run 在新增原生 GET 下載前完成，不將它稱為最新 GET 的完整 suite。                                                                                                                                                                                                                       |
| 最新受影響 Python    | **181 passed、1 既有 Starlette warning，52.69s**：[log](../release-evidence/a6/python-a11-native-root-final-20261003.log)，涵蓋 maintenance round trip／host／safety、Windows launcher／resources、admin auth、gateway private-path boundary。另有 native GET/API 97 項測試由 Sol 完成；不能把重疊項目相加為完整套件數。                                                                                                            |
| 最新 Web             | **480 tests／42 files**，format／lint／types／production build 通過：[log](../release-evidence/a6/web-a11-native-download-final-20261003.log)。19 個既有 Fast Refresh warnings 與既有 classic-script bundling warning 保留。                                                                                                                                                                                                        |
| 最新靜態與 guard     | Ruff lint／260 files format、mypy103 sources 通過：[Ruff](../release-evidence/a6/ruff-a11-native-final-20261003.log)、[mypy](../release-evidence/a6/mypy-a11-native-final-20261003.log)。[Visitor guard](../release-evidence/a6/web-guard-a11-native-final-20261003.log) 14 self-tests／15 runtime sources 通過。                                                                                                                   |
| Docker／Compose      | **2 passed，78.59s**：[log](../release-evidence/a6/docker-a11-final-20261003.log)，A11 整合後、新增 private GET 前的本機 smoke。未變更 deployment configuration；最新 gateway security regression 另在 181 項 run 中通過。沒有公開 Funnel 驗收。                                                                                                                                                                                    |
| 最新 wheel           | [build log](../release-evidence/a6/wheel-a11-native-final-20261003.log) 成功，artifact 為 `dist/a11-wheel/reponpc-0.1.0-py3-none-any.whl`。                                                                                                                                                                                                                                                                                         |
| 最新 Windows         | [完整 build log](../release-evidence/a6/windows-build-a11-native-download-final-20261003.log) 成功；[frozen receipt](../release-evidence/a6/windows-frozen-smoke-a11-native-final-20261003.json) 在 checkout 外、fresh disposable data-dir 執行，**exit0，2.3415s**，SHA-256 `12cb22f65be4a66fae8006f263452659be537a2a40e06c2c3f70407c29ced2ff`。只證明健康／正常停止，未宣稱 frozen restore／installer／clean-account acceptance。 |

### 實際 in-app browser

另外以 A6／A7 disposable fixture 重驗最新「使用外部模型服務」修復：中文與英文以 Enter 選擇後，實際打開 content-finder service 表單並聚焦 `model-connection-name-embedding` 的服務名稱輸入，沒有提交服務或 outbound 呼叫；error logs 為空。[雙語焦點收據](../release-evidence/a6/browser-external-choice-focus-final-20261003.json) 與中英 screenshots 保存在 A6 evidence。先前 synthetic download／cancel／resume／complete 結果保留其原始來源與 fixture 限制。

使用 `browser_maintenance_fixture.py` 建立一次性原資料目錄，透過真實 Main.prepare／MaintenanceHost 與 production authentication 完成以下操作；只使用明確合成帳密／備份密碼，不記錄 hashes、session tokens、host keys 或完整資料庫列。

- 中文建立密文後按下載連結，英文按同一連結，兩次 native download event 均完成並取得本機檔案。兩份 **430242 bytes**，SHA-256 相同；離線在 private host temporary file 解密，schema34／app0.1.0／SQLite integrity `ok`：[download receipt](../release-evidence/a11/browser-native-download-20261003.json)。檔案以 RepoNPCBackup magic 開頭，未向瀏覽器傳送 raw SQLite。
- 將剛下載檔重新上傳、英文預檢與取消；中文錯誤密碼顯示安全訊息並清空輸入／檔案；正確基準檔在中文與英文均顯示範圍／版本／有效期限，未勾選確認時不能還原。
- 以 **Space → Tab → Enter** 操作確認；受理畫面只說 accepted，未提前宣稱成功。讀取 disposable runtime 證明 `SYNTHETIC_CURRENT_AFTER_BACKUP` → `SYNTHETIC_BACKUP_BASELINE`、session0、gateway off、integrity `ok`、三份 host 密文均可驗證、preview0：[restore receipt](../release-evidence/a11/browser-native-restore-state-20261003.json)。重新整理要求登入，保留的 owner 帳密可重新登入；error logs 為空：[interaction receipt](../release-evidence/a11/browser-native-interactions-20261003.json)。
- 375／768／1024／1440 × zh-TW／en，main language 正確、無 document 水平溢出、password cleared、unchecked confirm disabled：[responsive receipt](../release-evidence/a11/browser-native-responsive-20261003.json)。[中文手機](../release-evidence/a11/browser-native-zh-phone.png)、[英文手機](../release-evidence/a11/browser-native-en-phone.png)、[最終中文畫面](../release-evidence/a11/browser-native-zh-final.png) 已保存並視覺檢查。

先前 Blob download 的事件逾時記錄是早期版本，不能稱為成功。本次將保存流程整合至同源、owner authentication＋Origin／Referer 保護的 native HTTP attachment：POST 先保存 host 密文並提供 `Content-Location`，UI 只保留有效相對路徑並顯示明確下載連結；GET 只讀既有密文、不產生新備份、不含密碼／金鑰，檔案 ID 不授權存取。原 POST binary response 仍相容。沒有新增 download token／資料表／瀏覽器儲存。

### 未完成與下一步

獨立 [source／artifact receipt](../release-evidence/a11/source-artifact-fingerprints-20261003.json) 確認 wheel111份來源／資源與 frozen102個 application modules 等於目前來源，八個資源／15個編譯 Web 檔吻合，native ONNX／tokenizers 齊備，未包含權重／owner data／Torch，298筆 checksum 全數符合。最後311筆原始碼／建置／產物／規範指紋重新核對一致；可變 context／plan／handoff／memory 與最終 browser evidence 改由 Root 的 [文件／驗收收據](../release-evidence/a11/final-document-evidence-receipt-20261003.json) 保存。此收據分工保留來源，不擴大 AC 宣告。

兩個本次建立的 browser tabs 已關閉、viewport override 已 reset，disposable browser servers 以明確 Ctrl+C 停止；shell exit1／KeyboardInterrupt 不是 graceful-shutdown acceptance。原 A11 TemporaryDirectory 及 ports18763／18764 清理另有 [收據](../release-evidence/a11/browser-fixture-cleanup-20261003.json)，frozen normal shutdown 的 exit0 則由前述專用 smoke 證明。

完整 AC-076 的 installed deployment＋active／retained bundle＋gateway browser matrix 仍缺；API normal／edge／failure／security 覆蓋不取代這些條件。A8 缺 `ISCC.exe`、root `LICENSE`、完整 project／native／dependency license review、乾淨 Windows 安裝／升級／解除安裝／資料保留／SmartScreen／frozen restore walkthrough；保留 `RELEASE-GATES.txt`。

下一步分為可獨立並行的證據包：Sol 1 真實固定權重的 zh-TW／en retrieval／RAM／latency（須模型下載授權）；Sol 2 clean Windows installer／upgrade／uninstall／frozen maintenance（須 compiler／LICENSE 前提）；Sol 3 A5 真正200%zoom／screen reader／keyboard／reduced-motion／browser matrix 與 A9 Man 逐格美術／來源權利紀錄；Main 串接 A12 來源與證據，外部 provider／GitHub／Pages／Funnel 須相應明確授權。A9 的預設角色已選 Man，正式素材仍待定稿與接線。

A12 已另建 [79-row candidate ledger](../release-evidence/a11/acceptance-ledger-candidate-20261003.json)：76 not-run、3 blocked（AC-020／037／069），0 pass。完整列舉不代表全面驗收。[Candidate notes](../release-evidence/a11/acceptance-candidate-notes-20261003.md) 與 [最新 fingerprint](../release-evidence/a11/source-artifact-fingerprints-20261003.json) 保存來源界線。歷史 `acceptance-ledger.json` SHA-256 仍為 `f07cb1e265d14c6f082637422f302864fcd0b81ce7e1a067e13af0dae5979e88`，未重標歷史結果。計劃與專案記憶已更新最新 next-work pointer；不要重啟第一輪或 Pages／B1–B5。

## 第一輪歷史交接

本輪依擁有者「保存到計劃後開始進行」執行 [並行計劃](PARALLEL_IMPLEMENTATION_PLAN_2026-10-03.md)。三位 GPT-6.1 Sol 交付獨立模組，Main 審查、修復共用邊界並整合。基準為 main@877c6d6 的既有 dirty working tree；保留 A1–A5 與其他使用者修改。沒有 stage、commit、push、公開啟用、真實 provider／GitHub 呼叫、模型權重下載或 owner runtime 修改。

## 成果與檔案

### A6 基礎與整合

- `src/reponpc/providers/builtin_embedding_manifest.yml`、`builtin_artifacts.py`：單一官方固定 revision，八檔大小與 SHA-256，合計 2,289,765,790 bytes；只做 bounded streaming 本機完整性驗證，拒絕缺檔、錯誤大小／hash、非 regular file 及 symlink／junction，不下載或修復。
- `src/reponpc/providers/builtin_onnx.py`：lazy verified loading、真正 tokenizer、CPU-only ONNX session、CLS／明確輸出名稱、1024 維 normalized float32、8192 token 上限、每批最多八列且 padded token budget 8192；鎖住載入與推論，錯誤不反映輸入或私有路徑。
- `src/reponpc/providers/__init__.py`、`src/reponpc/config/models.py`：export 既有 runtime provider 介面；builtin public descriptor 必須符合固定 identity，revision 放入既有 model_id，沒有新增 bundle schema 欄位或任意 model path／URL。
- `pyproject.toml`、`uv.lock`：鎖定 onnxruntime 1.30.0、tokenizers 0.23.2，將 artifact manifest／model catalog 打包；沒有加入 PyTorch production dependency。
- `src/reponpc/indexing/index_database.py`：provider 失敗原本會留下部分 SQLite；清理移到 `finally`，保留原例外與上一個有效索引。重建失敗的既有 index 與 archive bytes 不變。
- 測試：`tests/unit/test_builtin_artifacts.py`（15）、`test_builtin_onnx.py`（48）、`tests/contract/test_builtin_embedding_config.py`（9）、`tests/integration/test_builtin_embedding_bundle.py`（4）。實際 builder → archive verifier → read-only index／hybrid query 通過；整合 session 是明確 test double，沒有宣稱真實權重品質。

支援 FR-049／FR-006／FR-012；AC-008／009／070 僅內部基礎及整合部分。A6-2 的首次使用三選一、下載／取消／續傳、正式 profile／runtime 接線、有限排程與模型卸載、切換及重建流程仍未完成。真實權重、zh-TW／en retrieval quality、RAM／延遲量測尚未執行。

### A7 目錄與純估算

`src/reponpc/admin/model_guidance.py`、`model_catalog.yml`、`tests/unit/test_model_guidance.py`（83）提供嚴格、bounded 的自有 catalog 與硬體資源估算。估算由 parameter count × bits + 明確 overhead 計算，硬體 unknown 不當成零；適合程度的 20% headroom 是引導 heuristic，沒有 runtime 保證。沒有足夠效能證據時速度保持 unknown，不以頻寬杜撰 tokens/s。

內建目錄目前刻意為空；fixture／一般 probe 不能當 live envelope-v2 證據。支援 FR-040／AC-057 的內部基礎。裝置偵測、Ollama helper 整合、管理 UI、實測 catalog 條目與新手 walkthrough 仍待完成。

### A9 私有候選草稿與 ZIP 邊界

`tools/prepare_character_assets.py`、`tests/unit/test_character_asset_preparation.py`（22）沿用現有 converter／canonical validator。唯讀 19 個來源檔案，前後 hashes 一致；Man 五個、Orange 四個結構候選，原版與 cleanup alternatives 合計 13 張 canonical PNG／contact sheets、91 個 GIF、兩份真正透明且標示無效 NPC 的空白模板。輸出與覆寫、重疊、symlink、路徑及大小／數量限制有測試；沒有新增動畫引擎或自動挑選。

草稿與每格 warnings／hash／來源事實見 [A9 審查索引](../release-evidence/a9/review-index-2026-10-03.md)。Main 抽查 contact sheets，確認存在跨格殘影與部件圖候選；canonical 結構通過不足以證明美術可用。授權事實仍未確認，不將 provenance graphic 的文字當授權。

`src/reponpc/cards/conversion.py` 原本使用可能已被 Windows zipfile 正規化或 NUL 截短的 filename；改驗證 orig_filename。`tests/security/test_sprite_archive_raw_names.py` 的四個反例先失敗，修復後與既有 conversion 測試合計 25 通過；A9 工具不保留重複 ZIP guard。

支援 FR-015／016／018、AC-020／021／022 的準備及安全部分。完整逐格美術審查、owner 選擇／來源權利核可、humanoid 組合矩陣、正式 pack／bundle／卡片與真實 GitHub 渲染仍未完成。

### A12 auditor

`tools/release_audit.py`、`tests/unit/test_release_audit.py`（29）要求 AC-001–079 列舉與 ledger 完整性，保留 AC-041–043 legacy 歷史列，維持報告／ledger shape 與 status。Coverage pass 明確不代表 acceptance pass。

既有 `release-evidence/acceptance-ledger.json` 仍是 2026-09-10 的歷史 source identity，缺 AC-062–079；本輪保留它而沒有將歷史 pass 改稱目前候選驗收。實際 audit snapshot 見 `release-evidence/a6/release-audit-wave1-20261003.json`。新版完整候選 ledger、LICENSE、完整 third-party notices、所有外部發布閘門仍在 A12。

## 本輪驗證

以下是最終凍結程式的結果；本輪基礎交付及受影響整合已通過，完整 FR／AC 驗收仍依前述缺項保留。

- Python 全部非 smoke：**1901 passed、2 既有 POSIX-only Windows skips、495 既有 warnings，355.27s**。命令為 `uv run --locked --no-sync pytest --ignore=tests/smoke --basetemp .pytest-tmp/parallel-wave1-final-20261003 -p no:cacheprovider --tb=short`；完整 log 在 `release-evidence/a6/python-final-20261003.log`。
- 聚焦上述 leaf／contract／security／producer-consumer tests 通過，詳見各檔案及 worker 報告。
- Ruff lint 通過；format 231 檔通過；mypy 94 source files 通過。新增兩個共用修復的 CRLF 格式已由 Ruff 修正。
- Web format／lint／types、388 tests／38 files、registry／production build 與 guard 14 self-tests／15 sources 通過；19 個既有 Fast Refresh warnings，classic scene-mode.js bundling warning 不使 build 失敗。Logs：`release-evidence/a9/web-check-20261003.log`、`web-guard-20261003.log`。
- 最終 Wheel build、YAML resources／依賴 metadata／共用修復 source bytes 檢查通過；Windows 與隔離 Linux container 的 native ONNX Runtime import／CPU provider、tokenizers 及 packaged resources 均通過。Linux import 有 telemetry device ID 無法持久化的 warning；該檢查使用 `--network none`，沒有執行真實 bge-m3 graph。21 個本輪程式／測試／依賴檔及最終 wheel hashes 記錄於 `release-evidence/a6/source-fingerprints-final-20261003.json`。
- `git diff --check` 在既有 CRLF 設定及 cr-at-eol 規則下通過；沒有為檢查改寫整個 working tree 的換行。
- 首次完整 Python run 過早收集仍在修改的 integration fixture，其當時 sorted YAML 使 owner assertion source range 找不到；1 failed／2 errors、1897 passed／2 skips。最終 fixture 保留原始 key 順序，四項獨立整合與完整凍結版本均通過，不隱藏初次失敗。
- Docker／Compose 最終 **2 passed，26.71s**：`uv run --locked --no-sync pytest tests/smoke --basetemp .pytest-tmp/parallel-wave1-docker-final-20261003 -p no:cacheprovider --tb=short`，log 在 `release-evidence/a6/docker-final-20261003.log`。包含一般 container／restart／volume 與本機 gateway ingress／private-path denial／stop；不是公開 Funnel 驗收。初次 gateway image build 及一次重試失敗的確切原因為 GHCR manifest HTTP 429，診斷 logs 在 A9 目錄；後續 registry build 及正式重驗均成功，沒有變更 source、daemon 或 cache 來繞過檢查。

全部 fixture containers／Compose projects／其 volumes 由原測試清理；額外診斷 image 由 Main 移除。沒有啟動真實 Funnel 或修改 owner 資料。三位 Sol 均已交接，沒有背景實作仍在執行。

## 下一輪

Main 先完成 A6-2 的安全下載與 owner 選擇／persisted profile／instance lifetime 接線，再凍結 UI payload 與 exact file ownership，拆給三位 Sol 實作 A6 初次使用、A7 管理引導與 A5 人工驗收準備。A8／A11 保持相依順序。公開入口、真實 provider、模型權重及外部驗收的相應授權依保存計劃辦理；本輪沒有尚待決定的內部實作選項。

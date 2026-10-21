# RepoNPC 剩餘實作與並行計劃

**最新接續：**沿用三位GPT-6.1 Sol及Root的[接續分派](REMAINING_WORK_EXECUTION_2026-10-03.md)，最終成果／證據／剩餘閘門见[當前交接](CONTINUATION_HANDOFF_2026-10-03.md)。Approved0.4.8／ADR-055及fixture-only ADR-056／OR-030；正式builtin AC-009、16384推理政策與完整Python2613項通過。修正模型suite9/12未admit；不得把本計劃的完成項目代替完整v1驗收。

狀態：擁有者於 2026-10-03 核准保存並開始執行。Main 負責共用契約、安全、生命週期、持久化與整合；三位 GPT-6.1 Sol 負責指定的獨立模組、測試及驗收。沿用最新 owner 指示，不使用 agent-foreman。

**最新執行結果：** 依 owner 最新指示重用三位 Sol 並行；A6 已有真實固定 bge 及本機 Ollama 證據，A8 已有 exact production installer build 與不同 AppId 的開發機隔離 install／合成 patch overlay／uninstall／資料保留、installed A11 API 證據，A9 已有私有 Man／A5 fixtures。Root A7 卡片→既有設定→明確填入已整合，Web484／42、affected Python226、Ruff258／mypy103、wheel／installer／300 checksums 通過。詳見[最新交接](PARALLEL_IMPLEMENTATION_HANDOFF_2026-10-03.md)；formal baseline／reviewed catalog、Man art／rights、clean-host／完整手動及外部驗收仍未完成。來源 Approved0.4.7。下方第一次授權與舊進度保留其歷史範圍。

## 基準與範圍

以 D:\RepoNPC 目前 working tree 為基準，HEAD 為 main@877c6d6。A1–A4、A10 的 R11／R12-B、Pages 與 B1–B5 簡化已有本機證據；不重做這些批次。A5 仍缺真正 200% zoom 與完整手動／輔助技術驗收。A6、A7、A8、A9、A11 尚未結案，A12 為完整發布閘門。

來源：PROJECT_CONTEXT.md 最新段落、Approved Technical Specification 0.4.7、ACCEPTANCE_CRITERIA.md、DECISIONS.md、IMPLEMENTATION_BACKLOG_2026-09-26.md、COMPLETION_DIRECTION_CONTRACT_2026-09-26.md，以及 current-state-2026-10-03 專案記憶。

保留目前全部未提交修改。不得 reset、stage、commit、push、啟用公開入口、執行 Funnel、寫入 GitHub 或修改真實 owner runtime。初次授權只含本機實作與 disposable fixture；最新三 Sol 批次另授權固定 bge-m3 下載至 disposable 路徑及既有本機 Ollama 的合成資料測試，見下方最新派工。公開、雲端 provider、任意新模型下載與發布仍須相應的明確授權。不要從 HEAD 建立缺少 A5 成果的工作樹。共享 checkout 的每個 worker 只修改列出的檔案，不得回復其他人的修改。

## 剩餘工作

| 工作    | 交付步驟                                                                                                                                                | FR／AC                             | 相依                                               |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- | -------------------------------------------------- |
| A6-1    | 固定官方 bge-m3 artifact manifest；builtin_onnx CPU 推論、tokenizer、1024 維正規化輸出；接既有模型 identity、索引與查詢                                 | FR-049；AC-008／009／070           | 無                                                 |
| A6-2    | 明確首次使用三選一；大小、來源與授權；進度／取消／續傳／逐檔 SHA-256；切換模型完整重建提醒；LKG 不變                                                    | FR-049；AC-070                     | A6-1                                               |
| A7      | 自有且有實測證據的模型目錄；裝置檢查與適合程度；沿用 Ollama helper；錯誤提示、狀態與雲端資料揭露，僅管理端                                              | FR-040；AC-057                     | 與 A6 共用面板由 Main 串接                         |
| A9      | Man／Orange 候選 canonical 素材、28 格檢查、空白模板、動畫預覽、來源／授權；humanoid 矩陣；角色至 bundle／卡片流程                                      | FR-015／016／018；AC-020／021／022 | 最終美術及未確認來源由 owner 核可                  |
| A8      | PyInstaller onedir＋Inno Setup 個人安裝；啟動／健康檢查／管理頁／退出；獨立資料目錄；升級及解除安裝保留資料；checksums／SmartScreen                     | FR-048；AC-069                     | A6；不包含模型權重                                 |
| A11     | 維護頁；SQLite 備份下載與確認還原／自動先備份；bundle pin；gateway stop；更新與 Funnel off 說明                                                         | FR-053；AC-076                     | A8；Main 先明定 backup 範圍及缺失 key／bundle 處理 |
| A5 驗收 | 真正 200% zoom、鍵盤、screen reader、reduced motion、雙語、瀏覽器矩陣與必要修復                                                                         | AC-023／068／072–075／079          | 可與開發並行，以實際 source identity 記錄          |
| A12     | auditor／ledger 至 AC-079（041–043 保留 legacy）；品質／效能、安全、乾淨 Windows／Linux、live provider、Pages／Funnel／GitHub；授權及操作文件、發布成果 | 全部現行 FR／NFR／AC               | A1–A11；外部操作另行授權；D8 owner 執行            |

## 執行輪次

| 輪次   | Sol 1          | Sol 2           | Sol 3                | Main                                |
| ------ | -------------- | --------------- | -------------------- | ----------------------------------- |
| 第一輪 | A6 推論核心    | A7 目錄／純估算 | A9 可重現候選素材    | artifact／介面定稿、依賴及整合      |
| 第二輪 | A6 首次使用 UI | A7 管理 UI      | A5 驗收／A12 auditor | 下載、安全、模型設定／索引／runtime |
| 第三輪 | 雙語檢索量測   | 安全與回復驗證  | A8 安裝驗證          | 正式打包、啟動器                    |
| 第四輪 | A11 維護頁     | A11 故障驗證    | 安裝升級／解除安裝   | 備份還原整合、完整 A12              |

每輪相依由交付成果決定；單包完成後可接無衝突工作，不為等待其他包而空轉。每次正式派工先鎖定 exact paths、輸入輸出與最小反例。網路、API、migration、設定、entrypoint、provider registry、共用 UI／翻譯／CSS、依賴／lockfiles 由 Main 修改。

## 第一輪檔案責任與完成門檻

### Sol 1 A6 推論核心

只新增 src/reponpc/providers/builtin_onnx.py、tests/unit/test_builtin_onnx.py。實作既有 RuntimeEmbeddingProvider 介面：identity、embed_query、embed_passages、health；輸出依既有 EmbeddingIdentity／numpy float32 契約。內部使用已驗證 artifact 目錄與 injectable session/tokenizer。不得下載、不接 API／registry、不選擇 provider、不暴露路徑或輸入文字。ONNX CPU、無 PyTorch；以官方 pinned source 確認 CLS pooling／normalization 與 tokenizer 行為。Main 提供 artifact manifest／驗證與依賴。測試涵蓋雙語輸入、順序、空批、上下文界線、錯誤 shape／非有限／零向量、安全錯誤、無下載。

### Sol 2 A7 目錄與估算

只新增 src/reponpc/admin/model_guidance.py、src/reponpc/admin/model_catalog.yml、tests/unit/test_model_guidance.py。純 loader／估算：外部提供硬體數據，不執行偵測、不呼叫網路、不 pull／選模型。目錄欄位包含參數、量化、記憶體估計、結構化 envelope 實測證據與日期；不得捏造模型通過紀錄。沒有已驗證條目時可明確空目錄，留待 live test 補齊。適合程度以參數×bits＋明確 overhead 計算，unknown 硬體不可當成零或保證可跑。測試使用未見過的模型 ID、不同硬體、unknown 與非法輸入。

### Sol 3 A9 候選素材

只新增 tools/prepare_character_assets.py、tests/unit/test_character_asset_preparation.py；候選成果只寫 release-evidence/a9/ 之下。唯讀 PixelNPC/，使用既有 converter／canonical validator；多候選必須完整列出，不依檔名／物種猜選。輸出 canonical 候選、28 格 contact sheet、七狀態動畫預覽、真正空白模板、hash／警告與來源審查紀錄。所有成果標 draft，不自動接入公開 pack 或宣稱 MIT 授權／美術核可。既有動畫引擎不改寫。測試覆蓋不同結構尺寸、候選歧義、非空／透明／metadata／重現性及來源不變。

### Main 第一輪

新增 src/reponpc/providers/builtin_artifacts.py、src/reponpc/providers/builtin_embedding_manifest.yml 及測試，集中保存完成方向契約 §6.2 的八檔 pin／SHA-256／大小，驗證完成後才容許推論；不得增加 arbitrary URL/path downloader。處理 onnxruntime／tokenizers 的鎖定依賴、package inclusion、provider export 與既有 builder／bundle／查詢介面整合；正式入口接線與 A6-2 的明確首次使用設定、排程及模型生命週期一同完成。模型 identity 需包含固定 revision，現有外部 provider 與 sentence-transformers fixture 路徑維持各自界線。先完成第一輪可測內部基礎，不以 leaf tests 宣稱 A6／A7／A9 全部完成。

## 驗證與交接

worker 回報修改檔案、FR／AC、命令、結果及不足；不可自行宣告 v1 完成。各 worker 使用獨立 writable pytest basetemp，避免同時修改 lockfiles、共用測試產物與 browser ports。Main 獨立審查並跑聚焦與受影響整合測試，整合輪次跑 Python format／lint／mypy／tests、Web format／lint／types／tests／build／guard、git diff --check；部署改動才跑 Docker／Compose。實際模型品質、乾淨主機與人工驗收記錄 pass／fail／not-run／blocked，fixture 不替代真實證據。

## 進度

- **下一輪三路並行已獲 owner 授權（2026-10-03）**：擁有者在 A7 實作流程說明後指示「按照先前的分配把任務給幾個6.1 sol並行」。沿用三位 GPT-6.1 Sol，Main 處理共用契約／A7推薦 UI 接線與驗收整合。這次授權包含前述固定約2.29GB bge-m3 在獨立目錄的下載與本機真實模型驗證；不使用真實 owner runtime，不呼叫已儲存雲端金鑰、不啟用公開入口／Funnel／Pages、不寫 GitHub／Git。下述 exact ownership 適用本輪，取代先前輪次的相同檔案責任。
  - Sol 1 `/root/a6_inference`：A6 真實固定權重與雙語品質／RAM／延遲、本機已安裝 Ollama 模型的 synthetic envelope-v2 實測及 A7 reviewed catalog。只修改 `src/reponpc/admin/model_catalog.yml`，必要測試限 `tests/unit/test_model_guidance.py`；evaluation scripts／reports 只在 `release-evidence/a6/real-model-20261003/`，權重只在 `.pytest-tmp/bge-m3-real-20261003/`。不修改 provider／API／DB／lockfiles，目錄條目須有真實可重現中英證據；無通過條目保留空，不杜撰品質或速度。
  - Sol 2 `/root/a7_guidance`：A8 installer compiler 的 user-local／portable 準備、實際 installer build／disposable install／upgrade／uninstall／保留資料證據，以及 A11 frozen host walkthrough 準備。只修改 `packaging/windows/reponpc.iss`、`tests/contract/test_windows_installer.py` 與 `packaging/windows/README.md`；compiler／安裝輸出／reports 在 `release-evidence/a8/parallel-20261003/`，測試安裝／data 路徑使用該目錄獨立子目錄。先交付可重現 compiler/build/fixture 腳本；真正乾淨 Windows 帳號／無Python主機不以目前開發機冒充。全局安裝、現有 RepoNPC 安裝／owner data／registry 衝突則 fail closed。Main 擁有 LICENSE、notices 最終審核、build script／spec、shared dist 及 frozen build，避免同時覆寫。
  - Sol 3 `/root/a9_assets`：預設 Man 的完整角色候選視覺／28格／七狀態審查、選定合理完整版本與必要 canonical 修整、正式 pack／卡片接線提案；並補 A5 無障礙檢查方案／局部 evidence。來源 `PixelNPC/` 唯讀；只修改 `tools/prepare_character_assets.py`、`tests/unit/test_character_asset_preparation.py`，輸出／審查／walkthrough 限 `release-evidence/a9/man-default-20261003/`、`release-evidence/a5/accessibility-20261003/`。先交 Root 候選與確切production接線檔案提案；Root 保留 public assets／composer／manifest／shared WebCSS 的寫入責任，收到proposal後再明確移交需要的檔案。不得以 owner 選 Man 推定來源授權事實，保留 custom sprite／species-neutral能力；Orange草稿保留。
  - Main：A7 `ModelGuidancePanel.tsx`／`LocalModelSetup.tsx` 及其測試、`admin/operations.py`／private API metadata、全域docs／LICENSE／依賴／打包與browser ports18763–18765；把已有 CPU suitability／catalog 資料呈現為双語逐模型推薦與明確選用，沿用既有模型設定／probe／profile，不新增推薦模型服務／LLM／自動provider切換。模型清單為開放資料，grade／reason codes 是閉合契約；不硬寫單一模型或人工猜速度。若細部提案需要新public contract，先以可審查的文件處理。
  - 所有 worker 都在共用 checkout，保留其他人的修改；各自 fresh pytest basetemp，只跑相關測試，Main凍結後再整合。每包回報 FR／AC、產物、正常／失敗／安全與未能執行的實機條件；不提升全部 AC。概念預算為沿用 catalog／hardware／provider/profile／installer／canonical asset，無新DB、服務、狀態機或download管理器。以具體交付接續工作，不為準備報告而停在 inventory。

- **A9 預設角色決定（2026-10-03）**：擁有者指示「A9預設npc使用man即可」，預設 NPC 採用 Man。後續以 Man 完成 28 格／七種動畫定稿、來源與授權紀錄、正式 pack／bundle／卡片接線；Orange 草稿保留。見 [決定紀錄](A9_MAN_DEFAULT_DECISION_2026-10-03.md)。角色方向已確定，剩餘素材品質、權利紀錄及完整 AC 驗收仍依 A9／A12 執行。

- **最新凍結交接（2026-10-03）**：A6 明確下載／取消／續傳、持久化 profile／共用推論生命週期與 A7 裝置／引導 UI 已接入；A8 最新完整 onedir build、outside-checkout frozen health／stop exit0；owner 批准 A11 選項 A，規格更新至 Approved0.4.7／ADR-054／OR-028。A11 密碼加密原生下載、預檢／取消／確認、資源驗證、自動加密先備份、Main lifespan 重建／rollback／session 撤銷／gateway off 與維護 UI 已本機整合。中英 in-app browser 實際下載相同密文，下載檔 upload／inspect／cancel、錯誤密碼、keyboard 還原與 reauthentication／relogin、八組響應式畫面通過。最新 Web480／42 files、affected Python181、Ruff260／mypy103、guard／wheel／frozen checksums 通過；完整 Python2497／2 Windows skips 在 native GET 新增前完成。詳見 [最新交接](PARALLEL_IMPLEMENTATION_HANDOFF_2026-10-03.md) 與 [來源／artifact 指紋](../../release-evidence/a11/source-artifact-fingerprints-20261003.json)。79-row candidate 為76not-run／3blocked；沒有提升完整 AC。下一步為真實模型品質、已驗證 catalog、clean Windows installer／frozen維護、A5完整無障礙與真正200%zoom、A9美術／權利、A12外部證據；相應模型／外部操作授權與 ISCC／LICENSE 前提仍保留。下列派工紀錄保留為歷史。

- 2026-10-03 A11 選項 A 已由 owner 核准，見 [備份界線決定](A11_BACKUP_BOUNDARY_DECISION_2026-10-03.md)。Sol 1 只新增 src/reponpc/admin/backup_encryption.py、tests/unit/test_backup_encryption.py；bounded versioned Scrypt/AES-GCM bytes container 與 plaintext metadata，不觸 DB/network/API。Sol 2 只新增 src/reponpc/admin/backup_validation.py、tests/unit/test_backup_validation.py；唯讀上傳 SQLite、strict trusted schema／integrity／FK、正規化至受信任 schema，不接 live DB／key／resources。Sol 3 只新增 apps/web/src/features/admin/MaintenancePanel.tsx 及自己的 test；雙語純 presentation、備份／上傳預檢／確認、scope／password／failure labels。Main 擁有路由、host key／bundle／appearance validation、restore quiescence／automatic backup／rollback／relogin、共用 UI／資料持久化、文件與 actual fixture/browser 驗證。所有操作僅 disposable runtime。

- 2026-10-03 第三輪派工契約：在 A6／A7 本機整合及 in-app browser 驗收期間，沿用三位 Sol 接 A8。Sol 1 只新增 src/reponpc/windows_launcher.py、tests/unit/test_windows_launcher.py；小 console、OS 指派 loopback port、health 後一次性 grant、重新開啟與 graceful quit，預設 %LOCALAPPDATA%/RepoNPC/data，測試只用顯式 disposable data-dir。Sol 2 只新增 packaging/windows/reponpc.iss、tests/contract/test_windows_installer.py；per-user、固定 AppId、升級／解除安裝預設保留 install folder 外的資料，不新增自動刪除。Sol 3 只新增 packaging/windows/reponpc.spec、packaging/windows/launch.py、scripts/build_windows.ps1、tests/contract/test_windows_packaging.py；onedir、预建 Web／registry／native dependencies，不包含任何模型權重；版本由 pyproject 唯一來源提供。Main 擁有 frozen resource 接線、windows-build 依賴／lock、workflow、實際打包及 fixture 啟動、營運／發布文件。禁止安裝到真實使用者資料目錄、寫 Git／啟用公開入口／下載模型權重；clean Windows 與 SmartScreen／upgrade／uninstall walkthrough 不能以 fixture 視為 pass。

- 2026-10-03 第二輪授權：擁有者要求繼續，指定可用 in-app browser 驗收。Sol 1 只擁有 src/reponpc/providers/builtin_download.py、tests/unit/test_builtin_download.py，實作 injected streaming transport 的本機取消／續傳／驗證及原子發布；HTTP egress、API、profile／runtime／DB／生命周期由 Main 擁有。Sol 2 只擁有 src/reponpc/admin/device_check.py、tests/unit/test_device_check.py，實作唯讀有限硬體觀測，返回第一輪 HardwareProfile，不觸發網路或模型工作。Sol 3 待 Main 凍結 UI payload 後接 A6／A7 管理元件；共用 AdminWorkspace、translations／CSS 及 browser 驗收由 Main 整合。所有 worker 保留其他人的 edits，不使用 agent-foreman；原來的 Git／外部／真實權重／owner runtime 限制持續有效。

- 2026-10-03：計劃保存，第一輪開始。尚未更新任何 AC 為 pass。
- 2026-10-03：A6 推論核心、A7 目錄／估算、A9 草稿準備已交付，Main 進行跨模組驗證。A7 worker 接續 A12 auditor：只修改 tools/release_audit.py 與 tests/unit/test_release_audit.py，將文件及 ledger 完整性要求更新至 AC-079，保留 AC-041–043 的 legacy 記錄；不修改 ledger、不執行外部操作、不把覆蓋完整視為驗收通過。
- 2026-10-03：A6 worker 接續 tests/integration/test_builtin_embedding_bundle.py，經現有 builder／bundle verifier／查詢驗證 builtin identity、1024 維向量與錯誤阻擋；使用真正合成 tokenizer 及明確測試 session，不下載權重、不宣稱真實模型品質。Main 負責 provider export、共用組態與部署驗證，首次使用設定及正式啟用留在 A6-2。
- 2026-10-03：第一輪基礎交付與 Main 整合驗證完成。Python 1901 pass／2 既有 Windows skips；Web 388／38 files、Ruff 231／mypy 94、wheel resources／native CPU imports、guard、Docker／Compose 2 均通過。修復 ZIP raw filename 邊界及 provider 失敗留下暫存 SQLite；保留原例外與 LKG。A12 auditor 至 AC-079，歷史 ledger 保留且仍缺 062–079。詳見 [第一輪交接](PARALLEL_IMPLEMENTATION_HANDOFF_2026-10-03.md)。下一輪先由 Main 完成 A6-2 下載／profile／生命週期及 UI 契約，再依 exact paths 派工；A6／A7／A9／A12 完整驗收未結案，沒有新增 AC pass 或外部操作。

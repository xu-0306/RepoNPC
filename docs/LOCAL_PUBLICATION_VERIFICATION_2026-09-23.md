# 本機發布與 GitHub 卡片引導驗收 — 2026-09-23

本次交付為 ADR-046 的本機主流程。使用者已明確表示目前沒有公開 HTTPS 網址，先完成本機並保留分享設定。功能驗收沒有建立公開入口，也沒有修改 GitHub Profile repository 或 README；專案原始碼的提交與推送另行處理。

## 已完成的行為

- 引導內容與角色共用本機草稿；Orange 經既有轉換、清理選擇及對齊驗證後可直接套用。
- 一般工作區提供「預覽與分享」：完整作品集／卡片預覽、儲存、準備／更新、取消和試聊。YAML 是選用備份。
- 本機建立與驗證不可變 bundle，再原子啟用；查找使用已選 embedding 模型，回答使用已選 chat 模型。GitHub Actions、Release 和 GitHub 寫入 token 均非本機主流程必要條件。
- 受限 passage cache 重用相同內容及完整模型身分的向量；內容或模型改變會重新計算必要部分。新問題仍須 query embedding。
- GitHub 三步引導涵蓋同名公開 Profile repository／README、GIF 上傳、保留原文的 README 嵌入及檢查。實際分支由 metadata 決定；未知、找不到和讀取失敗分開顯示。
- 無公開網址時仍可準備本機 NPC。空白、localhost 和私人網址不會產生宣稱可對外聊天的 Markdown。只在目前 browser session 保留安全的分享欄位。

## 主要修改位置與需求

| 範圍 | 主要檔案 | 對應 |
| --- | --- | --- |
| 本機草稿、準備與取消 | `src/reponpc/admin/local_portfolio.py`, `local_publication.py`, `embedding_reindex.py`, `src/reponpc/main.py` | ADR-046、FR-019–021、AC-026/029–032 |
| API、引用與驗證 | `src/reponpc/api/admin.py`, `public.py`, `src/reponpc/bundles/archive.py`, `index_reader.py`, `manager.py` | FR-006/012/019–021、AC-029–032/034–040 |
| 索引重用 | `src/reponpc/indexing/passage_cache.py`, `index_database.py`, `pipeline.py`, `sources.py` | ADR-046、FR-019–021 |
| 角色與普通使用者流程 | `apps/web/src/features/admin/AdminPage.tsx`, `AdminWorkspace.tsx`, `CharacterAssetConverter.tsx`, `LocalPublishingWorkspace.tsx`, `GitHubShareGuide.tsx`, `sharing.ts` | FR-015/018/022–025、AC-020/023/026 |
| 真實試聊所發現的修正 | `src/reponpc/chat/service.py`, `apps/web/src/app/App.tsx`, `visitorChat.ts`, `chatAdmission.test.ts` | FR-012、現有聊天限制／安全契約 |
| 文件與操作 | `LOCAL_PUBLICATION_CONTRACT_2026-09-22.md`, `TECHNICAL_SPEC.md`, `ACCEPTANCE_CRITERIA.md`, `DECISIONS.md`, `SECURITY.md`, `OPERATIONS.md`, `README.md` | ADR-046、規格 0.3.9 |

這是本次涉及需求的對照，不代表上述全部 v1 接受條件或歷史修復計劃均已完成。工作樹原有其他修改完整保留。

## 自動化結果

| 驗證 | 結果 |
| --- | --- |
| Python unit/security/integration/contract/eval + 新增獨立 fault probe | 1,096 passed，2 skipped，105.97 秒 |
| 最後 provider 類型與聊天歷史修正後的相關 backend 回歸 | 38 passed |
| 最後 provider lifecycle + 獨立 fault probe | 9 passed |
| 全前端 Vitest | 29 files，220 passed |
| workspace/share 專用 Vitest（含 repo 根目錄 tests/web） | 25 passed；其中 sharing 的 15 項也在全前端套件內，不重複加總 |
| Ruff lint/format、mypy | 通過；mypy 檢查 73 個 source files |
| TypeScript、Vite production build、變更處格式檢查 | 通過 |
| 變更處 ESLint | 0 errors；App 有 2 個既有 Fast Refresh warnings |
| git diff --check | 通過 |

兩個 skip 是 Windows 不提供的 POSIX mode bits／descriptor no-follow 語意。Python 有既有 Starlette/httpx deprecation warning。部分 Node 指令在 sandbox 遇到 EPERM，重新用獲准的本機建置權限執行後通過，沒有省略失敗。

## in-app browser 與實際資料

- 使用 `xu-0306/live-subtitle`、`xu-0306/framefit-media-shrinker`、`xu-0306/anti-hardcode-engineering` 建立的本機索引已啟用。僅採用使用者確認的「與 Codex 協作完成」貢獻文字。
- Orange 已出現在作品集、角色預覽及卡片。服務重啟後仍還原相同 active bundle；最終 `/api/public/status` 顯示 ready、chat_available=true。
- 中文 live-subtitle 功能問答成功，附 `085d4055fba24bf6a2111a1c95fd55e283961a6b` 的 README 1–14、16–25 行引用。
- 英文 FrameFit 檔案類型問答成功，附 `5eae255fa99686c67de6df7cd962e8f51a58ea94` 的 index.html 1–124 行引用。
- 最終重啟後，本人確認陳述問答成功，引用 `OWNER_ASSERTION` 並連到本站 `/api/public/owner-statements/...` 的純文字來源，沒有偽裝成 Git commit。
- 也觀察到安全拒答與一次暫時模型離線；重新檢查後恢復並成功重試。要求 README 的 FrameFit 問題未取得 README 證據，模型安全拒答；並未偽造 README 引用。本次樣本不代表完整真實模型品質評估。
- 使用者已於本次續接明確允許用目前設定的 coderelay／gpt-5.6-terra 回答服務，傳送測試問題、公開貢獻文字及公開專案檢索片段。先前診斷的自動核准阻擋因此已解除。沒有輸出模型密鑰或提示內容。
- 輸入 GitHub Profile URL 能正規化為帳號。對 xu-0306 的匿名檢查回報找不到可見的同名公開 repository，介面提供明確的建立步驟；沒有將此說成私人 repository 不存在。
- 中英文分享引導、reload 後帳號保留、無公開網址及 localhost 停用分享均已走訪。
- 公開卡片 endpoint 可取得有效 GIF：600×180、4 幀、33,944 bytes。副本位於 `runtime-data/local-publication-evidence-2026-09-23/reponpc-card.gif`。

## 審核發現與修復

1. 真實專案不一定包含測試字詞 `retrieval`。bundle 與 restart 的 lexical smoke 改從索引內容取得查詢詞，保留完整驗證。
2. 新模型組合建立失敗時，完整還原 chat profile、provider runtime、chat service 和 adapter。
3. 獨立 probe 重現 provider transition 後接受取消卻仍啟用的競態。新增 commit 前 guard；已接受的取消或逾時會回復 bundle／provider／profile，進入 commit 後明確拒絕取消。三個正式回歸及原始 fault probe 通過。
4. 回滾到前一 bundle 後，草稿不再被誤報為已套用。初次準備不再聲稱存在舊版本。
5. 模型提示明確說明每一實質文字行的引用及來源 ID 格式；既有來源／個人歸屬驗證保持不變。
6. 真實多輪提問重現前端 10 則上限超過後端預設 6 則而 413。既有錯誤 details 回報數值上限，前端只重試一次，保留最近完整問答並維持可見 transcript。超長當前問題、錯誤限制、取消或第二次拒絕均不繞過限制。

## 範圍與仍待確認

- in-app browser 的 GIF 下載按鈕確實觸發操作提示，但工具未收到 download event，也未在預設 Downloads 找到檔案。**UI 下載落盤未驗證完成**；上述 GIF 副本來自公開 endpoint，不冒充 UI 下載證據。
- 本人確認陳述的引用已在聊天介面正確呈現；開啟純文字來源時，in-app browser 回報 `net::ERR_BLOCKED_BY_CLIENT`。來源 endpoint 的整合測試通過，但**瀏覽器開啟來源未驗證成功**；未改用其他瀏覽器或網路方式繞過此阻擋。
- 尚未進行公開 HTTPS、GitHub README 真正寫入或從外部 Profile 點卡片至 NPC 的實測，符合使用者指定的本次交付邊界。
- 沒有做本次不涉及的 Docker／Compose 發布、跨瀏覽器／螢幕閱讀器完整矩陣或乾淨主機正式驗收。
- 功能驗收沒有新增代管服務、tunnel 或公開 admin/model port。
- Luna worker 提供草稿儲存、cache 和分享元件；Main 整合及審核。取消修正的續接未具備新的 dispatch readiness receipt，已如實列為 uncontrolled 候選並由 Main 接管，沒有追溯補造。細節見 `.agent-foreman/local-first-review-2026-09-23/CANCELLATION_FIX.md`。本次不宣稱正式 agent 效率或多模型可靠性基準。

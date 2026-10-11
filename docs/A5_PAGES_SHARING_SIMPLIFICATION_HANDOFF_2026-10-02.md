# A5 Pages 分享收據系統簡化交接（2026-10-02）

**狀態：** 專案擁有者已於 2026-10-02 核准「選項 1」：在 A5 提交前簡化 Pages 分享，接受本文 §5 的契約變更（端點、migration 33、回應標頭、A5 契約 §5），也接受 §5.3 的語意：本機變更不會自動讓 verified 失效。§7 步驟 0 只剩「擁有者的資料目錄是否已套用 migration 33」一項需要確認。同日擁有者也核准 [A1–A4 審查](A1_A4_COMPLEXITY_AUDIT_2026-10-02.md) §6 的全部項目，執行範圍見本文 §11。commit 與 push 仍需另行指示。
**來源：** 2026-10-02 以 anti-complexity-engineering 審查目前 A5 未提交工作的結論。
**讀者：** 接手的實作／審查 Agent。開工前仍須依 `AGENTS.md` §1 讀完必讀文件。

**最新執行進度（2026-10-02；覆蓋下方歷史狀態描述）：** Pages §7 步驟 0–5 已完成，步驟 6 本機閘門也通過。原聊天已唯讀確認擁有者 launcher runtime 為 schema 27，未套用 33；本輪不修改真實資料。Pages 專項 86 通過、完整 Python 1,658 通過／2 Windows 略過（另補 6 個回歸案例已專項通過）、Web 388 通過、格式／lint／型別／build／registry／source guard 通過，Docker 2 通過。繁中與英文原生 ZIP 均已完成落盤，23 個 manifest 檔案雜湊全數相符。完整命令、變更範圍與限制見 [本機驗證證據](../release-evidence/a5/pages-simplification-2026-10-02.md)。下一批為 §11 B1；B1–B5 與步驟 7 尚未完成。200% zoom、完整手動／輔助技術矩陣及 A12 仍開放；沒有 commit／push／部署。

**最新交接（2026-10-03；覆蓋上述歷史進度）：** Pages 與 §11 B1–B5 的指定簡化均完成本機閘門，§7 步驟 7 已完成。最終 Python 1703 passed／2 skipped、Web 388 passed、Docker 2 passed；原生 FAQ 19 項、gateway 11 項與雙語 ZIP 落盤／23 records 雜湊通過。B1–B5 應用程式實測淨減 1156 行，沒有新增產品概念或 domain state。見 [總交接](../release-evidence/a5/simplification-handoff-2026-10-03.md) 與新 current-state-2026-10-03 記憶；200% zoom、完整手動／輔助技術矩陣及 A12 仍開放。沒有 commit／push／部署或真實資料遷移。

---

## 0. 一句話結論

Pages 分享的「已核對」狀態**可以每次從資料推導**（匯出是決定性的），但目前實作把它存成一份帶修訂號的收據，接著為了讓收據不過期，又加上 CAS、微秒時間戳、重讀比對、UI 欄位比對等一整層防競態機制。**收據本身是衍生層，也是這些競態的根源。** 刪掉收據，改成「核對時重新計算期望 manifest、跟遠端位元組比對」，約可刪除 1000 行以上的程式碼與測試，功能需求（FR-047、AC-068）不變。

### 0.1 本輪分析歸檔與執行入口（2026-10-02）

本文是這次簡化工作的主計劃；[A1–A4 審查](A1_A4_COMPLEXITY_AUDIT_2026-10-02.md) 保留分析證據，專案記憶只維護入口與進度，不另建一份平行計劃。

**核對結論：** 本輪分析涵蓋的 Pages、A1–A4 與未提交 A5 FAQ 實作，仍符合記憶所記錄的「已核准簡化、尚未執行」狀態。保存分析時再次確認 `main@877c6d6`，並抽查 receipt、epoch、legacy envelope、pronoun rewriting、participation metadata、rewrite request、FAQ chip re-check 與重複 helper 仍存在。這是指定範圍的靜態核對，不代表全專案無缺陷或驗收通過。

| 分析發現／待刪合併層 | 重用的既有能力 | 計劃位置與核准項目 |
|---|---|---|
| Pages receipt、CAS、微秒時間戳、前端逐欄比對 | 共用匯出內容、manifest/hash、遠端抓取與位元組比對 | §7；Pages option 1；FR-047／AC-068 |
| A5 FAQ fingerprint、重複驗證、matcher 設定、雙 resolver helper | 同一讀取交易、寫入驗證、資料庫約束、manifest schema、共用 helper | §11.2 B1；已納入的內部項目 |
| A2 legacy adapter 與代名詞改寫 | v2 segments、證據 ID 驗證、後端引用建構 | §11.3 B2；A2-1b、A2-4；AC-064 |
| A3 只寫不讀的 metadata 與隱含 collector 轉送 | typed participation evidence、明確傳入 collector | §11.4 B3；A3-2 與內部項目 |
| A4 rewrite 平行生命週期、client bundle 欄位、chip re-fetch | 既有 claim 編輯器、local draft、一般 regenerate/review | §11.5 B4；A4-1、A4-3、A4-4、A4-5；FR-046／AC-067 |
| A1 verification epoch／identity 比對與重複處理器 | 設定 revision、listener readiness、單一 verified_at 語意、共用聊天流程 | §11.6 B5；A1-1、A1-4；AC-071 |

**執行順序：** §7 步驟 0–6 → B1 → B2 → B3 → B4 → B5 → §7 步驟 7。對話分析曾依問題重要性列出 Pages → A1 → A4 等順序，那不是新的執行順序；本表與 §11.1 維持原先核准的批次安排。

**根因與保留邊界：** 主要負擔來自重述既有事實的衍生狀態及平行生命週期。前三個刪除／合併重點是 Pages receipt、A1 verification state、A4 rewrite lifecycle。保留 admin／CSRF／same-origin、SSRF 傳輸限制、schema 與證據 ID 驗證、後端引用 URL 建構、FAQ allowlist 與伺服器 revision／active bundle 檢查、participation 登入連結與 `None` 語意，以及 bundle 啟用驗證、last-known-good 與 rollback。

**參照與概念預算：** 本次整理以專案內既有能力為重用依據，未新增外部參考實作的量化比對；先前「成熟做法」的概念數是審查估計，不能當成實測基準。文件整理新增執行批次與產品概念均為 0；實作刪除清單沿用 §6、§11，行數為估計，完成後才填實際值。凍結規則沿用 §9；scene 發布生命週期、visitorData 重新雜湊與傳輸實作評估仍依 §8 延後。

**驗證與待確認：** 本輪只保存分析並釐清文件入口，未修改應用程式、未重跑測試／lint／build；§1 的結果是歷史證據。migration 33 是否已套用於擁有者真實資料目錄仍未確認，處理依 §7 步驟 0。已核准項目無須再次取得同一份核准。

---

## 1. 目前狀態與限制

- 分支 `main`，HEAD `877c6d6`。A5 全部**未提交**（61 個已追蹤檔案修改，約 50 個未追蹤新檔）。
- 最近本機閘門（見 `release-evidence/a5/resume-2026-10-01.md`）：Python 1655 pass / 2 Windows skip、Web 389/38、mypy 91、Ruff 219、Docker 2 PASS。
- A5 尚未結案的項目：原生 ZIP 下載（瀏覽器下載事件 20 秒逾時）、真正 200% zoom、手動／輔助技術矩陣、A12。
- 擁有者常設限制（仍有效）：
  - 未經擁有者明確指示，不得 commit、push、部署、呼叫真實 provider、寫 GitHub、上傳 Pages、啟用 Funnel。
  - 保留未追蹤目錄 `%SystemDrive%/`、`.claude/`、`PixelNPC/`、`RepoNPC_R09_R14_REPAIR_2026-09-17/`；stage 時只列明確檔案。
  - 變更端點、schema、migration、錯誤碼或 AC 前必須先問擁有者（`AGENTS.md` §3）。
  - 繁中與英文行為需等價；CJK 文件以 UTF-8 寫入並檢查無 U+FFFD。
  - pytest 需加 `--basetemp=<可寫目錄>`，否則 `%TEMP%\pytest-of-xu` 會出現 WinError 5。
  - 不使用 `agent-foreman`。

---

## 2. 需求到底要求什麼

**規格原文**（`docs/TECHNICAL_SPEC.md` FR-047，第 301 行附近）對核對只有一句話：

> The GitHub card links to the owner-entered page URL after a fetch and manifest-hash check.

其餘要求：
- 匯出只含公開資料，通過 secret scan，符合 Pages 大小限制，不含 admin 路由；
- 有 `.nojekyll` 和雜湊過的 manifest；
- CORS 只允許 Pages origin，且不帶 credentials。

**AC-068**（`docs/ACCEPTANCE_CRITERIA.md` 第 778 行）要求匯出包含 `.nojekyll`、有雜湊 manifest、通過 secret scan、只含 gateway origin、不超過大小限制。**沒有任何需求要求「保存匯出收據」、「設定修訂號」或「下載連結必須與重讀狀態逐欄相符」。**

這些都是在 A5 契約 §5（`docs/A5_VISITOR_APPEARANCE_EXPORT_CONTRACT.md` 第 392–472 行）中，隨著多輪審查發現的競態問題逐一加上去的實作細節。

---

## 3. 目前的實作（問題所在）

### 3.1 資料：migration 33 `pages_sharing_state`

- 位置：`src/RepoNPC/runtime/database.py` 第 1329–1397 行。
- 結構：單列表格，共 13 個欄位，加兩個整列一致性 CHECK。欄位包括：
  - `settings_revision`、`pages_url`；
  - `expected_manifest_json`（最多 4 MiB）、`export_sha256`、`bundle_id`、`character_revision`、`faq_fingerprint`、`export_settings_revision`、`exported_at`；
  - `verified_export_sha256`、`verified_settings_revision`、`verified_at`。
- **HEAD 的 migration 只到 30**，31–33 都還沒提交。因此 33 可以直接改寫，不必另加 34。
  - 例外：如果擁有者自己的真實資料目錄已經跑過 33，改寫前要先問擁有者（見 §7 步驟 0）。

### 3.2 後端：`src/RepoNPC/sharing/pages.py`（562 行）

`PagesSharingService` 的主要方法：

| 方法 | 做什麼 | 屬於哪一層 |
|---|---|---|
| `state()` | 讀收據，再用 `_export_binding_current` 重新確認收據沒過期 | 衍生層 |
| `configure_pages` | `BEGIN IMMEDIATE` + `settings_revision` CAS；URL 改變時清空整份收據 | 衍生層（CAS 只為了保護收據） |
| `export_context` | 擷取修訂號、bundle、角色修訂、FAQ fingerprint，供之後比對 | 衍生層 |
| `record_export` / `_commit_export` | 在 `_source_guard`（四段鎖順序）內重新比對全部欄位，寫入收據；用 `_timestamp_after` 產生嚴格遞增的微秒時間戳；寫入後重讀並用 `_receipt_identity` 比對 | 衍生層 |
| `verify` / `_commit_verification` | 從收據取出期望 manifest，抓遠端內容比對，再在鎖內逐欄確認收據沒被換掉才寫入 verified | 混合：**抓取與比對是需要的**，收據比對是衍生的 |
| `_clear_verification` | 以 9 欄身分條件清除 verified | 衍生層 |
| `_validated_target`、`_current_origins` | URL 與 origin 驗證 | **邊界，保留** |

### 3.3 API：`src/RepoNPC/api/admin.py`

| 路由 | 行號 | 現況 |
|---|---|---|
| `POST /api/admin/sharing/export` | 1729 | body 為 `{expected_settings_revision}`；建 ZIP、寫收據，回傳 ZIP 並附 `X-RepoNPC-Export-SHA256`、`-Bundle-ID`、`-Character-Revision`、`-Sharing-Settings-Revision`、`-Exported-At` 標頭；不一致時回傳 `SHARING_CONFLICT` |
| `GET /api/admin/sharing/state` | 1801 | 回傳收據衍生狀態 |
| `PUT /api/admin/sharing/pages` | 1818 | body 為 `{pages_url, expected_settings_revision}` |
| `POST /api/admin/sharing/verify` | 1841 | body 為 `{expected_settings_revision, export_sha256}` |

### 3.4 前端

- `apps/web/src/features/admin/pagesReceipt.ts`（81 行）：從 POST 回應標頭解析收據，再與重讀的 state 逐欄比對（`pagesExportReceiptMatches`），全部相符才允許下載。
- `apps/web/src/features/admin/PagesSharePanel.tsx`（458 行）：
  - 第 213–256 行 `exportSite`：`requestBlob` POST → 驗收據 → 重讀 state → 比對 → `URL.createObjectURL` → 下載連結（含 Blob URL 回收）；
  - 第 258 行起 `verifySite`。
- `LocalPublishingWorkspace.tsx:130` 讀 state，`:315` 用 `verified` 決定 GitHub 卡片能否連到 Pages。
- `sharing.ts:97` 的 `verifiedPagesMarkdown` 產生 README 文字。

### 3.5 測試（多數是以審查輪次命名，鎖住的是衍生層行為）

| 檔案 | 行數 | 處理 |
|---|---:|---|
| `tests/security/test_a5_pages_receipt_review.py` | 85 | 刪除 |
| `tests/security/test_a5_pages_api_review.py` | 185 | 改寫：只留 auth、CSRF、admin 邊界與錯誤碼 |
| `tests/security/test_pages_verification.py` | 340 | 改寫：只留抓取／比對／拒絕案例 |
| `tests/security/test_a5_pages_transport_review.py` | 240 | **保留**（傳輸邊界） |
| `tests/security/test_a5_sharing_review.py` | 476 | 逐案檢視：匯出內容與 secret scan 保留，收據競態刪除 |
| `tests/integration/test_runtime_database.py` 第 1104–1200 行 | 約 100 | 改成新 schema 的單一 migration 測試 |
| `apps/web/src/features/admin/PagesSharePanel.test.tsx` | 96 | 改寫 |

---

## 4. 根因層（root-layer statement）

- **出錯的層：** 「存起來的匯出／核對收據」（migration 33 的大部分欄位，加上 `pages.py` 的 receipt 方法和 `pagesReceipt.ts`）。
- **反事實：** 如果沒有收據，以下問題都不會存在：
  - 匯出後收據被另一次匯出覆蓋；
  - 核對時收據已經換掉；
  - 時間戳相同無法分辨；
  - 前端下載連結與重讀狀態不一致；
  - `SHARING_CONFLICT` 的大部分觸發點。
- **分類：** 收據是**衍生層**，它重述的是「目前快照會產生哪份 manifest」，而這件事系統隨時可以重新算出來。
- **能推導的證據：** 匯出是決定性的。
  - `src/RepoNPC/sharing/export.py:628` 以固定的 `ZipInfo(name, date_time=(1980,1,1,0,0,0))` 寫 ZIP；
  - `manifest.py` 的 `create_manifest` 只由這些輸入組成，不含任何時間戳：檔案內容（排序後）、`bundle_id`、`character_revision`、`pages_url`、`base_path`、兩個 origin；
  - `canonical_json_bytes` 是正規化 JSON。
  - **但「同一快照建兩次得到相同位元組」目前沒有測試證明，這是實作第一步要補上的。**

---

## 5. 目標設計（薄版）

### 5.1 參照

> 「部署後核對」在一般靜態網站工具裡是：本機算出期望內容的雜湊 → 抓遠端 → 比對。不保存中間收據，也沒有修訂號。

### 5.2 資料

把 migration 33 改寫成只存：

```sql
CREATE TABLE pages_sharing_state (
    singleton_id INTEGER PRIMARY KEY CHECK(singleton_id = 1),
    pages_url TEXT CHECK(pages_url IS NULL OR length(pages_url) BETWEEN 1 AND 2048),
    verified_pages_url TEXT CHECK(verified_pages_url IS NULL OR length(verified_pages_url) BETWEEN 1 AND 2048),
    verified_content_sha256 TEXT CHECK(verified_content_sha256 IS NULL OR (
        length(verified_content_sha256) = 64 AND verified_content_sha256 NOT GLOB '*[^0-9a-f]*')),
    verified_at TEXT CHECK(verified_at IS NULL OR length(verified_at) BETWEEN 1 AND 64),
    CHECK((verified_pages_url IS NULL) = (verified_content_sha256 IS NULL)
          AND (verified_pages_url IS NULL) = (verified_at IS NULL))
);
INSERT INTO pages_sharing_state(singleton_id) VALUES (1);
```

如果現有設定儲存已經有適合放 `pages_url` 的位置，就用它，不另建表；改之前先查。

### 5.3 語意

- **`verified` 的定義：** `verified_pages_url == pages_url`。它表示「在 `verified_at` 時，遠端網站與當時的本機快照完全相符」。
- 本機之後換角色或改 FAQ，**不會自動讓 verified 失效**：
  - 已上傳的靜態網站仍然可用，卡片連到的 URL 仍然有效；
  - 內容是否需要更新，由擁有者重新匯出並核對決定。這與 `docs/PAGES_SHARING_GUIDE.md` 第 24–29 行的既有說法一致：匯出內容是快照，變更後需重新匯出、上傳、核對。
- 如果擁有者希望在 UI 提示「本機內容已在核對後變更」，列為 Deferred，**不要**為此把收據加回來。

### 5.4 端點（契約變更，需擁有者核准）

| 端點 | 新行為 |
|---|---|
| `GET /api/admin/sharing/state` | 回傳 `{pages_url, configured, verified, verified_at, verified_content_sha256}`。不重算 manifest，不持鎖。 |
| `PUT /api/admin/sharing/pages` | body 為 `{pages_url}`；保留 CSRF 與 `_validated_target`。URL 改變時清空 verified 三欄。單一擁有者，採 last-write-wins，**不要 revision CAS**。 |
| `GET /api/admin/sharing/export` | **沒有副作用**。需 admin session，回傳 `FileResponse`，帶 `Content-Disposition: attachment; filename="reponpc-site.zip"`、`Cache-Control: no-store`、`nosniff`。<br>前端改用原生 `<a href download>`，不再用 Blob 或 `createObjectURL`。<br>GET 不改狀態，跨站請求也讀不到回應，所以不需要 CSRF token；session cookie 的 SameSite 設定維持原樣。<br>刪除所有 `X-RepoNPC-*` 收據標頭；如需顯示內容識別碼，可只保留 `X-RepoNPC-Export-SHA256`，作為資訊用。 |
| `POST /api/admin/sharing/verify` | body 為空；保留 CSRF。步驟：<br>1. 在現有的 `scene_service.published_profile()` 快照租約內建出期望的 files dict 與 manifest（與匯出共用同一個函式，見 5.5）；<br>2. 用 `fetch_pages_resource` 抓 `<pages_url>`（entrance，≤1 MiB）和 `<pages_url><MANIFEST_NAME>`（≤4 MiB），共用一個 20 秒絕對期限；<br>3. 檢查 status 200 與 content-type；遠端 manifest 位元組必須等於 `canonical_json_bytes(期望 manifest)`（含結尾換行，與匯出寫入的格式一致）；entrance 的大小與 sha256 必須等於 manifest 裡 `index.html` 的紀錄；<br>4. 相符就寫入 `verified_pages_url = pages_url`、`verified_content_sha256`、`verified_at`；不符就清空 verified，回傳 `SHARING_VERIFICATION_FAILED`；網路錯誤回傳 `SHARING_VERIFICATION_UNAVAILABLE`。<br>寫入時只需一個條件：`UPDATE ... WHERE pages_url = ?`。這是唯一真實的競態：核對期間擁有者剛好改了 URL。 |

錯誤碼：`SHARING_CONFLICT` 應只剩極少數情況，或可以刪除。檢查前端和文件的引用後，**由擁有者決定**是否從契約移除。

### 5.5 共用建置函式

把 `export.py` 的 `build_visitor_site_export` 拆成兩部分：
- 純函式：`build_site_files(snapshot, faq, web_dist, pages_url, origins) -> (files: dict[str, bytes], manifest)`；
- 寫 ZIP 的部分。

匯出和核對都呼叫前者，保證兩邊算出的 manifest 一致。下列邊界保留在純函式裡，**一個都不能少**：
- `_scan_public_secrets`、`_validate_public_links`、`_add_cited_owner_assertions`；
- 大小限制；
- `_verify_written_export`（寫出 ZIP 後的自我檢查）。

### 5.6 必須保留的邊界（不要以「簡化」為由削弱）

- **URL 與 origin：**
  - `_validated_target` / `pages_target`：exact configured `*.github.io` origin，只允許 HTTPS，拒絕空白與控制字元；
  - `_current_origins`：從 gateway 設定取得 origin 並正規化，設定無效時 fail closed。
- **抓取（`pages_transport.py`）：** 不跟隨 redirect，不帶 credentials，只連公開 IP（`_public_ip` / `_check_peer`），有大小上限和絕對期限。
  - 這裡也偏重（pinned DNS／TLS、最多 4 個進行中的 OS DNS 呼叫、socket shutdown timer），但它屬於 SSRF 邊界，**這次不動**，只列入 Deferred。
- **匯出內容：** secret scan、只含公開資料、連結驗證、`.nojekyll`、manifest、大小限制、不含 admin 路由。
- **權限：** admin session 檢查（`faq_boundary`），以及會改狀態的請求（PUT 與 POST）都要 CSRF。

---

## 6. 刪除清單（deletion ledger）

| 刪除或合併 | 位置 | 預估 |
|---|---|---|
| migration 33 的 10 個收據欄位與兩個整列 CHECK | `runtime/database.py` | 約 55 行 |
| `export_context`、`record_export`、`_commit_export`、`_commit_verification`、`_source_guard`、`_export_binding_current`、`_manifest_from_row`、`_clear_verification`、`_receipt_identity`、`_timestamp_after`、`_read_archive_manifest`、`PagesExportContext`；`configure_pages` 的 CAS | `sharing/pages.py` | 562 行降到約 150 行 |
| 匯出端點的 context／record 兩段流程與 6 個收據標頭；verify／pages 端點的 revision 參數；`SiteExportRequest`、`PagesVerifyRequest` 的 revision 欄位 | `api/admin.py` | 約 60 行 |
| 整個檔案 | `apps/web/src/features/admin/pagesReceipt.ts` | 81 行 |
| `exportSite` 的 Blob、收據、重讀比對，以及 Blob URL 回收邏輯 | `PagesSharePanel.tsx` | 約 120 行 |
| 收據競態測試 | §3.5 所列 | 約 500 行以上 |
| 契約 §5 的收據、修訂號、微秒時間戳、captured-field 比對、Blob 文字 | `A5_VISITOR_APPEARANCE_EXPORT_CONTRACT.md` | 改寫成外部行為描述 |

**新增的概念：** `build_site_files` 純函式，以及 verified 三欄。它們取代原本 13 欄的收據和 revision，概念數淨減少。

---

## 7. 修正步驟

**步驟 0：確認 migration 33 的實際使用狀態（改寫前必要）**
- 選項 1、§5 所列契約變更與 §5.3 的 verified 語意已獲核准；FR-047 與 AC-068 文字不需修改，不再要求重複核准。`SHARING_CONFLICT` 的最終去留仍依 §5.4 處理。
- 確認擁有者自己的資料目錄是否已經套用過 migration 33（可唯讀查詢 migration 紀錄；無法確認真實目錄時詢問擁有者，不以測試資料庫推斷）。
  - 若已套用：由擁有者決定重建開發資料庫，或保留 33 並新增 34 做轉換；
  - 不要自行刪除任何資料庫。

**步驟 1：先證明匯出是決定性的**
- 新增一個測試：同一快照連續建置兩次，manifest 位元組和 ZIP 位元組都要完全相同。
- 如果不同，先找出並修正不決定性的來源（例如 dict 順序、mtime、壓縮參數），再繼續。這一步是整個設計成立的前提。

**步驟 2：更新文件**
- A5 契約 §5 改寫成只描述外部行為：設定 URL、下載 ZIP、核對方式，以及判定為 verified 的條件。
- 同步修改以下文件中與匯出／核對有關的描述：`docs/PAGES_SHARING_GUIDE.md`（雙語）、`README.md` 第 5 行、`docs/OPERATIONS.md`、`docs/A5_HANDOFF_2026-09-30.md`。
- `docs/SECURITY.md` 與 `docs/TECHNICAL_SPEC.md` 目前沒有引用收據細節，確認後不需要修改。

**步驟 3：後端**
- 拆出 `build_site_files`；
- 改寫 migration 33；
- 把 `PagesSharingService` 縮成 `state`、`configure_pages`、`verify` 三個方法；
- 把匯出改成沒有副作用的 GET。

**步驟 4：前端**
- 刪除 `pagesReceipt.ts`；
- 匯出按鈕改成 `<a href="/api/admin/sharing/export" download>`；
- 核對改為不帶 body 的 POST；
- state 型別改用新欄位；
- 調整 `LocalPublishingWorkspace.tsx:315` 與 `PagesSharePanel` 的雙語文字，繁中與英文要等價。

**步驟 5：測試**
- 按 §3.5 刪除或改寫，並補足以下案例：
  - 決定性（步驟 1）；
  - 核對：相符 → verified；manifest 不符 → 失敗並清空；entrance 雜湊不符 → 失敗；
  - 拒絕：非設定的 origin、HTTP、redirect、超過大小、逾時、非 200、錯誤 content-type；請求不帶 credentials；
  - 核對期間 URL 被改掉時，不寫入 verified；
  - 匯出 GET：需 session，沒有副作用（呼叫前後 state 相同），標頭正確；
  - PUT 與 verify 需 CSRF；
  - 繁中與英文 UI。

**步驟 6：閘門（全部執行，結果如實回報）**
- Python：
  - `pytest --basetemp=<可寫目錄>`
  - Ruff format／check
  - mypy
- Web：
  - format、lint、tsc、單元測試、production build
  - visitor source guard（`scripts/check_visitor_source.mjs`）
  - registry 檢查
- Docker／Compose 2 個 smoke。
- 以原生瀏覽器重跑「原生 ZIP 下載」項目。
  - **假設**（尚未驗證）：原本 20 秒下載事件逾時的原因是 POST→Blob 連結，改用原生 `<a download>` 後應該會消失；
  - 結果請記錄到 `release-evidence/a5/`。

**步驟 7：交回**（§11 的批次全部完成後才執行；一份報告涵蓋 Pages 與 §11）

**已完成（2026-10-03）：** [總交接](../release-evidence/a5/simplification-handoff-2026-10-03.md) 包含需求／AC、逐批實測刪除量、最終閘門、限制與下一步；新 current-state-2026-10-03 記憶為 START HERE。沒有 commit。

- 依 `AGENTS.md` §7 撰寫最終報告；
- 更新專案記憶 `current-state-*.md`；
- **不要 commit**，由擁有者決定。

---

## 8. 其他審查發現（這次不做，列入 Deferred）

1. **`src/RepoNPC/admin/scene.py`（1405 行）**
   - 內含一套自己的發布生命週期：revision、`_recover_unlocked`、recovery backup、`write_presentation_receipt`（`local_publication.py:42/210` 也引用）、`_trim_receipts`、`_atomic_content_addressed`。這與 `admin/local_publication.py` 既有的生命週期平行，疑似重複。
   - 這次不動。合併前要先查清楚它存在的原因（Chesterton's fence）：看呼叫者、測試、git 歷史。
   - 觸發條件：下一次需要修改 scene 發布流程的時候。
2. **`apps/web/src/app/visitorData.ts`（980 行）**
   - 對網站自己同源匯出的資料做了大量手寫驗證，並在瀏覽器內重新算 sha256（`readStaticManifest`、`validateStaticManifest`、`sha256`）。
   - 建議保留基本結構驗證，移除重新雜湊。下次修改這個檔案時順便處理。
3. **`pages_transport.py` 的 DNS／TLS pinning 細節**
   - 屬於邊界，所以保留。
   - 觸發條件：要改傳輸行為時，再評估標準 HTTP client 加上連線後 IP 檢查是否足夠。
4. **「本機內容已在核對後變更」的 UI 提示**
   - 擁有者提出時，可在 state 讀取時比對目前 manifest 雜湊與 `verified_content_sha256`；**不要恢復收據**。
5. **A1–A4 與未提交 A5 FAQ 的同類審查**
   - 見 [A1_A4_COMPLEXITY_AUDIT_2026-10-02.md](A1_A4_COMPLEXITY_AUDIT_2026-10-02.md)。擁有者已於 2026-10-02 全部核准，**已移入本交接範圍**，執行方式見 §11。

---

## 9. 流程規則（避免再長回來）

- 這次的複雜度來自審查循環：每輪審查找到一個競態，就加一個概念來修，並寫進契約，於是暫時的複雜度被凍結成規格。之後的修正應遵守：
  - 一個發現先問「沒有這一層，這個問題還會存在嗎？」；如果答案是不會，就刪掉那一層，不要再加防護。
  - 契約只寫外部行為，不寫鎖順序、時間戳精度或欄位比對這類實作細節。
  - 每批工作外部審查最多 3 輪。同一類發現出現兩次，就升級成設計決策，交給擁有者。
  - 審查者新增的需求屬於範圍變更，不是 bug。
- 正面先例：離線 FAQ 的決策 B 把約 200 行的模糊比對換成 69 行的精確比對（`apps/web/src/app/offlineFaq.ts`）。
- **凍結令：** 不要在 `src/RepoNPC/sharing/`、scene 發布路徑、訪客閘道驗證與 FAQ 審核流程上新增任何收據、指紋、epoch、revision 或競態修補。

## 10. 不要做的事

- 不要在未獲核准前修改端點、migration、錯誤碼或契約。
- 不要刪除或弱化 §5.6 列出的任何邊界。
- 不要刪除任何資料庫或擁有者資料目錄。
- 不要 commit、push、上傳 Pages 或啟用 Funnel。
- 不要用新的收據、快取或 revision 來「修」簡化後出現的問題；先回到 §4 的根因判斷。
- 不要把 `test_a5_pages_transport_review.py` 和 secret scan 相關測試當成收據測試一起刪掉。

---

## 11. 已核准的追加範圍：A1–A4 與未提交 A5 FAQ（2026-10-02）

擁有者已核准 [A1–A4 審查](A1_A4_COMPLEXITY_AUDIT_2026-10-02.md) §6 的全部項目，包括審查原本建議延後的 A1-4、A4-4、A4-5。審查中標為「內部」的項目不改變外部契約，一併納入。證據見審查文件。下列行號以 2026-10-02 的工作區為準，動手前請以符號名稱重新定位。

### 11.1 共同規則

- **順序：** 先完成 §7 步驟 0–6（Pages），再依 B1→B5 執行。
  - 每一批獨立完成：先改文件，再改程式，再改測試，最後跑 §7 步驟 6 的閘門，加上該批列出的額外閘門。
  - 前一批的閘門沒通過，不開始下一批。
- **每批交付內容：**
  - 刪除清單：刪了哪些函式、欄位、錯誤碼、測試，各約幾行；
  - 根因層一句話；
  - 新增概念預算表。預期為空；如果不得不新增，先停下來問擁有者。
- **已出貨的 migration（29、30）不改寫。** 用不到的欄位保留不用，也不新增 migration 去刪欄位。未提交的 migration 31–33 可以改寫（33 的處理見 §7 步驟 0）。
- **遇到下列情況，停下來問擁有者：**
  - 實作時發現本節沒寫到的外部行為變化；
  - 需要新的錯誤碼或欄位；
  - 任何邊界必須放寬（§5.6，以及審查文件各節的「保留」清單）。
- 繁中與英文行為保持等價。文件以 UTF-8 寫入，並確認沒有 U+FFFD。

### 11.2 B1：未提交的 A5 FAQ 層與雙 resolver 欄位（沒有 migration 成本）

**2026-10-02 完成：** B1 文件、程式、測試及全部本機閘門通過。應用程式淨減 56 行；測試淨增 75 行，補上雙語一致快照、拒絕寫入與雙 resolver 計數邊界。Python 1,677 通過／2 Windows 略過、Web 完整閘門、Docker 2、雙語原生 ZIP 與 23 個 manifest 記錄核對通過。刪除清單、概念預算及完整命令見 [B1 證據](../release-evidence/a5/b1-simplification-2026-10-02.md)。下一批 B2；B2–B5 與整體步驟 7 尚未完成。

| 項目 | 做法 |
|---|---|
| `content_fingerprint`（`admin/faq.py:376`） | 刪除。匯出改在同一個讀取交易內取得 FAQ 快照，競態就不存在。 |
| variants 三重驗證 | 保留寫入時的驗證與 migration 32 的 `CHECK`／`json_valid`。刪除讀取時（`public_payload_for_bundle` 等）的重新驗證、`FAQ_VARIANTS_INVALID` 與 `LIMIT 257/513`。同步修改 `docs/A5_VISITOR_APPEARANCE_EXPORT_CONTRACT.md`。 |
| `replace_variants` | revision 與 bundle 各只檢查一次，放在條件式 UPDATE 的 WHERE 裡。 |
| `OFFLINE_FAQ_MATCHER`（`faq.py:43`）與匯出的 `matcher` 物件 | 刪除。靜態站的版本由 manifest 的 `schema_version` 承擔。同步刪除 `apps/web/src/app/visitorData.ts:199-202` 的 `matcher` 檢查與 `publicTypes.ts:78` 的型別，並更新 `docs/A5_HANDOFF_2026-09-30.md` 的描述。 |
| `language`／`stars`／`forks` 雙實作 | `indexing/github.py` 的 `_optional_repository_count` 與 `admin/batch_resolver.py` 的 `_optional_github_count` 合併成一個共用函式，兩個 resolver 都呼叫它。 |

額外閘門：靜態匯出測試、離線 FAQ 的 Web 測試、visitor source guard。

### 11.3 B2：A2 回答政策（A2-1b、A2-4、死碼、政策資料）

**完成（2026-10-03）：** 單一 v2 驗證入口，移除 v1、代名詞改寫與不可達檢查；14 筆品質評估改走正式路徑並全數通過。應用程式淨減 420 行；Python 1682 pass／2 skip、Web 388／38、Docker 2 pass 及雙語原生 ZIP 下載通過。完整證據：[B2 報告](../release-evidence/a5/b2-simplification-2026-10-03.md)。

1. **完全移除 v1 封包（A2-1b，取代審查的 A2 #1、#2）。**
   - 刪除下列項目：
     - `validate_answer` 的遺留路徑與預設的 `allow_legacy=True`；
     - `_looks_like_v2`、`_validate_legacy_envelope`、`_validate_legacy_project_adapter`；
     - `_PERSON_CLAIM_RE` 與它的停用詞；
     - `_owner_assertion_supports`、`_claim_terms`；
     - 只被上述函式使用的 helper（例如 `_abstention`，刪除前先確認呼叫者）。
   - 只保留一個驗證入口：`validate_v2_answer`，或把它改名為 `validate_answer`。二擇一，全專案一致。
   - 保留未提交的 `discarded_segments`（`admin/faq.py` 正在使用）。
   - 文件：
     - 刪除 `docs/TECHNICAL_SPEC.md` §8.1 的「The v1 envelope below is accepted only through a legacy adapter…」與其後的 v1 範例；
     - 刪除 `docs/COMPLETION_DIRECTION_CONTRACT_2026-09-26.md` 第 75 行的 legacy adapter 條文。
     - 答案不落地儲存，所以**沒有資料要遷移**。
   - **評估必須改寫：**
     - `tests/eval/test_chat_answer_quality.py` 的 14 筆 v1 `answer_markdown` 夾具改寫為 v2 segments，並改為呼叫正式的驗證入口。
     - 重跑評估，結果記錄到 `release-evidence/`。
     - 這是本批最重要的產出：目前的品質關卡量的並不是正式路徑。
   - `tests/unit/test_answer_validation.py` 中測試舊人物主張規則的案例（約第 40–160 行）刪除或改寫成 v2。
2. **移除代名詞改寫（A2-4）。**
   - 刪除 `_normalize_owner_references`（`chat/answers.py:767`）與它的呼叫點：`:319`，以及 `:570`（後者隨 v1 一起刪除）。驗證與渲染直接使用模型原文。
   - `person` 段沒有 `{{owner}}` 時，仍以 `OWNER_REFERENCE_MISSING` 丟棄。規格本來就要求模型輸出 `{{owner}}`。
   - 保留「`project`／`inference` 段含人物指涉時重分類為 `person`」。這是邊界：防止專案段夾帶沒有依據的人物主張。
   - **只刪改寫還不夠。** 含 they/our/we 的專案段仍會被重分類，然後被丟棄。所以要修改參考詞清單，保留單數第一、第三人稱與身分詞：
     - `chat/policy/person_reference.en.yml` 刪除 `we`、`our`、`us`、`they`、`them`、`their`；
     - `person_reference.zh-TW.yml` 刪除 `我們`、`他們`。
   - 新增測試：
     - README 式的英文與繁中專案敘述（含 we/they/我們/他們）保留為 `project`；
     - "his work" 這類文字不再被改寫成「名字 work」；
     - 單數人物指涉仍會被重分類。
     - AC-064 原有案例全數通過。
3. **死碼：**
   - 要刪的項目：
     - `_valid_v2_segment`；
     - `_SEGMENT_DROP_REASON_CODES`；
     - `PROJECT_OWNER_REFERENCE` 的不可達條件；
     - 推論段的 `OWNER_NAME_MISSING` 分支與落空分支；
     - 已由 `min_length=1` 保證的 `not evidence` 檢查。
   - 刪除前先以測試確認這些路徑確實不可達。
4. **政策資料：**
   - 刪除 zh-TW 的無效排除詞「開發工具」「這個專案實作了」，兩者都不含任何參考詞。
   - `tests/unit/test_answer_policy.py:30` 改成斷言這兩句不被視為人物指涉（測行為，不測資料內容）。
   - YAML 的 `version: 1` 沒有人讀取，刪除。
   - `person_reference` 與膨脹 `role` 群組的重疊**保留**，兩者用途不同。

額外閘門：retrieval／answer-quality 評估；`test_chat_grounding_security.py` 全數通過。

### 11.4 B3：A3 參與事實（A3-2 與內部項目）

**已完成（2026-10-03）：** 明確傳入 collector，移除隱含轉送、重複 unavailable 與未讀取 metadata；沒有 collector 與 unavailable 分開驗證。全 Python 1685 passed／2 skipped、Web 388 passed、Docker 2 passed、雙語原生 ZIP 下載通過。應用程式淨增 32 行（保留取消與期限邊界的明確配線），詳細清單與證據見 [B3 完成紀錄](../release-evidence/a5/b3-simplification-2026-10-03.md)。

1. **明確傳遞參與收集器（根因修正）。**
   - `build_index_bundle` 新增一個明確的參數，接收參與收集器。
   - 刪除下列三處：
     - `indexing/pipeline.py:145` 的 `getattr(source_resolver, "participation", None)`；
     - `admin/embedding_reindex.py` 的 `_BoundedResolver.participation` 轉送；
     - `admin/local_publication.py` 另外串接的 `participation_resolver`。
   - 「沒有收集器」與「API 失敗」必須可以區分：
     - 沒有收集器時，不產生參與證據；
     - API 失敗時，記為 unavailable（`None`，絕不記為 0）。
   - 改寫 `test_local_publication.py:144`，它目前鎖住的是兩者混淆的行為。
2. **停止寫入 `participation:{slug}` bundle_meta（A3-2）。**
   - 刪除 `indexing/index_database.py:366-371`，以及 `tests/integration/test_index_build.py:183` 的斷言。
   - 舊 bundle 仍帶這個鍵；沒有人讀取它，所以無害。
   - 先確認 bundle 驗證沒有列舉 meta 鍵；如果有，一併更新。
3. **重複的 unavailable 備援：** 刪除 `index_database.py:354-363` 的第二份。
4. **引導流程的佔位登入：** `admin/onboarding.py:1039` 的 `"reponpc-onboarding"` 不應產生 PARTICIPATION 列。改成沒有真實登入時不收集參與資料。

額外閘門：bundle build、validation、activation、rollback 測試。

### 11.5 B4：A4 FAQ 審核（A4-1、A4-3、A4-4、A4-5、內部項目）

**已完成（2026-10-03）：** 改用既有貢獻編輯器與一般生成，移除 rewrite 協定、續接輪詢與訪客選取時重查；revision CAS、bundle 檢查與公開安全投影保留。完整 Python 1686 passed／2 skipped、Web 388 passed、Docker 2 passed、原生 FAQ 19 項與雙語 ZIP 通過。應用程式淨減 469 行、測試淨減 48 行（Web .test. 歸入測試），見 [B4 完成紀錄](../release-evidence/a5/b4-simplification-2026-10-03.md)。

1. **改寫流程改用既有的編輯器（A4-1；A4-3 隨之消失）。**
   - 新流程：
     1. FAQ 面板的「改寫為擁有者陳述」改為呼叫既有的缺口捷徑：開啟貢獻編輯器，預選 repository 與 claim kind，讓擁有者新增雙語的擁有者陳述（`docs/A4_COVERAGE_FAQ_IMPLEMENTATION.md`「Owner flow」第三段已有這個捷徑）。
     2. 擁有者存檔、準備發布。
     3. 新 bundle 啟用後，該項目在讀取時自動顯示「需要重新確認」。
     4. 擁有者按「重新生成」走一般管線，然後審核。
   - 刪除下列項目：
     - `POST /api/admin/portfolio/faq/{id}/rewrite`。`expected_draft_revision` 只存在於它的請求體，所以 A4-3 一併完成。
     - rewrite association 的寫入與讀取。
     - `required_claim`／`excluded_bundle_id`：從 `admin/faq.py:134-137` 到 `chat/service.py:100-154`，含 `:160-174` 重做的融合上限。
     - `index_reader.owner_claim_evidence`。
     - `FAQ_REWRITE_NOT_INDEXED`、`FAQ_CONTEXT_INSUFFICIENT`。
     - 前端的「繼續」動作，以及 `CoverageFaqPanel.tsx` 的 180 秒輪詢。
     - 對應的測試：`tests/integration/test_reviewed_faq.py` 與 `tests/security/test_reviewed_faq_security.py` 中的 rewrite 案例。
   - `rewrite_json` 欄位屬於已出貨的 migration 29：保留欄位但不使用，寫入 NULL，讀取時忽略既有值。「rewrite-pending 不可核准」規則隨之刪除。
   - 文件：
     - 改寫 `A4_COVERAGE_FAQ_IMPLEMENTATION.md` 的 Owner flow 第四、五段、HTTP 表格與錯誤碼段；
     - `docs/TECHNICAL_SPEC.md:291` 刪除「actual indexed-claim rewrite continuation」；
     - `docs/SECURITY.md:38` 刪除 rewrite 路由，以及「Rewrite generation requires the saved claim ID…」這一句。
     - FR-046 與 AC-067 的文字不需修改：「存成 claim 再重新生成」與「轉成擁有者陳述會建立 `OWNER_ASSERTION` 草稿」仍然成立。
   - 語意變化：重新生成**不保證**會引用新的陳述，由擁有者審核時判斷。請在 UI 說明文字中寫清楚。
2. **`_MUTATION_LOCK`（`faq.py:48`）：**
   - 隨第 1 項移除。其餘的寫入靠 `revision` 條件式 UPDATE 保護。
   - 既有的並發 review／regenerate 測試要保留並通過。
3. **`/review` 移除 `bundle_id`（A4-4）：**
   - 請求體改為 `{revision, action}`。
   - 伺服器以列上的 `bundle_id` 對照目前的 bundle，不符時回 `FAQ_STALE`。
   - 前端停止送出這個欄位；更新契約的 HTTP 表格。
4. **移除訪客晶片的重新檢查（A4-5）：**
   - 刪除下列項目：
     - `apps/web/src/app/VisitorApp.tsx` 的 `currentApprovedFaq`、`faqSelectionController`、`faqSelectionPending`；
     - `publicTypes.ts:110` 的 `faqSelectionPending`；
     - 對應的測試夾具。
   - 選擇晶片與離線比對直接使用隨 profile 載入的 FAQ，保留本地的 `bundle_id` 對 `profile.index.version` 檢查。
   - 語意變化：工作階段中途被撤回的核准，要等訪客重新載入才會消失。
   - 文件：`A4_COVERAGE_FAQ_IMPLEMENTATION.md`「Visitor use」第一段、`docs/SECURITY.md:38` 最後一句。
5. **小項：** 公開查詢的多餘條件（`faq.py:292`）。

額外閘門：FAQ API 測試、匯出測試、雙語瀏覽器測試、`scripts/check_visitor_source.mjs`。

### 11.6 B5：A1 訪客閘道（A1-1、A1-4、內部項目）

**已完成（2026-10-03）：** verified_at/listener 取代 epoch／association，訪客不讀寫擁有者閘道設定；嚴格來源與 heartbeat 聊天共用，身分、投影、額度、取消／期限與閘道禁止重試保留。Python 1703 passed／2 skipped、Web 388 passed、Docker 2 passed、原生面板 11 項與雙語 ZIP 通過。應用程式淨減 243 行、測試／harness 淨增 177 行，見 [B5 完成紀錄](../release-evidence/a5/b5-simplification-2026-10-03.md)。

1. **驗證縮成單一 `verified_at`（A1-1）。**
   - **請求：**
     - `POST /api/admin/visitor-gateway/verify` 的請求體改為 `{revision, external_checks_confirmed: true}`。
     - 刪除 `GatewayVerificationRequest` 的 `gateway_origin`、`pages_origin`、`bundle_id`。
     - 監聽器未就緒時，回既有的 `GATEWAY_UNAVAILABLE`。
     - 設定已變更時，由既有的 `revision` 檢查回 `GATEWAY_CONFLICT`。
   - **寫入：**
     - migration 30 對 5 個 `verification_*` 欄位有「全空或全填」的 CHECK，所以仍一次寫滿：取當下的設定與 bundle，`verification_method='owner_reported'`。
     - 但**只讀 `verified_at`**，不再拿其他欄位做比對。
     - 不新增 migration。
   - **清空：**
     - 設定、啟動、停止、恢復與程序重啟時，在同一筆寫入中把 5 欄設為 NULL。這符合 ADR-053 的「dated external verification cannot resume from persisted state」。
     - bundle 啟用時**不清空**，與 Pages §5.3 的語意相同。
   - **顯示：** `external_verified = verified_at is not None and listener_ready`。
   - **刪除：**
     - `api/visitor_gateway.py` 的 `_observation_epoch`、`matching_report` 比對；
     - `observe_state`／`_observe`，以及 `main.py:1549` 的呼叫；
     - 存檔競態的 epoch 檢查；
     - `GATEWAY_VERIFICATION_STALE`；
     - `VisitorGatewayPanel.tsx` 的 9 欄 `checklistKey`；
     - `tests/integration/test_visitor_gateway_lifecycle.py` 與 `tests/security/test_visitor_gateway_review.py` 中測試 epoch／stale 的案例（約 5 個）。
   - **新測試：** 改為測「變更時清空」與「未就緒時拒絕」。
   - **文件：**
     - `docs/A1_FUNNEL_GATEWAY_CONTRACT.md` §3、§4、§8、§10；
     - `docs/DECISIONS.md` 的 ADR-053，若提到觀察比對則同步修改；
     - `docs/ACCEPTANCE_CRITERIA.md` AC-071 的「stale revisions」維持不變（revision 檢查仍在）。
2. **不再於每個訪客請求重讀設定（內部）。**
   - `create_visitor_gateway_app(settings_supplier=self.snapshot)` 改為在建立 app 時傳入固定的 `pages_origin`。閘道執行中，`_configure` 本來就拒絕變更來源。
   - 確認訪客請求路徑不再讀 SQLite，也不再改變任何擁有者狀態。
3. **合併兩個來源正規化函式（內部，安全邊界）。**
   - `config/environment.py:274 _canonical_origin` 與 `api/admin.py:3480 _normalized_origin` 合併成一個，連同 `_strict_url_origin`／`_https_origin` 這兩個包裝。
   - 先寫一張表，列出兩者的規則差異，取較嚴格者。
   - 補齊安全測試：大小寫、預設埠、尾斜線、userinfo、IDN、IPv6、非 https。
4. **合併聊天處理器（A1-4）。**
   - 先列出閘道的 `chat`（`api/visitor_ingress.py`，約 185 行）與 `public.chat_stream` 的所有差異：錯誤碼、SSE 事件、心跳、限流身分、取消。
   - 合併成一個處理器：以參數傳入投影與錯誤對照，兩條路徑都使用心跳版本。
   - 對外行為以 A1 契約 §7 凍結的閘道版為準。
   - 身分與限流的差異屬於邊界：保持參數化，不得統一放寬。
   - 更新 A1 契約 §7，以及 `docs/TECHNICAL_SPEC.md` 的本機公開錯誤碼清單。
   - 某項差異無法判斷該取哪一邊時，停下來問擁有者。
5. **小項（內部）：**
   - 刪除無用的 `admin_origins` 參數（`visitor_ingress.py:352,364` 直接 `del`）。
   - `_started_*` 改為正式屬性。
   - 合併重複的 snapshot 備援 dict。
   - 評估 `allow_retry`／`generate_once` 是否已被截止時間涵蓋；涵蓋的話就刪除。
6. **不做：** 把自寫的 CORS 改用 Starlette。被拒的 preflight 會從 404 變成 400，價值低。

額外閘門：
- 閘道安全回歸：編碼、大小寫、斜線、未知方法、偽造身分、憑證拒絕、CORS；
- Docker／Compose 2 個 smoke；
- 閘道面板的瀏覽器測試。

**不得**啟用 Funnel，也不得做外部連線測試。

### 11.7 預期刪除量（審查估計）

| 批次 | 程式碼（約） | 測試（約） |
|---|---|---|
| B1 | −150 | −80 |
| B2 | −330 | −150（評估夾具改寫另計） |
| B3 | −60 | −45 |
| B4 | −500 | −250 |
| B5 | −450 | −200 |

實際數字寫進每批的刪除清單。如果某批淨增加行數，請在報告中說明原因。

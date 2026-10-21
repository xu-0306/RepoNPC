# A1–A4 過度複雜化審查（2026-10-02）

**狀態：** 唯讀審查結果，尚未修改任何程式碼。專案擁有者已於 2026-10-02 核准 §6 全部項目，執行範圍與順序見 [A5 交接文件 §11](A5_PAGES_SHARING_SIMPLIFICATION_HANDOFF_2026-10-02.md)。標示「需核准」的項目會改變端點、請求欄位、錯誤碼、規格文字或訪客可見行為，依 AGENTS.md §3 必須先由專案擁有者決定。標示「內部」的項目不改變外部契約，可直接排入實作。

**配套文件：** A5 Pages 收據簡化見 [A5_PAGES_SHARING_SIMPLIFICATION_HANDOFF_2026-10-02.md](A5_PAGES_SHARING_SIMPLIFICATION_HANDOFF_2026-10-02.md)（擁有者已核准選項 1）。

**方法：** 每個里程碑比較「成熟系統的同類功能需要幾個概念」與「實際新增的概念」，並把每一層分類為「邊界」（限制能發生什麼，保留）或「衍生層」（重述系統已知的事，是嫌疑）。每項主張都已回到檔案行號抽查。

## 0. 總覽

| 里程碑 | 嚴重度 | 主要問題 | 是否有 A5 式「收據層」 |
|---|---|---|---|
| A1 Funnel 訪客閘道（`302e3de`） | 中 | 外部 Funnel 檢查的「驗證」綁定閘道即時狀態，靠 epoch／觀察掛勾維持 | 有（縮小版） |
| A2 回答政策 v2（`3132a9d`） | 低–中 | 已被取代的 v1 驗證器仍活著，且品質評估量的是它而不是正式路徑 | 無 |
| A3 參與事實（`1e82ee8`、`cf948f8`） | 低 | 參與資料靠 duck-typed `getattr` 可選方法傳遞，缺能力與 API 失敗無法區分 | 無 |
| A4 覆蓋檢查／FAQ 審核（`b80422d`） | 低–中 | 「改寫為擁有者陳述」做成第二條強制續接生命週期 | 無（重新確認是讀取時計算） |
| A5 未提交的 FAQ 部分 | 中（但現在修最便宜） | 與 Pages 收據同型的指紋、三重驗證 | 有 |

結論：A2–A4 沒有 A5 那種「每輪審查加一個概念」的失控，核心都合理；A1 有一個縮小版的收據層（§1 #1）。可刪的重量集中在：遺留／死碼、重複的生命週期、以及 duck-typed 傳遞。

## 1. A1 Funnel 訪客閘道

**參考：** 成熟做法約 16 個概念：第二個只綁 127.0.0.1 的 uvicorn app 加公開路由允許清單、單一來源且不帶憑證的 CORS、Host/路徑/憑證拒絕中介層、只信任 loopback 的 `X-Forwarded-For`、既有限流、帶心跳的 SSE、`{enabled, origins, verified_at}` 設定列、啟停端點、管理介面 Host/Origin 綁定。A1 實際約 38 個概念；約七成是必要的邊界。

**規模：** `api/visitor_ingress.py` 620 行、`api/visitor_gateway.py` 571 行、`runtime/visitor_gateway.py` 136 行、`VisitorGatewayPanel.tsx` 690 行；5 個端點、10 個資料庫欄位、7 個以上錯誤碼；「verif」出現 119 次、「revision」90 次。

**保留（信任邊界，參考沒有但有理由）：**
- 原始路徑／Host／憑證／方法允許清單，不符一律 404（`visitor_ingress.py`）。
- 只對 Pages 來源開 CORS、不帶 credentials、移除 Set-Cookie。
- 訪客身分只信任 loopback 來的 `X-Forwarded-For`，否則併入總量計數。
- 有真截止時間的 body 上限與 `VisitorChatWorkers`：Python 執行緒殺不掉，名額要等執行緒真的結束才釋放。
- Vite manifest 閉包，確保管理介面 bundle 不會出現在訪客端。
- 獨佔埠綁定、僅正式環境的驗證、主機名分離、`PrivateOriginRoute` 與管理主機 404。
- 不含 provider／用量欄位的狀態／SSE 投影。

**刪除／合併候選：**

1. **外部檢查的「驗證」綁定閘道即時狀態（衍生層；需核准，約 −300 程式碼／−150 測試行）。** 這是 A5 收據問題的縮小版。
   - 位置：`runtime/visitor_gateway.py` 的 5 個 `verification_*` 欄位（migration 30）；`api/visitor_gateway.py` 的 `_observation_epoch`、`matching_report` 比對、`observe_state`／`_observe` 掛勾（`main.py:1549` 呼叫）與存檔競態的 epoch 檢查；嚴格的 verify 請求體、`GATEWAY_VERIFICATION_STALE`；`VisitorGatewayPanel.tsx` 的 9 欄 `checklistKey`；約 5 個測試（皆已核對）。
   - 來源：原始需求沒有。A1 契約第 412 行「stale readiness, verification-save races」與 `release-evidence/a1/local-checks.md` 顯示是審查修正一輪輪加上去的。
   - 反事實：只留一個 `verified_at`，設定／啟動／停止／恢復時在同一筆寫入中清空；畫面顯示 `verified_at 且 listener_ready`。契約本身已稱之為「有日期的擁有者觀察，不是監控」，AC-071 也把外部 Funnel 檢查列為發布證據而非即時徽章。存檔競態只因驗證綁定觀察狀態才存在。
   - 影響：schema、verify 請求體、錯誤碼與 ADR-053 文字都要改。migration 30 已出貨，多餘欄位保留不用，或另加 migration 移除。
2. **每個訪客請求都重讀設定（衍生層；內部，約 −20 行）。** `create_visitor_gateway_app(settings_supplier=self.snapshot)`，`snapshot` 讀 SQLite、bundle 狀態並呼叫 `_observe`。結果是公開流量會改變擁有者的驗證狀態。閘道執行中 `_configure` 拒絕變更來源，所以來源在 app 生命週期內固定，建立 app 時擷取一次即可。
3. **兩個來源正規化函式（安全邊界上的重複；內部，約 −30 行，需補安全測試）。** `config/environment.py:274 _canonical_origin` 與 `api/admin.py:3480 _normalized_origin` 規則略有不同，另有 `_strict_url_origin`／`_https_origin` 包裝。合併成一個。
4. **分叉的聊天處理器（部分是邊界；需核准）。** 閘道的 `chat`（約 185 行）與 `public.chat_stream` 錯誤碼不同。合併成一個帶投影／錯誤對照參數、共用心跳的處理器，約 −100 行；本機公開錯誤碼與 SSE 行為會變，風險中。
5. **自寫 CORS（低價值）。** 可改用 Starlette `CORSMiddleware`，約 −35 行，但被拒的 preflight 會從 404 變成 400，測試要改。建議不做。
6. **小項（內部，約 −40 行）。** 無用的 `admin_origins` 參數（`visitor_ingress.py:352,364` 直接 `del`，已核對）；`_started_*` 屬性臨時設定再用 `getattr` 讀；重複的 snapshot 備援 dict；可選：`allow_retry`／`generate_once` 管線（截止時間已限制重試）。

**未提交工作：** A5 對 A1 檔案約 +38 行（`visitor.html`、`scene-mode.js`、伺服器端訪客文件渲染、`scene_supplier`），是一層中等的 HTML 改寫，沒有再加驗證式的層。

## 2. A2 回答政策 v2

**參考：** 一般有依據的回答系統約 5 個概念：帶來源 ID 的 claim schema、ID 必須屬於已檢索來源、丟棄無引用 claim、伺服器組 URL、無匹配回覆。A2 約 10 個概念，多出的（segment kind 對應證據類別、`{{owner}}`、膨脹詞表、數字檢查）都能追溯到 FR-043/044，比例合理。

**保留（信任邊界或規格要求）：**
- 整份拒絕的封包完整性檢查（`chat/answers.py:285-305`）：嚴格 schema、URL/HTML/標記禁止、未知或未選取的來源 ID、推論循環。
- 各 kind 的證據類別規則（`answers.py:366-391`）。
- 數字檢查（`answers.py:830-906`），中文數字解析是契約 §1.7 要求。
- 膨脹詞檢查（約 30 行程式碼加 YAML 資料）。
- 固定的擁有者專用原因碼日誌與伺服器端引用建構。

**刪除／合併候選（依重要性）：**

1. **已被取代的 v1 驗證器仍經由公開的 `validate_answer` 存活（內部，但需重寫評估資料）。**
   - `validate_answer` 預設 `allow_legacy=True`（`answers.py:183,191`）；正式路徑只用 `validate_v2_answer`（`chat/service.py:207,254`，已核對）。
   - `tests/eval/test_chat_answer_quality.py:174,230` 自稱評估「正式驗證器」，實際把 14 筆 v1 `answer_markdown` 餵進遺留路徑（已核對）。**品質關卡量的不是會出貨的東西**，這是 A2 最重要的發現。
   - 可刪：`_validate_legacy_envelope`、`_PERSON_CLAIM_RE` 與停用詞、`_owner_assertion_supports`、`_claim_terms`、只為路由存在的 `_looks_like_v2`（約 150 行）。規格 §8.2 已宣告此行為被取代。
   - 代價：評估夾具改寫為 v2 並重跑證據。
2. **轉接器重複 v2 主迴圈（內部）。** `answers.py:559-600` 複製 `307-352`。改成把 v1 每行轉為 `AnswerSegment(kind="project")` 後呼叫 `_validate_v2_envelope`，約 −45 行。
   - 進一步完全移除 v1（約 −290 行）會改規格 §8.1 與契約 §1.3 → **需核准**。答案不落地儲存、schema 已強制 v2，所以沒有資料要遷移。
3. **死碼（內部，約 −35 行）。** `_valid_v2_segment`（`answers.py:407`）零呼叫者；`_SEGMENT_DROP_REASON_CODES`（`answers.py:80`）未使用（兩者皆已核對）；`PROJECT_OWNER_REFERENCE`、推論的 `OWNER_NAME_MISSING` 分支與 `answers.py:404` 的落空分支不可達。
4. **先把代名詞改寫成 `{{owner}}`，再要求必須有 `{{owner}}`（需核准，訪客措辭會變）。** `_normalize_owner_references`（`answers.py:767`）加 `OWNER_REFERENCE_MISSING` 是「預測再把關」：
   - 規格只要求模型輸出 `{{owner}}`，沒有要求改寫。
   - 副作用：英文 "his work" 會變成 "Alice work"；README 式專案文字中的 they/our/we 會被重分類為人物主張然後被丟棄，正是 AC-064 要消除的那類誤判的英文版。
   - 改為只偵測不改寫，約 −40 行，風險中。
5. **為測試字串擬合的政策資料（內部，瑣碎）。** zh-TW 排除詞「開發工具」「這個專案實作了」不含任何參考詞，只是因為 AC-064 列出、`test_answer_policy.py:30` 鎖住；YAML 的 `version: 1` 無人讀取；四個英文 `person_reference` 詞與膨脹 `role` 群組重複。

## 3. A3 參與事實

**參考：** 三次 GitHub REST 呼叫即可完成；A3 額外概念約為參考的 1.3 倍，合理。

**保留：** 連結登入檢查、取不到時記為 `None`（絕不記 0）、不存計數、以 SHA 驗證的 permalink、取消與截止時間處理、設定驗證器、`_last_page` 的 URL 驗證（驗證不受信任的輸入）。

**刪除／合併候選：**

1. **`cf948f8` 的根因：參與資料是 duck-typed 可選 resolver 方法（衍生層；內部，低風險）。**
   - `indexing/pipeline.py:145` 用 `getattr(source_resolver, "participation", None)` 取代 `isinstance`；`admin/embedding_reindex.py:463-469` 加了轉送用的 `_BoundedResolver.participation`；`admin/local_publication.py:119,124,188,331` 另外串第二個 `participation_resolver`（皆已核對）。
   - 缺少該能力時回傳 `None`，與 API 失敗長得一樣；`tests/.../test_local_publication.py:144` 把這個行為鎖住。
   - 修法：把明確的參與收集器作為參數傳給 `build_index_bundle`。約 src −30／test −35，+10。
2. **寫了沒人讀的 bundle_meta 鍵（內部，但 bundle 內容會變，先告知擁有者）。** `indexing/index_database.py:366-371` 寫入 `participation:{slug}`，唯一讀者是 `tests/integration/test_index_build.py:183`（已核對）。約 −15 行。
3. **重複的 unavailable 備援（內部）。** `index_database.py:354-363` 重做一次備援，約 −10 行。
4. **引導流程的佔位登入（內部，觀察）。** `admin/onboarding.py:1039` 的 `"reponpc-onboarding"` 會產生一筆惰性 PARTICIPATION 列。

**未提交工作的同型問題：** `language`／`stars`／`forks` 分別在 `indexing/github.py`（`_optional_repository_count`）與 `admin/batch_resolver.py`（`_optional_github_count`）各寫一次。底層原因是有兩個 resolver 實作（`GitHubSourceResolver`、`LocalArchiveResolver`），每加一個欄位就要寫兩次。建議在 A5 提交前先合併成一個共用的欄位擷取函式。

## 4. A4 覆蓋檢查／FAQ 審核

**沒有收據層：** `needs_reconfirmation` 是讀取時以 `row["bundle_id"] != active` 計算（`admin/faq.py:437`，已核對），這正是 A5 Pages 應採用的模式。

**規模：** 資料表 `faq_entries`（migration 29，已出貨，16 欄）、5 個擁有者端點加 1 個公開端點、8 個新錯誤碼。

**保留：** 驗證／CSRF（`api/admin.py:1285`）、公開允許清單（`faq.py:26,285`）、失敗處理、`revision` 檢查、租用的 bundle 身分、`coverage_status` 列舉、六題標準題庫。

**刪除／合併候選：**

1. **「改寫為擁有者陳述」做成強制續接的第二條生命週期（需核准，約 −400～450 行）。**
   - FR-046 只要求「存成 claim，然後重新生成」。目前實作另外加了：`rewrite_json`、`required_claim`／`excluded_bundle_id` 一路從 `faq.py:134-137` 傳到 `chat/service.py:100-154`（強制把指定 claim 塞進證據，並在 `:160-174` 重做一次融合上限）、`index_reader.owner_claim_evidence`、錯誤碼 `FAQ_REWRITE_NOT_INDEXED` 與 `FAQ_CONTEXT_INSUFFICIENT`（`api/admin.py:1551-1552`）、前端 180 秒輪詢（`CoverageFaqPanel.tsx:194-233`）（皆已核對）。
   - 薄版：「改寫」按鈕開啟既有的 claim 編輯器並預填題目；擁有者存檔、重建後，項目自動顯示「需要重新確認」，按「重新生成」走一般管線。這仍滿足 FR-046 的「存成 claim 再重新生成」，只是不再保證下一次生成一定引用那條 claim。
   - 影響：移除 `/rewrite` 端點與兩個錯誤碼，需修訂 `A4_COVERAGE_FAQ_IMPLEMENTATION.md` 與 TECHNICAL_SPEC 第 291 行的「actual indexed-claim rewrite continuation」。`rewrite_json` 欄位因 migration 29 已出貨而保留不用。
2. **`_MUTATION_LOCK`（內部，約 −15 行）。** `faq.py:48` 的全域 RLock 主要服務 #1 的續接流程；#1 落地後一起移除，其餘寫入已有 `revision` 條件更新保護。
3. **`expected_draft_revision`（需核准，請求欄位）。** `api/admin.py:287`、`faq.py:242` 與 `store.save` 自己的檢查重複。
4. **`/review` 的用戶端 `bundle_id`（需核准，價值低）。** `faq.py:196`；`revision` 已釘住 bundle。
5. **訪客晶片重新檢查（需核准，訪客可見行為）。** `apps/web/src/app/VisitorApp.tsx` 的 `currentApprovedFaq`／`faqSelectionController`／`faqSelectionPending`，約 70 行加約 118 行測試夾具。
6. **小項：** 公開查詢的多餘條件（`faq.py:292`）。`topic` 欄可推導但已出貨，保留。

**未提交的 A5 FAQ 層（與 Pages 收據同型，現在修最便宜，因 migration 32/33 尚未提交）：**
- `content_fingerprint`（`faq.py:376`，14 欄的 SHA-256，只用於匯出競態檢查）：匯出改在同一個讀取交易內取快照即可。
- variants 被驗證三次：寫入時、migration 32 的 `CHECK`／`json_valid`、讀取時在 `public_payload_for_bundle` 再驗一次（含假的 `FAQ_VARIANTS_INVALID` 與 `LIMIT 257/513`）。保留寫入驗證加資料庫約束即可。
- `replace_variants` 對 revision 與 bundle 各檢查兩次。
- `OFFLINE_FAQ_MATCHER` v2 設定只有一種模式：一個沒人改的設定就是常數。

## 5. 已核准的執行順序

統一依 [主計劃 §7 與 §11](A5_PAGES_SHARING_SIMPLIFICATION_HANDOFF_2026-10-02.md) 執行：Pages 步驟 0–6 → B1（A5 FAQ／共用 helper）→ B2（A2）→ B3（A3）→ B4（A4）→ B5（A1）→ 步驟 7 最終報告。本輪記憶與實作核對結果已存入主計劃 §0.1。

§6 全部項目已核准；本文前段的「需核准」與替代方案保留為審查背景，實際採用方案依主計劃。例如 A2 完全移除 v1，不再實作過渡 adapter；migration 29、30 保留，不另加刪欄 migration。每批仍須附刪除清單、概念預算與驗證結果。

## 6. 需要擁有者決定的項目

| ID | 項目 | 審查建議 | 擁有者決定 | 影響 |
|---|---|---|---|---|
| A2-1b | 完全移除 v1 回答封包轉接器 | 核准 | 已核准 2026-10-02 | 規格 §8.1、契約 §1.3 修訂；約 −290 行；無資料遷移 |
| A2-4 | 移除代名詞改寫，只偵測 `{{owner}}` | 核准 | 已核准 2026-10-02 | 訪客措辭改變；修正 "Alice work" 與 they/our/we 誤判 |
| A3-2 | 停止寫入 `participation:{slug}` bundle_meta | 核准（告知即可） | 已核准 2026-10-02 | 新 bundle 少一個無人讀的鍵 |
| A4-1 | 改寫流程改為「開啟 claim 編輯器 → 重建 → 重新生成」 | 核准 | 已核准 2026-10-02 | 移除 `/rewrite` 端點與 2 個錯誤碼；修訂 A4 實作契約；約 −400 行 |
| A4-3 | 移除 `expected_draft_revision` | 核准 | 已核准 2026-10-02（併入 A4-1） | 請求欄位移除 |
| A4-4 | 移除 `/review` 的 `bundle_id` | 可延後 | 已核准 2026-10-02 | 請求欄位移除，價值低 |
| A4-5 | 移除訪客晶片重新檢查 | 待討論 | 已核准 2026-10-02 | 訪客可見行為改變 |
| A1-1 | 閘道驗證縮成單一 `verified_at`，變更時清空 | 核准 | 已核准 2026-10-02 | schema、verify 請求體、`GATEWAY_VERIFICATION_STALE`、ADR-053 修訂；約 −450 行 |
| A1-4 | 合併閘道與本機公開聊天處理器 | 可延後 | 已核准 2026-10-02 | 本機公開錯誤碼與 SSE 行為改變；約 −100 行 |

## 7. 流程規則

- 每個修正都要先寫「根因層」：問題出在哪一層、拿掉那一層問題是否還在、該層是邊界還是衍生層。
- 衍生層是根因時，最小修正加一筆 Deferred 移除項目是預期結果；不得只修症狀而不登記。
- 不要因為審查意見而新增 fingerprint、receipt、verifier、lease 之類的新概念，除非它對應一個真的發生過的失敗，並寫進預算表。

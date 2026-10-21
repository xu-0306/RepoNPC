# 離線人物歸屬診斷與 Man 七像素修整交接 — 2026-10-03

**後續更新：**擁有者未批准正式schema變更，先要求確認訪客UX，並批准隔離對照。
[訪客報告](../../release-evidence/a7/visitor-ux-comparison-20261003/REPORT.zh-TW.md)已完成24組；
有資料10題完整正確由1題變4題，但候選5題超時、1題引用缺口，因此建議暫不正式整合。
82檢查／四腳本static checks／241檔fingerprint與分析重現通過。以下記錄保留前一輪範圍；
前一輪無model calls不代表後續實驗沒有，後續實際25次本機generation、24次預定輸入。

本輪完成擁有者同意進行的離線診斷及私有素材修整。未變更 application
source、production prompt／schema／lexicon、provider／deadline、oracle、catalog、
公開資產或發布候選；既有 dirty work 完整保留。Approved0.4.8／ADR-055／056
仍適用。沒有 model／GitHub／cloud call、owner runtime 操作或 Git write。

## 本輪完成

- **A7：**獨立合成的 98 案例經既有驗證器診斷，74 符合預期、24 個普通專案
  敘述遭誤判。CJK substring 在自我檢查／自我測試／自我修復／吉他找到單數
  人稱，共八個案例；author／owner／maintainer／employee 技術欄位、列舉與
  資料表描述被雙語 recall reclassification，共16個案例。32個不受證據支持的
  人物正例均被阻擋，六個 anchor／selected-ID 結構案例符合預期。這是
  **AC-064 合成輸入缺陷證據**，不是先前 live labeled-inference 原文的重建或
  原因證明。[診斷與提案](../../release-evidence/a7/offline-attribution-20261003/README.md)。
- **A7 schema review：**沿用既有 wire schema，產出四種 request-local source-ID
  enum 樣本；唯一差異是 `source_ids.items.enum`。驗證 membership、未知 ID
  不在 enum、跨 request 隔離、順序一致、深拷貝及序列化大小。只是可審查資料，
  沒有整合或 provider/schema-compiler 驗證；正式變更依 AGENTS.md §3 待批准。
- **A9：**imagegen 新候選變成948×1659，已拒絕並保存 provenance。擁有者
  **明確批准 Python 精準移除七像素**後，以舊 canonical sheet 為來源移除
  `(64,289..292)`及`(65,289..291)`；其餘114,681像素完全一致、27幀未改動、
  19個 Man／Orange 來源檔未變。256×448／binary alpha／canonical validation
  通過，候選 SHA-256 為
  `a88572ec58ac715c1a933a51025f01915db125b2cea5734153e5856814c8ef35`。
  [私有成果及完整證據](../../release-evidence/a9/seven-pixel-review-20261003/README.md)。
- **A9 重現：**兩份私有建置各23檔（sheet／contact sheet／七GIF／提案YAML／
  13卡片資產）逐位元組一致。最終腳本另在 fresh disposable 目錄重跑，兩份
  receipt、schema 樣本及四次素材建置均一致；沒有覆寫歷史 receipts。

## 已跑檢查

- 既有 answer validation／policy／quality subset：**43 passed**。
- 既有 character preparation／conversion／assets／composer／card subset：
  **76 passed**。
- 三支本輪 owned scripts：Ruff lint、format check、mypy 全通過。
  初次 mypy 的 source-path／locale typing 問題已修正；最後以
  `MYPYPATH=src`及`--follow-imports=silent`檢查。
- [最終重現核對](../../release-evidence/a7/offline-attribution-20261003/verification.json)
  確認六個受保護 production／fixture 檔案與19個原素材檔保持原 hash。

98案例是**診斷**，其中24個 mismatch仍存在；不可寫成98通過。本輪沒有
重跑完整Python／Web／Docker／Windows建置，因 application／發布輸入未變。
先前2613／2skip、Web484／42及Docker2結果保留原 provenance，不冒充本輪重跑。

## 下一步及批准界線

1. 擁有者已收到 source-ID enum 的下一批批准問題；**尚未批准正式變更**。
   擁有者要求先確認實際UX，隔離對照已完成；Root建議先處理超時與引用精確度，
   暫不採用目前候選。若後續批准，先完成 source/schema/provider/context 回歸。
   enum只針對 confirmed invalid-ID violation；不修正缺少anchor、不解決任意
   人物語意分類，也不使模型自動12/12。不要為本輪案例新增 prompt 特例。
2. 人物 recall 修正要保留 identity／單數人稱正例、雙語與安全回歸；已證明的
   compounds可作中央非權威 recall policy 的審查材料，技術欄位語意不能只靠
   另一份短詞表宣稱已解決。任何 trust-model／specified-contract 改動須先批准。
3. **七像素修整已完成**，不必再要求 Python 編輯授權。Man 作者／來源與
   再散布權尚未確認；私有候選不可直接進 production／pack／default／bundle／
   card／export。此前 integration proposal 保留，正式使用時換成本輪候選hash。
4. 模型資格仍9/12，catalog空白；clean Windows／最新binary maintenance、
   真正200%zoom／screen reader／完整互動與外部GitHub／Pages／Funnel仍未完成。
   新79-row候選ledger仍1pass／75not-run／3blocked，未提升任何項目。

範圍：FR-043／044、AC-057／062／063／064 的診斷／審查；FR-015／016／018、
AC-020／021／022 的私有素材準備；ADR-040／043／045／048／055／056。

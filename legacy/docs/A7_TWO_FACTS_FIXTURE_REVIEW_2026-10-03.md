# A7 兩事實測例的題目／oracle 不一致

狀態：擁有者已批准「修正提問，保留判分」（2026-10-03）。ADR-056／OR-030 記錄此 fixture-only 決定；規格維持 Approved0.4.8。下文保存批准前的問題與提案。新完整 suite 的結果與原始 fixture 指紋另存於 `release-evidence/a7/two-facts-correction-20261003/`；不覆寫舊10/12結果。

批准後一次完整重驗：9/12，兩個修正的two-facts案例均通過。另三題未通過原有的人物reference／來源選擇／owner assertion檢查；三個案例超過public預設45s，因此180s adapter suite不建立public期限資格。Catalog保持原有空白；未改production prompt、oracle或validator。

16k／推理開啟後，qwen3.5:9b 的固定12雙語案例為10/12。兩個失敗都是同一 `supported_two_facts` 的中英文版本；模型回答儲存位置並引用S2，但現有oracle要求同時引用S1檢索融合及S2儲存。

現有英文題目是 `Where are immutable evidence and runtime state kept?`，詢問不可變證據與runtime state的儲存位置。S2一個來源已涵蓋此問題。Oracle的另一個必要事實是S1：`The retrieval pipeline combines lexical and vector candidates with reciprocal-rank fusion.`，目前題目沒有詢問它。見 `tests/fixtures/chat/answer_quality_scenarios.json` 的該case，以及新版 `production-9b.json`；先前27b的明確兩部分問題診斷不作正式admission證据。

建議只修正題目，使「兩個事實、兩個正確來源」的既有測試目的明確，保留所有expected claims／source IDs／拒絕規則／12題數量／中英文一致性／全案例通過要求：

- 英文：`How does retrieval combine candidates, and where are immutable evidence and runtime state kept?`
- 繁體中文：`檢索如何合併候選結果？不可變證據與執行階段狀態各自存放在哪裡？`

不加入「每個來源都必須引用」等與一般回答無關的prompt特例，不修改production提示詞或為qwen加分支。若批准，保存原測例與指紋、修正固定fixture及其runner雙語題目，重跑完整12案例與相關評估／安全／contract tests；只有全通過及來源授權／revision完整才考慮catalog。新的suite revision與舊結果分開，不把舊10/12重寫為pass。

另一個選項是保留現有題目與oracle，繼續誠實記錄10/12並保持catalog空白。沒有證據可把此citation coverage失敗改報成安全或推理失敗。

AGENTS.md §3 要求在「resolving a contradiction at the same source-of-truth level」及改動驗收門檻前詢問擁有者。本提案保留門檻，但修正現有固定測例的提問意義，因此由擁有者批准此範圍；不從一般「繼續實作」推定可以悄悄改oracle。

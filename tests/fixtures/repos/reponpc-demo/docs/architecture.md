# Hybrid retrieval architecture

The fixture service retrieves exact filenames, paths, symbols, and technical
terms with a lexical FTS channel. It retrieves paraphrased concepts with a
normalized vector channel, then uses reciprocal-rank fusion to merge the two
ranked lists. The `rank_evidence` symbol intentionally appears in both this
document and `src/retrieval_pipeline.py` to exercise overlap handling.

繁體中文：詞彙檢索會處理精確檔名、路徑、符號與技術名詞；向量檢索處理不同措辭的
語意問題。系統再用 reciprocal-rank fusion 合併兩個排序結果。這段中文與英文段落
描述相同的架構，供雙語檢索等價性測試使用。

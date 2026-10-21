# A11 備份下載／還原界線待決定

狀態：擁有者 2026-10-03 回覆「好，那採用A」，核准以下選項 A 及同主機範圍。
依序實作加密下載、預先檢查、明確確認、自動保存目前狀態及安全還原。

## 證據與衝突

FR-053／AC-076 要求在管理頁下載並上傳還原 `runtime backup` 成果。
現有 `RuntimeDatabase.backup_to` 使用 SQLite online backup 原樣複製 runtime：
包含 sole-owner Argon2id hash、session/grant digest 與加密 model connection
revisions；它沒有提供 Web 專用的去敏版本。可解密 model revisions 的 host
master key、IP-HMAC key、bundle／appearance 檔案另存在資料目錄，未包含於
SQLite backup。`AGENTS.md` §4 禁止 admin hash／stored secrets 出現在 browser，
§3 要求 trust model／schema／endpoint 契約的改變先交 owner 決定。

因此不能直接把現有 SQLite 檔加上 download route，也不能把它稱為可跨主機
復原的完整備份。刪除 owner hash 或 model revisions 會失去登入／憑證連續性，
並改變既有 recovery 契約。

## 選項 A — 加密管理備份（建議）

使用既有 online SQLite backup primitive 生成一致資料，再以現有 cryptography
套件的受審核 KDF／authenticated encryption，加上 owner 每次新輸入的備份密碼，
產生版本化 encrypted artifact。Web 只收到 ciphertext，沒有儲存密碼／host key
readback。備份密碼不進 log、DB、browser storage 或公開草稿。

- 下載保留 owner hash／加密 revisions，但只存在 encrypted artifact 中。
- 不複製 raw sessions；還原後撤銷 session／launch grants，需要 launcher 重新登入。
- 初版為同一資料目錄的 SQLite 狀態還原；保留 host keys、bundles、appearance／
  local-portfolio 原檔，不表示完整跨主機搬移。UI 在下載前明示此範圍。
- 缺失／不相容 host key、引用的 bundle 或 appearance 檔案時，還原失敗且不改現有
  資料；不建立空 key store、不下載、不自動啟用 gateway。
- 只接受明確版本、bounded 長度與驗證成功的 artifact。先驗證 schema／integrity／
  foreign keys／retained resources，再顯示確認；真正還原前自動備份目前狀態。
- 以現有 worker／gateway lifecycle 進入短暫維護，保證沒有同時寫入，使用原子／
  可回退 SQLite replace；失敗保留現有 DB／LKG，不讓 uploaded SQLite 執行 SQL。
- API 與格式先凍結，再拆 UI、驗證器、fault tests；沒有另加 paid/service dependency。

影響：新增 encrypted artifact 與備份密碼輸入契約、管理端 restore lifecycle；
需更新 SECURITY／TECHNICAL_SPEC／OPERATIONS 的明確例外与正常／故障測試。

## 選項 B — 原始 SQLite 僅 owner 私有下載

owner 明確批准 FR-053 備份下載為 §4 browser-hash 禁令的例外，下載前提示它包含
管理認證 hash／加密私有設定，僅可安全保存。host master key 仍不下載；還原仍
限定相同資料目錄、引用資源齊備且撤銷 sessions。實作較少，但下載檔沒有新增
at-rest protection，備份遺失風險較大，且需明確批准 security 例外。

兩者都不在本輪真實 owner runtime 上操作；先用 disposable fixture 驗證。最終
完整資料目錄災難復原／跨主機搬移仍依現有 stopped-service operations guide。

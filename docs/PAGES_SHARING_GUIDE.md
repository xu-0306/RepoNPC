# GitHub Pages 手動分享 / Manual sharing

This guide accompanies approved A5. Implementation verification is in progress;
no site has been uploaded or externally verified by this task.

## RepoNPC

1. 在私人管理頁設定 HTTPS Pages 完整網址，例如
   `https://example.github.io/` 或 `https://example.github.io/portfolio/`。
   網域必須與 gateway 設定中的 Pages origin 相同。
2. 檢查公開內容與 FAQ 核准，再按「下載靜態網站」原生下載連結，
   下載 `reponpc-site.zip`，確認下載完成並解壓縮。
   把匯出內容交給自己的專用 repository；包含 `.nojekyll`。
3. 網站發布後回到 RepoNPC，按「核對 Pages」檢查入口頁與
   `export-manifest.json`。只有兩者都與本機重新建立的匯出內容逐位元組
   相符時，才會標示為已核對並提供 Pages 卡片連結。
4. 按「預覽 README 內容」核對完整檔案，再按「下載 README.md」。
   下載時會再次核對目前內容與 Pages 公開卡片；不必另上傳圖片。
   README.md 必須放在「與 GitHub 帳號同名的公開 repository」根目錄，
   才能顯示在個人首頁。已有 README 時先比較並保留原文，也可使用
   原有卡片 GIF 下載／上傳與複製區塊，追加名片。RepoNPC 不會自動覆寫。

Enter the full HTTPS Pages URL matching the gateway's Pages origin. Review the
public content and approved FAQ, select the native Download static site link
for `reponpc-site.zip`. Confirm the download completed and extract
it. Upload the export to your dedicated repository, including `.nojekyll`. After
publication, choose Verify Pages in RepoNPC. The entrance page and
`export-manifest.json` must both match the locally rebuilt export byte for byte
before the page is marked verified and its card link is offered. Preview the
complete file with Preview README content, then select Download README.md.
Download rechecks the current snapshot and public Pages card, so no separate
image upload is needed. README.md must be at the root of a public repository
with the same name as the GitHub account to appear on the profile. Compare and
preserve existing README content first, or append the existing copied card block
with the manual GIF upload path. RepoNPC never overwrites README automatically.

核對內容與 gateway 外網檢查是不同紀錄。已匯出的 FAQ 是匯出時的核准快照；
之後在主機撤回核准，無法立即撤回已下載的副本。更新後由擁有者決定是否
重新匯出、上傳、核對；本機內容變更不會自動清除既有的 Pages 核對狀態。

Content verification and the gateway's external check are separate records.
Exported FAQ is approved at export time; later withdrawal cannot revoke a
downloaded copy. After a content change, the owner decides when to export,
upload and verify again; local changes do not automatically clear an existing
Pages verification.

The export endpoint is a read-only authenticated `GET`, so the browser uses a
native download rather than a Blob URL. Verification is an authenticated,
CSRF-protected empty-body `POST`; it fetches only the configured Pages entrance
and manifest. The separate readonly README endpoint also checks the fixed Pages
GIF before returning the exact preview/download content. README failures explain
how to upload and verify again; content above the 500 KiB display boundary must
be shortened and republished. It does not upload to GitHub or activate a site.

## GitHub：設定發布來源 / Set the publishing source

GitHub 官方步驟：進入 repository 的 **Settings → Pages**，選擇
**Deploy from a branch**，指定放有匯出內容的 branch 與 folder，再按 Save。
網站類型與網址以 [GitHub Pages 說明](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
為準；下列截圖來自 [官方發布來源指南](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
（2026-09-29 查核）。

Open **Settings → Pages**, choose **Deploy from a branch**, select the branch
and folder holding your export, then save. The linked official guide includes
the current instructions and screenshots.

![GitHub repository Settings tab / repository 的 Settings](https://docs.github.com/assets/cb-28260/images/help/repository/repo-actions-settings.png)

![Choose the publishing branch / 選擇發布 branch](https://docs.github.com/assets/cb-47265/images/help/pages/publishing-source-drop-down.png)

![Choose the publishing folder / 選擇發布 folder](https://docs.github.com/assets/cb-24510/images/help/pages/publishing-source-folder-drop-down.png)

GitHub 列出的網站上限為 1 GB、每月頻寬軟限 100 GB；RepoNPC 檢查匯出大小，
不量測 GitHub 每月流量。[官方限制](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)

GitHub documents a 1 GB site limit and a 100 GB monthly soft bandwidth limit.
RepoNPC checks export size; it does not measure GitHub traffic.

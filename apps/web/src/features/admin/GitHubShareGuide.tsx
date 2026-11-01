import { InfoParagraphs } from "./InfoParagraphs";
import "../../p4-w3.css";
import type { ChangeEvent } from "react";

import { githubAccount, verifiedPagesMarkdown } from "./sharing";

export type GitHubShareGuideProps = {
  locale: "zh-TW" | "en";
  account: string;
  verifiedPagesUrl: string | null;
  profileStatus:
    | "unchecked"
    | "ready"
    | "missing"
    | "missing_readme"
    | "unavailable";
  imageStatus: "unchecked" | "ready" | "missing" | "unavailable";
  repositoryUrl: string | null;
  profileUrl: string | null;
  readmeUrl: string | null;
  createUrl: string | null;
  filename: string;
  cardReady: boolean;
  busy: boolean;
  notice: string;
  onAccountChange: (value: string) => void;
  onCheckProfile: () => void;
  onCheckImage: () => void;
  onDownload: () => void;
  onDownloadReadme: () => void;
  onPreviewReadme: () => void;
  readmePreview: string | null;
  onCopy: (markdown: string) => void;
};

type ProfileStatus = GitHubShareGuideProps["profileStatus"];
type ImageStatus = GitHubShareGuideProps["imageStatus"];

type GuideCopy = {
  title: string;
  subtitle: string;
  downloadReadme: string;
  previewReadme: string;
  readmePreviewHelp: string;
  readmeContents: string;
  readmePlacement: string;
  readmeReady: string;
  readmeUnavailable: string;
  existingReadme: string;
  stageProfile: string;
  stageCard: string;
  stageReadme: string;
  accountLabel: string;
  accountHelp: string;
  accountPlaceholder: string;
  accountNotEntered: string;
  checkProfile: string;
  profileStatus: Record<ProfileStatus, string>;
  repositoryDetails: string;
  publicRepository: string;
  rootReadme: string;
  createProfileHeading: string;
  createProfileIntro: string;
  repositoryName: string;
  choosePublic: string;
  addReadme: string;
  createRepository: string;
  existingRepositoryReadme: string;
  openRepository: string;
  openCreatePage: string;
  openReadme: string;
  openProfile: string;
  verifyPages: string;
  cardIntro: string;
  filenameLabel: string;
  filenameMissing: string;
  cardReady: string;
  cardNotReady: string;
  downloadCard: string;
  downloadDisabled: string;
  checkImage: string;
  imageStatus: Record<ImageStatus, string>;
  imageReadyNote: string;
  uploadStepsHeading: string;
  uploadSteps: string[];
  protectedBranch: string;
  readmeIntro: string;
  markdownPreviewHeading: string;
  markdownLabel: string;
  markdownReady: string;
  markdownMissing: string;
  copyMarkdown: string;
  preserveReadmeHeading: string;
  preserveReadmeSteps: string[];
  profileLinkPending: string;
  testHeading: string;
  testInstruction: string;
  testChecks: string[];
  busy: string;
  linkUnavailable: string;
  notCheckedAction: string;
};

const COPY: Record<GitHubShareGuideProps["locale"], GuideCopy> = {
  "zh-TW": {
    title: "4. GitHub 個人頁",
    subtitle:
      "下載完整 README.md，手動上傳到 GitHub 個人頁使用的 repository。卡片使用已核對 Pages 網站的公開圖片，不必另外上傳圖片。GitHub 只顯示名片。點擊連結才會前往 RepoNPC 網站對話。",
    downloadReadme: "下載 README.md",
    previewReadme: "預覽 README 內容",
    readmePreviewHelp:
      "這是最終 README.md 的完整檔案內容，並非 GitHub 渲染外觀；可用鍵盤捲動檢查介紹、作品與連結。下載時仍會重新核對。",
    readmeContents:
      "檔案包含公開介紹、作品連結、NPC 名片與「與我的 NPC 對話」入口。這些內容已套用並與 Pages 核對。尚未套用的草稿不會匯出。",
    readmePlacement:
      "README.md 必須放在「與 GitHub 帳號同名的公開 repository」根目錄，才能顯示在個人首頁。",
    readmeReady:
      "下載時會再次核對目前內容與公開卡片。請確認瀏覽器完成下載，再手動上傳 README.md。",
    readmeUnavailable:
      "先到第 3 段上傳並核對 Pages 網站，才能下載含公開卡片的 README.md。也可沿用下方的卡片下載、上傳與複製區塊。",
    existingReadme:
      "已有 README？請保留原文，使用下方「複製要貼進 README 的文字」追加名片。上傳完整檔案前先比較內容。RepoNPC 不會自動覆寫 GitHub README。",
    stageProfile: "同名 repository",
    stageCard: "上傳卡片",
    stageReadme: "README",
    accountLabel: "GitHub 帳號",
    accountHelp:
      "輸入 GitHub 使用者名稱或個人頁網址。這一步只查公開資料，不會登入帳號或建立 repository。",
    accountPlaceholder: "輸入 GitHub 帳號",
    accountNotEntered: "尚未輸入帳號",
    checkProfile: "檢查同名 repository",
    profileStatus: {
      unchecked:
        "尚未檢查同名 repository。GitHub 帳號存在，不代表個人頁的 README 已準備好。",
      ready:
        "已找到同名公開 repository 和根目錄 README.md。下一步請下載並上傳卡片。",
      missing:
        "目前找不到可公開讀取的同名 repository。這不表示 GitHub 帳號不存在，也無法判斷是否有私人 repository。若已建立，請確認名稱和 Public（公開）設定。尚未建立則依下方步驟操作。",
      missing_readme:
        "已找到同名公開 repository，但根目錄尚未找到 README.md。請在這個 repository 新增 README.md，不用再建一個。",
      unavailable:
        "目前無法查證同名 repository。可能是存取限制、GitHub 限流或暫時故障；請稍後重試。這不表示帳號或 repository 不存在。",
    },
    repositoryDetails: "這一步檢查的目標",
    publicRepository: "個人頁使用的 repository",
    rootReadme: "要編輯的檔案",
    createProfileHeading: "尚未建立同名 repository？",
    createProfileIntro:
      "只需建立一個與帳號同名的公開 repository，README 和卡片都放在這裡：",
    repositoryName: "Repository name 輸入",
    choosePublic: "確認 Owner（擁有者）是你的帳號，並選擇 Public（公開）。",
    addReadme: "勾選 Add a README file（新增說明檔），建立 README.md。",
    createRepository: "按 Create repository。完成後回來重新檢查。",
    existingRepositoryReadme:
      "repository 已存在，只需在根目錄新增 README.md，無須建立第二個 repository。",
    openRepository: "查看同名 repository",
    openCreatePage: "前往 GitHub 建立 repository",
    openReadme: "編輯 README.md",
    openProfile: "查看 GitHub 帳號頁",
    verifyPages: "前往第 3 段上傳並核對 Pages 網站",
    cardIntro:
      "先下載卡片，再把圖片上傳到第一步的同名 repository 根目錄。不用建立另一個 repository。",
    filenameLabel: "建議上傳檔名（根目錄）",
    filenameMissing: "尚未提供檔名",
    cardReady: "卡片已準備好，可以下載。",
    cardNotReady: "先按頁面上方的「預覽作品與卡片」，產生圖片後即可下載。",
    downloadCard: "下載卡片",
    downloadDisabled: "先按頁面上方的「預覽作品與卡片」產生圖片，才能下載。",
    checkImage: "檢查圖片是否已上傳",
    imageStatus: {
      unchecked: "尚未檢查圖片。上傳到 GitHub 後，按「檢查圖片是否已上傳」。",
      ready:
        "已在同名 repository 找到這個檔名的圖片；這只確認檔案存在，請在最後確認個人頁顯示的是新卡片。",
      missing:
        "尚未找到卡片圖片。請確認檔名正確、檔案放在 repository 根目錄，並已存入預設分支。",
      unavailable:
        "目前無法確認圖片狀態；可能是未登入、沒有權限、repository 不可見、限流或服務暫時無法使用。請稍後重試或手動開啟 repository。",
    },
    imageReadyNote:
      "這是狀態檢查結果，不代表 README 已更新；README 仍需下一步手動貼入。",
    uploadStepsHeading: "在 GitHub 依序操作",
    uploadSteps: [
      "在第一步的同名 repository，按 Add file（新增檔案）→ Upload files（上傳檔案）。",
      "選剛下載的圖片，放在 repository 最外層（不要放進資料夾）。檔名保持為上方顯示的名稱。",
      "依 GitHub 畫面提交變更；若需要審查或合併，完成後再回來檢查圖片。",
    ],
    protectedBranch:
      "受保護的預設分支可能需要提案與合併；圖片進入預設分支前，不要把上傳視為完成。",
    readmeIntro:
      "最後編輯同名 repository 的 README.md。把下方文字貼到想顯示卡片的位置，保留原本的介紹。",
    markdownPreviewHeading: "已核對 Pages 網站的 README 文字",
    markdownLabel: "複製下方這段文字",
    markdownReady: "要貼進 README.md 的文字已準備好，可以複製。",
    markdownMissing:
      "還沒有可複製的內容。已核對的 Pages 網址要是 https://account.github.io/project/ 這種格式，結尾要有 /，才能產生文字；卡片圖片仍可先下載。",
    copyMarkdown: "複製要貼進 README 的文字",
    preserveReadmeHeading: "在 README 保留原文",
    preserveReadmeSteps: [
      "打開同名 repository 的 README.md，點 GitHub 的編輯按鈕。",
      "貼入上方複製的內容，保留原有介紹文字。",
      "先預覽圖片和連結，再依 GitHub 畫面提交變更。",
    ],
    profileLinkPending:
      "請先完成第一步，確認同名公開 repository 和 README.md。",
    testHeading: "從 GitHub 實際查看",
    testInstruction:
      "提交 README 後，開啟 GitHub 帳號頁。確認卡片出現在個人介紹。再點卡片進入公開 RepoNPC 網站並試問一次。",
    testChecks: [
      "圖片可見是第一個檢查。",
      "README 引用正確是第二個檢查。",
      "NPC 公開網址能連線並回答是第三個檢查；主機或必要模型停止時，訪客仍可能無法聊天。",
    ],
    busy: "正在處理中…",
    linkUnavailable: "填入有效 GitHub 帳號後才會顯示連結。",
    notCheckedAction: "在 GitHub 建立或修改後，回來按「檢查同名 repository」。",
  },
  en: {
    title: "4. GitHub profile",
    subtitle:
      "Download a complete README.md and manually upload it to your GitHub profile repository. The card uses a public image from your verified Pages site. You do not need a separate image upload. GitHub displays only the card. Its link opens the RepoNPC site for conversations.",
    downloadReadme: "Download README.md",
    previewReadme: "Preview README content",
    readmePreviewHelp:
      "This is the full final README.md file content, not GitHub's rendered appearance. Use the keyboard to scroll through the introduction, projects and links. Download still rechecks it.",
    readmeContents:
      "The file includes the applied public introduction, project links, NPC card and Chat with my NPC link matching the verified Pages site. The file excludes unapplied drafts.",
    readmePlacement:
      "README.md must be at the root of a public repository with the same name as your GitHub account to appear on your profile.",
    readmeReady:
      "Download rechecks the current content and public card. Confirm the browser download completes, then upload README.md manually.",
    readmeUnavailable:
      "Upload and check your Pages site in section 3 before downloading a README.md with a public card. You can also use the card download, upload and copy steps below.",
    existingReadme:
      "Already have a README? Keep its text and use Copy text for README below to append the card. Compare content before uploading a complete file. RepoNPC never overwrites your GitHub README automatically.",
    stageProfile: "Matching repository",
    stageCard: "Upload card",
    stageReadme: "README",
    accountLabel: "GitHub account",
    accountHelp:
      "Enter your GitHub username or profile URL. This step only checks public information. It does not sign in or create a repository.",
    accountPlaceholder: "Enter a GitHub account",
    accountNotEntered: "No account entered",
    checkProfile: "Check matching repository",
    profileStatus: {
      unchecked:
        "RepoNPC has not checked the matching repository. Having a GitHub account does not mean its profile README is ready.",
      ready:
        "The matching public repository and root README.md were found. Next, download and upload the card.",
      missing:
        "No publicly readable matching repository was found. This does not mean your GitHub account is missing, and it cannot rule out a private repository. If you already created it, check its name and Public setting; otherwise follow the steps below.",
      missing_readme:
        "The matching public repository was found, but README.md was not found at its root. Add README.md there; you do not need another repository.",
      unavailable:
        "The matching repository cannot be checked right now. Access restrictions, GitHub rate limits, or a temporary failure may be responsible. Try again later; this does not mean the account or repository is missing.",
    },
    repositoryDetails: "What this step checks",
    publicRepository: "Repository used for your profile",
    rootReadme: "File to edit",
    createProfileHeading: "No matching repository yet?",
    createProfileIntro:
      "Create one public repository with the same name as your account. Both README and the card go here:",
    repositoryName: "Enter this Repository name:",
    choosePublic: "Confirm Owner is your account and select Public.",
    addReadme: "Select Add a README file to create README.md.",
    createRepository:
      "Select Create repository, then return here and check again.",
    existingRepositoryReadme:
      "The repository already exists. Add README.md at its root; do not create a second repository.",
    openRepository: "View matching repository",
    openCreatePage: "Create the repository on GitHub",
    openReadme: "Edit README.md",
    openProfile: "View GitHub account page",
    verifyPages: "Go to section 3 to upload and check your Pages site",
    cardIntro:
      "Download the card, then upload the image to the root of the matching repository from step one. You do not need another repository.",
    filenameLabel: "Suggested upload filename (repository root)",
    filenameMissing: "No filename supplied",
    cardReady: "The card is ready to download.",
    cardNotReady:
      "Select Preview portfolio and card above to generate the image before downloading.",
    downloadCard: "Download card",
    downloadDisabled:
      "Select Preview portfolio and card above to generate the image before downloading.",
    checkImage: "Check the uploaded image",
    imageStatus: {
      unchecked:
        "RepoNPC has not checked the image. After uploading it to GitHub, select Check the uploaded image.",
      ready:
        "An image with this filename was found in the matching repository. This confirms only that the file exists; check the profile page for the updated card at the end.",
      missing:
        "The card image was not found. Check its filename, that it is at the repository root, and that it has reached the default branch.",
      unavailable:
        "The image state cannot be confirmed right now. You may be signed out, lack access, have an invisible repository, be rate-limited, or be facing a temporary service failure. Retry later or open the repository manually.",
    },
    imageReadyNote:
      "This is an image check result; it does not mean the README is updated. Add the Markdown in the next step.",
    uploadStepsHeading: "Use these GitHub controls",
    uploadSteps: [
      "In the matching repository from step one, select Add file → Upload files.",
      "Choose the downloaded image, place it at the root, and keep the filename shown above.",
      "Submit the change in GitHub. If GitHub requires review or a merge, complete it before checking the image again.",
    ],
    protectedBranch:
      "A protected default branch may require a proposal and merge. Do not call the upload complete until the image is on the default branch.",
    readmeIntro:
      "Finally, edit README.md in the matching repository. Paste the text below where the card should appear and keep your existing introduction.",
    markdownPreviewHeading: "README text for the verified Pages site",
    markdownLabel: "Copy the text below",
    markdownReady: "The text for README.md is ready to copy.",
    markdownMissing:
      "Nothing is ready to copy yet. The verified Pages URL must look like https://account.github.io/project/ and end with /. You can still download the card image now.",
    copyMarkdown: "Copy text for README",
    preserveReadmeHeading: "Keep existing README text",
    preserveReadmeSteps: [
      "Open README.md in the matching repository and select GitHub's edit control.",
      "Paste the copied text and keep your existing introduction.",
      "Preview the image and link, then submit the change using GitHub's controls.",
    ],
    profileLinkPending:
      "Complete step one first to confirm the matching public repository and README.md.",
    testHeading: "View the result on GitHub",
    testInstruction:
      "After submitting README, open your GitHub account page. Confirm the card appears in your profile introduction. Click it to open the public RepoNPC site and ask a test question.",
    testChecks: [
      "A visible image is the first check.",
      "A correct README reference is the second check.",
      "A reachable visitor URL and answer are the third check. Visitors may lose chat when the host or required model stops.",
    ],
    busy: "Working…",
    linkUnavailable: "Enter a valid GitHub account to show the link.",
    notCheckedAction:
      "After creating or editing it on GitHub, return and select Check matching repository.",
  },
};

export function GitHubShareGuide({
  locale,
  account,
  verifiedPagesUrl,
  profileStatus,
  imageStatus,
  repositoryUrl,
  profileUrl,
  readmeUrl,
  createUrl,
  filename,
  cardReady,
  busy,
  notice,
  onAccountChange,
  onCheckProfile,
  onCheckImage,
  onDownload,
  onDownloadReadme,
  onPreviewReadme,
  readmePreview,
  onCopy,
}: GitHubShareGuideProps) {
  const copy = COPY[locale];
  const accountIsEmpty = account.trim().length === 0;
  const normalizedAccount = githubAccount(account);
  const profileOpen = profileStatus !== "ready";
  const pagesReady =
    !!verifiedPagesUrl && !!verifiedPagesMarkdown(verifiedPagesUrl, locale);
  const cardOpen =
    !pagesReady && profileStatus === "ready" && imageStatus !== "ready";
  const readmeOpen =
    !pagesReady && profileStatus === "ready" && imageStatus === "ready";

  function markdownField(value: string, id: string) {
    const empty = !value.trim();
    return (
      <>
        <label htmlFor={id}>{copy.markdownLabel}</label>
        <textarea
          className="px-field"
          aria-describedby={`${id}-status`}
          id={id}
          readOnly
          rows={7}
          value={value}
        />
        <div className="publication-actions" aria-label={copy.stageReadme}>
          <button
            aria-describedby={empty ? `${id}-status` : undefined}
            className="px-button px-button--secondary"
            disabled={busy || empty}
            onClick={() => onCopy(value)}
            type="button"
          >
            {copy.copyMarkdown}
          </button>
        </div>
        <p id={`${id}-status`} role="status">
          {empty ? copy.markdownMissing : copy.markdownReady}
        </p>
      </>
    );
  }

  return (
    <section
      aria-busy={busy}
      aria-labelledby="github-share-guide-heading"
      className="github-share px-panel"
      data-testid="github-share-guide"
      lang={locale}
    >
      <p className="publication-kicker px-meta">GitHub</p>
      <h2 id="github-share-guide-heading">{copy.title}</h2>
      <details className="publication-info px-info">
        <summary>
          ⓘ {locale === "zh-TW" ? "分享方式" : "How sharing works"}
        </summary>
        <InfoParagraphs locale={locale} text={copy.subtitle} />
        <InfoParagraphs
          locale={locale}
          id="github-share-readme-placement"
          text={copy.readmePlacement}
        />
        <InfoParagraphs locale={locale} text={copy.existingReadme} />
      </details>

      {notice.trim().length > 0 && (
        <p className="publication-notice" role="alert">
          {notice}
        </p>
      )}

      <div className="github-share__stage">
        <details className="publication-info px-info">
          <summary>
            ⓘ {locale === "zh-TW" ? "檔案內容" : "File contents"}
          </summary>
          <InfoParagraphs locale={locale} text={copy.readmeContents} />
          <InfoParagraphs
            locale={locale}
            text={pagesReady ? copy.readmeReady : copy.readmeUnavailable}
          />
        </details>
        <div className="publication-actions">
          <button
            type="button"
            className="px-button px-button--secondary"
            disabled={!pagesReady}
            aria-disabled={busy || !pagesReady}
            aria-describedby="github-share-readme-placement github-share-readme-download-status"
            onClick={() => {
              if (!busy && pagesReady) onDownloadReadme();
            }}
          >
            {copy.downloadReadme}
          </button>
          <button
            className="px-button px-button--secondary"
            type="button"
            disabled={!pagesReady}
            aria-disabled={busy || !pagesReady}
            aria-describedby="github-share-readme-download-status"
            onClick={() => {
              if (!busy && pagesReady) onPreviewReadme();
            }}
          >
            {copy.previewReadme}
          </button>
        </div>
        <p id="github-share-readme-download-status" role="status">
          {pagesReady
            ? locale === "zh-TW"
              ? "已核對"
              : "Verified"
            : locale === "zh-TW"
              ? "未核對 Pages"
              : "Pages unverified"}
        </p>
        {readmePreview !== null && (
          <>
            <label htmlFor="github-share-readme-preview">
              {copy.previewReadme}
            </label>
            <textarea
              className="px-field"
              id="github-share-readme-preview"
              aria-describedby="github-share-readme-preview-help"
              readOnly
              rows={14}
              value={readmePreview}
            />
            <p id="github-share-readme-preview-help">
              {copy.readmePreviewHelp}
            </p>
          </>
        )}
      </div>

      <details className="github-share__alternative">
        <summary>
          {locale === "zh-TW" ? "卡片 → README" : "Card → README"}
        </summary>
        <section
          aria-labelledby="github-share-profile-heading"
          className="github-share__stage"
          data-stage="profile"
        >
          <details open={profileOpen}>
            <summary id="github-share-profile-heading">
              <span aria-hidden="true" className="publication-kicker px-meta">
                1
              </span>{" "}
              {copy.stageProfile}
            </summary>
            <label htmlFor="github-share-account">
              {copy.accountLabel}
              <input
                className="px-field"
                aria-describedby="github-share-account-help"
                disabled={busy}
                id="github-share-account"
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                  onAccountChange(event.target.value)
                }
                placeholder={copy.accountPlaceholder}
                value={account}
              />
            </label>
            <details className="publication-info px-info">
              <summary>ⓘ {copy.accountLabel}</summary>
              <InfoParagraphs
                locale={locale}
                id="github-share-account-help"
                text={copy.accountHelp}
              />
            </details>

            <div className="publication-actions" aria-label={copy.stageProfile}>
              <button
                aria-describedby={
                  accountIsEmpty ? "github-share-account-help" : undefined
                }
                className="px-button px-button--secondary"
                disabled={busy || accountIsEmpty}
                onClick={onCheckProfile}
                type="button"
              >
                {copy.checkProfile}
              </button>
            </div>

            <div
              className="publication-message"
              data-status={profileStatus}
              id="github-share-profile-status"
              role={profileStatus === "unavailable" ? "alert" : "status"}
            >
              <InfoParagraphs
                locale={locale}
                text={copy.profileStatus[profileStatus]}
              />
            </div>

            <section aria-labelledby="github-share-repository-details-heading">
              <h3 id="github-share-repository-details-heading">
                {copy.repositoryDetails}
              </h3>
              <dl>
                <div>
                  <dt>{copy.accountLabel}</dt>
                  <dd>
                    <code>{account || copy.accountNotEntered}</code>
                  </dd>
                </div>
                <div>
                  <dt>{copy.publicRepository}</dt>
                  <dd>
                    <code>
                      {normalizedAccount
                        ? `${normalizedAccount}/${normalizedAccount}`
                        : "—"}
                    </code>
                  </dd>
                </div>
                <div>
                  <dt>{copy.rootReadme}</dt>
                  <dd>
                    <code>README.md</code>
                  </dd>
                </div>
              </dl>
            </section>

            {profileStatus === "missing" && (
              <div className="publication-message">
                <h3>{copy.createProfileHeading}</h3>
                <InfoParagraphs
                  locale={locale}
                  text={copy.createProfileIntro}
                />
                <ol>
                  <li>
                    {copy.repositoryName}{" "}
                    <code>{account || copy.accountNotEntered}</code>.
                  </li>
                  <li>{copy.choosePublic}</li>
                  <li>{copy.addReadme}</li>
                  <li>{copy.createRepository}</li>
                </ol>
                {createUrl ? (
                  <ExternalLink href={createUrl} label={copy.openCreatePage} />
                ) : (
                  <InfoParagraphs locale={locale} text={copy.linkUnavailable} />
                )}
              </div>
            )}

            {profileStatus === "missing_readme" && (
              <p className="publication-message">
                {copy.existingRepositoryReadme}
              </p>
            )}

            <div
              className="publication-actions"
              aria-label={copy.stageProfile}
              role="group"
            >
              {repositoryUrl && (
                <ExternalLink
                  href={repositoryUrl}
                  label={copy.openRepository}
                />
              )}
              {readmeUrl && profileStatus === "ready" && (
                <ExternalLink href={readmeUrl} label={copy.openReadme} />
              )}
              {profileUrl && (
                <ExternalLink href={profileUrl} label={copy.openProfile} />
              )}
              {profileStatus === "unchecked" && (
                <p role="status">{copy.notCheckedAction}</p>
              )}
            </div>
          </details>
        </section>

        <section
          aria-labelledby="github-share-card-heading"
          className="github-share__stage"
          data-stage="card"
        >
          <details open={cardOpen}>
            <summary id="github-share-card-heading">
              <span aria-hidden="true" className="publication-kicker px-meta">
                2
              </span>{" "}
              {copy.stageCard}
            </summary>
            <InfoParagraphs locale={locale} text={copy.cardIntro} />
            <dl>
              <div>
                <dt>{copy.filenameLabel}</dt>
                <dd>
                  <code>{filename || copy.filenameMissing}</code>
                </dd>
              </div>
            </dl>
            <div
              className="publication-actions"
              aria-label={copy.stageCard}
              role="group"
            >
              <button
                aria-describedby={
                  !cardReady ? "github-share-download-reason" : undefined
                }
                className="px-button px-button--secondary"
                disabled={busy || !cardReady}
                onClick={onDownload}
                type="button"
              >
                {copy.downloadCard}
              </button>
              <button
                className="px-button px-button--secondary"
                disabled={busy}
                onClick={onCheckImage}
                type="button"
              >
                {copy.checkImage}
              </button>
            </div>
            <p id="github-share-download-reason" role="status">
              {cardReady ? copy.cardReady : copy.downloadDisabled}
            </p>
            <p
              className="publication-message"
              data-status={imageStatus}
              id="github-share-image-status"
              role={imageStatus === "unavailable" ? "alert" : "status"}
            >
              {copy.imageStatus[imageStatus]}
            </p>
            {imageStatus === "ready" && (
              <p className="publication-message">{copy.imageReadyNote}</p>
            )}
            <h3>{copy.uploadStepsHeading}</h3>
            <ol>
              {copy.uploadSteps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            <InfoParagraphs locale={locale} text={copy.protectedBranch} />
            {repositoryUrl ? (
              <ExternalLink href={repositoryUrl} label={copy.openRepository} />
            ) : (
              <InfoParagraphs locale={locale} text={copy.linkUnavailable} />
            )}
          </details>
        </section>

        <section
          aria-labelledby="github-share-readme-heading"
          className="github-share__stage"
          data-stage="readme"
        >
          <details open={readmeOpen}>
            <summary id="github-share-readme-heading">
              <span aria-hidden="true" className="publication-kicker px-meta">
                3
              </span>{" "}
              {copy.stageReadme}
            </summary>
            <InfoParagraphs locale={locale} text={copy.readmeIntro} />

            {verifiedPagesUrl ? (
              <>
                <h3>{copy.markdownPreviewHeading}</h3>
                {markdownField(
                  verifiedPagesMarkdown(verifiedPagesUrl, locale),
                  "github-share-pages-markdown",
                )}
              </>
            ) : (
              <div className="publication-link">
                <a
                  href="#pages-share-panel-heading"
                  onClick={() => {
                    const heading = document.getElementById(
                      "pages-share-panel-heading",
                    );
                    if (heading) {
                      heading.tabIndex = -1;
                      heading.focus({ preventScroll: true });
                      heading.scrollIntoView({
                        block: "start",
                        behavior: "instant",
                      });
                    }
                  }}
                >
                  {copy.verifyPages}
                </a>
              </div>
            )}

            <div className="publication-message">
              <h3>{copy.preserveReadmeHeading}</h3>
              <ol>
                {copy.preserveReadmeSteps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              <div className="publication-actions">
                {readmeUrl && profileStatus === "ready" && (
                  <ExternalLink href={readmeUrl} label={copy.openReadme} />
                )}
                {profileStatus === "ready" && profileUrl ? (
                  <ExternalLink href={profileUrl} label={copy.openProfile} />
                ) : (
                  <InfoParagraphs
                    locale={locale}
                    text={copy.profileLinkPending}
                  />
                )}
              </div>
            </div>

            <div className="publication-message">
              <h3>{copy.testHeading}</h3>
              <InfoParagraphs locale={locale} text={copy.testInstruction} />
              <ul>
                {copy.testChecks.map((check) => (
                  <li key={check}>{check}</li>
                ))}
              </ul>
            </div>
          </details>
        </section>
      </details>
      {busy && <p role="status">{copy.busy}</p>}
    </section>
  );
}

function ExternalLink({ href, label }: { href: string; label: string }) {
  return (
    <a href={href} rel="noopener noreferrer" target="_blank">
      {label}
    </a>
  );
}

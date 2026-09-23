import type { ChangeEvent } from "react";

import { githubAccount } from "./sharing";

export type GitHubShareGuideProps = {
  locale: "zh-TW" | "en";
  account: string;
  publicUrl: string;
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
  markdown: string;
  cardReady: boolean;
  busy: boolean;
  notice: string;
  onAccountChange: (value: string) => void;
  onPublicUrlChange: (value: string) => void;
  onCheckProfile: () => void;
  onCheckImage: () => void;
  onDownload: () => void;
  onCopy: () => void;
};

type ProfileStatus = GitHubShareGuideProps["profileStatus"];
type ImageStatus = GitHubShareGuideProps["imageStatus"];

type GuideCopy = {
  title: string;
  subtitle: string;
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
  publicUrlLabel: string;
  publicUrlHelp: string;
  publicUrlNotReady: string;
  publicUrlEntered: string;
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
    title: "把 RepoNPC 卡片放到 GitHub 個人頁",
    subtitle:
      "GitHub 帳號和用來放個人介紹的儲存庫（repository）是兩回事。要在個人頁顯示卡片，請準備與帳號同名的公開儲存庫，把 README.md 和卡片圖片放在一起；不必另外建立卡片專用 repository。這裡只檢查公開資料並說明步驟，不會替你修改 GitHub。",
    stageProfile: "確認個人頁的同名 repository",
    stageCard: "下載卡片並上傳到同一個 repository",
    stageReadme: "把卡片加入 README 並檢查結果",
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
        "目前找不到可公開讀取的同名 repository。這不表示 GitHub 帳號不存在，也無法判斷是否有私人 repository。若已建立，請確認名稱和 Public 設定；尚未建立則依下方步驟操作。",
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
    choosePublic: "確認 Owner 是你的帳號，並選擇 Public（公開）。",
    addReadme: "勾選 Add a README file，建立 README.md。",
    createRepository: "按 Create repository；完成後回來重新檢查。",
    existingRepositoryReadme:
      "repository 已存在，只需在根目錄新增 README.md，無須建立第二個 repository。",
    openRepository: "查看同名 repository",
    openCreatePage: "前往 GitHub 建立 repository",
    openReadme: "編輯 README.md",
    openProfile: "查看 GitHub 帳號頁",
    publicUrlLabel: "公開 RepoNPC 訪客網址",
    publicUrlHelp:
      "訪客點卡片後會開啟這個 RepoNPC 網站。請填能從外網開啟的 HTTPS 網址；localhost 只能在你的電腦使用。沒有公開網址也可先準備圖片。",
    publicUrlNotReady:
      "還沒有可用的公開訪客連結。可先下載圖片，之後再產生要貼進 README 的連結。",
    publicUrlEntered:
      "網址格式已通過檢查；發佈後仍要從 GitHub 實際點擊卡片並試問。",
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
      "在第一步的同名 repository，按 Add file → Upload files。",
      "選剛下載的圖片，放在 repository 最外層（不要放進資料夾），檔名保持為上方顯示的名稱。",
      "依 GitHub 畫面提交變更；若需要審查或合併，完成後再回來檢查圖片。",
    ],
    protectedBranch:
      "受保護的預設分支可能需要提案與合併；圖片進入預設分支前，不要把上傳視為完成。",
    readmeIntro:
      "最後編輯同名 repository 的 README.md，把下方文字貼到想顯示卡片的位置，保留原本的介紹。",
    markdownPreviewHeading: "要貼進 README.md 的文字",
    markdownLabel: "複製下方這段文字",
    markdownReady: "要貼進 README.md 的文字已準備好，可以複製。",
    markdownMissing:
      "還沒有可複製的內容。先填入可公開連線的 HTTPS 訪客網址；卡片圖片仍可先下載。",
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
      "提交 README 後，開啟 GitHub 帳號頁，確認卡片出現在個人介紹，再點卡片進入公開 RepoNPC 網站並試問一次。",
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
    title: "Put your RepoNPC card on your GitHub profile",
    subtitle:
      "Your GitHub account and the repository used for your profile are different things. To show the card on your profile, use a public repository with the same name as your account and put README.md and the card image in it. You do not need a separate card repository. This guide checks public information and explains the steps; it never edits GitHub for you.",
    stageProfile: "Check the repository used for your profile",
    stageCard: "Download the card and upload it to the same repository",
    stageReadme: "Add the card to README and check the result",
    accountLabel: "GitHub account",
    accountHelp:
      "Enter your GitHub username or profile URL. This step only checks public information; it does not sign in or create a repository.",
    accountPlaceholder: "Enter a GitHub account",
    accountNotEntered: "No account entered",
    checkProfile: "Check matching repository",
    profileStatus: {
      unchecked:
        "The matching repository has not been checked. Having a GitHub account does not mean its profile README is ready.",
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
    publicUrlLabel: "Public RepoNPC visitor URL",
    publicUrlHelp:
      "Visitors open this RepoNPC site when they click the card. Enter a public HTTPS URL they can reach; localhost only works on your computer. You can prepare the image before you have a public URL.",
    publicUrlNotReady:
      "No public visitor link is ready yet. You can download the image now and generate the README link later.",
    publicUrlEntered:
      "The URL format passed validation. After publishing, click the card from GitHub and ask a test question.",
    cardIntro:
      "Download the card, then upload the image to the root of the matching repository from step one. No other repository is needed.",
    filenameLabel: "Suggested upload filename (repository root)",
    filenameMissing: "No filename supplied",
    cardReady: "The card is ready to download.",
    cardNotReady:
      "Select Preview portfolio and card above to generate the image before downloading.",
    downloadCard: "Download card",
    downloadDisabled:
      "Select Preview portfolio and card above to generate the image before downloading.",
    checkImage: "Check whether the image is uploaded",
    imageStatus: {
      unchecked:
        "The image has not been checked. After uploading it to GitHub, select Check whether the image is uploaded.",
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
      "Submit the change in GitHub. If review or a merge is required, complete it before checking the image again.",
    ],
    protectedBranch:
      "A protected default branch may require a proposal and merge. Do not call the upload complete until the image is on the default branch.",
    readmeIntro:
      "Finally, edit README.md in the matching repository. Paste the text below where the card should appear and keep your existing introduction.",
    markdownPreviewHeading: "Text to paste into README.md",
    markdownLabel: "Copy the text below",
    markdownReady: "The text for README.md is ready to copy.",
    markdownMissing:
      "Nothing is ready to copy yet. Enter a public HTTPS visitor URL first; you can still download the card image now.",
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
      "After submitting README, open your GitHub account page. Confirm the card appears in your profile introduction, then click it to open the public RepoNPC site and ask a test question.",
    testChecks: [
      "A visible image is the first check.",
      "A correct README reference is the second check.",
      "A reachable visitor URL and answer are the third check; visitors may lose chat when the host or required model is stopped.",
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
  publicUrl,
  profileStatus,
  imageStatus,
  repositoryUrl,
  profileUrl,
  readmeUrl,
  createUrl,
  filename,
  markdown,
  cardReady,
  busy,
  notice,
  onAccountChange,
  onPublicUrlChange,
  onCheckProfile,
  onCheckImage,
  onDownload,
  onCopy,
}: GitHubShareGuideProps) {
  const copy = COPY[locale];
  const accountIsEmpty = account.trim().length === 0;
  const markdownIsEmpty = markdown.trim().length === 0;
  const normalizedAccount = githubAccount(account);
  const profileOpen = profileStatus !== "ready";
  const cardOpen = profileStatus === "ready" && imageStatus !== "ready";
  const readmeOpen = profileStatus === "ready" && imageStatus === "ready";

  return (
    <section
      aria-busy={busy}
      aria-labelledby="github-share-guide-heading"
      className="admin-surface"
      data-testid="github-share-guide"
      lang={locale}
    >
      <p className="admin-section-kicker">GitHub</p>
      <h2 id="github-share-guide-heading">{copy.title}</h2>
      <p>{copy.subtitle}</p>

      {notice.trim().length > 0 && (
        <p className="admin-workspace__notice" role="alert">
          {notice}
        </p>
      )}

      <section
        aria-labelledby="github-share-profile-heading"
        className="guided-onboarding__step"
        data-stage="profile"
      >
        <details open={profileOpen}>
          <summary id="github-share-profile-heading">
            <span aria-hidden="true" className="admin-section-kicker">
              1
            </span>{" "}
            {copy.stageProfile}
          </summary>
          <label htmlFor="github-share-account">
            {copy.accountLabel}
            <input
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
          <p id="github-share-account-help">{copy.accountHelp}</p>

          <div
            className="admin-workspace__actions"
            aria-label={copy.stageProfile}
          >
            <button
              aria-describedby={
                accountIsEmpty ? "github-share-account-help" : undefined
              }
              className="ux-primary"
              disabled={busy || accountIsEmpty}
              onClick={onCheckProfile}
              type="button"
            >
              {copy.checkProfile}
            </button>
          </div>

          <p
            className="ux-missing-fields"
            data-status={profileStatus}
            id="github-share-profile-status"
            role={profileStatus === "unavailable" ? "alert" : "status"}
          >
            {copy.profileStatus[profileStatus]}
          </p>

          <section aria-labelledby="github-share-repository-details-heading">
            <h4 id="github-share-repository-details-heading">
              {copy.repositoryDetails}
            </h4>
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
            <div className="ux-missing-fields">
              <h4>{copy.createProfileHeading}</h4>
              <p>{copy.createProfileIntro}</p>
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
                <p>{copy.linkUnavailable}</p>
              )}
            </div>
          )}

          {profileStatus === "missing_readme" && (
            <p className="ux-missing-fields">{copy.existingRepositoryReadme}</p>
          )}

          <div className="ux-actions" aria-label={copy.stageProfile}>
            {repositoryUrl && (
              <ExternalLink href={repositoryUrl} label={copy.openRepository} />
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
        className="guided-onboarding__step"
        data-stage="card"
      >
        <details open={cardOpen}>
          <summary id="github-share-card-heading">
            <span aria-hidden="true" className="admin-section-kicker">
              2
            </span>{" "}
            {copy.stageCard}
          </summary>
          <p>{copy.cardIntro}</p>
          <dl>
            <div>
              <dt>{copy.filenameLabel}</dt>
              <dd>
                <code>{filename || copy.filenameMissing}</code>
              </dd>
            </div>
          </dl>
          <div className="admin-workspace__actions" aria-label={copy.stageCard}>
            <button
              aria-describedby={
                !cardReady ? "github-share-download-reason" : undefined
              }
              className="ux-primary"
              disabled={busy || !cardReady}
              onClick={onDownload}
              type="button"
            >
              {copy.downloadCard}
            </button>
            <button disabled={busy} onClick={onCheckImage} type="button">
              {copy.checkImage}
            </button>
          </div>
          <p id="github-share-download-reason" role="status">
            {cardReady ? copy.cardReady : copy.downloadDisabled}
          </p>
          <p
            className="ux-missing-fields"
            data-status={imageStatus}
            id="github-share-image-status"
            role={imageStatus === "unavailable" ? "alert" : "status"}
          >
            {copy.imageStatus[imageStatus]}
          </p>
          {imageStatus === "ready" && (
            <p className="ux-missing-fields">{copy.imageReadyNote}</p>
          )}
          <h4>{copy.uploadStepsHeading}</h4>
          <ol>
            {copy.uploadSteps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <p>{copy.protectedBranch}</p>
          {repositoryUrl ? (
            <ExternalLink href={repositoryUrl} label={copy.openRepository} />
          ) : (
            <p>{copy.linkUnavailable}</p>
          )}
        </details>
      </section>

      <section
        aria-labelledby="github-share-readme-heading"
        className="guided-onboarding__step"
        data-stage="readme"
      >
        <details open={readmeOpen}>
          <summary id="github-share-readme-heading">
            <span aria-hidden="true" className="admin-section-kicker">
              3
            </span>{" "}
            {copy.stageReadme}
          </summary>
          <p>{copy.readmeIntro}</p>

          <label htmlFor="github-share-public-url">
            {copy.publicUrlLabel}
            <input
              aria-describedby="github-share-public-url-help"
              disabled={busy}
              id="github-share-public-url"
              inputMode="url"
              onChange={(event: ChangeEvent<HTMLInputElement>) =>
                onPublicUrlChange(event.target.value)
              }
              type="url"
              value={publicUrl}
            />
          </label>
          <p id="github-share-public-url-help">
            {copy.publicUrlHelp}{" "}
            {!markdownIsEmpty ? copy.publicUrlEntered : copy.publicUrlNotReady}
          </p>

          <h4>{copy.markdownPreviewHeading}</h4>
          <label htmlFor="github-share-markdown">{copy.markdownLabel}</label>
          <textarea
            aria-describedby="github-share-markdown-status"
            id="github-share-markdown"
            readOnly
            rows={7}
            value={markdown}
          />
          <div
            className="admin-workspace__actions"
            aria-label={copy.stageReadme}
          >
            <button
              aria-describedby={
                markdownIsEmpty ? "github-share-markdown-status" : undefined
              }
              className="ux-primary"
              disabled={busy || markdownIsEmpty}
              onClick={onCopy}
              type="button"
            >
              {copy.copyMarkdown}
            </button>
          </div>
          <p id="github-share-markdown-status" role="status">
            {markdownIsEmpty ? copy.markdownMissing : copy.markdownReady}
          </p>

          <div className="ux-missing-fields">
            <h4>{copy.preserveReadmeHeading}</h4>
            <ol>
              {copy.preserveReadmeSteps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            <div className="ux-actions">
              {readmeUrl && profileStatus === "ready" && (
                <ExternalLink href={readmeUrl} label={copy.openReadme} />
              )}
              {profileStatus === "ready" && profileUrl ? (
                <ExternalLink href={profileUrl} label={copy.openProfile} />
              ) : (
                <p>{copy.profileLinkPending}</p>
              )}
            </div>
          </div>

          <div className="ux-missing-fields">
            <h4>{copy.testHeading}</h4>
            <p>{copy.testInstruction}</p>
            <ul>
              {copy.testChecks.map((check) => (
                <li key={check}>{check}</li>
              ))}
            </ul>
          </div>
        </details>
      </section>

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

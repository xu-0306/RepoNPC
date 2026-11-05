import { chromeLocale, type LanguageTag } from "../../i18n/languages";
import { InfoParagraphs } from "./InfoParagraphs";
import "../../p4-w3.css";
import type { ChangeEvent } from "react";

import { githubAccount, verifiedPagesMarkdown } from "./sharing";
import { sectionRef, sectionTitle } from "./sharingSections";

export type GitHubShareGuideProps = {
  locale: LanguageTag;
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
  /** True once a Pages URL has been saved (verified or not). */
  pagesConfigured?: boolean;
  /**
   * Where the next export sends live chat: a string when live chat is set up,
   * null when it is off. Undefined (an older server) shows no status line.
   */
  liveChatOrigin?: string | null;
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
  readmeStatus: {
    verified: string;
    notSaved: string;
    unverified: string;
  };
  liveChatStatus: { on: string; off: string };
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

const COPY: Record<ReturnType<typeof chromeLocale>, GuideCopy> = {
  "zh-TW": {
    title: sectionTitle("profile", "GitHub 個人頁"),
    subtitle:
      "下載 README.md。開啟下方的 GitHub 個人頁專案連結。上傳下載的 README.md。卡片圖片來自已核對的 Pages 網站。點擊卡片即可開啟對話網站。",
    downloadReadme: "下載 README.md",
    previewReadme: "預覽 README 內容",
    readmePreviewHelp:
      "這裡顯示 README.md 的文字。用鍵盤捲動可查看介紹、專案和連結。下載時會再次核對內容。",
    readmeContents:
      "檔案包含公開介紹、專案連結和 NPC 卡片。卡片可開啟對話。內容來自已套用並核對的 Pages 網站。尚未套用的草稿不會加入。",
    readmePlacement:
      "在 GitHub 建立與帳號同名的公開專案。將 README.md 上傳到該專案的最外層，即可在個人頁顯示。",
    readmeReady:
      "下載時會再次核對內容和卡片。等候下載完成。再到 GitHub 上傳 README.md。",
    readmeUnavailable:
      "先上傳 Pages 網站。再按「核對 Pages 網站」。核對成功後，即可下載 README.md 或複製卡片文字。卡片圖片可先在下方下載。",
    readmeStatus: {
      verified: "已核對",
      notSaved: `請先完成${sectionRef("zh-TW", "pages")}。儲存 Pages 網址。下載網站。將網站上傳到 GitHub。按「核對 Pages 網站」。`,
      unverified: `Pages 網址已儲存，但還沒核對。上傳最新網站。等候 Pages 更新。到${sectionRef("zh-TW", "pages")}按「核對 Pages 網站」。`,
    },
    liveChatStatus: {
      on: "即時聊天：已開啟。",
      off: "即時聊天：未開啟。訪客會看到常見問答和「休息中」訊息。",
    },
    existingReadme:
      "已有 README？先保留原文。可用下方的複製按鈕加入卡片。上傳完整檔案前，先比較內容。RepoNPC 不會自動覆寫 GitHub README。",
    stageProfile: "同名 GitHub 專案",
    stageCard: "上傳卡片",
    stageReadme: "README",
    accountLabel: "GitHub 帳號",
    accountHelp:
      "輸入 GitHub 帳號或個人頁網址。GitHub 專案用來存放檔案。這裡只查公開資料。不會登入帳號或建立專案。",
    accountPlaceholder: "輸入 GitHub 帳號",
    accountNotEntered: "尚未輸入帳號",
    checkProfile: "檢查同名 GitHub 專案",
    profileStatus: {
      unchecked:
        "尚未檢查同名 GitHub 專案。有 GitHub 帳號後，仍需準備個人頁的 README。",
      ready:
        "已找到同名公開專案和最外層的 README.md。接著下載卡片。再上傳卡片。",
      missing:
        "找不到同名公開專案。帳號可能仍存在，也可能有私人專案。已建立專案時，請確認名稱。再確認 Public（公開）設定。尚未建立時，請依下方步驟操作。",
      missing_readme:
        "已找到同名公開專案，但最外層沒有 README.md。開啟下方的 GitHub 專案連結。上傳下載的 README.md。",
      unavailable:
        "目前無法檢查同名專案。GitHub 可能限制存取，或暫時無法使用。請稍後重試。帳號和專案可能仍存在。",
    },
    repositoryDetails: "這一步檢查的目標",
    publicRepository: "個人頁使用的 GitHub 專案",
    rootReadme: "個人頁說明檔",
    createProfileHeading: "尚未建立同名 GitHub 專案？",
    createProfileIntro:
      "建立與帳號同名的公開 GitHub 專案。這裡用來存放 README 和卡片。",
    repositoryName: "在 Repository name（專案名稱）填入",
    choosePublic: "確認 Owner（擁有者）是你的帳號。選擇 Public（公開）。",
    addReadme: "勾選 Add a README file（新增說明檔）。",
    createRepository: "按 Create repository（建立專案）。回到這裡重新檢查。",
    existingRepositoryReadme:
      "專案已存在。開啟下方的 GitHub 專案連結。上傳下載的 README.md。",
    openRepository: "開啟 GitHub 個人頁專案",
    openCreatePage: "在 GitHub 建立個人頁專案",
    openReadme: "開啟 GitHub 個人頁 README",
    openProfile: "查看 GitHub 帳號頁",
    verifyPages: `前往${sectionRef("zh-TW", "pages")}上傳並核對 Pages 網站`,
    cardIntro:
      "下載卡片。開啟下方的 GitHub 卡片上傳頁。上傳卡片到第一步的專案最外層。",
    filenameLabel: "建議上傳檔名（專案最外層）",
    filenameMissing: "尚未提供檔名",
    cardReady: "卡片已準備好，可以下載。",
    cardNotReady: "按頁面上方的「預覽作品集與卡片」。圖片產生後即可下載。",
    downloadCard: "下載卡片",
    downloadDisabled: "按頁面上方的「預覽作品集與卡片」。圖片產生後即可下載。",
    checkImage: "檢查圖片是否已上傳",
    imageStatus: {
      unchecked: "尚未檢查圖片。上傳到 GitHub 後，按「檢查圖片是否已上傳」。",
      ready: "已找到同名專案中的卡片圖片。最後請到個人頁確認新卡片是否出現。",
      missing:
        "尚未找到卡片圖片。確認檔名與上方相同。將圖片上傳到專案最外層。完成 GitHub 要求的審核後，再回來檢查。",
      unavailable:
        "目前無法檢查圖片。GitHub 可能限制存取，或暫時無法使用。請稍後重試。也可開啟下方的 GitHub 專案連結查看圖片。",
    },
    imageReadyNote: "圖片已找到。接著將卡片文字加入 GitHub 個人頁介紹。",
    uploadStepsHeading: "在 GitHub 依序操作",
    uploadSteps: [
      "開啟下方的 GitHub 卡片上傳頁。",
      "選擇剛下載的圖片。保留上方顯示的檔名。",
      "按 GitHub 的 Commit changes（儲存變更）。完成 GitHub 要求的審核後，再回來檢查圖片。",
    ],
    protectedBranch:
      "GitHub 可能要求審核變更。等候變更加入主要版本後，才算完成上傳。",
    readmeIntro:
      "複製下方的卡片文字。開啟 GitHub 個人頁 README 連結。按鉛筆按鈕。將文字貼到想顯示卡片的位置。保留原有介紹。",
    markdownPreviewHeading: "已核對 Pages 網站的 README 文字",
    markdownLabel: "複製下方這段文字",
    markdownReady: "要貼進 README.md 的文字已準備好，可以複製。",
    markdownMissing: `還沒有可複製的內容。請在${sectionRef("zh-TW", "pages")}填入完整 Pages 網址。網址結尾須有 /。核對網站後，卡片文字就會出現。卡片圖片可先下載。`,
    copyMarkdown: "複製要貼進 README 的文字",
    preserveReadmeHeading: "在 README 保留原文",
    preserveReadmeSteps: [
      "開啟 GitHub 個人頁 README 連結。按鉛筆按鈕。",
      "貼入上方複製的內容。保留原有介紹。",
      "按 Preview（預覽）。確認圖片和連結。按 Commit changes（儲存變更）。",
    ],
    profileLinkPending: "請先完成第一步。確認同名公開專案和 README.md。",
    testHeading: "從 GitHub 實際查看",
    testInstruction:
      "儲存後，開啟 GitHub 帳號頁連結。確認卡片出現在個人介紹。點擊卡片。進入對話網站後，試問一個問題。",
    testChecks: [
      "圖片可見是第一個檢查。",
      "README 引用正確是第二個檢查。",
      "確認對話網站能回答問題。電腦和所需模型必須保持運作，訪客才能聊天。",
    ],
    busy: "正在處理中…",
    linkUnavailable: "填入有效 GitHub 帳號後才會顯示連結。",
    notCheckedAction: "在 GitHub 完成後，回來按「檢查同名 GitHub 專案」。",
  },
  en: {
    title: sectionTitle("profile", "GitHub profile"),
    subtitle:
      "Download README.md. Open the GitHub profile repository link below. Upload the downloaded README.md. The card image comes from your checked Pages site. Select the card to open your chat website.",
    downloadReadme: "Download README.md",
    previewReadme: "Preview README content",
    readmePreviewHelp:
      "This shows the README.md text. Scroll with your keyboard to check the introduction, projects and links. Download checks the content again.",
    readmeContents:
      "The file includes your public introduction, project links and NPC card. The card opens chat. Content matches your applied and checked Pages site. Unapplied drafts stay out.",
    readmePlacement:
      "Create a public repository with the same name as your GitHub account. Upload README.md outside all folders to show it on your profile.",
    readmeReady:
      "Download checks the content and card again. Wait for the download to finish. Then upload README.md on GitHub.",
    readmeUnavailable:
      "Upload your Pages site first. Select Check Pages site. After the check succeeds, download README.md or copy the card text. You can download the card image below now.",
    readmeStatus: {
      verified: "Verified",
      notSaved: `Finish ${sectionRef("en", "pages")} first. Save your Pages URL. Download the site. Upload the site to GitHub. Select Check Pages site.`,
      unverified: `Your Pages URL is saved but not checked yet. Upload the latest site. Wait for Pages to update. Select Check Pages site in ${sectionRef("en", "pages")}.`,
    },
    liveChatStatus: {
      on: "Live chat: on.",
      off: "Live chat: off. Visitors see the FAQ and a resting message.",
    },
    existingReadme:
      "Already have a README? Keep its text first. Use the copy button below to add the card. Compare content before uploading a complete file. RepoNPC never overwrites your GitHub README automatically.",
    stageProfile: "Matching repository",
    stageCard: "Upload card",
    stageReadme: "README",
    accountLabel: "GitHub account",
    accountHelp:
      "Enter your GitHub username or profile URL. A repository is a GitHub project that stores files. This step only checks public information. It does not sign in or create a repository.",
    accountPlaceholder: "Enter a GitHub account",
    accountNotEntered: "No account entered",
    checkProfile: "Check matching repository",
    profileStatus: {
      unchecked:
        "RepoNPC has not checked the matching repository. Having a GitHub account does not mean its profile README is ready.",
      ready:
        "Found your matching public repository and README.md outside all folders. Download the card next. Then upload the card.",
      missing:
        "No matching public repository was found. Your account or a private repository may still exist. If you created it, check its name. Then check its Public setting. Otherwise, follow the steps below.",
      missing_readme:
        "Found your matching public repository, but README.md is missing outside its folders. Open the GitHub repository link below. Upload your downloaded README.md.",
      unavailable:
        "Cannot check your matching repository now. GitHub may limit access or be temporarily unavailable. Try again later. Your account and repository may still exist.",
    },
    repositoryDetails: "What this step checks",
    publicRepository: "Repository used for your profile",
    rootReadme: "Profile README",
    createProfileHeading: "No matching repository yet?",
    createProfileIntro:
      "Create a public GitHub repository with the same name as your account. It stores your README and card.",
    repositoryName: "Enter this Repository name:",
    choosePublic: "Check that Owner shows your account. Select Public.",
    addReadme: "Select Add a README file.",
    createRepository: "Select Create repository. Return here to check again.",
    existingRepositoryReadme:
      "The repository exists. Open the GitHub repository link below. Upload your downloaded README.md.",
    openRepository: "Open GitHub profile repository",
    openCreatePage: "Create the repository on GitHub",
    openReadme: "Open GitHub profile README",
    openProfile: "View GitHub account page",
    verifyPages: `Go to ${sectionRef("en", "pages")} to upload and check your Pages site`,
    cardIntro:
      "Download the card. Open the GitHub card upload page below. Upload the card outside all folders in the step-one repository.",
    filenameLabel: "Suggested filename (outside all folders)",
    filenameMissing: "No filename supplied",
    cardReady: "The card is ready to download.",
    cardNotReady:
      "Select Preview portfolio and card above. Download the image after it appears.",
    downloadCard: "Download card",
    downloadDisabled:
      "Select Preview portfolio and card above. Download the image after it appears.",
    checkImage: "Check the uploaded image",
    imageStatus: {
      unchecked:
        "RepoNPC has not checked the image. After uploading it to GitHub, select Check the uploaded image.",
      ready:
        "Found the card image in your matching repository. Finally, check your profile for the updated card.",
      missing:
        "The card image was not found. Check that its filename matches the name above. Upload it outside all folders. Complete any GitHub review before checking again.",
      unavailable:
        "Cannot check the image now. GitHub may limit access or be temporarily unavailable. Try again later. You can also open the GitHub repository link below to view the image.",
    },
    imageReadyNote:
      "The image was found. Next, add the card text to your GitHub profile introduction.",
    uploadStepsHeading: "Use these GitHub controls",
    uploadSteps: [
      "Open the GitHub card upload page below.",
      "Choose the downloaded image. Keep the filename shown above.",
      "Select Commit changes on GitHub. Complete any GitHub review before returning to check the image.",
    ],
    protectedBranch:
      "GitHub may require a review. Wait until your change joins the main version before treating the upload as complete.",
    readmeIntro:
      "Copy the card text below. Open the GitHub profile README link. Select the pencil button. Paste the text where you want the card. Keep your existing introduction.",
    markdownPreviewHeading: "README text for the verified Pages site",
    markdownLabel: "Copy the text below",
    markdownReady: "The text for README.md is ready to copy.",
    markdownMissing: `Nothing is ready to copy yet. Enter your full Pages URL in ${sectionRef("en", "pages")}. End the URL with /. Check the site to show the card text. You can download the card image now.`,
    copyMarkdown: "Copy text for README",
    preserveReadmeHeading: "Keep existing README text",
    preserveReadmeSteps: [
      "Open the GitHub profile README link. Select the pencil button.",
      "Paste the copied text. Keep your existing introduction.",
      "Select Preview. Check the image and link. Select Commit changes.",
    ],
    profileLinkPending:
      "Complete step one first to confirm the matching public repository and README.md.",
    testHeading: "View the result on GitHub",
    testInstruction:
      "After saving, open the GitHub account page link. Check that your card appears in your introduction. Select the card. Ask a question on the chat website.",
    testChecks: [
      "A visible image is the first check.",
      "A correct README reference is the second check.",
      "Check that the chat website answers a question. Keep your computer and required models running so visitors can chat.",
    ],
    busy: "Working…",
    linkUnavailable: "Enter a valid GitHub account to show the link.",
    notCheckedAction:
      "After finishing on GitHub, return here. Select Check matching repository.",
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
  pagesConfigured = false,
  liveChatOrigin,
  onAccountChange,
  onCheckProfile,
  onCheckImage,
  onDownload,
  onDownloadReadme,
  onPreviewReadme,
  readmePreview,
  onCopy,
}: GitHubShareGuideProps) {
  const copy = COPY[chromeLocale(locale)];
  const accountIsEmpty = account.trim().length === 0;
  const normalizedAccount = githubAccount(account);
  const uploadUrl = normalizedAccount
    ? `https://github.com/${normalizedAccount}/${normalizedAccount}/upload`
    : "https://github.com/new";
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
          ⓘ{" "}
          {chromeLocale(locale) === "zh-TW" ? "分享方式" : "How sharing works"}
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
            ⓘ {chromeLocale(locale) === "zh-TW" ? "檔案內容" : "File contents"}
          </summary>
          <InfoParagraphs locale={locale} text={copy.readmeContents} />
          <InfoParagraphs
            locale={locale}
            text={pagesReady ? copy.readmeReady : copy.readmeUnavailable}
          />
        </details>
        <div className="publication-actions">
          <ExternalLink
            href={
              normalizedAccount
                ? `https://github.com/${normalizedAccount}/${normalizedAccount}`
                : "https://github.com/new"
            }
            label={copy.openRepository}
          />
          <ExternalLink
            href={uploadUrl}
            label={
              chromeLocale(locale) === "zh-TW"
                ? "開啟 GitHub README 上傳頁"
                : "Open the GitHub README upload page"
            }
          />
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
            ? copy.readmeStatus.verified
            : pagesConfigured
              ? copy.readmeStatus.unverified
              : copy.readmeStatus.notSaved}
        </p>
        {liveChatOrigin !== undefined && (
          <p data-testid="live-chat-status" role="status">
            {liveChatOrigin ? copy.liveChatStatus.on : copy.liveChatStatus.off}
          </p>
        )}
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
          {chromeLocale(locale) === "zh-TW" ? "卡片 → README" : "Card → README"}
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
                <ExternalLink
                  href={createUrl ?? "https://github.com/new"}
                  label={copy.openCreatePage}
                />
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
              <ExternalLink
                href={
                  repositoryUrl ??
                  (normalizedAccount
                    ? `https://github.com/${normalizedAccount}/${normalizedAccount}`
                    : "https://github.com/new")
                }
                label={copy.openRepository}
              />
              <ExternalLink
                href={createUrl ?? "https://github.com/new"}
                label={copy.openCreatePage}
              />
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
            <ExternalLink
              href={uploadUrl}
              label={
                chromeLocale(locale) === "zh-TW"
                  ? "開啟 GitHub 卡片上傳頁"
                  : "Open the GitHub card upload page"
              }
            />
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
              <ExternalLink
                href={
                  normalizedAccount
                    ? `https://github.com/${normalizedAccount}`
                    : "https://github.com/new"
                }
                label={copy.openProfile}
              />
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

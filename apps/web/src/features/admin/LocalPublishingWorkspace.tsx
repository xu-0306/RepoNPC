import "../../p4-w3.css";
import { useEffect, useRef, useState } from "react";
import { guidedErrorMessage } from "./guidedOnboarding";
import { githubRateLimitMessage } from "./githubRetry";
import { CoverageFaqPanel } from "./CoverageFaqPanel";
import type { ClaimKind } from "./ClaimEditor";
import type {
  AdminLocale,
  AdminPreview,
  PreviewProfile,
} from "./AdminWorkspace";
import type { AnalysisSelectionView } from "./AnalysisSelectionPanel";
import { Base64PngCanvas } from "./Base64PngCanvas";
import {
  GitHubShareGuide,
  type GitHubShareGuideProps,
} from "./GitHubShareGuide";
import {
  CARD_FILENAME,
  githubAccount,
  previewInputsMatch,
  safeShareFields,
} from "./sharing";
import { VisitorGatewayPanel } from "./VisitorGatewayPanel";
import { AppearancePanel, type SceneAppearanceState } from "./AppearancePanel";
import { PagesSharePanel, type PagesSharingState } from "./PagesSharePanel";

export interface LocalDraftBody {
  content: string;
  sprite_base64: string | null;
  revision: string | null;
}
interface PublicationStatus {
  state: "idle" | "preparing" | "ready" | "failed";
  index_ready: boolean;
  draft_changed: boolean;
  error_code: string | null;
  retry_at: string | null;
  revision: string | null;
  active_bundle_id: string | null;
  scene_state?: SceneAppearanceState | null;
}
interface ShareMetadata {
  account: string;
  profile_status: GitHubShareGuideProps["profileStatus"];
  image_status: GitHubShareGuideProps["imageStatus"];
  repository_url: string;
  profile_url: string;
  readme_url: string;
  create_url: string;
}
type Request = <T>(path: string, options?: RequestInit) => Promise<T>;

function publicationErrorMessage(
  locale: AdminLocale,
  error: unknown,
  retryAt: string | null = null,
): string {
  const zh = locale === "zh-TW";
  const code =
    error instanceof TypeError
      ? "REQUEST_FAILED"
      : error instanceof Error
        ? error.message
        : "";
  switch (code) {
    case "SERVICE_NOT_READY":
    case "REQUEST_FAILED":
    case "RATE_LIMITED":
      return guidedErrorMessage(locale, code);
    case "GITHUB_RATE_LIMITED":
      return githubRateLimitMessage(
        locale,
        retryAt === null
          ? undefined
          : Math.ceil((Date.parse(retryAt) - Date.now()) / 1000),
      );
    case "GITHUB_ERROR":
    case "GITHUB_TIMEOUT":
      return zh
        ? "GitHub 暫時無法使用，請稍後再試。"
        : "GitHub is temporarily unavailable; try again later.";
    case "NOT_FOUND":
      return zh
        ? "找不到儲存庫或無法存取。"
        : "Repository not found or inaccessible.";
    case "ARCHIVED_NOT_ALLOWED":
      return zh
        ? "儲存庫已封存，無法準備 NPC。"
        : "The repository is archived and cannot be used to prepare the NPC.";
    case "ARCHIVE_TOO_LARGE":
      return zh
        ? "儲存庫封存檔超過大小限制。"
        : "The repository archive exceeds the size limit.";
    case "ARCHIVE_INVALID":
      return zh
        ? "儲存庫封存檔無效，請稍後再試。"
        : "The repository archive is invalid; try again later.";
    case "ARCHIVE_UNSAFE":
      return zh
        ? "儲存庫封存檔未通過安全檢查。"
        : "The repository archive failed safety checks.";
    case "PORTFOLIO_CONFLICT":
      return zh
        ? "草稿版本已變更。請先保留目前編輯內容，再重新載入並核對最新草稿後儲存；不要直接覆蓋。"
        : "The draft version changed. Keep a copy of your edits, then reload and compare the latest draft before saving; do not overwrite it blindly.";
    case "SHARING_CONFLICT":
    case "SHARING_CONFIGURATION_INVALID":
    case "SHARING_EXPORT_INVALID":
    case "SHARING_EXPORT_UNAVAILABLE":
    case "SHARING_VERIFICATION_FAILED":
    case "SHARING_VERIFICATION_UNAVAILABLE":
      return zh
        ? "README 尚未取得。請到第 3 段確認 Pages 網址，重新上傳目前網站並核對；也可沿用卡片下載、上傳與複製區塊。原有 README 不會被改動。"
        : "README could not be retrieved. Check the Pages URL in section 3, upload the current site and verify it again. You can also use the card download, upload and copy steps. Your existing README is unchanged.";
    case "SHARING_EXPORT_TOO_LARGE":
      return zh
        ? "README 超過 GitHub 可顯示的 500 KiB 上限。請縮減公開介紹或作品文字，套用後重新匯出、上傳並核對 Pages 網站，再重試。原有 README 不會被改動。"
        : "README exceeds GitHub's 500 KiB display limit. Shorten the public introduction or project text, apply it, then export, upload and verify the Pages site again before retrying. Your existing README is unchanged.";
    case "PORTFOLIO_BUSY":
    case "EMBEDDING_REINDEX_ACTIVE":
      return zh
        ? "已有準備工作進行中。請等候下方狀態完成，或取消準備後再重試。"
        : "Preparation is already running. Wait for the status below to finish, or cancel preparation before retrying.";
    case "PORTFOLIO_MODEL_CHANGED":
    case "CHAT_PROBE_REQUIRED":
    case "EMBEDDING_PROBE_REQUIRED":
    case "EMBEDDING_REINDEX_STALE":
    case "MODEL_UNAVAILABLE":
      return zh
        ? "模型設定已變更或尚未就緒。請前往模型設定，重新測試並確認選用兩種模型，再返回準備 NPC。"
        : "Model settings changed or are not ready. Open model setup, retest and confirm both model selections, then return to prepare the NPC.";
    case "CONFIG_INVALID":
    case "VALIDATION_ERROR":
    case "PORTFOLIO_INVALID":
      return zh
        ? "草稿未通過驗證，目前輸入仍保留。請回到內容編輯，檢查必填欄位、雙語內容及確認狀態，再預覽並儲存。"
        : "The draft did not pass validation. Your input is kept. Return to content editing, check required fields, both languages and confirmations, then preview and save.";
    case "PORTFOLIO_ASSET_REQUIRED":
    case "ASSET_INVALID":
      return zh
        ? "角色素材缺少或無效。請到「角色與動畫」重新選擇並驗證素材，再返回預覽及儲存。"
        : "The character asset is missing or invalid. Open Character & animation, select and validate the asset, then return to preview and save.";
    case "PAYLOAD_TOO_LARGE":
      return zh
        ? "草稿或素材超過大小限制。請縮減草稿內容或在「角色與動畫」選擇符合限制的素材，再重試。"
        : "The draft or asset exceeds the size limit. Reduce the draft or choose an asset within the limits in Character & animation, then retry.";
    case "PORTFOLIO_WRITE_FAILED":
    case "PORTFOLIO_CORRUPT":
      return zh
        ? "本機草稿無法安全讀寫。請先保留目前編輯內容，檢查資料目錄的可用空間與存取權限，並到「維護」查看備份，再決定是否重試；不要刪除現有資料。"
        : "The local draft could not be read or written safely. Keep a copy of your edits, check data-directory space and access permissions, and review backups in Maintenance before retrying; do not delete existing data.";
    case "EMBEDDING_REINDEX_CANCELLED":
    case "EMBEDDING_REINDEX_INTERRUPTED":
      return zh
        ? "準備已取消或中斷。請確認本機服務與模型已就緒，再按「準備 NPC」重新開始。"
        : "Preparation was cancelled or interrupted. Check that the local service and models are ready, then select Prepare NPC to start again.";
    case "EMBEDDING_REINDEX_TIMEOUT":
      return zh
        ? "準備逾時。請檢查模型服務連線與電腦資源，確認服務恢復後再重試準備。"
        : "Preparation timed out. Check model-service connectivity and computer resources, then retry preparation once the service has recovered.";
    case "PORTFOLIO_PREPARE_FAILED":
    case "EMBEDDING_REINDEX_FAILED":
      return zh
        ? "準備未完成。請到「維護」查看服務狀態，並在模型設定測試所選模型；排除問題後再重試準備。"
        : "Preparation did not complete. Open Maintenance to check service status and test the selected models in model setup; retry preparation after resolving the problem.";
    default:
      return zh
        ? "操作未完成，目前無法確認原因，輸入仍保留。請先保留未儲存內容，再到「維護」查看服務狀態，確認後再重試。"
        : "Could not complete the operation; the cause is unknown and your input is kept. Keep a copy of unsaved content, open Maintenance to check service status, then retry after checking.";
  }
}

export function LocalPublishingWorkspace({
  locale,
  content,
  spriteBase64,
  revision,
  initialAccount,
  selection,
  request,
  onStored,
  onCreateDraft,
  onConfigureModels,
  repositories,
  onAddClaim,
  onActiveSceneChange,
  draftUnsaved = false,
  publicSharingAvailable = true,
}: {
  locale: AdminLocale;
  content: string;
  spriteBase64: string | null;
  revision: string | null;
  initialAccount: string;
  selection: AnalysisSelectionView | null;
  request: Request;
  onStored: (body: LocalDraftBody) => void;
  onCreateDraft: () => void;
  onConfigureModels?: () => void;
  repositories: string[];
  onAddClaim: (repository: string, kind: ClaimKind) => void;
  onActiveSceneChange?: (state: SceneAppearanceState | null) => void;
  draftUnsaved?: boolean;
  publicSharingAvailable?: boolean;
}) {
  const zh = locale === "zh-TW";
  const [preview, setPreview] = useState<AdminPreview | null>(null);
  const [status, setStatus] = useState<PublicationStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<{
    scope: "local" | "share" | "appearance";
    message: string;
    error?: boolean;
  } | null>(null);
  const [account, setAccount] = useState(
    githubAccount(initialAccount) ?? initialAccount,
  );
  const [pagesSharingState, setPagesSharingState] =
    useState<PagesSharingState | null>(null);
  const [metadata, setMetadata] = useState<ShareMetadata | null>(null);
  const [readmePreview, setReadmePreview] = useState<{
    key: string;
    text: string;
  } | null>(null);
  const mounted = useRef(true);
  const operationPending = useRef(false);
  const sceneGeneration = useRef(0);
  const pagesGeneration = useRef(0);
  const contentRef = useRef(content);
  contentRef.current = content;
  const spriteRef = useRef(spriteBase64);
  spriteRef.current = spriteBase64;
  const accountRef = useRef(account);
  accountRef.current = account;
  const onActiveSceneChangeRef = useRef(onActiveSceneChange);
  onActiveSceneChangeRef.current = onActiveSceneChange;
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    setPreview(null);
  }, [content, spriteBase64]);
  useEffect(() => {
    let closed = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      const generation = sceneGeneration.current;
      const sharingGeneration = pagesGeneration.current;
      const [statusResult, sharingResult] = await Promise.allSettled([
        request<PublicationStatus>("/api/admin/portfolio/status"),
        request<PagesSharingState>("/api/admin/sharing/state"),
      ]);
      if (!closed && sceneGeneration.current === generation) {
        setStatusLoading(false);
        if (statusResult.status === "fulfilled") {
          setStatus(statusResult.value);
          onActiveSceneChangeRef.current?.(
            statusResult.value.scene_state ?? null,
          );
        } else {
          setStatus(null);
          onActiveSceneChangeRef.current?.(null);
        }
        if (pagesGeneration.current === sharingGeneration) {
          setPagesSharingState(
            sharingResult.status === "fulfilled" ? sharingResult.value : null,
          );
        }
      }
      if (!closed) timer = setTimeout(() => void poll(), 3000);
    };
    void poll();
    return () => {
      closed = true;
      clearTimeout(timer);
    };
  }, [request]);
  useEffect(() => {
    try {
      const saved = JSON.parse(
        sessionStorage.getItem("reponpc.share.public") ?? "null",
      );
      if (saved && typeof saved === "object") {
        const safe = safeShareFields(
          typeof saved.account === "string" ? saved.account : "",
        );
        if (safe.account) setAccount(safe.account);
        try {
          if (Object.keys(safe).length > 0)
            sessionStorage.setItem(
              "reponpc.share.public",
              JSON.stringify(safe),
            );
          else sessionStorage.removeItem("reponpc.share.public");
        } catch {
          /* Optional public-field cleanup. */
        }
      }
    } catch {
      /* Optional public-field continuity. */
    }
  }, []);
  function remember(nextAccount: string) {
    const safe = safeShareFields(nextAccount);
    try {
      if (Object.keys(safe).length > 0)
        sessionStorage.setItem("reponpc.share.public", JSON.stringify(safe));
      else sessionStorage.removeItem("reponpc.share.public");
    } catch {
      /* Optional. */
    }
  }
  async function run(scope: "local" | "share", operation: () => Promise<void>) {
    if (operationPending.current) return;
    operationPending.current = true;
    setPending(true);
    setNotice(null);
    try {
      await operation();
    } catch (error) {
      if (mounted.current)
        setNotice({
          scope,
          error: true,
          message: publicationErrorMessage(locale, error),
        });
    } finally {
      operationPending.current = false;
      if (mounted.current) setPending(false);
    }
  }
  const body = {
    content,
    sprite_base64: spriteBase64,
    expected_revision: revision,
  };
  async function showPreview() {
    const result = await request<AdminPreview>("/api/admin/portfolio/preview", {
      method: "POST",
      body: JSON.stringify(body),
    });
    if (
      mounted.current &&
      previewInputsMatch(
        contentRef.current,
        spriteRef.current,
        content,
        spriteBase64,
      )
    )
      setPreview(result);
  }
  async function save(prepare: boolean) {
    const saved = await request<LocalDraftBody>("/api/admin/portfolio", {
      method: "PUT",
      body: JSON.stringify(body),
    });
    if (!mounted.current) return;
    onStored(saved);
    if (prepare) {
      try {
        const result = await request<PublicationStatus>(
          "/api/admin/portfolio/prepare",
          {
            method: "POST",
            body: JSON.stringify({
              expected_revision: saved.revision,
              selection_generation: selection?.selection.generation,
              confirmed: true,
            }),
          },
        );
        if (mounted.current) setStatus(result);
      } catch (error) {
        if (mounted.current)
          setNotice({
            scope: "local",
            error: true,
            message:
              (zh
                ? "草稿已儲存在本機，但尚無法確認 NPC 準備結果。"
                : "The draft was saved locally, but NPC preparation could not be confirmed. ") +
              publicationErrorMessage(locale, error),
          });
      }
    } else
      setNotice({
        scope: "local",
        message: zh
          ? "已儲存在本機；訪客內容尚未變更。"
          : "Saved locally. Visitor content has not changed.",
      });
  }
  async function checkProfile() {
    const chosen = githubAccount(account);
    if (!chosen)
      throw new Error(zh ? "請填 GitHub 帳號" : "Enter a GitHub account");
    const result = await request<ShareMetadata>(
      "/api/admin/portfolio/github-profile",
      {
        method: "POST",
        body: JSON.stringify({ account: chosen, filename: CARD_FILENAME }),
      },
    );
    if (mounted.current && githubAccount(accountRef.current) === chosen) {
      setAccount(chosen);
      setMetadata(result);
      remember(chosen);
    }
  }
  const selectedCard = preview?.cards?.[`light-${locale}`];
  async function download() {
    if (!selectedCard?.gif_base64) return;
    let image: Blob;
    if (selectedCard.gif_url) {
      const parsed = new URL(selectedCard.gif_url, window.location.href);
      if (
        parsed.origin !== window.location.origin ||
        !parsed.pathname.startsWith("/api/admin/assets/previews/")
      )
        throw new Error("Unexpected preview URL");
      const response = await fetch(parsed.href, {
        credentials: "same-origin",
        cache: "no-store",
      });
      if (!response.ok) throw new Error("Preview asset is unavailable");
      image = await response.blob();
    } else {
      const bytes = Uint8Array.from(atob(selectedCard.gif_base64), (c) =>
        c.charCodeAt(0),
      );
      image = new Blob([bytes], { type: "image/gif" });
    }
    const url = URL.createObjectURL(image);
    const link = document.createElement("a");
    link.href = url;
    link.download = CARD_FILENAME;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setNotice({
      scope: "share",
      message: zh
        ? `已交給瀏覽器下載 ${CARD_FILENAME}；請確認下載完成。`
        : `Browser download requested: ${CARD_FILENAME}. Check that it completed.`,
    });
  }
  const chosen = githubAccount(account);
  const verifiedPagesUrl = pagesSharingState?.verified
    ? pagesSharingState.pages_url
    : null;
  const readmeKey = `${locale}|${verifiedPagesUrl ?? ""}|${pagesSharingState?.verified_content_sha256 ?? ""}|${status?.active_bundle_id ?? ""}`;
  const readmeKeyRef = useRef(readmeKey);
  readmeKeyRef.current = readmeKey;
  async function loadReadme(previewOnly: boolean) {
    if (!verifiedPagesUrl) return;
    const requestedKey = readmeKey;
    const response = await fetch(`/api/admin/sharing/readme?locale=${locale}`, {
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!response.ok) {
      const failure = await response.json();
      throw new Error(failure?.error?.code ?? "SHARING_EXPORT_UNAVAILABLE");
    }
    if (
      response.headers.get("content-type") !== "text/markdown; charset=utf-8" ||
      response.headers.get("content-disposition") !==
        'attachment; filename="README.md"'
    )
      throw new Error("SHARING_EXPORT_INVALID");
    const file = await response.blob();
    if (!mounted.current || readmeKeyRef.current !== requestedKey) return;
    if (previewOnly) {
      const text = await file.text();
      if (!mounted.current || readmeKeyRef.current !== requestedKey) return;
      setReadmePreview({ key: requestedKey, text });
      setTimeout(() => {
        if (mounted.current && readmeKeyRef.current === requestedKey)
          document.getElementById("github-share-readme-preview")?.focus();
      }, 0);
      return;
    }
    const url = URL.createObjectURL(file);
    const link = document.createElement("a");
    link.href = url;
    link.download = "README.md";
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setNotice({
      scope: "share",
      message: zh
        ? "已交給瀏覽器下載 README.md；請確認下載完成，再上傳到與帳號同名的公開儲存庫根目錄。已有 README 時，先比較並保留原文。"
        : "Browser download requested: README.md. Confirm it completed, then upload it to the root of your public matching-name repository. Compare and keep existing README text first.",
    });
  }
  const links = chosen
    ? {
        repository: `https://github.com/${chosen}/${chosen}`,
        profile: `https://github.com/${chosen}`,
        create: `https://github.com/new?name=${encodeURIComponent(chosen)}&visibility=public`,
      }
    : null;
  const profiles = preview?.profile;
  const profile =
    profiles && typeof (profiles as PreviewProfile).display_name === "string"
      ? (profiles as PreviewProfile)
      : (profiles as Record<string, PreviewProfile> | undefined)?.[locale];
  const preparing = status?.state === "preparing";
  const prepareReason = pending
    ? zh
      ? "正在處理，請稍候。"
      : "An operation is in progress. Please wait."
    : preparing
      ? zh
        ? "正在準備 NPC，完成後才能再次更新。"
        : "The NPC preparation must finish before you can update it again."
      : !content
        ? zh
          ? "先從已確認內容建立草稿。"
          : "Create a draft from confirmed content first."
        : !selection?.eligible
          ? zh
            ? "先設定並測試兩種模型，再返回準備 NPC。預覽及儲存草稿仍可使用。"
            : "Set up and test both models, then return to prepare the NPC. Preview and saving a draft remain available."
          : null;
  const publicationMessage =
    status === null
      ? statusLoading
        ? zh
          ? "正在讀取本機發布狀態…"
          : "Loading local publication status…"
        : zh
          ? "目前無法確認本機發布狀態；請稍後重新檢查。"
          : "The local publication status is unknown right now; check again shortly."
      : preparing
        ? zh
          ? status.index_ready
            ? "正在本機準備，可離開此頁再回來。舊版本仍可使用。"
            : "正在本機準備，可離開此頁再回來。完成後就能試聊。"
          : status.index_ready
            ? "Preparing locally. You can return later; the previous version remains available."
            : "Preparing locally. You can return later and try chatting once it is ready."
        : status.state === "failed"
          ? zh
            ? "本次準備未完成；目前訪客版本仍維持不變。"
            : "This preparation did not complete; the current visitor version is unchanged."
          : status.draft_changed
            ? zh
              ? "本機草稿已變更，但尚未套用到目前訪客版本。"
              : "The local draft changed, but it has not been applied to the current visitor version."
            : status.index_ready
              ? zh
                ? "已有可試聊的本機版本。"
                : "A local version is available to try."
              : zh
                ? "尚未準備本機 NPC。"
                : "Local NPC has not been prepared.";
  const prepareNotice =
    !pending && !preparing && content && !selection?.eligible
      ? (prepareReason ?? "") +
        (zh ? "" : " ") +
        (zh
          ? "內容草稿會保留，完成後可返回準備 NPC。"
          : "RepoNPC keeps your content draft. Return here after setup to prepare the NPC.")
      : prepareReason;
  return (
    <div className="local-publication" lang={locale}>
      <header className="local-publication__heading">
        <p className="px-display">{zh ? "工作區／分享" : "WORKSHOP / SHARE"}</p>
        <h1>{zh ? "預覽與分享" : "Preview & share"}</h1>
        <nav aria-label={zh ? "預覽與分享步驟" : "Preview and sharing steps"}>
          <a
            aria-current="step"
            className="px-chip"
            href="#local-publication-heading"
          >
            {zh ? "01 預覽" : "01 Preview"}
          </a>
          <a className="px-chip" href="#publication-appearance">
            {zh ? "02 外觀（選填）" : "02 Appearance (optional)"}
          </a>
          <a className="px-chip" href="#visitor-gateway-heading">
            {zh ? "03 分享" : "03 Share"}
          </a>
        </nav>
      </header>
      <section
        className="publication-local px-panel"
        aria-labelledby="local-publication-heading"
      >
        <h2 id="local-publication-heading">
          {zh ? "1. 本機準備與試聊" : "1. Prepare and try locally"}
        </h2>
        <p>
          {zh
            ? "先預覽作品與卡片，再儲存草稿並準備 NPC。"
            : "Preview your portfolio and card, then save the draft and prepare the NPC."}
        </p>
        {!content && (
          <p>
            {zh
              ? "尚未建立內容草稿。先完成內容確認，再開始預覽。"
              : "No content draft yet. Finish confirming your content before previewing."}
          </p>
        )}
        {!content && (
          <button
            className="px-button px-button--primary"
            type="button"
            onClick={onCreateDraft}
          >
            {zh
              ? "從已確認內容建立草稿"
              : "Create draft from confirmed content"}
          </button>
        )}
        <div className="publication-actions publication-local__actions">
          <button
            className="px-button px-button--primary"
            type="button"
            disabled={pending || !content}
            onClick={() => void run("local", showPreview)}
          >
            {zh ? "預覽作品集與卡片" : "Preview portfolio and card"}
          </button>
          <button
            className="px-button px-button--secondary"
            type="button"
            disabled={!content}
            aria-disabled={pending || !content}
            onClick={() => {
              if (content) void run("local", () => save(false));
            }}
          >
            {zh ? "儲存本機草稿" : "Save local draft"}
          </button>
          <button
            className="px-button px-button--secondary"
            type="button"
            aria-describedby={
              prepareReason ? "local-prepare-reason" : undefined
            }
            disabled={pending || preparing || !content || !selection?.eligible}
            onClick={() => void run("local", () => save(true))}
          >
            {zh
              ? status?.index_ready
                ? "檢查專案並更新 NPC"
                : "準備 NPC 並套用"
              : status?.index_ready
                ? "Check projects and update NPC"
                : "Prepare and apply NPC"}
          </button>
          {preparing && (
            <button
              className="px-button px-button--secondary"
              type="button"
              disabled={pending}
              onClick={() =>
                void run("local", async () =>
                  setStatus(
                    await request<PublicationStatus>(
                      "/api/admin/portfolio/prepare",
                      { method: "DELETE" },
                    ),
                  ),
                )
              }
            >
              {zh ? "取消準備" : "Cancel preparation"}
            </button>
          )}
        </div>
        {notice?.scope === "local" && (
          <p
            className={notice.error ? "publication-notice" : undefined}
            role={notice.error ? "alert" : "status"}
          >
            {notice.message}
          </p>
        )}
        {(prepareNotice || !selection?.eligible) && (
          <div className="publication-status px-panel px-panel--inset">
            <p id="local-prepare-reason">{prepareNotice}</p>
            {!selection?.eligible && onConfigureModels && (
              <button
                className="px-button px-button--secondary"
                type="button"
                onClick={onConfigureModels}
              >
                {zh ? "前往設定模型" : "Set up models"}
              </button>
            )}
          </div>
        )}
        <p role="status">{publicationMessage}</p>
        {status?.error_code && (
          <p role="alert">
            {zh ? "上次準備未完成" : "Last preparation failed"}:{" "}
            {publicationErrorMessage(
              locale,
              new Error(status.error_code),
              status.retry_at,
            )}
          </p>
        )}
        {status?.index_ready && (
          <a
            className="px-button px-button--quiet publication-current-version"
            href="/"
            target="_blank"
            rel="noreferrer"
          >
            {zh
              ? "開啟目前版本並試聊"
              : "Open current version and try chatting"}
          </a>
        )}
        <p className="publication-impact">
          {zh
            ? "套用才會更新訪客看到的內容。"
            : "Applying updates visitor content."}
        </p>
        <details className="px-info publication-impact-details">
          <summary>
            ⓘ{" "}
            {zh
              ? "試聊與一般預覽的模型"
              : "Models used by try-chat and preview"}
          </summary>
          <p>
            {zh
              ? "試聊會使用已選模型。一般預覽不會使用模型。"
              : "Chat uses your selected models. Preview does not use models."}
          </p>
        </details>
        {profile && (
          <article>
            <h3>{profile.display_name}</h3>
            <p>{profile.headline}</p>
            <p>{profile.bio}</p>
            <p>{profile.greeting}</p>
          </article>
        )}
        {preview?.repositories?.map((repository) => (
          <article key={repository.slug}>
            <h3>{repository.slug}</h3>
            <p>{repository.role[locale]}</p>
            <p>{repository.summary[locale]}</p>
            {repository.claims.map((claim) => (
              <p key={claim.id}>{claim.statement[locale]}</p>
            ))}
          </article>
        ))}
        {preview?.character?.png_base64 && (
          <Base64PngCanvas
            width={64}
            height={64}
            state="idle"
            pngBase64={preview.character.png_base64}
            pngUrl={preview.character.png_url}
            label={
              zh ? "目前草稿角色動畫" : "Current draft character animation"
            }
            failureText={zh ? "角色預覽失敗" : "Character preview failed"}
          />
        )}
        {selectedCard?.png_base64 && (
          <Base64PngCanvas
            width={600}
            height={180}
            pngBase64={selectedCard.png_base64}
            pngUrl={selectedCard.png_url}
            label={
              zh
                ? "GitHub 卡片靜態預覽（下載為 GIF）"
                : "Static GitHub card preview (GIF download)"
            }
            failureText={zh ? "卡片預覽失敗" : "Card preview failed"}
          />
        )}
      </section>
      <details
        id="publication-appearance"
        className="publication-optional px-panel"
      >
        <summary>
          {zh ? "選填：調整訪客外觀" : "Optional: customize visitor appearance"}
        </summary>
        {notice?.scope === "appearance" && (
          <p className="publication-notice" role="alert">
            {notice.message}
          </p>
        )}
        {status?.scene_state ? (
          <AppearancePanel
            locale={locale}
            initialState={status.scene_state}
            request={request}
            applyDisabled={
              draftUnsaved || revision !== status.scene_state.draft_revision
            }
            onStateChange={(updated) => {
              sceneGeneration.current += 1;
              pagesGeneration.current += 1;
              setPagesSharingState(null);
              setStatus((current) =>
                current ? { ...current, scene_state: updated } : current,
              );
              onActiveSceneChangeRef.current?.(updated);
              const contentAtApply = contentRef.current;
              const spriteAtApply = spriteRef.current;
              void request<LocalDraftBody>("/api/admin/portfolio")
                .then((saved) => {
                  if (!mounted.current) return;
                  if (
                    previewInputsMatch(
                      contentRef.current,
                      spriteRef.current,
                      contentAtApply,
                      spriteAtApply,
                    )
                  ) {
                    onStored(saved);
                  } else {
                    setNotice({
                      scope: "appearance",
                      message: zh
                        ? "外觀已套用；草稿在讀回期間有新編輯，請重新載入並核對草稿後再儲存。"
                        : "Appearance applied. The draft changed during refresh; reload and review it before saving.",
                    });
                  }
                })
                .catch(() => {
                  if (mounted.current)
                    setNotice({
                      scope: "appearance",
                      message: zh
                        ? "外觀已套用，但草稿版本讀回失敗；請重新載入後再儲存。"
                        : "Appearance applied, but the saved draft could not be refreshed. Reload before saving.",
                    });
                });
            }}
          />
        ) : (
          <section
            className="publication-local px-panel"
            aria-labelledby="scene-appearance-title"
          >
            <h2 id="scene-appearance-title">
              {zh ? "訪客外觀" : "Visitor appearance"}
            </h2>
            <p>
              {zh
                ? "先準備本機 NPC，再預覽及套用外觀。"
                : "Prepare the local NPC before previewing and applying appearance."}
            </p>
          </section>
        )}
      </details>
      <VisitorGatewayPanel
        locale={locale}
        request={request}
        publicSharingAvailable={publicSharingAvailable}
      />
      <PagesSharePanel
        locale={locale}
        request={request}
        observedState={pagesSharingState}
        onStateChange={(updated) => {
          pagesGeneration.current += 1;
          setPagesSharingState(updated);
        }}
        onOperationPendingChange={(value) => {
          if (value) pagesGeneration.current += 1;
        }}
      />
      <GitHubShareGuide
        locale={locale}
        account={account}
        verifiedPagesUrl={verifiedPagesUrl}
        profileStatus={metadata?.profile_status ?? "unchecked"}
        imageStatus={metadata?.image_status ?? "unchecked"}
        repositoryUrl={metadata?.repository_url ?? links?.repository ?? null}
        profileUrl={metadata?.profile_url ?? links?.profile ?? null}
        readmeUrl={metadata?.readme_url ?? links?.repository ?? null}
        createUrl={metadata?.create_url ?? links?.create ?? null}
        filename={CARD_FILENAME}
        cardReady={!!selectedCard?.gif_base64}
        busy={pending}
        notice={notice?.scope === "share" ? notice.message : ""}
        onAccountChange={(value) => {
          setAccount(value);
          setMetadata(null);
          remember(value);
        }}
        onCheckProfile={() => void run("share", checkProfile)}
        onCheckImage={() => void run("share", checkProfile)}
        onDownload={() => void run("share", download)}
        onDownloadReadme={() => void run("share", () => loadReadme(false))}
        onPreviewReadme={() => void run("share", () => loadReadme(true))}
        readmePreview={
          readmePreview?.key === readmeKey ? readmePreview.text : null
        }
        onCopy={(markdown) =>
          void run("share", async () => {
            await navigator.clipboard.writeText(markdown);
            setNotice({
              scope: "share",
              message: zh
                ? "已複製。請貼入 README、預覽並儲存，再從 GitHub 點擊測試。"
                : "Copied. Paste into README, preview and save, then test the card from GitHub.",
            });
          })
        }
      />
      <details className="publication-optional px-panel">
        <summary>
          {zh
            ? "選填：檢查涵蓋範圍與審核常見問答"
            : "Optional: check coverage and review FAQ"}
        </summary>
        <CoverageFaqPanel
          locale={locale}
          request={request}
          repositories={repositories}
          bundleId={status?.active_bundle_id ?? null}
          draftChanged={status?.draft_changed ?? false}
          onAddClaim={onAddClaim}
        />
      </details>
    </div>
  );
}

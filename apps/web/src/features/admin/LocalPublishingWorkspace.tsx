import { useEffect, useRef, useState } from "react";
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
  cardMarkdown,
  githubAccount,
  previewInputsMatch,
  publicVisitorUrl,
  safeShareFields,
} from "./sharing";

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
  revision: string | null;
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
}) {
  const zh = locale === "zh-TW";
  const [preview, setPreview] = useState<AdminPreview | null>(null);
  const [status, setStatus] = useState<PublicationStatus | null>(null);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const [account, setAccount] = useState(
    githubAccount(initialAccount) ?? initialAccount,
  );
  const [publicUrl, setPublicUrl] = useState("");
  const [metadata, setMetadata] = useState<ShareMetadata | null>(null);
  const mounted = useRef(true);
  const contentRef = useRef(content);
  contentRef.current = content;
  const spriteRef = useRef(spriteBase64);
  spriteRef.current = spriteBase64;
  const accountRef = useRef(account);
  accountRef.current = account;
  const publicUrlRef = useRef(publicUrl);
  publicUrlRef.current = publicUrl;
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
      try {
        const current = await request<PublicationStatus>(
          "/api/admin/portfolio/status",
        );
        if (!closed) setStatus(current);
      } catch {
        if (!closed) setStatus(null);
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
          typeof saved.publicUrl === "string" ? saved.publicUrl : "",
        );
        if (safe.account) setAccount(safe.account);
        if (safe.publicUrl) setPublicUrl(safe.publicUrl);
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
  function remember(nextAccount: string, nextUrl: string) {
    const safe = safeShareFields(nextAccount, nextUrl);
    try {
      if (Object.keys(safe).length > 0)
        sessionStorage.setItem("reponpc.share.public", JSON.stringify(safe));
      else sessionStorage.removeItem("reponpc.share.public");
    } catch {
      /* Optional. */
    }
  }
  async function run(operation: () => Promise<void>) {
    if (pending) return;
    setPending(true);
    setNotice("");
    try {
      await operation();
    } catch (error) {
      if (mounted.current)
        setNotice(
          `${zh ? "操作未完成，請檢查輸入內容或服務狀態後重試" : "Could not complete. Check your input or service status and try again"}: ${error instanceof Error ? error.message : "REQUEST_FAILED"}`,
        );
    } finally {
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
    } else
      setNotice(
        zh
          ? "已儲存在本機；訪客內容尚未變更。"
          : "Saved locally. Visitor content has not changed.",
      );
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
      remember(chosen, publicUrlRef.current);
    }
  }
  const selectedCard = preview?.cards?.[`light-${locale}`];
  function download() {
    if (!selectedCard?.gif_base64) return;
    const bytes = Uint8Array.from(atob(selectedCard.gif_base64), (c) =>
      c.charCodeAt(0),
    );
    const url = URL.createObjectURL(new Blob([bytes], { type: "image/gif" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = CARD_FILENAME;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setNotice(
      zh
        ? `已交給瀏覽器下載 ${CARD_FILENAME}；請確認下載完成。`
        : `Browser download requested: ${CARD_FILENAME}. Check that it completed.`,
    );
  }
  const chosen = githubAccount(account);
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
  const publicationMessage =
    status === null
      ? zh
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
  return (
    <div className="local-publication">
      <section
        className="admin-surface"
        aria-labelledby="local-publication-heading"
      >
        <h2 id="local-publication-heading">
          {zh ? "預覽、試聊與分享" : "Preview, try and share"}
        </h2>
        <p>
          {zh
            ? "先預覽作品與卡片、儲存草稿，再準備或更新 NPC；完成後就能在這台電腦試聊。分享到 GitHub 是下一步：GitHub 顯示卡片，訪客點開後才會前往你的 RepoNPC 網站。"
            : "Preview your portfolio and card, save the draft, then prepare or update the NPC. Once it is ready, try it on this computer. Sharing on GitHub comes next: GitHub shows the card, and visitors click it to open your RepoNPC site."}
        </p>
        {!content && (
          <p>
            {zh
              ? "尚未建立內容草稿。先完成內容確認，再開始預覽。"
              : "No content draft yet. Finish confirming your content before previewing."}
          </p>
        )}
        {!content && (
          <button type="button" onClick={onCreateDraft}>
            {zh
              ? "從已確認內容建立草稿"
              : "Create draft from confirmed content"}
          </button>
        )}
        <div className="admin-workspace__actions">
          <button
            type="button"
            disabled={pending || !content}
            onClick={() => void run(showPreview)}
          >
            {zh ? "預覽作品集與卡片" : "Preview portfolio and card"}
          </button>
          <button
            type="button"
            disabled={pending || !content}
            onClick={() => void run(() => save(false))}
          >
            {zh ? "儲存本機草稿" : "Save local draft"}
          </button>
          <button
            type="button"
            disabled={pending || preparing || !content || !selection?.eligible}
            onClick={() => void run(() => save(true))}
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
              type="button"
              disabled={pending}
              onClick={() =>
                void run(async () =>
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
        {!selection?.eligible && (
          <p>
            {zh
              ? "請先在模型設定選好並測試回答模型和資料查找模型。"
              : "Select and test both the answer and retrieval models first."}
          </p>
        )}
        <p role="status">{publicationMessage}</p>
        {status?.error_code && (
          <p role="alert">
            {zh ? "上次準備未完成" : "Last preparation failed"}:{" "}
            {status.error_code}
          </p>
        )}
        {status?.index_ready && (
          <a href="/" target="_blank" rel="noreferrer">
            {zh
              ? "開啟目前版本並試聊"
              : "Open current version and try chatting"}
          </a>
        )}
        <p>
          {zh
            ? "套用才會更新訪客看到的內容。試聊會使用已選模型；一般預覽不會。"
            : "Applying updates visitor content. Chat uses your selected models; preview does not."}
        </p>
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
            label={
              zh
                ? "GitHub 卡片靜態預覽（下載為 GIF）"
                : "Static GitHub card preview (GIF download)"
            }
            failureText={zh ? "卡片預覽失敗" : "Card preview failed"}
          />
        )}
        {!publicVisitorUrl(publicUrl) && (
          <p>
            {zh
              ? "目前沒有公開網址也能先完成本機試聊和卡片圖片。若要讓別人從 GitHub 點開並聊天，之後須提供可從外網開啟的 HTTPS 訪客網址；localhost 只能在這台電腦使用。管理頁和模型服務仍須保持私人連線。"
              : "You can finish the local trial and card image before getting a public URL. For others to click the GitHub card and chat, provide a public HTTPS visitor URL later; localhost works only on this computer. Keep the admin page and model services private."}
          </p>
        )}
      </section>
      <GitHubShareGuide
        locale={locale}
        account={account}
        publicUrl={publicUrl}
        profileStatus={metadata?.profile_status ?? "unchecked"}
        imageStatus={metadata?.image_status ?? "unchecked"}
        repositoryUrl={metadata?.repository_url ?? links?.repository ?? null}
        profileUrl={metadata?.profile_url ?? links?.profile ?? null}
        readmeUrl={metadata?.readme_url ?? links?.repository ?? null}
        createUrl={metadata?.create_url ?? links?.create ?? null}
        filename={CARD_FILENAME}
        markdown={cardMarkdown(publicUrl, locale)}
        cardReady={!!selectedCard?.gif_base64}
        busy={pending}
        notice={notice}
        onAccountChange={(value) => {
          setAccount(value);
          setMetadata(null);
          remember(value, publicUrl);
        }}
        onPublicUrlChange={(value) => {
          setPublicUrl(value);
          remember(account, value);
        }}
        onCheckProfile={() => void run(checkProfile)}
        onCheckImage={() => void run(checkProfile)}
        onDownload={download}
        onCopy={() =>
          void run(async () => {
            await navigator.clipboard.writeText(
              cardMarkdown(publicUrl, locale),
            );
            setNotice(
              zh
                ? "已複製。請貼入 README、預覽並儲存，再從 GitHub 點擊測試。"
                : "Copied. Paste into README, preview and save, then test the card from GitHub.",
            );
          })
        }
      />
    </div>
  );
}

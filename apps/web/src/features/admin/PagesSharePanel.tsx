import { chromeLocale, type LanguageTag } from "../../i18n/languages";
import { InfoParagraphs } from "./InfoParagraphs";
import { pagesShareErrorMessage } from "./pagesShareError";
import { githubPagesRepository } from "./sharing";
import { sectionTitle } from "./sharingSections";
import "../../p4-w3.css";
import { useEffect, useRef, useState } from "react";
import sharingGuideUrl from "../../../../../docs/PAGES_SHARING_GUIDE.md?url&no-inline";

type Request = <T>(path: string, options?: RequestInit) => Promise<T>;

export interface PagesSharingState {
  pages_url: string | null;
  configured: boolean;
  verified: boolean;
  verified_at: string | null;
  verified_content_sha256: string | null;
  /** Origin of the saved Pages URL. Missing from an older server. */
  pages_origin?: string | null;
  /** Where the next export sends live chat, or null when it is off. */
  live_chat_origin?: string | null;
}

function pagesSourceIdentity(state: PagesSharingState | null): string {
  return [
    state?.pages_url ?? "",
    state?.verified ?? false,
    state?.verified_at ?? "",
    state?.verified_content_sha256 ?? "",
  ].join("|");
}

export function PagesSharePanel({
  locale,
  request,
  observedState,
  onStateChange,
  onOperationPendingChange,
  account = "",
}: {
  locale: LanguageTag;
  request: Request;
  observedState: PagesSharingState | null;
  onStateChange: (state: PagesSharingState | null) => void;
  onOperationPendingChange: (pending: boolean) => void;
  account?: string;
}) {
  const zh = chromeLocale(locale) === "zh-TW";
  const [state, setState] = useState<PagesSharingState | null>(observedState);
  const [pagesUrl, setPagesUrl] = useState(observedState?.pages_url ?? "");
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const mounted = useRef(true);
  const pendingRef = useRef(false);
  const operationGeneration = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const urlDirty = useRef(false);
  const sourceIdentity = pagesSourceIdentity(observedState);
  const previousLocale = useRef(locale);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      operationGeneration.current += 1;
      controller.current?.abort();
      controller.current = null;
    };
  }, []);

  useEffect(() => {
    const localeChanged = previousLocale.current !== locale;
    previousLocale.current = locale;
    operationGeneration.current += 1;
    controller.current?.abort();
    controller.current = null;
    pendingRef.current = false;
    setPending(false);
    onOperationPendingChange(false);
    setState(observedState);
    if (!urlDirty.current) setPagesUrl(observedState?.pages_url ?? "");
    if (localeChanged) setNotice("");
    // State polling supplies the source identity for invalidating stale operations.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale, sourceIdentity]);

  useEffect(() => {
    setState(observedState);
    if (!urlDirty.current) setPagesUrl(observedState?.pages_url ?? "");
  }, [observedState]);

  function publishState(value: PagesSharingState | null) {
    setState(value);
    onStateChange(value);
    if (value && !urlDirty.current) setPagesUrl(value.pages_url ?? "");
  }

  interface OperationContext {
    signal: AbortSignal;
    isCurrent: () => boolean;
  }

  async function run(operation: (context: OperationContext) => Promise<void>) {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(true);
    onOperationPendingChange(true);
    setNotice("");
    const currentGeneration = ++operationGeneration.current;
    const requestController = new AbortController();
    controller.current = requestController;
    const context: OperationContext = {
      signal: requestController.signal,
      isCurrent: () =>
        mounted.current && operationGeneration.current === currentGeneration,
    };
    try {
      await operation(context);
    } catch (error) {
      if (
        !requestController.signal.aborted &&
        context.isCurrent() &&
        mounted.current
      ) {
        publishState(null);
        setNotice(pagesShareErrorMessage(locale, error));
      }
    } finally {
      if (context.isCurrent()) {
        pendingRef.current = false;
        setPending(false);
        onOperationPendingChange(false);
        controller.current = null;
      }
    }
  }

  function requireCurrent(context: OperationContext) {
    if (!context.isCurrent()) throw new Error("SHARING_REQUEST_STALE");
  }

  async function loadState(context: OperationContext) {
    const value = await request<PagesSharingState>("/api/admin/sharing/state", {
      signal: context.signal,
    });
    requireCurrent(context);
    urlDirty.current = false;
    publishState(value);
  }

  async function savePagesUrl(context: OperationContext) {
    if (!pagesUrl.trim()) return;
    const value = await request<PagesSharingState>("/api/admin/sharing/pages", {
      method: "PUT",
      body: JSON.stringify({ pages_url: pagesUrl.trim() }),
      signal: context.signal,
    });
    requireCurrent(context);
    urlDirty.current = false;
    publishState(value);
    setNotice(
      zh
        ? "Pages 網址已儲存。上傳網站後，按「核對 Pages 網站」。"
        : "Pages URL saved. After uploading the site, select Check Pages site.",
    );
  }

  async function verifySite(context: OperationContext) {
    if (!state?.configured || urlChanged) return;
    const value = await request<PagesSharingState>(
      "/api/admin/sharing/verify",
      {
        method: "POST",
        signal: context.signal,
      },
    );
    requireCurrent(context);
    publishState(value);
    setNotice(
      value.verified
        ? zh
          ? "Pages 網站與這台電腦上的內容相符。"
          : "Your Pages site matches the content on this computer."
        : zh
          ? "尚未核對 Pages 網站。"
          : "The Pages site has not been verified.",
    );
  }

  const urlChanged = Boolean(state && pagesUrl.trim() !== state.pages_url);
  const repositoryUrl = githubPagesRepository(account, pagesUrl);
  const copy = zh
    ? {
        title: sectionTitle("pages", "GitHub Pages"),
        intro:
          "GitHub Pages 用來顯示你的網站。只需填入一個完整網站網址。下載網站後，開啟上方的 GitHub 網站上傳頁連結。這一段不需要 Funnel 或 Tailscale。",
        url: "Pages 網址",
        urlHelp:
          "填入完整網站網址，例如 https://account.github.io/project/。首頁網站可填 https://account.github.io/。其他網址不必另外填。",
        save: "儲存",
        export: "下載網站",
        verify: "核對 Pages 網站",
        refresh: "重新整理",
        downloadReady: "下載網站 ZIP 檔",
        uploadTitle: "上傳說明",
        uploadSteps: [
          "按「下載網站」。解壓縮下載的 ZIP 檔。開啟上方的 GitHub 網站上傳頁連結。上傳所有檔案和資料夾。",
          "將 .nojekyll、index.html 和 export-manifest.json 放在專案最外層。這些檔案用來顯示和核對網站。",
          "開啟上方的 GitHub Pages 設定連結。選擇剛上傳的網站作為發布來源。等候 Pages 更新。回來按「核對 Pages 網站」。",
        ],
        configured: "已儲存",
        missing: "未設定",
        verified: "已核對",
        unverified: "未核對",
        digest: "網站核對編號",
      }
    : {
        title: sectionTitle("pages", "GitHub Pages"),
        intro:
          "GitHub Pages displays your website. Enter one full website URL. Download the site. Open the GitHub website upload page link above. This section does not need Funnel or Tailscale.",
        url: "Pages URL",
        urlHelp:
          "Enter the full website URL, such as https://account.github.io/project/. For a homepage site, enter https://account.github.io/. You do not need to enter any other address.",
        save: "Save",
        export: "Download site",
        verify: "Check Pages site",
        refresh: "Refresh",
        downloadReady: "Download website ZIP file",
        uploadTitle: "Upload help",
        uploadSteps: [
          "Select Download site. Extract the downloaded ZIP file. Open the GitHub website upload page link above. Upload every file and folder.",
          "Place .nojekyll, index.html and export-manifest.json outside all folders. These files display and check your website.",
          "Open the GitHub Pages settings link above. Choose your uploaded website as the publishing source. Wait for Pages to update. Return here and select Check Pages site.",
        ],
        configured: "Saved",
        missing: "Not configured",
        verified: "Verified",
        unverified: "Unverified",
        digest: "Website check number",
      };

  return (
    <section
      aria-labelledby="pages-share-panel-heading"
      aria-busy={pending}
      className="pages-share px-panel"
      data-testid="pages-share-panel"
      lang={locale}
    >
      <p className="publication-kicker px-meta">Pages</p>
      <h2 id="pages-share-panel-heading">{copy.title}</h2>
      <div className="publication-actions">
        <a
          href="https://github.com/new"
          target="_blank"
          rel="noopener noreferrer"
        >
          {zh
            ? "在 GitHub 建立網站專案"
            : "Create a website repository on GitHub"}
        </a>
        <a
          href={
            repositoryUrl
              ? `${repositoryUrl}/settings/pages`
              : "https://github.com/new"
          }
          target="_blank"
          rel="noopener noreferrer"
        >
          {zh ? "開啟 GitHub Pages 設定" : "Open GitHub Pages settings"}
        </a>
        <a
          href={
            repositoryUrl ? `${repositoryUrl}/upload` : "https://github.com/new"
          }
          target="_blank"
          rel="noopener noreferrer"
        >
          {zh
            ? "開啟 GitHub 網站上傳頁"
            : "Open the GitHub website upload page"}
        </a>
      </div>
      <label htmlFor="pages-share-url">
        {copy.url}
        <input
          className="px-field"
          autoComplete="url"
          aria-describedby="pages-share-url-help"
          disabled={pending}
          id="pages-share-url"
          inputMode="url"
          onChange={(event) => {
            urlDirty.current = true;
            setPagesUrl(event.target.value);
          }}
          placeholder="https://account.github.io/project/"
          type="url"
          value={pagesUrl}
        />
      </label>
      <details className="publication-info px-info">
        <summary>ⓘ {zh ? "網址說明" : "URL help"}</summary>
        <InfoParagraphs locale={locale} text={copy.intro} />
        <InfoParagraphs
          locale={locale}
          id="pages-share-url-help"
          text={copy.urlHelp}
        />
      </details>
      <div className="publication-actions">
        <button
          className="px-button px-button--secondary"
          disabled={pending || !pagesUrl.trim() || !urlChanged}
          onClick={() => void run(savePagesUrl)}
          type="button"
        >
          {copy.save}
        </button>
        {state?.configured && !urlChanged ? (
          <a
            className="px-button px-button--secondary"
            download="reponpc-site.zip"
            href="/api/admin/sharing/export"
          >
            {copy.export}
          </a>
        ) : (
          <button
            className="px-button px-button--secondary"
            disabled
            type="button"
          >
            {copy.export}
          </button>
        )}
        <button
          className="px-button px-button--secondary"
          disabled={pending || urlChanged || !state?.configured}
          onClick={() => void run(verifySite)}
          type="button"
        >
          {copy.verify}
        </button>
        <button
          className="px-button px-button--secondary"
          disabled={pending}
          onClick={() => void run(loadState)}
          type="button"
        >
          {copy.refresh}
        </button>
      </div>

      <p role="status">
        {!state?.configured
          ? copy.missing
          : state.verified
            ? copy.verified
            : copy.unverified}
      </p>
      {notice && <p role="alert">{notice}</p>}
      {state?.configured && !urlChanged && (
        <div className="publication-link">
          <a
            data-testid="pages-site-download"
            download="reponpc-site.zip"
            href="/api/admin/sharing/export"
          >
            {copy.downloadReady}
          </a>
        </div>
      )}
      <details className="publication-info px-info">
        <summary>ⓘ {copy.uploadTitle}</summary>
        <div className="publication-link">
          <a href={sharingGuideUrl} download="PAGES_SHARING_GUIDE.md">
            {zh
              ? "下載完整雙語分享指南"
              : "Download the full bilingual sharing guide"}
          </a>
        </div>
        <dl>
          <div>
            <dt>{copy.digest}</dt>
            <dd>
              <code>{state?.verified_content_sha256 ?? "—"}</code>
            </dd>
          </div>
        </dl>
        <ol>
          {copy.uploadSteps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </details>
    </section>
  );
}

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
}: {
  locale: "zh-TW" | "en";
  request: Request;
  observedState: PagesSharingState | null;
  onStateChange: (state: PagesSharingState | null) => void;
  onOperationPendingChange: (pending: boolean) => void;
}) {
  const zh = locale === "zh-TW";
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
        setNotice(
          `${zh ? "操作未完成" : "Could not complete"}: ${
            error instanceof Error ? error.message : "REQUEST_FAILED"
          }`,
        );
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
        ? "Pages 網址已儲存；如需確認遠端內容，請重新核對。"
        : "Pages URL saved. Verify the remote content when it is ready.",
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
          ? "遠端 Pages 入口和 manifest 與目前本機內容相符。"
          : "The Pages entry and manifest match the current local content."
        : zh
          ? "尚未核對 Pages 網站。"
          : "The Pages site has not been verified.",
    );
  }

  const urlChanged = Boolean(state && pagesUrl.trim() !== state.pages_url);
  const copy = zh
    ? {
        title: "3. 上傳並核對 GitHub Pages 網站",
        intro:
          "輸入與訪客入口設定相符的 GitHub Pages 網址。匯出不會啟用 Funnel、呼叫模型或修改 GitHub。",
        url: "GitHub Pages 完整網站網址（包含專案路徑）",
        urlHelp:
          "網域須與上一步的 Pages 網域相同。這裡需包含網站路徑，例如 https://account.github.io/project/；若網站在根目錄，填 https://account.github.io/。",
        save: "儲存 Pages 網址",
        export: "下載靜態網站",
        verify: "核對已上傳網站",
        refresh: "重新讀取狀態",
        downloadReady: "下載網站封存檔",
        uploadTitle: "手動上傳與核對",
        uploadSteps: [
          "下載封存檔，解壓縮後將所有檔案和資料夾放到同一個 Pages 發布來源。",
          "保留根目錄中的 .nojekyll、index.html 與 export-manifest.json。",
          "等待 Pages 更新後，再按「核對已上傳網站」。",
        ],
        configured: "Pages 網址已儲存。",
        missing: "先儲存有效的 Pages 網址。",
        verified: "已核對此 Pages 網站。",
        unverified: "尚未核對目前 Pages 網站。",
        digest: "已核對內容識別碼",
      }
    : {
        title: "3. Upload and verify your GitHub Pages site",
        intro:
          "Enter the GitHub Pages URL that matches the visitor-entry configuration. Export does not enable Funnel, call a model, or edit GitHub.",
        url: "Full GitHub Pages site URL (including project path)",
        urlHelp:
          "Use the same domain as the Pages domain in the previous step. Include the site path here, such as https://account.github.io/project/, or https://account.github.io/ for a root site.",
        save: "Save Pages URL",
        export: "Download static site",
        verify: "Verify uploaded site",
        refresh: "Refresh status",
        downloadReady: "Download site archive",
        uploadTitle: "Upload and verify manually",
        uploadSteps: [
          "Download and extract the archive, then place every file and folder in the same Pages publishing source.",
          "Keep .nojekyll, index.html, and export-manifest.json at the root.",
          "After Pages updates, select Verify uploaded site.",
        ],
        configured: "Pages URL saved.",
        missing: "Save a valid Pages URL first.",
        verified: "This Pages site has been verified.",
        unverified: "The current Pages site has not been verified.",
        digest: "Verified content identity",
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
      <p>{copy.intro}</p>
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
        <p id="pages-share-url-help">{copy.urlHelp}</p>
      </details>
      <div className="publication-actions">
        <button
          className="px-button px-button--primary"
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
      <dl>
        <div>
          <dt>{copy.digest}</dt>
          <dd>
            <code>{state?.verified_content_sha256 ?? "—"}</code>
          </dd>
        </div>
      </dl>
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
        <ol>
          {copy.uploadSteps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </details>
    </section>
  );
}

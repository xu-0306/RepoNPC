import { useEffect, useRef, type RefObject } from "react";

import type { Locale } from "../../i18n/messages";

export interface GitHubOAuthSetupGuideBody {
  configured: boolean;
  callback_url: string;
  documentation_url: string;
  next_step: string;
}

interface GitHubOAuthSetupGuideDialogProps {
  error: string;
  guide: GitHubOAuthSetupGuideBody | null;
  locale: Locale;
  onClose: () => void;
  onRefresh: () => void;
  open: boolean;
  pending: boolean;
  returnFocusRef: RefObject<HTMLElement | null>;
}

function copyFor(locale: Locale, chinese: string, english: string): string {
  return locale === "zh-TW" ? chinese : english;
}

function focusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  );
}

export function GitHubOAuthSetupGuideDialog({
  error,
  guide,
  locale,
  onClose,
  onRefresh,
  open,
  pending,
  returnFocusRef,
}: GitHubOAuthSetupGuideDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;

    const invokingElement = returnFocusRef.current;
    previousFocusRef.current =
      invokingElement ??
      (document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null);
    const frame = window.requestAnimationFrame(() => {
      closeButtonRef.current?.focus();
    });

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || dialogRef.current === null) return;
      const elements = focusableElements(dialogRef.current);
      if (elements.length === 0) {
        event.preventDefault();
        dialogRef.current.focus();
        return;
      }
      const current = document.activeElement;
      const first = elements[0];
      const last = elements[elements.length - 1];
      if (
        event.shiftKey &&
        (current === first || !elements.includes(current as HTMLElement))
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (current === last || !elements.includes(current as HTMLElement))
      ) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handleKeyDown);
      const target = invokingElement ?? previousFocusRef.current;
      if (target !== null && document.contains(target)) target.focus();
      previousFocusRef.current = null;
    };
  }, [onClose, open, returnFocusRef]);

  if (!open) return null;

  const configured = guide?.configured === true;
  return (
    <div className="admin-oauth-guide" data-testid="github-oauth-setup-guide">
      <div
        aria-describedby="github-oauth-setup-dialog-description"
        aria-labelledby="github-oauth-setup-dialog-title"
        aria-modal="true"
        className="admin-oauth-guide__dialog"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <div className="admin-oauth-guide__header">
          <div>
            <p className="admin-auth__eyebrow">
              {copyFor(locale, "GitHub 登入設定", "GitHub sign-in setup")}
            </p>
            <h2 id="github-oauth-setup-dialog-title">
              {copyFor(locale, "設定 GitHub 登入", "Set up GitHub sign-in")}
            </h2>
          </div>
          <button
            aria-label={copyFor(locale, "關閉設定說明", "Close setup guide")}
            className="admin-oauth-guide__close"
            onClick={onClose}
            ref={closeButtonRef}
            type="button"
          >
            ×
          </button>
        </div>

        <p id="github-oauth-setup-dialog-description">
          {configured
            ? copyFor(
                locale,
                "GitHub OAuth 已由部署管理員設定完成。關閉此視窗即可繼續登入或連結。",
                "GitHub OAuth is configured by the deployment operator. Close this guide to continue sign-in or linking.",
              )
            : copyFor(
                locale,
                "這是部署管理員在主機端完成的一次設定，不是一般使用者註冊步驟。",
                "This is a one-time host-side deployment step for the operator, not a user registration step.",
              )}
        </p>

        {pending && (
          <p
            aria-live="polite"
            className="admin-oauth-guide__status"
            role="status"
          >
            {copyFor(
              locale,
              "正在重新檢查 GitHub OAuth 設定…",
              "Checking GitHub OAuth configuration…",
            )}
          </p>
        )}
        {error && (
          <p
            aria-live="assertive"
            className="admin-oauth-guide__error"
            role="alert"
          >
            {error}
          </p>
        )}

        {guide && (
          <>
            <div className="admin-oauth-guide__callback">
              <strong>
                {copyFor(
                  locale,
                  "GitHub OAuth Callback URL",
                  "GitHub OAuth callback URL",
                )}
              </strong>
              <code>{guide.callback_url}</code>
            </div>
            {!configured && (
              <ol className="admin-oauth-guide__steps">
                <li>
                  {copyFor(
                    locale,
                    "在 GitHub 建立專用 OAuth App，並填入上方 Callback URL。",
                    "Create a dedicated OAuth App in GitHub and enter the callback URL above.",
                  )}
                </li>
                <li>
                  {copyFor(
                    locale,
                    "在主機端設定 Client ID、恰好一個 Client Secret（直接值或檔案），Callback URL，以及獨立且至少 32 bytes 的加密金鑰（直接值或檔案）。",
                    "On the host, configure the client ID, exactly one client secret (direct value or file), the callback URL, and an independent encryption key of at least 32 bytes (direct value or file).",
                  )}
                </li>
                <li>
                  {copyFor(
                    locale,
                    "重啟 RepoNPC，再按下方按鈕重新檢查。",
                    "Restart RepoNPC, then use the check button below.",
                  )}
                </li>
              </ol>
            )}
            <p className="admin-oauth-guide__warning" role="note">
              {copyFor(
                locale,
                "請勿在網頁貼上 Client Secret、加密金鑰或 OAuth token。RepoNPC 不會在瀏覽器收集或顯示這些值。",
                "Never paste a client secret, encryption key, or OAuth token into this page. RepoNPC does not collect or display those values in the browser.",
              )}
            </p>
            <a
              className="admin-oauth-guide__docs"
              href={guide.documentation_url}
              rel="noopener noreferrer"
              target="_blank"
            >
              {copyFor(
                locale,
                "閱讀 GitHub 官方建立 OAuth App 文件",
                "Read GitHub's official OAuth App setup guide",
              )}
            </a>
          </>
        )}

        <div className="admin-oauth-guide__actions">
          <button disabled={pending} onClick={onRefresh} type="button">
            {copyFor(locale, "重新檢查設定", "Check configuration again")}
          </button>
          <button
            className="admin-oauth-guide__secondary"
            onClick={onClose}
            type="button"
          >
            {copyFor(locale, "關閉", "Close")}
          </button>
        </div>
      </div>
    </div>
  );
}

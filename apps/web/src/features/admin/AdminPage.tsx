import { useCallback, useEffect, useState } from "react";

import {
  AdminWorkspace,
  type AdminPreview,
  type AdminStatus,
  type AdminValidation,
} from "./AdminWorkspace";
import type { Locale } from "../../i18n/messages";

interface SessionBody {
  csrf_token: string;
}

interface ConfigBody {
  content: string;
  blob_sha: string;
}

interface SnippetBody {
  markdown: string;
  asset_url: string;
  target_url: string;
}

export function AdminPage({ locale }: { locale: Locale }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [csrfToken, setCsrfToken] = useState("");
  const [draft, setDraft] = useState("");
  const [blobSha, setBlobSha] = useState("");
  const [validation, setValidation] = useState<AdminValidation | null>(null);
  const [preview, setPreview] = useState<AdminPreview | null>(null);
  const [status, setStatus] = useState<AdminStatus | null>(null);
  const [snippet, setSnippet] = useState<SnippetBody | null>(null);
  const [conflict, setConflict] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const authenticated = Boolean(csrfToken);

  const request = useCallback(
    async function request<T>(path: string, init?: RequestInit): Promise<T> {
      const response = await fetch(path, {
        credentials: "same-origin",
        ...init,
        headers: {
          ...(init?.body instanceof FormData
            ? {}
            : { "Content-Type": "application/json" }),
          ...(init?.method && init.method !== "GET" && csrfToken
            ? { "X-CSRF-Token": csrfToken }
            : {}),
          ...init?.headers,
        },
      });
      const body = (await response.json().catch(() => null)) as
        | T
        | { error?: { code?: string } }
        | null;
      if (!response.ok) {
        if (response.status === 409) setConflict(true);
        const code =
          body !== null && typeof body === "object" && "error" in body
            ? body.error?.code
            : "REQUEST_FAILED";
        throw new Error(code);
      }
      return body as T;
    },
    [csrfToken],
  );

  useEffect(() => {
    if (!authenticated) return;
    void (async () => {
      setBusy(true);
      setError("");
      try {
        const [config, currentStatus, currentSnippet] = await Promise.all([
          request<ConfigBody>("/api/admin/config"),
          request<AdminStatus>("/api/admin/index/status"),
          request<SnippetBody>(
            `/api/admin/readme-snippet?locale=${encodeURIComponent(locale)}&theme=light&extension=svg&revision=1`,
          ),
        ]);
        setDraft(config.content);
        setBlobSha(config.blob_sha);
        setStatus(currentStatus);
        setSnippet(currentSnippet);
      } catch {
        setError(
          locale === "zh-TW"
            ? "無法載入管理資料。"
            : "Admin data could not be loaded.",
        );
      } finally {
        setBusy(false);
      }
    })();
  }, [authenticated, locale, request]);

  async function login(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const session = await request<SessionBody>("/api/admin/session", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setPassword("");
      setCsrfToken(session.csrf_token);
    } catch {
      setPassword("");
      setError(locale === "zh-TW" ? "登入失敗。" : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  async function validate() {
    await perform(async () => {
      const result = await request<AdminValidation>(
        "/api/admin/config/validate",
        {
          method: "POST",
          body: JSON.stringify({ content: draft }),
        },
      );
      setValidation(result);
      setConflict(false);
    });
  }

  async function showPreview() {
    await perform(async () => {
      setPreview(
        await request<AdminPreview>("/api/admin/config/preview", {
          method: "POST",
          body: JSON.stringify({ content: draft }),
        }),
      );
    });
  }

  async function save() {
    await perform(async () => {
      const result = await request<{ blob_sha: string }>("/api/admin/config", {
        method: "PUT",
        body: JSON.stringify({
          content: draft,
          expected_blob_sha: blobSha,
          commit_message: "Update RepoNPC configuration",
        }),
      });
      setBlobSha(result.blob_sha);
      setConflict(false);
    });
  }

  async function dispatch() {
    await perform(async () => {
      await request<{ accepted: boolean }>("/api/admin/index/dispatch", {
        method: "POST",
      });
      setStatus(await request<AdminStatus>("/api/admin/index/status"));
    });
  }

  async function logout() {
    await perform(async () => {
      await request<unknown>("/api/admin/session", { method: "DELETE" });
      clearSensitiveState();
    });
  }

  async function perform(operation: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await operation();
    } catch {
      setError(
        locale === "zh-TW"
          ? "操作失敗，請重試。"
          : "The operation failed. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  function clearSensitiveState() {
    setCsrfToken("");
    setDraft("");
    setBlobSha("");
    setValidation(null);
    setPreview(null);
    setSnippet(null);
    setConflict(false);
  }

  if (!authenticated) {
    return (
      <main className="admin-login" lang={locale}>
        <h1>
          {locale === "zh-TW" ? "RepoNPC 管理登入" : "RepoNPC admin sign in"}
        </h1>
        {error && <p role="alert">{error}</p>}
        <form onSubmit={(event) => void login(event)}>
          <label htmlFor="admin-username">
            {locale === "zh-TW" ? "管理員帳號" : "Username"}
          </label>
          <input
            autoComplete="username"
            id="admin-username"
            onChange={(event) => setUsername(event.target.value)}
            required
            value={username}
          />
          <label htmlFor="admin-password">
            {locale === "zh-TW" ? "密碼" : "Password"}
          </label>
          <input
            autoComplete="current-password"
            id="admin-password"
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
          <button disabled={busy} type="submit">
            {busy
              ? locale === "zh-TW"
                ? "登入中…"
                : "Signing in…"
              : locale === "zh-TW"
                ? "登入"
                : "Sign in"}
          </button>
        </form>
      </main>
    );
  }

  return (
    <>
      {error && <p role="alert">{error}</p>}
      <AdminWorkspace
        authenticated
        busy={busy}
        conflict={conflict}
        draft={draft}
        locale={locale}
        onCopy={() =>
          void navigator.clipboard.writeText(snippet?.markdown ?? "")
        }
        onDispatch={() => void dispatch()}
        onDraftChange={(value) => {
          setDraft(value);
          setValidation(null);
          setConflict(false);
        }}
        onLogout={() => void logout()}
        onPreview={() => void showPreview()}
        onSave={() => void save()}
        onValidate={() => void validate()}
        preview={preview}
        snippet={snippet}
        status={status}
        validation={validation}
      />
    </>
  );
}

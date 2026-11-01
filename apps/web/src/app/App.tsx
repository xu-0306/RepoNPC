import { lazy, Suspense, useEffect, useState } from "react";

import { AdminAccessLayout } from "../features/admin/AdminAccessLayout";
import type { Locale } from "../i18n/messages";
import { VisitorApp } from "./VisitorApp";

export { consumeSse, type SseEvent } from "./sse";

const ADMIN_LOADING_COPY: Record<Locale, string> = {
  "zh-TW": "正在載入管理介面…",
  en: "Loading admin…",
};

const AdminPage = lazy(() =>
  import("../features/admin/AdminPage").then((module) => ({
    default: module.AdminPage,
  })),
);

export function App() {
  return window.location.pathname.startsWith("/admin") ? (
    <AdminRouter />
  ) : (
    <VisitorApp />
  );
}

function AdminRouter() {
  const [locale, setLocale] = useState<Locale>("zh-TW");
  useEffect(() => syncDocumentLanguage(locale), [locale]);
  return (
    <Suspense
      fallback={
        <AdminAccessLayout
          locale={locale}
          title="RepoNPC"
          headingId="admin-loading-heading"
          mode="loading"
        >
          <p className="admin-auth__status" role="status">
            {ADMIN_LOADING_COPY[locale]}
          </p>
        </AdminAccessLayout>
      }
    >
      <AdminPage locale={locale} onLocaleChange={setLocale} />
    </Suspense>
  );
}

export function syncDocumentLanguage(locale: Locale) {
  document.documentElement.lang = locale;
}

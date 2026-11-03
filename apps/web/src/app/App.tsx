import { lazy, Suspense, useEffect, useState } from "react";

import { AdminAccessLayout } from "../features/admin/AdminAccessLayout";
import { resolveLocaleIn, storeLocale } from "../i18n/initialLocale";
import {
  LANGUAGES,
  chromeLocale,
  type LanguageTag as Locale,
} from "../i18n/languages";
import { VisitorApp } from "./VisitorApp";

export { consumeSse, type SseEvent } from "./sse";

const ADMIN_LOADING_COPY: Record<ReturnType<typeof chromeLocale>, string> = {
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
  const [locale, setLocale] = useState<Locale>(() =>
    resolveLocaleIn(
      LANGUAGES.map(({ tag }) => tag),
      "zh-TW",
    ),
  );
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
            {ADMIN_LOADING_COPY[chromeLocale(locale)]}
          </p>
        </AdminAccessLayout>
      }
    >
      <AdminPage
        locale={locale}
        onLocaleChange={(next) => {
          setLocale(next);
          storeLocale(next);
        }}
      />
    </Suspense>
  );
}

export function syncDocumentLanguage(locale: Locale) {
  document.documentElement.lang = locale;
}

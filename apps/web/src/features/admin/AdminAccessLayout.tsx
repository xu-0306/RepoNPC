import type { ReactNode } from "react";

export function AdminAccessLayout({
  locale,
  title,
  headingId,
  mode,
  children,
}: {
  locale: "zh-TW" | "en";
  title: ReactNode;
  headingId: string;
  mode: string;
  children: ReactNode;
}) {
  return (
    <main className="admin-auth-shell" lang={locale}>
      <section
        className="admin-auth-card"
        aria-labelledby={headingId}
        data-mode={mode}
      >
        <header className="admin-auth__header">
          <p className="admin-auth__eyebrow">
            {locale === "zh-TW" ? "本機管理主控台" : "Local admin console"}
          </p>
          <h1 className="admin-auth__title" id={headingId} tabIndex={-1}>
            {title}
          </h1>
        </header>
        {children}
      </section>
    </main>
  );
}

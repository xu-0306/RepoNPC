import type { ReactNode } from "react";
import "../../p4-w4.css";

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
        className="admin-auth-card px-panel px-panel--raised"
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
        <div className="admin-auth__scene px-scene" aria-hidden="true">
          <span className="px-scene__horizon" />
          <span className="px-scene__celestial" />
          <span className="px-scene__hill-far" />
          <span className="px-scene__hill-near" />
          <span className="px-scene__grass" />
          <span className="px-scene__ground" />
          <span className="px-scene__sign" />
        </div>
        {children}
      </section>
    </main>
  );
}

import { useState } from "react";

import { messages, type Locale } from "../i18n/messages";

export function App() {
  const [locale, setLocale] = useState<Locale>("zh-TW");
  const copy = messages[locale];

  return (
    <main className="setup-shell" lang={locale}>
      <header>
        <p className="eyebrow">RepoNPC</p>
        <h1>{copy.title}</h1>
      </header>
      <section aria-labelledby="setup-status-title" className="status-card">
        <h2 id="setup-status-title">{copy.statusTitle}</h2>
        <p role="status">{copy.statusDetail}</p>
        <p>{copy.availabilityDetail}</p>
      </section>
      <nav aria-label={copy.languageLabel} className="locale-switcher">
        {(["zh-TW", "en"] as const).map((option) => (
          <button
            aria-pressed={locale === option}
            key={option}
            onClick={() => setLocale(option)}
            type="button"
          >
            {messages[option].languageName}
          </button>
        ))}
      </nav>
    </main>
  );
}

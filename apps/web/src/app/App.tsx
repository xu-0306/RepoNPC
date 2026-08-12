import { lazy, Suspense, useEffect, useMemo, useState } from "react";

import {
  CharacterRenderer,
  type CharacterState,
} from "../features/character/CharacterRenderer";
import { messages, type Locale } from "../i18n/messages";

const AdminPage = lazy(() =>
  import("../features/admin/AdminPage").then((module) => ({
    default: module.AdminPage,
  })),
);

interface Citation {
  id: string;
  title: string;
  excerpt: string;
  url: string;
}

interface Turn {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}

interface PublicStatus {
  chat_available: boolean;
}

interface PublicProfile {
  profile: {
    display_name: string;
    headline: string;
    bio: string;
    location: string | null;
    links: Array<{ label: string; url: string }>;
  };
  repositories: Array<{
    slug: string;
    summary: string;
    role: string;
    tags: string[];
    demo_url: string | null;
  }>;
  suggested_questions: string[];
}

export function App() {
  const [locale, setLocale] = useState<Locale>("zh-TW");
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [chatAvailable, setChatAvailable] = useState(false);
  const [pending, setPending] = useState(false);
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [profileError, setProfileError] = useState(false);
  const [characterState, setCharacterState] = useState<CharacterState>("idle");
  const copy = messages[locale];
  const reducedMotion = useMemo(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    [],
  );

  useEffect(() => {
    syncDocumentLanguage(locale);
  }, [locale]);

  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/public/status", { signal: controller.signal })
      .then((response) => response.json() as Promise<PublicStatus>)
      .then((status) => {
        setChatAvailable(status.chat_available);
        setCharacterState(status.chat_available ? "idle" : "offline");
      })
      .catch(() => setCharacterState("offline"));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setProfile(null);
    setProfileError(false);
    void fetch(`/api/public/profile?locale=${encodeURIComponent(locale)}`, {
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error("profile unavailable");
        return response.json() as Promise<PublicProfile>;
      })
      .then(setProfile)
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          setProfileError(true);
        }
      });
    return () => controller.abort();
  }, [locale]);

  if (window.location.pathname.startsWith("/admin")) {
    return (
      <Suspense fallback={<p role="status">Loading admin…</p>}>
        <AdminPage locale={locale} />
      </Suspense>
    );
  }

  async function submit(questionText: string) {
    const trimmed = questionText.trim();
    if (!trimmed || pending || !chatAvailable) return;
    const history = turns.map(({ role, content }) => ({ role, content }));
    setTurns((current) => [...current, { role: "user", content: trimmed }]);
    setQuestion("");
    setPending(true);
    setCharacterState("think");
    try {
      const response = await fetch("/api/public/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, locale, history }),
      });
      if (!response.ok || !response.body) throw new Error("chat unavailable");
      setCharacterState("talk");
      const events = await readSse(response.body);
      const answer = events
        .filter((event) => event.name === "token")
        .map((event) => String(event.data.delta ?? ""))
        .join("");
      const citationEvent = events.find((event) => event.name === "citations");
      const citations = Array.isArray(citationEvent?.data.items)
        ? (citationEvent.data.items as Citation[])
        : [];
      setTurns((current) => [
        ...current,
        { role: "assistant", content: answer, citations },
      ]);
      setCharacterState("success");
    } catch {
      setTurns((current) => [
        ...current,
        { role: "assistant", content: copy.genericError },
      ]);
      setCharacterState("offline");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="visitor-shell" lang={locale}>
      <header className="hero">
        <div>
          <p className="eyebrow">RepoNPC</p>
          <h1>{copy.title}</h1>
          <p className="subtitle">{copy.subtitle}</p>
        </div>
        <CharacterRenderer
          assetUrl="/api/public/character.png"
          reducedMotion={reducedMotion}
          state={characterState}
          stateLabel={
            copy[
              `character${capitalize(characterState)}` as keyof typeof copy
            ] as string
          }
        />
      </header>

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

      <section
        aria-busy={!profile && !profileError}
        aria-labelledby="profile-title"
        className="profile-panel"
      >
        <h2 id="profile-title">{copy.profileTitle}</h2>
        {!profile && !profileError && (
          <p role="status">{copy.profileLoading}</p>
        )}
        {profileError && <p role="alert">{copy.profileUnavailable}</p>}
        {profile && (
          <>
            <h3>{profile.profile.display_name}</h3>
            <p className="profile-headline">{profile.profile.headline}</p>
            <p>{profile.profile.bio}</p>
            {profile.profile.location && <p>{profile.profile.location}</p>}
            {profile.profile.links.length > 0 && (
              <nav aria-label={copy.linksTitle} className="profile-links">
                {profile.profile.links.map((link) => (
                  <a
                    href={link.url}
                    key={link.url}
                    rel="noopener noreferrer"
                    target="_blank"
                  >
                    {link.label}
                  </a>
                ))}
              </nav>
            )}
            <h3>{copy.projectsTitle}</h3>
            <ul className="project-grid">
              {profile.repositories.map((repository) => (
                <li key={repository.slug}>
                  <h4>{repository.slug}</h4>
                  <p>{repository.summary}</p>
                  <p>{repository.role}</p>
                  <ul aria-label="Tags" className="tags">
                    {repository.tags.map((tag) => (
                      <li key={tag}>{tag}</li>
                    ))}
                  </ul>
                  {repository.demo_url && (
                    <a
                      href={repository.demo_url}
                      rel="noopener noreferrer"
                      target="_blank"
                    >
                      Demo
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section aria-labelledby="chat-title" className="chat-panel">
        <div className="section-heading">
          <h2 id="chat-title">{copy.chatTitle}</h2>
          <p role="status">
            {chatAvailable ? copy.statusReady : copy.statusUnavailable}
          </p>
        </div>

        {turns.length > 0 && (
          <ol aria-live="polite" className="conversation">
            {turns.map((turn, index) => (
              <li
                className={`turn turn--${turn.role}`}
                key={`${turn.role}-${index}`}
              >
                <p>{turn.content}</p>
                {turn.citations && turn.citations.length > 0 && (
                  <aside aria-label={copy.citations} className="citations">
                    <h3>{copy.citations}</h3>
                    <ul>
                      {turn.citations.map((citation) => (
                        <li key={citation.id}>
                          <a
                            href={citation.url}
                            rel="noopener noreferrer"
                            target="_blank"
                          >
                            {citation.id}: {citation.title}
                          </a>
                          <p>{citation.excerpt}</p>
                        </li>
                      ))}
                    </ul>
                  </aside>
                )}
              </li>
            ))}
          </ol>
        )}

        <div className="suggestions">
          <h3>{copy.suggested}</h3>
          <div className="suggestion-list">
            {(profile?.suggested_questions ?? copy.suggestionItems).map(
              (suggestion) => (
                <button
                  disabled={!chatAvailable || pending}
                  key={suggestion}
                  onClick={() => setQuestion(suggestion)}
                  type="button"
                >
                  {suggestion}
                </button>
              ),
            )}
          </div>
        </div>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void submit(question);
          }}
        >
          <label htmlFor="portfolio-question">{copy.inputLabel}</label>
          <textarea
            disabled={!chatAvailable || pending}
            id="portfolio-question"
            maxLength={4000}
            onChange={(event) => {
              setQuestion(event.target.value);
              if (chatAvailable && !pending) setCharacterState("listen");
            }}
            placeholder={copy.inputPlaceholder}
            rows={3}
            value={question}
          />
          <button
            disabled={!question.trim() || !chatAvailable || pending}
            type="submit"
          >
            {pending ? copy.sending : copy.send}
          </button>
        </form>
      </section>
    </main>
  );
}

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function syncDocumentLanguage(locale: Locale) {
  document.documentElement.lang = locale;
}

interface SseEvent {
  name: string;
  data: Record<string, unknown>;
}

async function readSse(
  stream: ReadableStream<Uint8Array>,
): Promise<SseEvent[]> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const events: SseEvent[] = [];
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const name = block.match(/^event: (.+)$/m)?.[1];
      const data = block.match(/^data: (.+)$/m)?.[1];
      if (name && data)
        events.push({
          name,
          data: JSON.parse(data) as Record<string, unknown>,
        });
    }
    if (done) break;
  }
  return events;
}

import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  CharacterRenderer,
  type CharacterMovement,
  type CharacterState,
} from "../features/character/CharacterRenderer";
import { messages, type Locale } from "../i18n/messages";
import {
  VisitorConversation,
  type Citation,
  type VisitorTurn,
} from "./VisitorConversation";

const AdminPage = lazy(() =>
  import("../features/admin/AdminPage").then((module) => ({
    default: module.AdminPage,
  })),
);

interface PublicStatus {
  chat_available: boolean;
}

interface PublicProfile {
  profile: {
    display_name: string;
    headline: string;
    bio: string;
    greeting: string;
    location: string | null;
    avatar_url: string | null;
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
  character: {
    mode: "builtin" | "custom";
    asset_url: string;
    revision: number;
    frame_duration_ms: number;
    movement: CharacterMovement;
  };
}

export function App() {
  const [locale, setLocale] = useState<Locale>("zh-TW");
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<VisitorTurn[]>([]);
  const [chatAvailable, setChatAvailable] = useState(false);
  const [pending, setPending] = useState(false);
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [profileError, setProfileError] = useState(false);
  const [profileReload, setProfileReload] = useState(0);
  const [characterState, setCharacterState] = useState<CharacterState>("idle");
  const questionInput = useRef<HTMLTextAreaElement>(null);
  const profileErrorAlert = useRef<HTMLParagraphElement>(null);
  const chatStatus = useRef<HTMLParagraphElement>(null);
  const statusController = useRef<AbortController | null>(null);
  const copy = messages[locale];
  const reducedMotion = useMemo(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    [],
  );

  useEffect(() => {
    syncDocumentLanguage(locale);
  }, [locale]);

  useEffect(() => {
    if (reducedMotion) return;
    setCharacterState("walk");
    const timeout = window.setTimeout(() => setCharacterState("idle"), 900);
    return () => window.clearTimeout(timeout);
  }, [reducedMotion]);

  const refreshStatus = useCallback(() => {
    statusController.current?.abort();
    const controller = new AbortController();
    statusController.current = controller;
    void fetch("/api/public/status", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("status unavailable");
        return response.json() as Promise<PublicStatus>;
      })
      .then((status) => {
        if (statusController.current !== controller) return;
        setChatAvailable(status.chat_available);
        setCharacterState(status.chat_available ? "idle" : "offline");
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          if (statusController.current !== controller) return;
          setChatAvailable(false);
          setCharacterState("offline");
          window.setTimeout(() => chatStatus.current?.focus(), 0);
        }
      });
    return controller;
  }, []);

  useEffect(() => {
    const controller = refreshStatus();
    return () => controller.abort();
  }, [refreshStatus]);

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
          window.setTimeout(() => profileErrorAlert.current?.focus(), 0);
        }
      });
    return () => controller.abort();
  }, [locale, profileReload]);

  if (window.location.pathname.startsWith("/admin")) {
    return (
      <Suspense fallback={<p role="status">{copy.adminLoading}</p>}>
        <AdminPage locale={locale} />
      </Suspense>
    );
  }

  async function submit(questionText: string) {
    const trimmed = questionText.trim();
    if (!trimmed || pending || !chatAvailable) return;
    const history = turns
      .filter((turn) => !turn.failed && turn.content.length > 0)
      .map(({ role, content }) => ({ role, content }));
    const requestId =
      window.crypto?.randomUUID?.() ??
      `chat-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const assistantId = `${requestId}-assistant`;
    setTurns((current) => [
      ...current,
      { id: `${requestId}-user`, role: "user", content: trimmed },
      {
        id: assistantId,
        role: "assistant",
        content: "",
        citations: [],
        retryQuestion: trimmed,
      },
    ]);
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
      let completed = false;
      await consumeSse(response.body, (event) => {
        if (event.name === "token") {
          const delta = String(event.data.delta ?? "");
          setTurns((current) =>
            current.map((turn) =>
              turn.id === assistantId
                ? { ...turn, content: turn.content + delta }
                : turn,
            ),
          );
        } else if (event.name === "citations") {
          const citations = Array.isArray(event.data.items)
            ? (event.data.items as Citation[])
            : [];
          setTurns((current) =>
            current.map((turn) =>
              turn.id === assistantId ? { ...turn, citations } : turn,
            ),
          );
        } else if (event.name === "complete") {
          completed = true;
        }
      });
      if (!completed) throw new Error("chat stream incomplete");
      setCharacterState("success");
    } catch {
      setTurns((current) =>
        current.map((turn) =>
          turn.id === assistantId
            ? {
                ...turn,
                content: turn.content || copy.genericError,
                failed: true,
              }
            : turn,
        ),
      );
      setCharacterState("offline");
      window.setTimeout(() => questionInput.current?.focus(), 0);
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
          assetUrl={profile?.character.asset_url ?? "/api/public/character.png"}
          frameDurationMs={profile?.character.frame_duration_ms}
          movement={profile?.character.movement}
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
        {profileError && (
          <div>
            <p ref={profileErrorAlert} role="alert" tabIndex={-1}>
              {copy.profileUnavailable}
            </p>
            <button
              onClick={() => setProfileReload((value) => value + 1)}
              type="button"
            >
              {copy.retryProfile}
            </button>
          </div>
        )}
        {profile && (
          <>
            <h3>{profile.profile.display_name}</h3>
            <p className="profile-headline">{profile.profile.headline}</p>
            <p className="profile-greeting">{profile.profile.greeting}</p>
            <p>{profile.profile.bio}</p>
            {profile.profile.location && <p>{profile.profile.location}</p>}
            {profile.profile.avatar_url && (
              <p>
                <a
                  href={profile.profile.avatar_url}
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  {copy.avatarLink}
                </a>
              </p>
            )}
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
                  <ul aria-label={copy.tagsLabel} className="tags">
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
                      {copy.demoLink}
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
          <p
            ref={chatStatus}
            role="status"
            tabIndex={!chatAvailable ? -1 : undefined}
          >
            {chatAvailable ? copy.statusReady : copy.statusUnavailable}
          </p>
          {!chatAvailable && (
            <button
              onClick={() => {
                refreshStatus();
              }}
              type="button"
            >
              {copy.recheckStatus}
            </button>
          )}
        </div>

        <VisitorConversation
          chatAvailable={chatAvailable}
          locale={locale}
          onRetry={(retryQuestion) => void submit(retryQuestion)}
          pending={pending}
          turns={turns}
        />

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
            ref={questionInput}
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

export interface SseEvent {
  name: string;
  data: Record<string, unknown>;
}

export async function consumeSse(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: SseEvent) => void,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    buffer = buffer.replace(/\r\n/g, "\n");
    if (done && buffer.trim()) buffer += "\n\n";
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const name = block.match(/^event: (.+)$/m)?.[1];
      const data = block.match(/^data: (.+)$/m)?.[1];
      if (name && data) {
        const parsed = JSON.parse(data) as unknown;
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          throw new Error("invalid SSE event");
        }
        onEvent({
          name,
          data: parsed as Record<string, unknown>,
        });
      }
    }
    if (done) break;
  }
}

import { useCallback, useEffect, useRef, useState } from "react";

import { type CharacterState } from "../features/character/CharacterRenderer";
import { messages, type Locale } from "../i18n/messages";
import {
  collectValidatedReply,
  chatProgress,
  chatPublicSummary,
  requestPortfolioChat,
  retainSuccessfulExchanges,
  type SuccessfulExchange,
} from "./visitorChat";
import { focusQuestionAfterPendingClears } from "./visitorFocus";
import type { Citation, VisitorTurn } from "./VisitorConversation";
import { VisitorPage } from "./VisitorPage";
import type { PublicFaq, PublicProfile } from "./publicTypes";
import {
  readVisitorMode,
  setVisitorMode,
  syncVisitorPolicy,
  type VisitorMode,
} from "./scene";
import { matchOfflineFaq } from "./offlineFaq";
import {
  fetchPublicFaq,
  fetchPublicProfile,
  fetchPublicStatus,
  isStaticExport,
  staticChatGateway,
} from "./visitorData";
import "../visitor.css";
import "./scene-fallback.generated.css";

export function VisitorApp() {
  const [locale, setLocale] = useState<Locale>("zh-TW");
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<VisitorTurn[]>([]);
  const [exchanges, setExchanges] = useState<SuccessfulExchange[]>([]);
  const [chatAvailable, setChatAvailable] = useState(false);
  const [statusBundleMismatch, setStatusBundleMismatch] = useState(false);
  const observedFaq = useRef<Partial<Record<Locale, PublicFaq | null>>>({});
  const [pending, setPending] = useState(false);
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [profileError, setProfileError] = useState(false);
  const [profileReload, setProfileReload] = useState(0);
  const [faq, setFaq] = useState<PublicFaq | null>(null);
  const [characterState, setCharacterState] = useState<CharacterState>("idle");
  const [visitorMode, setCurrentVisitorMode] = useState<VisitorMode>(() =>
    readVisitorMode(),
  );
  const [reducedMotion, setReducedMotion] = useState(() =>
    typeof window === "undefined"
      ? true
      : window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const questionInput = useRef<HTMLTextAreaElement>(null);
  const profileErrorAlert = useRef<HTMLParagraphElement>(null);
  const chatStatus = useRef<HTMLParagraphElement>(null);
  const statusController = useRef<AbortController | null>(null);
  const requestController = useRef<AbortController | null>(null);
  const focusQuestionWhenIdle = useRef(false);
  const characterTimer = useRef<number | null>(null);
  const copy = messages[locale];

  const transitionCharacter = useCallback((state: CharacterState) => {
    if (characterTimer.current !== null) {
      window.clearTimeout(characterTimer.current);
      characterTimer.current = null;
    }
    setCharacterState(state);
  }, []);

  function showCharacterSuccess() {
    transitionCharacter("success");
    characterTimer.current = window.setTimeout(() => {
      characterTimer.current = null;
      if (!requestController.current) setCharacterState("idle");
    }, 1200);
  }

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    return () => {
      requestController.current?.abort();
      requestController.current = null;
      statusController.current?.abort();
      if (characterTimer.current !== null) {
        window.clearTimeout(characterTimer.current);
        characterTimer.current = null;
      }
    };
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  useEffect(() => {
    if (reducedMotion) return;
    transitionCharacter("walk");
    characterTimer.current = window.setTimeout(() => {
      characterTimer.current = null;
      if (!requestController.current) setCharacterState("idle");
    }, 900);
    return () => {
      if (characterTimer.current !== null) {
        window.clearTimeout(characterTimer.current);
        characterTimer.current = null;
      }
    };
  }, [reducedMotion, transitionCharacter]);

  const refreshStatus = useCallback(() => {
    statusController.current?.abort();
    const controller = new AbortController();
    statusController.current = controller;
    void fetchPublicStatus(controller.signal)
      .then((status) => {
        if (statusController.current !== controller) return;
        setChatAvailable(status.chat_available);
        setStatusBundleMismatch(status.bundle_mismatch === true);
        if (!requestController.current) {
          transitionCharacter(status.chat_available ? "idle" : "offline");
        }
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          if (statusController.current !== controller) return;
          setChatAvailable(false);
          if (!requestController.current) transitionCharacter("offline");
          window.setTimeout(() => chatStatus.current?.focus(), 0);
        }
      });
    return controller;
  }, [transitionCharacter]);

  useEffect(() => {
    const controller = refreshStatus();
    return () => controller.abort();
  }, [refreshStatus]);

  useEffect(() => {
    focusQuestionAfterPendingClears(
      pending,
      focusQuestionWhenIdle,
      questionInput.current,
    );
  }, [pending]);

  useEffect(() => {
    const controller = new AbortController();
    setProfile(null);
    setFaq(null);
    setProfileError(false);
    void fetchPublicProfile(locale, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) {
          setProfile(value);
          const scene = value.character.scene;
          setCurrentVisitorMode(
            syncVisitorPolicy(
              scene?.color_mode ?? "system",
              scene?.visitor_mode_toggle ?? true,
            ),
          );
        }
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          setProfileError(true);
          window.setTimeout(() => profileErrorAlert.current?.focus(), 0);
        }
      });
    void fetchPublicFaq(
      locale,
      controller.signal,
      fetch,
      observedFaq.current[locale],
    )
      .then((value) => {
        if (!controller.signal.aborted) {
          observedFaq.current[locale] = value;
          setFaq(value);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          observedFaq.current[locale] = null;
          setFaq(null);
        }
      });
    return () => controller.abort();
  }, [locale, profileReload]);

  async function submit(questionText: string) {
    const trimmed = questionText.trim();
    if (!trimmed || pending || requestController.current) return;
    if (!chatAvailable) {
      if (!offlineFaqAvailable || !faq) return;
      const matched = matchOfflineFaq(trimmed, faq);
      const requestId = createRequestId();
      setTurns((current) => [
        ...current,
        { id: requestId + "-user", role: "user", content: trimmed },
        {
          id: requestId + "-assistant",
          role: "assistant",
          content:
            matched.kind === "answer"
              ? matched.entry.answer_markdown
              : matched.questions.length > 0
                ? copy.offlineFaqNoMatch
                : copy.offlineFaqNoMatchWithoutSuggestions,
          citations: matched.kind === "answer" ? matched.entry.citations : [],
          suggestedQuestions:
            matched.kind === "suggestions" ? matched.questions : undefined,
        },
      ]);
      setQuestion((current) => (current.trim() === trimmed ? "" : current));
      if (matched.kind === "answer") showCharacterSuccess();
      else transitionCharacter("idle");
      return;
    }
    const controller = new AbortController();
    requestController.current = controller;
    const requestId = createRequestId();
    const assistantId = requestId + "-assistant";
    const startedAt = performance.now();
    setTurns((current) => [
      ...current,
      { id: requestId + "-user", role: "user", content: trimmed },
      {
        id: assistantId,
        role: "assistant",
        content: "",
        citations: [],
        retryQuestion: trimmed,
        process: { startedAt, status: "pending", stages: [] },
      },
    ]);
    setQuestion("");
    setPending(true);
    transitionCharacter("think");
    try {
      const gateway = isStaticExport()
        ? await staticChatGateway(controller.signal)
        : null;
      const response = await requestPortfolioChat(
        trimmed,
        locale,
        exchanges,
        controller.signal,
        fetch,
        gateway?.origin,
      );
      if (!response.ok || !response.body) throw new Error("chat unavailable");
      let insufficientEvidence = false;
      const answer = await collectValidatedReply(response.body, (event) => {
        if (requestController.current !== controller) return;
        const progress = chatProgress(event);
        if (progress) {
          setTurns((current) =>
            current.map((turn) => {
              if (turn.id !== assistantId || !turn.process) return turn;
              return {
                ...turn,
                process: {
                  ...turn.process,
                  currentStage: progress.stage,
                  stages: turn.process.stages.includes(progress.stage)
                    ? turn.process.stages
                    : [...turn.process.stages, progress.stage],
                },
              };
            }),
          );
        } else if (event.name === "reasoning_summary") {
          const summary = chatPublicSummary(event)!;
          setTurns((current) =>
            current.map((turn) =>
              turn.id === assistantId && turn.process
                ? {
                    ...turn,
                    process: {
                      ...turn.process,
                      summaries: [...(turn.process.summaries ?? []), summary],
                    },
                  }
                : turn,
            ),
          );
        } else if (event.name === "token") {
          const delta = String(event.data.delta ?? "");
          if (delta) transitionCharacter("talk");
          setTurns((current) =>
            current.map((turn) =>
              turn.id === assistantId
                ? { ...turn, content: turn.content + delta }
                : turn,
            ),
          );
        } else if (event.name === "citations") {
          const citations = Array.isArray(event.data.items)
            ? (event.data.items as Citation[]).map((citation) => ({
                ...citation,
                url: gateway ? gateway.citationUrl(citation.url) : citation.url,
              }))
            : [];
          setTurns((current) =>
            current.map((turn) =>
              turn.id === assistantId ? { ...turn, citations } : turn,
            ),
          );
        } else if (
          event.name === "complete" &&
          event.data.insufficient_evidence === true
        ) {
          insufficientEvidence = true;
          const suggestedQuestions = Array.isArray(
            event.data.suggested_questions,
          )
            ? event.data.suggested_questions.filter(
                (item): item is string => typeof item === "string",
              )
            : [];
          const link = event.data.contact_link;
          const contactLink =
            link &&
            typeof link === "object" &&
            "label" in link &&
            "url" in link &&
            typeof link.label === "string" &&
            typeof link.url === "string"
              ? { label: link.label, url: link.url }
              : undefined;
          setTurns((current) =>
            current.map((turn) =>
              turn.id === assistantId
                ? { ...turn, suggestedQuestions, contactLink }
                : turn,
            ),
          );
        }
      });
      if (controller.signal.aborted || requestController.current !== controller)
        return;
      if (!insufficientEvidence)
        setExchanges((current) =>
          retainSuccessfulExchanges([
            ...current,
            { question: trimmed, answer },
          ]),
        );
      setTurns((current) =>
        current.map((turn) =>
          turn.id === assistantId && turn.process
            ? {
                ...turn,
                process: {
                  ...turn.process,
                  status: "complete",
                  elapsedMs: performance.now() - startedAt,
                },
              }
            : turn,
        ),
      );
      if (insufficientEvidence) transitionCharacter("idle");
      else showCharacterSuccess();
    } catch {
      if (controller.signal.aborted || requestController.current !== controller)
        return;
      setTurns((current) =>
        current.map((turn) =>
          turn.id === assistantId
            ? {
                ...turn,
                content: turn.content || copy.genericError,
                failed: true,
                process: turn.process
                  ? {
                      ...turn.process,
                      status: "failed",
                      elapsedMs: performance.now() - startedAt,
                    }
                  : undefined,
              }
            : turn,
        ),
      );
      transitionCharacter("idle");
      refreshStatus();
      focusQuestionWhenIdle.current = true;
    } finally {
      if (requestController.current === controller) {
        requestController.current = null;
        setPending(false);
      }
    }
  }

  function cancelChat() {
    const controller = requestController.current;
    if (!controller) return;
    requestController.current = null;
    controller.abort();
    setTurns((current) =>
      current.map((turn) =>
        turn.process?.status === "pending"
          ? {
              ...turn,
              content: copy.processingCancelled,
              process: {
                ...turn.process,
                status: "cancelled",
                elapsedMs: performance.now() - turn.process.startedAt,
              },
            }
          : turn,
      ),
    );
    setPending(false);
    transitionCharacter("idle");
    focusQuestionWhenIdle.current = true;
  }

  function canAskSuggestion(suggestion: string): boolean {
    if (chatAvailable) return true;
    const currentFaq = faq;
    return Boolean(
      offlineFaqAvailable &&
        currentFaq &&
        currentFaq.bundle_id === profile?.index.version &&
        currentFaq.entries.some((entry) => entry.question === suggestion),
    );
  }

  function selectSuggestion(suggestion: string) {
    const currentFaq = faq;
    const approved =
      currentFaq && currentFaq.bundle_id === profile?.index.version
        ? currentFaq.entries.find((entry) => entry.question === suggestion)
        : undefined;
    if (!approved) {
      setQuestion(suggestion);
      questionInput.current?.focus();
      return;
    }
    if (pending || requestController.current || statusBundleMismatch) return;
    const id = createRequestId();
    setTurns((current) => [
      ...current,
      { id: id + "-user", role: "user", content: suggestion },
      {
        id: id + "-assistant",
        role: "assistant",
        content: approved.answer_markdown,
        citations: approved.citations,
      },
    ]);
    if (chatAvailable)
      setExchanges((current) =>
        retainSuccessfulExchanges([
          ...current,
          { question: suggestion, answer: approved.answer_markdown },
        ]),
      );
    showCharacterSuccess();
  }

  const latestSuggestions = new Set(
    [...turns]
      .reverse()
      .find((turn) => turn.role === "assistant")?.suggestedQuestions,
  );
  const suggestions = [
    ...new Set([
      ...(faq && faq.bundle_id === profile?.index.version
        ? faq.entries.map((entry) => entry.question)
        : []),
      ...(profile?.suggested_questions ?? copy.suggestionItems),
    ]),
  ].filter((suggestion) => !latestSuggestions.has(suggestion));
  const offlineFaqAvailable = Boolean(
    !chatAvailable &&
      !statusBundleMismatch &&
      faq &&
      faq.bundle_id === profile?.index.version,
  );

  return (
    <VisitorPage
      canAskSuggestion={canAskSuggestion}
      chatAvailable={chatAvailable}
      offlineFaqAvailable={offlineFaqAvailable}
      chatStatusRef={chatStatus}
      characterState={characterState}
      locale={locale}
      onLocaleChange={setLocale}
      onQuestionChange={(value) => {
        setQuestion(value);
        if (chatAvailable && !pending) {
          transitionCharacter(value ? "listen" : "idle");
        }
      }}
      onRecheckStatus={() => refreshStatus()}
      onRetry={(retryQuestion) => void submit(retryQuestion)}
      onRetryProfile={() => setProfileReload((value) => value + 1)}
      onSelectSuggestion={selectSuggestion}
      onSubmit={() => void submit(question)}
      onCancel={cancelChat}
      pending={pending}
      profile={profile}
      profileError={profileError}
      profileErrorRef={profileErrorAlert}
      question={question}
      questionInputRef={questionInput}
      reducedMotion={reducedMotion}
      suggestions={suggestions}
      turns={turns}
      visitorMode={visitorMode}
      onVisitorModeChange={(mode) => {
        if (setVisitorMode(mode)) setCurrentVisitorMode(readVisitorMode());
      }}
    />
  );
}

function createRequestId(): string {
  return (
    window.crypto?.randomUUID?.() ??
    "chat-" + Date.now() + "-" + Math.random().toString(16).slice(2)
  );
}

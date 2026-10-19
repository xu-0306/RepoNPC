import { messages, type Locale } from "../i18n/messages";
import { useEffect, useState } from "react";
import type { ChatProcess } from "./visitorChat";
import {
  CharacterRenderer,
  type CharacterMovement,
  type CharacterState,
} from "../features/character/CharacterRenderer";

export interface Citation {
  id: string;
  evidence_class: string;
  repository: string;
  commit_sha: string;
  path: string;
  start_line: number;
  end_line: number;
  title: string;
  excerpt: string;
  url: string;
}

export interface VisitorTurn {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  failed?: boolean;
  noMatchKind?: "no_content" | "temporary";
  retryQuestion?: string;
  suggestedQuestions?: string[];
  contactLink?: { label: string; url: string };
  process?: ChatProcess;
}

interface Props {
  chatAvailable: boolean;
  locale: Locale;
  ownerName?: string;
  onRetry: (question: string) => void;
  canAskSuggestion?: (question: string) => boolean;
  pending: boolean;
  turns: VisitorTurn[];
  characterAssetUrl?: string;
  characterFrameDurationMs?: number;
  characterMovement?: CharacterMovement;
  characterState?: CharacterState;
  reducedMotion?: boolean;
}

type MessageCopy = (typeof messages)[Locale];

function citationLabel(
  evidenceClass: string,
  ownerName: string | undefined,
  copy: MessageCopy,
) {
  switch (evidenceClass) {
    case "OWNER_ASSERTION":
      return copy.citationOwner(
        ownerName?.trim() || copy.citationOwnerFallback,
      );
    case "PARTICIPATION":
      return copy.citationParticipation;
    case "REPOSITORY_FACT":
      return copy.citationProject;
    case "MODEL_INFERENCE":
      return copy.citationInference;
    default:
      return copy.citationOther;
  }
}

export function VisitorConversation({
  chatAvailable,
  locale,
  ownerName,
  onRetry,
  canAskSuggestion,
  pending,
  turns,
  characterAssetUrl = "/api/public/character.png",
  characterFrameDurationMs,
  characterMovement,
  characterState = "idle",
  reducedMotion = false,
}: Props) {
  const copy = messages[locale];
  if (turns.length === 0) return null;
  const latestAssistantId = [...turns]
    .reverse()
    .find((turn) => turn.role === "assistant")?.id;

  return (
    <ol aria-live="polite" className="conversation">
      {turns.map((turn) => (
        <li className={`turn turn--${turn.role}`} key={turn.id}>
          {turn.role === "assistant" && (
            <ConversationAvatar
              assetUrl={characterAssetUrl}
              frameDurationMs={characterFrameDurationMs}
              movement={characterMovement}
              characterState={characterState}
              copy={copy}
              isLatest={turn.id === latestAssistantId}
              reducedMotion={reducedMotion}
            />
          )}
          {turn.process && (
            <ProcessingDetails process={turn.process} locale={locale} />
          )}
          <p>
            {turn.content ||
              (turn.role === "assistant" && pending && !turn.process
                ? copy.streamingAnswer
                : "")}
          </p>
          {turn.suggestedQuestions && turn.suggestedQuestions.length > 0 && (
            <ul className="answer-suggestions">
              {[...new Set(turn.suggestedQuestions)].map((suggestion) => (
                <li key={suggestion}>
                  <button
                    disabled={
                      pending ||
                      !(canAskSuggestion?.(suggestion) ?? chatAvailable)
                    }
                    onClick={() => onRetry(suggestion)}
                    type="button"
                  >
                    {suggestion}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {turn.contactLink && (
            <p>
              <a
                href={turn.contactLink.url}
                rel="noopener noreferrer"
                target="_blank"
              >
                {turn.contactLink.label}
              </a>
            </p>
          )}
          {(turn.failed || turn.noMatchKind === "temporary") &&
            turn.retryQuestion && (
              <button
                disabled={pending || !chatAvailable}
                onClick={() => onRetry(turn.retryQuestion ?? "")}
                type="button"
              >
                {turn.noMatchKind === "temporary" ? copy.askAgain : copy.retry}
              </button>
            )}
          {turn.citations && turn.citations.length > 0 && (
            <details className="citations">
              <summary>{copy.citations}</summary>
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
                    <dl>
                      <dt>{copy.citationClass}</dt>
                      <dd>
                        {citationLabel(
                          citation.evidence_class,
                          ownerName,
                          copy,
                        )}
                      </dd>
                      <dt>{copy.citationLocation}</dt>
                      <dd>
                        {citation.repository} / {citation.path}:
                        {citation.start_line}-{citation.end_line} @{" "}
                        {citation.commit_sha.slice(0, 12)}
                      </dd>
                    </dl>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </li>
      ))}
    </ol>
  );
}

function ProcessingDetails({
  process,
  locale,
}: {
  process: ChatProcess;
  locale: Locale;
}) {
  const copy = messages[locale];
  const [, tick] = useState(0);
  const active = process.status === "pending";
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => tick((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  const elapsed = active
    ? performance.now() - process.startedAt
    : (process.elapsedMs ?? 0);
  const seconds = Math.max(0, Math.floor(elapsed / 1000));
  const duration = copy.processingDuration(
    Math.floor(seconds / 60),
    seconds % 60,
  );
  const latest = process.currentStage ?? process.stages.at(-1);
  return (
    <div className="chat-process" aria-live="off">
      <p className="chat-process__status" role="status" aria-live="polite">
        {process.status === "pending"
          ? latest
            ? copy.processingStages[latest]
            : copy.processingConnecting
          : copy.processingStatus[process.status]}
      </p>
      <details className="chat-process__details">
        <summary aria-label={copy.processingDetails}>
          {active ? copy.processingFor(duration) : copy.processedFor(duration)}
        </summary>
        <ol>
          {process.stages.map((stage) => (
            <li key={stage}>{copy.processingStages[stage]}</li>
          ))}
        </ol>
        <p className="chat-process__note">{copy.processingPrivacy}</p>
        {Boolean(process.summaries?.length) && (
          <section aria-label={copy.processingSummary}>
            <h3>{copy.processingSummary}</h3>
            <p className="chat-process__note">{copy.processingSummaryNote}</p>
            {process.summaries?.map((text, index) => (
              <p className="chat-process__summary" key={index}>
                {text}
              </p>
            ))}
          </section>
        )}
      </details>
    </div>
  );
}

function ConversationAvatar({
  assetUrl,
  frameDurationMs,
  movement,
  characterState,
  copy,
  isLatest,
  reducedMotion,
}: {
  assetUrl: string;
  frameDurationMs?: number;
  movement?: CharacterMovement;
  characterState: CharacterState;
  copy: MessageCopy;
  isLatest: boolean;
  reducedMotion: boolean;
}) {
  const state = isLatest ? characterState : "idle";
  const stateName = state.charAt(0).toUpperCase() + state.slice(1);
  const labelKey = `character${stateName}` as keyof MessageCopy;
  return (
    <CharacterRenderer
      assetUrl={assetUrl}
      className="visitor-turn__avatar"
      frameDurationMs={frameDurationMs}
      movement={movement}
      reducedMotion={isLatest ? reducedMotion : true}
      state={state}
      stateLabel={String(copy[labelKey])}
    />
  );
}

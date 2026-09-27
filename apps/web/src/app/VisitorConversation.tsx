import { messages, type Locale } from "../i18n/messages";

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
  retryQuestion?: string;
  suggestedQuestions?: string[];
  contactLink?: { label: string; url: string };
}

interface Props {
  chatAvailable: boolean;
  locale: Locale;
  ownerName?: string;
  onRetry: (question: string) => void;
  pending: boolean;
  turns: VisitorTurn[];
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
  pending,
  turns,
}: Props) {
  const copy = messages[locale];
  if (turns.length === 0) return null;

  return (
    <ol aria-live="polite" className="conversation">
      {turns.map((turn) => (
        <li className={`turn turn--${turn.role}`} key={turn.id}>
          <p>
            {turn.content ||
              (turn.role === "assistant" && pending
                ? copy.streamingAnswer
                : "")}
          </p>
          {turn.suggestedQuestions && turn.suggestedQuestions.length > 0 && (
            <ul className="answer-suggestions">
              {turn.suggestedQuestions.map((suggestion) => (
                <li key={suggestion}>
                  <button
                    disabled={pending || !chatAvailable}
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
          {turn.failed && turn.retryQuestion && (
            <button
              disabled={pending || !chatAvailable}
              onClick={() => onRetry(turn.retryQuestion ?? "")}
              type="button"
            >
              {copy.retry}
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

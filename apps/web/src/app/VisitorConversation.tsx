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
}

interface Props {
  chatAvailable: boolean;
  locale: Locale;
  onRetry: (question: string) => void;
  pending: boolean;
  turns: VisitorTurn[];
}

export function VisitorConversation({
  chatAvailable,
  locale,
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
                    <dl>
                      <dt>{copy.citationClass}</dt>
                      <dd>{citation.evidence_class}</dd>
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
            </aside>
          )}
        </li>
      ))}
    </ol>
  );
}

import type { ButtonHTMLAttributes, MouseEvent } from "react";

interface GitHubButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  available: boolean;
  label: string;
  pending?: boolean;
  pendingLabel?: string;
  onOpenSetupGuide: (trigger: HTMLButtonElement) => void;
}

/** The GitHub mark is decorative; the adjacent text is the accessible name. */
export function GitHubMark() {
  return (
    <svg
      aria-hidden="true"
      className="github-button__mark"
      focusable="false"
      height="20"
      viewBox="0 0 24 24"
      width="20"
    >
      <path
        d="M12 .5a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58v-2.03c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.75.08-.74.08-.74 1.2.08 1.83 1.23 1.83 1.23 1.07 1.83 2.8 1.3 3.48.99.11-.78.42-1.3.76-1.6-2.66-.3-5.46-1.33-5.46-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.12-3.18 0 0 1.01-.32 3.3 1.23a11.45 11.45 0 0 1 6 0c2.29-1.55 3.3-1.23 3.3-1.23.66 1.66.25 2.88.12 3.18.77.84 1.24 1.91 1.24 3.22 0 4.61-2.8 5.62-5.47 5.92.43.37.81 1.1.81 2.22v3.29c0 .32.22.69.83.57A12 12 0 0 0 12 .5Z"
        fill="currentColor"
      />
    </svg>
  );
}

export function GitHubButton({
  available,
  label,
  onClick,
  onOpenSetupGuide,
  pending = false,
  pendingLabel,
  ...buttonProps
}: GitHubButtonProps) {
  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    if (!available) {
      event.preventDefault();
      onOpenSetupGuide(event.currentTarget);
      return;
    }
    onClick?.(event);
  }

  const visibleLabel = pending && pendingLabel ? pendingLabel : label;
  const disabled = available ? buttonProps.disabled || pending : false;

  return (
    <button
      {...buttonProps}
      aria-busy={pending || undefined}
      className={["github-button", buttonProps.className]
        .filter(Boolean)
        .join(" ")}
      disabled={disabled}
      onClick={handleClick}
    >
      <GitHubMark />
      <span>{visibleLabel}</span>
    </button>
  );
}

import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import type { Locale } from "../../i18n/messages";
import {
  ADMIN_MODEL_STATES,
  type AdminModelSummary,
  type AdminWorkspaceStatus,
} from "./AdminStatusCards";

interface Props {
  locale: Locale;
  status?: Pick<AdminWorkspaceStatus, "chat" | "embedding">;
  selectionView: ReactNode;
  chatConnectionView: ReactNode;
  embeddingConnectionView: ReactNode;
  chatView: ReactNode;
  embeddingView: ReactNode;
  localModelView?: ReactNode;
  guidanceView?: ReactNode;
}

function RoleIcon({ role }: { role: "chat" | "embedding" }) {
  if (role === "chat") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="M7 18.5 3.5 21v-5.1A7.5 7.5 0 0 1 2 11.5C2 7.4 6.5 4 12 4s10 3.4 10 7.5S17.5 19 12 19a13 13 0 0 1-5-.5Z" />
        <path d="M8 11.5h.01M12 11.5h.01M16 11.5h.01" />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m15.5 15.5 5 5" />
    </svg>
  );
}

const COPY = {
  "zh-TW": {
    heading: "模型裝備",
    usable: "可用",
    chat: "分析與回答模型",
    chatDescription: "根據專案資料整理分析與回答。",
    embedding: "資料查找模型",
    embeddingDescription: "從專案中找出相關資料。",
    details: "設定細節",
    roles: "模型角色",
    confirm: "使用這組模型分析",
    guidance: "選模型有困難？查看裝置、推薦清單與手動路線",
  },
  en: {
    heading: "Models",
    usable: "usable",
    chat: "Analysis and answer model",
    chatDescription: "Analyzes and answers using your project information.",
    embedding: "Content finder model",
    embeddingDescription: "Finds relevant information in your projects.",
    details: "Setup details",
    roles: "Model roles",
    confirm: "Use this pair for analysis",
    guidance: "Need help choosing? Device checks, catalog and manual route",
  },
} as const;

export function ModelSetupWorkspace({
  locale,
  status,
  selectionView,
  chatConnectionView,
  embeddingConnectionView,
  chatView,
  embeddingView,
  localModelView,
  guidanceView,
}: Props) {
  const copy = COPY[locale];
  const usable = [status?.chat, status?.embedding].filter(isUsable).length;
  return (
    <div className="model-setup-workspace" lang={locale}>
      <section
        className="model-setup-workspace__equipment px-panel px-panel--raised"
        aria-labelledby="model-equipment-heading"
      >
        <header className="model-setup-workspace__heading">
          <h3 id="model-equipment-heading">{copy.heading}</h3>
          <span className="px-meta">
            <span className="px-display">{usable}/2</span> {copy.usable}
          </span>
        </header>
        <ModelRoleTabs
          locale={locale}
          status={status}
          chatFlow={
            <>
              {chatConnectionView}
              {chatView}
            </>
          }
          embeddingFlow={
            <>
              {localModelView}
              <div id="embedding-external-setup">{embeddingConnectionView}</div>
              {embeddingView}
            </>
          }
        />
      </section>
      {guidanceView && (
        <details className="model-setup-workspace__guidance px-panel px-panel--inset">
          <summary>{copy.guidance}</summary>
          {guidanceView}
        </details>
      )}
      {/* Last child of a flex column: it stays pinned for the whole step and
          follows the width of the step instead of the viewport. */}
      <footer
        aria-labelledby="model-setup-role-heading"
        className="model-setup-workspace__confirm"
        ref={watchConfirmation}
      >
        <h3 className="visually-hidden" id="model-setup-role-heading">
          {copy.confirm}
        </h3>
        {selectionView}
      </footer>
    </div>
  );
}

type Role = "chat" | "embedding";

function isUsable(summary?: AdminModelSummary) {
  return summary?.state === "tested" || summary?.state === "selected";
}

// Both flows stay mounted; the inactive one is hidden so typed values survive a tab switch.
function ModelRoleTabs({
  locale,
  status,
  chatFlow,
  embeddingFlow,
}: {
  locale: Locale;
  status?: Props["status"];
  chatFlow: ReactNode;
  embeddingFlow: ReactNode;
}) {
  const copy = COPY[locale];
  const [active, setActive] = useState<Role>(
    isUsable(status?.chat) && !isUsable(status?.embedding)
      ? "embedding"
      : "chat",
  );
  const tabs = useRef<Partial<Record<Role, HTMLButtonElement | null>>>({});
  const roles: Role[] = ["chat", "embedding"];
  function onKeyDown(event: KeyboardEvent, from: Role) {
    const next =
      event.key === "Home"
        ? "chat"
        : event.key === "End"
          ? "embedding"
          : ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(
                event.key,
              )
            ? roles[(roles.indexOf(from) + 1) % roles.length]
            : null;
    if (!next) return;
    event.preventDefault();
    setActive(next);
    tabs.current[next]?.focus();
  }
  return (
    <>
      <div
        aria-label={copy.roles}
        className="model-setup-workspace__tabs"
        role="tablist"
      >
        {roles.map((role) => {
          const summary = status?.[role];
          const state = summary?.state ?? "unconfigured";
          return (
            <button
              aria-controls={`${role}-role-panel`}
              aria-selected={active === role}
              id={`${role}-role-tab`}
              key={role}
              onClick={() => setActive(role)}
              onKeyDown={(event) => onKeyDown(event, role)}
              ref={(node) => {
                tabs.current[role] = node;
              }}
              role="tab"
              tabIndex={active === role ? 0 : -1}
              type="button"
            >
              <span>
                {isUsable(summary) && <span aria-hidden="true">✓ </span>}
                {copy[role]}
              </span>
              <span
                className="model-role-setup__status px-badge"
                data-state={state}
              >
                {ADMIN_MODEL_STATES[locale][state]}
              </span>
            </button>
          );
        })}
      </div>
      <div className="model-setup-workspace__slots">
        <div
          aria-labelledby="chat-role-tab"
          hidden={active !== "chat"}
          id="chat-role-panel"
          role="tabpanel"
        >
          <ModelSlot
            locale={locale}
            role="chat"
            number="01"
            heading={copy.chat}
            description={copy.chatDescription}
            summary={status?.chat}
          >
            {chatFlow}
          </ModelSlot>
        </div>
        <div
          aria-labelledby="embedding-role-tab"
          hidden={active !== "embedding"}
          id="embedding-role-panel"
          role="tabpanel"
        >
          <ModelSlot
            locale={locale}
            role="embedding"
            number="02"
            heading={copy.embedding}
            description={copy.embeddingDescription}
            summary={status?.embedding}
          >
            {embeddingFlow}
          </ModelSlot>
        </div>
      </div>
    </>
  );
}

function revealSlotHeading(event: Event) {
  const details = event.target as HTMLDetailsElement;
  if (!details.open || !details.classList.contains("model-selection__info"))
    return;
  const footer = event.currentTarget as HTMLElement;
  const heading = footer.parentElement?.querySelector(
    '[role="tabpanel"]:not([hidden]) .model-role-setup__heading',
  );
  if (!heading) return;
  const slot = heading.getBoundingClientRect();
  const bar = footer.getBoundingClientRect();
  // Keep the slot context visible when inline help makes the pinned bar taller.
  if (slot.bottom > bar.top && slot.top < bar.bottom)
    window.scrollBy({
      top: Math.ceil(slot.bottom - bar.top + 16),
      behavior: "instant",
    });
}

function watchConfirmation(confirm: HTMLElement | null) {
  if (!confirm) return;
  confirm.addEventListener("toggle", revealSlotHeading, true);
  return () => confirm.removeEventListener("toggle", revealSlotHeading, true);
}

function ModelSlot({
  locale,
  role,
  number,
  heading,
  description,
  summary,
  children,
}: {
  locale: Locale;
  role: "chat" | "embedding";
  number: string;
  heading: string;
  description: string;
  summary?: AdminModelSummary;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(true);
  const id = `${role}-role-setup-heading`;
  return (
    <section aria-labelledby={id} className="model-setup-workspace__role">
      <span aria-hidden="true" className="model-role-setup__tile">
        <RoleIcon role={role} />
        <span className="px-display">{number}</span>
      </span>
      <div className="model-role-setup__body">
        <header className="model-role-setup__heading">
          <div>
            <h3 id={id}>{heading}</h3>
            <p>{description}</p>
          </div>
        </header>
        {(summary?.connection || summary?.provider || summary?.model) && (
          <p className="model-role-setup__summary">
            {[summary.connection ?? summary.provider, summary.model]
              .filter(Boolean)
              .join(" · ")}
          </p>
        )}
        <details
          className="model-role-setup__details"
          open={open}
          onToggle={(event) => setOpen(event.currentTarget.open)}
        >
          <summary>{COPY[locale].details}</summary>
          <div className="model-role-setup__flow">{children}</div>
        </details>
      </div>
    </section>
  );
}

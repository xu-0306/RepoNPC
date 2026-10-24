import { useState, type ReactNode } from "react";

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
    confirm: "分析使用這一組",
    guidance: "選模型有困難？查看裝置、推薦清單與手動路線",
  },
  en: {
    heading: "Model equipment",
    usable: "usable",
    chat: "Analysis and answer model",
    chatDescription: "Analyzes and answers using your project information.",
    embedding: "Content finder model",
    embeddingDescription: "Finds relevant information in your projects.",
    details: "Setup details",
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
  const usable = [status?.chat, status?.embedding].filter(
    (summary) => summary?.state === "tested" || summary?.state === "selected",
  ).length;
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
        <div className="model-setup-workspace__slots">
          <ModelSlot
            locale={locale}
            role="chat"
            number="01"
            heading={copy.chat}
            description={copy.chatDescription}
            summary={status?.chat}
          >
            {chatConnectionView}
            {chatView}
          </ModelSlot>
          <ModelSlot
            locale={locale}
            role="embedding"
            number="02"
            heading={copy.embedding}
            description={copy.embeddingDescription}
            summary={status?.embedding}
          >
            {localModelView}
            <div id="embedding-external-setup">{embeddingConnectionView}</div>
            {embeddingView}
          </ModelSlot>
        </div>
        <footer
          aria-labelledby="model-setup-role-heading"
          className="model-setup-workspace__confirm"
          ref={reserveConfirmationSpace}
        >
          <h3 className="visually-hidden" id="model-setup-role-heading">
            {copy.confirm}
          </h3>
          {selectionView}
        </footer>
      </section>
      {guidanceView && (
        <details className="model-setup-workspace__guidance px-panel px-panel--inset">
          <summary>{copy.guidance}</summary>
          {guidanceView}
        </details>
      )}
    </div>
  );
}

function revealSlotHeading(event: Event) {
  const details = event.target as HTMLDetailsElement;
  if (!details.open || !details.classList.contains("model-selection__info"))
    return;
  const footer = event.currentTarget as HTMLElement;
  const heading = footer.parentElement?.querySelector(
    "#chat-role-setup-heading",
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

function reserveConfirmationSpace(confirm: HTMLElement | null) {
  if (!confirm) return;
  const slots = confirm.previousElementSibling as HTMLElement;
  const reserve = () => {
    slots.style.paddingBottom = `${confirm.getBoundingClientRect().height}px`;
  };
  reserve();
  const observer =
    typeof ResizeObserver === "undefined" ? null : new ResizeObserver(reserve);
  observer?.observe(confirm);
  confirm.addEventListener("toggle", revealSlotHeading, true);
  return () => {
    observer?.disconnect();
    confirm.removeEventListener("toggle", revealSlotHeading, true);
  };
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
  const state = summary?.state ?? "unconfigured";
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
          <span
            className="model-role-setup__status px-badge"
            data-state={state}
          >
            {ADMIN_MODEL_STATES[locale][state]}
          </span>
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

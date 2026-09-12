import type { ReactNode } from "react";

import type { Locale } from "../../i18n/messages";

interface Props {
  locale: Locale;
  selectionView: ReactNode;
  chatConnectionView: ReactNode;
  embeddingConnectionView: ReactNode;
  chatView: ReactNode;
  embeddingView: ReactNode;
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

export function ModelSetupWorkspace({
  locale,
  selectionView,
  chatConnectionView,
  embeddingConnectionView,
  chatView,
  embeddingView,
}: Props) {
  const chinese = locale === "zh-TW";
  return (
    <div className="model-setup-workspace">
      <section
        aria-labelledby="chat-role-setup-heading"
        className="model-setup-workspace__role admin-surface"
      >
        <RoleHeading
          description={
            chinese
              ? "負責理解專案內容並產生回答。新增服務與模型後，先測試是否能正常回應。"
              : "Understands project content and writes answers. Add a service and model, then test that it can respond."
          }
          heading={chinese ? "分析與回答模型" : "Analysis and answer model"}
          id="chat-role-setup-heading"
          role="chat"
        />
        <div className="model-role-setup__flow">
          {chatConnectionView}
          {chatView}
        </div>
      </section>
      <section
        aria-labelledby="embedding-role-setup-heading"
        className="model-setup-workspace__role admin-surface"
      >
        <RoleHeading
          description={
            chinese
              ? "協助從專案中找出相關資料。新增服務與模型後，先測試是否能處理文字。"
              : "Finds relevant project information. Add a service and model, then test that it can process text."
          }
          heading={chinese ? "資料查找模型" : "Content finder model"}
          id="embedding-role-setup-heading"
          role="embedding"
        />
        <div className="model-role-setup__flow">
          {embeddingConnectionView}
          {embeddingView}
        </div>
      </section>
      <aside
        aria-labelledby="model-setup-role-heading"
        className="model-setup-workspace__roles admin-surface"
      >
        <h3 id="model-setup-role-heading">
          {chinese ? "確認分析模型" : "Confirm models for analysis"}
        </h3>
        <p>
          {chinese
            ? "兩種模型都通過測試後，在這裡選擇並確認，接著就能分析專案。"
            : "After both models pass testing, select and confirm them here to analyze your projects."}
        </p>
        {selectionView}
      </aside>
    </div>
  );
}

function RoleHeading({
  id,
  role,
  heading,
  description,
}: {
  id: string;
  role: "chat" | "embedding";
  heading: string;
  description: string;
}) {
  return (
    <header className="model-role-setup__heading">
      <span className="model-role-switch__icon">
        <RoleIcon role={role} />
      </span>
      <span>
        <h3 id={id}>{heading}</h3>
        <p>{description}</p>
      </span>
    </header>
  );
}

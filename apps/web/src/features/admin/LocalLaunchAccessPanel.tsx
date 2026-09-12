import { AdminAccessLayout } from "./AdminAccessLayout";

type LocalLaunchAccessPanelProps = {
  locale: "zh-TW" | "en";
  state: "checking" | "relaunch";
};

const copy = {
  "zh-TW": {
    checking: "正在確認本機管理工作階段…",
    relaunchHeading: "請透過本機啟動器重新開啟 RepoNPC",
    relaunchBody:
      "此管理頁面必須由本機啟動器開啟。請關閉此頁面，重新執行啟動器後再試一次。",
  },
  en: {
    checking: "Checking the local admin session…",
    relaunchHeading: "Reopen RepoNPC through the local launcher",
    relaunchBody:
      "This admin page must be opened by the local launcher. Close this page, run the launcher again, then try again.",
  },
} as const;

export function LocalLaunchAccessPanel({
  locale,
  state,
}: LocalLaunchAccessPanelProps) {
  const text = copy[locale];

  return (
    <AdminAccessLayout
      locale={locale}
      mode={state}
      headingId="local-launch-relaunch-heading"
      title={state === "checking" ? "RepoNPC" : text.relaunchHeading}
    >
      {state === "checking" ? (
        <p className="admin-auth__status" role="status" aria-live="polite">
          {text.checking}
        </p>
      ) : (
        <div className="admin-auth__content">
          <p className="admin-auth__intro">{text.relaunchBody}</p>
        </div>
      )}
    </AdminAccessLayout>
  );
}

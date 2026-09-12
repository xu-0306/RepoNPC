import { useState } from "react";
import { createRoot } from "react-dom/client";
import { AdminAccessPanel } from "./src/features/admin/AdminPage";
import { LocalLaunchAccessPanel } from "./src/features/admin/LocalLaunchAccessPanel";
import { AdminAccessLayout } from "./src/features/admin/AdminAccessLayout";
import "./src/styles.css";

// Synthetic state inventory; callbacks cannot access a server or authenticate.
document.documentElement.classList.add("admin-route");
document.body.classList.add("admin-route");
const noop = () => {};
function Review() {
  const [locale, setLocale] = useState<"zh-TW" | "en">("zh-TW");
  const [mode, setMode] = useState("relaunch");
  return (
    <>
      <aside>
        <label>
          Scenario
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            {[
              "relaunch",
              "checking",
              "bundle-loading",
              "loading",
              "login",
              "setup",
              "recovery",
              "unavailable",
              "login-error",
            ].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          Language
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value as typeof locale)}
          >
            <option value="zh-TW">繁體中文</option>
            <option value="en">English</option>
          </select>
        </label>
        <label>
          Text size
          <select
            defaultValue="100%"
            onChange={(e) => {
              document.documentElement.style.fontSize = e.target.value;
            }}
          >
            <option>100%</option>
            <option>200%</option>
          </select>
        </label>
      </aside>
      {mode === "relaunch" || mode === "checking" ? (
        <LocalLaunchAccessPanel locale={locale} state={mode} />
      ) : mode === "bundle-loading" ? (
        <AdminAccessLayout
          locale={locale}
          mode="loading"
          headingId="loading-heading"
          title="RepoNPC"
        >
          <p role="status" className="admin-auth__status">
            {locale === "en"
              ? "Loading admin workspace…"
              : "正在載入管理工作區…"}
          </p>
        </AdminAccessLayout>
      ) : (
        <AdminAccessPanel
          locale={locale}
          busy={false}
          error={
            mode === "login-error" ? "Synthetic authentication failure" : ""
          }
          passwordAvailable={mode !== "recovery"}
          setupStatus={
            mode === "unavailable" || mode === "loading"
              ? null
              : { setup_required: mode === "setup", setup_code_available: true }
          }
          setupStatusPending={mode === "loading"}
          username=""
          password=""
          setupCode=""
          setupPassword=""
          setupPasswordConfirmation=""
          onUsernameChange={noop}
          onPasswordChange={noop}
          onSetupCodeChange={noop}
          onSetupPasswordChange={noop}
          onSetupPasswordConfirmationChange={noop}
          onLogin={noop}
          onSetupOwner={noop}
          onRefreshSetupStatus={noop}
        />
      )}
    </>
  );
}
createRoot(document.getElementById("root")!).render(<Review />);

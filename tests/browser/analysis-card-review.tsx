// Copy beside apps/web/index.html for an isolated Vite review, then remove the copies.
// Production UI and reducer, synthetic in-memory results; no network or owner data.
import { useState } from "react";
import { createRoot } from "react-dom/client";
import { GuidedOnboardingView } from "./src/features/admin/GuidedOnboardingView";
import { initialGuidedOnboardingState, guidedOnboardingReducer } from "./src/features/admin/guidedOnboarding";
import type { GuidedOnboardingState } from "./src/features/admin/guidedOnboarding";
import type { Locale } from "./src/i18n/messages";
import "./src/styles.css";

const noop = () => {};
function Review() {
  const [locale, setLocale] = useState<Locale>("zh-TW");
  const [state, setState] = useState<GuidedOnboardingState>(() => ({
    ...initialGuidedOnboardingState(), step: "analysis", modelsConfigured: true, selectionConfirmed: true,
    repositories: [{
      metadata: { slug: "example/evidence-browser", name: "evidence-browser", description: "Synthetic review project", primary_language: "TypeScript", default_branch: "main", is_fork: false, is_archived: false, updated_at: null, html_url: "https://github.com/example/evidence-browser" },
      selected: true, ref: null, include: [], exclude: [], confirmedSelectionFingerprint: JSON.stringify([null, [], []]), analysisStatus: "complete",
      analysis: {
        repository: { slug: "example/evidence-browser", commit_sha: "a".repeat(40), default_branch: "main", html_url: "https://github.com/example/evidence-browser" },
        facts: [
          { evidence_class: "REPOSITORY_FACT", evidence_id: "E_parser", path: "src/parser.ts", start_line: 4, end_line: 12, excerpt: 'export function parse(input: string) {\n  return validate(input);\n}\n// <script>alert("untrusted")</script>' },
          { evidence_class: "REPOSITORY_FACT", evidence_id: "E_docs", path: "docs/" + "long-path-".repeat(16) + "/guide.md", start_line: 10, end_line: 18, excerpt: "Documented project behavior. ".repeat(20) },
          { evidence_class: "REPOSITORY_FACT", evidence_id: "E_other", path: "LICENSE", start_line: null, end_line: null, excerpt: "Synthetic license content." },
        ],
        inferences: [
          { evidence_class: "MODEL_INFERENCE", statement: { "zh-TW": "這個專案提供輸入解析與驗證，讓其他功能可以共用一致的處理方式。", en: "This project provides input parsing and validation that other features can reuse." }, supporting_evidence_ids: ["E_parser"] },
          { evidence_class: "MODEL_INFERENCE", statement: { "zh-TW": "文件描述專案如何使用解析功能，並說明使用前需要核對的條件。這些內容描述專案本身，無法證明任何人的角色或貢獻。\n".repeat(8), en: "The documentation explains how to use parsing and which conditions to check first. This describes the project and cannot establish anyone's role or contribution.\n".repeat(8) }, supporting_evidence_ids: ["E_docs"] },
        ], skipped_summary: { count: 0, reasons: [] },
      },
      ownerStatement: "", proposal: null, confirmedContribution: null, previousContribution: null,
    }],
  }));
  return <main className="admin-workspace">
    <h1>Analysis card browser fixture</h1>
    <button type="button" onClick={() => setLocale(locale === "en" ? "zh-TW" : "en")}>中文 / English</button>
    <GuidedOnboardingView locale={locale} state={state} busy={false} errorCode="" providerStatus={null} providerStatusPending={false}
      batchAnalysisView={<p>{locale === "en" ? "Analysis complete" : "分析完成"}</p>} batchAnalysisTerminal
      onAction={(action) => setState((current) => guidedOnboardingReducer(current, action))}
      onDiscover={noop} onResolve={noop} onAnalyze={noop} onRefreshProviderStatus={noop} onSuggestContribution={noop} onCreateDraft={noop} onCopyDraft={noop} onDownloadDraft={noop} />
  </main>;
}
createRoot(document.getElementById("root")!).render(<Review />);

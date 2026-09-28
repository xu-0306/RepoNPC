// Controlled owner-route responses exercise real A4 components. Backend build/validator
// coverage lives in integration/test_reviewed_faq.py; this harness makes no live calls.
import { useCallback, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { LocalPublishingWorkspace } from "./src/features/admin/LocalPublishingWorkspace";
import { GuidedOnboardingView } from "./src/features/admin/GuidedOnboardingView";
import { guidedOnboardingReducer, initialGuidedOnboardingState } from "./src/features/admin/guidedOnboarding";
import "./src/styles.css";

const topics = ["responsibility", "built_work", "duration", "team_context", "outcome", "technologies"];
const kinds = ["responsibility", "responsibility", "context", "context", "achievement", "context"] as const;
function Review() {
  const [locale, setLocale] = useState<"zh-TW" | "en">("zh-TW");
  const [draft, setDraft] = useState({ content: "safe synthetic local draft", sprite_base64: null, revision: "a".repeat(64) });
  const [bundle, setBundle] = useState("bundle-one");
  const bundleRef = useRef(bundle); bundleRef.current = bundle;
  const rows = useRef<Record<string, any[]>>({});
  const delayNext = useRef(false);
  const releaseDelay = useRef<(() => void) | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [exported, setExported] = useState("");
  const [gap, setGap] = useState(false);
  const [guided, setGuided] = useState(() => ({ ...initialGuidedOnboardingState(true), selectionConfirmed: true, route: "manual" as const, repositories: [{
    metadata: { slug: "owner/demo", name: "demo", description: null, primary_language: "Python", default_branch: "main", is_fork: false, is_archived: false, updated_at: null, html_url: "https://github.com/owner/demo" },
    ref: null, include: ["**/*"], exclude: [], selected: true, confirmedSelectionFingerprint: null,
    analysisStatus: "idle" as const, analysis: null, ownerStatement: "My contribution", previousContribution: null,
    proposal: null, confirmedContribution: { evidence_class: "OWNER_ASSERTION" as const,
      role: { "zh-TW": "開發者", en: "Developer" }, summary: { "zh-TW": "實作功能", en: "Implemented features" }, claims: [] },
  }] }));
  const request = useCallback(async <T,>(path: string, options?: RequestInit): Promise<T> => {
    const body = options?.body ? JSON.parse(String(options.body)) : {};
    const language = new URL(path, "http://localhost").searchParams.get("locale") ?? body.locale ?? document.documentElement.lang;
    const state = rows.current[language] ?? [];
    if (path === "/api/admin/portfolio/status") return { state: "ready", index_ready: true, draft_changed: false, active_bundle_id: bundleRef.current, revision: "a".repeat(64), error_code: null } as T;
    if (path === "/api/admin/portfolio/prepare") {
      setLogs(log => [...log, "prepare:new-index"]); setBundle("bundle-rewrite"); bundleRef.current = "bundle-rewrite";
      return { state: "preparing", index_ready: true, draft_changed: false, active_bundle_id: bundleRef.current } as T;
    }
    if (path === "/api/admin/portfolio" && options?.method === "PUT") return { content: body.content, sprite_base64: null, revision: "a".repeat(64) } as T;
    if (path.endsWith("/faq/check")) {
      if (!state.length) rows.current[language] = [...topics, "suggested"].map((topic, index) => ({
        entry_id: (index + (language === "en" ? 100 : 1)).toString(16).padStart(32, "0"), bundle_id: bundleRef.current,
        question: `${language}: ${topic}`, topic: index < 6 ? topic : null, claim_kind: kinds[index] ?? "context",
        answer_markdown: null, citations: [], dropped_segments: [], coverage_status: "unchecked", review_state: "pending",
        needs_reconfirmation: false, rewrite: null, error_code: null, revision: 1,
      }));
    }
    const match = path.match(/\/faq\/([a-f0-9]+)\/(regenerate|review|rewrite)$/);
    if (match) {
      const entry = Object.values(rows.current).flat().find(row => row.entry_id === match[1] && row.question.startsWith(language));
      // Route body omits locale, so identify the currently displayed fixture locale.
      const target = entry ?? Object.values(rows.current).flat().find(row => row.entry_id === match[1] && row.question.startsWith(document.documentElement.lang));
      if (!target) throw new Error("FAQ_NOT_FOUND");
      const action = match[2];
      if (body.revision !== target.revision) throw new Error("FAQ_CONFLICT");
      target.revision += 1;
      if (action === "regenerate") {
        if (delayNext.current) {
          delayNext.current = false;
          setLogs(log => [...log, "generation:held"]);
          await new Promise<void>(resolve => { releaseDelay.current = resolve; });
        }
        setLogs(log => [...log, `generate:${target.question}:${bundleRef.current}`]);
        target.bundle_id = bundleRef.current; target.review_state = "pending"; target.rewrite = null;
        target.answer_markdown = `Validated answer for ${target.question}. [S1]`;
        target.citations = [{ title: "Evidence", url: "https://github.com/owner/demo", evidence_class: "REPOSITORY_FACT" }];
        target.coverage_status = target.topic === "responsibility" ? "partially_answered" : target.topic === "built_work" ? "no_relevant_content" : "answered";
        target.dropped_segments = target.topic === "responsibility" ? [{ segment_index: 1, reason_codes: ["OWNER_ASSERTION_MISSING"] }] : [];
      } else if (action === "review") {
        target.review_state = body.action === "approve" ? "approved" : "rejected";
        setLogs(log => [...log, body.action]);
      } else {
        target.review_state = "pending";
        target.rewrite = { claim_id: "faq_fixture", draft_revision: "b".repeat(64), source_bundle_id: target.bundle_id };
        setLogs(log => [...log, `save-claim:${body.kind}`]);
        return { draft: { content: "saved bilingual owner statement", sprite_base64: null, revision: "b".repeat(64) }, entry: { ...target } } as T;
      }
      return { ...target } as T;
    }
    const entries = (rows.current[language] ?? []).map(entry => ({ ...entry, needs_reconfirmation: entry.bundle_id !== bundleRef.current }));
    if (path.includes("/faq/export")) {
      const result = { bundle_id: bundleRef.current, locale: language, entries: entries.filter(entry => entry.bundle_id === bundleRef.current && entry.review_state === "approved" && !entry.rewrite).map(entry => ({ question: entry.question, answer_markdown: entry.answer_markdown, citations: entry.citations })) };
      setExported(JSON.stringify(result)); return result as T;
    }
    return { bundle_id: bundleRef.current, locale: language, entries } as T;
  }, []);
  document.documentElement.lang = locale;
  return <main>
    <button onClick={() => { setGap(false); setLocale(locale === "zh-TW" ? "en" : "zh-TW"); }}>中文 / English</button>
    <button onClick={() => { setBundle("bundle-new"); bundleRef.current = "bundle-new"; }}>Switch bundle fixture</button>
    <button onClick={() => { delayNext.current = true; }}>Delay next generation fixture</button>
    <button onClick={() => { releaseDelay.current?.(); releaseDelay.current = null; }}>Release delayed generation fixture</button>
    {gap ? <><button onClick={() => setGap(false)}>Return to FAQ</button><GuidedOnboardingView locale={locale} state={guided} busy={false} errorCode="" providerStatus={null} providerStatusPending={false}
      onAction={action => setGuided(current => guidedOnboardingReducer(current, action))} onDiscover={() => {}} onResolve={() => {}} onAnalyze={() => {}} onRefreshProviderStatus={() => {}} onSuggestContribution={() => {}} onCreateDraft={() => {}} onCopyDraft={() => {}} onDownloadDraft={() => {}} /></> :
      <LocalPublishingWorkspace locale={locale} content={draft.content} spriteBase64={null} revision={draft.revision} initialAccount="owner"
        selection={{ eligible: true, reason: "READY", selection: { generation: 1, chat_profile_id: "synthetic-chat", embedding_profile_id: "synthetic-embedding", updated_at: "2026-09-28T00:00:00Z" } }}
        request={request} onStored={value => setDraft(value as typeof draft)} onCreateDraft={() => {}} repositories={["owner/demo"]}
        onAddClaim={(slug, kind) => { setGuided(current => guidedOnboardingReducer(current, { type: "OPEN_CLAIM_EDITOR", slug, kind })); setGap(true); }} />}
    <output style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", maxWidth: "100%" }} aria-label="Recorded operations">{logs.join("\n")}</output>
    <output style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", maxWidth: "100%" }} aria-label="Exported FAQ">{exported}</output>
  </main>;
}
createRoot(document.getElementById("root")!).render(<Review />);

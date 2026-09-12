import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, ReactNode } from "react";

import type { Locale } from "../../i18n/messages";
import {
  guidedErrorMessage,
  type ContributionProposal,
  type GuidedOnboardingState,
  type GuidedProfile,
  type GuidedRepository,
  type GuidedStep,
  type LocalizedText,
  type ModelInference,
  type RepositoryFact,
} from "./guidedOnboarding";
import type { GuidedOnboardingViewProps } from "./guidedOnboarding";
import {
  AdminStatusCards,
  type AdminWorkspaceStatus,
} from "./AdminStatusCards";
import { OnboardingStepper } from "./OnboardingStepper";
import { CheckboxField } from "./CheckboxField";

const EMPTY_WORKSPACE_STATUS: AdminWorkspaceStatus = {
  chat: {
    model: null,
    connection: null,
    provider: null,
    state: "unconfigured",
  },
  embedding: {
    model: null,
    connection: null,
    provider: null,
    state: "unconfigured",
  },
  publicBundleId: null,
};

type Copy = {
  product: string;
  title: string;
  introTitle: string;
  introBody: string;
  outcome: string;
  outcomeItems: string[];
  start: string;
  startAi: string;
  startManual: string;
  modelsHeading: string;
  modelsDescription: string;
  confirmModels: string;
  modelsRequired: string;
  advanced: string;
  advancedDescription: string;
  progress: string;
  steps: Record<GuidedStep, string>;
  accountHeading: string;
  accountLabel: string;
  accountHelp: string;
  discover: string;
  discoverAgain: string;
  searchLabel: string;
  noMatches: string;
  discoveryComplete: string;
  manualHeading: string;
  repositoryLabel: string;
  repositoryHelp: string;
  refLabel: string;
  refOptional: string;
  resolve: string;
  repositoryHeading: string;
  repositoryCount: (selected: number, total: number) => string;
  repositoryDescription: string;
  selected: string;
  archived: string;
  fork: string;
  languageLabel: string;
  defaultBranchLabel: string;
  githubLabel: string;
  optionsLegend: string;
  includeLabel: string;
  excludeLabel: string;
  noRepositories: string;
  confirmSelection: string;
  selectionRequired: string;
  selectionLocked: string;
  analysisHeading: string;
  analysisDescription: string;
  providerHeading: string;
  providerReady: (provider: string) => string;
  providerNotReady: (provider: string) => string;
  providerUnknown: string;
  providerManaged: string;
  providerLastChecked: string;
  refreshProvider: string;
  checkingProvider: string;
  analyze: string;
  analyzing: string;
  analyzed: string;
  unavailable: string;
  analysisRequired: string;
  analysisRunning: string;
  analysisComplete: string;
  retryAnalysis: string;
  prepareAnalysis: string;
  createBatch: string;
  batchPreflightRequired: string;
  batchCreationPending: string;
  continueContributions: string;
  continueManually: string;
  back: string;
  editSelection: string;
  startOver: string;
  startOverConfirm: string;
  navigationBlockedByBatch: string;
  factsHeading: string;
  factsDescription: string;
  noFacts: string;
  inferenceHeading: string;
  inferenceDescription: string;
  noInferences: string;
  skipped: (count: number) => string;
  contributionsHeading: string;
  contributionsDescription: string;
  ownerStatementLabel: string;
  ownerStatementHelp: string;
  suggest: string;
  suggesting: string;
  manualEntry: string;
  manualEntryHelp: string;
  statementRequired: string;
  proposalHeading: string;
  proposalDescription: string;
  originalStatement: string;
  proposedAssertionsHeading: string;
  proposedAssertionsDescription: string;
  roleLabel: string;
  summaryLabel: string;
  claimsHeading: string;
  claimLabel: (kind: string) => string;
  accept: string;
  saveEditsAndAccept: string;
  reject: string;
  proposalRequired: string;
  assertionConfirmed: string;
  confirmationRequired: string;
  profileHeading: string;
  profileDescription: string;
  displayNameLabel: string;
  headlineLabel: string;
  bioLabel: string;
  greetingLabel: string;
  profileLocale: (locale: Locale) => string;
  profileRequired: string;
  confirmProfile: string;
  continueReview: string;
  reviewHeading: string;
  reviewDescription: string;
  confirmed: string;
  notConfirmed: string;
  createDraft: string;
  draftHeading: string;
  draftDescription: string;
  copyDraft: string;
  downloadDraft: string;
  draftReady: string;
  advancedMode: string;
  guidedMode: string;
  rawYamlWarning: string;
  busy: string;
  errorHeading: string;
  disabledBusy: string;
  disabledNeedsAccount: string;
  disabledSelectionConfirmed: string;
  disabledNoSelection: string;
  disabledAnalysisRunning: string;
  disabledNeedsAnalysis: string;
  disabledNeedsStatement: string;
  disabledNeedsProposal: string;
  disabledNeedsBilingualContribution: string;
  disabledNeedsConfirmation: string;
};

const COPY: Record<Locale, Copy> = {
  "zh-TW": {
    product: "RepoNPC",
    title: "引導式作品集設定",
    introTitle: "讓 RepoNPC 認識你的作品",
    introBody:
      "選擇公開的 GitHub 專案，檢視專案中可確認的資訊，再由你確認自己的貢獻。最後會產生可預覽、複製或下載的雙語設定檔。",
    outcome: "你會得到",
    outcomeItems: [
      "清楚分開的專案中可確認的資訊與 AI 推論",
      "只在你確認或編輯後才會成為你已確認的個人貢獻",
      "不需要 GitHub 寫入權杖也能驗證、預覽、複製或下載的設定草稿",
    ],
    start: "開始引導設定",
    startAi: "設定 AI 並開始",
    startManual: "先手動建立作品集",
    modelsHeading: "設定 AI 模型",
    modelsDescription:
      "先分別測試分析與回答模型、資料查找模型，再選擇要用於分析。資料查找模型會整理作品內容，協助找到回答的參考依據。這不會改變公開網站使用的模型。",
    confirmModels: "完成模型設定並選擇專案",
    modelsRequired:
      "請先測試回答模型與資料查找模型，再於選擇區按「確認用於分析」。",
    advanced: "使用進階 raw YAML",
    advancedDescription: "熟悉 schema 的使用者可以直接編輯 reponpc.yml。",
    progress: "引導設定進度",
    steps: {
      intro: "歡迎",
      models: "設定 AI 模型",
      repositories: "探索與選擇",
      analysis: "分析",
      contributions: "確認貢獻",
      profile: "基本資料",
      review: "檢閱",
      draft: "草稿完成",
    },
    accountHeading: "探索公開專案",
    accountLabel: "GitHub 使用者名稱或個人檔案 URL",
    accountHelp: "只會讀取公開專案資訊；勾選並確認前不會下載程式碼或呼叫模型。",
    discover: "探索專案",
    discoverAgain: "載入下一頁",
    searchLabel: "篩選已載入的專案",
    noMatches: "沒有符合篩選條件的專案。",
    discoveryComplete: "已完成最多五頁的探索，或沒有更多公開專案。",
    manualHeading: "手動加入專案",
    repositoryLabel: "專案識別字串或 GitHub 網址",
    repositoryHelp: "格式為 owner/name 或 https://github.com/owner/name。",
    refLabel: "版本（分支、標籤或 commit SHA）",
    refOptional: "可選",
    resolve: "解析專案",
    repositoryHeading: "公開專案",
    repositoryCount: (selected, total) => `已選 ${selected} 個，共 ${total} 個`,
    repositoryDescription: "使用鍵盤勾選你想呈現的專案。",
    selected: "已選取",
    archived: "已封存",
    fork: "fork",
    languageLabel: "語言",
    defaultBranchLabel: "預設分支",
    githubLabel: "GitHub",
    optionsLegend: "專案選項",
    includeLabel: "包含路徑（逗號分隔）",
    excludeLabel: "排除路徑（逗號分隔）",
    noRepositories: "目前沒有專案資訊。請先探索或手動加入。",
    confirmSelection: "確認選取並繼續分析",
    selectionRequired: "至少勾選一個專案後才能繼續。",
    selectionLocked: "選取已確認；你可以在後續步驟返回編輯。",
    analysisHeading: "分析已選專案",
    analysisDescription:
      "分析你已確認的公開專案；完成後檢視專案中可確認的資訊與 AI 推論，再填寫自己的貢獻。",
    providerHeading: "模型連線",
    providerReady: (provider) => `已連線：${provider}`,
    providerNotReady: (provider) =>
      `${provider} 尚未就緒。專案探索仍可使用；分析失敗後可改用手動填寫。`,
    providerUnknown: "尚未取得模型連線狀態。",
    providerManaged:
      "Ollama、vLLM 與 OpenAI-compatible 的連線資料由伺服器管理，API 金鑰與私人網址不會傳到瀏覽器。",
    providerLastChecked: "最後檢查",
    refreshProvider: "重新檢查",
    checkingProvider: "正在檢查模型連線…",
    analyze: "分析專案",
    analyzing: "分析中…",
    analyzed: "分析完成",
    unavailable: "分析不可用",
    analysisRequired: "請先確認專案選取。",
    analysisRunning: "此專案正在分析；完成後才可再次操作。",
    analysisComplete: "已取得分析結果；如需更新可明確重新分析。",
    retryAnalysis: "重新分析",
    prepareAnalysis: "準備批次分析",
    createBatch: "開始批次分析",
    batchPreflightRequired: "請先完成可用的分析前檢查。",
    batchCreationPending: "正在建立批次分析。",
    continueContributions: "檢視專案中可確認的資訊並填寫貢獻",
    continueManually: "略過分析，手動填寫貢獻",
    back: "返回",
    editSelection: "編輯專案選擇",
    startOver: "重新開始",
    startOverConfirm: "重新開始會清除目前尚未儲存的引導內容。確定繼續嗎？",
    navigationBlockedByBatch:
      "目前批次分析仍在執行。請先在下方取消批次，等待狀態更新後再返回、編輯選擇或重新開始。",
    factsHeading: "專案中可確認的資訊",
    factsDescription: "直接來自已固定 commit 的專案內容；不代表個人貢獻。",
    noFacts: "沒有可顯示的專案中可確認資訊。",
    inferenceHeading: "AI 推論",
    inferenceDescription:
      "AI 根據參考依據提出的推論；不會自動成為你已確認的個人貢獻。",
    noInferences: "沒有 AI 推論。",
    skipped: (count) => `已略過 ${count} 個不符合安全規則的項目`,
    contributionsHeading: "你對這個專案的貢獻",
    contributionsDescription:
      "請用自己的話描述工作與不應歸屬給你的內容。AI 建議只是草稿，必須由你確認或編輯。",
    ownerStatementLabel: "你的貢獻說明",
    ownerStatementHelp:
      "原文會一直顯示在建議旁邊；專案內容無法證明你的身分或角色。",
    suggest: "產生可編輯建議",
    suggesting: "產生建議中…",
    manualEntry: "手動輸入貢獻",
    manualEntryHelp: "模型不可用時，你仍可直接填寫雙語角色、摘要與貢獻描述。",
    statementRequired: "先填寫你的貢獻說明才能請求建議。",
    proposalHeading: "AI 建議（尚未確認）",
    proposalDescription:
      "以下欄位可以編輯；只有你明確確認或編輯後接受，才會成為你已確認的個人貢獻。",
    originalStatement: "你的原始貢獻說明",
    proposedAssertionsHeading: "待你確認的個人貢獻",
    proposedAssertionsDescription: "這些內容仍是草稿，尚未進入 YAML。",
    roleLabel: "角色",
    summaryLabel: "摘要",
    claimsHeading: "貢獻描述",
    claimLabel: (kind) =>
      ({
        role: "角色",
        responsibility: "負責內容",
        achievement: "成果",
        context: "背景",
      })[kind] ?? kind,
    accept: "確認這份貢獻",
    saveEditsAndAccept: "儲存編輯並接受",
    reject: "拒絕並重新填寫",
    proposalRequired: "先產生建議，或拒絕後重新填寫你的貢獻說明。",
    assertionConfirmed: "此專案的貢獻已由你確認。",
    confirmationRequired:
      "每個已選專案都需要確認貢獻後才能繼續。拒絕建議後，請重新填寫並確認。",
    profileHeading: "填寫基本資料",
    profileDescription:
      "這些公開文字會成為完整設定草稿的一部分；請提供中英文內容，不要讓模型替你猜測個人資料。",
    displayNameLabel: "顯示名稱",
    headlineLabel: "一句話介紹自己",
    bioLabel: "簡介",
    greetingLabel: "問候語",
    profileLocale: (locale) => (locale === "zh-TW" ? "繁體中文" : "English"),
    profileRequired: "完成所有中英文基本資料欄位後才能繼續。",
    confirmProfile: "確認基本資料並檢閱草稿",
    continueReview: "繼續檢閱草稿",
    reviewHeading: "檢閱已確認內容",
    reviewDescription:
      "再次確認哪些文字會進入設定草稿；尚未確認的 AI 推論不會進入草稿。",
    confirmed: "已確認",
    notConfirmed: "尚未確認",
    createDraft: "建立完整 YAML 草稿",
    draftHeading: "草稿已準備好",
    draftDescription:
      "草稿可先通過既有的驗證與預覽；儲存到 GitHub 是另一個明確動作。",
    copyDraft: "複製 YAML",
    downloadDraft: "下載 YAML",
    draftReady: "YAML 草稿已建立，可在進階模式中檢視。",
    advancedMode: "進階 raw YAML 模式",
    guidedMode: "返回引導模式",
    rawYamlWarning: "raw YAML 有無法對應回引導欄位的變更；請在進階模式中處理。",
    busy: "正在處理；目前操作可能暫時停用。",
    errorHeading: "引導設定錯誤",
    disabledBusy: "目前操作進行中，請稍候。",
    disabledNeedsAccount: "輸入 GitHub 使用者名稱或 URL 後才能探索。",
    disabledSelectionConfirmed: "選取已確認；不能在此步驟再修改。",
    disabledNoSelection: "至少選取一個專案後才能繼續。",
    disabledAnalysisRunning: "等待目前分析完成。",
    disabledNeedsAnalysis: "完成所有已選專案的分析後才能繼續。",
    disabledNeedsStatement: "填寫原始貢獻說明後才能產生建議。",
    disabledNeedsProposal: "先產生一份模型建議，或完成可確認的貢獻文字。",
    disabledNeedsBilingualContribution:
      "請完成繁體中文與 English 的角色和摘要後才能接受。",
    disabledNeedsConfirmation:
      "請確認每個專案的貢獻；拒絕建議後仍需重新填寫並確認。",
  },
  en: {
    product: "RepoNPC",
    title: "Guided portfolio setup",
    introTitle: "Let RepoNPC understand your work",
    introBody:
      "Choose public GitHub projects, review information you can verify from them, and confirm your own contribution. The result is a complete bilingual configuration draft that you can validate, preview, copy, or download.",
    outcome: "You will get",
    outcomeItems: [
      "Project information you can verify, kept separate from AI inferences",
      "Your confirmed contribution appears only after you accept or edit it",
      "A YAML configuration draft that works without a GitHub writeback token",
    ],
    start: "Start guided setup",
    startAi: "Set up AI and begin",
    startManual: "Build manually first",
    modelsHeading: "Set up AI models",
    modelsDescription:
      "Test the analysis/chat model and content finder separately, then choose them for analysis. The content finder organizes project content and locates supporting information for answers. This does not change the model used by the public website.",
    confirmModels: "Finish model setup and choose projects",
    modelsRequired:
      "Test both models, then select them and choose Use for analysis in the selection panel.",
    advanced: "Use advanced raw YAML",
    advancedDescription: "Experienced owners can edit reponpc.yml directly.",
    progress: "Guided setup progress",
    steps: {
      intro: "Welcome",
      models: "Set up AI models",
      repositories: "Discover and select",
      analysis: "Analyze",
      contributions: "Confirm contribution",
      profile: "Basic profile",
      review: "Review",
      draft: "Draft ready",
    },
    accountHeading: "Discover public projects",
    accountLabel: "GitHub username or profile URL",
    accountHelp:
      "Only public project information is read; no code is downloaded and no model call happens before you confirm the checkboxes.",
    discover: "Discover projects",
    discoverAgain: "Load next page",
    searchLabel: "Filter loaded projects",
    noMatches: "No loaded project matches this filter.",
    discoveryComplete:
      "Discovery reached five pages or GitHub has no more public projects.",
    manualHeading: "Add a project manually",
    repositoryLabel: "Project identifier or GitHub URL",
    repositoryHelp: "Use owner/name or https://github.com/owner/name.",
    refLabel: "Version (branch, tag, or commit SHA)",
    refOptional: "optional",
    resolve: "Resolve project",
    repositoryHeading: "Public projects",
    repositoryCount: (selected, total) => `${selected} selected of ${total}`,
    repositoryDescription:
      "Use the keyboard to choose the projects you want to present.",
    selected: "Selected",
    archived: "archived",
    fork: "fork",
    languageLabel: "Language",
    defaultBranchLabel: "Default branch",
    githubLabel: "GitHub",
    optionsLegend: "Project options",
    includeLabel: "Include paths (comma separated)",
    excludeLabel: "Exclude paths (comma separated)",
    noRepositories:
      "No project information yet. Discover an account or add one manually.",
    confirmSelection: "Confirm selection and continue to analysis",
    selectionRequired: "Select at least one project before continuing.",
    selectionLocked:
      "Selection is confirmed. You can return and edit it from later steps.",
    analysisHeading: "Analyze selected projects",
    analysisDescription:
      "Analyze confirmed public projects, then review information you can verify from each project and AI inferences before describing your contribution.",
    providerHeading: "Model connection",
    providerReady: (provider) => `Connected: ${provider}`,
    providerNotReady: (provider) =>
      `${provider} is not ready. Project discovery still works; after an analysis failure you can continue with manual entry.`,
    providerUnknown: "The model connection status is unavailable.",
    providerManaged:
      "Ollama, vLLM, and OpenAI-compatible connection details are managed by the server. API keys and private URLs are never sent to the browser.",
    providerLastChecked: "Last checked",
    refreshProvider: "Recheck",
    checkingProvider: "Checking the model connection…",
    analyze: "Analyze project",
    analyzing: "Analyzing…",
    analyzed: "Analysis complete",
    unavailable: "Analysis unavailable",
    analysisRequired: "Confirm your project selection first.",
    analysisRunning: "This project is being analyzed; wait for it to finish.",
    analysisComplete:
      "Analysis is complete; explicitly retry if you want a fresh result.",
    retryAnalysis: "Analyze again",
    prepareAnalysis: "Prepare batch analysis",
    createBatch: "Start batch analysis",
    batchPreflightRequired: "Complete an available preflight before starting.",
    batchCreationPending: "Creating the analysis batch.",
    continueContributions:
      "Review information you can verify and describe contribution",
    continueManually: "Skip analysis and enter contribution manually",
    back: "Back",
    editSelection: "Edit project selection",
    startOver: "Start over",
    startOverConfirm:
      "Starting over clears the unsaved guided setup. Continue?",
    navigationBlockedByBatch:
      "A batch analysis is still running. Cancel it below and wait for the status update before going back, editing the selection, or starting over.",
    factsHeading: "Project information you can verify",
    factsDescription:
      "Directly observed at the pinned commit; it does not prove personal contribution.",
    noFacts: "No verifiable project information to display.",
    inferenceHeading: "AI inferences",
    inferenceDescription:
      "AI suggestions grounded in supporting information; they never become your confirmed contribution automatically.",
    noInferences: "No AI inferences.",
    skipped: (count) => `${count} items were skipped by safety rules`,
    contributionsHeading: "Your contribution to this project",
    contributionsDescription:
      "Describe your work and boundaries in your own words. AI suggestions are drafts that require explicit confirmation or editing.",
    ownerStatementLabel: "Your contribution description",
    ownerStatementHelp:
      "The original text stays beside every suggestion; project content cannot establish your identity or role.",
    suggest: "Generate editable suggestion",
    suggesting: "Generating suggestion…",
    manualEntry: "Enter contribution manually",
    manualEntryHelp:
      "When the model is unavailable, fill in the bilingual role, summary, and contribution descriptions yourself.",
    statementRequired:
      "Enter your contribution description before requesting a suggestion.",
    proposalHeading: "AI suggestion (unconfirmed)",
    proposalDescription:
      "Edit these fields, then explicitly confirm the suggestion. Only explicit confirmation makes this your confirmed contribution.",
    originalStatement: "Your original contribution description",
    proposedAssertionsHeading:
      "Personal contribution awaiting your confirmation",
    proposedAssertionsDescription:
      "These are proposals only and are not in YAML yet.",
    roleLabel: "Role",
    summaryLabel: "Summary",
    claimsHeading: "Contribution descriptions",
    claimLabel: (kind) =>
      ({
        role: "Role",
        responsibility: "Responsibilities",
        achievement: "Achievement",
        context: "Context",
      })[kind] ?? kind,
    accept: "Confirm contribution",
    saveEditsAndAccept: "Save edits and accept",
    reject: "Reject and rewrite",
    proposalRequired:
      "Generate a suggestion first, or reject it and write a new contribution description.",
    assertionConfirmed: "You confirmed this project's contribution.",
    confirmationRequired:
      "Confirm a contribution for every selected project. After rejecting a suggestion, rewrite and confirm it before continuing.",
    profileHeading: "Add your basic profile",
    profileDescription:
      "These public fields become part of the complete YAML draft. Supply both languages; do not ask a model to guess personal profile details.",
    displayNameLabel: "Display name",
    headlineLabel: "One-line introduction",
    bioLabel: "Bio",
    greetingLabel: "Greeting",
    profileLocale: (locale) =>
      locale === "zh-TW" ? "Traditional Chinese" : "English",
    profileRequired:
      "Complete every bilingual profile field before continuing.",
    confirmProfile: "Confirm profile and review draft",
    continueReview: "Continue to draft review",
    reviewHeading: "Review confirmed content",
    reviewDescription:
      "Confirm which text enters the configuration draft; unconfirmed AI inferences stay out of the draft.",
    confirmed: "Confirmed",
    notConfirmed: "Not confirmed",
    createDraft: "Create complete YAML draft",
    draftHeading: "Draft ready",
    draftDescription:
      "Run the existing checks and preview first; saving to GitHub remains a separate explicit action.",
    copyDraft: "Copy YAML",
    downloadDraft: "Download YAML",
    draftReady: "The YAML draft is ready to inspect in advanced mode.",
    advancedMode: "Advanced raw YAML mode",
    guidedMode: "Return to guided mode",
    rawYamlWarning:
      "Raw YAML has changes that cannot map back to guided fields; resolve them in advanced mode.",
    busy: "Working; some actions are temporarily disabled.",
    errorHeading: "Guided setup error",
    disabledBusy: "An operation is in progress; wait a moment.",
    disabledNeedsAccount:
      "Enter a GitHub username or URL before discovering projects.",
    disabledSelectionConfirmed:
      "Selection is confirmed and cannot be edited at this step.",
    disabledNoSelection: "Select at least one project before continuing.",
    disabledAnalysisRunning: "Wait for the current analysis to finish.",
    disabledNeedsAnalysis:
      "Complete analysis for every selected project before continuing.",
    disabledNeedsStatement:
      "Enter your contribution description before generating a suggestion.",
    disabledNeedsProposal:
      "Generate a proposal first, or finish contribution text that can be confirmed.",
    disabledNeedsBilingualContribution:
      "Complete both Traditional Chinese and English role and summary fields before accepting.",
    disabledNeedsConfirmation:
      "Confirm each project's contribution. Rejected suggestions must be rewritten and confirmed before continuing.",
  },
};

function localized(value: LocalizedText, locale: Locale): string {
  return value[locale];
}

function selectedRepositories(
  state: GuidedOnboardingState,
): GuidedRepository[] {
  return state.repositories.filter((repository) => repository.selected);
}

function analysisReady(repository: GuidedRepository): boolean {
  return (
    repository.analysisStatus === "complete" && repository.analysis !== null
  );
}

function analysisButtonReason(
  repository: GuidedRepository,
  state: GuidedOnboardingState,
  copy: Copy,
  busy: boolean,
): string | null {
  if (busy) return copy.disabledBusy;
  if (!state.selectionConfirmed) return copy.analysisRequired;
  if (repository.analysisStatus === "running") return copy.analysisRunning;
  return null;
}

function updateProposal(
  proposal: ContributionProposal,
  update: Partial<ContributionProposal>,
): ContributionProposal {
  return {
    role: { ...proposal.role },
    summary: { ...proposal.summary },
    claims: proposal.claims.map((claim) => ({
      ...claim,
      statement: { ...claim.statement },
    })),
    ...update,
  };
}

function updateClaim(
  proposal: ContributionProposal,
  index: number,
  locale: Locale,
  value: string,
): ContributionProposal {
  return updateProposal(proposal, {
    claims: proposal.claims.map((claim, claimIndex) =>
      claimIndex === index
        ? { ...claim, statement: { ...claim.statement, [locale]: value } }
        : { ...claim, statement: { ...claim.statement } },
    ),
  });
}

function proposalWithField(
  proposal: ContributionProposal,
  field: "role" | "summary",
  locale: Locale,
  value: string,
): ContributionProposal {
  return updateProposal(proposal, {
    [field]: { ...proposal[field], [locale]: value },
  });
}

function profileWithField(
  profile: GuidedProfile,
  field: "headline" | "bio" | "greeting",
  locale: Locale,
  value: string,
): GuidedProfile {
  return {
    ...profile,
    [field]: { ...profile[field], [locale]: value },
  };
}

function profileWithDisplayName(
  profile: GuidedProfile,
  value: string,
): GuidedProfile {
  return { ...profile, displayName: value };
}

function profileIsComplete(profile: GuidedProfile): boolean {
  return [
    profile.displayName,
    profile.headline["zh-TW"],
    profile.headline.en,
    profile.bio["zh-TW"],
    profile.bio.en,
    profile.greeting["zh-TW"],
    profile.greeting.en,
  ].every((value) => value.trim().length > 0);
}

function dispatchProposal(
  onAction: GuidedOnboardingViewProps["onAction"],
  repository: GuidedRepository,
  proposal: ContributionProposal,
): void {
  onAction({
    type: "SET_CONTRIBUTION_PROPOSAL",
    slug: repository.metadata.slug,
    originalStatement: repository.ownerStatement,
    proposal,
  });
}

function disabledReason(reason: string | null, id: string): ReactNode {
  return reason ? (
    <p className="guided-onboarding__disabled-reason" id={id} role="status">
      {reason}
    </p>
  ) : null;
}

function providerDisplayName(
  locale: Locale,
  provider: NonNullable<
    GuidedOnboardingViewProps["providerStatus"]
  >["provider"],
): string {
  if (provider === "ollama") return "Ollama";
  if (provider === "openai_compatible") {
    return locale === "zh-TW"
      ? "OpenAI-compatible（包含 vLLM）"
      : "OpenAI-compatible (including vLLM)";
  }
  return locale === "zh-TW" ? "尚未設定" : "Not configured";
}

function EvidenceFact({ fact }: { fact: RepositoryFact }) {
  const location =
    fact.start_line === null
      ? fact.path
      : `${fact.path}:${fact.start_line}${
          fact.end_line && fact.end_line !== fact.start_line
            ? `-${fact.end_line}`
            : ""
        }`;
  return (
    <li>
      <strong>{location}</strong>
      <span>{fact.text}</span>
      <code>{fact.evidence_id}</code>
    </li>
  );
}

function EvidenceInference({
  inference,
  locale,
}: {
  inference: ModelInference;
  locale: Locale;
}) {
  return (
    <li>
      <span>{localized(inference.statement, locale)}</span>
      <small>
        {inference.supporting_evidence_ids.length > 0
          ? inference.supporting_evidence_ids.join(", ")
          : "—"}
      </small>
    </li>
  );
}

function EvidenceGroups({
  repository,
  locale,
  copy,
}: {
  repository: GuidedRepository;
  locale: Locale;
  copy: Copy;
}) {
  const analysis = repository.analysis;
  if (!analysis) return null;
  return (
    <div className="guided-onboarding__evidence-groups">
      <section
        aria-labelledby={`guided-facts-${repository.metadata.slug}`}
        className="guided-onboarding__evidence guided-onboarding__evidence--facts"
        data-evidence-class="REPOSITORY_FACT"
      >
        <h5 id={`guided-facts-${repository.metadata.slug}`}>
          {copy.factsHeading}
        </h5>
        <p>{copy.factsDescription}</p>
        {analysis.facts.length > 0 ? (
          <ul>
            {analysis.facts.map((fact) => (
              <EvidenceFact fact={fact} key={fact.evidence_id} />
            ))}
          </ul>
        ) : (
          <p>{copy.noFacts}</p>
        )}
      </section>

      <section
        aria-labelledby={`guided-inferences-${repository.metadata.slug}`}
        className="guided-onboarding__evidence guided-onboarding__evidence--inferences"
        data-evidence-class="MODEL_INFERENCE"
      >
        <h5 id={`guided-inferences-${repository.metadata.slug}`}>
          {copy.inferenceHeading}
        </h5>
        <p>{copy.inferenceDescription}</p>
        {analysis.inferences.length > 0 ? (
          <ul>
            {analysis.inferences.map((inference, index) => (
              <EvidenceInference
                inference={inference}
                key={`${repository.metadata.slug}-inference-${index}`}
                locale={locale}
              />
            ))}
          </ul>
        ) : (
          <p>{copy.noInferences}</p>
        )}
      </section>
    </div>
  );
}

function RepositoryRow({
  repository,
  state,
  locale,
  copy,
  busy,
  onAction,
  onAnalyze,
}: {
  repository: GuidedRepository;
  state: GuidedOnboardingState;
  locale: Locale;
  copy: Copy;
  busy: boolean;
  onAction: GuidedOnboardingViewProps["onAction"];
  onAnalyze: GuidedOnboardingViewProps["onAnalyze"];
}) {
  const slugId = repository.metadata.slug.replace(/[^a-zA-Z0-9_-]/g, "-");
  const selectionLocked = state.selectionConfirmed;
  const reason = analysisButtonReason(repository, state, copy, busy);
  const disabled = reason !== null || !repository.selected;
  const disabledMessage = !repository.selected
    ? copy.disabledNoSelection
    : reason;

  function optionChange(
    field: "ref" | "include" | "exclude",
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const value = event.target.value;
    const options = {
      ref: repository.ref,
      include: repository.include,
      exclude: repository.exclude,
      [field]:
        field === "ref"
          ? value || null
          : value
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean),
    };
    onAction({
      type: "SET_REPOSITORY_OPTIONS",
      slug: repository.metadata.slug,
      ref: options.ref,
      include: options.include,
      exclude: options.exclude,
    });
  }

  return (
    <li
      className="guided-onboarding__repository"
      data-slug={repository.metadata.slug}
    >
      <div className="guided-onboarding__repository-header">
        <CheckboxField
          checked={repository.selected}
          disabled={selectionLocked || busy}
          id={`guided-repository-${slugId}`}
          onChange={() =>
            onAction({
              type: "TOGGLE_REPOSITORY",
              slug: repository.metadata.slug,
            })
          }
        >
          <strong>{repository.metadata.name}</strong>
          <code>{repository.metadata.slug}</code>
        </CheckboxField>
        <span>
          {repository.selected ? copy.selected : ""}
          {repository.metadata.is_archived ? ` · ${copy.archived}` : ""}
          {repository.metadata.is_fork ? ` · ${copy.fork}` : ""}
        </span>
      </div>
      {repository.metadata.description && (
        <p>{repository.metadata.description}</p>
      )}
      <dl className="guided-onboarding__repository-meta">
        {repository.metadata.primary_language && (
          <>
            <dt>{copy.languageLabel}</dt>
            <dd>{repository.metadata.primary_language}</dd>
          </>
        )}
        <dt>{copy.defaultBranchLabel}</dt>
        <dd>{repository.metadata.default_branch}</dd>
        <dt>{copy.githubLabel}</dt>
        <dd>
          <a
            href={repository.metadata.html_url}
            rel="noopener noreferrer"
            target="_blank"
          >
            {repository.metadata.html_url}
          </a>
        </dd>
      </dl>
      {!selectionLocked && (
        <details>
          <summary>{copy.optionsLegend}</summary>
          <fieldset disabled={busy}>
            <legend>{copy.optionsLegend}</legend>
            <label htmlFor={`guided-ref-${slugId}`}>
              {copy.refLabel} ({copy.refOptional})
              <input
                id={`guided-ref-${slugId}`}
                onChange={(event) => optionChange("ref", event)}
                value={repository.ref ?? ""}
              />
            </label>
            <label htmlFor={`guided-include-${slugId}`}>
              {copy.includeLabel}
              <input
                id={`guided-include-${slugId}`}
                onChange={(event) => optionChange("include", event)}
                value={repository.include.join(", ")}
              />
            </label>
            <label htmlFor={`guided-exclude-${slugId}`}>
              {copy.excludeLabel}
              <input
                id={`guided-exclude-${slugId}`}
                onChange={(event) => optionChange("exclude", event)}
                value={repository.exclude.join(", ")}
              />
            </label>
          </fieldset>
        </details>
      )}
      {selectionLocked && <p>{copy.selectionLocked}</p>}
      {state.step === "analysis" && (
        <div className="guided-onboarding__analysis-action">
          <button
            aria-describedby={
              disabledMessage ? `guided-analysis-reason-${slugId}` : undefined
            }
            disabled={disabled}
            onClick={() => onAnalyze(repository.metadata.slug)}
            type="button"
          >
            {repository.analysisStatus === "running"
              ? copy.analyzing
              : repository.analysisStatus === "complete"
                ? copy.retryAnalysis
                : repository.analysisStatus === "unavailable"
                  ? copy.retryAnalysis
                  : copy.analyze}
          </button>
          {disabledReason(
            disabledMessage ?? null,
            `guided-analysis-reason-${slugId}`,
          )}
          {repository.analysisStatus === "complete" && (
            <p role="status">{copy.analyzed}</p>
          )}
          {repository.analysisStatus === "unavailable" && (
            <p role="alert">{copy.unavailable}</p>
          )}
          {analysisReady(repository) && (
            <EvidenceGroups
              copy={copy}
              locale={locale}
              repository={repository}
            />
          )}
        </div>
      )}
    </li>
  );
}

function ContributionEditor({
  repository,
  copy,
  busy,
  onAction,
  onSuggestContribution,
}: {
  repository: GuidedRepository;
  copy: Copy;
  busy: boolean;
  onAction: GuidedOnboardingViewProps["onAction"];
  onSuggestContribution: GuidedOnboardingViewProps["onSuggestContribution"];
}) {
  const slugId = repository.metadata.slug.replace(/[^a-zA-Z0-9_-]/g, "-");
  const statementMissing = repository.ownerStatement.trim().length === 0;
  const suggestDisabled = busy || statementMissing;
  const suggestReason = busy
    ? copy.disabledBusy
    : statementMissing
      ? copy.disabledNeedsStatement
      : null;

  function ownerStatementChange(event: ChangeEvent<HTMLTextAreaElement>) {
    onAction({
      type: "SET_OWNER_STATEMENT",
      slug: repository.metadata.slug,
      statement: event.target.value,
    });
  }

  function confirmContribution(contribution: ContributionProposal) {
    onAction({
      type: "CONFIRM_CONTRIBUTION",
      slug: repository.metadata.slug,
      contribution,
    });
  }

  function proposalChange(next: ContributionProposal) {
    dispatchProposal(onAction, repository, next);
  }

  const proposal = repository.proposal;
  const proposalMissingBilingual = proposal
    ? [
        proposal.role["zh-TW"],
        proposal.role.en,
        proposal.summary["zh-TW"],
        proposal.summary.en,
      ].some((value) => value.trim().length === 0)
    : false;
  const proposalDisabledReason = !proposal
    ? copy.disabledNeedsProposal
    : proposalMissingBilingual
      ? copy.disabledNeedsBilingualContribution
      : busy
        ? copy.disabledBusy
        : null;
  return (
    <article
      aria-labelledby={`guided-contribution-${slugId}`}
      className="guided-onboarding__contribution"
      data-slug={repository.metadata.slug}
    >
      <h4 id={`guided-contribution-${slugId}`}>{repository.metadata.name}</h4>
      <p>{copy.contributionsDescription}</p>
      <label htmlFor={`guided-owner-statement-${slugId}`}>
        {copy.ownerStatementLabel}
        <textarea
          aria-describedby={`guided-owner-statement-help-${slugId}`}
          disabled={busy}
          id={`guided-owner-statement-${slugId}`}
          onChange={ownerStatementChange}
          rows={4}
          value={repository.ownerStatement}
        />
      </label>
      <p id={`guided-owner-statement-help-${slugId}`}>
        {copy.ownerStatementHelp}
      </p>
      <button
        aria-describedby={
          suggestReason ? `guided-suggest-reason-${slugId}` : undefined
        }
        disabled={suggestDisabled}
        onClick={() => onSuggestContribution(repository.metadata.slug)}
        type="button"
      >
        {busy ? copy.suggesting : copy.suggest}
      </button>
      {disabledReason(suggestReason, `guided-suggest-reason-${slugId}`)}

      {!proposal && !repository.confirmedContribution && (
        <>
          <p>{copy.manualEntryHelp}</p>
          <button
            aria-describedby={
              suggestReason ? `guided-suggest-reason-${slugId}` : undefined
            }
            disabled={busy || statementMissing}
            onClick={() =>
              onAction({
                type: "BEGIN_MANUAL_CONTRIBUTION",
                slug: repository.metadata.slug,
              })
            }
            type="button"
          >
            {copy.manualEntry}
          </button>
        </>
      )}

      {repository.confirmedContribution && (
        <p className="guided-onboarding__confirmed" role="status">
          {copy.assertionConfirmed}
        </p>
      )}

      {proposal && (
        <section
          aria-labelledby={`guided-proposal-${slugId}`}
          className="guided-onboarding__proposal"
          data-evidence-class="OWNER_ASSERTION"
          data-confirmed={repository.confirmedContribution ? "true" : "false"}
        >
          <h5 id={`guided-proposal-${slugId}`}>{copy.proposalHeading}</h5>
          <p>{copy.proposalDescription}</p>
          <p>
            <strong>{copy.originalStatement}:</strong>{" "}
            {repository.ownerStatement}
          </p>
          <section
            aria-labelledby={`guided-proposed-assertions-${slugId}`}
            className="guided-onboarding__evidence guided-onboarding__evidence--proposed-assertions"
          >
            <h6 id={`guided-proposed-assertions-${slugId}`}>
              {copy.proposedAssertionsHeading}
            </h6>
            <p>{copy.proposedAssertionsDescription}</p>
            {(["zh-TW", "en"] as const).map((proposalLocale) => (
              <label
                htmlFor={`guided-role-${slugId}-${proposalLocale}`}
                key={`role-${proposalLocale}`}
              >
                {copy.roleLabel} ({copy.profileLocale(proposalLocale)})
                <input
                  disabled={busy}
                  id={`guided-role-${slugId}-${proposalLocale}`}
                  onChange={(event) =>
                    proposalChange(
                      proposalWithField(
                        proposal,
                        "role",
                        proposalLocale,
                        event.target.value,
                      ),
                    )
                  }
                  value={localized(proposal.role, proposalLocale)}
                />
              </label>
            ))}
            {(["zh-TW", "en"] as const).map((proposalLocale) => (
              <label
                htmlFor={`guided-summary-${slugId}-${proposalLocale}`}
                key={`summary-${proposalLocale}`}
              >
                {copy.summaryLabel} ({copy.profileLocale(proposalLocale)})
                <textarea
                  disabled={busy}
                  id={`guided-summary-${slugId}-${proposalLocale}`}
                  onChange={(event) =>
                    proposalChange(
                      proposalWithField(
                        proposal,
                        "summary",
                        proposalLocale,
                        event.target.value,
                      ),
                    )
                  }
                  rows={3}
                  value={localized(proposal.summary, proposalLocale)}
                />
              </label>
            ))}
            <fieldset disabled={busy}>
              <legend>{copy.claimsHeading}</legend>
              {proposal.claims.flatMap((claim, index) =>
                (["zh-TW", "en"] as const).map((proposalLocale) => (
                  <label
                    htmlFor={`guided-claim-${slugId}-${index}-${proposalLocale}`}
                    key={`${claim.id}-${proposalLocale}`}
                  >
                    {copy.claimLabel(claim.kind)} (
                    {copy.profileLocale(proposalLocale)})
                    <textarea
                      id={`guided-claim-${slugId}-${index}-${proposalLocale}`}
                      onChange={(event) =>
                        proposalChange(
                          updateClaim(
                            proposal,
                            index,
                            proposalLocale,
                            event.target.value,
                          ),
                        )
                      }
                      rows={2}
                      value={localized(claim.statement, proposalLocale)}
                    />
                  </label>
                )),
              )}
            </fieldset>
          </section>
          <div className="guided-onboarding__proposal-actions">
            <button
              aria-describedby={
                proposalDisabledReason
                  ? `guided-proposal-reason-${slugId}`
                  : undefined
              }
              disabled={Boolean(proposalDisabledReason)}
              className="ux-primary"
              onClick={() => confirmContribution(proposal)}
              type="button"
            >
              {copy.accept}
            </button>
            <button
              disabled={busy}
              onClick={() =>
                onAction({
                  type: "REJECT_CONTRIBUTION",
                  slug: repository.metadata.slug,
                })
              }
              type="button"
            >
              {copy.reject}
            </button>
          </div>
          {disabledReason(
            proposalDisabledReason,
            `guided-proposal-reason-${slugId}`,
          )}
        </section>
      )}
      {!proposal && !repository.confirmedContribution && (
        <p>{copy.proposalRequired}</p>
      )}
    </article>
  );
}

function IntroStep({
  state,
  copy,
  busy,
  onAction,
}: {
  state: GuidedOnboardingState;
  copy: Copy;
  busy: boolean;
  onAction: GuidedOnboardingViewProps["onAction"];
}) {
  return (
    <section
      aria-labelledby="guided-intro-heading"
      className="guided-onboarding__step"
    >
      <h2 id="guided-intro-heading">{copy.introTitle}</h2>
      <p>{copy.introBody}</p>
      <h3>{copy.outcome}</h3>
      <ul>
        {copy.outcomeItems.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <button
        disabled={busy}
        onClick={() => onAction({ type: "START_AI" })}
        type="button"
      >
        {copy.startAi}
      </button>
      <button
        disabled={busy}
        onClick={() => onAction({ type: "START_MANUAL" })}
        type="button"
      >
        {copy.startManual}
      </button>
      {disabledReason(busy ? copy.disabledBusy : null, "guided-start-reason")}
      <button
        className="guided-onboarding__advanced-link"
        disabled={busy}
        onClick={() => onAction({ type: "SET_MODE", mode: "advanced" })}
        type="button"
      >
        {copy.advanced}
      </button>
      <p>{copy.advancedDescription}</p>
      {state.rawYamlHasUnmappedChanges && (
        <p role="alert">{copy.rawYamlWarning}</p>
      )}
    </section>
  );
}

function ModelsStep({
  state,
  copy,
  busy,
  modelSetupView,
  onAction,
}: {
  state: GuidedOnboardingState;
  copy: Copy;
  busy: boolean;
  modelSetupView?: ReactNode;
  onAction: GuidedOnboardingViewProps["onAction"];
}) {
  const reason = busy
    ? copy.disabledBusy
    : !state.modelsConfigured
      ? copy.modelsRequired
      : null;
  return (
    <section
      aria-labelledby="guided-models-heading"
      className="guided-onboarding__step"
    >
      <h2 id="guided-models-heading">{copy.modelsHeading}</h2>
      <p>{copy.modelsDescription}</p>
      {modelSetupView ?? <p>{copy.providerUnknown}</p>}
      <button
        aria-describedby={reason ? "guided-models-reason" : undefined}
        disabled={Boolean(reason) || busy}
        onClick={() => onAction({ type: "COMPLETE_MODEL_SETUP" })}
        className="ux-primary"
        type="button"
      >
        {copy.confirmModels}
      </button>
      {disabledReason(reason, "guided-models-reason")}
      <button
        disabled={busy}
        onClick={() => onAction({ type: "START_MANUAL" })}
        type="button"
      >
        {copy.startManual}
      </button>
    </section>
  );
}

function RepositoriesStep({
  state,
  copy,
  locale,
  busy,
  onAction,
  onDiscover,
  onResolve,
}: {
  state: GuidedOnboardingState;
  copy: Copy;
  locale: Locale;
  busy: boolean;
  onAction: GuidedOnboardingViewProps["onAction"];
  onDiscover: GuidedOnboardingViewProps["onDiscover"];
  onResolve: GuidedOnboardingViewProps["onResolve"];
}) {
  const [search, setSearch] = useState("");
  const selectedCount = selectedRepositories(state).length;
  const accountMissing = state.githubAccount.trim().length === 0;
  const discoveryFinished =
    state.discoveryPage > 0 &&
    (state.discoveryPage >= 5 || !state.discoveryHasMore);
  const normalizedSearch = search.trim().toLowerCase();
  const visibleRepositories = normalizedSearch
    ? state.repositories.filter((repository) =>
        [
          repository.metadata.name,
          repository.metadata.slug,
          repository.metadata.description ?? "",
          repository.metadata.primary_language ?? "",
        ].some((value) => value.toLowerCase().includes(normalizedSearch)),
      )
    : state.repositories;
  const discoverReason = busy
    ? copy.disabledBusy
    : state.selectionConfirmed
      ? copy.disabledSelectionConfirmed
      : discoveryFinished
        ? copy.discoveryComplete
        : accountMissing
          ? copy.disabledNeedsAccount
          : null;
  const selectionReason = busy
    ? copy.disabledBusy
    : selectedCount === 0
      ? copy.disabledNoSelection
      : state.selectionConfirmed
        ? copy.disabledSelectionConfirmed
        : null;

  function resolve(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const repository = String(form.get("repository") ?? "").trim();
    const refValue = String(form.get("ref") ?? "").trim();
    if (repository) onResolve(repository, refValue || null);
  }

  return (
    <section
      aria-labelledby="guided-repositories-heading"
      className="guided-onboarding__step"
    >
      <h2 id="guided-repositories-heading">{copy.accountHeading}</h2>
      <label htmlFor="guided-github-account">{copy.accountLabel}</label>
      <input
        aria-describedby="guided-account-help"
        disabled={state.selectionConfirmed || busy}
        id="guided-github-account"
        onChange={(event) =>
          onAction({ type: "SET_ACCOUNT", account: event.target.value })
        }
        value={state.githubAccount}
      />
      <p id="guided-account-help">{copy.accountHelp}</p>
      <button
        aria-describedby={discoverReason ? "guided-discover-reason" : undefined}
        disabled={Boolean(discoverReason)}
        onClick={() => {
          const account = state.githubAccount.trim();
          const page = state.discoveryPage + 1;
          onDiscover(account, page);
        }}
        type="button"
      >
        {state.discoveryPage > 0 ? copy.discoverAgain : copy.discover}
      </button>
      {disabledReason(discoverReason, "guided-discover-reason")}

      <form aria-labelledby="guided-manual-heading" onSubmit={resolve}>
        <h3 id="guided-manual-heading">{copy.manualHeading}</h3>
        <label htmlFor="guided-manual-repository">{copy.repositoryLabel}</label>
        <input
          aria-describedby="guided-manual-help"
          disabled={state.selectionConfirmed || busy}
          id="guided-manual-repository"
          name="repository"
          required
        />
        <p id="guided-manual-help">{copy.repositoryHelp}</p>
        <label htmlFor="guided-manual-ref">
          {copy.refLabel} ({copy.refOptional})
        </label>
        <input
          disabled={state.selectionConfirmed || busy}
          id="guided-manual-ref"
          name="ref"
        />
        <button disabled={state.selectionConfirmed || busy} type="submit">
          {copy.resolve}
        </button>
      </form>

      <section aria-labelledby="guided-repository-list-heading">
        <h3 id="guided-repository-list-heading">{copy.repositoryHeading}</h3>
        <p>{copy.repositoryCount(selectedCount, state.repositories.length)}</p>
        <p>{copy.repositoryDescription}</p>
        <label htmlFor="guided-repository-search">{copy.searchLabel}</label>
        <input
          id="guided-repository-search"
          onChange={(event) => setSearch(event.target.value)}
          value={search}
        />
        {state.repositories.length > 0 ? (
          <ul aria-live="polite">
            {visibleRepositories.map((repository) => (
              <RepositoryRow
                busy={busy}
                copy={copy}
                key={repository.metadata.slug}
                locale={locale}
                onAction={onAction}
                onAnalyze={() => undefined}
                repository={repository}
                state={state}
              />
            ))}
            {visibleRepositories.length === 0 && <li>{copy.noMatches}</li>}
          </ul>
        ) : (
          <p>{copy.noRepositories}</p>
        )}
      </section>
      <button
        aria-describedby={
          selectionReason ? "guided-selection-reason" : undefined
        }
        disabled={Boolean(selectionReason)}
        onClick={() => onAction({ type: "CONFIRM_SELECTION" })}
        type="button"
      >
        {copy.confirmSelection}
      </button>
      {disabledReason(selectionReason, "guided-selection-reason")}
    </section>
  );
}

function ProviderStatusPanel({
  status,
  pending,
  copy,
  locale,
  busy,
  onRefresh,
}: {
  status: GuidedOnboardingViewProps["providerStatus"];
  pending: boolean;
  copy: Copy;
  locale: Locale;
  busy: boolean;
  onRefresh: GuidedOnboardingViewProps["onRefreshProviderStatus"];
}) {
  const message = pending
    ? copy.checkingProvider
    : status?.ready
      ? copy.providerReady(providerDisplayName(locale, status.provider))
      : status
        ? copy.providerNotReady(providerDisplayName(locale, status.provider))
        : copy.providerUnknown;

  return (
    <div
      aria-labelledby="guided-provider-heading"
      className="guided-onboarding__provider-status"
      role="group"
    >
      <div>
        <h3 id="guided-provider-heading">{copy.providerHeading}</h3>
        <button disabled={busy || pending} onClick={onRefresh} type="button">
          {copy.refreshProvider}
        </button>
      </div>
      <p aria-live="polite" role="status">
        {message}
      </p>
      {status?.lastCheckedAt && (
        <p>
          {copy.providerLastChecked}:{" "}
          <time dateTime={status.lastCheckedAt}>{status.lastCheckedAt}</time>
        </p>
      )}
      <p>{copy.providerManaged}</p>
    </div>
  );
}

function AnalysisStep({
  state,
  copy,
  locale,
  busy,
  providerStatus,
  providerStatusPending,
  batchAnalysisView,
  batchAnalysisTerminal = false,
  batchAnalysisActive,
  batchCanCreate = false,
  batchCreatePending = false,
  onAction,
  onAnalyze,
  onCreateBatch,
  onRefreshProviderStatus,
}: {
  state: GuidedOnboardingState;
  copy: Copy;
  locale: Locale;
  busy: boolean;
  providerStatus: GuidedOnboardingViewProps["providerStatus"];
  providerStatusPending: boolean;
  batchAnalysisView?: ReactNode;
  batchAnalysisTerminal?: boolean;
  batchAnalysisActive?: boolean;
  batchCanCreate?: boolean;
  batchCreatePending?: boolean;
  onAction: GuidedOnboardingViewProps["onAction"];
  onAnalyze: GuidedOnboardingViewProps["onAnalyze"];
  onCreateBatch?: GuidedOnboardingViewProps["onCreateBatch"];
  onRefreshProviderStatus: GuidedOnboardingViewProps["onRefreshProviderStatus"];
}) {
  const hasBatchAnalysis = batchAnalysisView !== undefined;
  const hasActiveBatch =
    batchAnalysisActive ?? (hasBatchAnalysis && !batchAnalysisTerminal);
  const repositories = selectedRepositories(state);
  const hasRunning = repositories.some(
    (repository) => repository.analysisStatus === "running",
  );
  const allTerminal =
    repositories.length > 0 &&
    repositories.every(
      (repository) =>
        repository.analysisStatus === "complete" ||
        repository.analysisStatus === "unavailable",
    );
  const continueReason = busy
    ? copy.disabledBusy
    : hasActiveBatch || hasRunning
      ? copy.disabledAnalysisRunning
      : null;
  return (
    <section
      aria-labelledby="guided-analysis-heading"
      className="guided-onboarding__step"
    >
      <h2 id="guided-analysis-heading">{copy.analysisHeading}</h2>
      <p>{copy.analysisDescription}</p>
      {hasBatchAnalysis ? (
        <>
          {batchAnalysisView}
          {onCreateBatch && (
            <div className="guided-onboarding__analysis-action">
              <button
                aria-busy={batchCreatePending || undefined}
                aria-describedby={
                  !batchCanCreate || batchCreatePending
                    ? "guided-batch-create-reason"
                    : undefined
                }
                disabled={!batchCanCreate || batchCreatePending}
                onClick={onCreateBatch}
                type="button"
              >
                {copy.createBatch}
              </button>
              {(!batchCanCreate || batchCreatePending) && (
                <p
                  className="guided-onboarding__disabled-reason"
                  id="guided-batch-create-reason"
                  role={batchCreatePending ? "status" : undefined}
                >
                  {batchCreatePending
                    ? copy.batchCreationPending
                    : copy.batchPreflightRequired}
                </p>
              )}
            </div>
          )}
        </>
      ) : (
        <>
          <ProviderStatusPanel
            busy={busy}
            copy={copy}
            locale={locale}
            onRefresh={onRefreshProviderStatus}
            pending={providerStatusPending}
            status={providerStatus}
          />
          {repositories.length > 0 ? (
            <ul>
              {repositories.map((repository) => (
                <RepositoryRow
                  busy={busy}
                  copy={copy}
                  key={repository.metadata.slug}
                  locale={locale}
                  onAction={onAction}
                  onAnalyze={onAnalyze}
                  repository={repository}
                  state={state}
                />
              ))}
            </ul>
          ) : (
            <p>{copy.analysisRequired}</p>
          )}
          {onCreateBatch && repositories.length > 0 && (
            <button
              aria-busy={batchCreatePending || undefined}
              disabled={busy || batchCreatePending || hasActiveBatch}
              onClick={onCreateBatch}
              type="button"
            >
              {batchCreatePending
                ? copy.batchCreationPending
                : copy.createBatch}
            </button>
          )}
        </>
      )}
      <button
        aria-describedby={
          continueReason ? "guided-analysis-continue-reason" : undefined
        }
        disabled={Boolean(continueReason)}
        onClick={() => onAction({ type: "CONTINUE_TO_CONTRIBUTIONS" })}
        className="ux-primary"
        type="button"
      >
        {allTerminal || batchAnalysisTerminal
          ? copy.continueContributions
          : copy.continueManually}
      </button>
      {disabledReason(continueReason, "guided-analysis-continue-reason")}
    </section>
  );
}

function ContributionsStep({
  state,
  copy,
  busy,
  onAction,
  onSuggestContribution,
}: {
  state: GuidedOnboardingState;
  copy: Copy;
  busy: boolean;
  onAction: GuidedOnboardingViewProps["onAction"];
  onSuggestContribution: GuidedOnboardingViewProps["onSuggestContribution"];
}) {
  const repositories = selectedRepositories(state);
  const confirmationsComplete =
    repositories.length > 0 &&
    repositories.every(
      (repository) => repository.confirmedContribution !== null,
    );
  const continueReason = busy
    ? copy.disabledBusy
    : !confirmationsComplete
      ? copy.disabledNeedsConfirmation
      : null;
  return (
    <section
      aria-labelledby="guided-contributions-heading"
      className="guided-onboarding__step"
    >
      <h2 id="guided-contributions-heading">{copy.contributionsHeading}</h2>
      <p>{copy.contributionsDescription}</p>
      <p role="status">
        {copy.confirmed}:{" "}
        {
          repositories.filter(
            (repository) => repository.confirmedContribution !== null,
          ).length
        }
        /{repositories.length}
      </p>
      {repositories.map((repository, index) => (
        <details key={repository.metadata.slug} open={index === 0}>
          <summary>
            {repository.metadata.slug} ·{" "}
            {repository.confirmedContribution
              ? copy.confirmed
              : copy.notConfirmed}
          </summary>
          <ContributionEditor
            busy={busy}
            copy={copy}
            key={repository.metadata.slug}
            onAction={onAction}
            onSuggestContribution={onSuggestContribution}
            repository={repository}
          />
        </details>
      ))}
      <button
        aria-describedby={
          continueReason ? "guided-contributions-continue-reason" : undefined
        }
        disabled={Boolean(continueReason)}
        onClick={() => onAction({ type: "CONTINUE_TO_PROFILE" })}
        className="ux-primary"
        type="button"
      >
        {copy.profileHeading}
      </button>
      {disabledReason(continueReason, "guided-contributions-continue-reason")}
    </section>
  );
}

function ProfileStep({
  state,
  copy,
  busy,
  onAction,
}: {
  state: GuidedOnboardingState;
  copy: Copy;
  busy: boolean;
  onAction: GuidedOnboardingViewProps["onAction"];
}) {
  const profile = state.profile;
  const complete = profileIsComplete(profile);
  const missing = [
    {
      id: "guided-profile-display-name",
      label: copy.displayNameLabel,
      value: profile.displayName,
    },
    ...(["headline", "bio", "greeting"] as const).flatMap((field) =>
      (["zh-TW", "en"] as const).map((language) => ({
        id: `guided-profile-${field}-${language}`,
        label: `${copy[`${field}Label`]} (${copy.profileLocale(language)})`,
        value: localized(profile[field], language),
      })),
    ),
  ].filter((field) => !field.value.trim());
  const confirmationReason = busy
    ? copy.disabledBusy
    : !complete
      ? copy.profileRequired
      : null;

  function setProfile(next: GuidedProfile) {
    onAction({ type: "SET_PROFILE", profile: next });
  }

  return (
    <section
      aria-labelledby="guided-profile-heading"
      className="guided-onboarding__step"
    >
      <h2 id="guided-profile-heading">{copy.profileHeading}</h2>
      <p>{copy.profileDescription}</p>
      {missing.length > 0 && (
        <aside className="ux-missing-fields" aria-label={copy.profileRequired}>
          <p>{copy.profileRequired}</p>
          <ul>
            {missing.map((field) => (
              <li key={field.id}>
                <a
                  href={`#${field.id}`}
                  onClick={(event) => {
                    event.preventDefault();
                    document.getElementById(field.id)?.focus();
                  }}
                >
                  {field.label}
                </a>
              </li>
            ))}
          </ul>
        </aside>
      )}
      <label htmlFor="guided-profile-display-name">
        {copy.displayNameLabel}
        <input
          disabled={busy}
          id="guided-profile-display-name"
          required
          onChange={(event) =>
            setProfile(profileWithDisplayName(profile, event.target.value))
          }
          value={profile.displayName}
        />
      </label>
      <fieldset disabled={busy}>
        <legend>{copy.headlineLabel}</legend>
        {(["zh-TW", "en"] as const).map((profileLocale) => (
          <label
            htmlFor={`guided-profile-headline-${profileLocale}`}
            key={profileLocale}
          >
            {copy.profileLocale(profileLocale)}
            <input
              id={`guided-profile-headline-${profileLocale}`}
              required
              onChange={(event) =>
                setProfile(
                  profileWithField(
                    profile,
                    "headline",
                    profileLocale,
                    event.target.value,
                  ),
                )
              }
              value={localized(profile.headline, profileLocale)}
            />
          </label>
        ))}
      </fieldset>
      <fieldset disabled={busy}>
        <legend>{copy.bioLabel}</legend>
        {(["zh-TW", "en"] as const).map((profileLocale) => (
          <label
            htmlFor={`guided-profile-bio-${profileLocale}`}
            key={profileLocale}
          >
            {copy.profileLocale(profileLocale)}
            <textarea
              id={`guided-profile-bio-${profileLocale}`}
              required
              onChange={(event) =>
                setProfile(
                  profileWithField(
                    profile,
                    "bio",
                    profileLocale,
                    event.target.value,
                  ),
                )
              }
              rows={4}
              value={localized(profile.bio, profileLocale)}
            />
          </label>
        ))}
      </fieldset>
      <fieldset disabled={busy}>
        <legend>{copy.greetingLabel}</legend>
        {(["zh-TW", "en"] as const).map((profileLocale) => (
          <label
            htmlFor={`guided-profile-greeting-${profileLocale}`}
            key={profileLocale}
          >
            {copy.profileLocale(profileLocale)}
            <textarea
              id={`guided-profile-greeting-${profileLocale}`}
              required
              onChange={(event) =>
                setProfile(
                  profileWithField(
                    profile,
                    "greeting",
                    profileLocale,
                    event.target.value,
                  ),
                )
              }
              rows={3}
              value={localized(profile.greeting, profileLocale)}
            />
          </label>
        ))}
      </fieldset>
      <button
        aria-describedby={
          confirmationReason ? "guided-profile-confirm-reason" : undefined
        }
        disabled={Boolean(confirmationReason)}
        onClick={() => onAction({ type: "CONFIRM_PROFILE" })}
        className="ux-primary"
        type="button"
      >
        {copy.confirmProfile}
      </button>
      {disabledReason(confirmationReason, "guided-profile-confirm-reason")}
    </section>
  );
}

function ReviewStep({
  state,
  copy,
  busy,
  onCreateDraft,
  onAction,
}: {
  state: GuidedOnboardingState;
  copy: Copy;
  busy: boolean;
  onCreateDraft: GuidedOnboardingViewProps["onCreateDraft"];
  onAction: GuidedOnboardingViewProps["onAction"];
}) {
  const repositories = selectedRepositories(state);
  return (
    <section
      aria-labelledby="guided-review-heading"
      className="guided-onboarding__step"
    >
      <h2 id="guided-review-heading">{copy.reviewHeading}</h2>
      <p>{copy.reviewDescription}</p>
      <section aria-labelledby="guided-review-profile-heading">
        <h3 id="guided-review-profile-heading">{copy.profileHeading}</h3>
        <dl>
          <dt>{copy.displayNameLabel}</dt>
          <dd>{state.profile.displayName}</dd>
          {(["zh-TW", "en"] as const).map((profileLocale) => (
            <div key={profileLocale}>
              <dt>
                {copy.headlineLabel} ({copy.profileLocale(profileLocale)})
              </dt>
              <dd>{localized(state.profile.headline, profileLocale)}</dd>
              <dt>
                {copy.bioLabel} ({copy.profileLocale(profileLocale)})
              </dt>
              <dd>{localized(state.profile.bio, profileLocale)}</dd>
              <dt>
                {copy.greetingLabel} ({copy.profileLocale(profileLocale)})
              </dt>
              <dd>{localized(state.profile.greeting, profileLocale)}</dd>
            </div>
          ))}
        </dl>
      </section>
      <ul>
        {repositories.map((repository) => (
          <li key={repository.metadata.slug}>
            <strong>{repository.metadata.slug}</strong>
            {repository.confirmedContribution ? (
              <>
                <span>{copy.confirmed}</span>
                {(["zh-TW", "en"] as const).map((language) => (
                  <section
                    className="ux-review-item"
                    lang={language}
                    key={language}
                  >
                    <h4>{copy.profileLocale(language)}</h4>
                    <dl>
                      <dt>{copy.roleLabel}</dt>
                      <dd>
                        {localized(
                          repository.confirmedContribution!.role,
                          language,
                        )}
                      </dd>
                      <dt>{copy.summaryLabel}</dt>
                      <dd>
                        {localized(
                          repository.confirmedContribution!.summary,
                          language,
                        )}
                      </dd>
                    </dl>
                    <ul>
                      {repository.confirmedContribution!.claims.map((claim) => (
                        <li key={claim.id}>
                          {localized(claim.statement, language)}
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </>
            ) : (
              <span>{copy.notConfirmed}</span>
            )}
          </li>
        ))}
      </ul>
      <button
        disabled={busy}
        onClick={() => onAction({ type: "GO_BACK" })}
        type="button"
      >
        {copy.back} · {copy.profileHeading}
      </button>
      <button
        className="ux-primary"
        disabled={busy}
        onClick={onCreateDraft}
        type="button"
      >
        {copy.createDraft}
      </button>
    </section>
  );
}

function DraftStep({
  state,
  copy,
  locale,
  busy,
  onAction,
  onCopyDraft,
  onDownloadDraft,
}: {
  state: GuidedOnboardingState;
  copy: Copy;
  locale: Locale;
  busy: boolean;
  onAction: GuidedOnboardingViewProps["onAction"];
  onCopyDraft: GuidedOnboardingViewProps["onCopyDraft"];
  onDownloadDraft: GuidedOnboardingViewProps["onDownloadDraft"];
}) {
  const [copyStatus, setCopyStatus] = useState<
    "idle" | "pending" | "done" | "failed"
  >("idle");
  const chinese = locale === "zh-TW";
  return (
    <section
      aria-labelledby="guided-draft-heading"
      className="guided-onboarding__step"
    >
      <h2 id="guided-draft-heading">{copy.draftHeading}</h2>
      <p>{copy.draftDescription}</p>
      <p>
        {chinese
          ? "設定草稿已完成，尚未發布。你可以下載保存，或進入進階模式驗證與預覽。"
          : "Your configuration draft is complete but not published. Download it, or open advanced mode to validate and preview."}
      </p>
      <p role="status">{copy.draftReady}</p>
      <div className="guided-onboarding__draft-actions">
        <button
          disabled={busy || copyStatus === "pending"}
          onClick={async () => {
            setCopyStatus("pending");
            try {
              await onCopyDraft();
              setCopyStatus("done");
            } catch {
              setCopyStatus("failed");
            }
          }}
          type="button"
        >
          {copyStatus === "done"
            ? chinese
              ? "已複製"
              : "Copied"
            : copy.copyDraft}
        </button>
        <button disabled={busy} onClick={onDownloadDraft} type="button">
          {copy.downloadDraft}
        </button>
      </div>
      {copyStatus === "done" && (
        <p role="status">
          {chinese
            ? "設定草稿已複製到剪貼簿。"
            : "Configuration copied to clipboard."}
        </p>
      )}
      {copyStatus === "failed" && (
        <p role="alert">
          {chinese
            ? "無法使用剪貼簿，請改用下載 YAML。"
            : "Clipboard unavailable. Download the YAML instead."}
        </p>
      )}
      {state.rawYamlHasUnmappedChanges && (
        <p role="alert">{copy.rawYamlWarning}</p>
      )}
      <button
        disabled={busy}
        onClick={() => onAction({ type: "SET_MODE", mode: "advanced" })}
        type="button"
      >
        {copy.advancedMode}
      </button>
      <button
        disabled={busy}
        onClick={() => onAction({ type: "SET_MODE", mode: "guided" })}
        type="button"
      >
        {copy.guidedMode}
      </button>
    </section>
  );
}

export function GuidedOnboardingView({
  locale,
  state,
  busy,
  errorCode,
  batchAnalysisView,
  batchAnalysisTerminal,
  batchAnalysisActive,
  batchCanCreate,
  batchCreatePending,
  modelSetupView,
  providerStatus,
  providerStatusPending,
  onAction,
  onDiscover,
  onResolve,
  onAnalyze,
  onCreateBatch,
  onRefreshProviderStatus,
  onSuggestContribution,
  onCreateDraft,
  onCopyDraft,
  onDownloadDraft,
  workspaceStatus,
}: GuidedOnboardingViewProps & { workspaceStatus?: AdminWorkspaceStatus }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const previousStep = useRef(state.step);
  useEffect(() => {
    if (previousStep.current !== state.step) {
      headingRef.current?.focus();
      previousStep.current = state.step;
    }
  }, [state.step]);
  const copy = COPY[locale];
  const error = errorCode ? guidedErrorMessage(locale, errorCode) : "";
  const navigationBatchActive =
    batchAnalysisActive ??
    (batchAnalysisView !== undefined && !batchAnalysisTerminal);

  return (
    <section
      aria-busy={busy}
      aria-labelledby="guided-onboarding-heading"
      className="guided-onboarding"
      data-mode={state.mode}
      data-step={state.step}
      lang={locale}
    >
      <AdminStatusCards
        locale={locale}
        state={state}
        status={workspaceStatus ?? EMPTY_WORKSPACE_STATUS}
      />
      <header className="guided-onboarding__header">
        <p className="guided-onboarding__eyebrow">{copy.product}</p>
        <h2 id="guided-onboarding-heading" ref={headingRef} tabIndex={-1}>
          {copy.title} · {copy.steps[state.step]}
        </h2>
        {state.mode === "guided" && (
          <OnboardingStepper copy={copy} locale={locale} state={state} />
        )}
        {state.step !== "intro" && (
          <div className="guided-onboarding__navigation-actions">
            <button
              aria-describedby={
                navigationBatchActive
                  ? "guided-navigation-batch-reason"
                  : undefined
              }
              disabled={busy || navigationBatchActive}
              onClick={() => onAction({ type: "GO_BACK" })}
              type="button"
            >
              {copy.back}
            </button>
            {state.step !== "repositories" && state.step !== "analysis" && (
              <button
                aria-describedby={
                  navigationBatchActive
                    ? "guided-navigation-batch-reason"
                    : undefined
                }
                disabled={busy || navigationBatchActive}
                onClick={() => onAction({ type: "EDIT_SELECTION" })}
                type="button"
              >
                {copy.editSelection}
              </button>
            )}
            <button
              aria-describedby={
                navigationBatchActive
                  ? "guided-navigation-batch-reason"
                  : undefined
              }
              disabled={busy || navigationBatchActive}
              onClick={() => {
                if (window.confirm(copy.startOverConfirm)) {
                  onAction({ type: "RESET" });
                }
              }}
              type="button"
            >
              {copy.startOver}
            </button>
            {navigationBatchActive && (
              <p
                className="guided-onboarding__disabled-reason"
                id="guided-navigation-batch-reason"
              >
                {copy.navigationBlockedByBatch}
              </p>
            )}
          </div>
        )}
      </header>

      {busy && (
        <p className="guided-onboarding__busy" role="status">
          {copy.busy}
        </p>
      )}
      {error && (
        <p className="guided-onboarding__error" role="alert">
          <strong>{copy.errorHeading}</strong> {error}
        </p>
      )}
      {state.rawYamlHasUnmappedChanges && (
        <p className="guided-onboarding__raw-warning" role="alert">
          {copy.rawYamlWarning}
        </p>
      )}

      {state.mode === "advanced" ? (
        <section
          aria-labelledby="guided-advanced-heading"
          className="guided-onboarding__advanced"
        >
          <h2 id="guided-advanced-heading">{copy.advancedMode}</h2>
          <p>{copy.advancedDescription}</p>
          <button
            disabled={busy}
            onClick={() => onAction({ type: "SET_MODE", mode: "guided" })}
            type="button"
          >
            {copy.guidedMode}
          </button>
        </section>
      ) : (
        <>
          {state.step === "intro" && (
            <IntroStep
              busy={busy}
              copy={copy}
              onAction={onAction}
              state={state}
            />
          )}
          {state.step === "models" && (
            <ModelsStep
              busy={busy}
              copy={copy}
              modelSetupView={modelSetupView}
              onAction={onAction}
              state={state}
            />
          )}
          {state.step === "repositories" && (
            <RepositoriesStep
              busy={busy}
              copy={copy}
              locale={locale}
              onAction={onAction}
              onDiscover={onDiscover}
              onResolve={onResolve}
              state={state}
            />
          )}
          {state.step === "analysis" && (
            <AnalysisStep
              busy={busy}
              batchAnalysisActive={batchAnalysisActive}
              batchAnalysisTerminal={batchAnalysisTerminal}
              batchAnalysisView={batchAnalysisView}
              batchCanCreate={batchCanCreate}
              batchCreatePending={batchCreatePending}
              copy={copy}
              locale={locale}
              onAction={onAction}
              onAnalyze={onAnalyze}
              onCreateBatch={onCreateBatch}
              onRefreshProviderStatus={onRefreshProviderStatus}
              providerStatus={providerStatus}
              providerStatusPending={providerStatusPending}
              state={state}
            />
          )}
          {state.step === "contributions" && (
            <ContributionsStep
              busy={busy}
              copy={copy}
              onAction={onAction}
              onSuggestContribution={onSuggestContribution}
              state={state}
            />
          )}
          {state.step === "profile" && (
            <ProfileStep
              busy={busy}
              copy={copy}
              onAction={onAction}
              state={state}
            />
          )}
          {state.step === "review" && (
            <ReviewStep
              busy={busy}
              copy={copy}
              onAction={onAction}
              onCreateDraft={onCreateDraft}
              state={state}
            />
          )}
          {state.step === "draft" && (
            <DraftStep
              busy={busy}
              copy={copy}
              locale={locale}
              onAction={onAction}
              onCopyDraft={onCopyDraft}
              onDownloadDraft={onDownloadDraft}
              state={state}
            />
          )}
        </>
      )}
    </section>
  );
}

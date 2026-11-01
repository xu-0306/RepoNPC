import { useEffect, useId, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, ReactNode } from "react";

import { Button, Dialog, DialogTrigger, Popover } from "react-aria-components";

import "./guidedAnalysis.css";
import "../../p4-w1.css";
import "../../p4-w2.css";

import { messages, type Locale } from "../../i18n/messages";
import {
  formatRepositorySize,
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
import { ConfirmButton } from "./ConfirmDialog";
import { CheckboxField } from "./CheckboxField";
import type { ClaimKind } from "./ClaimEditor";
import { DraftValidation } from "./AdminWorkspace";

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
  startAiHelp: string;
  startManualHelp: string;
  modelsHeading: string;
  modelsDescription: string;
  confirmModels: string;
  returnToPreparation: string;
  returnWithoutSetup: string;
  modelReturnHelp: string;
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
  sizeLabel: string;
  emptyRepositoryHint: string;
  githubLabel: string;
  optionsLegend: string;
  includeLabel: string;
  excludeLabel: string;
  noRepositories: string;
  confirmSelection: string;
  selectionRequired: string;
  selectionLocked: string;
  analysisHeading: string;
  analysisResultsHeading: string;
  analysisDescription: string;
  providerHeading: string;
  chatModel: string;
  searchModel: string;
  modelTested: string;
  modelsNotSelected: string;
  modelReasons: Record<string, string>;
  providerUnknown: string;
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
  startOverTitle: string;
  startOverDescription: string;
  navigationBlockedByBatch: string;
  factsHeading: string;
  inferenceHeading: string;
  inferenceDescription: string;
  inferencePrivacyLabel: string;
  inferencePrivacy: string;
  noInferences: string;
  p4Help: string;
  p4Required: string;
  p4Actions: string;
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
  manualProposalHeading: string;
  manualProposalDescription: string;
  confirmManualSelection: string;
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
  editConfirmed: string;
  restorePrevious: string;
  reject: string;
  proposalRequired: string;
  assertionConfirmed: string;
  confirmationRequired: string;
  profileHeading: string;
  profileDescription: string;
  displayNameLabel: string;
  githubLoginLabel: string;
  githubLoginHelp: string;
  aliasesLabel: string;
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
    startAiHelp:
      "先設定、測試並確認選用回答／分析模型與資料查找模型，再選專案讓 AI 分析。進入設定不會自動下載或呼叫模型，也不會發布作品集。",
    startManualHelp:
      "不需模型即可手動填寫、確認、預覽、儲存及備份草稿。準備 NPC 與即時聊天仍需模型；建立草稿不等於公開分享。",
    modelsHeading: "設定 AI 模型",
    modelsDescription: "設定並測試兩種模型，或先手動填寫、預覽及儲存內容。",
    confirmModels: "完成模型設定並選擇專案",
    returnToPreparation: "完成設定並返回準備 NPC",
    returnWithoutSetup: "返回準備 NPC",
    modelReturnHelp: "內容草稿已保留。完成模型設定後可返回準備 NPC。",
    modelsRequired:
      "請先測試回答模型與資料查找模型，再於選擇區按「確認用於分析」。",
    advanced: "編輯 raw YAML",
    advancedDescription: "熟悉設定格式時，可直接編輯 reponpc.yml。",
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
    repositoryHelp: "格式為 owner/name。也可用 https://github.com/owner/name。",
    refLabel: "版本（分支、標籤或commit SHA）",
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
    sizeLabel: "大小",
    emptyRepositoryHint: messages["zh-TW"].emptyRepositoryHint,
    githubLabel: "GitHub",
    optionsLegend: "專案選項",
    includeLabel: "包含路徑（逗號分隔）",
    excludeLabel: "排除路徑（逗號分隔）",
    noRepositories: "目前沒有專案資訊。請先探索或手動加入。",
    confirmSelection: "確認選取並繼續分析",
    selectionRequired: "至少勾選一個專案後才能繼續。",
    selectionLocked: "選取已確認；你可以在後續步驟返回編輯。",
    analysisHeading: "分析已選專案",
    analysisResultsHeading: "先看專案內容，再描述你的貢獻",
    analysisDescription:
      "分析你已確認的公開專案；完成後檢視專案中可確認的資訊與 AI 推論，再填寫自己的貢獻。",
    providerHeading: "分析模型",
    chatModel: "分析與回答模型",
    searchModel: "資料查找模型",
    modelTested: "已測試",
    modelsNotSelected: "尚未選擇",
    modelReasons: {
      CHAT_MODEL_NOT_SELECTED: "尚未選擇回答模型",
      SEARCH_MODEL_NOT_SELECTED: "尚未選擇資料查找模型",
      CHAT_MODEL_NOT_READY: "回答模型尚未通過測試",
      SEARCH_MODEL_NOT_READY: "資料查找模型尚未通過測試",
      CHAT_MODEL_REVISION_STALE: "回答模型設定已變更，請重新測試及選用",
      SEARCH_MODEL_REVISION_STALE: "資料查找模型設定已變更，請重新測試及選用",
      MODEL_CONNECTION_UNAVAILABLE: "模型服務目前無法使用",
    },
    providerUnknown: "無法取得分析模型狀態",
    refreshProvider: "檢查模型狀態",
    checkingProvider: "正在檢查分析模型…",
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
    continueContributions: "描述我的貢獻",
    continueManually: "略過分析，手動填寫貢獻",
    back: "返回",
    editSelection: "編輯專案選擇",
    startOver: "重新開始",
    startOverTitle: "重新開始？",
    startOverDescription: "這會清除目前尚未儲存的引導內容。",
    navigationBlockedByBatch:
      "目前批次分析仍在執行。請先在下方取消批次，等待狀態更新後再返回、編輯選擇或重新開始。",
    factsHeading: "專案中可確認的資訊",
    inferenceHeading: "專案重點",
    inferenceDescription: "AI 整理，僅供你參考",
    inferencePrivacyLabel: "隱私說明",
    inferencePrivacy: "不會公開，也不會自動寫進作品集。",
    noInferences: "沒有 AI 推論。",
    p4Help: "填寫說明",
    p4Required: "必填",
    p4Actions: "其他操作",
    contributionsHeading: "描述你的貢獻",
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
    manualProposalHeading: "手動填寫的貢獻",
    manualProposalDescription:
      "編輯雙語內容後，請明確確認。修改已確認內容後需要重新確認。",
    confirmManualSelection: "確認專案並填寫貢獻",
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
    editConfirmed: "編輯已確認內容",
    restorePrevious: "還原上一個已確認版本",
    reject: "拒絕並重新填寫",
    proposalRequired: "請按「產生可編輯建議」，或按「手動輸入貢獻」自己填寫。",
    assertionConfirmed: "此專案的貢獻已由你確認。",
    confirmationRequired:
      "每個已選專案都需要確認貢獻後才能繼續。拒絕建議後，請重新填寫並確認。",
    profileHeading: "填寫基本資料",
    profileDescription:
      "這些公開文字會成為完整設定草稿的一部分。請提供中英文內容。不要讓模型替你猜測個人資料。",
    displayNameLabel: "顯示名稱",
    githubLoginLabel: "你的 GitHub 帳號",
    githubLoginHelp:
      "請確認這是你的帳號。只會比對 GitHub 可見且連結到此帳號的提交。",
    aliasesLabel: "其他稱呼（選填，每行一個）",
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
    createDraft: "完成內容",
    draftHeading: "草稿已準備好",
    draftDescription:
      "草稿保存在你的主機，套用後才會更新 NPC。GitHub 只需放上卡片。",
    copyDraft: "複製 YAML",
    downloadDraft: "備份設定（YAML）",
    draftReady: "內容已完成，可前往「預覽與分享」準備 NPC。",
    advancedMode: "進階 raw YAML 模式",
    guidedMode: "返回引導模式",
    rawYamlWarning: "raw YAML 有無法對應回引導欄位的變更。請在進階模式中處理。",
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
      "請完成繁體中文與英文的角色和摘要後才能接受。",
    disabledNeedsConfirmation:
      "請確認每個專案的貢獻；拒絕建議後仍需重新填寫並確認。",
  },
  en: {
    product: "RepoNPC",
    title: "Guided portfolio setup",
    introTitle: "Let RepoNPC understand your work",
    introBody:
      "Choose public GitHub projects, review information you can verify from them, and confirm your own contribution. The result is a complete bilingual configuration draft that you can check, preview, copy, or download.",
    outcome: "You will get",
    outcomeItems: [
      "Project information you can verify, kept separate from AI inferences",
      "Your confirmed contribution appears only after you accept or edit it",
      "A YAML configuration draft that works without a GitHub writeback token",
    ],
    start: "Start guided setup",
    startAi: "Set up AI and start",
    startManual: "Build manually first",
    startAiHelp:
      "Before choosing projects for AI analysis, set up, test and explicitly select both answer/analysis and content finder models. Entering setup does not download, call a model or publish your portfolio.",
    startManualHelp:
      "You can write, confirm, preview, save or back up a draft manually without a model. Preparing the NPC and live chat still need models later. Creating a draft does not publish it.",
    modelsHeading: "Set up AI models",
    modelsDescription:
      "Set up and test both model roles, or write, preview and save your content manually.",
    confirmModels: "Finish model setup and choose projects",
    returnToPreparation: "Finish setup and return to prepare NPC",
    returnWithoutSetup: "Return to prepare NPC",
    modelReturnHelp:
      "Your content draft is kept. Return to prepare the NPC after model setup.",
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
      "RepoNPC reads only public project information. It downloads no code and makes no model calls before you confirm the checkboxes.",
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
    sizeLabel: "Size",
    emptyRepositoryHint: messages.en.emptyRepositoryHint,
    githubLabel: "GitHub",
    optionsLegend: "Project options",
    includeLabel: "Include paths (comma separated)",
    excludeLabel: "Exclude paths (comma separated)",
    noRepositories:
      "No project information yet. Discover an account or add one manually.",
    confirmSelection: "Confirm selection and continue to analysis",
    selectionRequired: "Select at least one project before continuing.",
    selectionLocked:
      "You confirmed the selection. You can return and edit it from later steps.",
    analysisHeading: "Analyze selected projects",
    analysisResultsHeading:
      "Review the projects, then describe your contribution",
    analysisDescription:
      "Analyze confirmed public projects, then review information you can verify from each project and AI inferences before describing your contribution.",
    providerHeading: "Analysis models",
    chatModel: "Analysis and chat",
    searchModel: "Content finder",
    modelTested: "Tested",
    modelsNotSelected: "Not selected",
    modelReasons: {
      CHAT_MODEL_NOT_SELECTED: "Chat model not selected",
      SEARCH_MODEL_NOT_SELECTED: "Content finder not selected",
      CHAT_MODEL_NOT_READY: "Chat model has not passed testing",
      SEARCH_MODEL_NOT_READY: "Content finder has not passed testing",
      CHAT_MODEL_REVISION_STALE:
        "Chat model settings changed; retest and select again",
      SEARCH_MODEL_REVISION_STALE:
        "Content finder settings changed; retest and select again",
      MODEL_CONNECTION_UNAVAILABLE: "Model service unavailable",
    },
    providerUnknown: "Analysis model status unavailable",
    refreshProvider: "Check model status",
    checkingProvider: "Checking analysis models…",
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
    continueContributions: "Describe my contribution",
    continueManually: "Skip analysis and enter contribution manually",
    back: "Back",
    editSelection: "Edit project selection",
    startOver: "Start over",
    startOverTitle: "Start over?",
    startOverDescription: "This clears the unsaved guided setup.",
    navigationBlockedByBatch:
      "A batch analysis is still running. Cancel it below and wait for the status update before going back, editing the selection, or starting over.",
    factsHeading: "Project information you can verify",
    inferenceHeading: "Highlights",
    inferenceDescription: "AI summary, for your reference",
    inferencePrivacyLabel: "Privacy details",
    inferencePrivacy:
      "Never public, never added to your portfolio automatically.",
    noInferences: "No AI inferences.",
    p4Help: "Field guidance",
    p4Required: "Required",
    p4Actions: "Other actions",
    contributionsHeading: "Describe your contribution",
    contributionsDescription:
      "Describe your work and boundaries in your own words. AI suggestions are drafts that require explicit confirmation or editing.",
    ownerStatementLabel: "Your contribution description",
    ownerStatementHelp:
      "The original text stays beside every suggestion. The project content cannot establish your identity or role.",
    suggest: "Generate editable suggestion",
    suggesting: "Generating suggestion…",
    manualEntry: "Enter contribution manually",
    manualEntryHelp:
      "When the model is unavailable, fill in the bilingual role, summary, and contribution descriptions yourself.",
    statementRequired:
      "Enter your contribution description before requesting a suggestion.",
    proposalHeading: "AI suggestion (unconfirmed)",
    manualProposalHeading: "Manually entered contribution",
    manualProposalDescription:
      "Edit both languages, then explicitly confirm. Changes to confirmed content require confirmation again.",
    confirmManualSelection: "Confirm projects and enter contributions",
    proposalDescription:
      "You can edit these fields. Only explicit confirmation makes this your confirmed contribution.",
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
    editConfirmed: "Edit confirmed content",
    restorePrevious: "Restore previous confirmed version",
    reject: "Reject and rewrite",
    proposalRequired:
      "Select Generate editable suggestion, or Enter contribution manually to write it yourself.",
    assertionConfirmed: "You confirmed this project's contribution.",
    confirmationRequired:
      "Confirm a contribution for every selected project. After rejecting a suggestion, rewrite and confirm it before continuing.",
    profileHeading: "Add your basic profile",
    profileDescription:
      "These public fields become part of the complete YAML draft. Supply both languages. Please do not ask a model to guess personal profile details.",
    displayNameLabel: "Display name",
    githubLoginLabel: "Your GitHub login",
    githubLoginHelp:
      "Confirm this is your account. RepoNPC matches only visible commits linked to it.",
    aliasesLabel: "Other names (optional, one per line)",
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
      "Confirm which text enters the configuration draft. Unconfirmed AI inferences do not enter it.",
    confirmed: "Confirmed",
    notConfirmed: "Not confirmed",
    createDraft: "Finish content",
    draftHeading: "Draft ready",
    draftDescription:
      "The draft stays on your host. It updates your NPC only after you apply it. GitHub only needs the card.",
    copyDraft: "Copy YAML",
    downloadDraft: "Back up settings (YAML)",
    draftReady: "Content is ready. Open Preview & share to prepare the NPC.",
    advancedMode: "Advanced raw YAML mode",
    guidedMode: "Return to guided mode",
    rawYamlWarning:
      "Raw YAML has changes that cannot map back to guided fields; resolve them in advanced mode.",
    busy: "Working. Some actions may be temporarily disabled.",
    errorHeading: "Guided setup error",
    disabledBusy: "An operation is in progress; wait a moment.",
    disabledNeedsAccount:
      "Enter a GitHub username or URL before discovering projects.",
    disabledSelectionConfirmed:
      "You confirmed the selection and cannot edit it at this step.",
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

// eslint-disable-next-line react-refresh/only-export-components -- the shell reuses the guided labels
export const GUIDED_PROGRESS_COPY = {
  "zh-TW": { progress: COPY["zh-TW"].progress, steps: COPY["zh-TW"].steps },
  en: { progress: COPY.en.progress, steps: COPY.en.steps },
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
    profile.githubLogin,
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

function sourceLocation(fact: RepositoryFact): string {
  return fact.start_line === null
    ? fact.path
    : `${fact.path}:${fact.start_line}${
        fact.end_line && fact.end_line !== fact.start_line
          ? `-${fact.end_line}`
          : ""
      }`;
}

export function AnalysisHighlight({
  inference,
  locale,
  facts,
}: {
  inference: ModelInference;
  locale: Locale;
  facts: RepositoryFact[];
}) {
  const [expanded, setExpanded] = useState(false);
  const bodyId = useId();
  const firstSource = facts[0];
  const missingSources =
    facts.length < new Set(inference.supporting_evidence_ids).size;
  return (
    <li
      className="guided-analysis__highlight"
      data-evidence-class="MODEL_INFERENCE"
    >
      <div className="guided-analysis__row">
        <button
          className="guided-analysis__toggle"
          aria-expanded={expanded}
          aria-controls={bodyId}
          onClick={() => setExpanded(!expanded)}
          type="button"
        >
          {localized(inference.title, locale)}
          {expanded && facts.length > 1 && (
            <span className="guided-analysis__more" aria-hidden="true">
              +{facts.length - 1}
            </span>
          )}
        </button>
        {firstSource && !expanded && (
          <div className="guided-analysis__source-chip">
            <a
              href={firstSource.url}
              target="_blank"
              rel="noopener noreferrer"
              title={sourceLocation(firstSource)}
            >
              {firstSource.path.split("/").pop()}{" "}
              <span aria-hidden="true">↗</span>
              <span className="visually-hidden">
                {locale === "zh-TW"
                  ? "（在新分頁開啟 GitHub）"
                  : " (opens GitHub in a new tab)"}
              </span>
            </a>
            {facts.length > 1 && (
              <span className="guided-analysis__more">+{facts.length - 1}</span>
            )}
          </div>
        )}
      </div>
      <div className="guided-analysis__body" id={bodyId} hidden={!expanded}>
        <p>{localized(inference.statement, locale)}</p>
        <ul>
          {facts.map((fact) => (
            <li key={fact.evidence_id} data-evidence-class="REPOSITORY_FACT">
              <a href={fact.url} target="_blank" rel="noopener noreferrer">
                {sourceLocation(fact)} <span aria-hidden="true">↗</span>
                <span className="visually-hidden">
                  {locale === "zh-TW"
                    ? "（在新分頁開啟 GitHub）"
                    : " (opens GitHub in a new tab)"}
                </span>
              </a>
            </li>
          ))}
        </ul>
        {missingSources && (
          <p className="guided-analysis__missing">
            {locale === "zh-TW"
              ? "部分出處不在這次結果中，請勿視為已核對。"
              : "Some sources are not in this result; do not treat them as verified."}
          </p>
        )}
      </div>
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
    <>
      <div className="guided-analysis__repo">
        <h3>{repository.metadata.slug}</h3>
        {repository.metadata.primary_language && (
          <span className="guided-analysis__chip">
            {repository.metadata.primary_language}
          </span>
        )}
        <code className="guided-analysis__chip">
          {analysis.repository.commit_sha.slice(0, 7)}
        </code>
      </div>
      <section
        className="guided-analysis__highlights"
        aria-labelledby={`guided-inferences-${repository.metadata.slug}`}
      >
        <h4 id={`guided-inferences-${repository.metadata.slug}`}>
          {copy.inferenceHeading}
        </h4>
        <div className="guided-analysis__note">
          <p>{copy.inferenceDescription}</p>
          <DialogTrigger>
            <Button
              className="guided-analysis__info"
              aria-label={copy.inferencePrivacyLabel}
            >
              ⓘ
            </Button>
            <Popover
              className="guided-analysis__popover"
              placement="bottom start"
            >
              <Dialog aria-label={copy.inferencePrivacyLabel} lang={locale}>
                <p>{copy.inferencePrivacy}</p>
              </Dialog>
            </Popover>
          </DialogTrigger>
        </div>
        {analysis.inferences.length > 0 ? (
          <ul className="guided-analysis__list">
            {analysis.inferences.map((inference, index) => (
              <AnalysisHighlight
                inference={inference}
                key={`${repository.metadata.slug}-inference-${index}`}
                locale={locale}
                facts={[...new Set(inference.supporting_evidence_ids)].flatMap(
                  (id) =>
                    analysis.facts.filter((fact) => fact.evidence_id === id),
                )}
              />
            ))}
          </ul>
        ) : (
          <p>{copy.noInferences}</p>
        )}
      </section>
    </>
  );
}

function BatchAnalysisResults({
  repositories,
  locale,
  copy,
}: {
  repositories: GuidedRepository[];
  locale: Locale;
  copy: Copy;
}) {
  const completed = repositories.filter(analysisReady);
  if (completed.length === 0) return null;
  return (
    <section
      aria-label={copy.factsHeading}
      className="guided-analysis__results"
    >
      <ul>
        {completed.map((repository) => (
          <li
            className="guided-analysis__repository"
            data-analysis-result={repository.metadata.slug}
            key={repository.metadata.slug}
          >
            <EvidenceGroups
              copy={copy}
              locale={locale}
              repository={repository}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}

function RepositoryRow({
  repository,
  state,
  copy,
  busy,
  onAction,
}: {
  repository: GuidedRepository;
  state: GuidedOnboardingState;
  copy: Copy;
  busy: boolean;
  onAction: GuidedOnboardingViewProps["onAction"];
}) {
  const slugId = repository.metadata.slug.replace(/[^a-zA-Z0-9_-]/g, "-");
  const selectionLocked = state.selectionConfirmed;
  const size = formatRepositorySize(repository.metadata.size_kb);

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
          aria-describedby={
            repository.metadata.size_kb === 0
              ? `guided-empty-${slugId}`
              : undefined
          }
          disabled={selectionLocked || busy || repository.metadata.is_archived}
          id={`guided-repository-${slugId}`}
          onChange={() => {
            if (repository.metadata.is_archived) return;
            onAction({
              type: "TOGGLE_REPOSITORY",
              slug: repository.metadata.slug,
            });
          }}
        >
          <strong>{repository.metadata.name}</strong>
          <span className="visually-hidden">{repository.metadata.slug}</span>
        </CheckboxField>
        {repository.metadata.primary_language && (
          <span className="px-badge">
            {repository.metadata.primary_language}
          </span>
        )}
        {size && <span className="px-badge">{size}</span>}
      </div>
      {repository.metadata.size_kb === 0 && (
        <p className="px-meta" id={`guided-empty-${slugId}`}>
          {copy.emptyRepositoryHint}
        </p>
      )}
      <details className="p4-w1-repository__details px-info">
        <summary
          aria-label={`${copy.optionsLegend}: ${repository.metadata.name}`}
        >
          ⓘ
        </summary>
        <code>{repository.metadata.slug}</code>
        <span className="px-meta">
          {repository.selected ? copy.selected : ""}
          {repository.metadata.is_archived ? ` · ${copy.archived}` : ""}
          {repository.metadata.is_fork ? ` · ${copy.fork}` : ""}
        </span>
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
          {size && (
            <>
              <dt>{copy.sizeLabel}</dt>
              <dd>{size}</dd>
            </>
          )}
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
      </details>
    </li>
  );
}

function ContributionEditor({
  locale,
  repository,
  copy,
  busy,
  onAction,
  onSuggestContribution,
}: {
  locale: Locale;
  repository: GuidedRepository;
  copy: Copy;
  busy: boolean;
  onAction: GuidedOnboardingViewProps["onAction"];
  onSuggestContribution: GuidedOnboardingViewProps["onSuggestContribution"];
}) {
  const [newClaimKind, setNewClaimKind] = useState<ClaimKind>("responsibility");
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
  const proposalLocked = repository.confirmedContribution !== null;
  const proposalMissingBilingual = proposal
    ? [
        proposal.role["zh-TW"],
        proposal.role.en,
        proposal.summary["zh-TW"],
        proposal.summary.en,
        ...proposal.claims.flatMap((claim) => [
          claim.statement["zh-TW"],
          claim.statement.en,
        ]),
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
      className="guided-onboarding__contribution p4-w2__contribution"
      data-slug={repository.metadata.slug}
    >
      <h3 className="visually-hidden" id={`guided-contribution-${slugId}`}>
        {repository.metadata.name}
      </h3>
      <label htmlFor={`guided-owner-statement-${slugId}`}>
        {copy.ownerStatementLabel}
        <textarea
          className="px-field"
          aria-describedby={`guided-owner-statement-help-${slugId}`}
          disabled={busy}
          id={`guided-owner-statement-${slugId}`}
          onChange={ownerStatementChange}
          rows={2}
          value={repository.ownerStatement}
        />
      </label>
      <section className="p5-contribution__suggestion px-panel px-panel--inset">
        <header className="p4-w2__tools">
          {proposal && (
            <h4 id={`guided-proposal-${slugId}`}>
              {repository.confirmedContribution
                ? copy.assertionConfirmed
                : repository.proposalSource === "model"
                  ? copy.proposalHeading
                  : copy.manualProposalHeading}
            </h4>
          )}
          <button
            className="px-button px-button--secondary"
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
        </header>

        {!proposal && !repository.confirmedContribution && (
          <>
            <p>{copy.manualEntryHelp}</p>
            <button
              className="px-button px-button--secondary"
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
          <>
            <p className="guided-onboarding__confirmed" role="status">
              {copy.assertionConfirmed}
            </p>
            <button
              className="px-button px-button--secondary"
              disabled={busy}
              onClick={() =>
                onAction({
                  type: "EDIT_CONFIRMED_CONTRIBUTION",
                  slug: repository.metadata.slug,
                })
              }
              type="button"
            >
              {copy.editConfirmed}
            </button>
          </>
        )}

        {proposal && (
          <section
            aria-labelledby={`guided-proposal-${slugId}`}
            className="guided-onboarding__proposal"
            data-evidence-class="OWNER_ASSERTION"
            data-confirmed={repository.confirmedContribution ? "true" : "false"}
          >
            <section
              aria-labelledby={`guided-proposed-assertions-${slugId}`}
              className="guided-onboarding__evidence guided-onboarding__evidence--proposed-assertions"
            >
              <h5
                className="visually-hidden"
                id={`guided-proposed-assertions-${slugId}`}
              >
                {proposalLocked
                  ? copy.confirmed
                  : copy.proposedAssertionsHeading}
              </h5>
              <div className="p4-w2__fields">
                {(["zh-TW", "en"] as const).map((proposalLocale) => (
                  <label
                    htmlFor={`guided-role-${slugId}-${proposalLocale}`}
                    key={`role-${proposalLocale}`}
                  >
                    {copy.roleLabel} ({copy.profileLocale(proposalLocale)})
                    <input
                      className="px-field"
                      disabled={busy || proposalLocked}
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
                      className="px-field"
                      disabled={busy || proposalLocked}
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
              </div>
              <fieldset
                className="p5-contribution__claims"
                disabled={busy || proposalLocked}
              >
                <legend id={`guided-claims-heading-${slugId}`}>
                  {copy.claimsHeading}
                </legend>
                <div className="p5-contribution__add">
                  <select
                    className="px-field"
                    aria-labelledby={`guided-claims-heading-${slugId}`}
                    id={`guided-new-claim-kind-${slugId}`}
                    value={newClaimKind}
                    onChange={(event) =>
                      setNewClaimKind(event.target.value as ClaimKind)
                    }
                  >
                    {(
                      [
                        "role",
                        "responsibility",
                        "achievement",
                        "context",
                      ] as const
                    ).map((kind) => (
                      <option key={kind} value={kind}>
                        {copy.claimLabel(kind)}
                      </option>
                    ))}
                  </select>
                  <button
                    className="px-button px-button--secondary"
                    type="button"
                    onClick={() =>
                      proposalChange({
                        ...proposal,
                        claims: [
                          ...proposal.claims,
                          {
                            id: `claim_${crypto.randomUUID().replaceAll("-", "")}`,
                            kind: newClaimKind,
                            statement: { "zh-TW": "", en: "" },
                          },
                        ],
                      })
                    }
                  >
                    {locale === "en" ? "Add my statement" : "新增自述"}
                  </button>
                </div>
                {proposal.claims.map((claim, index) => (
                  <section
                    className="p5-contribution__claim px-panel px-panel--inset"
                    key={claim.id}
                  >
                    <header className="p4-w2__tools">
                      <span className="px-badge">
                        {copy.claimLabel(claim.kind)}
                      </span>
                      <button
                        className="px-button px-button--quiet"
                        type="button"
                        onClick={() =>
                          proposalChange({
                            ...proposal,
                            claims: proposal.claims.filter(
                              (_, position) => position !== index,
                            ),
                          })
                        }
                      >
                        {locale === "en" ? "Remove my statement" : "移除自述"}{" "}
                        {index + 1}
                      </button>
                    </header>
                    <div className="p4-w2__fields">
                      {(["zh-TW", "en"] as const).map((proposalLocale) => (
                        <label
                          htmlFor={`guided-claim-${slugId}-${index}-${proposalLocale}`}
                          key={`${claim.id}-${proposalLocale}`}
                        >
                          {copy.claimLabel(claim.kind)} (
                          {copy.profileLocale(proposalLocale)})
                          <textarea
                            className="px-field"
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
                      ))}
                    </div>
                  </section>
                ))}
              </fieldset>
            </section>
          </section>
        )}
      </section>
      {proposal && !proposalLocked && (
        <>
          <footer className="p4-w2__confirm">
            <div className="guided-onboarding__proposal-actions">
              <button
                aria-describedby={
                  proposalDisabledReason
                    ? `guided-proposal-reason-${slugId}`
                    : undefined
                }
                disabled={Boolean(proposalDisabledReason)}
                className="ux-primary px-button px-button--primary"
                onClick={() => confirmContribution(proposal)}
                type="button"
              >
                {copy.accept}
              </button>
              <details className="p4-w2__info">
                <summary>
                  <span aria-hidden="true" className="p4-w2__actions-icon">
                    ⋯
                  </span>
                  <span className="p4-w2__actions-text">{copy.p4Actions}</span>
                </summary>
                {repository.previousContribution && (
                  <button
                    className="px-button px-button--secondary"
                    disabled={busy}
                    onClick={() =>
                      onAction({
                        type: "RESTORE_PREVIOUS_CONTRIBUTION",
                        slug: repository.metadata.slug,
                      })
                    }
                    type="button"
                  >
                    {copy.restorePrevious}
                  </button>
                )}
                <button
                  className="px-button px-button--secondary"
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
              </details>
            </div>
            {disabledReason(
              proposalDisabledReason,
              `guided-proposal-reason-${slugId}`,
            )}
          </footer>
        </>
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
      className="guided-onboarding__step p4-w1-intro px-panel"
    >
      <h2 id="guided-intro-heading">{copy.introTitle}</h2>
      <p>{copy.introBody}</p>
      <div className="p4-w1-intro__route">
        <button
          className="px-button px-button--primary"
          aria-describedby="guided-start-ai-help"
          disabled={busy}
          onClick={() => onAction({ type: "START_AI" })}
          type="button"
        >
          {copy.startAi}
        </button>
        <p id="guided-start-ai-help">{copy.startAiHelp}</p>
      </div>
      <div className="p4-w1-intro__route">
        <button
          className="px-button px-button--secondary"
          aria-describedby="guided-start-manual-help"
          disabled={busy}
          onClick={() => onAction({ type: "START_MANUAL" })}
          type="button"
        >
          {copy.startManual}
        </button>
        <p id="guided-start-manual-help">{copy.startManualHelp}</p>
      </div>
      {disabledReason(busy ? copy.disabledBusy : null, "guided-start-reason")}
      <details>
        <summary>{copy.outcome}</summary>
        <ul>
          {copy.outcomeItems.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </details>
      <button
        className="guided-onboarding__advanced-link px-button px-button--quiet"
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
  modelSetupReturn,
  onAction,
}: {
  state: GuidedOnboardingState;
  copy: Copy;
  busy: boolean;
  modelSetupView?: ReactNode;
  modelSetupReturn?: boolean;
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
      className="guided-onboarding__step guided-onboarding__step--models"
    >
      <h2 className="visually-hidden" id="guided-models-heading">
        {copy.modelsHeading}
      </h2>
      <p>{modelSetupReturn ? copy.modelReturnHelp : copy.modelsDescription}</p>
      {modelSetupView ?? <p>{copy.providerUnknown}</p>}
      <button
        aria-describedby={reason ? "guided-models-reason" : undefined}
        disabled={Boolean(reason) || busy}
        onClick={() => onAction({ type: "COMPLETE_MODEL_SETUP" })}
        className="px-button px-button--secondary"
        type="button"
      >
        {modelSetupReturn ? copy.returnToPreparation : copy.confirmModels}
      </button>
      {disabledReason(reason, "guided-models-reason")}
      <button
        disabled={busy}
        onClick={() => onAction({ type: "START_MANUAL" })}
        type="button"
      >
        {modelSetupReturn ? copy.returnWithoutSetup : copy.startManual}
      </button>
    </section>
  );
}

function RepositoriesStep({
  state,
  copy,
  busy,
  onAction,
  onDiscover,
  onResolve,
}: {
  state: GuidedOnboardingState;
  copy: Copy;
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
      className="guided-onboarding__step p4-w1-repositories px-panel"
    >
      <h2 id="guided-repositories-heading">{copy.accountHeading}</h2>
      <details className="p4-w1-sources" open={state.repositories.length === 0}>
        <summary>{copy.discover}</summary>
        <details
          className="p4-w1-discovery"
          open={state.repositories.length === 0}
        >
          <summary>{copy.accountLabel}</summary>
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
            aria-describedby={
              discoverReason ? "guided-discover-reason" : undefined
            }
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
        </details>
        <details className="p4-w1-manual">
          <summary>{copy.manualHeading}</summary>
          <form aria-labelledby="guided-manual-heading" onSubmit={resolve}>
            <h3 id="guided-manual-heading">{copy.manualHeading}</h3>
            <label htmlFor="guided-manual-repository">
              {copy.repositoryLabel}
            </label>
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
        </details>
      </details>

      <section aria-labelledby="guided-repository-list-heading">
        <h3 className="visually-hidden" id="guided-repository-list-heading">
          {copy.repositoryHeading}
        </h3>
        <p>{copy.repositoryCount(selectedCount, state.repositories.length)}</p>
        <p className="visually-hidden">{copy.repositoryDescription}</p>
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
                onAction={onAction}
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
      <footer className="p4-w1-confirm">
        <button
          className="px-button px-button--primary"
          aria-describedby={
            selectionReason ? "guided-selection-reason" : undefined
          }
          disabled={Boolean(selectionReason)}
          onClick={() => onAction({ type: "CONFIRM_SELECTION" })}
          type="button"
        >
          {state.route === "manual"
            ? copy.confirmManualSelection
            : copy.confirmSelection}
        </button>
        {disabledReason(selectionReason, "guided-selection-reason")}
      </footer>
    </section>
  );
}

function AnalysisModelStatusPanel({
  status,
  pending,
  copy,
  busy,
  onRefresh,
}: {
  status: GuidedOnboardingViewProps["analysisSelection"];
  pending: boolean;
  copy: Copy;
  busy: boolean;
  onRefresh: GuidedOnboardingViewProps["onRefreshAnalysisSelection"];
}) {
  const notSelected =
    status &&
    (status.selection.generation === 0 ||
      (!status.selection.chat_profile_id &&
        !status.selection.embedding_profile_id));
  const message = pending
    ? copy.checkingProvider
    : notSelected
      ? copy.modelsNotSelected
      : status
        ? (copy.modelReasons[status.reason] ?? copy.providerUnknown)
        : copy.providerUnknown;

  return (
    <div
      aria-labelledby="guided-provider-heading"
      className="guided-onboarding__provider-status p4-w1-model-status"
      role="group"
    >
      <div>
        <h3 id="guided-provider-heading">{copy.providerHeading}</h3>
        <button disabled={busy || pending} onClick={onRefresh} type="button">
          {copy.refreshProvider}
        </button>
      </div>
      <div aria-live="polite" role="status">
        {!pending && !notSelected && status?.eligible ? (
          <dl>
            <dt>{copy.chatModel}</dt>
            <dd>
              <span>{status.chat.model_id}</span>
              <span className="px-badge">{copy.modelTested}</span>
            </dd>
            <dt>{copy.searchModel}</dt>
            <dd>
              <span>{status.embedding.model_id}</span>
              <span className="px-badge">{copy.modelTested}</span>
            </dd>
          </dl>
        ) : (
          <p>{message}</p>
        )}
      </div>
    </div>
  );
}

function AnalysisStep({
  state,
  copy,
  locale,
  busy,
  analysisSelection,
  analysisSelectionPending,
  batchAnalysisView,
  batchAnalysisTerminal = false,
  batchAnalysisActive,
  batchCanCreate = false,
  batchCreatePending = false,
  onAction,
  onAnalyze,
  onCreateBatch,
  onRefreshAnalysisSelection,
}: {
  state: GuidedOnboardingState;
  copy: Copy;
  locale: Locale;
  busy: boolean;
  analysisSelection: GuidedOnboardingViewProps["analysisSelection"];
  analysisSelectionPending: boolean;
  batchAnalysisView?: ReactNode;
  batchAnalysisTerminal?: boolean;
  batchAnalysisActive?: boolean;
  batchCanCreate?: boolean;
  batchCreatePending?: boolean;
  onAction: GuidedOnboardingViewProps["onAction"];
  onAnalyze: GuidedOnboardingViewProps["onAnalyze"];
  onCreateBatch?: GuidedOnboardingViewProps["onCreateBatch"];
  onRefreshAnalysisSelection: GuidedOnboardingViewProps["onRefreshAnalysisSelection"];
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
  const analysisActions =
    !hasBatchAnalysis &&
    repositories.map((repository) => {
      const slugId = repository.metadata.slug.replace(/[^a-zA-Z0-9_-]/g, "-");
      const reason = analysisButtonReason(repository, state, copy, busy);
      const disabled = reason !== null || !repository.selected;
      const disabledMessage = !repository.selected
        ? copy.disabledNoSelection
        : reason;

      return (
        <div className="guided-analysis__retry" key={repository.metadata.slug}>
          {repositories.length > 1 && <span>{repository.metadata.slug}</span>}
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
        </div>
      );
    });
  const startBatchAction = onCreateBatch && (
    <div className="guided-onboarding__analysis-action">
      <button
        className={
          batchAnalysisTerminal
            ? "px-button px-button--secondary"
            : "px-button px-button--primary"
        }
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
  );
  const batchDetails = (
    <>
      {batchAnalysisView}
      {(batchAnalysisTerminal || hasActiveBatch) && startBatchAction}
    </>
  );
  return (
    <section
      aria-labelledby="guided-analysis-heading"
      className="guided-onboarding__step guided-analysis px-panel"
    >
      <h2 id="guided-analysis-heading">
        {allTerminal && !hasActiveBatch && repositories.some(analysisReady)
          ? copy.analysisResultsHeading
          : copy.analysisHeading}
      </h2>
      <p>{copy.analysisDescription}</p>
      {hasBatchAnalysis ? (
        <>
          {batchAnalysisTerminal ? (
            <details className="p4-w1-diagnostics">
              <summary>
                {locale === "zh-TW"
                  ? "分析診斷與批次詳情"
                  : "Analysis diagnostics and batch details"}
              </summary>
              {batchDetails}
            </details>
          ) : (
            batchDetails
          )}
          <BatchAnalysisResults
            copy={copy}
            locale={locale}
            repositories={repositories}
          />
        </>
      ) : (
        <>
          <AnalysisModelStatusPanel
            busy={busy}
            copy={copy}
            onRefresh={onRefreshAnalysisSelection}
            pending={analysisSelectionPending}
            status={analysisSelection}
          />
          {repositories.length > 0 ? (
            <ul className="guided-analysis__repositories">
              {repositories.map((repository) => (
                <li
                  className="guided-analysis__repository"
                  data-analysis-result={repository.metadata.slug}
                  key={repository.metadata.slug}
                >
                  {analysisReady(repository) ? (
                    <EvidenceGroups
                      copy={copy}
                      locale={locale}
                      repository={repository}
                    />
                  ) : (
                    <h3>{repository.metadata.slug}</h3>
                  )}
                  {repository.analysisStatus === "complete" && (
                    <p role="status">{copy.analyzed}</p>
                  )}
                  {repository.analysisStatus === "unavailable" && (
                    <p role="alert">{copy.unavailable}</p>
                  )}
                </li>
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
      <footer className="guided-analysis__actions">
        {hasBatchAnalysis &&
          !batchAnalysisTerminal &&
          !hasActiveBatch &&
          startBatchAction}
        <button
          aria-describedby={
            continueReason ? "guided-analysis-continue-reason" : undefined
          }
          disabled={Boolean(continueReason)}
          onClick={() => onAction({ type: "CONTINUE_TO_CONTRIBUTIONS" })}
          className={
            allTerminal || batchAnalysisTerminal
              ? "px-button px-button--primary"
              : "px-button px-button--secondary"
          }
          type="button"
        >
          {allTerminal || batchAnalysisTerminal
            ? copy.continueContributions
            : copy.continueManually}
        </button>
        {analysisActions}
        {disabledReason(continueReason, "guided-analysis-continue-reason")}
      </footer>
    </section>
  );
}

function ContributionsStep({
  locale,
  state,
  copy,
  busy,
  onAction,
  onSuggestContribution,
}: {
  locale: Locale;
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
      className="guided-onboarding__step p4-w2 p4-w2--contributions px-panel px-panel--raised"
    >
      <header className="p4-w2__tools p5-contributions__header">
        <h2 id="guided-contributions-heading">{copy.contributionsHeading}</h2>
        <details className="p4-w2__info px-info">
          <summary>ⓘ {copy.p4Help}</summary>
          <p>{copy.contributionsDescription}</p>
          {repositories.map((repository) => {
            const slugId = repository.metadata.slug.replace(
              /[^a-zA-Z0-9_-]/g,
              "-",
            );
            return (
              <section key={repository.metadata.slug}>
                <h3>{repository.metadata.slug}</h3>
                <p id={`guided-owner-statement-help-${slugId}`}>
                  {copy.ownerStatementHelp}
                </p>
                {repository.proposal && (
                  <>
                    <p>
                      {repository.proposalSource === "model"
                        ? copy.proposalDescription
                        : copy.manualProposalDescription}
                    </p>
                    <p>
                      <strong>{copy.originalStatement}:</strong>{" "}
                      {repository.ownerStatement}
                    </p>
                    {!repository.confirmedContribution && (
                      <p>{copy.proposedAssertionsDescription}</p>
                    )}
                  </>
                )}
              </section>
            );
          })}
        </details>
        <p className="px-meta" role="status">
          {copy.confirmed}:{" "}
          {
            repositories.filter(
              (repository) => repository.confirmedContribution !== null,
            ).length
          }
          /{repositories.length}
        </p>
      </header>
      {repositories.map((repository, index) => (
        <details
          className="p5-contributions__project px-panel"
          key={repository.metadata.slug}
          open={index === 0}
        >
          <summary className="p5-contributions__project-heading">
            <strong>{repository.metadata.slug}</strong>
            <span className="px-badge">
              {repository.confirmedContribution
                ? copy.confirmed
                : copy.notConfirmed}
            </span>
            <span className="p5-contributions__chevron" aria-hidden="true">
              ▶
            </span>
          </summary>
          <ContributionEditor
            locale={locale}
            busy={busy}
            copy={copy}
            key={repository.metadata.slug}
            onAction={onAction}
            onSuggestContribution={onSuggestContribution}
            repository={repository}
          />
        </details>
      ))}
      <footer
        className={confirmationsComplete ? "p4-w2__confirm" : "p4-w2__next"}
      >
        <button
          aria-describedby={
            continueReason ? "guided-contributions-continue-reason" : undefined
          }
          disabled={Boolean(continueReason)}
          onClick={() => onAction({ type: "CONTINUE_TO_PROFILE" })}
          className={`px-button ${confirmationsComplete ? "ux-primary px-button--primary" : "px-button--secondary"}`}
          type="button"
        >
          {copy.profileHeading}
        </button>
        {disabledReason(continueReason, "guided-contributions-continue-reason")}
      </footer>
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
    {
      id: "guided-profile-github-login",
      label: copy.githubLoginLabel,
      value: profile.githubLogin,
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
      className="guided-onboarding__step p4-w2 p4-w2--profile px-panel px-panel--raised"
    >
      <h2 id="guided-profile-heading">{copy.profileHeading}</h2>
      <details className="p4-w2__info px-info">
        <summary>ⓘ {copy.p4Help}</summary>
        <p>{copy.profileDescription}</p>
      </details>
      {missing.length > 0 && (
        <details className="p4-w2__info">
          <summary>{copy.profileRequired}</summary>
          <aside
            className="ux-missing-fields"
            aria-label={copy.profileRequired}
          >
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
        </details>
      )}
      <div className="p4-w2__profile-fields p4-w2__fields">
        <label htmlFor="guided-profile-display-name">
          {copy.displayNameLabel}
          <input
            className="px-field"
            disabled={busy}
            id="guided-profile-display-name"
            aria-invalid={!profile.displayName.trim() || undefined}
            aria-describedby={
              !profile.displayName.trim()
                ? "guided-profile-display-name-required"
                : undefined
            }
            required
            onChange={(event) =>
              setProfile(profileWithDisplayName(profile, event.target.value))
            }
            value={profile.displayName}
          />
          {!profile.displayName.trim() && (
            <span
              className="p4-w2__required"
              id="guided-profile-display-name-required"
            >
              {copy.p4Required}
            </span>
          )}
        </label>
        <label htmlFor="guided-profile-github-login">
          {copy.githubLoginLabel}
          <input
            className="px-field"
            disabled={busy}
            id="guided-profile-github-login"
            aria-invalid={!profile.githubLogin.trim() || undefined}
            aria-describedby={
              !profile.githubLogin.trim()
                ? "guided-profile-github-login-required"
                : "guided-profile-github-help"
            }
            required
            pattern="[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?"
            onChange={(event) =>
              setProfile({ ...profile, githubLogin: event.target.value })
            }
            value={profile.githubLogin}
          />
          {!profile.githubLogin.trim() && (
            <span
              className="p4-w2__required"
              id="guided-profile-github-login-required"
            >
              {copy.p4Required}
            </span>
          )}
        </label>
        <details className="p4-w2__info p4-w2__wide px-info">
          <summary>ⓘ {copy.githubLoginLabel}</summary>
          <p id="guided-profile-github-help">{copy.githubLoginHelp}</p>
        </details>
        <label className="p4-w2__wide" htmlFor="guided-profile-aliases">
          {copy.aliasesLabel}
          <textarea
            className="px-field"
            disabled={busy}
            id="guided-profile-aliases"
            onChange={(event) =>
              setProfile({ ...profile, aliasesText: event.target.value })
            }
            rows={2}
            value={profile.aliasesText}
          />
        </label>
        <fieldset className="p4-w2__fields p4-w2__wide" disabled={busy}>
          <legend>{copy.headlineLabel}</legend>
          {(["zh-TW", "en"] as const).map((profileLocale) => (
            <label
              htmlFor={`guided-profile-headline-${profileLocale}`}
              key={profileLocale}
            >
              {copy.profileLocale(profileLocale)}
              <input
                className="px-field"
                id={`guided-profile-headline-${profileLocale}`}
                aria-invalid={
                  !localized(profile.headline, profileLocale).trim() ||
                  undefined
                }
                aria-describedby={
                  !localized(profile.headline, profileLocale).trim()
                    ? `guided-profile-headline-${profileLocale}-required`
                    : undefined
                }
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
              {!localized(profile.headline, profileLocale).trim() && (
                <span
                  className="p4-w2__required"
                  id={`guided-profile-headline-${profileLocale}-required`}
                >
                  {copy.p4Required}
                </span>
              )}
            </label>
          ))}
        </fieldset>
        <fieldset className="p4-w2__fields p4-w2__wide" disabled={busy}>
          <legend>{copy.bioLabel}</legend>
          {(["zh-TW", "en"] as const).map((profileLocale) => (
            <label
              htmlFor={`guided-profile-bio-${profileLocale}`}
              key={profileLocale}
            >
              {copy.profileLocale(profileLocale)}
              <textarea
                className="px-field"
                id={`guided-profile-bio-${profileLocale}`}
                aria-invalid={
                  !localized(profile.bio, profileLocale).trim() || undefined
                }
                aria-describedby={
                  !localized(profile.bio, profileLocale).trim()
                    ? `guided-profile-bio-${profileLocale}-required`
                    : undefined
                }
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
              {!localized(profile.bio, profileLocale).trim() && (
                <span
                  className="p4-w2__required"
                  id={`guided-profile-bio-${profileLocale}-required`}
                >
                  {copy.p4Required}
                </span>
              )}
            </label>
          ))}
        </fieldset>
        <fieldset className="p4-w2__fields p4-w2__wide" disabled={busy}>
          <legend>{copy.greetingLabel}</legend>
          {(["zh-TW", "en"] as const).map((profileLocale) => (
            <label
              htmlFor={`guided-profile-greeting-${profileLocale}`}
              key={profileLocale}
            >
              {copy.profileLocale(profileLocale)}
              <textarea
                className="px-field"
                id={`guided-profile-greeting-${profileLocale}`}
                aria-invalid={
                  !localized(profile.greeting, profileLocale).trim() ||
                  undefined
                }
                aria-describedby={
                  !localized(profile.greeting, profileLocale).trim()
                    ? `guided-profile-greeting-${profileLocale}-required`
                    : undefined
                }
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
              {!localized(profile.greeting, profileLocale).trim() && (
                <span
                  className="p4-w2__required"
                  id={`guided-profile-greeting-${profileLocale}-required`}
                >
                  {copy.p4Required}
                </span>
              )}
            </label>
          ))}
        </fieldset>
      </div>
      <footer className="p4-w2__confirm">
        <button
          aria-describedby={
            confirmationReason ? "guided-profile-confirm-reason" : undefined
          }
          disabled={Boolean(confirmationReason)}
          onClick={() => onAction({ type: "CONFIRM_PROFILE" })}
          className="ux-primary px-button px-button--primary"
          type="button"
        >
          {copy.confirmProfile}
        </button>
        {disabledReason(confirmationReason, "guided-profile-confirm-reason")}
      </footer>
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
      className="guided-onboarding__step p4-w2 p4-w2--review px-panel px-panel--raised"
    >
      <h2 id="guided-review-heading">{copy.reviewHeading}</h2>
      <p>{copy.reviewDescription}</p>
      <section
        className="p4-w2__review-profile"
        aria-labelledby="guided-review-profile-heading"
      >
        <h3 id="guided-review-profile-heading">{copy.profileHeading}</h3>
        <dl>
          <dt>{copy.displayNameLabel}</dt>
          <dd>{state.profile.displayName}</dd>
          <dt>{copy.githubLoginLabel}</dt>
          <dd>{state.profile.githubLogin}</dd>
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
      <ul className="p4-w2__review-repositories">
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
      <footer className="p4-w2__confirm">
        <button
          className="px-button px-button--secondary"
          disabled={busy}
          onClick={() => onAction({ type: "GO_BACK" })}
          type="button"
        >
          {copy.back} · {copy.profileHeading}
        </button>
        <button
          className="ux-primary px-button px-button--primary"
          disabled={busy}
          onClick={onCreateDraft}
          type="button"
        >
          {copy.createDraft}
        </button>
      </footer>
    </section>
  );
}

function DraftStep({
  draft,
  validation,
  onOpenPublication,
  state,
  copy,
  locale,
  busy,
  onAction,
  onCopyDraft,
  onDownloadDraft,
}: {
  draft: GuidedOnboardingViewProps["draft"];
  validation: GuidedOnboardingViewProps["validation"];
  onOpenPublication: GuidedOnboardingViewProps["onOpenPublication"];
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
      className="guided-onboarding__step p4-w2 p4-w2--draft px-panel px-panel--raised"
    >
      <h2 className="visually-hidden" id="guided-draft-heading">
        {copy.draftHeading}
      </h2>
      <div className="p4-w2__tools">
        <DraftValidation locale={locale} validation={validation} />
        <details className="p4-w2__info px-info">
          <summary>
            ⓘ <span className="visually-hidden">{copy.p4Help}</span>
          </summary>
          <p>{copy.draftDescription}</p>
          <p>
            {chinese
              ? "內容草稿已完成，尚未套用。前往「預覽與分享」預覽、準備 NPC 並取得 GitHub 卡片。下方設定檔僅供備份／搬移，不是已上線網站。"
              : "Content is complete but not applied. Open Preview & share to preview, prepare your NPC and get its GitHub card. The settings file below is for backup or transfer, not a deployed website."}
          </p>
          <p className="px-badge" role="status">
            {copy.draftReady}
          </p>
        </details>
      </div>
      <pre
        className="p7-draft-yaml px-field"
        role="region"
        aria-label={chinese ? "設定草稿（YAML）" : "Configuration draft (YAML)"}
        tabIndex={0}
      >
        {draft}
      </pre>
      <footer className="p4-w2__confirm p4-w2__draft-confirm">
        <button
          className="px-button px-button--primary"
          disabled={busy}
          onClick={onOpenPublication}
          type="button"
        >
          {chinese ? "預覽與分享" : "Preview & share"}
        </button>
        <details className="p4-w2__info px-info">
          <summary>
            <span aria-hidden="true" className="p4-w2__actions-icon">
              ⋯
            </span>
            <span className="p4-w2__actions-text">{copy.p4Actions}</span>
          </summary>
          <div className="guided-onboarding__draft-actions">
            <button
              className="px-button px-button--secondary"
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
            <button
              className="px-button px-button--secondary"
              disabled={busy}
              onClick={onDownloadDraft}
              type="button"
            >
              {copy.downloadDraft}
            </button>
          </div>
          <button
            className="px-button px-button--secondary"
            disabled={busy}
            onClick={() => onAction({ type: "SET_MODE", mode: "advanced" })}
            type="button"
          >
            {copy.advancedMode}
          </button>
          <button
            className="px-button px-button--secondary"
            disabled={busy}
            onClick={() => onAction({ type: "SET_MODE", mode: "guided" })}
            type="button"
          >
            {copy.guidedMode}
          </button>
        </details>
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
              ? "無法使用剪貼簿，請改用備份設定（YAML）。"
              : "Clipboard unavailable. Download the YAML instead."}
          </p>
        )}
        {state.rawYamlHasUnmappedChanges && (
          <p role="alert">{copy.rawYamlWarning}</p>
        )}
      </footer>
    </section>
  );
}

export function GuidedOnboardingView({
  draft,
  validation,
  onOpenPublication,
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
  modelSetupReturn,
  analysisSelection,
  analysisSelectionPending,
  onAction,
  onDiscover,
  onResolve,
  onAnalyze,
  onCreateBatch,
  onRefreshAnalysisSelection,
  onSuggestContribution,
  onCreateDraft,
  onCopyDraft,
  onDownloadDraft,
  workspaceStatus,
}: GuidedOnboardingViewProps & { workspaceStatus?: AdminWorkspaceStatus }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const errorRef = useRef<HTMLParagraphElement>(null);
  const previousStep = useRef(state.step);
  const interacted = useRef(false);
  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true });
    if (previousStep.current !== state.step) {
      // Restoring a draft after mount is still initial loading.
      if (interacted.current)
        headingRef.current?.scrollIntoView({
          block: "start",
          behavior: "instant",
        });
      previousStep.current = state.step;
    }
  }, [state.step]);
  useEffect(() => {
    if (errorCode) errorRef.current?.focus();
  }, [errorCode]);
  const copy = COPY[locale];
  const error = errorCode
    ? guidedErrorMessage(locale, errorCode, state.step)
    : "";
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
      onClickCapture={() => {
        interacted.current = true;
      }}
      onKeyDownCapture={() => {
        interacted.current = true;
      }}
    >
      <header className="guided-onboarding__header">
        <h1
          className="px-display"
          id="guided-onboarding-heading"
          ref={headingRef}
          tabIndex={-1}
          onBlur={(event) => delete event.currentTarget.dataset.keyboardFocus}
          onKeyDown={(event) => {
            event.currentTarget.dataset.keyboardFocus = "true";
          }}
        >
          <span className="visually-hidden">{copy.title} · </span>
          {copy.steps[state.step]}
        </h1>
        {state.step !== "intro" && (
          <div className="guided-onboarding__navigation-actions">
            <button
              className="px-button px-button--secondary"
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
            <details className="guided-onboarding__navigation-disclosure">
              <summary>
                {locale === "zh-TW" ? "編輯或重新開始" : "Edit or start over"}
              </summary>
              {state.step !== "repositories" && state.step !== "analysis" && (
                <button
                  className="px-button px-button--secondary"
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
              <ConfirmButton
                className="px-button px-button--danger"
                aria-describedby={
                  navigationBatchActive
                    ? "guided-navigation-batch-reason"
                    : undefined
                }
                disabled={busy || navigationBatchActive}
                locale={locale}
                title={copy.startOverTitle}
                description={copy.startOverDescription}
                confirmLabel={copy.startOver}
                destructive
                onConfirm={() => {
                  if (!busy && !navigationBatchActive)
                    onAction({ type: "RESET" });
                }}
              >
                {copy.startOver}
              </ConfirmButton>
            </details>
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
        <p
          className="guided-onboarding__error"
          ref={errorRef}
          role="alert"
          tabIndex={-1}
        >
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
              modelSetupReturn={modelSetupReturn}
              onAction={onAction}
              state={state}
            />
          )}
          {state.step === "repositories" && (
            <RepositoriesStep
              busy={busy}
              copy={copy}
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
              onRefreshAnalysisSelection={onRefreshAnalysisSelection}
              analysisSelection={analysisSelection}
              analysisSelectionPending={analysisSelectionPending}
              state={state}
            />
          )}
          {state.step === "contributions" && (
            <ContributionsStep
              locale={locale}
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
              draft={draft}
              validation={validation}
              onOpenPublication={onOpenPublication}
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
      <AdminStatusCards
        locale={locale}
        state={state}
        status={workspaceStatus ?? EMPTY_WORKSPACE_STATUS}
      />
    </section>
  );
}

import type { ReactNode } from "react";

import type { Locale } from "../../i18n/messages";

export type LocalizedText = Record<Locale, string>;

export interface RepositoryMetadata {
  slug: string;
  name: string;
  description: string | null;
  primary_language: string | null;
  default_branch: string;
  is_fork: boolean;
  is_archived: boolean;
  updated_at: string | null;
  html_url: string;
}

export interface RepositoryFact {
  evidence_class: "REPOSITORY_FACT";
  evidence_id: string;
  path: string;
  start_line: number | null;
  end_line: number | null;
  text: string;
}

export interface ModelInference {
  evidence_class: "MODEL_INFERENCE";
  statement: LocalizedText;
  supporting_evidence_ids: string[];
}

export interface SuggestedClaim {
  id: string;
  kind: "role" | "responsibility" | "achievement" | "context";
  statement: LocalizedText;
}

export interface ContributionProposal {
  role: LocalizedText;
  summary: LocalizedText;
  claims: SuggestedClaim[];
}

export interface ConfirmedContribution extends ContributionProposal {
  evidence_class: "OWNER_ASSERTION";
}

export interface GuidedProfile {
  displayName: string;
  headline: LocalizedText;
  bio: LocalizedText;
  greeting: LocalizedText;
}

export interface RepositoryAnalysis {
  repository: {
    slug: string;
    commit_sha: string;
    default_branch: string;
    html_url: string;
  };
  facts: RepositoryFact[];
  inferences: ModelInference[];
  skipped_summary: { count: number; reasons: string[] };
}

export type AnalysisStatus = "idle" | "running" | "complete" | "unavailable";

export interface GuidedRepository {
  metadata: RepositoryMetadata;
  ref: string | null;
  include: string[];
  exclude: string[];
  selected: boolean;
  analysisStatus: AnalysisStatus;
  analysis: RepositoryAnalysis | null;
  ownerStatement: string;
  proposal: ContributionProposal | null;
  confirmedContribution: ConfirmedContribution | null;
}

export type GuidedStep =
  | "intro"
  | "repositories"
  | "analysis"
  | "contributions"
  | "profile"
  | "review"
  | "draft";

export interface GuidedOnboardingState {
  step: GuidedStep;
  mode: "guided" | "advanced";
  githubAccount: string;
  discoveryPage: number;
  discoveryHasMore: boolean;
  repositories: GuidedRepository[];
  selectionConfirmed: boolean;
  profile: GuidedProfile;
  profileConfirmed: boolean;
  rawYamlHasUnmappedChanges: boolean;
}

export type GuidedOnboardingAction =
  | { type: "START" }
  | { type: "SET_ACCOUNT"; account: string }
  | {
      type: "MERGE_REPOSITORIES";
      repositories: RepositoryMetadata[];
      page: number;
      hasMore: boolean;
    }
  | { type: "ADD_REPOSITORY"; repository: RepositoryMetadata }
  | { type: "TOGGLE_REPOSITORY"; slug: string }
  | {
      type: "SET_REPOSITORY_OPTIONS";
      slug: string;
      ref: string | null;
      include: string[];
      exclude: string[];
    }
  | { type: "CONFIRM_SELECTION" }
  | { type: "ANALYSIS_STARTED"; slug: string }
  | { type: "ANALYSIS_COMPLETED"; slug: string; analysis: RepositoryAnalysis }
  | { type: "ANALYSIS_UNAVAILABLE"; slug: string }
  | { type: "CONTINUE_TO_CONTRIBUTIONS" }
  | { type: "SET_OWNER_STATEMENT"; slug: string; statement: string }
  | { type: "BEGIN_MANUAL_CONTRIBUTION"; slug: string }
  | {
      type: "SET_CONTRIBUTION_PROPOSAL";
      slug: string;
      originalStatement: string;
      proposal: ContributionProposal;
    }
  | {
      type: "CONFIRM_CONTRIBUTION";
      slug: string;
      contribution: ContributionProposal;
    }
  | { type: "REJECT_CONTRIBUTION"; slug: string }
  | { type: "CONTINUE_TO_PROFILE" }
  | { type: "SET_PROFILE"; profile: GuidedProfile }
  | { type: "CONFIRM_PROFILE" }
  | { type: "DRAFT_READY" }
  | { type: "SET_MODE"; mode: "guided" | "advanced" }
  | { type: "MARK_RAW_YAML_UNMAPPED"; value: boolean }
  | { type: "RESET" };

export interface GuidedOnboardingViewProps {
  locale: Locale;
  state: GuidedOnboardingState;
  busy: boolean;
  errorCode: string;
  batchAnalysisView?: ReactNode;
  batchAnalysisTerminal?: boolean;
  batchCanCreate?: boolean;
  batchCreatePending?: boolean;
  providerStatus: GuidedProviderStatus | null;
  providerStatusPending: boolean;
  onAction: (action: GuidedOnboardingAction) => void;
  onDiscover: (account: string, page: number) => void;
  onResolve: (repository: string, ref: string | null) => void;
  onAnalyze: (slug: string) => void;
  onCreateBatch?: () => void;
  onRefreshProviderStatus: () => void;
  onSuggestContribution: (slug: string) => void;
  onCreateDraft: () => void;
  onCopyDraft: () => void;
  onDownloadDraft: () => void;
}

export interface GuidedProviderStatus {
  ready: boolean;
  provider: "ollama" | "openai_compatible" | null;
  lastCheckedAt: string | null;
}

interface PersistedRepository {
  slug: string;
  metadata: RepositoryMetadata;
  ref: string | null;
  include: string[];
  exclude: string[];
  ownerStatement: string;
  confirmedContribution: ConfirmedContribution | null;
}

interface PersistedGuidedOnboarding {
  version: 1;
  step: GuidedStep;
  githubAccount: string;
  discoveryPage: number;
  discoveryHasMore: boolean;
  selectionConfirmed: boolean;
  profile: GuidedProfile;
  profileConfirmed: boolean;
  repositories: PersistedRepository[];
}

const STORAGE_LIMIT = 128 * 1024;
const STEPS: readonly GuidedStep[] = [
  "intro",
  "repositories",
  "analysis",
  "contributions",
  "profile",
  "review",
  "draft",
];

export function initialGuidedOnboardingState(
  hasExistingDraft = false,
): GuidedOnboardingState {
  return {
    step: hasExistingDraft ? "draft" : "intro",
    mode: hasExistingDraft ? "advanced" : "guided",
    githubAccount: "",
    discoveryPage: 0,
    discoveryHasMore: false,
    repositories: [],
    selectionConfirmed: false,
    profile: emptyGuidedProfile(),
    profileConfirmed: false,
    rawYamlHasUnmappedChanges: false,
  };
}

export function selectedRepositories(
  state: GuidedOnboardingState,
): GuidedRepository[] {
  return state.repositories.filter((repository) => repository.selected);
}

export function guidedOnboardingReducer(
  state: GuidedOnboardingState,
  action: GuidedOnboardingAction,
): GuidedOnboardingState {
  switch (action.type) {
    case "START":
      requireStep(state, "intro");
      return { ...state, step: "repositories", mode: "guided" };
    case "SET_ACCOUNT":
      requireUnconfirmedSelection(state);
      return { ...state, githubAccount: action.account };
    case "MERGE_REPOSITORIES":
      requireUnconfirmedSelection(state);
      return {
        ...state,
        repositories: mergeRepositories(
          state.repositories,
          action.repositories,
        ),
        discoveryPage: action.page,
        discoveryHasMore: action.hasMore,
      };
    case "ADD_REPOSITORY":
      requireUnconfirmedSelection(state);
      return {
        ...state,
        repositories: mergeRepositories(state.repositories, [
          action.repository,
        ]),
      };
    case "TOGGLE_REPOSITORY":
      requireUnconfirmedSelection(state);
      return updateRepository(state, action.slug, (repository) => ({
        ...repository,
        selected: !repository.selected,
      }));
    case "SET_REPOSITORY_OPTIONS":
      requireUnconfirmedSelection(state);
      return updateRepository(state, action.slug, (repository) => ({
        ...repository,
        ref: action.ref,
        include: [...action.include],
        exclude: [...action.exclude],
      }));
    case "CONFIRM_SELECTION":
      requireStep(state, "repositories");
      if (selectedRepositories(state).length === 0) {
        throw new Error("ONBOARDING_SELECTION_REQUIRED");
      }
      return { ...state, step: "analysis", selectionConfirmed: true };
    case "ANALYSIS_STARTED":
      requireStep(state, "analysis");
      return updateSelectedRepository(state, action.slug, (repository) => ({
        ...repository,
        analysisStatus: "running",
        analysis: null,
      }));
    case "ANALYSIS_COMPLETED":
      requireStep(state, "analysis");
      if (action.analysis.repository.slug !== action.slug) {
        throw new Error("ONBOARDING_ANALYSIS_SLUG_MISMATCH");
      }
      return updateSelectedRepository(state, action.slug, (repository) => ({
        ...repository,
        analysisStatus: "complete",
        analysis: action.analysis,
      }));
    case "ANALYSIS_UNAVAILABLE":
      requireStep(state, "analysis");
      return updateSelectedRepository(state, action.slug, (repository) => ({
        ...repository,
        analysisStatus: "unavailable",
        analysis: null,
      }));
    case "CONTINUE_TO_CONTRIBUTIONS":
      requireStep(state, "analysis");
      if (
        selectedRepositories(state).some(
          (repository) => repository.analysisStatus === "running",
        )
      ) {
        throw new Error("ONBOARDING_ANALYSIS_IN_PROGRESS");
      }
      if (
        selectedRepositories(state).some(
          (repository) => repository.analysisStatus === "idle",
        )
      ) {
        throw new Error("ONBOARDING_ANALYSIS_REQUIRED");
      }
      return { ...state, step: "contributions" };
    case "SET_OWNER_STATEMENT":
      requireStep(state, "contributions");
      return updateSelectedRepository(state, action.slug, (repository) => ({
        ...repository,
        ownerStatement: action.statement,
        proposal: null,
        confirmedContribution: null,
      }));
    case "BEGIN_MANUAL_CONTRIBUTION":
      requireStep(state, "contributions");
      return updateSelectedRepository(state, action.slug, (repository) => {
        if (!repository.ownerStatement.trim()) {
          throw new Error("ONBOARDING_OWNER_STATEMENT_REQUIRED");
        }
        return {
          ...repository,
          proposal: {
            role: { "zh-TW": "", en: "" },
            summary: { "zh-TW": "", en: "" },
            claims: [],
          },
          confirmedContribution: null,
        };
      });
    case "SET_CONTRIBUTION_PROPOSAL":
      requireStep(state, "contributions");
      return updateSelectedRepository(state, action.slug, (repository) => {
        if (repository.ownerStatement !== action.originalStatement) {
          throw new Error("ONBOARDING_OWNER_STATEMENT_CHANGED");
        }
        return { ...repository, proposal: cloneProposal(action.proposal) };
      });
    case "CONFIRM_CONTRIBUTION":
      requireStep(state, "contributions");
      return updateSelectedRepository(state, action.slug, (repository) => {
        if (!repository.ownerStatement.trim()) {
          throw new Error("ONBOARDING_OWNER_STATEMENT_REQUIRED");
        }
        if (!contributionIsComplete(action.contribution)) {
          throw new Error("ONBOARDING_BILINGUAL_CONTRIBUTION_REQUIRED");
        }
        return {
          ...repository,
          confirmedContribution: {
            ...cloneProposal(action.contribution),
            evidence_class: "OWNER_ASSERTION",
          },
        };
      });
    case "REJECT_CONTRIBUTION":
      requireStep(state, "contributions");
      return updateSelectedRepository(state, action.slug, (repository) => ({
        ...repository,
        proposal: null,
        confirmedContribution: null,
      }));
    case "CONTINUE_TO_PROFILE":
      requireStep(state, "contributions");
      if (
        selectedRepositories(state).some(
          (repository) => repository.confirmedContribution === null,
        )
      ) {
        throw new Error("ONBOARDING_CONFIRMATION_REQUIRED");
      }
      return { ...state, step: "profile" };
    case "SET_PROFILE":
      requireStep(state, "profile");
      return {
        ...state,
        profile: cloneProfile(action.profile),
        profileConfirmed: false,
      };
    case "CONFIRM_PROFILE":
      requireStep(state, "profile");
      if (!profileIsComplete(state.profile)) {
        throw new Error("ONBOARDING_PROFILE_REQUIRED");
      }
      return { ...state, step: "review", profileConfirmed: true };
    case "DRAFT_READY":
      requireStep(state, "review");
      return { ...state, step: "draft" };
    case "SET_MODE":
      if (action.mode === "guided" && state.rawYamlHasUnmappedChanges) {
        throw new Error("ONBOARDING_RAW_YAML_UNMAPPED");
      }
      return { ...state, mode: action.mode };
    case "MARK_RAW_YAML_UNMAPPED":
      return {
        ...state,
        mode: action.value ? "advanced" : state.mode,
        rawYamlHasUnmappedChanges: action.value,
      };
    case "RESET":
      return initialGuidedOnboardingState();
  }
}

export function serializeGuidedOnboarding(
  state: GuidedOnboardingState,
): string {
  const persisted: PersistedGuidedOnboarding = {
    version: 1,
    step: state.step,
    githubAccount: state.githubAccount,
    discoveryPage: state.discoveryPage,
    discoveryHasMore: state.discoveryHasMore,
    selectionConfirmed: state.selectionConfirmed,
    profile: cloneProfile(state.profile),
    profileConfirmed: state.profileConfirmed,
    repositories: selectedRepositories(state).map((repository) => ({
      slug: repository.metadata.slug,
      metadata: { ...repository.metadata },
      ref: repository.ref,
      include: [...repository.include],
      exclude: [...repository.exclude],
      ownerStatement: repository.ownerStatement,
      confirmedContribution: repository.confirmedContribution
        ? {
            ...cloneProposal(repository.confirmedContribution),
            evidence_class: "OWNER_ASSERTION",
          }
        : null,
    })),
  };
  const content = JSON.stringify(persisted);
  if (content.length > STORAGE_LIMIT) {
    throw new Error("ONBOARDING_RESUME_TOO_LARGE");
  }
  return content;
}

export function parseGuidedOnboarding(
  content: string,
  metadata?: RepositoryMetadata[],
): GuidedOnboardingState | null {
  if (!content || content.length > STORAGE_LIMIT) return null;
  try {
    const value: unknown = JSON.parse(content);
    if (!isRecord(value) || value.version !== 1) return null;
    if (!isGuidedStep(value.step) || typeof value.githubAccount !== "string")
      return null;
    const profile = parseProfile(value.profile);
    if (
      typeof value.selectionConfirmed !== "boolean" ||
      typeof value.discoveryPage !== "number" ||
      typeof value.discoveryHasMore !== "boolean" ||
      typeof value.profileConfirmed !== "boolean" ||
      !profile ||
      !Array.isArray(value.repositories)
    ) {
      return null;
    }
    const bySlug = metadata
      ? new Map(metadata.map((repository) => [repository.slug, repository]))
      : null;
    const repositories: GuidedRepository[] = [];
    for (const item of value.repositories) {
      const persisted = parsePersistedRepository(item);
      if (!persisted) return null;
      const repositoryMetadata = bySlug
        ? bySlug.get(persisted.slug)
        : persisted.metadata;
      if (!repositoryMetadata) return null;
      repositories.push({
        metadata: repositoryMetadata,
        ref: persisted.ref,
        include: persisted.include,
        exclude: persisted.exclude,
        selected: true,
        analysisStatus: "idle",
        analysis: null,
        ownerStatement: persisted.ownerStatement,
        proposal: null,
        confirmedContribution: persisted.confirmedContribution,
      });
    }
    return {
      step: value.step,
      mode: "guided",
      githubAccount: value.githubAccount,
      discoveryPage: value.discoveryPage,
      discoveryHasMore: value.discoveryHasMore,
      repositories,
      selectionConfirmed: value.selectionConfirmed,
      profile,
      profileConfirmed: value.profileConfirmed,
      rawYamlHasUnmappedChanges: false,
    };
  } catch {
    return null;
  }
}

export function guidedErrorMessage(locale: Locale, code: string): string {
  const messages: Record<string, LocalizedText> = {
    NOT_FOUND: {
      "zh-TW":
        "找不到這個公開 GitHub 帳戶或 repository。請檢查名稱，或改用 repository 網址。",
      en: "This public GitHub account or repository was not found. Check the name or use a repository URL.",
    },
    RATE_LIMITED: {
      "zh-TW":
        "GitHub 暫時限制查詢頻率。你的選擇已保留，請稍後重試或手動加入 repository。",
      en: "GitHub temporarily limited requests. Your selection is preserved; retry later or add a repository manually.",
    },
    GITHUB_ERROR: {
      "zh-TW":
        "目前無法連線 GitHub。請檢查網路後重試，或改用手動加入 repository。",
      en: "GitHub could not be reached. Check the network and retry, or add a repository manually.",
    },
    VALIDATION_ERROR: {
      "zh-TW":
        "GitHub 使用者名稱或個人檔案 URL 格式無效。請輸入 username 或 https://github.com/username。",
      en: "The GitHub username or profile URL is invalid. Enter a username or https://github.com/username.",
    },
    MODEL_UNAVAILABLE: {
      "zh-TW":
        "目前無法使用設定好的模型。你的選擇已保留，可稍後重試或繼續手動填寫貢獻。",
      en: "The configured model is unavailable. Your selection is preserved; retry later or continue with manual contribution details.",
    },
    PROVIDER_TIMEOUT: {
      "zh-TW": "分析逾時且未儲存部分結果。你的選擇已保留，可以重新分析。",
      en: "Analysis timed out and no partial result was saved. Your selection is preserved and can be analyzed again.",
    },
    NO_ELIGIBLE_CONTENT: {
      "zh-TW":
        "這個 repository 沒有可安全分析的內容。請調整包含／排除路徑，或繼續手動填寫。",
      en: "This repository has no content eligible for safe analysis. Adjust include/exclude paths or continue manually.",
    },
    CONCURRENCY_LIMIT: {
      "zh-TW": "已有一個分析正在進行。請等待完成後再試。",
      en: "Another analysis is already running. Wait for it to finish before retrying.",
    },
    ONBOARDING_RAW_YAML_UNMAPPED: {
      "zh-TW":
        "原始 YAML 已被修改，無法安全地自動回填引導欄位。請留在進階模式驗證內容，或重新開始引導設定。",
      en: "Raw YAML was edited and cannot be mapped safely back into guided fields. Validate it in advanced mode or restart guided setup.",
    },
  };
  return (
    messages[code]?.[locale] ??
    (locale === "zh-TW"
      ? "操作未完成，但你的輸入已保留。請檢查內容後重試。"
      : "The operation did not complete, but your input is preserved. Review it and try again.")
  );
}

function newGuidedRepository(metadata: RepositoryMetadata): GuidedRepository {
  return {
    metadata,
    ref: null,
    include: [],
    exclude: [],
    selected: false,
    analysisStatus: "idle",
    analysis: null,
    ownerStatement: "",
    proposal: null,
    confirmedContribution: null,
  };
}

function mergeRepositories(
  existing: GuidedRepository[],
  incoming: RepositoryMetadata[],
): GuidedRepository[] {
  const result = [...existing];
  const indexes = new Map(
    result.map((repository, index) => [repository.metadata.slug, index]),
  );
  for (const metadata of incoming) {
    const index = indexes.get(metadata.slug);
    if (index === undefined) {
      indexes.set(metadata.slug, result.length);
      result.push(newGuidedRepository(metadata));
    } else {
      result[index] = { ...result[index], metadata };
    }
  }
  return result;
}

function updateRepository(
  state: GuidedOnboardingState,
  slug: string,
  update: (repository: GuidedRepository) => GuidedRepository,
): GuidedOnboardingState {
  let found = false;
  const repositories = state.repositories.map((repository) => {
    if (repository.metadata.slug !== slug) return repository;
    found = true;
    return update(repository);
  });
  if (!found) throw new Error("ONBOARDING_REPOSITORY_NOT_FOUND");
  return { ...state, repositories };
}

function updateSelectedRepository(
  state: GuidedOnboardingState,
  slug: string,
  update: (repository: GuidedRepository) => GuidedRepository,
): GuidedOnboardingState {
  return updateRepository(state, slug, (repository) => {
    if (!state.selectionConfirmed || !repository.selected) {
      throw new Error("ONBOARDING_REPOSITORY_NOT_CONFIRMED");
    }
    return update(repository);
  });
}

function requireStep(state: GuidedOnboardingState, step: GuidedStep): void {
  if (state.step !== step) throw new Error("ONBOARDING_ILLEGAL_TRANSITION");
}

function requireUnconfirmedSelection(state: GuidedOnboardingState): void {
  requireStep(state, "repositories");
  if (state.selectionConfirmed)
    throw new Error("ONBOARDING_SELECTION_ALREADY_CONFIRMED");
}

function cloneProposal(proposal: ContributionProposal): ContributionProposal {
  return {
    role: { ...proposal.role },
    summary: { ...proposal.summary },
    claims: proposal.claims.map((claim) => ({
      ...claim,
      statement: { ...claim.statement },
    })),
  };
}

function emptyGuidedProfile(): GuidedProfile {
  return {
    displayName: "",
    headline: { "zh-TW": "", en: "" },
    bio: { "zh-TW": "", en: "" },
    greeting: {
      "zh-TW": "嗨，我是你的 RepoNPC。想先了解哪一個專案？",
      en: "Hi, I am your RepoNPC. Which project would you like to explore?",
    },
  };
}

function cloneProfile(profile: GuidedProfile): GuidedProfile {
  return {
    displayName: profile.displayName,
    headline: { ...profile.headline },
    bio: { ...profile.bio },
    greeting: { ...profile.greeting },
  };
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

function contributionIsComplete(contribution: ContributionProposal): boolean {
  return [
    contribution.role["zh-TW"],
    contribution.role.en,
    contribution.summary["zh-TW"],
    contribution.summary.en,
  ].every((value) => value.trim().length > 0);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isGuidedStep(value: unknown): value is GuidedStep {
  return typeof value === "string" && STEPS.includes(value as GuidedStep);
}

function stringArray(value: unknown): string[] | null {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string"))
    return null;
  return [...value];
}

function localizedText(value: unknown): LocalizedText | null {
  if (
    !isRecord(value) ||
    typeof value["zh-TW"] !== "string" ||
    typeof value.en !== "string"
  ) {
    return null;
  }
  return { "zh-TW": value["zh-TW"], en: value.en };
}

function parseProfile(value: unknown): GuidedProfile | null {
  if (!isRecord(value) || typeof value.displayName !== "string") return null;
  const headline = localizedText(value.headline);
  const bio = localizedText(value.bio);
  const greeting = localizedText(value.greeting);
  if (!headline || !bio || !greeting) return null;
  return { displayName: value.displayName, headline, bio, greeting };
}

function parseConfirmedContribution(
  value: unknown,
): ConfirmedContribution | null | false {
  if (value === null) return null;
  if (!isRecord(value) || value.evidence_class !== "OWNER_ASSERTION")
    return false;
  const role = localizedText(value.role);
  const summary = localizedText(value.summary);
  if (!role || !summary || !Array.isArray(value.claims)) return false;
  const claims: SuggestedClaim[] = [];
  for (const claim of value.claims) {
    if (!isRecord(claim) || typeof claim.id !== "string") return false;
    if (
      !["role", "responsibility", "achievement", "context"].includes(
        String(claim.kind),
      )
    ) {
      return false;
    }
    const statement = localizedText(claim.statement);
    if (!statement) return false;
    claims.push({
      id: claim.id,
      kind: claim.kind as SuggestedClaim["kind"],
      statement,
    });
  }
  return { evidence_class: "OWNER_ASSERTION", role, summary, claims };
}

function parsePersistedRepository(value: unknown): PersistedRepository | null {
  if (!isRecord(value) || typeof value.slug !== "string") return null;
  if (value.ref !== null && typeof value.ref !== "string") return null;
  const include = stringArray(value.include);
  const exclude = stringArray(value.exclude);
  const metadata = parseRepositoryMetadata(value.metadata);
  const confirmedContribution = parseConfirmedContribution(
    value.confirmedContribution,
  );
  if (
    !metadata ||
    metadata.slug !== value.slug ||
    !include ||
    !exclude ||
    typeof value.ownerStatement !== "string" ||
    confirmedContribution === false
  ) {
    return null;
  }
  return {
    slug: value.slug,
    metadata,
    ref: value.ref,
    include,
    exclude,
    ownerStatement: value.ownerStatement,
    confirmedContribution,
  };
}

function parseRepositoryMetadata(value: unknown): RepositoryMetadata | null {
  if (!isRecord(value)) return null;
  if (
    typeof value.slug !== "string" ||
    !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(value.slug) ||
    typeof value.name !== "string" ||
    typeof value.default_branch !== "string" ||
    typeof value.is_fork !== "boolean" ||
    typeof value.is_archived !== "boolean" ||
    typeof value.html_url !== "string" ||
    value.html_url !== `https://github.com/${value.slug}` ||
    (value.description !== null && typeof value.description !== "string") ||
    (value.primary_language !== null &&
      typeof value.primary_language !== "string") ||
    (value.updated_at !== null && typeof value.updated_at !== "string")
  ) {
    return null;
  }
  return {
    slug: value.slug,
    name: value.name,
    description: value.description,
    primary_language: value.primary_language,
    default_branch: value.default_branch,
    is_fork: value.is_fork,
    is_archived: value.is_archived,
    updated_at: value.updated_at,
    html_url: value.html_url,
  };
}

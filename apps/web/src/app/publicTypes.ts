import type {
  CharacterMovement,
  CharacterState,
} from "../features/character/CharacterRenderer";
import type { RefObject } from "react";
import type { Locale } from "../i18n/messages";
import type { Citation, VisitorTurn } from "./VisitorConversation";

export interface SceneTokens {
  background: string;
  surface: string;
  surface_alt: string;
  ink: string;
  muted_ink: string;
  accent: string;
  accent_ink: string;
  border: string;
  stage: string;
  focus: string;
  sky: string;
  horizon: string;
  hill_far: string;
  hill_near: string;
  grass: string;
  ground: string;
  wood: string;
  celestial: string;
}

export interface PublicScene {
  revision: number;
  scheme: { id: string; version: number };
  color_mode: "system" | "light" | "dark";
  visitor_mode_toggle: boolean;
  visitor_scheme_choice: boolean;
  themes: { light: SceneTokens; dark: SceneTokens };
  npc_plate: { light: boolean; dark: boolean };
  schemes: Array<{
    id: string;
    version: number;
    label: Record<Locale, string>;
    themes: { light: SceneTokens; dark: SceneTokens };
    npc_plate: { light: boolean; dark: boolean };
  }>;
  background_url: string | null;
  background_scaling: "smooth" | "pixelated";
  background_focus: { x: number; y: number };
  background_dim: "auto" | "none" | "low" | "medium" | "high";
}

export interface PublicRepository {
  slug: string;
  summary: string;
  role: string;
  tags: string[];
  demo_url: string | null;
  language?: string | null;
  stars?: number | null;
  forks?: number | null;
}

export interface PublicProfile {
  schema_version: number;
  locale: Locale;
  profile: {
    display_name: string;
    headline: string;
    bio: string;
    greeting: string;
    location: string | null;
    avatar_url: string | null;
    links: Array<{ label: string; url: string }>;
  };
  repositories: PublicRepository[];
  suggested_questions: string[];
  character: {
    mode: "builtin" | "custom";
    asset_url: string;
    revision: number;
    frame_duration_ms: number;
    movement: CharacterMovement;
    scene?: PublicScene;
  };
  index: { version: string; built_at: string; repository_count: number };
}

export interface PublicStatus {
  chat_available: boolean;
  bundle_mismatch?: boolean;
}

export interface PublicFaq {
  bundle_id: string;
  locale: Locale;
  entries: Array<{
    question: string;
    variants: string[];
    answer_markdown: string;
    citations: Citation[];
  }>;
}

export interface VisitorPageProps {
  locale: Locale;
  onLocaleChange: (locale: Locale) => void;
  profile: PublicProfile | null;
  profileError: boolean;
  onRetryProfile: () => void;
  chatAvailable: boolean;
  offlineFaqAvailable?: boolean;
  pending: boolean;
  onRecheckStatus: () => void;
  characterState: CharacterState;
  reducedMotion: boolean;
  turns: VisitorTurn[];
  onRetry: (question: string) => void;
  question: string;
  onQuestionChange: (question: string) => void;
  onSubmit: () => void;
  onCancel?: () => void;
  suggestions: string[];
  canAskSuggestion: (question: string) => boolean;
  onSelectSuggestion: (question: string) => void;
  profileErrorRef?: RefObject<HTMLParagraphElement | null>;
  chatStatusRef?: RefObject<HTMLParagraphElement | null>;
  questionInputRef?: RefObject<HTMLTextAreaElement | null>;
  mode?: "visitor" | "preview";
  previewMode?: "light" | "dark";
  sceneOverride?: PublicScene | null;
  sampleConversation?: boolean;
  previewKeepHero?: boolean;
  showFocusFrame?: boolean;
  sampleContent?: boolean;
}

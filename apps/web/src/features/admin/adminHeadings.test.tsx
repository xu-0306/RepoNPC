import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";

import { AdminWorkspace } from "./AdminWorkspace";
import { CharacterAssetConverter } from "./CharacterAssetConverter";
import { GuidedOnboardingView } from "./GuidedOnboardingView";
import { LocalPublishingWorkspace } from "./LocalPublishingWorkspace";
import { MaintenancePanel } from "./MaintenancePanel";
import {
  initialGuidedOnboardingState,
  type GuidedRepository,
} from "./guidedOnboarding";

const contribution = {
  role: { "zh-TW": "測試角色", en: "Fixture role" },
  summary: { "zh-TW": "測試貢獻", en: "Fixture contribution" },
  claims: [],
};
const repository: GuidedRepository = {
  metadata: {
    slug: "fixture/project",
    name: "project",
    description: null,
    primary_language: null,
    default_branch: "main",
    is_fork: false,
    is_archived: false,
    updated_at: null,
    html_url: "https://github.com/fixture/project",
  },
  ref: null,
  include: [],
  exclude: [],
  selected: true,
  confirmedSelectionFingerprint: null,
  analysisStatus: "idle",
  analysis: null,
  ownerStatement: "Fixture statement",
  proposal: contribution,
  previousContribution: null,
  confirmedContribution: { ...contribution, evidence_class: "OWNER_ASSERTION" },
};

it.each(["zh-TW", "en"] as const)(
  "gives every admin screen one page-purpose h1, nonempty headings and no skipped levels in %s",
  (locale) => {
    const views: ReactNode[] = [
      ...(
        [
          "intro",
          "models",
          "repositories",
          "analysis",
          "contributions",
          "profile",
          "review",
          "draft",
        ] as const
      ).map((step) => (
        <GuidedOnboardingView
          key={step}
          locale={locale}
          state={{
            ...initialGuidedOnboardingState(),
            step,
            repositories: [repository],
          }}
          busy={false}
          errorCode=""
          draft=""
          validation={null}
          onAction={vi.fn()}
          onDiscover={vi.fn()}
          onResolve={vi.fn()}
          onAnalyze={vi.fn()}
          onSuggestContribution={vi.fn()}
          onCreateDraft={vi.fn()}
          onCopyDraft={vi.fn()}
          onDownloadDraft={vi.fn()}
          onOpenPublication={vi.fn()}
          analysisSelection={null}
          analysisSelectionPending={false}
          onRefreshAnalysisSelection={vi.fn()}
        />
      )),
      <CharacterAssetConverter
        locale={locale}
        onConvert={vi.fn()}
        onValidate={vi.fn()}
      />,
      <MaintenancePanel
        locale={locale}
        status={{
          active_bundle_id: "fixture-current",
          previous_bundle_id: "fixture-previous",
          pinned_bundle_id: null,
          last_backup_at: null,
          local_ready: true,
          gateway_configured: true,
          externally_verified: false,
        }}
        pending={false}
        restorePreview={null}
        onRefresh={vi.fn()}
        onBackup={vi.fn()}
        onInspect={vi.fn()}
        onRestore={vi.fn()}
        onCancelRestore={vi.fn()}
        onPinPrevious={vi.fn()}
        onStopGateway={vi.fn()}
      />,
      <LocalPublishingWorkspace
        locale={locale}
        content="schema_version: 1"
        spriteBase64={null}
        revision={null}
        initialAccount="fixture"
        selection={null}
        request={async <T,>() => ({}) as T}
        onStored={vi.fn()}
        onCreateDraft={vi.fn()}
        repositories={[]}
        onAddClaim={vi.fn()}
      />,
      null,
    ];
    for (const view of views) {
      const markup = renderToStaticMarkup(
        <AdminWorkspace
          locale={locale}
          draft=""
          validation={null}
          preview={null}
          status={null}
          snippet={null}
          busy={false}
          authenticated
          notice=""
          onDraftChange={vi.fn()}
          onValidate={vi.fn()}
          onPreview={vi.fn()}
          onCopy={vi.fn()}
          onLogout={vi.fn()}
          workspaceMode={view ? "guided" : "advanced"}
          guidedView={view}
        />,
      );
      const h1s = [...markup.matchAll(/<h1\b[^>]*>([\s\S]*?)<\/h1>/g)];
      expect(h1s).toHaveLength(1);
      expect(h1s[0][1]).not.toBe("RepoNPC");
      let previousLevel = 0;
      for (const heading of markup.matchAll(
        /<h([1-6])\b[^>]*>([\s\S]*?)<\/h\1>/g,
      )) {
        expect(heading[2].replace(/<[^>]*>/g, "").trim()).not.toBe("");
        const level = Number(heading[1]);
        expect(level).toBeLessThanOrEqual(previousLevel + 1);
        previousLevel = level;
      }
      const disclosures: boolean[] = [];
      let previousAccessibleLevel = 0;
      for (const token of markup.matchAll(
        /<details\b[^>]*>|<\/details>|<h([1-6])\b[^>]*>[\s\S]*?<\/h\1>/g,
      )) {
        if (token[0].startsWith("<details")) {
          disclosures.push(/\sopen=""/.test(token[0]));
        } else if (token[0] === "</details>") {
          disclosures.pop();
        } else if (disclosures.every(Boolean)) {
          const level = Number(token[1]);
          expect(level).toBeLessThanOrEqual(previousAccessibleLevel + 1);
          previousAccessibleLevel = level;
        }
      }
      if (markup.includes('id="admin-character-converter-heading"')) {
        expect(markup).toContain(
          `<h2>${locale === "en" ? "Animation preview" : "動畫預覽"}</h2>`,
        );
      }
      if (markup.includes('id="admin-maintenance-heading"')) {
        expect(markup).toMatch(
          new RegExp(
            `<h2\\b[^>]*>${locale === "en" ? "Service status" : "服務狀態"}</h2>`,
          ),
        );
      }
    }
  },
);

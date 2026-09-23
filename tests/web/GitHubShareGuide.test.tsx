import { renderToStaticMarkup } from "../../apps/web/node_modules/react-dom/server";
import { createElement } from "../../apps/web/node_modules/react";
import { describe, expect, it, vi } from "vitest";

import {
  GitHubShareGuide,
  type GitHubShareGuideProps,
} from "../../apps/web/src/features/admin/GitHubShareGuide";

function props(
  overrides: Partial<GitHubShareGuideProps> = {},
): GitHubShareGuideProps {
  return {
    locale: "en",
    account: "octo-lab",
    publicUrl: "https://npc.example.test/visitor",
    profileStatus: "ready",
    imageStatus: "ready",
    repositoryUrl: "https://github.com/octo-lab/octo-lab",
    profileUrl: "https://github.com/octo-lab",
    readmeUrl: "https://github.com/octo-lab/octo-lab#readme",
    createUrl: "https://github.com/new",
    filename: "reponpc-card.gif",
    markdown:
      "[![RepoNPC](reponpc-card.gif)](https://npc.example.test/visitor)",
    cardReady: true,
    busy: false,
    notice: "",
    onAccountChange: vi.fn(),
    onPublicUrlChange: vi.fn(),
    onCheckProfile: vi.fn(),
    onCheckImage: vi.fn(),
    onDownload: vi.fn(),
    onCopy: vi.fn(),
    ...overrides,
  };
}

function renderGuide(overrides: Partial<GitHubShareGuideProps> = {}) {
  return renderToStaticMarkup(
    createElement(GitHubShareGuide, props(overrides)),
  );
}

function stageDetails(markup: string, stage: string) {
  return (
    markup.match(
      new RegExp(
        `<section[^>]*data-stage="${stage}"[^>]*>\\s*(<details[^>]*>)`,
      ),
    )?.[1] ?? ""
  );
}

describe("GitHubShareGuide", () => {
  it("renders the three semantic sharing stages with dynamic links and values", () => {
    const markup = renderGuide();

    expect(markup).toContain('data-testid="github-share-guide"');
    expect(markup).toContain('data-stage="profile"');
    expect(markup).toContain('data-stage="card"');
    expect(markup).toContain('data-stage="readme"');
    expect(markup).toContain("octo-lab");
    expect(markup).toContain("reponpc-card.gif");
    expect(markup).toContain("https://npc.example.test/visitor");
    expect(markup).toContain("Add file → Upload files");
    expect(markup).toContain("Preview");
    expect(markup).toContain("keep your existing introduction");
    expect(markup).toContain('target="_blank"');
    expect(markup).toContain('rel="noopener noreferrer"');
    expect(markup).toContain('aria-labelledby="github-share-profile-heading"');
    expect(markup).toContain('aria-labelledby="github-share-card-heading"');
    expect(markup).toContain('aria-labelledby="github-share-readme-heading"');
    expect(markup.match(/<summary/g)).toHaveLength(3);
    expect(markup).toContain("octo-lab/octo-lab");
    expect(markup).toContain("You do not need a separate card repository.");
    expect(markup).not.toContain("localStorage");
    expect(markup).not.toContain("fetch(");
  });

  it("opens only the next relevant stage while keeping all summaries expandable", () => {
    const scenarios = [
      {
        overrides: {
          profileStatus: "unchecked" as const,
          imageStatus: "unchecked" as const,
        },
        openStage: "profile",
      },
      {
        overrides: {
          profileStatus: "ready" as const,
          imageStatus: "missing" as const,
        },
        openStage: "card",
      },
      {
        overrides: {
          profileStatus: "ready" as const,
          imageStatus: "ready" as const,
        },
        openStage: "readme",
      },
    ];

    for (const { overrides, openStage } of scenarios) {
      const markup = renderGuide(overrides);

      for (const stage of ["profile", "card", "readme"]) {
        const details = stageDetails(markup, stage);
        expect(details).toContain("<details");
        if (stage === openStage) {
          expect(details).toContain('open=""');
        } else {
          expect(details).not.toContain("open=");
        }
      }
    }
  });

  it("keeps Traditional Chinese materially equivalent and preserves unknown states honestly", () => {
    const markup = renderGuide({
      locale: "zh-TW",
      account: "another-owner",
      publicUrl: "",
      profileStatus: "unavailable",
      imageStatus: "unchecked",
      repositoryUrl: null,
      profileUrl: null,
      readmeUrl: null,
      createUrl: null,
      markdown: "",
    });

    expect(markup).toContain("another-owner");
    expect(markup).toContain("尚未檢查");
    expect(markup).toContain("目前無法查證同名 repository");
    expect(markup).toContain("還沒有可用的公開訪客連結");
    expect(markup).toContain("不會替你修改 GitHub");
    expect(markup).toContain("保留原有介紹");
    expect(markup).toContain("不必另外建立卡片專用 repository");
    expect(markup).not.toContain("xu-0306");
    expect(markup).not.toContain(
      "已找到同名公開 repository 和根目錄 README.md。下一步請下載並上傳卡片。",
    );
  });

  it("disables download without a ready card and copy without Markdown", () => {
    const markup = renderGuide({ cardReady: false, markdown: "" });

    expect(markup).toMatch(
      /<button[^>]*disabled=""[^>]*>Download card<\/button>/,
    );
    expect(markup).toMatch(
      /<button[^>]*disabled=""[^>]*>Copy text for README<\/button>/,
    );
    expect(markup).toContain(
      "Select Preview portfolio and card above to generate the image before downloading.",
    );
    expect(markup).toContain("Nothing is ready to copy yet.");
  });

  it("uses generated Markdown readiness instead of trusting a nonempty URL", () => {
    const markup = renderGuide({
      publicUrl: "https://not-validated.example.test/visitor",
      markdown: "",
    });

    expect(markup).toContain("No public visitor link is ready yet.");
    expect(markup).not.toContain("The URL format passed validation.");
  });

  it("disables every interactive mutation while busy", () => {
    const markup = renderGuide({ busy: true });

    expect(markup).toMatch(
      /<input[^>]*(?:id="github-share-account"[^>]*disabled=""|disabled=""[^>]*id="github-share-account")/,
    );
    expect(markup).toMatch(
      /<input[^>]*(?:id="github-share-public-url"[^>]*disabled=""|disabled=""[^>]*id="github-share-public-url")/,
    );
    expect(markup).toMatch(
      /<button[^>]*disabled=""[^>]*>Check matching repository<\/button>/,
    );
    expect(markup).toMatch(
      /<button[^>]*disabled=""[^>]*>Download card<\/button>/,
    );
    expect(markup).toMatch(
      /<button[^>]*disabled=""[^>]*>Check whether the image is uploaded<\/button>/,
    );
    expect(markup).toMatch(
      /<button[^>]*disabled=""[^>]*>Copy text for README<\/button>/,
    );
    expect(markup).toContain("Working…");
  });

  it("shows creation guidance without assuming a branch or successful publication", () => {
    const markup = renderGuide({
      account: "profile-user",
      profileStatus: "missing",
      imageStatus: "missing",
      repositoryUrl: null,
      profileUrl: null,
      readmeUrl: null,
    });

    expect(markup).toContain("Repository name:");
    expect(markup).toContain("profile-user");
    expect(markup).toContain("Public");
    expect(markup).toContain("Add a README file");
    expect(markup).toContain("Create repository");
    expect(markup).toContain("default branch");
    expect(markup).not.toContain("main branch");
    expect(markup).not.toContain("published successfully");
  });

  it("keeps the GitHub account page separate from a missing profile repository", () => {
    const markup = renderGuide({
      locale: "zh-TW",
      account: "xu-0306",
      profileStatus: "missing",
      imageStatus: "unchecked",
      readmeUrl: "https://github.com/xu-0306/xu-0306",
      repositoryUrl: "https://github.com/xu-0306/xu-0306",
      profileUrl: "https://github.com/xu-0306",
    });

    expect(markup).toContain("xu-0306/xu-0306");
    expect(markup).toContain("這不表示 GitHub 帳號不存在");
    expect(markup).toContain("查看 GitHub 帳號頁");
    expect(markup).not.toContain("編輯 README.md</a>");
  });
});

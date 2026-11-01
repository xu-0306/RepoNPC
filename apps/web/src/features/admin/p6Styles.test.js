import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (name) =>
  readFileSync(new URL(`../../${name}`, import.meta.url), "utf8");
const guided = source("features/admin/GuidedOnboardingView.tsx");
const workspace = source("features/admin/AdminWorkspace.tsx");
const pixel = source("pixel.css");
const w1 = source("p4-w1.css");
const w2 = source("p4-w2.css");
const w3 = source("p4-w3.css");
const w4 = source("p4-w4.css");
const styles = source("styles.css");
const localPublishing = source("features/admin/LocalPublishingWorkspace.tsx");
const pagesShare = source("features/admin/PagesSharePanel.tsx");
const githubShare = source("features/admin/GitHubShareGuide.tsx");

describe("P6 pixel UI contracts", () => {
  it("uses one shared info disclosure primitive", () => {
    expect(pixel).toMatch(/\.px-info > summary\s*\{[\s\S]*list-style:\s*none/);
    expect(pixel).toContain(".px-info > summary::-webkit-details-marker");
    expect(pixel).toMatch(/\.px-info > summary\s*\{[\s\S]*min-height:\s*44px/);
    expect(pixel).toMatch(
      /\.px-info > summary:focus-visible\s*\{[\s\S]*outline:/,
    );
    expect(w1).not.toContain(
      "p4-w1-repository__details > summary::-webkit-details-marker",
    );
    expect(w2).not.toContain(
      "p4-w2__confirm .p4-w2__info > summary::-webkit-details-marker",
    );
  });

  it("keeps the guided header bilingual and the inner headings compact", () => {
    expect(styles).toMatch(
      /\.guided-onboarding > \.guided-onboarding__header\s*\{[\s\S]*grid-template-columns:\s*minmax\(0, 1fr\)/,
    );
    expect(styles).toMatch(
      /#guided-onboarding-heading\s*\{[\s\S]*font-size:\s*clamp\(20px/,
    );
    expect(w2).toMatch(
      /\.guided-onboarding \.guided-onboarding__step :is\(h1, h2, h3, h4, h5, h6\)\s*\{[\s\S]*font-size:\s*18px/,
    );
    for (const id of [
      "guided-intro-heading",
      "guided-repositories-heading",
      "guided-analysis-heading",
      "guided-contributions-heading",
      "guided-profile-heading",
      "guided-review-heading",
      "guided-draft-heading",
    ])
      expect(guided).toContain(`id="${id}"`);
  });

  it("keeps both visitor chat summary targets at least 24 CSS pixels high", () => {
    const visitor = source("visitor.css");
    expect(visitor).toMatch(
      /\.visitor-page \.citations > summary,\s*\.visitor-page \.chat-process__details > summary\s*\{[^}]*min-block-size:\s*24px;/,
    );
  });

  it("styles the maintenance groups", () => {
    expect(w4).toMatch(
      /\.admin-maintenance__status,[\s\S]*\.admin-maintenance__data\s*\{/,
    );
    // `.admin-maintenance h2` adds a dashed top border and 24px margin; the
    // group title must out-rank it or each group shows two dashed lines.
    expect(w4).toMatch(
      /\.admin-maintenance \.admin-maintenance__group-title\s*\{[^}]*border:\s*0/,
    );
  });

  it("keeps publish steps as chips and the impact statement visible", () => {
    expect(w3).toMatch(/\.local-publication__heading nav a\.px-chip\s*\{/);
    expect(w3).toMatch(
      /\.local-publication__heading nav a\.px-chip\[aria-current="step"\]/,
    );
    expect(w3).toContain(".publication-status");
    expect(w3).toContain(".publication-current-version.px-button");
    expect(localPublishing).toContain('className="publication-impact"');
    expect(pagesShare).toContain('className="publication-link"');
    expect(githubShare).toContain('className="publication-link"');
  });

  it("keeps the owner header compact at tablet widths", () => {
    expect(styles).toContain("@media (max-width: 1100px)");
    expect(styles).toContain(
      ".admin-workspace__utilities .admin-workspace__utility-label",
    );
    expect(workspace).toContain("aria-label={copy.administrator}");
    expect(styles).toMatch(
      /\.admin-workspace__owner\s*\{[\s\S]*min-height:\s*44px/,
    );
    // Below 900px the decorative scene gives its column to the utilities so
    // the log-out button never sits alone on a second row.
    expect(styles).toMatch(
      /@media \(max-width: 900px\) \{\s*\.admin-workspace__header \{\s*grid-template-columns: minmax\(0, 1fr\) auto;\s*\}\s*\.admin-workspace__scene \{\s*display: none;/,
    );
  });
});

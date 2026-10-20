import { describe, expect, it } from "vitest";
import {
  githubAccount,
  safeShareFields,
  verifiedPagesMarkdown,
} from "./sharing";

describe("GitHub sharing values", () => {
  it("uses the supplied account", () => {
    expect(githubAccount("another-owner")).toBe("another-owner");
    expect(githubAccount("owner/repo")).toBeNull();
  });

  it("normalizes an exact GitHub profile URL without accepting a repository path", () => {
    expect(githubAccount(" https://github.com/another-owner/ ")).toBe(
      "another-owner",
    );
    expect(githubAccount("https://GITHUB.COM/another-owner")).toBe(
      "another-owner",
    );
    expect(githubAccount("https://github.com/another-owner/repo")).toBeNull();
    expect(githubAccount("https://github.com:443/another-owner")).toBeNull();
  });

  it("returns only normalized public fields for session continuity", () => {
    expect(safeShareFields("https://github.com/another-owner")).toEqual({
      account: "another-owner",
    });
    expect(safeShareFields("owner/repo")).toEqual({});
  });

  it("targets only a normalized github.io path for a verified Pages README card", () => {
    expect(verifiedPagesMarkdown("https://owner.github.io/", "en")).toBe(
      "[![Chat with my RepoNPC](./reponpc-card.gif)](<https://owner.github.io/>)",
    );
    expect(verifiedPagesMarkdown("https://owner.github.io/", "zh-TW")).toBe(
      "[![與我的 RepoNPC 對話](./reponpc-card.gif)](<https://owner.github.io/>)",
    );
    expect(
      verifiedPagesMarkdown("https://owner.github.io/project/", "en"),
    ).toBe(
      "[![Chat with my RepoNPC](./reponpc-card.gif)](<https://owner.github.io/project/>)",
    );
    expect(verifiedPagesMarkdown("https://example.com/project/", "en")).toBe(
      "",
    );
    expect(
      verifiedPagesMarkdown("https://owner.github.io/project/%2e%2e/", "en"),
    ).toBe("");
  });
});

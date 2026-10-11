import { describe, expect, it } from "vitest";
import {
  cardMarkdown,
  githubAccount,
  publicVisitorUrl,
  safeShareFields,
  verifiedPagesMarkdown,
} from "./sharing";

describe("GitHub sharing values", () => {
  it("uses the supplied account and actual public target", () => {
    expect(githubAccount("another-owner")).toBe("another-owner");
    expect(githubAccount("owner/repo")).toBeNull();
    expect(cardMarkdown("https://portfolio.example.org/?locale=en", "en")).toBe(
      "[![Chat with my RepoNPC](./reponpc-card.gif)](<https://portfolio.example.org/?locale=en>)",
    );
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
    expect(
      safeShareFields(
        "https://github.com/another-owner",
        "https://portfolio.example.org/visitor",
      ),
    ).toEqual({
      account: "another-owner",
      publicUrl: "https://portfolio.example.org/visitor",
    });
    expect(
      safeShareFields("owner/repo", "https://user:secret@example.org"),
    ).toEqual({});
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

  it.each([
    "http://localhost:8090",
    "https://localhost:8090",
    "https://127.0.0.1",
    "https://2130706433",
    "https://192.168.0.2",
    "https://172.16.1.2",
    "https://10.0.0.2",
    "https://box.local",
    "https://user:password@example.org",
    "javascript:alert(1)",
    "https://example.org/#secret",
    "",
  ])("does not create a chat link for %s", (value) => {
    expect(publicVisitorUrl(value)).toBeNull();
    expect(cardMarkdown(value, "zh-TW")).toBe("");
  });
});

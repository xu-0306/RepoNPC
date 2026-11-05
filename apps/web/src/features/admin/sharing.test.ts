import { describe, expect, it } from "vitest";
import {
  githubAccount,
  githubPagesRepository,
  pagesUrlOrigin,
  safeShareFields,
  verifiedPagesMarkdown,
} from "./sharing";

describe("pages URL origin", () => {
  it("takes the origin of a project site and of a root site", () => {
    expect(pagesUrlOrigin("https://account.github.io/project/")).toBe(
      "https://account.github.io",
    );
    expect(pagesUrlOrigin("https://account.github.io/")).toBe(
      "https://account.github.io",
    );
    expect(pagesUrlOrigin("https://another-owner.github.io/a/b/")).toBe(
      "https://another-owner.github.io",
    );
  });

  it("returns null for empty, malformed and non-HTTPS values", () => {
    expect(pagesUrlOrigin(null)).toBeNull();
    expect(pagesUrlOrigin(undefined)).toBeNull();
    expect(pagesUrlOrigin("")).toBeNull();
    expect(pagesUrlOrigin("not a url")).toBeNull();
    expect(pagesUrlOrigin("http://account.github.io/project/")).toBeNull();
  });
});

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

it.each([
  [
    "another-owner",
    "https://another-owner.github.io/project/",
    "https://github.com/another-owner/project",
  ],
  [
    "OctoCat",
    "https://octocat.github.io/",
    "https://github.com/OctoCat/OctoCat.github.io",
  ],
  ["", "https://owner.github.io/project/", null],
  ["owner", "https://other.github.io/project/", null],
  ["owner", "https://owner.github.io/path/nested/", null],
  ["owner", "https://owner.github.io/project/?token=secret", null],
  ["owner", "https://example.test/project/", null],
  ["owner/private", "https://owner.github.io/", null],
])(
  "maps only the public account's usable Pages repository: %s %s",
  (account, url, expected) => {
    expect(githubPagesRepository(account!, url!)).toBe(expected);
  },
);

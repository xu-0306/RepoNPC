import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchPublicFaq,
  fetchPublicProfile,
  fetchPublicStatus,
  staticChatGateway,
} from "./visitorData";

afterEach(() => vi.unstubAllGlobals());

const locale = "en" as const;
const gatewayOrigin = "https://fixture.ts.net";

function faqJson() {
  return JSON.stringify({
    bundle_id: "fixture-bundle",
    locale,
    entries: [
      {
        question: "Which project stands out?",
        variants: [],
        answer_markdown: "Approved answer",
        citations: [],
      },
    ],
  });
}

async function staticManifest(files: Record<string, string>) {
  const records = await Promise.all(
    Object.entries(files)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(async ([path, content]) => ({
        path,
        size: new TextEncoder().encode(content).byteLength,
        sha256: await digest(content),
      })),
  );
  const identity = JSON.stringify(
    records.map(({ path, size, sha256 }) => ({ path, sha256, size })),
  );
  return JSON.stringify({
    schema_version: 1,
    bundle_id: "fixture-bundle",
    character_revision: 0,
    pages_url: "https://fixture.github.io/portfolio/",
    base_path: "/portfolio/",
    pages_origin: "https://fixture.github.io",
    gateway_origin: gatewayOrigin,
    content_sha256: await digest(identity),
    files: records,
  });
}

async function digest(value: string): Promise<string> {
  const bytes = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return Array.from(new Uint8Array(bytes), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

function enableStaticExport() {
  vi.stubGlobal("document", {
    documentElement: { dataset: { staticExport: "true" } },
    querySelector: () => ({
      getAttribute: () =>
        `default-src 'none'; connect-src 'self' ${gatewayOrigin}; img-src 'self'`,
    }),
  });
}

function urlOf(input: RequestInfo | URL): string {
  return input instanceof Request ? input.url : String(input);
}

function profileValue() {
  const tokens = Object.fromEntries(
    [
      "background",
      "surface",
      "surface_alt",
      "ink",
      "muted_ink",
      "accent",
      "accent_ink",
      "border",
      "stage",
      "focus",
      "sky",
      "horizon",
      "hill_far",
      "hill_near",
      "grass",
      "ground",
      "wood",
      "celestial",
    ].map((key) => [key, "#111111"]),
  );
  return {
    schema_version: 1,
    locale,
    profile: {
      display_name: "Fixture",
      headline: "Fixture headline",
      bio: "Fixture biography",
      greeting: "Welcome",
      location: null,
      avatar_url: null,
      links: [],
    },
    character: {
      mode: "builtin",
      asset_url: "/api/public/character.png",
      revision: 0,
      frame_duration_ms: 160,
      movement: "subtle",
      scene: {
        revision: 0,
        scheme: { id: "fixture_scheme", version: 1 },
        color_mode: "system",
        visitor_mode_toggle: true,
        visitor_scheme_choice: true,
        themes: { light: { ...tokens }, dark: { ...tokens } },
        npc_plate: { light: false, dark: true },
        schemes: [
          {
            id: "fixture_scheme",
            version: 1,
            label: { "zh-TW": "測試", en: "Fixture" },
            themes: { light: { ...tokens }, dark: { ...tokens } },
            npc_plate: { light: false, dark: true },
          },
        ],
        background_url: null,
        background_focus: { x: 50, y: 50 },
        background_scaling: "smooth",
        background_dim: "none",
      },
    },
    index: {
      version: "fixture-bundle",
      built_at: "2026-09-29T00:00:00Z",
      repository_count: 1,
    },
    repositories: [
      {
        slug: "fixture/project",
        summary: "Fixture summary",
        role: "Fixture role",
        tags: ["TypeScript"],
        demo_url: null,
        language: null,
        stars: null,
        forks: null,
      },
    ],
    suggested_questions: ["Which project stands out?"],
  };
}

describe("static visitor data verification", () => {
  it.each(["/", "/portfolio/"])(
    "preserves owner statement links online and offline under %s",
    async (basePath) => {
      enableStaticExport();
      const revision = "a".repeat(40);
      const evidenceId = "E_" + "b".repeat(24);
      const path = `owner-statements/${revision}/${evidenceId}.txt`;
      const payload = JSON.parse(faqJson());
      payload.entries[0].citations = [
        {
          id: "S1",
          evidence_class: "OWNER_ASSERTION",
          evidence_id: evidenceId,
          repository: "local/portfolio",
          commit_sha: revision,
          path: "portfolio.yml",
          start_line: 1,
          end_line: 1,
          title: "Owner statement",
          excerpt: "Reviewed statement",
          url: `/api/public/owner-statements/${revision}/${evidenceId}`,
        },
      ];
      let networkDown = false;
      let copied = true;
      const send = vi.fn(async (input: RequestInfo | URL) => {
        if (urlOf(input) === "./export-manifest.json") {
          const manifest = JSON.parse(
            await staticManifest(
              copied ? { [path]: "Reviewed statement" } : {},
            ),
          );
          manifest.base_path = basePath;
          manifest.pages_url = manifest.pages_origin + basePath;
          return new Response(JSON.stringify(manifest));
        }
        expect(urlOf(input)).toBe(`${gatewayOrigin}/api/public/faq?locale=en`);
        if (networkDown) throw new TypeError("offline");
        return new Response(JSON.stringify(payload));
      });
      const signal = new AbortController().signal;
      const local = await fetchPublicFaq(locale, signal, send);
      expect(local?.entries[0].citations[0].url).toBe(`./${path}`);
      networkDown = true;
      expect(await fetchPublicFaq(locale, signal, send, local)).toEqual(local);
      copied = false;
      networkDown = false;
      const remote = await fetchPublicFaq(locale, signal, send);
      expect(remote?.entries[0].citations[0].url).toBe(
        gatewayOrigin + payload.entries[0].citations[0].url,
      );
      networkDown = true;
      expect(
        (await fetchPublicFaq(locale, signal, send, remote))?.entries,
      ).toEqual([]);
    },
  );

  it.each([
    "javascript:alert(1)",
    "/api/admin/private",
    "/api/public/owner-statements/" + "c".repeat(40) + "/E_" + "b".repeat(24),
  ])("rejects unsafe or mismatched owner citation %s", async (url) => {
    const payload = JSON.parse(faqJson());
    payload.entries[0].citations = [
      {
        id: "S1",
        evidence_class: "OWNER_ASSERTION",
        evidence_id: "E_" + "b".repeat(24),
        repository: "local/portfolio",
        commit_sha: "a".repeat(40),
        path: "portfolio.yml",
        start_line: 1,
        end_line: 1,
        title: "Owner statement",
        excerpt: "Reviewed statement",
        url,
      },
    ];
    expect(
      await fetchPublicFaq(
        locale,
        new AbortController().signal,
        vi.fn(async () => new Response(JSON.stringify(payload))),
      ),
    ).toBeNull();
  });

  it.each([
    ["character.asset_url", "/api/admin/assets/private.png"],
    ["character.scene.themes.light.ink", 'url("https://attacker.example/")'],
    ["character.scene.themes.light.extra", "#111111"],
    ["character.scene.background_url", "/api/admin/assets/background.png"],
    ["character.scene.background_focus.x", 101],
    ["character.scene.revision", 1],
    ["character.scene.visitor_scheme_choice", "false"],
    ["character.scene.npc_plate.light", 1],
    ["character.scene.schemes", []],
    ["character.scene.schemes.0.id", "unknown_default"],
    ["character.scene.schemes.0.label.en", ""],
    ["character.scene.schemes.0.npc_plate.dark", "true"],
    ["character.scene.schemes.0.themes.dark.sky", "url(attacker)"],
    ["character.scene.schemes.0.themes.light.unknown", "#111111"],
    ["repositories.0.tags", [true]],
    ["repositories.0.stars", true],
    ["repositories.0.forks", -1],
    ["profile.links", [{ label: "Unsafe", url: "javascript:alert(1)" }]],
    ["profile.display_name", "x".repeat(81)],
    ["index.repository_count", 2],
  ])(
    "rejects untrusted profile shape or value at %s",
    async (path, invalid) => {
      const payload = profileValue();
      const parts = String(path).split(".");
      const field = parts.pop()!;
      let target = payload as Record<string, unknown>;
      for (const part of parts)
        target = target[part] as Record<string, unknown>;
      target[field] = invalid;
      const send = vi.fn(async () => new Response(JSON.stringify(payload)));
      await expect(
        fetchPublicProfile(locale, new AbortController().signal, send),
      ).rejects.toThrow("profile invalid");
    },
  );

  it("keeps validated GitHub owner citations immutable in online and offline FAQ", async () => {
    enableStaticExport();
    const localRevision = "a".repeat(40);
    const localEvidenceId = "E_" + "a".repeat(24);
    const githubRevision = "b".repeat(40);
    const githubEvidenceId = "E_" + "b".repeat(24);
    const githubUrl = `https://github.com/sample-owner/sample-repo/blob/${githubRevision}/reponpc.yml#L2-L3`;
    const payload = JSON.parse(faqJson());
    payload.entries[0].citations = [
      {
        id: "S1",
        evidence_class: "OWNER_ASSERTION",
        evidence_id: githubEvidenceId,
        repository: "sample-owner/sample-repo",
        commit_sha: githubRevision,
        path: "reponpc.yml",
        start_line: 2,
        end_line: 3,
        title: "profile_headline",
        excerpt: "Github owner statement",
        url: githubUrl,
      },
      {
        id: "S2",
        evidence_class: "OWNER_ASSERTION",
        evidence_id: localEvidenceId,
        repository: "local/portfolio",
        commit_sha: localRevision,
        path: "reponpc.yml",
        start_line: 2,
        end_line: 3,
        title: "profile_headline",
        excerpt: "Local owner statement",
        url: `/api/public/owner-statements/${localRevision}/${localEvidenceId}`,
      },
      {
        id: "S3",
        evidence_class: "REPOSITORY_FACT",
        evidence_id: "E_" + "c".repeat(24),
        repository: "sample-owner/sample-repo",
        commit_sha: "c".repeat(40),
        path: "src/main.py",
        start_line: 8,
        end_line: 8,
        title: "main",
        excerpt: "print('hello')",
        url: `https://github.com/sample-owner/sample-repo/blob/${"c".repeat(40)}/src/main.py#L8`,
      },
      {
        id: "S4",
        evidence_class: "OWNER_ASSERTION",
        evidence_id: "E_" + "d".repeat(24),
        repository: "local/portfolio",
        commit_sha: "d".repeat(40),
        path: "reponpc.yml",
        start_line: 2,
        end_line: 3,
        title: "profile_headline",
        excerpt: "Github repository named like local source",
        url: `https://github.com/local/portfolio/blob/${"d".repeat(40)}/reponpc.yml#L2-L3`,
      },
    ];
    const exported = JSON.parse(JSON.stringify(payload));
    exported.entries[0].citations[1].url = `./owner-statements/${localRevision}/${localEvidenceId}.txt`;
    const statementPath = `owner-statements/${localRevision}/${localEvidenceId}.txt`;
    const manifest = await staticManifest({
      "faq-en.json": JSON.stringify(exported),
      [statementPath]: "Owner-confirmed statement",
    });
    let networkDown = true;
    const send = vi.fn(async (input: RequestInfo | URL) => {
      const url = urlOf(input);
      if (url === "./export-manifest.json") return new Response(manifest);
      if (url === "./faq-en.json")
        return new Response(JSON.stringify(exported));
      expect(url).toBe(`${gatewayOrigin}/api/public/faq?locale=en`);
      if (networkDown) throw new TypeError("offline");
      return new Response(JSON.stringify(payload));
    });
    const signal = new AbortController().signal;

    const offline = await fetchPublicFaq(locale, signal, send);
    expect(offline?.entries[0].citations.map(({ url }) => url)).toEqual([
      githubUrl,
      `./${statementPath}`,
      payload.entries[0].citations[2].url,
      payload.entries[0].citations[3].url,
    ]);
    networkDown = false;
    const online = await fetchPublicFaq(locale, signal, send);
    expect(online?.entries[0].citations.map(({ url }) => url)).toEqual([
      githubUrl,
      `./${statementPath}`,
      payload.entries[0].citations[2].url,
      payload.entries[0].citations[3].url,
    ]);
    expect(send).toHaveBeenCalledWith(
      `${gatewayOrigin}/api/public/faq?locale=en`,
      expect.objectContaining({ credentials: "omit" }),
    );
  });

  it.each([
    "repository",
    "path",
    "line",
    "revision",
    "source",
    "evidence",
    "duplicate",
  ])("rejects a forged GitHub owner citation %s binding", async (field) => {
    const revision = "a".repeat(40);
    const evidenceId = "E_" + "b".repeat(24);
    const citation: Record<string, unknown> = {
      id: "S1",
      evidence_class: "OWNER_ASSERTION",
      evidence_id: evidenceId,
      repository: "sample-owner/sample-repo",
      commit_sha: revision,
      path: "reponpc.yml",
      start_line: 2,
      end_line: 3,
      title: "profile_headline",
      excerpt: "Owner statement",
      url: `https://github.com/sample-owner/sample-repo/blob/${revision}/reponpc.yml#L2-L3`,
    };
    if (field === "repository") citation.repository = "attacker/repo";
    if (field === "path") citation.path = "attacker.yml";
    if (field === "line") citation.start_line = 1;
    if (field === "revision") citation.commit_sha = "c".repeat(40);
    if (field === "source") citation.id = "C1";
    if (field === "evidence") citation.evidence_id = "forged";
    const payload = JSON.parse(faqJson());
    if (field === "duplicate") {
      const secondRevision = "c".repeat(40);
      payload.entries[0].citations = [
        citation,
        {
          ...citation,
          evidence_id: "E_" + "c".repeat(24),
          repository: "other-owner/other-repo",
          commit_sha: secondRevision,
          url: `https://github.com/other-owner/other-repo/blob/${secondRevision}/reponpc.yml#L2-L3`,
        },
      ];
    } else {
      payload.entries[0].citations = [citation];
    }
    const send = vi.fn(async () => new Response(JSON.stringify(payload)));

    await expect(
      fetchPublicFaq(locale, new AbortController().signal, send),
    ).resolves.toBeNull();
  });

  it("accepts legacy profile metadata without a scene or statistics", async () => {
    const payload = profileValue();
    const legacyCharacter = { ...payload.character, scene: undefined };
    const legacyRepository = {
      ...payload.repositories[0],
      language: undefined,
      stars: undefined,
      forks: undefined,
    };
    const send = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            ...payload,
            character: legacyCharacter,
            repositories: [legacyRepository],
          }),
        ),
    );
    await expect(
      fetchPublicProfile(locale, new AbortController().signal, send),
    ).resolves.toMatchObject({ character: { revision: 0 } });
  });

  it("accepts hash-bound static profile with only canonical local character URL", async () => {
    enableStaticExport();
    const payload = profileValue();
    payload.character.asset_url = "./character.png";
    const profile = JSON.stringify(payload);
    const manifest = await staticManifest({
      "profile-en.json": profile,
      "character.png": "",
    });
    const send = vi.fn(async (input: RequestInfo | URL) => {
      const url = urlOf(input);
      if (url === "./export-manifest.json") return new Response(manifest);
      if (url === "./profile-en.json") return new Response(profile);
      throw new Error("unexpected request");
    });
    await expect(
      fetchPublicProfile(locale, new AbortController().signal, send),
    ).resolves.toMatchObject({ character: { asset_url: "./character.png" } });
  });

  it.each(["rejected", "withdrawn", "changed"])(
    "does not resurrect exported answers after %s then network loss",
    async (mode) => {
      enableStaticExport();
      const localFaq = faqJson();
      const manifest = await staticManifest({ "faq-en.json": localFaq });
      const live = JSON.parse(localFaq);
      if (mode === "withdrawn") live.entries = [];
      if (mode === "changed")
        live.entries[0].answer_markdown = "New reviewed answer";
      let networkDown = false;
      let fallbackReads = 0;
      const send = vi.fn(
        async (input: RequestInfo | URL, options?: RequestInit) => {
          const url = urlOf(input);
          if (url === "./export-manifest.json") return new Response(manifest);
          if (url === "./faq-en.json") {
            fallbackReads += 1;
            return new Response(localFaq);
          }
          expect(url).toBe(`${gatewayOrigin}/api/public/faq?locale=en`);
          expect(options?.credentials).toBe("omit");
          expect(options?.body).toBeUndefined();
          if (networkDown) throw new TypeError("offline");
          return mode === "rejected"
            ? new Response(null, { status: 503 })
            : new Response(JSON.stringify(live));
        },
      );
      const observed = await fetchPublicFaq(
        locale,
        new AbortController().signal,
        send,
      );
      networkDown = true;
      const fallback = await fetchPublicFaq(
        locale,
        new AbortController().signal,
        send,
        observed,
      );
      expect(fallback).toEqual(observed);
      expect(fallbackReads).toBe(0);
      if (mode === "withdrawn") expect(fallback?.entries).toEqual([]);
      if (mode === "changed")
        expect(fallback?.entries[0].answer_markdown).toBe(
          "New reviewed answer",
        );
    },
  );

  it("uses the integrity-checked FAQ after the gateway read deadline", async () => {
    enableStaticExport();
    vi.useFakeTimers();
    const exportedFaq = faqJson();
    const manifest = await staticManifest({ "faq-en.json": exportedFaq });
    let gatewaySignal: AbortSignal | undefined;
    const send = vi.fn(
      (input: RequestInfo | URL, options?: RequestInit): Promise<Response> => {
        const url = urlOf(input);
        if (url === "./export-manifest.json")
          return Promise.resolve(new Response(manifest));
        if (url === "./faq-en.json")
          return Promise.resolve(new Response(exportedFaq));
        expect(url).toBe(`${gatewayOrigin}/api/public/faq?locale=en`);
        return new Promise((_resolve, reject) => {
          gatewaySignal = options?.signal ?? undefined;
          gatewaySignal?.addEventListener(
            "abort",
            () => reject(gatewaySignal?.reason),
            { once: true },
          );
        });
      },
    );
    const read = fetchPublicFaq(locale, new AbortController().signal, send);

    await vi.waitFor(() => expect(gatewaySignal).toBeDefined());
    await vi.advanceTimersByTimeAsync(10_000);
    await expect(read).resolves.toMatchObject({
      bundle_id: "fixture-bundle",
      entries: [{ answer_markdown: "Approved answer" }],
    });
    expect(gatewaySignal?.aborted).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("does not start a public FAQ request when its parent is already aborted", async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    controller.abort();
    const send = vi.fn(async () => new Response(faqJson()));

    await expect(
      fetchPublicFaq(locale, controller.signal, send),
    ).rejects.toThrow();
    expect(send).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("keeps an authoritative empty FAQ latched after a later timeout", async () => {
    enableStaticExport();
    vi.useFakeTimers();
    const staleExport = faqJson();
    const manifest = await staticManifest({ "faq-en.json": staleExport });
    let gatewaySignal: AbortSignal | undefined;
    let shouldHang = false;
    let fallbackReads = 0;
    const withdrawn = JSON.parse(faqJson());
    withdrawn.entries = [];
    const send = vi.fn(
      (input: RequestInfo | URL, options?: RequestInit): Promise<Response> => {
        const url = urlOf(input);
        if (url === "./export-manifest.json")
          return Promise.resolve(new Response(manifest));
        if (url === "./faq-en.json") {
          fallbackReads += 1;
          return Promise.resolve(new Response(staleExport));
        }
        expect(url).toBe(`${gatewayOrigin}/api/public/faq?locale=en`);
        if (!shouldHang)
          return Promise.resolve(new Response(JSON.stringify(withdrawn)));
        return new Promise((_resolve, reject) => {
          gatewaySignal = options?.signal ?? undefined;
          gatewaySignal?.addEventListener(
            "abort",
            () => reject(gatewaySignal?.reason),
            { once: true },
          );
        });
      },
    );
    const signal = new AbortController().signal;
    const observed = await fetchPublicFaq(locale, signal, send);
    expect(observed?.entries).toEqual([]);
    shouldHang = true;
    const read = fetchPublicFaq(locale, signal, send, observed);

    await vi.waitFor(() => expect(gatewaySignal).toBeDefined());
    await vi.advanceTimersByTimeAsync(10_000);
    await expect(read).resolves.toEqual(observed);
    expect(gatewaySignal?.aborted).toBe(true);
    expect(fallbackReads).toBe(0);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("does not replace an authoritative bundle mismatch with a network-failure result", async () => {
    enableStaticExport();
    const manifest = await staticManifest({ "faq-en.json": faqJson() });
    let networkDown = false;
    const send = vi.fn(async (input: RequestInfo | URL) => {
      if (urlOf(input) === "./export-manifest.json")
        return new Response(manifest);
      if (networkDown) throw new TypeError("offline");
      return new Response(
        JSON.stringify({
          chat_available: true,
          index: { version: "new-bundle" },
        }),
      );
    });
    await expect(
      fetchPublicStatus(new AbortController().signal, send),
    ).resolves.toMatchObject({ bundle_mismatch: true });
    networkDown = true;
    await expect(
      fetchPublicStatus(new AbortController().signal, send),
    ).rejects.toThrow(TypeError);
  });

  it("rejects normalized traversal in Pages URLs before sending gateway requests", async () => {
    enableStaticExport();
    const manifest = JSON.parse(
      await staticManifest({ "faq-en.json": faqJson() }),
    );
    manifest.pages_url = "https://fixture.github.io/hidden/../portfolio/";
    const send = vi.fn(async () => new Response(JSON.stringify(manifest)));
    await expect(
      fetchPublicFaq(locale, new AbortController().signal, send),
    ).rejects.toThrow("static manifest invalid");
    expect(send).toHaveBeenCalledTimes(1);
  });

  it("does not use the exported FAQ after a known gateway HTTP rejection", async () => {
    enableStaticExport();
    const localFaq = faqJson();
    const manifest = await staticManifest({ "faq-en.json": localFaq });
    const send = vi.fn(async (input: RequestInfo | URL) => {
      const url = urlOf(input);
      if (url === "./export-manifest.json") return new Response(manifest);
      if (url === `${gatewayOrigin}/api/public/faq?locale=en`) {
        return new Response("unavailable", { status: 503 });
      }
      if (url === "./faq-en.json") return new Response(localFaq);
      throw new Error(`unexpected request: ${url}`);
    });

    await expect(
      fetchPublicFaq(locale, new AbortController().signal, send),
    ).resolves.toBeNull();
    expect(send).not.toHaveBeenCalledWith("./faq-en.json", expect.anything());
  });

  it("uses only a hash-verified export FAQ after a network failure", async () => {
    enableStaticExport();
    const localFaq = faqJson();
    const manifest = await staticManifest({ "faq-en.json": localFaq });
    const send = vi.fn(async (input: RequestInfo | URL) => {
      const url = urlOf(input);
      if (url === "./export-manifest.json") return new Response(manifest);
      if (url === `${gatewayOrigin}/api/public/faq?locale=en`) {
        throw new TypeError("network unavailable");
      }
      if (url === "./faq-en.json") return new Response(localFaq);
      throw new Error(`unexpected request: ${url}`);
    });

    await expect(
      fetchPublicFaq(locale, new AbortController().signal, send),
    ).resolves.toMatchObject({
      bundle_id: "fixture-bundle",
      entries: [{ answer_markdown: "Approved answer" }],
    });
  });

  it("rejects a static profile whose bytes differ from the export manifest", async () => {
    enableStaticExport();
    const profile = JSON.stringify({
      locale,
      profile: {},
      character: {},
      index: { version: "fixture-bundle" },
      repositories: [],
      suggested_questions: [],
    });
    const manifest = await staticManifest({ "profile-en.json": profile });
    const send = vi.fn(async (input: RequestInfo | URL) => {
      const url = urlOf(input);
      if (url === "./export-manifest.json") return new Response(manifest);
      if (url === "./profile-en.json") return new Response(profile + " ");
      throw new Error(`unexpected request: ${url}`);
    });

    await expect(
      fetchPublicProfile(locale, new AbortController().signal, send),
    ).rejects.toThrow("static file integrity failed");
  });

  it("reports gateway live chat for a matching bundle without sending credentials", async () => {
    enableStaticExport();
    const manifest = await staticManifest({ "faq-en.json": faqJson() });
    const send = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (urlOf(input) === "./export-manifest.json")
        return new Response(manifest);
      expect(urlOf(input)).toBe(`${gatewayOrigin}/api/public/status`);
      expect(init?.credentials).toBe("omit");
      return Response.json({
        chat_available: true,
        index: { version: "fixture-bundle" },
      });
    });
    await expect(
      fetchPublicStatus(new AbortController().signal, send),
    ).resolves.toEqual({ chat_available: true, bundle_mismatch: false });
  });

  it("maps live local owner citations to the exported copy, else the gateway", async () => {
    enableStaticExport();
    const sha = "a".repeat(40);
    const copied = `owner-statements/${sha}/E_${"b".repeat(24)}.txt`;
    const manifest = await staticManifest({ [copied]: "statement" });
    const send = vi.fn(async () => new Response(manifest));
    const gateway = await staticChatGateway(new AbortController().signal, send);
    const route = (id: string) => `/api/public/owner-statements/${sha}/${id}`;
    const github = "https://github.com/fixture/repo/blob/abc/README.md#L1";
    expect(gateway.origin).toBe(gatewayOrigin);
    expect(gateway.citationUrl(route(`E_${"b".repeat(24)}`))).toBe(
      `./${copied}`,
    );
    expect(gateway.citationUrl(route(`E_${"c".repeat(24)}`))).toBe(
      gatewayOrigin + route(`E_${"c".repeat(24)}`),
    );
    expect(gateway.citationUrl(github)).toBe(github);
  });

  it("disables static live chat when the gateway serves another bundle", async () => {
    enableStaticExport();
    const manifest = await staticManifest({ "faq-en.json": faqJson() });
    const send = vi.fn(async (input: RequestInfo | URL) =>
      urlOf(input) === "./export-manifest.json"
        ? new Response(manifest)
        : Response.json({
            chat_available: true,
            index: { version: "new-bundle" },
          }),
    );
    await expect(
      fetchPublicStatus(new AbortController().signal, send),
    ).resolves.toEqual({ chat_available: false, bundle_mismatch: true });
  });

  it("rejects a static gateway status without a boolean chat_available", async () => {
    enableStaticExport();
    const manifest = await staticManifest({ "faq-en.json": faqJson() });
    const send = vi.fn(async (input: RequestInfo | URL) =>
      urlOf(input) === "./export-manifest.json"
        ? new Response(manifest)
        : Response.json({
            chat_available: "yes",
            index: { version: "fixture-bundle" },
          }),
    );
    await expect(
      fetchPublicStatus(new AbortController().signal, send),
    ).rejects.toThrow("status invalid");
  });

  it("never yields a chat gateway that does not match the exported CSP", async () => {
    enableStaticExport();
    const rawManifest = JSON.parse(
      await staticManifest({ "faq-en.json": faqJson() }),
    );
    rawManifest.gateway_origin = "https://attacker.example";
    const manifest = JSON.stringify(rawManifest);
    const send = vi.fn(async () => new Response(manifest));
    await expect(
      staticChatGateway(new AbortController().signal, send),
    ).rejects.toThrow("static manifest gateway policy mismatch");
    expect(send).toHaveBeenCalledTimes(1);
  });

  it("rejects a manifest gateway that does not match the exported CSP", async () => {
    enableStaticExport();
    const rawManifest = JSON.parse(
      await staticManifest({ "faq-en.json": faqJson() }),
    );
    rawManifest.gateway_origin = "https://attacker.example";
    const manifest = JSON.stringify(rawManifest);
    const send = vi.fn(async () => new Response(manifest));

    await expect(
      fetchPublicFaq(locale, new AbortController().signal, send),
    ).rejects.toThrow("static manifest gateway policy mismatch");
    expect(send).toHaveBeenCalledTimes(1);
  });
});

import type { Locale } from "../i18n/messages";
import type { PublicFaq, PublicProfile, PublicStatus } from "./publicTypes";

type Fetcher = typeof fetch;
const MAX_STATIC_MANIFEST_BYTES = 4 * 1024 * 1024;
const MAX_STATIC_JSON_BYTES = 16 * 1024 * 1024;
const MAX_STATIC_EXPORT_BYTES = 1_000_000_000;
const PUBLIC_READ_DEADLINE_MS = 10_000;

class PublicReadTimeoutError extends Error {
  constructor() {
    super("public read timed out");
    this.name = "TimeoutError";
  }
}

export async function fetchPublicStatus(
  signal: AbortSignal,
  send: Fetcher = fetch,
): Promise<PublicStatus> {
  let url = "/api/public/status";
  let credentials: RequestCredentials | undefined;
  let staticBundleId: string | undefined;
  if (isStaticExport()) {
    const manifest = await withPublicReadDeadline(signal, (readSignal) =>
      readStaticManifest(readSignal, send),
    );
    url = `${manifest.gateway_origin}/api/public/status`;
    credentials = "omit";
    staticBundleId = manifest.bundle_id;
  }
  return withPublicReadDeadline(signal, async (readSignal) => {
    // Network failure leaves the controller's last authoritative observation intact.
    const response = await send(url, {
      signal: readSignal,
      ...(credentials ? { credentials } : {}),
    });
    if (!response.ok) {
      void response.body?.cancel();
      throw new Error("status unavailable");
    }
    const value: unknown = await readResponseJson(
      response,
      1024 * 1024,
      readSignal,
    );
    if (staticBundleId !== undefined) {
      if (
        !isRecord(value) ||
        !isRecord(value.index) ||
        typeof value.chat_available !== "boolean"
      )
        throw new Error("status invalid");
      const bundleMismatch = value.index.version !== staticBundleId;
      return {
        // A gateway serving another bundle cannot answer for this exported page.
        chat_available: value.chat_available && !bundleMismatch,
        bundle_mismatch: bundleMismatch,
      };
    }
    if (!isRecord(value) || typeof value.chat_available !== "boolean") {
      throw new Error("status invalid");
    }
    return { chat_available: value.chat_available };
  });
}

export async function fetchPublicProfile(
  locale: Locale,
  signal: AbortSignal,
  send: Fetcher = fetch,
): Promise<PublicProfile> {
  let value: unknown;
  let manifest: StaticExportManifest | undefined;
  if (isStaticExport()) {
    value = await readStaticJson(
      `profile-${locale}.json`,
      signal,
      send,
      1024 * 1024,
    );
    manifest = await readStaticManifest(signal, send);
    if (
      !isRecord(value) ||
      !isRecord(value.index) ||
      value.index.version !== manifest.bundle_id
    ) {
      throw new Error("profile bundle mismatch");
    }
  } else {
    const response = await send(
      `/api/public/profile?locale=${encodeURIComponent(locale)}`,
      { signal },
    );
    if (!response.ok) throw new Error("profile unavailable");
    value = await readResponseJson(response, 1024 * 1024);
  }
  if (!validProfile(value, locale, manifest)) {
    throw new Error("profile invalid");
  }
  return value as unknown as PublicProfile;
}

export async function fetchPublicFaq(
  locale: Locale,
  signal: AbortSignal,
  send: Fetcher = fetch,
  observedFaq?: PublicFaq | null,
): Promise<PublicFaq | null> {
  if (isStaticExport()) {
    const manifest = await withPublicReadDeadline(signal, (readSignal) =>
      readStaticManifest(readSignal, send),
    );
    let live: PublicFaq | null = null;
    try {
      const result = await withPublicReadDeadline(
        signal,
        async (readSignal) => {
          const response = await send(
            `${manifest.gateway_origin}/api/public/faq?locale=${encodeURIComponent(locale)}`,
            { signal: readSignal, credentials: "omit" },
          );
          if (!response.ok) {
            void response.body?.cancel();
            return { response, value: null };
          }
          return {
            response,
            value: await readResponseJson(
              response,
              MAX_STATIC_JSON_BYTES,
              readSignal,
            ),
          };
        },
      );
      if (!result.response.ok) return null;
      const parsed = parsePublicFaq(result.value, locale);
      live =
        parsed?.bundle_id === manifest.bundle_id
          ? staticFaqCitations(parsed, manifest, false)
          : null;
      return live;
    } catch (error) {
      if (signal.aborted) throw abortSignalReason(signal);
      if (!isTransientPublicReadFailure(error)) return null;
      // An observed rejection or withdrawal must survive subsequent network loss.
      if (observedFaq !== undefined) {
        return observedFaq?.bundle_id === manifest.bundle_id
          ? staticFaqCitations(observedFaq, manifest, true)
          : null;
      }
      try {
        const fallback = parsePublicFaq(
          await withPublicReadDeadline(signal, (readSignal) =>
            readStaticJson(`faq-${locale}.json`, readSignal, send),
          ),
          locale,
        );
        return fallback?.bundle_id === manifest.bundle_id
          ? staticFaqCitations(fallback, manifest, true)
          : null;
      } catch (fallbackError) {
        if (signal.aborted) throw abortSignalReason(signal);
        if (isTransientPublicReadFailure(fallbackError)) return null;
        return null;
      }
    }
  }
  return withPublicReadDeadline(signal, async (readSignal) => {
    const response = await send(
      `/api/public/faq?locale=${encodeURIComponent(locale)}`,
      { signal: readSignal },
    );
    if (!response.ok) {
      void response.body?.cancel();
      return null;
    }
    try {
      return parsePublicFaq(
        await readResponseJson(response, MAX_STATIC_JSON_BYTES, readSignal),
        locale,
      );
    } catch {
      return null;
    }
  });
}

export function parsePublicFaq(
  value: unknown,
  locale: Locale,
): PublicFaq | null {
  if (
    !isRecord(value) ||
    typeof value.bundle_id !== "string" ||
    !/^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$/.test(value.bundle_id) ||
    value.locale !== locale ||
    !Array.isArray(value.entries) ||
    value.entries.length > 256
  ) {
    return null;
  }
  const entries: PublicFaq["entries"] = [];
  for (const candidate of value.entries) {
    if (
      !isRecord(candidate) ||
      !boundedText(candidate.question, 2000, 1) ||
      !Array.isArray(candidate.variants) ||
      candidate.variants.length > 8 ||
      !candidate.variants.every(
        (variant) => boundedText(variant, 200, 1) && variant.trim().length > 0,
      ) ||
      !boundedText(candidate.answer_markdown, 100000) ||
      !Array.isArray(candidate.citations) ||
      candidate.citations.length > 256 ||
      !candidate.citations.every(isCitation) ||
      !uniqueOwnerCitationSources(candidate.citations)
    ) {
      return null;
    }
    entries.push({
      question: candidate.question,
      variants: candidate.variants as string[],
      answer_markdown: candidate.answer_markdown,
      citations:
        candidate.citations as PublicFaq["entries"][number]["citations"],
    });
  }
  return {
    bundle_id: value.bundle_id,
    locale,
    entries,
  };
}

function uniqueOwnerCitationSources(value: unknown[]): boolean {
  const sourceIds = new Set<string>();
  for (const citation of value) {
    if (!isRecord(citation) || citation.evidence_class !== "OWNER_ASSERTION")
      continue;
    if (typeof citation.id !== "string" || sourceIds.has(citation.id))
      return false;
    sourceIds.add(citation.id);
  }
  return true;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function staticFaqCitations(
  faq: PublicFaq,
  manifest: StaticExportManifest,
  offline: boolean,
): PublicFaq {
  return {
    ...faq,
    entries: faq.entries.flatMap((entry) => {
      let unavailable = false;
      const citations = entry.citations.map((citation) => {
        if (citation.evidence_class !== "OWNER_ASSERTION") return citation;
        if (citation.url.startsWith("https://github.com/")) return citation;
        const route = citation.url.startsWith(manifest.gateway_origin + "/")
          ? citation.url.slice(manifest.gateway_origin.length)
          : citation.url;
        const evidenceId = (
          citation as typeof citation & { evidence_id?: string }
        ).evidence_id;
        const path = route.startsWith("./")
          ? route.slice(2)
          : `owner-statements/${citation.commit_sha}/${evidenceId}.txt`;
        if (manifest.files.some((file) => file.path === path))
          return { ...citation, url: `./${path}` };
        if (offline || route.startsWith("./")) unavailable = true;
        return { ...citation, url: `${manifest.gateway_origin}${route}` };
      });
      return unavailable ? [] : [{ ...entry, citations }];
    }),
  };
}

function boundedText(
  value: unknown,
  maximum: number,
  minimum = 0,
): value is string {
  if (typeof value !== "string") return false;
  const length = Array.from(value).length;
  return length >= minimum && length <= maximum;
}

function integer(
  value: unknown,
  maximum = Number.MAX_SAFE_INTEGER,
  minimum = 0,
): boolean {
  return (
    typeof value === "number" &&
    Number.isSafeInteger(value) &&
    value >= minimum &&
    value <= maximum
  );
}

function publicUrl(value: unknown): boolean {
  if (!boundedText(value, 2048, 1)) return false;
  try {
    const url = new URL(value);
    return (
      !url.username &&
      !url.password &&
      Boolean(url.hostname) &&
      (url.protocol === "https:" ||
        (url.protocol === "http:" &&
          ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)))
    );
  } catch {
    return false;
  }
}

function textList(
  value: unknown,
  maximum: number,
  itemMaximum: number,
): boolean {
  return (
    Array.isArray(value) &&
    value.length <= maximum &&
    value.every((item) => boundedText(item, itemMaximum, 1))
  );
}

function validProfile(
  value: unknown,
  locale: Locale,
  manifest?: StaticExportManifest,
): boolean {
  if (
    !isRecord(value) ||
    value.schema_version !== 1 ||
    value.locale !== locale ||
    !isRecord(value.profile) ||
    !isRecord(value.character) ||
    !isRecord(value.index) ||
    !Array.isArray(value.repositories) ||
    value.repositories.length > 10000 ||
    !textList(value.suggested_questions, 100, 2000)
  )
    return false;
  const { profile, character, index } = value;
  if (
    !boundedText(profile.display_name, 80, 1) ||
    !boundedText(profile.headline, 10000, 1) ||
    !boundedText(profile.bio, 100000, 1) ||
    !boundedText(profile.greeting, 10000, 1) ||
    !(profile.location == null || boundedText(profile.location, 120)) ||
    !(profile.avatar_url == null || publicUrl(profile.avatar_url)) ||
    !Array.isArray(profile.links) ||
    profile.links.length > 100 ||
    !profile.links.every(
      (link) =>
        isRecord(link) &&
        boundedText(link.label, 200, 1) &&
        publicUrl(link.url),
    ) ||
    !["builtin", "custom"].includes(String(character.mode)) ||
    !integer(character.revision) ||
    !integer(character.frame_duration_ms, 1000, 80) ||
    !["none", "subtle"].includes(String(character.movement)) ||
    character.asset_url !==
      (manifest ? "./character.png" : "/api/public/character.png") ||
    !boundedText(index.version, 128, 1) ||
    !/^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$/.test(index.version) ||
    !boundedText(index.built_at, 64, 1) ||
    !Number.isFinite(Date.parse(index.built_at)) ||
    !integer(index.repository_count, 10000) ||
    index.repository_count !== value.repositories.length ||
    (manifest &&
      (character.revision !== manifest.character_revision ||
        !manifest.files.some((file) => file.path === "character.png")))
  )
    return false;
  if (
    !value.repositories.every(
      (repo) =>
        isRecord(repo) &&
        boundedText(repo.slug, 200, 3) &&
        repo.slug.split("/").length === 2 &&
        repo.slug
          .split("/")
          .every((part) => part && part !== "." && part !== "..") &&
        boundedText(repo.summary, 100000, 1) &&
        boundedText(repo.role, 10000, 1) &&
        textList(repo.tags, 100, 64) &&
        (repo.demo_url == null || publicUrl(repo.demo_url)) &&
        (repo.language == null ||
          (boundedText(repo.language, 100, 1) &&
            Boolean(repo.language.trim()))) &&
        (repo.stars == null || integer(repo.stars, 2147483647)) &&
        (repo.forks == null || integer(repo.forks, 2147483647)),
    )
  )
    return false;
  if (character.scene == null) return !manifest;
  const scene = character.scene;
  if (
    !isRecord(scene) ||
    scene.revision !== character.revision ||
    !isRecord(scene.scheme) ||
    !boundedText(scene.scheme.id, 64, 1) ||
    !/^[a-z0-9_]+$/.test(scene.scheme.id) ||
    !integer(scene.scheme.version, Number.MAX_SAFE_INTEGER, 1) ||
    !["system", "light", "dark"].includes(String(scene.color_mode)) ||
    typeof scene.visitor_mode_toggle !== "boolean" ||
    typeof scene.visitor_scheme_choice !== "boolean" ||
    !isNpcPlate(scene.npc_plate) ||
    !Array.isArray(scene.schemes) ||
    scene.schemes.length === 0 ||
    !["smooth", "pixelated"].includes(String(scene.background_scaling)) ||
    !["auto", "none", "low", "medium", "high"].includes(
      String(scene.background_dim),
    ) ||
    !isRecord(scene.background_focus) ||
    !integer(scene.background_focus.x, 100) ||
    !integer(scene.background_focus.y, 100) ||
    !isSceneThemes(scene.themes)
  )
    return false;
  const ids = new Set<string>();
  for (const scheme of scene.schemes) {
    if (
      !isRecord(scheme) ||
      !boundedText(scheme.id, 64, 1) ||
      !/^[a-z0-9_]+$/.test(scheme.id) ||
      ids.has(scheme.id) ||
      !integer(scheme.version, Number.MAX_SAFE_INTEGER, 1) ||
      !isRecord(scheme.label) ||
      Object.keys(scheme.label).sort().join(",") !== "en,zh-TW" ||
      !Object.values(scheme.label).every(
        (label) => typeof label === "string" && label.trim().length > 0,
      ) ||
      !isSceneThemes(scheme.themes) ||
      !isNpcPlate(scheme.npc_plate)
    )
      return false;
    ids.add(scheme.id);
  }
  const ownerScheme = scene.scheme;
  const ownerThemes = scene.themes;
  const selected = scene.schemes.find((scheme) => scheme.id === ownerScheme.id);
  if (
    !selected ||
    selected.version !== scene.scheme.version ||
    selected.npc_plate.light !== scene.npc_plate.light ||
    selected.npc_plate.dark !== scene.npc_plate.dark ||
    !["light", "dark"].every((variant) =>
      Object.keys(ownerThemes[variant]).every(
        (role) => selected.themes[variant][role] === ownerThemes[variant][role],
      ),
    )
  )
    return false;
  return (
    scene.background_url === null ||
    (typeof scene.background_url === "string" &&
      (manifest
        ? /^\.\/scene\/[0-9a-f]{64}\.(?:png|webp)$/.test(
            scene.background_url,
          ) &&
          manifest.files.some(
            (file) => file.path === (scene.background_url as string).slice(2),
          )
        : scene.background_url ===
          `/api/public/scene-background?rev=${character.revision}`))
  );
}

function isNpcPlate(
  value: unknown,
): value is { light: boolean; dark: boolean } {
  return (
    isRecord(value) &&
    Object.keys(value).sort().join(",") === "dark,light" &&
    typeof value.light === "boolean" &&
    typeof value.dark === "boolean"
  );
}

function isSceneThemes(
  value: unknown,
): value is Record<string, Record<string, string>> {
  if (!isRecord(value) || Object.keys(value).sort().join(",") !== "dark,light")
    return false;
  return ["light", "dark"].every((variant) => {
    const tokens = value[variant];
    return (
      isRecord(tokens) &&
      Object.keys(tokens).sort().join(",") ===
        "accent,accent_ink,background,border,celestial,focus,grass,ground,hill_far,hill_near,horizon,ink,muted_ink,sky,stage,surface,surface_alt,wood" &&
      Object.values(tokens).every(
        (color) => typeof color === "string" && /^#[0-9a-f]{6}$/.test(color),
      )
    );
  });
}

function isCitation(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.evidence_class === "string" &&
    typeof value.repository === "string" &&
    typeof value.commit_sha === "string" &&
    typeof value.path === "string" &&
    typeof value.start_line === "number" &&
    Number.isInteger(value.start_line) &&
    typeof value.end_line === "number" &&
    Number.isInteger(value.end_line) &&
    value.start_line >= 1 &&
    value.end_line >= value.start_line &&
    typeof value.title === "string" &&
    typeof value.excerpt === "string" &&
    typeof value.url === "string" &&
    validCitationUrl(value)
  );
}

function validCitationUrl(value: Record<string, unknown>): boolean {
  if (!boundedText(value.url, 2048, 1)) return false;
  if (value.evidence_class === "OWNER_ASSERTION") {
    if (
      typeof value.id !== "string" ||
      !/^S[1-9][0-9]*$/.test(value.id) ||
      typeof value.evidence_id !== "string" ||
      !/^E_[0-9a-f]{24}$/.test(value.evidence_id) ||
      typeof value.commit_sha !== "string" ||
      !/^[0-9a-f]{40}$/.test(value.commit_sha) ||
      typeof value.repository !== "string"
    ) {
      return false;
    }
    const path = githubCitationPath(value.path);
    if (path === null) return false;
    const localRoute = `/api/public/owner-statements/${value.commit_sha}/${value.evidence_id}`;
    const localAsset = `./owner-statements/${value.commit_sha}/${value.evidence_id}.txt`;
    if (value.url === localRoute || value.url === localAsset)
      return value.repository === "local/portfolio";
    if (
      !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(value.repository) ||
      value.repository
        .split("/")
        .some((part) => part === "." || part === "..") ||
      typeof value.start_line !== "number" ||
      typeof value.end_line !== "number" ||
      !Number.isInteger(value.start_line) ||
      !Number.isInteger(value.end_line) ||
      value.start_line < 1 ||
      value.end_line < value.start_line
    ) {
      return false;
    }
    const line =
      value.start_line === value.end_line
        ? `#L${value.start_line}`
        : `#L${value.start_line}-L${value.end_line}`;
    return (
      value.url ===
      `https://github.com/${value.repository}/blob/${value.commit_sha}/${path}${line}`
    );
  }
  try {
    const url = new URL(value.url);
    return (
      url.protocol === "https:" &&
      url.hostname === "github.com" &&
      !url.username &&
      !url.password &&
      !url.port
    );
  } catch {
    return false;
  }
}

function githubCitationPath(value: unknown): string | null {
  if (
    !boundedText(value, 2048, 1) ||
    value.startsWith("/") ||
    value.includes("\\")
  ) {
    return null;
  }
  const parts = value.split("/");
  if (parts.some((part) => part === "" || part === "." || part === ".."))
    return null;
  try {
    return parts
      .map((part) =>
        encodeURIComponent(part).replace(
          /[!'()*]/g,
          (character) =>
            `%${character.charCodeAt(0).toString(16).toUpperCase()}`,
        ),
      )
      .join("/");
  } catch {
    return null;
  }
}

interface StaticManifestFile {
  path: string;
  size: number;
  sha256: string;
}

interface StaticExportManifest {
  schema_version: 1;
  bundle_id: string;
  character_revision: number;
  pages_url: string;
  base_path: string;
  pages_origin: string;
  gateway_origin: string;
  content_sha256: string;
  files: StaticManifestFile[];
}

export interface StaticChatGateway {
  origin: string;
  citationUrl(url: string): string;
}

/** Pages share site live chat targets only the integrity-checked manifest gateway.
 * Relative local owner-statement routes use the exported copy when present,
 * otherwise the same gateway. */
export async function staticChatGateway(
  signal: AbortSignal,
  send: Fetcher = fetch,
): Promise<StaticChatGateway> {
  const manifest = await withPublicReadDeadline(signal, (readSignal) =>
    readStaticManifest(readSignal, send),
  );
  const route = "/api/public/owner-statements/";
  return {
    origin: manifest.gateway_origin,
    citationUrl: (url) => {
      if (!url.startsWith(route)) return url;
      const path = `owner-statements/${url.slice(route.length)}.txt`;
      return manifest.files.some((file) => file.path === path)
        ? `./${path}`
        : `${manifest.gateway_origin}${url}`;
    },
  };
}

export function isStaticExport(): boolean {
  return (
    typeof document !== "undefined" &&
    document.documentElement.dataset.staticExport === "true"
  );
}

async function withPublicReadDeadline<T>(
  parentSignal: AbortSignal,
  operation: (signal: AbortSignal) => Promise<T>,
): Promise<T> {
  if (parentSignal.aborted) throw abortSignalReason(parentSignal);
  const controller = new AbortController();
  let timedOut = false;
  const onParentAbort = () => controller.abort(abortSignalReason(parentSignal));
  parentSignal.addEventListener("abort", onParentAbort, { once: true });
  if (parentSignal.aborted) onParentAbort();
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort(new PublicReadTimeoutError());
  }, PUBLIC_READ_DEADLINE_MS);
  try {
    return await raceWithAbort(
      Promise.resolve().then(() => operation(controller.signal)),
      controller.signal,
    );
  } catch (error) {
    if (parentSignal.aborted) throw abortSignalReason(parentSignal);
    if (timedOut) throw new PublicReadTimeoutError();
    throw error;
  } finally {
    clearTimeout(timer);
    parentSignal.removeEventListener("abort", onParentAbort);
  }
}

function raceWithAbort<T>(
  operation: Promise<T>,
  signal: AbortSignal,
): Promise<T> {
  return new Promise((resolve, reject) => {
    let finished = false;
    const cleanup = () => signal.removeEventListener("abort", onAbort);
    const onAbort = () => {
      if (finished) return;
      finished = true;
      cleanup();
      reject(abortSignalReason(signal));
    };
    signal.addEventListener("abort", onAbort, { once: true });
    operation.then(
      (value) => {
        if (finished) return;
        finished = true;
        cleanup();
        resolve(value);
      },
      (error: unknown) => {
        if (finished) return;
        finished = true;
        cleanup();
        reject(error);
      },
    );
    if (signal.aborted) onAbort();
  });
}

function abortSignalReason(signal: AbortSignal): unknown {
  return (
    signal.reason ?? new DOMException("The operation was aborted", "AbortError")
  );
}

function isTransientPublicReadFailure(error: unknown): boolean {
  return error instanceof TypeError || error instanceof PublicReadTimeoutError;
}

async function readStaticManifest(
  signal: AbortSignal,
  send: Fetcher,
): Promise<StaticExportManifest> {
  const response = await send("./export-manifest.json", {
    signal,
    credentials: "omit",
  });
  if (!response.ok) throw new Error("static manifest unavailable");
  const bytes = await readResponseBytes(
    response,
    MAX_STATIC_MANIFEST_BYTES,
    signal,
  );
  let value: unknown;
  try {
    value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    throw new Error("static manifest invalid");
  }
  const manifest = validateStaticManifest(value);
  if (!manifest) throw new Error("static manifest invalid");
  if (!matchesStaticGatewayPolicy(manifest.gateway_origin)) {
    throw new Error("static manifest gateway policy mismatch");
  }
  if (
    bytes.byteLength +
      manifest.files.reduce((total, file) => total + file.size, 0) >
    MAX_STATIC_EXPORT_BYTES
  ) {
    throw new Error("static manifest invalid");
  }
  const identity = JSON.stringify(
    manifest.files.map(({ path, size, sha256 }) => ({ path, sha256, size })),
  );
  if (
    (await sha256(new TextEncoder().encode(identity))) !==
    manifest.content_sha256
  ) {
    throw new Error("static manifest invalid");
  }
  return manifest;
}

async function readStaticJson(
  path: string,
  signal: AbortSignal,
  send: Fetcher,
  maximumBytes = MAX_STATIC_JSON_BYTES,
): Promise<unknown> {
  const manifest = await readStaticManifest(signal, send);
  const file = manifest.files.find((candidate) => candidate.path === path);
  if (!file || file.size > maximumBytes) {
    throw new Error("static file unavailable");
  }
  const response = await send(`./${path}`, { signal, credentials: "omit" });
  if (!response.ok) throw new Error("static file unavailable");
  const bytes = await readResponseBytes(response, maximumBytes, signal);
  if (bytes.byteLength !== file.size || (await sha256(bytes)) !== file.sha256) {
    throw new Error("static file integrity failed");
  }
  try {
    return JSON.parse(
      new TextDecoder("utf-8", { fatal: true }).decode(bytes),
    ) as unknown;
  } catch {
    throw new Error("static file invalid");
  }
}

function validateStaticManifest(value: unknown): StaticExportManifest | null {
  if (
    !isRecord(value) ||
    Object.keys(value).sort().join(",") !==
      "base_path,bundle_id,character_revision,content_sha256,files,gateway_origin,pages_origin,pages_url,schema_version" ||
    value.schema_version !== 1 ||
    typeof value.bundle_id !== "string" ||
    !/^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$/.test(value.bundle_id) ||
    typeof value.character_revision !== "number" ||
    !Number.isSafeInteger(value.character_revision) ||
    value.character_revision < 0 ||
    typeof value.pages_url !== "string" ||
    typeof value.base_path !== "string" ||
    typeof value.pages_origin !== "string" ||
    typeof value.gateway_origin !== "string" ||
    typeof value.content_sha256 !== "string" ||
    !/^[0-9a-f]{64}$/.test(value.content_sha256) ||
    !Array.isArray(value.files) ||
    value.files.length > 4096
  ) {
    return null;
  }
  const pages = validOrigin(value.pages_origin, true);
  const gateway = validOrigin(value.gateway_origin, false);
  if (!pages || !gateway) return null;
  try {
    const pagesUrl = new URL(value.pages_url);
    if (
      pagesUrl.origin !== value.pages_origin ||
      value.pages_url !== value.pages_origin + value.base_path ||
      value.pages_url.length > 2048 ||
      pagesUrl.pathname !== value.base_path ||
      pagesUrl.protocol !== "https:" ||
      pagesUrl.search ||
      pagesUrl.hash ||
      !value.base_path.startsWith("/") ||
      !value.base_path.endsWith("/")
    ) {
      return null;
    }
    if (
      value.base_path !== "/" &&
      !safeStaticPath(value.base_path.slice(1, -1))
    )
      return null;
  } catch {
    return null;
  }
  const files: StaticManifestFile[] = [];
  let previous = "";
  let totalBytes = 0;
  for (const candidate of value.files) {
    if (
      !isRecord(candidate) ||
      Object.keys(candidate).sort().join(",") !== "path,sha256,size" ||
      typeof candidate.path !== "string" ||
      !safeStaticPath(candidate.path) ||
      candidate.path <= previous ||
      candidate.path === "export-manifest.json" ||
      typeof candidate.size !== "number" ||
      !Number.isSafeInteger(candidate.size) ||
      candidate.size < 0 ||
      typeof candidate.sha256 !== "string" ||
      !/^[0-9a-f]{64}$/.test(candidate.sha256)
    ) {
      return null;
    }
    totalBytes += candidate.size;
    if (totalBytes > MAX_STATIC_EXPORT_BYTES) return null;
    previous = candidate.path;
    files.push({
      path: candidate.path,
      size: candidate.size,
      sha256: candidate.sha256,
    });
  }
  return {
    schema_version: 1,
    bundle_id: value.bundle_id,
    character_revision: value.character_revision,
    pages_url: value.pages_url,
    base_path: value.base_path,
    pages_origin: value.pages_origin,
    gateway_origin: value.gateway_origin,
    content_sha256: value.content_sha256,
    files,
  };
}

async function readResponseJson(
  response: Response,
  maximumBytes: number,
  signal?: AbortSignal,
): Promise<unknown> {
  const bytes = await readResponseBytes(response, maximumBytes, signal);
  try {
    return JSON.parse(
      new TextDecoder("utf-8", { fatal: true }).decode(bytes),
    ) as unknown;
  } catch {
    throw new Error("response JSON invalid");
  }
}

async function readResponseBytes(
  response: Response,
  maximumBytes: number,
  signal?: AbortSignal,
): Promise<Uint8Array> {
  const declared = response.headers.get("content-length");
  if (
    declared !== null &&
    (!/^\d+$/.test(declared) || Number(declared) > maximumBytes)
  ) {
    throw new Error("response too large");
  }
  const reader = response.body?.getReader();
  if (!reader) throw new Error("response body unavailable");
  const chunks: Uint8Array[] = [];
  let size = 0;
  let cancellation: Promise<void> | undefined;
  let rejectAbort: ((reason: unknown) => void) | undefined;
  const abortPromise = signal
    ? new Promise<never>((_resolve, reject) => {
        rejectAbort = reject;
      })
    : undefined;
  const cancelReader = () => {
    cancellation ??= reader.cancel().catch(() => undefined);
    return cancellation;
  };
  const onAbort = () => {
    void cancelReader();
    rejectAbort?.(abortSignalReason(signal!));
  };
  signal?.addEventListener("abort", onAbort, { once: true });
  if (signal?.aborted) onAbort();
  try {
    for (;;) {
      const pendingRead = reader.read();
      const result = abortPromise
        ? await Promise.race([pendingRead, abortPromise])
        : await pendingRead;
      if (result.done) break;
      size += result.value.byteLength;
      if (size > maximumBytes) {
        await cancelReader();
        throw new Error("response too large");
      }
      chunks.push(result.value);
    }
  } finally {
    signal?.removeEventListener("abort", onAbort);
    if (signal?.aborted) await cancelReader();
    reader.releaseLock();
  }
  const content = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    content.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return content;
}

function validOrigin(value: string, pages: boolean): boolean {
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase();
    return (
      url.protocol === "https:" &&
      url.origin === value &&
      url.pathname === "/" &&
      !url.search &&
      !url.hash &&
      !url.username &&
      !url.password &&
      (!pages || (host.split(".").length === 3 && host.endsWith(".github.io")))
    );
  } catch {
    return false;
  }
}

function matchesStaticGatewayPolicy(gatewayOrigin: string): boolean {
  const policy = document
    .querySelector('meta[http-equiv="Content-Security-Policy"]')
    ?.getAttribute("content");
  if (!policy) return false;
  const connectDirective = policy
    .split(";")
    .map((directive) => directive.trim())
    .find((directive) => directive.startsWith("connect-src "));
  if (!connectDirective) return false;
  const sources = connectDirective.slice("connect-src ".length).split(/\s+/u);
  return (
    sources.length === 2 &&
    sources.includes("'self'") &&
    sources.includes(gatewayOrigin)
  );
}

function safeStaticPath(value: string): boolean {
  return (
    value.length > 0 &&
    !value.startsWith("/") &&
    !value.includes("\\") &&
    !value.includes(":") &&
    value
      .split("/")
      .every(
        (part) =>
          /^[A-Za-z0-9._-]{1,128}$/.test(part) && part !== "." && part !== "..",
      )
  );
}

async function sha256(content: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", content);
  return Array.from(new Uint8Array(digest), (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("");
}

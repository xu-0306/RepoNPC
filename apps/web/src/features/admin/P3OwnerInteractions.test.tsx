import {
  Children,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Button, FileTrigger } from "react-aria-components";
import {
  CharacterAssetConverter,
  type CharacterConversionResult,
  type CharacterAssetConverterProps,
} from "./CharacterAssetConverter";
import { Base64PngCanvas } from "./Base64PngCanvas";
import { CHARACTER_STATES } from "../character/CharacterRenderer";
import { AppearancePanel, type SceneAppearanceState } from "./AppearancePanel";
import { ModelSetupWorkspace } from "./ModelSetupWorkspace";
import type { PublicProfile, SceneTokens } from "../../app/publicTypes";

// The project's Node suite exercises real component handlers with retained hooks.
const hooks = vi.hoisted(() => ({
  values: [] as unknown[],
  cursor: 0,
  effects: [] as Array<() => unknown>,
}));
vi.mock("react", async (importOriginal) => {
  const react = await importOriginal<typeof import("react")>();
  return {
    ...react,
    useEffect: (effect: () => unknown) => {
      hooks.effects.push(effect);
    },
    useMemo: (factory: () => unknown) => factory(),
    useState: (initial: unknown) => {
      const index = hooks.cursor++;
      if (!(index in hooks.values))
        hooks.values[index] =
          typeof initial === "function" ? initial() : initial;
      return [
        hooks.values[index],
        (next: unknown) => {
          hooks.values[index] =
            typeof next === "function" ? next(hooks.values[index]) : next;
        },
      ];
    },
    useRef: (initial: unknown) => {
      const index = hooks.cursor++;
      if (!(index in hooks.values)) hooks.values[index] = { current: initial };
      return hooks.values[index];
    },
  };
});
vi.mock("./characterFrameAlignment", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./characterFrameAlignment")>()),
  inspectFrameAlignment: vi.fn(async () => ({
    bounds: Array.from({ length: 28 }, () => ({
      left: 10,
      top: 10,
      right: 50,
      bottom: 60,
    })),
    anchors: Array(28).fill(30),
    suggestedOffsets: Array.from({ length: 28 }, () => ({ x: 0, y: 0 })),
    horizontalDrift: Array(7).fill(0),
  })),
}));
function elements(node: ReactNode): ReactElement<Record<string, unknown>>[] {
  return Children.toArray(node).flatMap((child) =>
    isValidElement<Record<string, unknown>>(child)
      ? [child, ...elements(child.props.children as ReactNode)]
      : [],
  );
}
function render(component: () => ReactNode) {
  hooks.cursor = 0;
  hooks.effects = [];
  return elements(component());
}
function files(...items: File[]) {
  return items as unknown as FileList;
}
function material(name: string) {
  const file = new File(["fixture"], name);
  Object.defineProperty(file, "webkitRelativePath", {
    value: "",
    configurable: true,
  });
  return file;
}
function click(node: ReactElement<Record<string, unknown>>) {
  return (node.props.onClick as () => unknown)();
}
const asset = {
  width: 256,
  height: 448,
  png_base64: "fixture-bytes",
  sha256: "a".repeat(64),
};
const result: CharacterConversionResult = {
  status: "converted",
  asset,
  edge_cleanup: null,
  conversion: {
    source_kind: "grid",
    strategy: "pixelize",
    source_frame_sizes: [[64, 64]],
    candidate_id: null,
    source_path: null,
    warnings: [],
  },
};
beforeEach(() => {
  hooks.values = [];
  hooks.cursor = 0;
  hooks.effects = [];
});
afterEach(() => vi.unstubAllGlobals());

describe("pixel character creation interactions", () => {
  function setup(overrides: Partial<CharacterAssetConverterProps> = {}) {
    const input: CharacterAssetConverterProps = {
      locale: "en",
      onConvert: vi.fn(async () => result),
      onValidate: vi.fn(async () => asset),
      onApply: vi.fn(async () => undefined),
      ...overrides,
    };
    const view = () => render(() => CharacterAssetConverter(input));
    const trigger = (folder = false) =>
      view().find(
        (node) =>
          node.type === FileTrigger &&
          Boolean(node.props.acceptDirectory) === folder,
      )!;
    const convert = () => {
      const form = view().find((node) => node.type === "form")!;
      (form.props.onSubmit as (event: unknown) => void)({
        preventDefault: vi.fn(),
      });
    };
    return { input, view, trigger, convert };
  }
  it.each(["zh-TW", "en"] as const)(
    "exposes FileTrigger buttons, empty stage and seven named states in %s",
    (locale) => {
      const { view, trigger } = setup({ locale });
      const nodes = view();
      expect(nodes.filter((node) => node.type === FileTrigger)).toHaveLength(2);
      expect(trigger().props.acceptedFileTypes).toEqual([
        ".png",
        ".zip",
        "image/png",
        "application/zip",
      ]);
      expect(trigger(true).props.allowsMultiple).toBe(true);
      const buttons = nodes.filter((node) => node.type === Button);
      expect(buttons.map((node) => node.props.children)).toEqual(
        locale === "en"
          ? ["Choose PNG or ZIP", "Choose a folder"]
          : ["選擇 PNG 或 ZIP", "選擇整個資料夾"],
      );
      expect(
        nodes.some(
          (node) => node.type === "input" && node.props.type === "file",
        ),
      ).toBe(false);
      expect(
        nodes.some(
          (node) =>
            node.props.children ===
            (locale === "en"
              ? "Upload art to preview your character."
              : "上傳素材後即可預覽角色。"),
        ),
      ).toBe(true);
      const poses = nodes.filter(
        (node) => node.type === "button" && "aria-pressed" in node.props,
      );
      expect(poses).toHaveLength(7);
      expect(poses.map((node) => node.props["aria-pressed"])).toEqual([
        true,
        false,
        false,
        false,
        false,
        false,
        false,
      ]);
      expect(poses.every((node) => node.props.disabled)).toBe(true);
      expect(
        nodes.find(
          (node) =>
            node.props.className === "character-converter__instructions",
        )?.props.open,
      ).toBeUndefined();
      expect(
        nodes.filter((node) => node.type === Base64PngCanvas),
      ).toHaveLength(0);
    },
  );
  it("keeps file, folder and drop sources on the same conversion path, including picking the same file twice", async () => {
    const { input, trigger, convert, view } = setup();
    const file = material("arbitrary-art.zip");
    for (let attempt = 1; attempt <= 2; attempt++) {
      (trigger().props.onSelect as (value: FileList | null) => void)(
        files(file),
      );
      convert();
      await vi.waitFor(() =>
        expect(view().some((node) => node.type === "footer")).toBe(true),
      );
      expect(input.onConvert).toHaveBeenCalledTimes(attempt);
      expect(input.onConvert).toHaveBeenLastCalledWith(
        { kind: "file", file, displayName: file.name },
        "pixelize",
        undefined,
      );
    }
    const folderFile = material("anything.png");
    Object.defineProperty(folderFile, "webkitRelativePath", {
      value: "自訂資料/art.png",
      configurable: true,
    });
    (trigger(true).props.onSelect as (value: FileList) => void)(
      files(folderFile),
    );
    convert();
    await vi.waitFor(() =>
      expect(view().some((node) => node.type === "footer")).toBe(true),
    );
    expect(input.onConvert).toHaveBeenLastCalledWith(
      {
        kind: "folder",
        displayName: "自訂資料",
        entries: [{ file: folderFile, path: "自訂資料/art.png" }],
      },
      "pixelize",
      undefined,
    );
    const dropped = material("unseen.png");
    const drop = view().find(
      (node) => node.props.className === "character-converter__dropzone",
    )!;
    (drop.props.onDrop as (event: unknown) => void)({
      preventDefault: vi.fn(),
      dataTransfer: { files: files(dropped) },
    });
    convert();
    await vi.waitFor(() =>
      expect(view().some((node) => node.type === "footer")).toBe(true),
    );
    expect(input.onConvert).toHaveBeenLastCalledWith(
      { kind: "file", file: dropped, displayName: dropped.name },
      "pixelize",
      undefined,
    );
    (trigger().props.onSelect as (value: null) => void)(null);
    expect(view().some((node) => node.type === "footer")).toBe(false);
  });
  it("runs one live canvas with seven fixed-frame thumbnails and keeps apply/download guards", async () => {
    const { input, trigger, convert, view } = setup();
    (trigger().props.onSelect as (value: FileList) => void)(
      files(material("concept.png")),
    );
    convert();
    await vi.waitFor(() =>
      expect(view().some((node) => node.type === "footer")).toBe(true),
    );
    const canvases = view().filter(
      (node) => node.type === Base64PngCanvas && node.props.state,
    );
    expect(canvases).toHaveLength(8);
    expect(canvases.filter((node) => node.props.frame == null)).toHaveLength(1);
    expect(
      canvases
        .filter((node) => node.props.frame === 0)
        .map((node) => node.props.state),
    ).toEqual([...CHARACTER_STATES]);
    const poses = view().filter(
      (node) => node.type === "button" && "aria-pressed" in node.props,
    );
    click(poses[4]);
    expect(
      view().find(
        (node) => node.type === Base64PngCanvas && node.props.frame === null,
      )?.props.state,
    ).toBe("talk");
    const footer = () =>
      elements(view().find((node) => node.type === "footer")!);
    const apply = () =>
      footer().find(
        (node) =>
          node.type === "button" &&
          node.props.children === "Apply to portfolio",
      )!;
    expect(apply().props.disabled).toBe(false);
    const filename = view().find(
      (node) => node.props.id === "admin-character-filename",
    )!;
    (filename.props.onChange as (event: unknown) => void)({
      target: { value: "../unsafe.png" },
    });
    expect(
      footer().find(
        (node) =>
          node.type === "button" &&
          node.props.children === "Download character image",
      )?.props.disabled,
    ).toBe(true);
    expect(apply().props.disabled).toBe(false);
    input.disabled = true;
    expect(apply().props.disabled).toBe(true);
    input.disabled = false;
    await click(apply());
    expect(input.onApply).toHaveBeenCalledExactlyOnceWith(asset);
  });
  it("preserves conversion failures, busy guards and explicit cleanup choice", async () => {
    let finish!: (value: CharacterConversionResult) => void;
    const { input, trigger, convert, view } = setup({
      onConvert: vi.fn(
        () =>
          new Promise<CharacterConversionResult>((resolve) => {
            finish = resolve;
          }),
      ),
    });
    (trigger().props.onSelect as (value: FileList) => void)(
      files(material("source.png")),
    );
    convert();
    expect(
      view()
        .filter((node) => node.type === Button)
        .every((node) => node.props.isDisabled),
    ).toBe(true);
    const drop = view().find(
      (node) => node.props.className === "character-converter__dropzone",
    )!;
    (drop.props.onDrop as (event: unknown) => void)({
      preventDefault: vi.fn(),
      dataTransfer: { files: files(material("ignored.png")) },
    });
    finish({
      ...result,
      edge_cleanup: {
        asset,
        affected_frames: [{ state: "walk", frame: 1 }],
        removed_source_pixels: 4,
      },
    });
    await vi.waitFor(() =>
      expect(view().some((node) => node.type === "footer")).toBe(true),
    );
    const footerButtons = () =>
      elements(view().find((node) => node.type === "footer")!).filter(
        (node) => node.type === "button",
      );
    expect(footerButtons().every((node) => node.props.disabled)).toBe(true);
    const keep = view().find(
      (node) =>
        node.type === "button" &&
        node.props.children === "Keep original conversion",
    )!;
    await click(keep);
    await vi.waitFor(() =>
      expect(footerButtons().every((node) => !node.props.disabled)).toBe(true),
    );
    expect(input.onApply).not.toHaveBeenCalled();
    input.onConvert = vi.fn(async () => {
      throw new Error("ASSET_INVALID");
    });
    convert();
    await vi.waitFor(() =>
      expect(view().some((node) => node.props.role === "alert")).toBe(true),
    );
    expect(view().some((node) => node.type === "footer")).toBe(false);
  });
});

describe("equipment disclosure state", () => {
  it("starts open and preserves a user collapse across status refresh", () => {
    const tree = ModelSetupWorkspace({
      locale: "en",
      selectionView: null,
      chatConnectionView: null,
      embeddingConnectionView: null,
      chatView: null,
      embeddingView: null,
    });
    const slot = elements(tree).find((node) => node.props.number === "01")!;
    const view = () =>
      render(() => (slot.type as (props: unknown) => ReactNode)(slot.props));
    let details = view().find((node) => node.type === "details")!;
    expect(details.props.open).toBe(true);
    (details.props.onToggle as (event: unknown) => void)({
      currentTarget: { open: false },
    });
    details = view().find((node) => node.type === "details")!;
    expect(details.props.open).toBe(false);
  });
});

// Synthetic scene values are confined to tests; the production palette is token data.
const tokens: SceneTokens = {
  background: "#ffffff",
  surface: "#ffffff",
  surface_alt: "#ffffff",
  ink: "#ffffff",
  muted_ink: "#ffffff",
  accent: "#ffffff",
  accent_ink: "#ffffff",
  border: "#ffffff",
  stage: "#ffffff",
  focus: "#ffffff",
  sky: "#ffffff",
  horizon: "#ffffff",
  hill_far: "#ffffff",
  hill_near: "#ffffff",
  grass: "#ffffff",
  ground: "#ffffff",
  wood: "#ffffff",
  celestial: "#ffffff",
};
const settings = {
  color_scheme: "invented-fixture",
  color_mode: "system" as const,
  visitor_mode_toggle: true,
  visitor_scheme_choice: true,
  accent: null,
  background: "none",
  focus: { x: 50, y: 50 },
  dim: "none" as const,
  scaling: "smooth" as const,
};
const scene = {
  revision: 1,
  scheme: { id: settings.color_scheme, version: 1 },
  color_mode: "system" as const,
  visitor_mode_toggle: true,
  visitor_scheme_choice: true,
  themes: { light: tokens, dark: tokens },
  npc_plate: { light: false, dark: false },
  schemes: [],
  background_url: null,
  background_scaling: "smooth" as const,
  background_focus: settings.focus,
  background_dim: "none" as const,
};
const appearance: SceneAppearanceState = {
  source_bundle_id: "fixture",
  source_character_revision: 1,
  character_revision: 1,
  appearance_revision: 1,
  sprite_sha256: "a".repeat(64),
  draft_revision: "draft-fixture",
  issued_revision: 1,
  scene,
  settings,
  defaults: settings,
  schemes: [],
};
const profile: PublicProfile = {
  schema_version: 1,
  locale: "en",
  profile: {
    display_name: "Fixture",
    headline: "",
    bio: "",
    greeting: "",
    location: null,
    avatar_url: null,
    links: [],
  },
  repositories: [],
  suggested_questions: [],
  character: {
    mode: "custom",
    revision: 1,
    asset_url: "/api/public/character.png",
    frame_duration_ms: 160,
    movement: "none",
    scene,
  },
  index: { version: "fixture", repository_count: 0, built_at: "fixture" },
};

describe("visitor scheme permission round trip", () => {
  it.each(["zh-TW", "en"] as const)(
    "sends false through preview and apply, then restores server false in %s",
    async (locale) => {
      const returned: SceneAppearanceState = {
        ...appearance,
        appearance_revision: 2,
        settings: { ...settings, visitor_scheme_choice: false },
        scene: { ...scene, visitor_scheme_choice: false },
      };
      const calls: Array<[string, RequestInit | undefined]> = [];
      const request = async <T,>(
        path: string,
        options?: RequestInit,
      ): Promise<T> => {
        calls.push([path, options]);
        if (path.startsWith("/api/public/profile"))
          return { ...profile, locale } as T;
        if (path === "/api/admin/scene/preview" && options?.method === "POST")
          return { scene: returned.scene, notices: [] } as T;
        if (path === "/api/admin/scene" && options?.method === "PUT")
          return { scene_state: returned } as T;
        throw new Error("Unexpected request");
      };
      const input = {
        locale,
        initialState: appearance,
        request,
        onStateChange: vi.fn(),
      };
      const view = () => render(() => AppearancePanel(input));
      const permission = () => {
        const label = view().find(
          (node) =>
            node.type === "label" &&
            Children.toArray(node.props.children as ReactNode).includes(
              locale === "en"
                ? "Let visitors choose a colour scheme"
                : "允許訪客切換配色",
            ),
        )!;
        return elements(label).find((node) => node.type === "input")!;
      };
      view();
      for (const effect of hooks.effects) effect();
      await Promise.resolve();
      expect(permission().props.checked).toBe(true);
      (permission().props.onChange as (event: unknown) => void)({
        target: { checked: false },
      });
      expect(permission().props.checked).toBe(false);
      const preview = view().find(
        (node) =>
          node.type === "button" &&
          node.props.children ===
            (locale === "en" ? "Preview appearance" : "預覽外觀"),
      )!;
      expect(preview.props.disabled).toBe(false);
      await click(preview);
      const previewOptions = calls.find(
        ([path]) => path === "/api/admin/scene/preview",
      )![1] as RequestInit;
      expect(
        JSON.parse(previewOptions.body as string).visitor_scheme_choice,
      ).toBe(false);
      const apply = view().find(
        (node) =>
          node.type === "button" &&
          node.props.children ===
            (locale === "en" ? "Apply appearance" : "套用外觀"),
      )!;
      expect(apply.props.disabled).toBe(false);
      await click(apply);
      const applyOptions = calls.find(
        ([path]) => path === "/api/admin/scene",
      )![1] as RequestInit;
      expect(
        JSON.parse(applyOptions.body as string).proposal.visitor_scheme_choice,
      ).toBe(false);
      expect(input.onStateChange).toHaveBeenCalledExactlyOnceWith(returned);
      expect(permission().props.checked).toBe(false);
      hooks.values = [];
      input.initialState = returned;
      expect(permission().props.checked).toBe(false);
    },
  );
});

it.each([
  [false, 0, false],
  [true, undefined, false],
  [false, undefined, true],
] as const)(
  "keeps canvas reduced=%s frame=%s animation=%s",
  async (reduced, frame, animated) => {
    const context = {
      save: vi.fn(),
      beginPath: vi.fn(),
      rect: vi.fn(),
      clip: vi.fn(),
      drawImage: vi.fn<(...args: unknown[]) => void>(),
      restore: vi.fn(),
      clearRect: vi.fn(),
    };
    const bitmap = { width: 256, height: 448, close: vi.fn() };
    const media = {
      matches: reduced,
      addEventListener: vi.fn<(name: string, callback: () => void) => void>(),
      removeEventListener: vi.fn(),
    };
    const interval = vi.fn(() => 1);
    const clearInterval = vi.fn();
    vi.stubGlobal("window", {
      atob,
      matchMedia: () => media,
      setInterval: interval,
      clearInterval,
    });
    vi.stubGlobal(
      "createImageBitmap",
      vi.fn(async () => bitmap),
    );
    const tree = render(() =>
      Base64PngCanvas({
        pngBase64: "AA==",
        width: 64,
        height: 64,
        state: "think",
        frame,
        label: "Think",
        failureText: "Unavailable",
      }),
    );
    const canvas = tree.find((node) => node.type === "canvas")!;
    (canvas.props.ref as { current: unknown }).current = {
      getContext: () => context,
    };
    const dispose = hooks.effects[0]() as () => void;
    await vi.waitFor(() => expect(context.drawImage).toHaveBeenCalled());
    expect(context.drawImage.mock.calls[0].slice(1, 3)).toEqual([0, 192]);
    expect(interval).toHaveBeenCalledTimes(animated ? 1 : 0);
    if (animated) {
      media.matches = true;
      media.addEventListener.mock.calls[0][1]();
      expect(clearInterval).toHaveBeenCalledWith(1);
      expect(interval).toHaveBeenCalledTimes(1);
    }
    dispose();
    expect(bitmap.close).toHaveBeenCalledOnce();
  },
);

it.each(["zh-TW", "en"] as const)(
  "uses the server's false default when there is no appearance receipt in %s",
  (locale) => {
    const nodes = render(() =>
      AppearancePanel({
        locale,
        initialState: {
          ...appearance,
          settings: null,
          defaults: { ...settings, visitor_scheme_choice: false },
        },
        request: async () => {
          throw new Error("No request during render");
        },
        onStateChange: vi.fn(),
      }),
    );
    const label = nodes.find(
      (node) =>
        node.type === "label" &&
        Children.toArray(node.props.children as ReactNode).includes(
          locale === "en"
            ? "Let visitors choose a colour scheme"
            : "允許訪客切換配色",
        ),
    )!;
    expect(
      elements(label).find((node) => node.type === "input")?.props.checked,
    ).toBe(false);
  },
);

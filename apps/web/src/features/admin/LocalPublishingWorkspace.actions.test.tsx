import {
  Children,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocalPublishingWorkspace } from "./LocalPublishingWorkspace";

// The suite uses Node; retain hook state while exercising the real component's
// event handlers and element tree, without mounting unrelated polling panels.
const hooks = vi.hoisted(() => ({ values: [] as unknown[], cursor: 0 }));
vi.mock("react", async (importOriginal) => {
  const react = await importOriginal<typeof import("react")>();
  return {
    ...react,
    useEffect: vi.fn(),
    useState: (initial: unknown) => {
      const index = hooks.cursor++;
      if (!(index in hooks.values)) hooks.values[index] = initial;
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

function elements(node: ReactNode): ReactElement<Record<string, unknown>>[] {
  return Children.toArray(node).flatMap((child) =>
    isValidElement<Record<string, unknown>>(child)
      ? [child, ...elements(child.props.children as ReactNode)]
      : [],
  );
}

beforeEach(() => {
  hooks.values = [];
  hooks.cursor = 0;
});
afterEach(() => vi.unstubAllGlobals());

describe("local publication operation feedback", () => {
  it.each(["zh-TW", "en"] as const)(
    "previews exact confirmed content and requests a checked README download once in %s",
    async (locale) => {
      const requestCalls = vi.fn();
      const input = {
        locale,
        content: "unapplied draft canary",
        spriteBase64: null,
        revision: null,
        initialAccount: "another-owner",
        selection: null,
        request: async <T,>() => {
          requestCalls();
          return {} as T;
        },
        onStored: vi.fn(),
        onCreateDraft: vi.fn(),
        repositories: [],
        onAddClaim: vi.fn(),
      };
      const render = () => {
        hooks.cursor = 0;
        return elements(LocalPublishingWorkspace(input));
      };
      const guide = () =>
        render().find((node) => "onDownloadReadme" in node.props)!;
      const sharing = () =>
        render().find((node) => "observedState" in node.props)!;
      const state = {
        pages_url: "https://another-owner.github.io/site/",
        configured: true,
        verified: true,
        verified_at: "2026-10-12T00:00:00Z",
        verified_content_sha256: "a".repeat(64),
      };
      const action = () => (guide().props.onDownloadReadme as () => void)();
      const text =
        "# Confirmed public owner\n\n[![NPC](https://another-owner.github.io/site/card-light-en.gif)](https://another-owner.github.io/site/)\n";
      let finish!: (response: Response) => void;
      const fetchReadme = vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            finish = resolve;
          }),
      );
      vi.stubGlobal("fetch", fetchReadme);
      const link = { href: "", download: "", click: vi.fn(), remove: vi.fn() };
      const append = vi.fn();
      const focus = vi.fn();
      vi.stubGlobal("document", {
        createElement: vi.fn(() => link),
        body: { append },
        getElementById: vi.fn(() => ({ focus })),
      });
      const createUrl = vi
        .spyOn(URL, "createObjectURL")
        .mockReturnValue("blob:readme-fixture");
      const revokeUrl = vi
        .spyOn(URL, "revokeObjectURL")
        .mockImplementation(() => undefined);
      const response = () =>
        new Response(text, {
          headers: {
            "content-type": "text/markdown; charset=utf-8",
            "content-disposition": 'attachment; filename="README.md"',
          },
        });
      try {
        action();
        await vi.waitFor(() => expect(guide().props.busy).toBe(false));
        expect(fetchReadme).not.toHaveBeenCalled();
        (sharing().props.onStateChange as (value: unknown) => void)(state);
        (guide().props.onPreviewReadme as () => void)();
        finish(response());
        await vi.waitFor(() => expect(guide().props.readmePreview).toBe(text));
        await vi.waitFor(() => expect(focus).toHaveBeenCalledOnce());
        expect(link.click).not.toHaveBeenCalled();
        expect(input.content).toBe("unapplied draft canary");
        action();
        action();
        expect(guide().props.busy).toBe(true);
        expect(fetchReadme).toHaveBeenCalledTimes(2);
        finish(response());
        await vi.waitFor(() => expect(link.click).toHaveBeenCalledOnce());
        expect(fetchReadme).toHaveBeenLastCalledWith(
          `/api/admin/sharing/readme?locale=${locale}`,
          {
            credentials: "same-origin",
            cache: "no-store",
          },
        );
        const file = createUrl.mock.calls[0][0] as Blob;
        expect(file.type).toBe("text/markdown;charset=utf-8");
        expect(await file.text()).toBe(text);
        expect(link.download).toBe("README.md");
        expect(link.href).toBe("blob:readme-fixture");
        expect(append).toHaveBeenCalledWith(link);
        expect(link.remove).toHaveBeenCalledOnce();
        expect(guide().props.notice).toContain(
          locale === "zh-TW" ? "請確認下載完成" : "Confirm it completed",
        );
        (sharing().props.onStateChange as (value: unknown) => void)({
          ...state,
          verified_content_sha256: "b".repeat(64),
        });
        expect(guide().props.readmePreview).toBeNull();
        action();
        finish(
          new Response(
            JSON.stringify({ error: { code: "SHARING_CONFLICT" } }),
            { status: 409 },
          ),
        );
        await vi.waitFor(() =>
          expect(guide().props.notice).toContain(
            locale === "zh-TW"
              ? "README 尚未取得"
              : "README could not be retrieved",
          ),
        );
        expect(link.click).toHaveBeenCalledOnce();
        expect(requestCalls).not.toHaveBeenCalled();
        expect(input.onStored).not.toHaveBeenCalled();
      } finally {
        createUrl.mockRestore();
        revokeUrl.mockRestore();
      }
    },
  );
  it.each(["zh-TW", "en"] as const)(
    "scopes success, failure and partial preparation to the initiating area in %s",
    async (locale) => {
      const zh = locale === "zh-TW";
      let failure: string | null = null;
      const request = vi.fn(async (path: string) => {
        if (path === failure) throw new Error("private-failure-canary");
        return {
          content: "unchanged public draft",
          revision: "saved",
          sprite_base64: null,
        };
      });
      const onStored = vi.fn();
      const input = {
        locale,
        content: "unchanged public draft",
        spriteBase64: null,
        revision: null,
        initialAccount: "fixture",
        selection: {
          eligible: true,
          reason: "",
          chat: {
            profile_id: "chat",
            model_id: "chat-model",
            status: "ready",
            tested: true,
          },
          embedding: {
            profile_id: "search",
            model_id: "search-model",
            status: "ready",
            tested: true,
          },
          selection: {
            chat_profile_id: "chat",
            embedding_profile_id: "search",
            generation: 1,
            updated_at: "",
          },
        },
        request: request as <T>(
          path: string,
          options?: RequestInit,
        ) => Promise<T>,
        onStored,
        onCreateDraft: vi.fn(),
        repositories: [],
        onAddClaim: vi.fn(),
      };
      const render = () => {
        hooks.cursor = 0;
        return elements(LocalPublishingWorkspace(input));
      };
      const section = () =>
        render().find(
          (node) =>
            node.props["aria-labelledby"] === "local-publication-heading",
        )!;
      const localAlerts = () =>
        elements(section()).filter(
          (node) =>
            (node.props.role === "alert" || node.props.role === "status") &&
            typeof node.props.children === "string" &&
            node.props.children !==
              (locale === "zh-TW"
                ? "正在讀取本機發布狀態…"
                : "Loading local publication status…"),
        );
      const share = () => render().find((node) => "onCopy" in node.props)!;
      const click = (name: string) => {
        const button = render().find(
          (node) => node.type === "button" && node.props.children === name,
        )!;
        expect(button.props.disabled).toBeFalsy();
        (button.props.onClick as () => void)();
      };
      const expectLocal = async (text: string) => {
        await vi.waitFor(() => {
          expect(localAlerts()).toHaveLength(1);
          expect(localAlerts()[0].props.children).toContain(text);
        });
        expect(share().props.notice).toBe("");
        expect(localAlerts()[0].props.children).not.toContain(
          "private-failure-canary",
        );
        expect(input.content).toBe("unchanged public draft");
      };

      click(zh ? "儲存本機草稿" : "Save local draft");
      await expectLocal(zh ? "已儲存在本機" : "Saved locally");
      expect(localAlerts()[0].props.role).toBe("status");
      expect(localAlerts()[0].props.className).toBeUndefined();
      expect(onStored).toHaveBeenCalledTimes(1);
      expect(request.mock.calls.map(([path]) => path)).toEqual([
        "/api/admin/portfolio",
      ]);

      failure = "/api/admin/portfolio";
      click(zh ? "儲存本機草稿" : "Save local draft");
      await expectLocal(zh ? "操作未完成" : "Could not complete");
      expect(localAlerts()[0].props.role).toBe("alert");
      expect(localAlerts()[0].props.className).toBe("publication-notice");
      expect(onStored).toHaveBeenCalledTimes(1);

      failure = "/api/admin/portfolio/prepare";
      click(zh ? "準備 NPC 並套用" : "Prepare and apply NPC");
      await expectLocal(zh ? "草稿已儲存在本機" : "draft was saved locally");
      expect(localAlerts()[0].props.children).toContain(
        zh ? "尚無法確認" : "could not be confirmed",
      );
      expect(onStored).toHaveBeenCalledTimes(2);

      failure = "/api/admin/portfolio/preview";
      click(zh ? "預覽作品集與卡片" : "Preview portfolio and card");
      await expectLocal(zh ? "操作未完成" : "Could not complete");

      const writeText = vi.fn().mockResolvedValue(undefined);
      vi.stubGlobal("navigator", { clipboard: { writeText } });
      const markdown = "[Pages](<https://fixture.github.io/project/>)";
      (share().props.onCopy as (value: string) => void)(markdown);
      await vi.waitFor(() =>
        expect(share().props.notice).toContain(zh ? "已複製" : "Copied"),
      );
      expect(writeText).toHaveBeenCalledWith(markdown);
      expect(localAlerts()).toHaveLength(0);

      writeText.mockRejectedValueOnce(new Error("private-failure-canary"));
      (share().props.onCopy as (value: string) => void)(markdown);
      await vi.waitFor(() =>
        expect(share().props.notice).toContain(
          zh ? "操作未完成" : "Could not complete",
        ),
      );
      expect(share().props.notice).not.toContain("private-failure-canary");
      expect(localAlerts()).toHaveLength(0);
    },
  );
});

function workspace(
  locale: "zh-TW" | "en",
  request: <T>(path: string, options?: RequestInit) => Promise<T>,
) {
  const input = {
    locale,
    request,
    content: "retained draft",
    spriteBase64: null,
    revision: "original",
    initialAccount: "fixture",
    selection: {
      eligible: true,
      reason: "",
      chat: {
        profile_id: "chat",
        model_id: "chat-model",
        status: "ready",
        tested: true,
      },
      embedding: {
        profile_id: "search",
        model_id: "search-model",
        status: "ready",
        tested: true,
      },
      selection: {
        chat_profile_id: "chat",
        embedding_profile_id: "search",
        generation: 1,
        updated_at: "",
      },
    },
    onStored: vi.fn(),
    onCreateDraft: vi.fn(),
    onConfigureModels: vi.fn(),
    repositories: [],
    onAddClaim: vi.fn(),
  };
  const render = () => {
    hooks.cursor = 0;
    return elements(LocalPublishingWorkspace(input));
  };
  const button = (label: string) =>
    render().find(
      (node) => node.type === "button" && node.props.children === label,
    )!;
  return { input, render, button };
}

it.each(["zh-TW", "en"] as const)(
  "keeps the save control focusable while blocking duplicate submissions in %s",
  async (locale) => {
    let finish!: (value: unknown) => void;
    const request = vi.fn(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    const view = workspace(locale, request as <T>() => Promise<T>);
    const label = locale === "zh-TW" ? "儲存本機草稿" : "Save local draft";
    const original = view.button(label);
    const click = original.props.onClick as () => void;
    click();
    click(); // Same-render activation must not send a second write.
    const busy = view.button(label);
    expect(busy.props.disabled).toBe(false);
    expect(busy.props["aria-disabled"]).toBe(true);
    (busy.props.onClick as () => void)();
    expect(request).toHaveBeenCalledTimes(1);
    finish({
      content: "retained draft",
      sprite_base64: null,
      revision: "saved",
    });
    await vi.waitFor(() =>
      expect(view.button(label).props["aria-disabled"]).toBe(false),
    );
    expect(view.button(label).props.disabled).toBe(false);
    expect(view.input.onStored).toHaveBeenCalledTimes(1);
  },
);

const sourceFailureCodes = new Set([
  "GITHUB_RATE_LIMITED",
  "GITHUB_ERROR",
  "GITHUB_TIMEOUT",
  "NOT_FOUND",
  "ARCHIVED_NOT_ALLOWED",
  "ARCHIVE_TOO_LARGE",
  "ARCHIVE_INVALID",
  "ARCHIVE_UNSAFE",
]);

const publicationErrors = [
  ["GITHUB_RATE_LIMITED", "GitHub 目前限制", "GitHub is limiting"],
  ["GITHUB_ERROR", "GitHub 暫時無法使用", "GitHub is temporarily unavailable"],
  [
    "GITHUB_TIMEOUT",
    "GitHub 暫時無法使用",
    "GitHub is temporarily unavailable",
  ],
  ["NOT_FOUND", "找不到 repository", "Repository not found"],
  ["ARCHIVED_NOT_ALLOWED", "repository 已封存", "repository is archived"],
  ["ARCHIVE_TOO_LARGE", "封存檔超過大小限制", "archive exceeds the size limit"],
  ["ARCHIVE_INVALID", "封存檔無效", "archive is invalid"],
  ["ARCHIVE_UNSAFE", "未通過安全檢查", "archive failed safety checks"],
  ["PORTFOLIO_CONFLICT", "核對最新草稿", "compare the latest draft"],
  ["PORTFOLIO_BUSY", "取消準備", "cancel preparation"],
  ["PORTFOLIO_MODEL_CHANGED", "重新測試", "retest"],
  ["EMBEDDING_PROBE_REQUIRED", "確認選用", "confirm both model selections"],
  ["CONFIG_INVALID", "必填欄位", "required fields"],
  ["PORTFOLIO_ASSET_REQUIRED", "角色與動畫", "Character & animation"],
  ["PAYLOAD_TOO_LARGE", "縮減草稿", "Reduce the draft"],
  ["PORTFOLIO_WRITE_FAILED", "存取權限", "access permissions"],
  ["PORTFOLIO_CORRUPT", "不要刪除", "do not delete"],
  ["EMBEDDING_REINDEX_INTERRUPTED", "重新開始", "start again"],
  ["EMBEDDING_REINDEX_CANCELLED", "重新開始", "start again"],
  ["EMBEDDING_REINDEX_TIMEOUT", "電腦資源", "computer resources"],
  ["PORTFOLIO_PREPARE_FAILED", "維護", "Maintenance"],
  ["EMBEDDING_REINDEX_FAILED", "維護", "Maintenance"],
  ["SERVICE_NOT_READY", "維護", "Maintenance"],
  ["REQUEST_FAILED", "網路連線", "network connection"],
  ["untrusted-runtime-canary", "無法確認原因", "cause is unknown"],
] as const;

describe.each(["zh-TW", "en"] as const)(
  "safe actionable publication failures in %s",
  (locale) => {
    it.each(publicationErrors)(
      "shows safe actionable failures for requests, partial saves and stored status: %s",
      async (code, zh, en) => {
        hooks.values = [];
        let mode: "save" | "prepare" | "status" = "save";
        const request = vi.fn(async (path: string) => {
          if (
            mode === "save" ||
            (mode === "prepare" && path.endsWith("/prepare"))
          )
            throw new Error(code);
          if (path.endsWith("/prepare"))
            return {
              state: "failed",
              index_ready: true,
              draft_changed: true,
              error_code: code,
              retry_at: null,
              revision: "saved",
              active_bundle_id: "previous",
            };
          return {
            content: "retained draft",
            sprite_base64: null,
            revision: "saved",
          };
        });
        const view = workspace(
          locale,
          request as <T>(path: string) => Promise<T>,
        );
        const alerts = () =>
          view.render().filter((node) => node.props.role === "alert");
        const expectRecovery = async () => {
          await vi.waitFor(() => expect(alerts()).toHaveLength(1), {
            interval: 1,
          });
          const text = elements(alerts()[0])
            .map((node) =>
              Children.toArray(node.props.children as ReactNode)
                .filter((child) => typeof child === "string")
                .join(""),
            )
            .join("");
          expect(text).toContain(locale === "zh-TW" ? zh : en);
          expect(text).not.toContain(code);
          if (sourceFailureCodes.has(code)) {
            expect(text).not.toMatch(/維護|Maintenance/);
            expect(text).not.toMatch(/重新測試|retest/);
          }
          expect(view.input.content).toBe("retained draft");
        };
        (
          view.button(locale === "zh-TW" ? "儲存本機草稿" : "Save local draft")
            .props.onClick as () => void
        )();
        await expectRecovery();
        expect(view.input.onStored).not.toHaveBeenCalled();
        mode = "prepare";
        (
          view.button(
            locale === "zh-TW" ? "準備 NPC 並套用" : "Prepare and apply NPC",
          ).props.onClick as () => void
        )();
        await expectRecovery();
        expect(alerts()[0].props.children).toContain(
          locale === "zh-TW" ? "草稿已儲存" : "draft was saved",
        );
        expect(view.input.onStored).toHaveBeenCalledTimes(1);
        mode = "status";
        (
          view.button(
            locale === "zh-TW" ? "準備 NPC 並套用" : "Prepare and apply NPC",
          ).props.onClick as () => void
        )();
        await expectRecovery();
        expect(
          view
            .render()
            .some((node) => node.type === "a" && node.props.href === "/"),
        ).toBe(true);
      },
    );
  },
);

it("maps a native network failure without showing the exception", async () => {
  const view = workspace("en", async () => {
    throw new TypeError("private-network-detail");
  });
  (view.button("Save local draft").props.onClick as () => void)();
  await vi.waitFor(() => {
    const alert = view.render().find((node) => node.props.role === "alert")!;
    expect(alert.props.children).toContain("network connection");
    expect(alert.props.children).not.toContain("private-network-detail");
  });
  expect(view.button("Save local draft").props["aria-disabled"]).toBe(false);
});

it.each(["zh-TW", "en"] as const)(
  "shows stored GitHub retry waits only while retry_at is in the future in %s",
  (locale) => {
    const now = vi
      .spyOn(Date, "now")
      .mockReturnValue(Date.parse("2026-10-20T00:00:00Z"));
    try {
      for (const retryAt of [
        "2026-10-20T00:02:00Z",
        null,
        "2026-10-19T23:59:59Z",
      ]) {
        hooks.values = [];
        const view = workspace(locale, async <T,>() => ({}) as T);
        view.render();
        hooks.values[1] = {
          state: "failed",
          index_ready: true,
          draft_changed: true,
          error_code: "GITHUB_RATE_LIMITED",
          retry_at: retryAt,
          revision: "saved",
          active_bundle_id: "previous",
          message: "private-upstream-exception-canary",
        };
        const alerts = view
          .render()
          .filter((node) => node.props.role === "alert");
        expect(alerts).toHaveLength(1);
        const text = elements(alerts[0])
          .flatMap((node) =>
            Children.toArray(node.props.children as ReactNode).filter(
              (child) => typeof child === "string",
            ),
          )
          .join("");
        expect(text).toContain(
          locale === "zh-TW" ? "GitHub 目前限制" : "GitHub is limiting",
        );
        if (retryAt === "2026-10-20T00:02:00Z") {
          expect(text).toContain(
            locale === "zh-TW"
              ? "請在約 2 分 0 秒 後再試。"
              : "Try again in about 2m 0s.",
          );
        } else {
          expect(text).not.toMatch(/請在約|Try again in about/);
        }
        expect(text).not.toMatch(/維護|Maintenance|重新測試|retest/);
        expect(text).not.toContain("private-upstream-exception-canary");
      }
    } finally {
      now.mockRestore();
    }
  },
);

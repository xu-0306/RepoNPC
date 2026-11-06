import {
  Children,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TailscaleLivePanel } from "./TailscaleLivePanel";
import {
  tailscaleErrorMessage,
  tailscaleGuide,
  type TailscaleState,
  type TailscaleStatus,
} from "./tailscaleFunnel";
import type { VisitorGatewayStatus } from "./VisitorGatewayPanel";
import { sectionRef } from "./sharingSections";

const hooks = vi.hoisted(() => ({
  values: [] as unknown[],
  cursor: 0,
  effects: [] as { index: number; run: () => void | (() => void) }[],
  cleanups: new Map<number, () => void>(),
}));
vi.mock("react", async (importOriginal) => {
  const react = await importOriginal<typeof import("react")>();
  const nextValue = (initial: unknown) => {
    const index = hooks.cursor++;
    if (!(index in hooks.values)) hooks.values[index] = initial;
    return index;
  };
  const same = (a: unknown[] | undefined, b: unknown[]) =>
    a?.length === b.length &&
    b.every((value, index) => Object.is(value, a[index]));
  return {
    ...react,
    useState: (initial: unknown) => {
      const index = nextValue(initial);
      return [
        hooks.values[index],
        (next: unknown) => {
          hooks.values[index] =
            typeof next === "function" ? next(hooks.values[index]) : next;
        },
      ];
    },
    useRef: (initial: unknown) => hooks.values[nextValue({ current: initial })],
    useCallback: (callback: unknown, deps: unknown[]) => {
      const index = nextValue(undefined);
      const previous = hooks.values[index] as
        | { deps: unknown[]; callback: unknown }
        | undefined;
      if (!same(previous?.deps, deps)) hooks.values[index] = { deps, callback };
      return (hooks.values[index] as { callback: unknown }).callback;
    },
    useEffect: (run: () => void | (() => void), deps: unknown[]) => {
      const index = nextValue(undefined);
      if (!same(hooks.values[index] as unknown[] | undefined, deps)) {
        hooks.values[index] = deps;
        hooks.effects.push({ index, run });
      }
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
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}
async function settle() {
  for (let index = 0; index < 8; index += 1) await Promise.resolve();
}
const FUNNEL = "https://other-host.example.ts.net:10000";
function tailscale(state: TailscaleState): TailscaleStatus {
  return {
    state,
    funnel_url: state === "live" || state === "ready" ? FUNNEL : null,
    port: 10000,
    version: "1.104.4",
  };
}
function gateway(
  overrides: Partial<VisitorGatewayStatus> = {},
): VisitorGatewayStatus {
  return {
    revision: 27,
    gateway_origin: null,
    pages_origin: "https://owner.github.io",
    enabled: false,
    listener_ready: false,
    error_code: null,
    local_ready: true,
    entry_configured: false,
    external_verified: false,
    verified_at: null,
    verification_method: null,
    active_bundle_id: "fixture",
    client_identity_mode: "aggregate",
    visitor_port: 9043,
    visitor_port_source: "owner",
    ...overrides,
  };
}
function panel(state: TailscaleState = "ready", locale: "zh-TW" | "en" = "en") {
  const request = vi.fn().mockResolvedValue(tailscale(state));
  const input: Parameters<typeof TailscaleLivePanel>[0] = {
    locale,
    request,
    pagesOrigin: "https://owner.github.io",
    gateway: gateway(),
    onChanged: vi.fn(),
  };
  const render = () => {
    hooks.cursor = 0;
    const node = TailscaleLivePanel(input);
    const tree = elements(node);
    const markup = renderToStaticMarkup(node);
    for (const effect of hooks.effects.splice(0)) {
      hooks.cleanups.get(effect.index)?.();
      const cleanup = effect.run();
      if (cleanup) hooks.cleanups.set(effect.index, cleanup);
    }
    return { tree, markup };
  };
  const button = (action: "start" | "stop" | "check") =>
    render().tree.find(
      (node) =>
        node.type === "button" &&
        node.props.children ===
          {
            start: locale === "en" ? "Turn on live chat" : "開啟即時聊天",
            stop: locale === "en" ? "Turn off live chat" : "關閉即時聊天",
            check: locale === "en" ? "Check again" : "重新檢查",
          }[action],
    );
  const click = (action: "start" | "stop" | "check") =>
    (button(action)!.props.onClick as () => void)();
  return { input, request, render, button, click };
}
beforeEach(() => {
  hooks.values = [];
  hooks.cursor = 0;
  hooks.effects = [];
  hooks.cleanups.clear();
  vi.stubGlobal("window", new EventTarget());
});
afterEach(() => {
  for (const cleanup of hooks.cleanups.values()) cleanup();
  vi.unstubAllGlobals();
});

const STATES: TailscaleState[] = [
  "unavailable_profile",
  "not_installed",
  "unsupported_version",
  "needs_login",
  "stopped",
  "offline",
  "https_disabled",
  "funnel_not_allowed",
  "no_free_port",
  "error",
  "ready",
  "live",
];

describe("Tailscale live panel states", () => {
  it.each(STATES)(
    "%s renders its bilingual instruction, official link and safe controls",
    async (state) => {
      for (const locale of ["zh-TW", "en"] as const) {
        hooks.values = [];
        hooks.cursor = 0;
        const view = panel(state, locale);
        view.input.gateway = gateway({
          enabled: state === "live",
          listener_ready: state === "live",
          gateway_origin: state === "live" ? FUNNEL : null,
        });
        expect(view.render().markup).toBe("");
        await settle();
        const { tree, markup } = view.render();
        if (state === "unavailable_profile") {
          expect(markup).toBe("");
        } else {
          const guide = tailscaleGuide(state, locale);
          const instruction = tree.find(
            (node) => node.props.id === "tailscale-live-instruction",
          )!;
          expect(renderToStaticMarkup(instruction)).toContain(guide.text);
          expect(guide.text).not.toMatch(/command|terminal|\.env|\d/i);
          const links = tree.filter((node) => node.type === "a");
          expect(links).toHaveLength(guide.link ? 1 : 0);
          if (guide.link) {
            expect(links[0].props.href).toBe(guide.link.href);
            expect(links[0].props.children).toBe(guide.link.label);
            expect(links[0].props.target).toBe("_blank");
            expect(links[0].props.rel).toBe("noreferrer noopener");
          }
          expect(
            tree.filter((node) => node.props.role === "status"),
          ).toHaveLength(1);
          expect(markup).not.toMatch(
            /<input|<pre|<code|password|token|9043|1\.104\.4/,
          );
          expect(markup.includes(FUNNEL)).toBe(state === "live");
          expect(Boolean(view.button("start"))).toBe(state === "ready");
          expect(Boolean(view.button("stop"))).toBe(state === "live");
          for (const button of tree.filter((node) => node.type === "button")) {
            expect(button.props.disabled).toBe(false);
            expect(button.props["aria-describedby"]).toBe(
              "tailscale-live-instruction",
            );
            expect(button.props.className).toContain("px-button");
          }
        }
        expect(view.request).toHaveBeenCalledExactlyOnceWith(
          "/api/admin/tailscale/status",
        );
        for (const cleanup of hooks.cleanups.values()) cleanup();
        hooks.cleanups.clear();
      }
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "%s explains a live Funnel with a stopped or mismatched visitor connection",
    async (locale) => {
      const view = panel("live", locale);
      view.render();
      await settle();
      const expected =
        locale === "zh-TW"
          ? "Funnel 已開啟，但訪客連線已停止。按「開啟即時聊天」重新啟動。"
          : "Funnel is on, but the visitor connection is stopped. Select Turn on live chat to start it again.";
      expect(view.render().markup).toContain(expected);
      expect(view.button("start")?.props.disabled).toBe(false);
      expect(view.button("stop")?.props.disabled).toBe(false);
      view.input.gateway = gateway({
        listener_ready: true,
        gateway_origin: "https://different.example.ts.net",
      });
      expect(view.render().markup).toContain(expected);
      expect(view.button("start")?.props.disabled).toBe(false);
      view.input.gateway = gateway({
        listener_ready: true,
        gateway_origin: FUNNEL,
      });
      expect(view.button("start")).toBeUndefined();
      expect(view.render().markup).toContain(
        locale === "zh-TW" ? "即時聊天：已開啟。" : "Live chat: on.",
      );
    },
  );

  it("offers stop for an enabled gateway even when Tailscale is not ready", async () => {
    const view = panel("offline");
    view.input.gateway = gateway({ enabled: true });
    view.render();
    await settle();
    expect(view.button("stop")?.props.disabled).toBe(false);
    expect(view.button("start")).toBeUndefined();
    view.input.gateway = null;
    expect(view.button("stop")).toBeUndefined();
  });

  it.each(["zh-TW", "en"] as const)(
    "%s disables start and describes the saved Pages prerequisite",
    async (locale) => {
      const view = panel("ready", locale);
      view.input.pagesOrigin = null;
      view.render();
      await settle();
      expect(view.button("start")?.props.disabled).toBe(true);
      expect(view.button("start")?.props["aria-describedby"]).toBe(
        "tailscale-live-instruction tailscale-live-pages",
      );
      expect(view.render().markup).toContain(
        locale === "zh-TW"
          ? `請先在${sectionRef(locale, "pages")}儲存 Pages 網址，再開啟即時聊天。`
          : `Save your Pages URL in ${sectionRef(locale, "pages")} before you turn on live chat.`,
      );
      view.click("start");
      expect(view.request).toHaveBeenCalledTimes(1);
      view.input.pagesOrigin = "https://owner.github.io";
      view.input.gateway = null;
      expect(view.button("start")?.props.disabled).toBe(true);
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "%s disables start until the NPC is prepared and says where to prepare it",
    async (locale) => {
      const view = panel("ready", locale);
      view.input.gateway = gateway({ local_ready: false });
      view.render();
      await settle();
      expect(view.button("start")?.props.disabled).toBe(true);
      expect(view.button("start")?.props["aria-describedby"]).toBe(
        "tailscale-live-instruction tailscale-live-prepared",
      );
      expect(view.render().markup).toContain(
        locale === "zh-TW"
          ? `請先在${sectionRef(locale, "prepare")}準備好 NPC，再開啟即時聊天。`
          : `Prepare the NPC in ${sectionRef(locale, "prepare")} before you turn on live chat.`,
      );
      view.click("start");
      expect(view.request).toHaveBeenCalledTimes(1);
      view.input.gateway = gateway({ local_ready: true });
      expect(view.button("start")?.props.disabled).toBe(false);
      expect(view.render().markup).not.toContain("tailscale-live-prepared");
    },
  );

  it.each(["ready", "unavailable_profile"] as const)(
    "%s opens the advanced disclosure only in the manual profile with a saved origin",
    async (state) => {
      const view = panel(state);
      view.input.children = (
        <details className="visitor-gateway__setup">
          <summary>Advanced</summary>
          <input type="url" />
          <pre>Manual setup</pre>
        </details>
      );
      view.input.gateway = gateway({ gateway_origin: FUNNEL });
      expect(view.render().markup).not.toContain('open=""');
      await settle();
      expect(view.render().markup.includes('open=""')).toBe(
        state === "unavailable_profile",
      );
      view.input.gateway = gateway();
      expect(view.render().markup).not.toContain('open=""');
    },
  );
});

describe("Tailscale requests", () => {
  it.each(["start", "stop"] as const)(
    "%s sends the exact revision once, applies the response and re-reads",
    async (action) => {
      const view = panel(action === "start" ? "ready" : "live");
      view.render();
      await settle();
      const response = deferred<{
        tailscale: TailscaleStatus;
        gateway: VisitorGatewayStatus;
      }>();
      const reread = deferred<TailscaleStatus>();
      view.request
        .mockReturnValueOnce(response.promise)
        .mockReturnValueOnce(reread.promise);
      const click = view.button(action)!.props.onClick as () => void;
      click();
      click();
      expect(view.request).toHaveBeenCalledTimes(2);
      expect(view.request).toHaveBeenNthCalledWith(
        2,
        `/api/admin/tailscale/funnel/${action}`,
        { method: "POST", body: JSON.stringify({ revision: 27 }) },
      );
      for (const button of view
        .render()
        .tree.filter((node) => node.type === "button"))
        expect(button.props.disabled).toBe(true);
      view.click("check");
      window.dispatchEvent(new Event("focus"));
      expect(view.request).toHaveBeenCalledTimes(2);
      const next = tailscale(action === "start" ? "live" : "ready");
      response.resolve({ tailscale: next, gateway: gateway() });
      await settle();
      expect(view.input.onChanged).toHaveBeenCalledOnce();
      expect(view.request).toHaveBeenNthCalledWith(
        3,
        "/api/admin/tailscale/status",
      );
      expect(view.render().markup.includes(FUNNEL)).toBe(action === "start");
      reread.resolve(next);
      await settle();
      expect(view.button("check")?.props.disabled).toBe(false);
    },
  );

  it.each(["TAILSCALE_NOT_READY", "TAILSCALE_FAILED", "GATEWAY_CONFLICT"])(
    "a failing start shows %s and re-reads without reporting success",
    async (code) => {
      const view = panel();
      view.render();
      await settle();
      view.request
        .mockRejectedValueOnce(new Error(code))
        .mockResolvedValueOnce(tailscale("offline"));
      view.click("start");
      await settle();
      const alert = view
        .render()
        .tree.find((node) => node.props.role === "alert")!;
      expect(alert.props.children).toBe(tailscaleErrorMessage(code, "en"));
      expect(view.render().markup).toContain(
        tailscaleGuide("offline", "en").text,
      );
      expect(view.request).toHaveBeenNthCalledWith(
        3,
        "/api/admin/tailscale/status",
      );
      expect(view.input.onChanged).not.toHaveBeenCalled();
    },
  );

  it("shows a failed initial read and recovers through Check again", async () => {
    const view = panel();
    view.request.mockRejectedValueOnce(new Error("AUTHENTICATION_REQUIRED"));
    expect(view.render().markup).toBe("");
    await settle();
    expect(view.render().markup).toContain(tailscaleGuide("error", "en").text);
    expect(
      view.render().tree.find((node) => node.props.role === "alert")?.props
        .children,
    ).toBe(tailscaleErrorMessage("AUTHENTICATION_REQUIRED", "en"));
    const second = deferred<TailscaleStatus>();
    view.request.mockReturnValueOnce(second.promise);
    const click = view.button("check")!.props.onClick as () => void;
    click();
    click();
    expect(view.request).toHaveBeenCalledTimes(2);
    expect(view.button("check")?.props.disabled).toBe(true);
    second.resolve(tailscale("ready"));
    await settle();
    expect(view.render().tree.some((node) => node.props.role === "alert")).toBe(
      false,
    );
    expect(view.button("start")?.props.disabled).toBe(false);
  });

  it.each([false, true])(
    "focus re-reads and drops an older %s response",
    async (rejectOld) => {
      const view = panel();
      const older = deferred<TailscaleStatus>();
      const newer = deferred<TailscaleStatus>();
      view.request
        .mockReturnValueOnce(older.promise)
        .mockReturnValueOnce(newer.promise);
      view.render();
      window.dispatchEvent(new Event("focus"));
      expect(view.request.mock.calls).toEqual([
        ["/api/admin/tailscale/status"],
        ["/api/admin/tailscale/status"],
      ]);
      newer.resolve(tailscale("ready"));
      await settle();
      expect(view.button("start")?.props.disabled).toBe(true);
      if (rejectOld) older.reject(new Error("TAILSCALE_FAILED"));
      else older.resolve(tailscale("not_installed"));
      await settle();
      expect(view.render().markup).toContain(
        tailscaleGuide("ready", "en").text,
      );
      expect(
        view.render().tree.some((node) => node.props.role === "alert"),
      ).toBe(false);
      expect(view.button("start")?.props.disabled).toBe(false);
      for (const cleanup of hooks.cleanups.values()) cleanup();
      window.dispatchEvent(new Event("focus"));
      expect(view.request).toHaveBeenCalledTimes(2);
    },
  );
});

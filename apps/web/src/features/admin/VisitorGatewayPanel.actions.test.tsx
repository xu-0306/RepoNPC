import {
  Children,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";
import { expect, it, vi } from "vitest";
import {
  VisitorGatewayPanel,
  type VisitorGatewayRequest,
  type VisitorGatewayStatus,
} from "./VisitorGatewayPanel";

// Follow the publication action suite: exercise controls without polling timers.
const hooks = vi.hoisted(() => ({ values: [] as unknown[], cursor: 0 }));
vi.mock("react", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react")>()),
  useEffect: vi.fn(),
  useCallback: (callback: unknown) => callback,
  useRef: (current: unknown) => ({ current }),
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
}));

function elements(node: ReactNode): ReactElement<Record<string, unknown>>[] {
  return Children.toArray(node).flatMap((child) =>
    isValidElement<Record<string, unknown>>(child)
      ? [child, ...elements(child.props.children as ReactNode)]
      : [],
  );
}

it.each(["zh-TW", "en"] as const)(
  "enables configured sharing and preserves readiness checks in %s",
  async (locale) => {
    for (const localReady of [true, false]) {
      const status: VisitorGatewayStatus = {
        revision: 7,
        gateway_origin: "https://another-host.example.ts.net",
        pages_origin: "https://another-owner.github.io",
        enabled: false,
        listener_ready: false,
        error_code: null,
        local_ready: localReady,
        entry_configured: true,
        external_verified: false,
        verified_at: null,
        verification_method: null,
        active_bundle_id: "another-bundle",
        client_identity_mode: "aggregate",
        visitor_port: 9043,
        visitor_port_source: "owner",
      };
      hooks.values = [status, false];
      hooks.cursor = 0;
      const request = vi.fn(async <T,>(): Promise<T> => status as T);
      const tree = elements(
        VisitorGatewayPanel({
          locale,
          request: request as VisitorGatewayRequest,
          pagesOrigin: "https://another-owner.github.io",
        }),
      );
      const fields = tree.find((node) => node.type === "fieldset")!;
      expect(fields.props.disabled).toBe(false);
      expect(fields.props["aria-disabled"]).toBe(false);
      const start = tree.find(
        (node) =>
          node.type === "button" &&
          node.props.children === (locale === "zh-TW" ? "啟動" : "Start"),
      )!;
      expect(start.props.disabled).toBe(!localReady);
      if (localReady) {
        (start.props.onClick as () => void)();
        await vi.waitFor(() =>
          expect(request).toHaveBeenCalledExactlyOnceWith(
            "/api/admin/visitor-gateway/start",
            { method: "POST", body: JSON.stringify({ revision: 7 }) },
          ),
        );
      } else {
        expect(request).not.toHaveBeenCalled();
      }
    }
  },
);

// ADR-081: the Pages address is never typed here. It is the origin of the
// Pages URL saved in the Pages section, and it is saved together with the
// Funnel URL or not at all.
const FUNNEL = "https://host.example.ts.net";

function statusFor(
  overrides: Partial<VisitorGatewayStatus> = {},
): VisitorGatewayStatus {
  return {
    revision: 7,
    gateway_origin: null,
    pages_origin: null,
    enabled: false,
    listener_ready: false,
    error_code: null,
    local_ready: true,
    entry_configured: false,
    external_verified: false,
    verified_at: null,
    verification_method: null,
    active_bundle_id: "another-bundle",
    client_identity_mode: "aggregate",
    visitor_port: 9043,
    visitor_port_source: "owner",
    ...overrides,
  };
}

function renderPanel(
  locale: "zh-TW" | "en",
  status: VisitorGatewayStatus,
  pagesOrigin: string | null,
  draftGateway?: string,
) {
  hooks.values = [status, false];
  // Index 5 is the panel's own draft (after the five gateway-hook states).
  if (draftGateway !== undefined)
    hooks.values[5] = {
      gateway: draftGateway,
      port: String(status.visitor_port),
      revision: status.revision,
      baseGateway: status.gateway_origin ?? "",
    };
  hooks.cursor = 0;
  const request = vi.fn(async <T,>(): Promise<T> => status as T);
  const tree = elements(
    VisitorGatewayPanel({
      locale,
      request: request as VisitorGatewayRequest,
      pagesOrigin,
    }),
  );
  const button = (label: string) =>
    tree.find(
      (node) => node.type === "button" && node.props.children === label,
    )!;
  const alerts = tree
    .filter((node) => node.props.role === "alert")
    .map((node) => String(node.props.children));
  return { tree, request, button, alerts };
}

it.each(["zh-TW", "en"] as const)(
  "saves the Pages origin of the saved Pages URL, never a typed one, in %s",
  async (locale) => {
    const save = locale === "zh-TW" ? "儲存" : "Save";
    // A root site and another owner's site: the body must follow the prop.
    for (const origin of [
      "https://account.github.io",
      "https://another-owner.github.io",
    ]) {
      const { button, request } = renderPanel(
        locale,
        statusFor(),
        origin,
        FUNNEL,
      );
      expect(button(save).props.disabled).toBe(false);
      (button(save).props.onClick as () => void)();
      await vi.waitFor(() =>
        expect(request).toHaveBeenCalledExactlyOnceWith(
          "/api/admin/visitor-gateway",
          {
            method: "PUT",
            body: JSON.stringify({
              revision: 7,
              gateway_origin: FUNNEL,
              pages_origin: origin,
            }),
          },
        ),
      );
    }
  },
);

it.each(["zh-TW", "en"] as const)(
  "asks for the Pages URL first when none is saved in %s",
  (locale) => {
    const { button, request, alerts } = renderPanel(
      locale,
      statusFor(),
      null,
      FUNNEL,
    );
    expect(button(locale === "zh-TW" ? "儲存" : "Save").props.disabled).toBe(
      true,
    );
    expect(alerts).toHaveLength(1);
    expect(alerts[0]).toContain(locale === "zh-TW" ? "第 2 段" : "section 2");
    expect(request).not.toHaveBeenCalled();
  },
);

it.each(["zh-TW", "en"] as const)(
  "shows no warning and no Save when only the Pages URL is set in %s",
  (locale) => {
    const { button, alerts } = renderPanel(
      locale,
      statusFor(),
      "https://account.github.io",
    );
    expect(button(locale === "zh-TW" ? "儲存" : "Save").props.disabled).toBe(
      true,
    );
    expect(alerts).toEqual([]);
  },
);

it.each(["zh-TW", "en"] as const)(
  "re-saves when the Pages URL changed after live chat was saved in %s",
  async (locale) => {
    const status = statusFor({
      gateway_origin: FUNNEL,
      pages_origin: "https://old-owner.github.io",
    });
    const { button, request } = renderPanel(
      locale,
      status,
      "https://new-owner.github.io",
    );
    expect(button(locale === "zh-TW" ? "儲存" : "Save").props.disabled).toBe(
      false,
    );
    // Start waits until the saved addresses match the Pages URL.
    expect(button(locale === "zh-TW" ? "啟動" : "Start").props.disabled).toBe(
      true,
    );
    (
      button(locale === "zh-TW" ? "儲存" : "Save").props.onClick as () => void
    )();
    await vi.waitFor(() =>
      expect(request).toHaveBeenCalledExactlyOnceWith(
        "/api/admin/visitor-gateway",
        {
          method: "PUT",
          body: JSON.stringify({
            revision: 7,
            gateway_origin: FUNNEL,
            pages_origin: "https://new-owner.github.io",
          }),
        },
      ),
    );
  },
);

it("clears both addresses together when the Funnel URL is cleared", async () => {
  const status = statusFor({
    gateway_origin: FUNNEL,
    pages_origin: "https://account.github.io",
  });
  const { button, request } = renderPanel(
    "en",
    status,
    "https://account.github.io",
    "",
  );
  (button("Save").props.onClick as () => void)();
  await vi.waitFor(() =>
    expect(request).toHaveBeenCalledExactlyOnceWith(
      "/api/admin/visitor-gateway",
      {
        method: "PUT",
        body: JSON.stringify({
          revision: 7,
          gateway_origin: null,
          pages_origin: null,
        }),
      },
    ),
  );
});

it.each([
  [null, false],
  [FUNNEL, true],
] as const)(
  "opens the live chat section only when a Funnel URL is saved (%s)",
  (gatewayOrigin, expectedOpen) => {
    const { tree } = renderPanel(
      "en",
      statusFor({
        gateway_origin: gatewayOrigin,
        pages_origin: gatewayOrigin ? "https://account.github.io" : null,
      }),
      "https://account.github.io",
    );
    const setup = tree.find(
      (node) =>
        node.type === "details" &&
        node.props.className === "visitor-gateway__setup",
    )!;
    expect(setup.props.open).toBe(expectedOpen);
  },
);

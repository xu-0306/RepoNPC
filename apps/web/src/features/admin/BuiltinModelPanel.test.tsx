import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import {
  BuiltinModelPanel,
  type BuiltinModelPanelProps,
} from "./BuiltinModelPanel";

function props(
  overrides: Partial<BuiltinModelPanelProps> = {},
): BuiltinModelPanelProps {
  return {
    locale: "en",
    info: {
      model_id: "official-pinned-model",
      display_name: "A local model",
      total_bytes: 2_005_123_456,
      license: "MIT",
      source_url: "https://example.org/models/pinned-revision",
      profile_id: null,
    },
    operation: null,
    pending: false,
    error: "",
    onDownload: vi.fn(),
    onCancel: vi.fn(),
    onRefresh: vi.fn(),
    onExternal: vi.fn(),
    onLater: vi.fn(),
    ...overrides,
  };
}

function operation(
  overrides: Partial<NonNullable<BuiltinModelPanelProps["operation"]>> = {},
): NonNullable<BuiltinModelPanelProps["operation"]> {
  return {
    operation_id: "operation-1",
    profile_id: "profile-1",
    model_id: "official-pinned-model",
    status: "running",
    completed: 125,
    total: 500,
    error_code: null,
    ...overrides,
  };
}

function render(overrides: Partial<BuiltinModelPanelProps> = {}) {
  return renderToStaticMarkup(<BuiltinModelPanel {...props(overrides)} />);
}

function expectAssociatedReferences(markup: string) {
  for (const match of markup.matchAll(
    /aria-(?:labelledby|describedby)="([^"]+)"/g,
  )) {
    for (const id of match[1].split(" ")) {
      expect(markup).toContain(`id="${id}"`);
    }
  }
}

describe("BuiltinModelPanel", () => {
  it("offers three choices without starting downloads or other actions on render", () => {
    const initial = props();
    const markup = renderToStaticMarkup(<BuiltinModelPanel {...initial} />);
    expect(markup).toContain("<summary>Download the built-in model</summary>");
    expect(markup).toContain("Use an external model service");
    expect(markup).toContain("Set up later and continue manual editing");
    expect(markup).toContain("<details>");
    expect(markup).not.toContain("<details open");
    expect(markup).toMatch(/<input[^>]+type="checkbox"/);
    expect(markup).not.toContain("checked=");
    expect(markup).toMatch(/<button[^>]+disabled=""[^>]*>Confirm and download/);
    expect(markup).toContain("requires a full reindex");
    expect(markup).toContain("license terms and download size");
    for (const callback of [
      initial.onDownload,
      initial.onCancel,
      initial.onRefresh,
      initial.onExternal,
      initial.onLater,
    ]) {
      expect(callback).not.toHaveBeenCalled();
    }
    expectAssociatedReferences(markup);
  });

  it("renders manifest size, license and public source rather than a fixed model size", () => {
    expect(render()).toContain("2.005 GB (2,005,123,456 bytes)");
    expect(render()).toContain("MIT");
    expect(render()).toContain(
      'href="https://example.org/models/pinned-revision"',
    );
    const nextInfo = { ...props().info!, total_bytes: 321_654_987 };
    const markup = render({ info: nextInfo });
    expect(markup).toContain("0.322 GB (321,654,987 bytes)");
    expect(markup).not.toContain("2,005,123,456");
  });

  it("renders equivalent Traditional Chinese choices and explicit consent", () => {
    const markup = render({ locale: "zh-TW" });
    expect(markup).toContain("下載內建模型");
    expect(markup).toContain("使用外部模型服務");
    expect(markup).toContain("稍後設定，繼續手動編輯");
    expect(markup).toContain("我同意");
    expect(markup).toContain("重新建立全部索引");
    expect(markup).toContain("2,005,123,456 bytes");
    expectAssociatedReferences(markup);
  });

  it("labels byte progress and cancellation while leaving external/manual choices available", () => {
    const markup = render({ operation: operation(), pending: true });
    expect(markup).toContain('max="500" value="125"');
    expect(markup).toContain("Model download progress");
    const progressId = markup.match(/<progress id="([^"]+)"/)?.[1];
    expect(markup).toContain(`for="${progressId}"`);
    expect(markup).toContain("Cancel download");
    expect(markup).toMatch(
      /<button type="button">Use an external model service/,
    );
    expect(markup).toMatch(
      /<button type="button" aria-describedby="[^"]+">Set up later/,
    );
    expect(markup).toContain('role="status" aria-live="polite"');
    expectAssociatedReferences(markup);
  });

  it("uses indeterminate progress for unknown totals and bounds stale byte counts", () => {
    const markup = render({
      operation: operation({ completed: null, total: null }),
    });
    expect(markup).toMatch(
      /<progress id="[^"]+" aria-describedby="[^"]+"><\/progress>/,
    );
    expect(markup).toContain("Waiting for download progress information");
    expect(
      render({ operation: operation({ completed: 900, total: 500 }) }),
    ).toContain('max="500" value="500"');
    expect(render({ operation: operation({ total: 0 }) })).not.toContain(
      'max="0"',
    );
  });

  it.each([
    ["cancelled", "Agree and resume", "cancelled"],
    ["failed", "Agree and retry", "did not finish"],
  ])("offers consent-gated recovery for %s", (status, action, description) => {
    const markup = render({ operation: operation({ status }) });
    expect(markup).toContain('<details open="">');
    expect(markup).toContain(description);
    expect(markup).toMatch(
      new RegExp(`<button[^>]+disabled=""[^>]*>${action}`),
    );
    expect(markup).not.toContain("checked=");
    expect(markup).not.toContain("<progress");
    expectAssociatedReferences(markup);
  });

  it.each(["en", "zh-TW"] as const)(
    "separates download success from testing and public activation in %s",
    (locale) => {
      const markup = render({
        locale,
        operation: operation({ status: "succeeded" }),
      });
      expect(markup).toContain(
        locale === "en"
          ? "Test model&quot; and confirm its analysis role"
          : "「測試模型」，並確認它的分析角色",
      );
      expect(markup).toContain(
        locale === "en"
          ? "does not activate public answers"
          : "不會啟用公開回答服務",
      );
      expect(markup).not.toContain("<progress");
      expect(markup).not.toContain("Cancel download");
    },
  );

  it("explains deferred builds and preserves manual editing", () => {
    const markup = render();
    expect(markup).toContain(
      "RepoNPC blocks automatic builds until models are ready",
    );
    expect(markup).toContain("You can continue editing content manually");
    expectAssociatedReferences(markup);
  });

  it("uses fixed safe errors and does not expose operation identifiers or credentials", () => {
    const secret =
      "api_key=secret-token https://private-host.invalid/internal C:\\owner\\model";
    const markup = render({
      error: secret,
      operation: operation({
        status: secret,
        error_code: secret,
        operation_id: secret,
        profile_id: secret,
      }),
    });
    expect(markup).toContain('role="alert"');
    expect(markup).toContain("The operation could not be completed");
    expect(markup).not.toContain(secret);
    expect(markup).not.toContain("private-host");
    expect(markup).not.toContain("secret-token");
    expect(markup).not.toContain('type="password"');
  });

  it("blocks consent until download metadata and a safe public source are available", () => {
    expect(render({ info: null })).toContain(
      "Download information is unavailable",
    );
    for (const source_url of [
      "javascript:alert(1)",
      "https://user:secret@example.org/",
      "file:///C:/owner/model",
    ]) {
      const markup = render({ info: { ...props().info!, source_url } });
      expect(markup).not.toContain(`href="${source_url}"`);
      expect(markup).toContain("Download information is unavailable");
      expect(markup).toMatch(/<input[^>]+disabled=""/);
      expectAssociatedReferences(markup);
    }
  });
});

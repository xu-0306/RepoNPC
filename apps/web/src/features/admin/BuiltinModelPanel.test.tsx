import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import {
  BuiltinModelPanel,
  type BuiltinModelPanelProps,
  type GpuRuntimeInfo,
} from "./BuiltinModelPanel";

function gpu(overrides: Partial<GpuRuntimeInfo> = {}): GpuRuntimeInfo {
  return {
    state: "can_install",
    gpu_name: "NVIDIA GeForce RTX 3090",
    driver_version: "610.88",
    minimum_driver: 580,
    download_bytes: 1_330_778_450,
    required_free_bytes: 3_992_335_350,
    operation: null,
    ...overrides,
  };
}

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
      compute_device: "cpu",
      gpu_available: false,
      gpu_runtime: gpu({
        state: "no_nvidia_gpu",
        gpu_name: null,
        driver_version: null,
      }),
    },
    operation: null,
    gpuOperation: null,
    pending: false,
    error: "",
    deviceError: "",
    onDevice: vi.fn(),
    onDownload: vi.fn(),
    onInstallGpu: vi.fn(),
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

describe("BuiltinModelPanel compute device", () => {
  const withProfile = (
    overrides: Partial<NonNullable<BuiltinModelPanelProps["info"]>> = {},
  ) => ({ ...props().info!, profile_id: "profile-1", ...overrides });

  it("offers no device choice before the built-in model has a profile", () => {
    expect(render()).not.toContain("builtin-device");
  });

  it.each([
    ["en", "Compute device", "CPU (default", "GPU (NVIDIA", "cannot use a GPU"],
    ["zh-TW", "運算裝置", "CPU（預設", "GPU（NVIDIA", "目前無法使用 GPU"],
  ] as const)(
    "keeps the GPU option disabled and says why in %s when no GPU support exists",
    (locale, label, cpu, gpu, missing) => {
      const markup = render({ locale, info: withProfile() });
      expect(markup).toContain(label);
      expect(markup).toContain(cpu);
      expect(markup).toContain(`<option value="gpu" disabled="">${gpu}`);
      expect(markup).toContain(missing);
      expect(markup).toMatch(/<option value="cpu" selected="">/);
      expectAssociatedReferences(markup);
    },
  );

  it("enables the GPU option when GPU support is present and selects the saved device", () => {
    const available = render({
      info: withProfile({ gpu_available: true, compute_device: "gpu" }),
    });
    expect(available).not.toMatch(/<option value="gpu" disabled/);
    expect(available).toMatch(/<option value="gpu" selected="">/);
    expect(available).toContain("loads the model on it to check");
    // A saved GPU choice stays selectable after the support disappears, so the
    // owner can see it and switch back to the CPU.
    expect(
      render({ info: withProfile({ compute_device: "gpu" }) }),
    ).not.toMatch(/<option value="gpu" disabled/);
  });

  it("locks the device while busy and shows a device failure as an alert", () => {
    const markup = render({
      info: withProfile({ gpu_available: true }),
      pending: true,
      deviceError: "The model keeps using the CPU.",
    });
    expect(markup).toMatch(/<select[^>]+disabled=""/);
    expect(markup).toContain(
      '<p role="alert">The model keeps using the CPU.</p>',
    );
  });
});

describe("BuiltinModelPanel GPU support", () => {
  const withGpu = (
    runtime: Partial<GpuRuntimeInfo> = {},
    info: Partial<NonNullable<BuiltinModelPanelProps["info"]>> = {},
  ) => ({
    ...props().info!,
    profile_id: "profile-1",
    gpu_runtime: gpu(runtime),
    ...info,
  });
  const gpuOperation = (
    overrides: Partial<NonNullable<BuiltinModelPanelProps["operation"]>> = {},
  ) =>
    operation({
      profile_id: "",
      model_id: "gpu-runtime",
      completed: 665_389_225,
      total: 1_330_778_450,
      ...overrides,
    });
  const install = (label: string) =>
    new RegExp(`<button[^>]+disabled=""[^>]*>${label}`);

  it.each([
    [
      "en",
      "Download and install GPU support",
      "Detected graphics card: NVIDIA GeForce RTX 3090 (driver 610.88)",
      "About 1.3 GB to download, and about 4 GB of free disk space",
      "I agree to download the GPU build",
    ],
    [
      "zh-TW",
      "下載並安裝 GPU 支援",
      "NVIDIA GeForce RTX 3090 (驅動程式 610.88)",
      "需下載約 1.3 GB，安裝期間約需 4 GB 可用磁碟空間",
      "我同意從 PyPI",
    ],
  ] as const)(
    "offers the one-step install with size and explicit consent in %s",
    (locale, label, found, size, consent) => {
      const markup = render({ locale, info: withGpu() });
      expect(markup).toContain(found);
      expect(markup).toContain(size);
      expect(markup).toContain(consent);
      expect(markup).toContain('href="https://docs.nvidia.com/cuda/eula/');
      expect(markup).toMatch(install(label));
      expect(markup).not.toContain("checked=");
      expectAssociatedReferences(markup);
    },
  );

  it.each([
    [
      "no_nvidia_gpu",
      "no NVIDIA graphics card was detected",
      "沒有偵測到 NVIDIA 顯示卡",
    ],
    ["driver_too_old", "version 580 or newer is required", "需要 580 以上"],
    ["gpu_too_old", "RTX 20 / GTX 16 series", "RTX 20／GTX 16 系列"],
    [
      "unsupported_platform",
      "64-bit Windows started from the Windows launcher",
      "64 位元環境",
    ],
  ] as const)(
    "explains %s in both languages and offers no install",
    (state, english, chinese) => {
      const en = render({ info: withGpu({ state }) });
      const zh = render({ locale: "zh-TW", info: withGpu({ state }) });
      expect(en).toContain(english);
      expect(en).toContain("cannot use a GPU right now");
      expect(en).not.toContain("I agree to download the GPU build");
      expect(zh).toContain(chinese);
      expect(zh).toContain("目前無法使用 GPU");
      expect(zh).not.toContain("我同意從 PyPI");
      expectAssociatedReferences(en);
    },
  );

  it("asks for a restart once the runtime is installed", () => {
    const markup = render({ info: withGpu({ state: "restart_required" }) });
    expect(markup).toContain("Close RepoNPC completely");
    expect(markup).not.toContain("Download and install GPU support");
    const done = render({
      info: withGpu(),
      gpuOperation: gpuOperation({ status: "succeeded" }),
    });
    expect(done).toMatch(
      /<p id="[^"]+" role="status">GPU support is installed/,
    );
    expect(done).not.toContain("Download and install GPU support");
  });

  it("shows no install once the GPU already works", () => {
    const markup = render({ info: withGpu({}, { gpu_available: true }) });
    expect(markup).toContain("loads the model on it to check");
    expect(markup).not.toContain("Download and install GPU support");
  });

  it("labels byte progress and cancellation while installing and locks the other choices", () => {
    const markup = render({ info: withGpu(), gpuOperation: gpuOperation() });
    expect(markup).toContain('max="1330778450" value="665389225"');
    expect(markup).toContain("0.7 GB / 1.3 GB");
    expect(markup).toContain("GPU support installation progress");
    expect(markup).toContain("Cancel installation");
    expect(markup).toContain("Downloading, verifying and testing GPU support");
    expect(markup).toMatch(/<select[^>]+disabled=""/);
    // The model download consent and the GPU consent are both locked.
    expect(markup.match(/<input[^>]+disabled=""/g)).toHaveLength(2);
    expectAssociatedReferences(markup);
  });

  it("locks the GPU install while the model download runs", () => {
    const markup = render({ info: withGpu(), operation: operation() });
    expect(markup.match(/<input[^>]+disabled=""/g)).toHaveLength(2);
    expect(markup).not.toContain("Cancel installation");
  });

  it("names the failure the user can act on and never shows raw codes", () => {
    const check = render({
      info: withGpu(),
      gpuOperation: gpuOperation({
        status: "failed",
        error_code: "GPU_RUNTIME_SELF_CHECK",
        completed: null,
        total: null,
      }),
    });
    expect(check).toContain("the GPU test did not pass");
    expect(check).toMatch(install("Agree and retry"));
    expect(check).not.toContain("GPU_RUNTIME_SELF_CHECK");
    const secret = "api_key=secret-token C:\\owner\\wheel";
    const generic = render({
      info: withGpu(),
      gpuOperation: gpuOperation({ status: "failed", error_code: secret }),
    });
    expect(generic).toContain("The installation did not finish");
    expect(generic).not.toContain("secret-token");
    expect(
      render({
        locale: "zh-TW",
        info: withGpu(),
        gpuOperation: gpuOperation({
          status: "failed",
          error_code: "BUILTIN_DOWNLOAD_DISK_SPACE",
        }),
      }),
    ).toContain("磁碟可用空間不足");
  });

  it("shows an install request failure as the device alert", () => {
    const markup = render({
      info: withGpu(),
      deviceError: "This host does not meet the requirements.",
    });
    expect(markup).toContain(
      '<p role="alert">This host does not meet the requirements.</p>',
    );
  });
});

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

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import {
  ModelGuidancePanel,
  type ModelGuidancePanelProps,
  type ModelGuidanceEntry,
} from "./ModelGuidancePanel";

function props(
  overrides: Partial<ModelGuidancePanelProps> = {},
): ModelGuidancePanelProps {
  return {
    locale: "en",
    pending: false,
    error: "",
    hardware: null,
    onCheck: vi.fn(),
    models: [],
    onChoose: vi.fn(),
    ...overrides,
  };
}

function model(
  grade: ModelGuidanceEntry["suitability"]["grade"],
): ModelGuidanceEntry {
  return {
    model_id: `fixture-model-${grade}:4b`,
    quantization_id: "fixture-q4",
    parameter_count: 4_000_000_000,
    bits_per_weight: 4,
    download_bytes: 2_100_000_000,
    memory_overhead_bytes: 1_000_000_000,
    last_reviewed: "2026-10-03",
    source_url: "https://example.org/fixture-model",
    license_id: "MIT",
    license_url: "https://example.org/fixture-license",
    envelope_evidence: {
      provider: "ollama",
      model_revision: "fixture-revision",
      tested_on: "2026-10-03",
      tested_locales: ["zh-TW", "en"],
      cases_passed: 8,
      cases_total: 8,
    },
    suitability: {
      grade,
      execution_target: "cpu",
      reason_codes: ["SPEED_ESTIMATE_UNAVAILABLE"],
      weight_bytes: 2_000_000_000,
      estimated_memory_bytes: 3_000_000_000,
      required_disk_bytes: 2_100_000_000,
      available_memory_bytes: 6_000_000_000,
      available_disk_bytes: 8_000_000_000,
      speed_estimate_tokens_per_second: null,
    },
  };
}

function render(overrides: Partial<ModelGuidancePanelProps> = {}) {
  return renderToStaticMarkup(<ModelGuidancePanel {...props(overrides)} />);
}

describe("ModelGuidancePanel", () => {
  it("offers an explicitly requested device check without running it on render", () => {
    const initial = props();
    const markup = renderToStaticMarkup(<ModelGuidancePanel {...initial} />);
    expect(initial.onCheck).not.toHaveBeenCalled();
    expect(markup).toContain("Check this host");
    expect(markup).toContain(
      "RepoNPC reads device information only when you press",
    );
    const reason = markup.match(/aria-describedby="([^"]+)"/)?.[1];
    expect(markup).toContain(`id="${reason}"`);
    const heading = markup.match(/aria-labelledby="([^"]+)"/)?.[1];
    expect(markup).toContain(`id="${heading}"`);
    expect(markup.match(/Unknown \(information not available\)/g)).toHaveLength(
      5,
    );
    expect(markup).not.toContain("0 GB");
  });

  it("keeps unknown distinct from measured zero and displays all memory readings", () => {
    const markup = render({
      hardware: {
        host_ram_bytes: 16_000_000_000,
        free_memory_bytes: null,
        free_disk_bytes: 0,
        gpu_vram_bytes: 8_000_000_000,
        gpu_free_vram_bytes: null,
      },
    });
    expect(markup).toContain("16 GB (16,000,000,000 bytes)");
    expect(markup).toContain("8 GB (8,000,000,000 bytes)");
    expect(markup).toContain("0 GB (0 bytes)");
    expect(markup.match(/Unknown \(information not available\)/g)).toHaveLength(
      2,
    );
    for (const label of [
      "Host RAM",
      "Available host memory",
      "Available disk space",
      "GPU VRAM",
      "Available GPU VRAM",
    ]) {
      expect(markup).toContain(`<dt>${label}</dt>`);
    }
  });

  it("does not turn invalid hardware readings into a resource claim", () => {
    const markup = render({
      hardware: {
        host_ram_bytes: -1,
        free_memory_bytes: Number.NaN,
        free_disk_bytes: Number.POSITIVE_INFINITY,
        gpu_vram_bytes: null,
        gpu_free_vram_bytes: null,
      },
    });
    expect(markup.match(/Unknown \(information not available\)/g)).toHaveLength(
      5,
    );
    expect(markup).not.toContain("NaN");
    expect(markup).not.toContain("Infinity");
  });

  it.each(["en", "zh-TW"] as const)(
    "announces completed checks and the result count in %s",
    (locale) => {
      const markup = render({
        locale,
        models: [model("suitable")],
        hardware: {
          host_ram_bytes: null,
          free_memory_bytes: null,
          free_disk_bytes: null,
          gpu_vram_bytes: null,
          gpu_free_vram_bytes: null,
        },
      });
      expect(markup).toMatch(
        locale === "en"
          ? /<p role="status">Check complete; some readings may still be unknown\. Model entries available for reference: 1<\/p>/
          : /<p role="status">檢查完成；資料仍可能未知。 可參考的模型項目數: 1<\/p>/,
      );
      expect(
        render({
          locale,
          error: "failed",
          hardware: {
            host_ram_bytes: null,
            free_memory_bytes: null,
            free_disk_bytes: null,
            gpu_vram_bytes: null,
            gpu_free_vram_bytes: null,
          },
        }),
      ).not.toContain(locale === "en" ? "Check complete" : "檢查完成");
    },
  );

  it("honestly describes the empty catalog, weight estimate and host/cloud data flows", () => {
    const markup = render({
      hardware: {
        host_ram_bytes: null,
        free_memory_bytes: null,
        free_disk_bytes: null,
        gpu_vram_bytes: null,
        gpu_free_vram_bytes: null,
      },
    });
    expect(markup).toContain(
      "No recommended answer model has passed the complete verification yet",
    );
    expect(markup).toContain("bring your own Ollama or compatible API service");
    expect(markup).toContain(
      "Preparing the NPC and live chat still require tested, selected",
    );
    expect(markup).toContain("Parameter count × bits per parameter ÷ 8");
    expect(markup).toContain("does not guarantee speed, performance");
    expect(markup).toContain("computes embeddings on this host");
    expect(markup).toContain("receive selected text or prompts");
    expect(markup).toContain("privacy, and data processing terms before use");
    expect(markup).toContain(
      'href="https://canirun.ai/" target="_blank" rel="noopener noreferrer"',
    );
    expect(markup).not.toContain("<iframe");
  });

  it("shows all resource grades and catalog facts without activating or promising speed", () => {
    const models = (
      ["suitable", "marginal", "not_recommended", "unknown"] as const
    ).map(model);
    const choose = vi.fn();
    const markup = render({ models, onChoose: choose });
    expect(markup).toContain("Model entries available for reference: 4");
    expect(markup).toContain(
      "Check live test evidence and your device for each entry",
    );
    expect(markup).toContain("does not guarantee suitability or speed");
    expect(markup).not.toContain("There is no verified model catalog yet");
    for (const label of [
      "Suitable (capacity estimate)",
      "Marginal (limited headroom)",
      "Not recommended (insufficient capacity)",
      "Insufficient information to assess",
    ])
      expect(markup).toContain(label);
    for (const entry of models) expect(markup).toContain(entry.model_id);
    expect(markup).toContain("3 GB (3,000,000,000 bytes)");
    expect(markup).toContain("Host CPU; GPU acceleration is not included");
    expect(markup).toContain("8/8 · zh-TW / en · 2026-10-03");
    expect(markup).toContain('href="https://example.org/fixture-license"');
    expect(markup).toContain("fixture-revision");
    expect(markup).toContain(
      "No download or model switch happens automatically",
    );
    expect(markup).toContain("No speed estimate is available");
    expect(choose).not.toHaveBeenCalled();
  });

  it.each(["en", "zh-TW"] as const)(
    "explains known capacity failures and unknown observations in %s",
    (locale) => {
      const candidate = model("unknown");
      candidate.suitability.available_memory_bytes = null;
      candidate.suitability.reason_codes = [
        "HOST_RAM_UNKNOWN",
        "FREE_MEMORY_UNKNOWN",
        "FREE_DISK_INSUFFICIENT",
        "BANDWIDTH_UNKNOWN",
        "SPEED_ESTIMATE_UNAVAILABLE",
        "FUTURE_REASON",
      ];
      const markup = render({ locale, models: [candidate], pending: true });
      expect(markup).toContain(
        locale === "en"
          ? "Available disk space is insufficient"
          : "可用磁碟空間不足",
      );
      expect(markup).toContain(
        locale === "en"
          ? "Available memory could not be measured"
          : "無法取得可用記憶體",
      );
      expect(markup).not.toContain("FUTURE_REASON");
      expect(markup).toMatch(/<button type="button" disabled="" aria-label=/);
    },
  );

  it("renders equivalent Traditional Chinese guidance and unknown readings", () => {
    const markup = render({
      locale: "zh-TW",
      hardware: {
        host_ram_bytes: null,
        free_memory_bytes: null,
        free_disk_bytes: null,
        gpu_vram_bytes: null,
        gpu_free_vram_bytes: null,
      },
    });
    expect(markup).toContain("檢查這台主機");
    expect(markup).toContain("只有按下");
    expect(markup.match(/未知（尚未取得資料）/g)).toHaveLength(5);
    expect(markup).toContain("目前沒有通過完整驗證的推薦回答模型");
    expect(markup).toContain("自行準備 Ollama 或相容 API 服務");
    expect(markup).toContain("完成內容、預覽、儲存與備份設定");
    expect(markup).toContain("不是速度、效能或能否執行的保證");
    expect(markup).toContain("這台主機處理向量");
    expect(markup).toContain("會收到所選文字或提示詞");
    expect(markup).toContain("隱私與資料處理條款");
  });

  it("labels pending checks and displays safe errors without exposing private details", () => {
    const secret =
      "device_probe_failed secret-token https://private-host.invalid/ C:\\owner\\model";
    const markup = render({ pending: true, error: secret });
    expect(markup).toMatch(
      /<button type="button" disabled="" aria-describedby="[^"]+">Check this host/,
    );
    expect(markup).toContain('role="status"');
    expect(markup).toContain('role="alert"');
    expect(markup).toContain("Device information could not be read");
    expect(markup).not.toContain("secret-token");
    expect(markup).not.toContain("private-host");
    expect(markup).not.toContain("device_probe_failed");
    expect(markup).not.toContain('type="password"');
  });
});

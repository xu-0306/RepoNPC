import { useEffect, useId, useRef, useState } from "react";
import type { Locale } from "../../i18n/messages";

export interface ModelDeviceHardware {
  host_ram_bytes: number | null;
  free_memory_bytes: number | null;
  free_disk_bytes: number | null;
  gpu_vram_bytes: number | null;
  gpu_free_vram_bytes: number | null;
}

export interface ModelGuidancePanelProps {
  locale: Locale;
  pending: boolean;
  error: string;
  hardware: ModelDeviceHardware | null;
  onCheck: () => void;
  models: ModelGuidanceEntry[];
  onChoose: (model: ModelGuidanceEntry) => void;
}

export interface ModelGuidanceEntry {
  model_id: string;
  quantization_id: string;
  parameter_count: number;
  bits_per_weight: number;
  download_bytes: number;
  memory_overhead_bytes: number;
  last_reviewed: string;
  source_url: string;
  license_id: string;
  license_url: string;
  envelope_evidence: {
    provider: "ollama" | "openai_compatible" | "vllm";
    model_revision: string;
    tested_on: string;
    tested_locales: string[];
    cases_passed: number;
    cases_total: number;
  };
  suitability: {
    grade: "suitable" | "marginal" | "not_recommended" | "unknown";
    execution_target: "cpu" | "gpu";
    reason_codes: string[];
    weight_bytes: number;
    estimated_memory_bytes: number;
    required_disk_bytes: number;
    available_memory_bytes: number | null;
    available_disk_bytes: number | null;
    speed_estimate_tokens_per_second: null;
  };
}

const COPY = {
  "zh-TW": {
    heading: "選擇模型前先了解裝置與資料流向",
    description: "只有按下「檢查這台主機」才會讀取裝置資訊。",
    check: "檢查這台主機",
    pending: "正在檢查這台主機，請稍候。",
    checked: "檢查完成；資料仍可能未知。",
    unknown: "未知（尚未取得資料）",
    ram: "主機記憶體",
    freeMemory: "可用主機記憶體",
    freeDisk: "可用磁碟空間",
    vram: "GPU 記憶體",
    freeVram: "可用 GPU 記憶體",
    estimate:
      "模型參數量 × 每個參數的位元數 ÷ 8 只能估算權重大小。實際執行還需要額外記憶體。這不是速度、效能或能否執行的保證。",
    compare: "在 canirun.ai 查看模型與裝置估算（外部網站）",
    empty:
      "目前沒有通過完整驗證的推薦回答模型。你可以自行準備 Ollama 或相容 API 服務，在「分析與回答模型」新增、測試並選用；單次連線測試不代表回答品質已通過完整驗證。",
    beforeCheck:
      "「檢查這台主機」只讀取容量資訊；若有已驗證的模型項目，才會顯示估算。你仍需自行準備回答模型服務。",
    manual:
      "還沒有模型服務？可選「先手動建立作品集」，完成內容、預覽、儲存與備份設定。準備 NPC 和實際試聊仍需要已測試並選用的回答模型及資料查找模型。",
    catalog: "可參考的模型項目數",
    suitable: "適合（容量估算）",
    marginal: "勉強可用（餘裕有限）",
    not_recommended: "不建議（容量不足）",
    unknownGrade: "資料不足，無法評估",
    target: "估算執行位置",
    cpu: "主機 CPU；不包含 GPU 加速",
    gpu: "GPU；仍需服務支援",
    weights: "估算權重大小",
    memory: "估算執行記憶體",
    disk: "所需下載空間",
    download: "下載大小",
    parameters: "參數量",
    bits: "每個權重的位元數",
    overhead: "額外記憶體預留",
    available: "本次可用記憶體",
    tested: "雙語回答格式測試",
    reviewed: "最近核對",
    revision: "實測模型版本",
    source: "模型來源（外部網站）",
    license: "授權（外部網站）",
    choose: "前往設定此回答模型",
    next: "選擇只會開啟設定。仍需確認服務、明確新增、測試並選用；不會自動下載或切換模型。",
    details: "估算與實測資料",
    runtime: "以下是容量估算，實測回答格式通過不代表你的服務已可用。",
    evidence:
      "清單項目仍須核對實機測試證據與你的裝置；項目數不代表適合或速度保證。",
    disclosure:
      "內建本機內容查找模型會在這台主機處理向量。設定的外部模型服務（包括雲端服務）會收到所選文字或提示詞。使用前請確認各服務的授權、隱私與資料處理條款。",
    error: "未能取得裝置資訊。請確認本機服務可用後再檢查。",
  },
  en: {
    heading: "Understand your device and data flow before choosing models",
    description:
      'RepoNPC reads device information only when you press "Check this host".',
    check: "Check this host",
    pending: "Checking this host. Please wait.",
    checked: "Check complete; some readings may still be unknown.",
    unknown: "Unknown (information not available)",
    ram: "Host RAM",
    freeMemory: "Available host memory",
    freeDisk: "Available disk space",
    vram: "GPU VRAM",
    freeVram: "Available GPU VRAM",
    estimate:
      "Parameter count × bits per parameter ÷ 8 estimates only weight size. Running a model needs additional memory. This does not guarantee speed, performance, or that the model will run.",
    compare: "Compare model and device estimates on canirun.ai (external site)",
    empty:
      "No recommended answer model has passed the complete verification yet. You can bring your own Ollama or compatible API service, then add, test and select it under Analysis and answer model. A connection test alone does not establish verified answer quality.",
    beforeCheck:
      "Check this host reads only capacity information. It displays estimates only when verified entries exist. You still need your own answer model service.",
    manual:
      "No model service yet? Choose the manual portfolio route to write content, preview, save and back up configuration. Preparing the NPC and live chat still require tested, selected answer and content finder models.",
    catalog: "Model entries available for reference",
    suitable: "Suitable (capacity estimate)",
    marginal: "Marginal (limited headroom)",
    not_recommended: "Not recommended (insufficient capacity)",
    unknownGrade: "Insufficient information to assess",
    target: "Estimated execution target",
    cpu: "Host CPU; GPU acceleration is not included",
    gpu: "GPU; provider support is still required",
    weights: "Estimated weight size",
    memory: "Estimated runtime memory",
    disk: "Required download space",
    download: "Download size",
    parameters: "Parameter count",
    bits: "Bits per weight",
    overhead: "Extra memory allowance",
    available: "Memory available at this check",
    tested: "Bilingual answer format tests",
    reviewed: "Last reviewed",
    revision: "Tested model revision",
    source: "Model source (external site)",
    license: "License (external site)",
    choose: "Set up this answer model",
    next: "Choosing only opens setup. Confirm the service. Explicitly add, test and select the model. No download or model switch happens automatically.",
    details: "Estimate and test facts",
    runtime:
      "These are capacity estimates. Passing answer format tests does not mean your service is ready.",
    evidence:
      "Check live test evidence and your device for each entry. The entry count does not guarantee suitability or speed.",
    disclosure:
      "The built-in local content finder computes embeddings on this host. Configured external model services, including cloud services, receive selected text or prompts. Confirm each service's license, privacy, and data processing terms before use.",
    error:
      "Device information could not be read. Check that the local service is available, then try again.",
  },
};

const REASONS: Record<string, Record<Locale, string>> = {
  TOTAL_MEMORY_INSUFFICIENT: {
    "zh-TW": "裝置總記憶體不足。",
    en: "Total device memory is insufficient.",
  },
  FREE_MEMORY_INSUFFICIENT: {
    "zh-TW": "可用記憶體不足。",
    en: "Available memory is insufficient.",
  },
  FREE_DISK_INSUFFICIENT: {
    "zh-TW": "可用磁碟空間不足。",
    en: "Available disk space is insufficient.",
  },
  MEMORY_HEADROOM_LOW: {
    "zh-TW": "記憶體餘裕低於 20%，其他程式可能影響執行。",
    en: "Memory headroom is below 20%; other applications may affect execution.",
  },
  DISK_HEADROOM_LOW: {
    "zh-TW": "磁碟餘裕低於 20%。",
    en: "Disk headroom is below 20%.",
  },
  HOST_RAM_UNKNOWN: {
    "zh-TW": "無法取得主機總記憶體。",
    en: "Total host memory could not be measured.",
  },
  FREE_MEMORY_UNKNOWN: {
    "zh-TW": "無法取得可用記憶體。",
    en: "Available memory could not be measured.",
  },
  GPU_VRAM_UNKNOWN: {
    "zh-TW": "無法取得 GPU 總記憶體。",
    en: "Total GPU memory could not be measured.",
  },
  FREE_VRAM_UNKNOWN: {
    "zh-TW": "無法取得可用 GPU 記憶體。",
    en: "Available GPU memory could not be measured.",
  },
  FREE_DISK_UNKNOWN: {
    "zh-TW": "無法取得可用磁碟空間。",
    en: "Available disk space could not be measured.",
  },
  BANDWIDTH_UNKNOWN: {
    "zh-TW": "未測量記憶體頻寬。",
    en: "Memory bandwidth has not been measured.",
  },
  SPEED_ESTIMATE_UNAVAILABLE: {
    "zh-TW": "目前沒有可用的速度估算。",
    en: "No speed estimate is available.",
  },
};

export function ModelGuidancePanel({
  locale,
  pending,
  error,
  hardware,
  onCheck,
  models,
  onChoose,
}: ModelGuidancePanelProps) {
  const copy = COPY[locale];
  const id = useId();
  const formatMemory = (bytes: number | null | undefined) =>
    bytes != null && Number.isSafeInteger(bytes) && bytes >= 0
      ? `${new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(bytes / 1_000_000_000)} GB (${new Intl.NumberFormat(locale).format(bytes)} bytes)`
      : copy.unknown;
  const readings = [
    [copy.ram, hardware?.host_ram_bytes],
    [copy.freeMemory, hardware?.free_memory_bytes],
    [copy.freeDisk, hardware?.free_disk_bytes],
    [copy.vram, hardware?.gpu_vram_bytes],
    [copy.freeVram, hardware?.gpu_free_vram_bytes],
  ] as const;

  return (
    <section
      className="admin-surface model-guidance"
      aria-labelledby={`${id}-heading`}
    >
      <h2 id={`${id}-heading`}>{copy.heading}</h2>
      <p id={`${id}-check-reason`}>{copy.description}</p>
      <button
        type="button"
        disabled={pending}
        aria-describedby={`${id}-check-reason`}
        onClick={onCheck}
      >
        {copy.check}
      </button>
      <p role="status">
        {pending
          ? copy.pending
          : hardware && !error
            ? `${copy.checked} ${copy.catalog}: ${models.length}`
            : ""}
      </p>
      {error && <p role="alert">{copy.error}</p>}
      <dl>
        {readings.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{formatMemory(value)}</dd>
          </div>
        ))}
      </dl>
      <p>{copy.estimate}</p>
      <a href="https://canirun.ai/" target="_blank" rel="noopener noreferrer">
        {copy.compare}
      </a>
      {models.length > 0 ? (
        <>
          <p>
            {copy.catalog}:{" "}
            {new Intl.NumberFormat(locale).format(models.length)}
          </p>
          <p>{copy.evidence}</p>
          <p>{copy.runtime}</p>
          <ul className="model-card-list">
            {models.map((model) => {
              const estimate = model.suitability;
              const grade =
                estimate.grade === "unknown"
                  ? copy.unknownGrade
                  : copy[estimate.grade];
              return (
                <li
                  className="model-card"
                  key={`${model.model_id}:${model.quantization_id}`}
                >
                  <h3>
                    {model.model_id} · {model.quantization_id}
                  </h3>
                  <p>
                    <strong>{grade}</strong>
                  </p>
                  <dl>
                    <dt>{copy.target}</dt>
                    <dd>
                      {estimate.execution_target === "gpu"
                        ? copy.gpu
                        : copy.cpu}
                    </dd>
                    <dt>{copy.memory}</dt>
                    <dd>{formatMemory(estimate.estimated_memory_bytes)}</dd>
                    <dt>{copy.available}</dt>
                    <dd>{formatMemory(estimate.available_memory_bytes)}</dd>
                    <dt>{copy.disk}</dt>
                    <dd>{formatMemory(estimate.required_disk_bytes)}</dd>
                  </dl>
                  <ul>
                    {estimate.reason_codes.map((reason) => (
                      <li key={reason}>
                        {REASONS[reason]?.[locale] ?? copy.unknownGrade}
                      </li>
                    ))}
                  </ul>
                  <p>
                    {copy.tested}: {model.envelope_evidence.cases_passed}/
                    {model.envelope_evidence.cases_total} · zh-TW / en ·{" "}
                    {model.envelope_evidence.tested_on}
                  </p>
                  <p>
                    {copy.reviewed}: {model.last_reviewed}
                  </p>
                  <a
                    href={model.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {copy.source}
                  </a>
                  {" · "}
                  <a
                    href={model.license_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {copy.license}: {model.license_id}
                  </a>
                  <details className="model-card__technical">
                    <summary>{copy.details}</summary>
                    <dl>
                      <dt>{copy.parameters}</dt>
                      <dd>
                        {new Intl.NumberFormat(locale).format(
                          model.parameter_count,
                        )}
                      </dd>
                      <dt>{copy.bits}</dt>
                      <dd>{model.bits_per_weight}</dd>
                      <dt>{copy.weights}</dt>
                      <dd>{formatMemory(estimate.weight_bytes)}</dd>
                      <dt>{copy.overhead}</dt>
                      <dd>{formatMemory(model.memory_overhead_bytes)}</dd>
                      <dt>{copy.download}</dt>
                      <dd>{formatMemory(model.download_bytes)}</dd>
                      <dt>{copy.revision}</dt>
                      <dd>{model.envelope_evidence.model_revision}</dd>
                    </dl>
                  </details>
                  <p>{copy.next}</p>
                  <button
                    type="button"
                    disabled={pending}
                    onClick={() => onChoose(model)}
                    aria-label={`${copy.choose} ${model.model_id} · ${model.quantization_id}`}
                  >
                    {copy.choose}
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      ) : (
        <p>{hardware === null ? copy.beforeCheck : copy.empty}</p>
      )}
      <p>{copy.manual}</p>
      <p>{copy.disclosure}</p>
    </section>
  );
}

export function ModelGuidanceSetup({
  locale,
  request,
  onChoose,
}: {
  locale: Locale;
  request: <T>(path: string, init?: RequestInit) => Promise<T>;
  onChoose: (model: ModelGuidanceEntry) => void;
}) {
  const [hardware, setHardware] = useState<ModelDeviceHardware | null>(null);
  const [models, setModels] = useState<ModelGuidanceEntry[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const lifetime = useRef(0);
  useEffect(() => {
    const generation = ++lifetime.current;
    return () => {
      lifetime.current = generation + 1;
    };
  }, [request]);
  async function check() {
    const generation = lifetime.current;
    setPending(true);
    setError("");
    try {
      const value = await request<{
        hardware: ModelDeviceHardware;
        models: ModelGuidanceEntry[];
      }>("/api/admin/model-guidance/device-check", {
        method: "POST",
        body: "{}",
      });
      if (generation !== lifetime.current) return;
      setHardware(value.hardware);
      setModels(value.models);
    } catch {
      if (generation === lifetime.current) setError("device_check_failed");
    } finally {
      if (generation === lifetime.current) setPending(false);
    }
  }
  return (
    <ModelGuidancePanel
      locale={locale}
      pending={pending}
      error={error}
      hardware={hardware}
      models={models}
      onChoose={onChoose}
      onCheck={() => void check()}
    />
  );
}

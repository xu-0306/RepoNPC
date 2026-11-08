import { useId, useState } from "react";

import { chromeLocale } from "../../i18n/languages";
import type { LanguageTag as Locale } from "../../i18n/languages";
import type {
  BuiltinModelOperation,
  GpuRuntimeInfo,
} from "./BuiltinModelPanel";
import { CheckboxField } from "./CheckboxField";

export interface GpuRuntimeSupportProps {
  locale: Locale;
  helpId: string;
  runtime: GpuRuntimeInfo;
  operation: BuiltinModelOperation | null;
  pending: boolean;
  // Another model operation is running; the owned operations share one lane.
  blocked: boolean;
  onInstall: () => void;
  onCancel: () => void;
}

const LICENSE_URL = "https://docs.nvidia.com/cuda/eula/index.html";

const COPY = {
  "zh-TW": {
    found: "偵測到的顯示卡",
    driver: "驅動程式",
    intro:
      "這台主機有可用的 NVIDIA 顯示卡，但還沒有 GPU 版執行環境。可以一鍵安裝：檔案放在資料夾內，不會更動 Windows 或 Python 環境。",
    size: (download: string, free: string) =>
      `需下載約 ${download}，安裝期間約需 ${free} 可用磁碟空間。`,
    consent:
      "我同意從 PyPI（files.pythonhosted.org）下載 ONNX Runtime GPU 版與 NVIDIA CUDA、cuDNN 函式庫，安裝到這台主機的資料夾，並已閱讀 NVIDIA 授權條款。",
    license: "查看 NVIDIA CUDA 授權條款",
    install: "下載並安裝 GPU 支援",
    retry: "同意並重試",
    cancel: "取消安裝",
    progress: "GPU 支援安裝進度",
    unknown: "等待安裝進度資訊。",
    pending: "正在處理操作，請稍候。",
    restart:
      "GPU 支援已安裝並通過驗證。請完全關閉 RepoNPC（包含啟動器視窗）後重新開啟，之後就能選擇 GPU。",
    noGpu:
      "這台主機目前無法使用 GPU：沒有偵測到 NVIDIA 顯示卡。想用 GPU，可改選「使用外部模型服務」連到 Ollama。",
    driverOld: (minimum: number) =>
      `這台主機目前無法使用 GPU：NVIDIA 驅動程式版本太舊（需要 ${minimum} 以上）。請到 NVIDIA 官方網站更新驅動程式，再按「更新狀態」。`,
    gpuOld:
      "這台主機目前無法使用 GPU：這張顯示卡太舊，需要 RTX 20／GTX 16 系列（Turing）或更新的 NVIDIA 顯示卡。可改選「使用外部模型服務」連到 Ollama。",
    unsupported:
      "這台主機目前無法使用 GPU：一鍵安裝只支援以 Windows 啟動器執行的 64 位元環境。可改選「使用外部模型服務」連到 Ollama。",
    states: {
      queued: "安裝已排入佇列。",
      running:
        "正在下載、驗證並測試 GPU 支援。下載完成後的測試可能再花一兩分鐘，請不要關閉 RepoNPC。",
      cancelled: "安裝已取消。確認同意後可以重新開始；已驗證的檔案會保留續用。",
      failed:
        "安裝未完成。請確認網路與磁碟空間，再確認同意並重試；已驗證的檔案會保留續用。",
    },
    failures: {
      GPU_RUNTIME_SELF_CHECK:
        "檔案已下載，但 GPU 測試沒有通過，所以沒有啟用。請更新 NVIDIA 驅動程式後重試，或改選「使用外部模型服務」連到 Ollama。",
      BUILTIN_DOWNLOAD_DISK_SPACE:
        "磁碟可用空間不足。請清出空間後再確認同意並重試。",
      GPU_RUNTIME_PATH:
        "資料夾的路徑太長，無法解壓縮。請把 RepoNPC 移到較短的路徑後重試。",
    },
  },
  en: {
    found: "Detected graphics card",
    driver: "driver",
    intro:
      "This host has a usable NVIDIA graphics card but not the GPU build of the runtime. You can install it in one step: the files go into the data folder and Windows and the Python environment are left alone.",
    size: (download: string, free: string) =>
      `About ${download} to download, and about ${free} of free disk space while installing.`,
    consent:
      "I agree to download the GPU build of ONNX Runtime and the NVIDIA CUDA and cuDNN libraries from PyPI (files.pythonhosted.org) into this host's data folder, and I have read the NVIDIA license terms.",
    license: "View the NVIDIA CUDA license terms",
    install: "Download and install GPU support",
    retry: "Agree and retry",
    cancel: "Cancel installation",
    progress: "GPU support installation progress",
    unknown: "Waiting for installation progress information.",
    pending: "An operation is in progress. Please wait.",
    restart:
      "GPU support is installed and verified. Close RepoNPC completely, including the launcher window, and open it again; then you can choose the GPU.",
    noGpu:
      "This host cannot use a GPU right now: no NVIDIA graphics card was detected. To use a GPU, choose Use an external model service and connect to Ollama.",
    driverOld: (minimum: number) =>
      `This host cannot use a GPU right now: the NVIDIA driver is too old (version ${minimum} or newer is required). Update the driver from NVIDIA's website, then press Refresh status.`,
    gpuOld:
      "This host cannot use a GPU right now: this graphics card is too old. It needs an RTX 20 / GTX 16 series (Turing) or newer NVIDIA card. You can choose Use an external model service and connect to Ollama.",
    unsupported:
      "This host cannot use a GPU right now: one-step installation only supports 64-bit Windows started from the Windows launcher. You can choose Use an external model service and connect to Ollama.",
    states: {
      queued: "The installation is queued.",
      running:
        "Downloading, verifying and testing GPU support. The test after the download can take another minute or two; do not close RepoNPC.",
      cancelled:
        "The installation was cancelled. Confirm your consent to start again; verified files are kept and reused.",
      failed:
        "The installation did not finish. Check the network and disk space, then confirm your consent to retry; verified files are kept and reused.",
    },
    failures: {
      GPU_RUNTIME_SELF_CHECK:
        "The files were downloaded but the GPU test did not pass, so nothing was turned on. Update the NVIDIA driver and retry, or choose Use an external model service and connect to Ollama.",
      BUILTIN_DOWNLOAD_DISK_SPACE:
        "There is not enough free disk space. Free some space, then confirm your consent and retry.",
      GPU_RUNTIME_PATH:
        "The data folder path is too long to unpack into. Move RepoNPC to a shorter path and retry.",
    },
  },
};

function validBytes(value: number | null): value is number {
  return value !== null && Number.isSafeInteger(value) && value >= 0;
}

function gigabytes(bytes: number, locale: Locale): string {
  const value = new Intl.NumberFormat(locale, {
    maximumFractionDigits: 1,
  }).format(bytes / 1_000_000_000);
  return `${value} GB`;
}

export function GpuRuntimeSupport({
  locale,
  helpId,
  runtime,
  operation,
  pending,
  blocked,
  onInstall,
  onCancel,
}: GpuRuntimeSupportProps) {
  const copy = COPY[chromeLocale(locale)];
  const id = useId();
  const [consented, setConsented] = useState(false);
  const status = operation?.status;
  const active = status === "queued" || status === "running";
  const succeeded = status === "succeeded";
  const complete = succeeded || runtime.state === "restart_required";
  const retryable = status === "cancelled" || status === "failed";
  const installable = runtime.state === "can_install" && !complete;
  const progress =
    operation &&
    validBytes(operation.completed) &&
    validBytes(operation.total) &&
    operation.total > 0
      ? { completed: operation.completed, total: operation.total }
      : null;
  const help = complete
    ? copy.restart
    : runtime.state === "can_install"
      ? copy.intro
      : runtime.state === "driver_too_old"
        ? copy.driverOld(runtime.minimum_driver)
        : runtime.state === "gpu_too_old"
          ? copy.gpuOld
          : runtime.state === "unsupported_platform"
            ? copy.unsupported
            : copy.noGpu;
  const failure =
    status === "failed" &&
    operation?.error_code &&
    Object.hasOwn(copy.failures, operation.error_code)
      ? copy.failures[operation.error_code as keyof typeof copy.failures]
      : null;
  const statusText =
    failure ??
    (status && Object.hasOwn(copy.states, status)
      ? copy.states[status as keyof typeof copy.states]
      : copy.pending);

  return (
    <>
      <p id={helpId} role={succeeded ? "status" : undefined}>
        {help}
      </p>
      {runtime.gpu_name && (
        <p>
          {copy.found}: {runtime.gpu_name}
          {runtime.driver_version
            ? ` (${copy.driver} ${runtime.driver_version})`
            : ""}
        </p>
      )}
      {installable && (
        <>
          <p>
            {copy.size(
              gigabytes(runtime.download_bytes, locale),
              gigabytes(runtime.required_free_bytes, locale),
            )}
          </p>
          <a href={LICENSE_URL}>{copy.license}</a>
          <CheckboxField
            checked={consented}
            disabled={pending || active || blocked}
            onChange={(event) => setConsented(event.target.checked)}
          >
            <span id={`${id}-consent`}>{copy.consent}</span>
          </CheckboxField>
          <button
            type="button"
            disabled={!consented || pending || active || blocked}
            aria-describedby={[
              `${id}-consent`,
              ...(operation ? [`${id}-status`] : []),
            ].join(" ")}
            onClick={() => {
              if (consented && !pending && !active && !blocked) onInstall();
            }}
          >
            {retryable ? copy.retry : copy.install}
          </button>
          {operation && (
            <p id={`${id}-status`} role="status" aria-live="polite">
              {statusText}
            </p>
          )}
          {active && (
            <>
              <label htmlFor={`${id}-progress`}>{copy.progress}</label>
              <progress
                id={`${id}-progress`}
                aria-describedby={`${id}-status`}
                max={progress?.total}
                value={
                  progress
                    ? Math.min(progress.completed, progress.total)
                    : undefined
                }
              />
              <p>
                {progress
                  ? `${gigabytes(progress.completed, locale)} / ${gigabytes(progress.total, locale)}`
                  : copy.unknown}
              </p>
              <button
                type="button"
                disabled={pending}
                aria-describedby={`${id}-status`}
                onClick={onCancel}
              >
                {copy.cancel}
              </button>
            </>
          )}
        </>
      )}
    </>
  );
}

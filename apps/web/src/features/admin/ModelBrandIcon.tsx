import ollamaIcon from "@lobehub/icons-static-svg/icons/ollama.svg?no-inline";
import openAiIcon from "@lobehub/icons-static-svg/icons/openai.svg?no-inline";
import qwenIcon from "@lobehub/icons-static-svg/icons/qwen.svg?no-inline";
import vllmIcon from "@lobehub/icons-static-svg/icons/vllm.svg?no-inline";

export type ModelProvider = "ollama" | "openai_compatible" | "vllm";

const PROVIDER_ICONS: Record<ModelProvider, string> = {
  ollama: ollamaIcon,
  openai_compatible: openAiIcon,
  vllm: vllmIcon,
};

export function ModelBrandIcon({
  provider,
  modelId,
}: {
  provider: ModelProvider | null | undefined;
  modelId?: string | null;
}) {
  const normalizedModel = modelId?.toLowerCase() ?? "";
  const icon = normalizedModel.includes("qwen")
    ? qwenIcon
    : normalizedModel.includes("gpt")
      ? openAiIcon
      : provider
        ? PROVIDER_ICONS[provider]
        : null;

  if (!icon) return null;
  return (
    <span aria-hidden="true" className="model-brand-icon">
      <img alt="" src={icon} />
    </span>
  );
}

export function ProviderBrandIcon({ provider }: { provider: ModelProvider }) {
  return (
    <span aria-hidden="true" className="model-brand-icon">
      <img alt="" src={PROVIDER_ICONS[provider]} />
    </span>
  );
}

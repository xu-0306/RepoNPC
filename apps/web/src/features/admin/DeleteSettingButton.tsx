import type { Locale } from "../../i18n/messages";

export function DeleteSettingButton({
  locale,
  name,
  kind,
  pending,
  blockedReason,
  onDelete,
}: {
  locale: Locale;
  name: string;
  kind: "connection" | "model";
  pending: boolean;
  blockedReason?: string;
  onDelete: () => void;
}) {
  const label = locale === "zh-TW" ? "刪除設定" : "Delete setting";
  const message =
    locale === "zh-TW"
      ? `確定刪除「${name}」的${kind === "connection" ? "連線" : "模型"}設定？此操作無法復原，但不會卸載 AI 服務或模型檔案。${kind === "connection" ? "若仍有模型使用此連線，請先刪除或改用其他連線。" : "之後若要使用，需重新新增並測試。"}`
      : `Delete the ${kind === "connection" ? "connection" : "model"} setting for “${name}”? This cannot be undone. It does not uninstall AI services or model files. ${kind === "connection" ? "Remove or reassign models using this connection first." : "To use it again, add and test it again."}`;
  return (
    <>
      <button
        type="button"
        disabled={pending || Boolean(blockedReason)}
        aria-label={`${label}: ${name}`}
        onClick={() => {
          if (!pending && !blockedReason && window.confirm(message)) onDelete();
        }}
      >
        {label}
      </button>
      {blockedReason && <p className="model-card__note">{blockedReason}</p>}
    </>
  );
}

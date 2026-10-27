import type { Locale } from "../../i18n/messages";
import { ConfirmButton } from "./ConfirmDialog";

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
  const title =
    locale === "zh-TW"
      ? `刪除「${name}」的${kind === "connection" ? "連線" : "模型"}設定？`
      : `Delete the ${kind === "connection" ? "connection" : "model"} setting for “${name}”?`;
  const description =
    locale === "zh-TW"
      ? `此操作無法復原，但不會卸載 AI 服務或模型檔案。${kind === "connection" ? "若仍有模型使用此連線，請先刪除或改用其他連線。" : "之後若要使用，需重新新增並測試。"}`
      : `This cannot be undone. It does not uninstall AI services or model files. ${kind === "connection" ? "Remove or reassign models using this connection first." : "To use it again, add and test it again."}`;
  return (
    <>
      <ConfirmButton
        locale={locale}
        title={title}
        description={description}
        confirmLabel={locale === "zh-TW" ? "刪除設定" : "Delete setting"}
        destructive
        disabled={pending || Boolean(blockedReason)}
        aria-label={`${label}: ${name}`}
        onConfirm={() => {
          if (!pending && !blockedReason) onDelete();
        }}
      >
        {label}
      </ConfirmButton>
      {blockedReason && <p className="model-card__note">{blockedReason}</p>}
    </>
  );
}

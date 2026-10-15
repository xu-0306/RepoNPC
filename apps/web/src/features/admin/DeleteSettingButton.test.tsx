import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { ConfirmButton } from "./ConfirmDialog";
import { DeleteSettingButton } from "./DeleteSettingButton";

describe("DeleteSettingButton", () => {
  it.each([true, false])(
    "deletes only after confirmation (%s)",
    (confirmed) => {
      const onDelete = vi.fn();
      const element = DeleteSettingButton({
        locale: "en",
        name: "My gateway",
        kind: "connection",
        pending: false,
        onDelete,
      });
      const button = element.props.children[0];
      expect(button.type).toBe(ConfirmButton);
      expect(button.props.title).toContain("My gateway");
      expect(button.props.description).toContain("does not uninstall");
      expect(button.props.description).toContain("This cannot be undone.");
      expect(button.props.description).toContain(
        "Remove or reassign models using this connection first.",
      );
      expect(button.props.confirmLabel).toBe("Delete");
      expect(button.props.destructive).toBe(true);
      expect(onDelete).not.toHaveBeenCalled();
      if (confirmed) button.props.onConfirm();
      expect(onDelete).toHaveBeenCalledTimes(confirmed ? 1 : 0);
    },
  );

  it.each([
    { pending: true },
    { pending: false, blockedReason: "Still active" },
  ])("blocks unsafe/repeated deletion: %j", (state) => {
    const onDelete = vi.fn();
    const element = DeleteSettingButton({
      locale: "zh-TW",
      name: "模型",
      kind: "model",
      onDelete,
      ...state,
    });
    expect(renderToStaticMarkup(element)).toContain('disabled=""');
    const button = element.props.children[0];
    expect(button.type).toBe(ConfirmButton);
    expect(button.props.disabled).toBe(true);
    expect(button.props.confirmLabel).toBe("刪除");
    button.props.onConfirm();
    expect(onDelete).not.toHaveBeenCalled();
  });
});

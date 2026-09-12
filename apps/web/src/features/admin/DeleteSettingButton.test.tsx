import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DeleteSettingButton } from "./DeleteSettingButton";

afterEach(() => vi.unstubAllGlobals());

describe("DeleteSettingButton", () => {
  it.each([true, false])(
    "deletes only after confirmation (%s)",
    (confirmed) => {
      const confirm = vi.fn(() => confirmed);
      vi.stubGlobal("window", { confirm });
      const onDelete = vi.fn();
      const element = DeleteSettingButton({
        locale: "en",
        name: "My gateway",
        kind: "connection",
        pending: false,
        onDelete,
      });
      element.props.children[0].props.onClick();
      expect(confirm).toHaveBeenCalledWith(
        expect.stringContaining("My gateway"),
      );
      expect(confirm).toHaveBeenCalledWith(
        expect.stringContaining("does not uninstall"),
      );
      expect(onDelete).toHaveBeenCalledTimes(confirmed ? 1 : 0);
    },
  );

  it.each([
    { pending: true },
    { pending: false, blockedReason: "Still active" },
  ])("blocks unsafe/repeated deletion: %j", (state) => {
    const confirm = vi.fn(() => true);
    vi.stubGlobal("window", { confirm });
    const onDelete = vi.fn();
    const element = DeleteSettingButton({
      locale: "zh-TW",
      name: "模型",
      kind: "model",
      onDelete,
      ...state,
    });
    expect(renderToStaticMarkup(element)).toContain('disabled=""');
    element.props.children[0].props.onClick();
    expect(confirm).not.toHaveBeenCalled();
    expect(onDelete).not.toHaveBeenCalled();
  });
});

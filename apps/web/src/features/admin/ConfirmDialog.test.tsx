import {
  Children,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";
import {
  Button,
  Dialog,
  Heading,
  Modal,
  ModalOverlay,
} from "react-aria-components";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ConfirmButton,
  ConfirmDialogView,
  useConfirmDialog,
} from "./ConfirmDialog";

// Node has no overlay portal. Reuse the existing hook-state test pattern to
// exercise our handlers and promises; real focus behavior needs a browser.
const hooks = vi.hoisted(() => ({
  values: [] as unknown[],
  cursor: 0,
  cleanup: undefined as (() => void) | undefined,
}));
vi.mock("react", async (importOriginal) => {
  const react = await importOriginal<typeof import("react")>();
  return {
    ...react,
    useId: () => "confirm-description",
    useCallback: (callback: unknown) => callback,
    useEffect: (effect: () => (() => void) | undefined) => {
      hooks.cleanup = effect();
    },
    useState: (initial: unknown) => {
      const index = hooks.cursor++;
      if (!(index in hooks.values)) hooks.values[index] = initial;
      return [
        hooks.values[index],
        (next: unknown) => {
          hooks.values[index] = next;
        },
      ];
    },
    useRef: (initial: unknown) => {
      const index = hooks.cursor++;
      if (!(index in hooks.values)) hooks.values[index] = { current: initial };
      return hooks.values[index];
    },
  };
});

function elements(node: ReactNode): ReactElement<Record<string, unknown>>[] {
  return Children.toArray(node).flatMap((child) =>
    isValidElement<Record<string, unknown>>(child)
      ? [child, ...elements(child.props.children as ReactNode)]
      : [],
  );
}

const request = {
  title: "Delete the connection?",
  description: "This cannot be undone.\nIt does not uninstall model files.",
  confirmLabel: "Delete",
};

beforeEach(() => {
  hooks.values = [];
  hooks.cursor = 0;
  hooks.cleanup = undefined;
});

describe("ConfirmDialogView", () => {
  it.each(["zh-TW", "en"] as const)(
    "renders a labelled alertdialog with safe default focus in %s",
    (locale) => {
      const onClose = vi.fn();
      const nodes = elements(
        ConfirmDialogView({
          ...request,
          locale,
          descriptionId: "description-id",
          destructive: true,
          onClose,
        }),
      );
      expect(nodes[0].type).toBe(ModalOverlay);
      expect(nodes[0].props.isOpen).toBe(true);
      expect(nodes[0].props.isDismissable).toBe(false);
      expect(nodes[1].type).toBe(Modal);
      const dialog = nodes.find((node) => node.type === Dialog)!;
      expect(dialog.props.role).toBe("alertdialog");
      expect(dialog.props["aria-describedby"]).toBe("description-id");
      expect(dialog.props.lang).toBe(locale);
      const heading = nodes.find((node) => node.type === Heading)!;
      expect(heading.props.slot).toBe("title");
      expect(heading.props.children).toBe(request.title);
      const paragraphs = nodes.filter((node) => node.type === "p");
      expect(paragraphs).toHaveLength(1);
      expect(paragraphs[0].props.id).toBe("description-id");
      expect(paragraphs[0].props.children).toBe(request.description);
      expect(paragraphs[0].props.className).toBe(
        "admin-confirm-dialog__description",
      );
      expect(paragraphs[0].props.style).toBeUndefined();
      const buttons = nodes.filter((node) => node.type === Button);
      expect(buttons).toHaveLength(2);
      expect(buttons[0].props.children).toBe(
        locale === "zh-TW" ? "取消" : "Cancel",
      );
      expect(buttons[0].props.autoFocus).toBe(true);
      expect(buttons[1].props.autoFocus).toBeUndefined();
      expect(buttons[1].props.children).toBe("Delete");
      expect(buttons[1].props.className).toContain("--destructive");
      expect(onClose).not.toHaveBeenCalled();
      (buttons[0].props.onPress as () => void)();
      expect(onClose).toHaveBeenLastCalledWith(false);
      (buttons[1].props.onPress as () => void)();
      expect(onClose).toHaveBeenLastCalledWith(true);
      (nodes[0].props.onOpenChange as (open: boolean) => void)(false);
      expect(onClose).toHaveBeenLastCalledWith(false);
      expect(onClose).toHaveBeenCalledTimes(3);
    },
  );

  it("leaves the non-destructive confirm button in its normal style", () => {
    const nodes = elements(
      ConfirmDialogView({
        ...request,
        locale: "en",
        descriptionId: "description-id",
        onClose: vi.fn(),
      }),
    );
    expect(
      nodes.filter((node) => node.type === Button)[1].props.className,
    ).toBe("admin-confirm-dialog__confirm px-button px-button--primary");
  });
});

describe("ConfirmButton", () => {
  it.each([true, false])(
    "runs its action only after confirmation (%s)",
    (confirmed) => {
      const onConfirm = vi.fn();
      const input = {
        ...request,
        locale: "en" as const,
        onConfirm,
        children: "Delete setting",
      };
      const render = () => {
        hooks.cursor = 0;
        return elements(ConfirmButton(input));
      };
      expect(render().some((node) => node.type === ConfirmDialogView)).toBe(
        false,
      );
      const button = render().find((node) => node.type === "button")!;
      expect(button.props.type).toBe("button");
      expect(button.props.children).toBe("Delete setting");
      (button.props.onClick as () => void)();
      expect(onConfirm).not.toHaveBeenCalled();
      const view = render().find((node) => node.type === ConfirmDialogView)!;
      expect(view.props.title).toBe(request.title);
      (view.props.onClose as (confirmed: boolean) => void)(confirmed);
      expect(onConfirm).toHaveBeenCalledTimes(confirmed ? 1 : 0);
      expect(render().some((node) => node.type === ConfirmDialogView)).toBe(
        false,
      );
    },
  );

  it("blocks opening and confirming when its trigger is disabled", () => {
    const onConfirm = vi.fn();
    let disabled = true;
    const render = () => {
      hooks.cursor = 0;
      return elements(
        ConfirmButton({ ...request, locale: "en", disabled, onConfirm }),
      );
    };
    const button = render().find((node) => node.type === "button")!;
    expect(button.props.disabled).toBe(true);
    (button.props.onClick as () => void)();
    expect(render().some((node) => node.type === ConfirmDialogView)).toBe(
      false,
    );
    disabled = false;
    (
      render().find((node) => node.type === "button")!.props
        .onClick as () => void
    )();
    disabled = true;
    const view = render().find((node) => node.type === ConfirmDialogView)!;
    (view.props.onClose as (confirmed: boolean) => void)(true);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});

describe("useConfirmDialog", () => {
  function ConfirmDialogHarness() {
    hooks.cursor = 0;
    return useConfirmDialog("en");
  }

  it.each([true, false])(
    "settles the async decision and closes (%s)",
    async (confirmed) => {
      const [element, confirm] = ConfirmDialogHarness();
      expect(element).toBeNull();
      const result = confirm(request);
      const view = elements(ConfirmDialogHarness()[0])[0];
      expect(view.type).toBe(ConfirmDialogView);
      expect(view.props.description).toBe(request.description);
      (view.props.onClose as (confirmed: boolean) => void)(confirmed);
      await expect(result).resolves.toBe(confirmed);
      expect(ConfirmDialogHarness()[0]).toBeNull();
    },
  );

  it("settles an outstanding request as cancelled on replacement or unmount", async () => {
    const [, confirm] = ConfirmDialogHarness();
    const first = confirm(request);
    const second = confirm({ ...request, title: "Another decision" });
    await expect(first).resolves.toBe(false);
    expect(elements(ConfirmDialogHarness()[0])[0].props.title).toBe(
      "Another decision",
    );
    hooks.cleanup!();
    await expect(second).resolves.toBe(false);
  });
});

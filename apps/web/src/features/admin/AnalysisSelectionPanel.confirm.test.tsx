import {
  Children,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";
import { describe, expect, it, vi } from "vitest";
import { AnalysisSelectionPanel } from "./AnalysisSelectionPanel";
import type { ChatProfileView } from "./ChatProfilePanel";
import type { EmbeddingProfileView } from "./EmbeddingProfilePanel";

// Handlers are exercised with retained hooks, like the other interaction tests.
const hooks = vi.hoisted(() => ({
  values: [] as unknown[],
  cursor: 0,
  effects: [] as Array<() => unknown>,
}));
vi.mock("react", async (importOriginal) => {
  const react = await importOriginal<typeof import("react")>();
  return {
    ...react,
    useEffect: (effect: () => unknown) => {
      hooks.effects.push(effect);
    },
    useMemo: (factory: () => unknown) => factory(),
    useState: (initial: unknown) => {
      const index = hooks.cursor++;
      if (!(index in hooks.values)) hooks.values[index] = initial;
      return [
        hooks.values[index],
        (next: unknown) => {
          hooks.values[index] =
            typeof next === "function" ? next(hooks.values[index]) : next;
        },
      ];
    },
  };
});

type Node = ReactElement<Record<string, unknown>>;
function elements(node: ReactNode): Node[] {
  return Children.toArray(node).flatMap((child) =>
    isValidElement<Record<string, unknown>>(child)
      ? [child as Node, ...elements(child.props.children as ReactNode)]
      : [],
  );
}

const chat: ChatProfileView = {
  profile_id: "chat-a",
  connection_id: "service-a",
  connection_revision: 1,
  model_id: "chat-model",
  status: "ready",
  active: false,
  last_error_code: null,
  last_probed_at: "fixture-time",
  observed_model_id: "chat-model",
};
const finder: EmbeddingProfileView = {
  profile_id: "finder",
  connection_reference: "service-a",
  connection_revision: 1,
  provider: "openai_compatible",
  model_id: "finder-model",
  dimension: 3,
  normalized: true,
  status: "ready",
  active: false,
  last_error_code: null,
  last_probed_at: "fixture-time",
};
const accepted = (eligible: boolean) => ({
  selection: {
    chat_profile_id: "chat-a",
    embedding_profile_id: "finder",
    generation: 4,
    updated_at: "fixture-time",
  },
  eligible,
  reason: eligible ? "READY" : "CHAT_MODEL_NOT_READY",
  chat: {
    profile_id: "chat-a",
    model_id: "chat-model",
    status: "ready",
    connection_revision: 1,
    tested: true,
  },
  embedding: {
    profile_id: "finder",
    model_id: "finder-model",
    status: "ready",
    connection_revision: 1,
    tested: true,
  },
});

function mount(props: {
  locale?: "zh-TW" | "en";
  value: ReturnType<typeof accepted> | null;
  returning?: boolean;
}) {
  const onSelect = vi.fn();
  const onContinue = vi.fn();
  hooks.values.length = 0;
  const draw = () => {
    hooks.cursor = 0;
    hooks.effects = [];
    return elements(
      AnalysisSelectionPanel({
        locale: props.locale ?? "zh-TW",
        chatProfiles: [chat],
        embeddingProfiles: [finder],
        value: props.value,
        pending: false,
        error: "",
        returning: props.returning,
        onSelect,
        onContinue,
      }),
    );
  };
  draw();
  // Run the sync effects, then draw again with the state they produced.
  for (const effect of hooks.effects) effect();
  const nodes = draw();
  return { nodes, onSelect, onContinue, redraw: draw };
}
const button = (nodes: Node[]) => nodes.find((n) => n.type === "button")!;

describe("AnalysisSelectionPanel one-click confirmation", () => {
  it("moves on without a second save when the accepted pair is unchanged", () => {
    const { nodes, onSelect, onContinue } = mount({ value: accepted(true) });
    expect(button(nodes).props.disabled).toBe(false);
    (button(nodes).props.onClick as () => void)();
    expect(onContinue).toHaveBeenCalledTimes(1);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("saves a pair the server has not accepted yet", () => {
    const { nodes, onSelect, onContinue } = mount({ value: accepted(false) });
    (button(nodes).props.onClick as () => void)();
    expect(onSelect).toHaveBeenCalledExactlyOnceWith("chat-a", "finder", 4);
    expect(onContinue).not.toHaveBeenCalled();
  });

  it("saves a pair the owner picked from empty selects", () => {
    const { nodes, redraw, onSelect, onContinue } = mount({ value: null });
    expect(button(nodes).props.disabled).toBe(true);
    const selects = nodes.filter((n) => n.type === "select");
    type Change = (event: { target: { value: string } }) => void;
    (selects[0].props.onChange as Change)({ target: { value: "chat-a" } });
    (selects[1].props.onChange as Change)({ target: { value: "finder" } });
    const next = redraw();
    expect(button(next).props.disabled).toBe(false);
    (button(next).props.onClick as () => void)();
    expect(onSelect).toHaveBeenCalledExactlyOnceWith("chat-a", "finder", 0);
    expect(onContinue).not.toHaveBeenCalled();
  });

  it.each([
    ["zh-TW", false, "確認並前往選擇專案"],
    ["zh-TW", true, "完成設定並返回準備 NPC"],
    ["en", false, "Confirm and choose projects"],
    ["en", true, "Finish setup and return to prepare NPC"],
  ] as const)(
    "labels the action in %s (returning=%s)",
    (locale, returning, label) => {
      const { nodes } = mount({ locale, value: accepted(true), returning });
      expect(button(nodes).props.children).toBe(label);
      expect(button(nodes).props["aria-describedby"]).toBe(
        "analysis-selection-status",
      );
    },
  );
});

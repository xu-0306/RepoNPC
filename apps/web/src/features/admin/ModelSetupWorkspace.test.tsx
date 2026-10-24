import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ADMIN_MODEL_STATES } from "./AdminStatusCards";
import { AnalysisSelectionPanel } from "./AnalysisSelectionPanel";
import { ModelSetupWorkspace } from "./ModelSetupWorkspace";

describe("ModelSetupWorkspace", () => {
  it("keeps model selection and both complete role setup areas visible together", () => {
    const markup = renderToStaticMarkup(
      <ModelSetupWorkspace
        guidanceView={<p>DEVICE CHECK AND MODEL GUIDANCE</p>}
        chatConnectionView={<p>CHAT SERVICE FORM</p>}
        chatView={<p>CHAT MODEL FORM</p>}
        embeddingConnectionView={<p>FINDER SERVICE FORM</p>}
        embeddingView={<p>FINDER MODEL FORM</p>}
        locale="zh-TW"
        selectionView={<p>MODEL SELECTION</p>}
      />,
    );

    expect(markup).toContain("分析使用這一組");
    expect(markup.indexOf("DEVICE CHECK AND MODEL GUIDANCE")).toBeGreaterThan(
      markup.indexOf("MODEL SELECTION"),
    );
    expect(markup).toContain(
      '<details class="model-setup-workspace__guidance px-panel px-panel--inset">',
    );
    expect(markup).not.toContain("步驟 1");
    expect(markup).not.toContain("右側");
    expect(markup.indexOf("FINDER MODEL FORM")).toBeLessThan(
      markup.indexOf("MODEL SELECTION"),
    );
    expect(markup).toContain("分析與回答模型");
    expect(markup).toContain("資料查找模型");
    expect(markup).toContain("CHAT SERVICE FORM");
    expect(markup).toContain("CHAT MODEL FORM");
    expect(markup).toContain("FINDER SERVICE FORM");
    expect(markup).toContain("FINDER MODEL FORM");
    expect(markup).not.toContain("aria-pressed");
  });
});

it.each(["zh-TW", "en"] as const)(
  "renders both open slots, truthful badges and the original confirmation action in %s",
  (locale) => {
    for (const state of [
      "unconfigured",
      "testing",
      "tested",
      "selected",
      "unavailable",
    ] as const) {
      const summary = {
        model: "<unsafe-model>",
        connection: "Fixture service",
        provider: "openai_compatible" as const,
        state,
      };
      const markup = renderToStaticMarkup(
        <ModelSetupWorkspace
          locale={locale}
          status={{ chat: summary, embedding: summary }}
          chatConnectionView={<button>Inner chat test</button>}
          chatView={<input aria-label="Chat model" />}
          embeddingConnectionView={<button>Inner finder test</button>}
          embeddingView={<input aria-label="Finder model" />}
          localModelView={<p>Local model choice</p>}
          selectionView={
            <AnalysisSelectionPanel
              locale={locale}
              chatProfiles={[]}
              embeddingProfiles={[]}
              value={null}
              pending={false}
              error=""
              onSelect={() => undefined}
            />
          }
        />,
      );
      expect(markup).toContain('aria-labelledby="chat-role-setup-heading"');
      expect(markup).toContain(
        'aria-labelledby="embedding-role-setup-heading"',
      );
      expect(markup).toContain('id="chat-role-setup-heading"');
      expect(markup).toContain('id="embedding-role-setup-heading"');
      expect(
        markup.match(/class="model-role-setup__details" open=""/g),
      ).toHaveLength(2);
      expect(
        markup.match(new RegExp(`data-state="${state}">`, "g")),
      ).toHaveLength(2);
      expect(markup.split(ADMIN_MODEL_STATES[locale][state]).length - 1).toBe(
        2,
      );
      expect(markup).toContain("Fixture service · &lt;unsafe-model&gt;");
      expect(markup).not.toContain("<unsafe-model>");
      expect(markup).toContain("Local model choice");
      const footer = markup.slice(
        markup.indexOf("<footer"),
        markup.indexOf("</footer>"),
      );
      expect(footer).toContain('aria-labelledby="model-setup-role-heading"');
      expect(footer).toContain('id="model-setup-role-heading"');
      expect(footer).toContain(
        'aria-labelledby="analysis-model-selection-heading"',
      );
      expect(footer).toContain(
        locale === "en" ? "Use for analysis" : "確認用於分析",
      );
      expect(markup.match(/<button/g)).toHaveLength(3);
      expect(markup).toContain(
        `${state === "tested" || state === "selected" ? 2 : 0}/2`,
      );
    }
  },
);

it("reserves the measured confirmation height as it changes and disconnects on unmount", () => {
  for (const supported of [true, false]) {
    const slots = { style: { paddingBottom: "" } };
    let height = 198.3;
    const confirm = {
      previousElementSibling: slots,
      getBoundingClientRect: () => ({ height }),
    };
    let resized: (() => void) | undefined;
    const observe = vi.fn();
    const disconnect = vi.fn();
    vi.stubGlobal(
      "ResizeObserver",
      supported
        ? class {
            constructor(callback: () => void) {
              resized = callback;
            }
            observe = observe;
            disconnect = disconnect;
          }
        : undefined,
    );
    try {
      const tree = ModelSetupWorkspace({
        locale: "en",
        selectionView: null,
        chatConnectionView: null,
        embeddingConnectionView: null,
        chatView: null,
        embeddingView: null,
      });
      const footer = tree.props.children[0].props.children.at(-1);
      expect(footer.type).toBe("footer");
      expect(footer.props.ref(null)).toBeUndefined();
      const cleanup = footer.props.ref(confirm);
      expect(slots.style.paddingBottom).toBe("198.3px");
      if (supported) {
        expect(observe).toHaveBeenCalledWith(confirm);
        height = 121.375;
        resized?.();
        expect(slots.style.paddingBottom).toBe("121.375px");
      }
      if (typeof cleanup === "function") cleanup();
      expect(disconnect).toHaveBeenCalledTimes(supported ? 1 : 0);
    } finally {
      vi.unstubAllGlobals();
    }
  }
});

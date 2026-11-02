import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ADMIN_MODEL_STATES, type AdminModelSummary } from "./AdminStatusCards";
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

    expect(markup).toContain("使用這組模型分析");
    expect(markup.indexOf("DEVICE CHECK AND MODEL GUIDANCE")).toBeLessThan(
      markup.indexOf("MODEL SELECTION"),
    );
    expect(markup.lastIndexOf("<footer")).toBeGreaterThan(
      markup.indexOf("</details></div>"),
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
        locale === "en" ? "Confirm and choose projects" : "確認並前往選擇專案",
      );
      // Two role tabs, two inner test buttons and the pinned confirmation.
      expect(markup.match(/<button/g)).toHaveLength(5);
      expect(markup.match(/role="tab"/g)).toHaveLength(2);
      expect(markup.match(/role="tabpanel"/g)).toHaveLength(2);
      expect(markup).toContain(
        `${state === "tested" || state === "selected" ? 2 : 0}/2`,
      );
    }
  },
);

it("shows one role panel at a time and starts on the role that still needs setup", () => {
  const summary = (state: AdminModelSummary["state"]): AdminModelSummary => ({
    model: null,
    connection: null,
    provider: null,
    state,
  });
  const usable = summary("tested");
  const none = summary("unconfigured");
  const render = (chat: AdminModelSummary, embedding: AdminModelSummary) =>
    renderToStaticMarkup(
      <ModelSetupWorkspace
        locale="en"
        status={{ chat, embedding }}
        chatConnectionView={null}
        chatView={<p>CHAT FORM</p>}
        embeddingConnectionView={null}
        embeddingView={<p>FINDER FORM</p>}
        selectionView={null}
      />,
    );
  const selected = (markup: string) =>
    markup.match(
      /<button[^>]*aria-selected="true"[^>]*id="([a-z]+)-role-tab"/,
    )?.[1];
  expect(selected(render(none, none))).toBe("chat");
  expect(selected(render(usable, usable))).toBe("chat");
  expect(selected(render(usable, none))).toBe("embedding");
  const markup = render(usable, none);
  // Both flows stay mounted so typed values survive a tab switch.
  expect(markup).toContain("CHAT FORM");
  expect(markup).toContain("FINDER FORM");
  expect(markup).toMatch(/<div[^>]*hidden=""[^>]*id="chat-role-panel"/);
  expect(markup).not.toMatch(
    /<div[^>]*hidden=""[^>]*id="embedding-role-panel"/,
  );
  expect(markup).toContain('aria-controls="chat-role-panel"');
  expect(markup).toContain('aria-labelledby="embedding-role-tab"');
  expect(markup).toContain('tabindex="-1"');
});

it("only watches the pinned bar and leaves the slots untouched", () => {
  const tree = ModelSetupWorkspace({
    locale: "en",
    selectionView: null,
    chatConnectionView: null,
    embeddingConnectionView: null,
    chatView: null,
    embeddingView: null,
  });
  const footer = tree.props.children.at(-1);
  expect(footer.type).toBe("footer");
  expect(footer.props.ref(null)).toBeUndefined();
  const confirm = { addEventListener: vi.fn(), removeEventListener: vi.fn() };
  const cleanup = footer.props.ref(confirm);
  expect(confirm.addEventListener).toHaveBeenCalledWith(
    "toggle",
    expect.any(Function),
    true,
  );
  cleanup();
  expect(confirm.removeEventListener).toHaveBeenCalledWith(
    "toggle",
    expect.any(Function),
    true,
  );
});

it("reveals a covered slot heading only when inline confirmation help opens", () => {
  const scrollBy = vi.fn();
  vi.stubGlobal("window", { scrollBy });
  try {
    const tree = ModelSetupWorkspace({
      locale: "en",
      selectionView: null,
      chatConnectionView: null,
      embeddingConnectionView: null,
      chatView: null,
      embeddingView: null,
    });
    const footer = tree.props.children.at(-1);
    let bottom = 640;
    const target = {
      open: true,
      classList: {
        contains: (name: string): boolean => name === "model-selection__info",
      },
    };
    let toggle: (event: unknown) => void = () => {};
    const currentTarget = {
      addEventListener: (_name: string, callback: (event: unknown) => void) => {
        toggle = callback;
      },
      removeEventListener: vi.fn(),
      parentElement: {
        querySelector: () => ({
          getBoundingClientRect: () => ({ top: bottom - 30, bottom }),
        }),
      },
      getBoundingClientRect: () => ({ top: 570, bottom: 844, height: 274 }),
    };
    const cleanup = footer.props.ref(currentTarget);
    const event = { target, currentTarget };
    toggle(event);
    expect(scrollBy).toHaveBeenCalledExactlyOnceWith({
      top: 86,
      behavior: "instant",
    });
    scrollBy.mockClear();
    bottom = 530;
    toggle(event);
    expect(scrollBy).not.toHaveBeenCalled();
    target.open = false;
    bottom = 640;
    toggle(event);
    expect(scrollBy).not.toHaveBeenCalled();
    target.open = true;
    target.classList.contains = () => false;
    toggle(event);
    expect(scrollBy).not.toHaveBeenCalled();
    cleanup();
  } finally {
    vi.unstubAllGlobals();
  }
});

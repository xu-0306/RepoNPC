import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CoverageFaqPanel } from "./CoverageFaqPanel";
import { LANGUAGES } from "../../i18n/languages";
import { ADMIN_CHROMES } from "./__fixtures__/siteLanguages";

// Seed the fetched queue while retaining React's other hooks and full panel render.
const queue = vi.hoisted(() => ({
  inject: false,
  view: {} as unknown,
  effects: null as Array<() => unknown> | null,
}));
vi.mock("react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react")>();
  return {
    ...actual,
    useEffect: (...args: Parameters<typeof actual.useEffect>) =>
      queue.effects ? queue.effects.push(args[0]) : actual.useEffect(...args),
    useState: (initial: unknown) => {
      if (queue.inject && initial === null) {
        queue.inject = false;
        return [queue.view, vi.fn()];
      }
      return actual.useState(initial);
    },
  };
});
afterEach(() => {
  queue.effects = null;
});

it.each(
  ADMIN_CHROMES.flatMap((locale) =>
    LANGUAGES.map(({ tag }) => ({ locale, tag })),
  ),
)(
  "requests the selected FAQ language $tag with $locale chrome",
  async ({ locale, tag }) => {
    queue.effects = [];
    const request = vi.fn().mockResolvedValue({
      locale: tag,
      bundle_id: "site-bundle",
      entries: [],
    });
    const html = renderToStaticMarkup(
      <CoverageFaqPanel
        locale={locale}
        contentLocale={tag}
        request={request}
        repositories={[]}
        bundleId="site-bundle"
        draftChanged={false}
        onAddClaim={vi.fn()}
      />,
    );
    for (const effect of queue.effects) effect();
    await Promise.resolve();
    expect(request).toHaveBeenCalledWith(
      `/api/admin/portfolio/faq?locale=${tag}`,
    );
    expect(html).toContain(
      locale === "en" ? "Coverage and FAQ review" : "涵蓋檢查與 FAQ 審核",
    );
  },
);

const cases = [
  [
    "MODEL_INSUFFICIENT_EVIDENCE",
    "模型判斷證據不足",
    "Model found too little evidence",
  ],
  ["ENVELOPE_SCHEMA_INVALID", "回覆格式不符", "Reply format invalid"],
  ["SOURCE_ID_UNKNOWN", "引用了不存在的來源", "Cited an unknown source"],
  [
    "MODEL_AUTHORED_MARKUP",
    "回覆含不允許的連結或標記",
    "Reply contained disallowed links or markup",
  ],
  ["INFERENCE_CYCLE", "推論引用了推論", "Inference cited an inference"],
  ["ALL_SEGMENTS_DROPPED", "每段都未通過檢查", "Every part failed checks"],
  ["SELECTED_MAP_INVALID", "系統檢查錯誤", "Internal check error"],
  ["VALIDATION_UNEXPECTED", "系統檢查錯誤", "Internal check error"],
  ["NO_EVIDENCE_SELECTED", "沒有找到相關資料", "No relevant content found"],
] as const;

function render(locale: "zh-TW" | "en", reason: string | null) {
  queue.view = {
    bundle_id: "fixture-bundle",
    locale,
    entries: [
      {
        entry_id: "fixture",
        bundle_id: "fixture-bundle",
        question: "Fixture question?",
        variants: [],
        topic: "responsibility",
        claim_kind: "responsibility",
        answer_markdown: null,
        citations: [],
        dropped_segments: [],
        no_match_reason: reason,
        coverage_status: reason ? "no_relevant_content" : "answered",
        review_state: "pending",
        needs_reconfirmation: false,
        error_code: null,
        revision: 1,
      },
    ],
  };
  queue.inject = true;
  return renderToStaticMarkup(
    <CoverageFaqPanel
      locale={locale}
      request={async <T,>() => ({}) as T}
      repositories={["fixture/repo"]}
      bundleId="fixture-bundle"
      draftChanged={false}
      onAddClaim={vi.fn()}
    />,
  );
}

describe.each(["zh-TW", "en"] as const)("owner FAQ reasons in %s", (locale) => {
  it.each(cases)("renders one short label for %s", (reason, zh, en) => {
    const html = render(locale, reason);
    const label = locale === "zh-TW" ? zh : en;
    expect(html).toContain(`<span> · ${label}</span>`);
    expect(html.match(/<span>/g)).toHaveLength(1);
    expect(html).not.toContain(reason);
    expect(html).toContain(
      `<article lang="${locale}" class="coverage-faq__entry" aria-label="Fixture question?">`,
    );
  });
  it("renders no diagnostic label for an answered entry with a null reason", () => {
    const html = render(locale, null);
    expect(html).not.toContain("<span>");
    for (const [, zh, en] of cases)
      expect(html).not.toContain(locale === "zh-TW" ? zh : en);
    expect(html).toContain(locale === "zh-TW" ? "已回答" : "Answered");
  });
});

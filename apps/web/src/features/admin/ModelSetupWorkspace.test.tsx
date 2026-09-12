import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ModelSetupWorkspace } from "./ModelSetupWorkspace";

describe("ModelSetupWorkspace", () => {
  it("keeps model selection and both complete role setup areas visible together", () => {
    const markup = renderToStaticMarkup(
      <ModelSetupWorkspace
        chatConnectionView={<p>CHAT SERVICE FORM</p>}
        chatView={<p>CHAT MODEL FORM</p>}
        embeddingConnectionView={<p>FINDER SERVICE FORM</p>}
        embeddingView={<p>FINDER MODEL FORM</p>}
        locale="zh-TW"
        selectionView={<p>MODEL SELECTION</p>}
      />,
    );

    expect(markup).toContain("確認分析模型");
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

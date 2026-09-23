import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { CharacterAssetConverter } from "./CharacterAssetConverter";
import { suggestedCharacterFilename } from "./characterAssetFilename";

describe("CharacterAssetConverter", () => {
  it("derives a safe output name without depending on source language or vendor naming", () => {
    expect(suggestedCharacterFilename("My Cat Concept.PNG")).toBe(
      "my-cat-concept.png",
    );
    expect(suggestedCharacterFilename("角色草圖.png")).toBe("character.png");
    expect(suggestedCharacterFilename("../../unsafe name.zip")).toBe(
      "unsafe-name.png",
    );
  });

  it("renders the conversion boundary and fallback download guidance bilingually", () => {
    const zh = renderToStaticMarkup(
      <CharacterAssetConverter
        githubOperationsReady={false}
        locale="zh-TW"
        onConvert={vi.fn()}
        onValidate={vi.fn()}
        onSave={vi.fn()}
      />,
    );
    const en = renderToStaticMarkup(
      <CharacterAssetConverter
        githubOperationsReady={false}
        locale="en"
        onConvert={vi.fn()}
        onValidate={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    for (const markup of [zh, en]) {
      expect(markup).toContain('accept=".png,.zip,image/png,application/zip"');
      expect(markup).toContain('id="admin-character-folder"');
      expect(markup).toContain("webkitdirectory");
      expect(markup).toContain("multiple");
      expect(markup).toContain('value="pixelize"');
      expect(markup).toContain('value="pixel_exact"');
      expect(markup).toContain('type="file"');
    }
    expect(zh).toContain("製作角色動畫");
    expect(zh).toContain("選擇整個資料夾");
    expect(zh).toContain("進階轉換設定");
    expect(zh).toContain("選擇素材");
    expect(en).toContain("Create character animation");
    expect(en).toContain("Choose a folder");
    expect(en).toContain("Advanced conversion settings");
  });
});

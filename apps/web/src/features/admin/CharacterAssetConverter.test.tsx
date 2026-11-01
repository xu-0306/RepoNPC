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
        locale="zh-TW"
        onConvert={vi.fn()}
        onValidate={vi.fn()}
      />,
    );
    const en = renderToStaticMarkup(
      <CharacterAssetConverter
        locale="en"
        onConvert={vi.fn()}
        onValidate={vi.fn()}
      />,
    );

    for (const markup of [zh, en]) {
      expect(markup).toContain('accept=".png,.zip,image/png,application/zip"');
      expect(markup).toContain('id="admin-character-folder"');
      expect(markup).toContain("webkitdirectory");
      expect(markup).toContain("multiple");
      expect(markup).toContain('value="pixelize"');
      expect(markup).toContain('value="pixel_exact"');
      const inputs = markup.match(/<input[^>]+type="file"[^>]*>/g)!;
      expect(inputs).toHaveLength(2);
      expect(
        inputs.every((input) => input.includes('style="display:none"')),
      ).toBe(true);
      expect(markup).toContain('id="admin-character-source"');
      expect(markup).toContain(
        'class="character-converter__pedestal px-panel px-panel--inset"',
      );
      expect(markup).not.toContain("Choose File");
      const headings = [
        ...markup.matchAll(/<h([1-6])\b[^>]*>([\s\S]*?)<\/h\1>/g),
      ];
      expect(headings.filter((heading) => heading[1] === "1")).toHaveLength(1);
      let previousLevel = 0;
      for (const heading of headings) {
        expect(heading[2].replace(/<[^>]*>/g, "").trim()).not.toBe("");
        const level = Number(heading[1]);
        expect(level).toBeLessThanOrEqual(previousLevel + 1);
        previousLevel = level;
      }
    }
    expect(zh).toContain("<h2>動畫預覽</h2>");
    expect(en).toContain("<h2>Animation preview</h2>");
    expect(zh).toContain("製作角色動畫");
    expect(zh).toContain("選擇整個資料夾");
    expect(zh).toContain("進階轉換設定");
    expect(zh).toContain("選擇素材");
    expect(en).toContain("Create character animation");
    expect(en).toContain("Choose a folder");
    expect(en).toContain("Advanced conversion settings");
  });
});

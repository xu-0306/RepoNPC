import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { LocalLaunchAccessPanel } from "./LocalLaunchAccessPanel";

describe("local access presentation", () => {
  for (const locale of ["zh-TW", "en"] as const) {
    for (const state of ["checking", "relaunch"] as const) {
      it(`${locale} ${state} has a themed landmark without unauthorized actions`, () => {
        const markup = renderToStaticMarkup(
          <LocalLaunchAccessPanel locale={locale} state={state} />,
        );
        expect(markup).toContain(`class="admin-auth-shell" lang="${locale}"`);
        expect(markup).toContain('class="admin-auth-card"');
        expect(markup).toContain('class="admin-auth__title"');
        expect(markup).not.toMatch(/<(form|button|input)\b/);
        if (state === "checking") expect(markup).toContain('role="status"');
        else
          expect(markup).toContain(
            locale === "en" ? "run the launcher again" : "重新執行啟動器",
          );
      });
    }
  }
});

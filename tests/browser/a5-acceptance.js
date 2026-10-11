// Test-only controls. Loaded by the disposable host, never copied into exports.
(() => {
  const simulateMotion =
    new URLSearchParams(location.search).get("a5-reduced") === "1";
  let reduced = simulateMotion;
  const listeners = new Set();
  let toggleMotion;
  if (simulateMotion) {
    const original = window.matchMedia.bind(window);
    const media = {
      media: "(prefers-reduced-motion: reduce)",
      get matches() {
        return reduced;
      },
      onchange: null,
      addEventListener(type, listener) {
        if (type === "change") listeners.add(listener);
      },
      removeEventListener(type, listener) {
        if (type === "change") listeners.delete(listener);
      },
      addListener(listener) {
        listeners.add(listener);
      },
      removeListener(listener) {
        listeners.delete(listener);
      },
      dispatchEvent(event) {
        for (const listener of listeners) {
          if (typeof listener === "function") listener(event);
          else listener.handleEvent(event);
        }
        media.onchange?.(event);
        return true;
      },
    };
    window.matchMedia = (query) =>
      query === media.media ? media : original(query);
    document.documentElement.dataset.a5Motion = "simulated";
    toggleMotion = () => {
      reduced = !reduced;
      media.dispatchEvent(
        new MediaQueryListEvent("change", {
          media: media.media,
          matches: reduced,
        }),
      );
    };
  }
  window.addEventListener("DOMContentLoaded", () => {
    const controls = document.createElement("details");
    controls.dataset.a5TestControls = "true";
    const heading = document.createElement("summary");
    heading.textContent = "A5 acceptance checks";
    const audit = document.createElement("button");
    audit.type = "button";
    audit.textContent = "Run accessibility audit";
    const output = document.createElement("pre");
    output.dataset.a5Audit = "true";
    output.setAttribute("aria-live", "polite");
    output.style.whiteSpace = "pre-wrap";
    output.style.overflowWrap = "anywhere";
    audit.addEventListener("click", async () => {
      audit.disabled = true;
      output.textContent = "Running accessibility audit";
      try {
        const result = await axe.run(
          { exclude: ["[data-a5-test-controls]"] },
          {
            runOnly: {
              type: "tag",
              values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
            },
          },
        );
        const issues = (items) =>
          items.map((item) => ({
            id: item.id,
            impact: item.impact,
            targets: item.nodes.map((node) => node.target),
          }));
        output.textContent = JSON.stringify({
          version: result.testEngine.version,
          passes: result.passes.length,
          violations: issues(result.violations),
          incomplete: issues(result.incomplete),
          profileInitialContrast: Array.from(
            document.querySelectorAll(".visitor-profile-card__avatar"),
          ).map((element) => {
            const style = getComputedStyle(element);
            const luminance = (color) => {
              const [red, green, blue] = color.match(/[\d.]+/g).map(Number);
              return [red, green, blue].reduce((sum, channel, index) => {
                const value = channel / 255;
                const linear =
                  value <= 0.04045
                    ? value / 12.92
                    : ((value + 0.055) / 1.055) ** 2.4;
                return sum + linear * [0.2126, 0.7152, 0.0722][index];
              }, 0);
            };
            const foreground = luminance(style.color);
            const background = luminance(style.backgroundColor);
            const ratio =
              (Math.max(foreground, background) + 0.05) /
              (Math.min(foreground, background) + 0.05);
            return {
              color: style.color,
              background: style.backgroundColor,
              ratio,
              pass: ratio >= 4.5,
            };
          }),
        });
      } catch (error) {
        output.textContent = JSON.stringify({ error: String(error) });
      } finally {
        audit.disabled = false;
      }
    });
    controls.append(heading, audit);
    const delayPreview = document.createElement("button");
    delayPreview.type = "button";
    delayPreview.textContent = "Delay next scene preview";
    delayPreview.addEventListener("click", async () => {
      const response = await fetch("/__a5-test/delay-scene-preview", {
        method: "POST",
        credentials: "same-origin",
      });
      output.textContent = response.ok
        ? "Scene preview delay armed"
        : "Scene preview delay unavailable";
    });
    controls.append(delayPreview);
    if (simulateMotion) {
      const motion = document.createElement("button");
      motion.type = "button";
      motion.textContent = "Toggle simulated reduced motion";
      motion.addEventListener("click", toggleMotion);
      controls.append(motion);
    }
    controls.append(output);
    document.body.append(controls);
  });
})();

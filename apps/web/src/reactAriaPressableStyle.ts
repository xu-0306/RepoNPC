// React Aria's usePress prepends <style id="react-aria-pressable-style"> unless an
// element with that id already exists. The CSP is `style-src 'self'`, so the browser
// blocks the injected style and logs one violation per load. styles.css carries the same
// `[data-react-aria-pressable]` rule, so a marker element is enough to skip the injection.
// reactAriaPressableStyle.test.ts fails if a React Aria upgrade changes the id or the check.
export const REACT_ARIA_PRESSABLE_STYLE_ID = "react-aria-pressable-style";

type MarkerDocument = Pick<Document, "createElement" | "getElementById"> & {
  head: Pick<HTMLHeadElement, "append"> | null;
};

export function claimReactAriaPressableStyle(
  doc: MarkerDocument = document,
): void {
  if (!doc.head || doc.getElementById(REACT_ARIA_PRESSABLE_STYLE_ID)) return;
  const marker = doc.createElement("meta");
  marker.id = REACT_ARIA_PRESSABLE_STYLE_ID;
  marker.setAttribute("name", REACT_ARIA_PRESSABLE_STYLE_ID);
  marker.setAttribute("content", "static rule in styles.css");
  doc.head.append(marker);
}

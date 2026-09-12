// Pass this function to the documented browser's read-only evaluate API.
// Uses visible layout and semantic relationships, never form values or browser storage.
export function measureUi() {
  const visible = (element) => element.getClientRects().length > 0;
  const overlaps = (a, b) =>
    a.left < b.right &&
    a.right > b.left &&
    a.top < b.bottom &&
    a.bottom > b.top;
  const choices = [...document.querySelectorAll("main .checkbox-field")]
    .filter(visible)
    .map((label) => {
      const input = label.querySelector("input");
      const text = label.querySelector(".checkbox-field__text");
      const a = input.getBoundingClientRect(),
        b = text.getBoundingClientRect();
      return {
        associated: input.id === label.htmlFor,
        aligned: a.top >= b.top && a.top - b.top < a.height,
        targetHeight: label.getBoundingClientRect().height,
        overflow: label.scrollWidth > label.clientWidth + 1,
      };
    });
  const badgeOverlap = [
    ...document.querySelectorAll(".admin-status-card__badge"),
  ]
    .filter(visible)
    .some((badge) =>
      overlaps(
        badge.getBoundingClientRect(),
        badge.parentElement
          .querySelector(".admin-status-card__copy")
          .getBoundingClientRect(),
      ),
    );
  const ids = [...document.querySelectorAll("main [id]")].map(
    (element) => element.id,
  );
  return {
    pageOverflow: document.documentElement.scrollWidth > innerWidth + 1,
    choices,
    badgeOverlap,
    uniqueIds: ids.length === new Set(ids).size,
    selects: [...document.querySelectorAll("main select")]
      .filter(visible)
      .map((select) => ({
        font: getComputedStyle(select).fontSize,
        labelFont: getComputedStyle(select.closest("label")).fontSize,
      })),
  };
}

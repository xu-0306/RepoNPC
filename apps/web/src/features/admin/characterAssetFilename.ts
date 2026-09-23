export function suggestedCharacterFilename(sourceName: string): string {
  const stem = sourceName.replace(/\.[^.]*$/, "").toLowerCase();
  const normalized = stem
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 59);
  return `${normalized || "character"}.png`;
}

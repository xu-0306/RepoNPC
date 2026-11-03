import { chromeLocale } from "../../i18n/languages";
import type { LanguageTag as Locale } from "../../i18n/languages";

export function githubRateLimitLabel(locale: Locale): string {
  return chromeLocale(locale) === "zh-TW"
    ? "GitHub 目前限制新的工作"
    : "GitHub is limiting new work";
}

export function githubRateLimitMessage(
  locale: Locale,
  retryAfterSeconds?: number,
): string {
  const label = githubRateLimitLabel(locale);
  return retryAfterSeconds !== undefined && retryAfterSeconds > 0
    ? `${label}${chromeLocale(locale) === "zh-TW" ? "；" : ". "}${retryAfter(retryAfterSeconds, locale)}`
    : `${label}${chromeLocale(locale) === "zh-TW" ? "。" : "."}`;
}

export function retryAfter(seconds: number, locale: Locale): string {
  return chromeLocale(locale) === "zh-TW"
    ? `請在約 ${formatDuration(seconds, locale)} 後再試。`
    : `Try again in about ${formatDuration(seconds, locale)}.`;
}

export function formatDuration(seconds: number, locale: Locale): string {
  const boundedSeconds = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(boundedSeconds / 60);
  const remainder = boundedSeconds % 60;
  if (chromeLocale(locale) === "zh-TW") {
    return minutes > 0 ? `${minutes} 分 ${remainder} 秒` : `${remainder} 秒`;
  }
  return minutes > 0 ? `${minutes}m ${remainder}s` : `${remainder}s`;
}

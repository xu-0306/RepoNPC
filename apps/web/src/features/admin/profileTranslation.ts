import { useEffect, useRef, useState } from "react";

import {
  deriveConverter,
  languageByTag,
  type LanguageTag,
} from "../../i18n/languages";
import { planLanguages } from "../../i18n/plan";
import { localizedTags, type GuidedProfile } from "./guidedOnboarding";

export const PROFILE_FIELDS = ["headline", "bio", "greeting"] as const;
export type ProfileField = (typeof PROFILE_FIELDS)[number];

export interface ProfileTranslationItem {
  field: ProfileField;
  source_locale: LanguageTag;
  target_locale: LanguageTag;
  text: string;
}

export interface ProfileTranslationResult {
  field: ProfileField;
  target_locale: LanguageTag;
  text: string;
  method: "model" | "converted";
  confirmed: false;
}

export type TranslateProfile = (
  items: ProfileTranslationItem[],
  signal: AbortSignal,
) => Promise<unknown>;

export function requestProfileTranslation(
  request: <T>(path: string, init?: RequestInit) => Promise<T>,
  items: ProfileTranslationItem[],
  signal: AbortSignal,
) {
  return request<unknown>("/api/admin/onboarding/profile/translate", {
    method: "POST",
    signal,
    body: JSON.stringify({ items }),
  });
}

// Browsers without `field-sizing: content` get the height fitted after each render.
export function fitHeight(element: HTMLTextAreaElement | null) {
  if (
    !element ||
    (typeof CSS !== "undefined" && CSS.supports("field-sizing", "content"))
  )
    return;
  element.style.height = "auto";
  element.style.height = `${element.scrollHeight + element.offsetHeight - element.clientHeight}px`;
}

export function profileLanguages(supported: readonly LanguageTag[]) {
  return supported.map((tag) => ({ ...languageByTag(tag)!, tag }));
}

export function profileTranslationSource(
  profile: GuidedProfile,
  field: ProfileField,
  target: LanguageTag,
  supported = localizedTags(profile.headline),
): ProfileTranslationItem | undefined {
  const plan = planLanguages(supported);
  const derived = plan.derived.find((pair) => pair.target === target)?.source;
  const candidates = [
    ...new Set([
      ...(derived ? [derived] : []),
      ...supported.filter((tag) => deriveConverter(tag, target)),
      ...plan.written,
      ...supported,
    ]),
  ];
  const source = candidates.find(
    (tag) => tag !== target && profile[field][tag]?.trim(),
  );
  return (
    source && {
      field,
      source_locale: source,
      target_locale: target,
      text: profile[field][source],
    }
  );
}

export function emptyProfileTranslationItems(
  profile: GuidedProfile,
  supported = localizedTags(profile.headline),
) {
  const plan = planLanguages(supported);
  return PROFILE_FIELDS.flatMap((field) =>
    supported.flatMap((tag) => {
      if (profile[field][tag].trim()) return [];
      const derived = plan.derived.find((pair) => pair.target === tag);
      if (derived && !profile[field][derived.source]?.trim()) return [];
      const item = profileTranslationSource(profile, field, tag, supported);
      return item ? [item] : [];
    }),
  );
}

export function profileTranslationBody(
  value: unknown,
  requested: ProfileTranslationItem[],
): ProfileTranslationResult[] | null {
  if (typeof value !== "object" || value === null || !("items" in value))
    return null;
  if (!Array.isArray(value.items) || value.items.length !== requested.length)
    return null;
  const items: ProfileTranslationResult[] = [];
  for (const [index, item] of value.items.entries()) {
    const expected = requested[index];
    if (
      typeof item !== "object" ||
      item === null ||
      item.field !== expected.field ||
      item.target_locale !== expected.target_locale ||
      typeof item.text !== "string" ||
      !item.text.trim() ||
      Array.from(item.text).length > 2000 ||
      item.method !==
        (deriveConverter(expected.source_locale, expected.target_locale)
          ? "converted"
          : "model") ||
      item.confirmed !== false
    )
      return null;
    items.push({
      field: item.field,
      target_locale: item.target_locale,
      text: item.text,
      method: item.method,
      confirmed: false,
    });
  }
  return items;
}

type FieldKey = `${ProfileField}:${LanguageTag}`;
interface TranslationReview {
  previousText: string;
  translatedText: string;
  reviewed: boolean;
  method: ProfileTranslationResult["method"];
}
type TranslationStatus =
  | { kind: "translated"; applied: number; discarded: number }
  | { kind: "reviewed" | "restored" }
  | null;

export function useProfileTranslation({
  profile,
  active,
  reset,
  modelGeneration,
  enabled,
  modelEnabled = true,
  supported = localizedTags(profile.headline),
  translate,
  onChange,
}: {
  profile: GuidedProfile;
  active: boolean;
  reset: boolean;
  modelGeneration: number | undefined;
  enabled: boolean;
  modelEnabled?: boolean;
  supported?: LanguageTag[];
  translate: TranslateProfile | undefined;
  onChange: (profile: GuidedProfile) => void;
}) {
  const latestProfile = useRef(profile);
  latestProfile.current = profile;
  const generation = useRef(0);
  const requestAbort = useRef<AbortController | null>(null);
  const editVersions = useRef<Partial<Record<FieldKey, number>>>({});
  const [pending, setPending] = useState(false);
  const [reviews, setReviews] = useState<
    Partial<Record<FieldKey, TranslationReview>>
  >({});
  const [status, setStatus] = useState<TranslationStatus>(null);
  const [errorCode, setErrorCode] = useState("");
  const siteKey = supported.join(",");

  useEffect(() => {
    setPending(false);
    if (reset) {
      setReviews({});
      setStatus(null);
      setErrorCode("");
    } else {
      setReviews((current) =>
        Object.fromEntries(
          Object.entries(current).filter(([key]) =>
            siteKey.split(",").includes(key.split(":")[1]),
          ),
        ),
      );
    }
    return () => {
      generation.current += 1;
      requestAbort.current?.abort();
      requestAbort.current = null;
    };
  }, [active, modelGeneration, reset, siteKey]);

  function setField(field: ProfileField, locale: LanguageTag, text: string) {
    const current = latestProfile.current;
    const next = { ...current, [field]: { ...current[field], [locale]: text } };
    latestProfile.current = next;
    onChange(next);
  }

  function markReviewed(field: ProfileField, locale: LanguageTag) {
    const key: FieldKey = `${field}:${locale}`;
    setReviews((current) => {
      const review = current[key];
      return review
        ? { ...current, [key]: { ...review, reviewed: true } }
        : current;
    });
  }

  async function run(items: ProfileTranslationItem[]) {
    if (
      !active ||
      !enabled ||
      !translate ||
      !items.length ||
      items.some(
        (item) =>
          !supported.includes(item.source_locale) ||
          !supported.includes(item.target_locale) ||
          (!modelEnabled &&
            !deriveConverter(item.source_locale, item.target_locale)),
      ) ||
      requestAbort.current
    )
      return;
    const currentGeneration = ++generation.current;
    const controller = new AbortController();
    requestAbort.current = controller;
    const snapshots = items.map((item) => ({
      targetText: latestProfile.current[item.field][item.target_locale],
      sourceVersion:
        editVersions.current[`${item.field}:${item.source_locale}`],
      targetVersion:
        editVersions.current[`${item.field}:${item.target_locale}`],
    }));
    setPending(true);
    setStatus(null);
    setErrorCode("");
    try {
      const results: ProfileTranslationResult[] = [];
      for (let offset = 0; offset < items.length; offset += 6) {
        const batch = items.slice(offset, offset + 6);
        const response = await translate(batch, controller.signal);
        if (generation.current !== currentGeneration) return;
        const validated = profileTranslationBody(response, batch);
        if (!validated) throw new Error("PROVIDER_OUTPUT_SCHEMA_INVALID");
        results.push(...validated);
      }
      let next = latestProfile.current;
      const nextReviews: Partial<Record<FieldKey, TranslationReview>> = {};
      let applied = 0;
      results.forEach((result, index) => {
        const item = items[index];
        const snapshot = snapshots[index];
        if (
          next[item.field][item.source_locale] !== item.text ||
          next[item.field][item.target_locale] !== snapshot.targetText ||
          editVersions.current[`${item.field}:${item.source_locale}`] !==
            snapshot.sourceVersion ||
          editVersions.current[`${item.field}:${item.target_locale}`] !==
            snapshot.targetVersion
        )
          return;
        next = {
          ...next,
          [item.field]: {
            ...next[item.field],
            [item.target_locale]: result.text,
          },
        };
        nextReviews[`${item.field}:${item.target_locale}`] = {
          previousText: snapshot.targetText,
          translatedText: result.text,
          reviewed: false,
          method: result.method,
        };
        applied += 1;
      });
      if (applied) {
        latestProfile.current = next;
        onChange(next);
        setReviews((current) => ({ ...current, ...nextReviews }));
      }
      setStatus({
        kind: "translated",
        applied,
        discarded: items.length - applied,
      });
      return {
        applied,
        discarded: items.length - applied,
        generation: currentGeneration,
      };
    } catch (error) {
      if (generation.current === currentGeneration)
        setErrorCode(error instanceof Error ? error.message : "REQUEST_FAILED");
    } finally {
      if (generation.current === currentGeneration) {
        requestAbort.current = null;
        setPending(false);
      }
    }
  }

  return {
    pending,
    status,
    errorCode,
    run,
    async fillEmpty() {
      const items = emptyProfileTranslationItems(
        latestProfile.current,
        supported,
      ).filter(
        (item) =>
          modelEnabled ||
          deriveConverter(item.source_locale, item.target_locale),
      );
      const first = await run(items);
      if (!first || generation.current !== first.generation) return;
      const derived = emptyProfileTranslationItems(
        latestProfile.current,
        supported,
      ).filter(
        (item) =>
          deriveConverter(item.source_locale, item.target_locale) &&
          !items.some(
            (previous) =>
              previous.field === item.field &&
              previous.target_locale === item.target_locale,
          ),
      );
      if (derived.length) {
        const second = await run(derived);
        if (second && generation.current === second.generation)
          setStatus({
            kind: "translated",
            applied: first.applied + second.applied,
            discarded: first.discarded + second.discarded,
          });
      }
    },
    review: (field: ProfileField, locale: LanguageTag) =>
      reviews[`${field}:${locale}`],
    unreviewedCount: PROFILE_FIELDS.reduce(
      (count, field) =>
        count +
        supported.filter((tag) => {
          const review = reviews[`${field}:${tag}`];
          return (
            review &&
            !review.reviewed &&
            review.translatedText === profile[field][tag]
          );
        }).length,
      0,
    ),
    edit(field: ProfileField, locale: LanguageTag, text: string) {
      const key: FieldKey = `${field}:${locale}`;
      editVersions.current[key] = (editVersions.current[key] ?? 0) + 1;
      markReviewed(field, locale);
      setField(field, locale, text);
    },
    markReviewed(field: ProfileField, locale: LanguageTag) {
      markReviewed(field, locale);
      setStatus({ kind: "reviewed" });
    },
    restore(field: ProfileField, locale: LanguageTag) {
      const review = reviews[`${field}:${locale}`];
      if (!review) return;
      const key: FieldKey = `${field}:${locale}`;
      editVersions.current[key] = (editVersions.current[key] ?? 0) + 1;
      markReviewed(field, locale);
      setField(field, locale, review.previousText);
      setStatus({ kind: "restored" });
    },
  };
}

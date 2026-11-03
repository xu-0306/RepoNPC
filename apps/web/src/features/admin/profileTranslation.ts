import { useEffect, useRef, useState } from "react";

import { LEGACY_LANGUAGES, type PairTag } from "../../i18n/languages";
import type { GuidedProfile } from "./guidedOnboarding";

export const PROFILE_FIELDS = ["headline", "bio", "greeting"] as const;
export type ProfileField = (typeof PROFILE_FIELDS)[number];

export interface ProfileTranslationItem {
  field: ProfileField;
  source_locale: PairTag;
  target_locale: PairTag;
  text: string;
}

export interface ProfileTranslationResult {
  field: ProfileField;
  target_locale: PairTag;
  text: string;
  method: "model";
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

export function profileLanguages(locale: string) {
  return [...LEGACY_LANGUAGES].sort(
    (left, right) => Number(right.tag === locale) - Number(left.tag === locale),
  );
}

export function profileTranslationSource(
  profile: GuidedProfile,
  field: ProfileField,
  target: PairTag,
): ProfileTranslationItem | undefined {
  const source = LEGACY_LANGUAGES.find(
    ({ tag }) => tag !== target && profile[field][tag].trim(),
  );
  return (
    source && {
      field,
      source_locale: source.tag,
      target_locale: target,
      text: profile[field][source.tag],
    }
  );
}

export function emptyProfileTranslationItems(profile: GuidedProfile) {
  return PROFILE_FIELDS.flatMap((field) =>
    LEGACY_LANGUAGES.flatMap(({ tag }) => {
      if (profile[field][tag].trim()) return [];
      const item = profileTranslationSource(profile, field, tag);
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
      item.method !== "model" ||
      item.confirmed !== false
    )
      return null;
    items.push({
      field: item.field,
      target_locale: item.target_locale,
      text: item.text,
      method: "model",
      confirmed: false,
    });
  }
  return items;
}

type FieldKey = `${ProfileField}:${PairTag}`;
interface TranslationReview {
  previousText: string;
  translatedText: string;
  reviewed: boolean;
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
  translate,
  onChange,
}: {
  profile: GuidedProfile;
  active: boolean;
  reset: boolean;
  modelGeneration: number | undefined;
  enabled: boolean;
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

  useEffect(() => {
    setPending(false);
    if (reset) {
      setReviews({});
      setStatus(null);
      setErrorCode("");
    }
    return () => {
      generation.current += 1;
      requestAbort.current?.abort();
      requestAbort.current = null;
    };
  }, [active, modelGeneration, reset]);

  function setField(field: ProfileField, locale: PairTag, text: string) {
    const current = latestProfile.current;
    const next = { ...current, [field]: { ...current[field], [locale]: text } };
    latestProfile.current = next;
    onChange(next);
  }

  function markReviewed(field: ProfileField, locale: PairTag) {
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
      const response = await translate(items, controller.signal);
      if (generation.current !== currentGeneration) return;
      const results = profileTranslationBody(response, items);
      if (!results) throw new Error("PROVIDER_OUTPUT_SCHEMA_INVALID");
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
    review: (field: ProfileField, locale: PairTag) =>
      reviews[`${field}:${locale}`],
    unreviewedCount: PROFILE_FIELDS.reduce(
      (count, field) =>
        count +
        LEGACY_LANGUAGES.filter(({ tag }) => {
          const review = reviews[`${field}:${tag}`];
          return (
            review &&
            !review.reviewed &&
            review.translatedText === profile[field][tag]
          );
        }).length,
      0,
    ),
    edit(field: ProfileField, locale: PairTag, text: string) {
      const key: FieldKey = `${field}:${locale}`;
      editVersions.current[key] = (editVersions.current[key] ?? 0) + 1;
      markReviewed(field, locale);
      setField(field, locale, text);
    },
    markReviewed(field: ProfileField, locale: PairTag) {
      markReviewed(field, locale);
      setStatus({ kind: "reviewed" });
    },
    restore(field: ProfileField, locale: PairTag) {
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

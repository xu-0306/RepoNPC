import type { CSSProperties } from "react";

import {
  deriveConverter,
  endonym,
  type LanguageTag as Locale,
} from "../../i18n/languages";
import { localizedTags, type GuidedProfile } from "./guidedOnboarding";
import { ConfirmButton } from "./ConfirmDialog";
import {
  PROFILE_FIELDS,
  fitHeight,
  profileLanguages,
  profileTranslationSource,
  type useProfileTranslation,
} from "./profileTranslation";

const FIELD_ROWS = { headline: 1, bio: 4, greeting: 3 } as const;

export function ProfileTranslationFields({
  locale,
  profile,
  supported = localizedTags(profile.headline),
  busy,
  modelReason,
  translation,
  copy,
}: {
  locale: Locale;
  profile: GuidedProfile;
  supported?: Locale[];
  busy: boolean;
  modelReason: string | null;
  translation: ReturnType<typeof useProfileTranslation>;
  copy: {
    headlineLabel: string;
    bioLabel: string;
    greetingLabel: string;
    p4Required: string;
    disabledBusy: string;
    translatingProfile: string;
    translateRequired: string;
    translationSourceRequired: string;
    retranslate: string;
    retranslateDescription: string;
    translationUnreviewed: string;
    conversionUnreviewed: string;
    markTranslationReviewed: string;
    restoreTranslation: string;
  };
}) {
  return PROFILE_FIELDS.map((field) => (
    <fieldset className="p4-w2__fields p4-w2__wide" disabled={busy} key={field}>
      <legend>{copy[`${field}Label`]}</legend>
      {profileLanguages(supported).map(({ tag, direction }) => {
        const id = `guided-profile-${field}-${tag}`;
        const value = profile[field][tag];
        const source = profileTranslationSource(profile, field, tag, supported);
        const review = translation.review(field, tag);
        const unreviewed =
          review && !review.reviewed && review.translatedText === value;
        const reason = busy
          ? copy.disabledBusy
          : translation.pending
            ? copy.translatingProfile
            : source &&
                deriveConverter(source.source_locale, source.target_locale)
              ? null
              : (modelReason ??
                (source ? null : copy.translationSourceRequired));
        // The section status line already says "translating"; six more copies are noise.
        const hint = !busy && translation.pending ? null : reason;
        const actionProps = {
          "aria-describedby": hint ? `${id}-translate-reason` : undefined,
          "aria-disabled": Boolean(reason),
          className: "px-button px-button--secondary",
        };
        const translate = () => {
          if (!reason && source) void translation.run([source]);
        };
        return (
          <div className="profile-translation__field" key={tag}>
            <label htmlFor={id}>{endonym(tag)}</label>
            <textarea
              className="px-field"
              id={id}
              dir={direction}
              lang={tag}
              aria-invalid={!value.trim() || undefined}
              aria-describedby={
                [
                  !value.trim() && `${id}-required`,
                  unreviewed && `${id}-review`,
                ]
                  .filter(Boolean)
                  .join(" ") || undefined
              }
              required
              onChange={(event) =>
                translation.edit(field, tag, event.target.value)
              }
              rows={FIELD_ROWS[field]}
              style={{ "--profile-rows": FIELD_ROWS[field] } as CSSProperties}
              ref={(element) => fitHeight(element)}
              value={value}
            />
            {!value.trim() && (
              <span className="p4-w2__required" id={`${id}-required`}>
                {copy.p4Required} {source && copy.translateRequired}
              </span>
            )}
            {unreviewed && (
              <p className="profile-translation__marker" id={`${id}-review`}>
                {review.method === "converted"
                  ? copy.conversionUnreviewed
                  : copy.translationUnreviewed}
              </p>
            )}
            <div className="profile-translation__actions">
              <ConfirmButton
                {...actionProps}
                locale={locale}
                title={`${copy.retranslate} — ${copy[`${field}Label`]} (${endonym(tag)})`}
                description={copy.retranslateDescription}
                confirmLabel={copy.retranslate}
                onClickCapture={(event) => {
                  if (reason || !value.trim()) {
                    event.stopPropagation();
                    if (!reason) translate();
                  }
                }}
                onConfirm={translate}
              >
                {copy.retranslate}
              </ConfirmButton>
              {review && (
                <>
                  <button
                    className="px-button px-button--secondary"
                    aria-disabled={!unreviewed}
                    type="button"
                    onClick={() => {
                      if (unreviewed) translation.markReviewed(field, tag);
                    }}
                  >
                    {copy.markTranslationReviewed}
                  </button>
                  <button
                    className="px-button px-button--secondary"
                    aria-disabled={value === review.previousText}
                    type="button"
                    onClick={() => translation.restore(field, tag)}
                  >
                    {copy.restoreTranslation}
                  </button>
                </>
              )}
            </div>
            {hint && (
              <p
                className="guided-onboarding__disabled-reason"
                id={`${id}-translate-reason`}
              >
                {hint}
              </p>
            )}
          </div>
        );
      })}
    </fieldset>
  ));
}

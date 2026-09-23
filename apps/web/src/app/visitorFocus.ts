/** Apply a deferred focus request only after the chat input is enabled again. */
export function focusQuestionAfterPendingClears(
  pending: boolean,
  requested: { current: boolean },
  input: Pick<HTMLTextAreaElement, "focus"> | null,
) {
  if (pending || !requested.current || input === null) return;
  requested.current = false;
  input.focus();
}

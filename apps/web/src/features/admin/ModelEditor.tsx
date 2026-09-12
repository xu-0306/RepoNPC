import { useEffect, useRef } from "react";
import type { ReactNode, RefObject } from "react";

export function ModelEditor({
  label,
  cancel,
  pending,
  error,
  editorRef,
  children,
  onClose,
  onOpen,
}: {
  label: string;
  cancel: string;
  pending: boolean;
  error: string;
  editorRef: RefObject<HTMLDetailsElement | null>;
  children: ReactNode;
  onClose?: () => void;
  onOpen?: () => void;
}) {
  const submitted = useRef(false);
  const wasPending = useRef(false);
  useEffect(() => {
    if (submitted.current && wasPending.current && !pending) {
      if (!error && editorRef.current) {
        editorRef.current.open = false;
        editorRef.current.querySelector("summary")?.focus();
        onClose?.();
      }
      submitted.current = false;
    }
    wasPending.current = pending;
  }, [pending, error, editorRef, onClose]);

  return (
    <details
      className="model-editor"
      ref={editorRef}
      onToggle={(event) => {
        if (!event.currentTarget.open) onClose?.();
        else onOpen?.();
      }}
      onSubmitCapture={() => {
        submitted.current = true;
      }}
    >
      <summary
        aria-disabled={pending}
        onClick={(event) => {
          if (pending) event.preventDefault();
        }}
      >
        {label}
      </summary>
      {children}
      <button
        className="model-editor__close"
        disabled={pending}
        onClick={() => {
          if (editorRef.current) {
            editorRef.current.open = false;
            editorRef.current.querySelector("summary")?.focus();
            onClose?.();
          }
        }}
        type="button"
      >
        {cancel}
      </button>
    </details>
  );
}

import { useCallback, useEffect, useId, useRef, useState } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import {
  Button,
  Dialog,
  Heading,
  Modal,
  ModalOverlay,
} from "react-aria-components";

import type { Locale } from "../../i18n/messages";

interface ConfirmRequest {
  title: string;
  description: string;
  confirmLabel: string;
  destructive?: boolean;
}

export function ConfirmDialogView({
  locale,
  title,
  description,
  descriptionId,
  confirmLabel,
  destructive = false,
  onClose,
}: ConfirmRequest & {
  locale: Locale;
  descriptionId: string;
  onClose: (confirmed: boolean) => void;
}) {
  return (
    <ModalOverlay
      className="admin-confirm-overlay"
      isOpen
      isDismissable={false}
      onOpenChange={(open) => {
        if (!open) onClose(false);
      }}
    >
      <Modal className="admin-confirm-modal">
        <Dialog
          role="alertdialog"
          className="admin-confirm-dialog"
          aria-describedby={descriptionId}
          lang={locale}
        >
          <Heading slot="title">{title}</Heading>
          <p
            id={descriptionId}
            className="admin-confirm-dialog__description"
            style={{ whiteSpace: "pre-line" }}
          >
            {description}
          </p>
          <div className="admin-confirm-dialog__actions">
            <Button autoFocus onPress={() => onClose(false)}>
              {locale === "zh-TW" ? "取消" : "Cancel"}
            </Button>
            <Button
              className={
                destructive
                  ? "admin-confirm-dialog__confirm admin-confirm-dialog__confirm--destructive"
                  : "admin-confirm-dialog__confirm"
              }
              onPress={() => onClose(true)}
            >
              {confirmLabel}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

export function ConfirmButton({
  locale,
  title,
  description,
  confirmLabel,
  destructive,
  onConfirm,
  children,
  disabled,
  ...buttonProps
}: ConfirmRequest &
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, "title" | "onClick"> & {
    locale: Locale;
    onConfirm: () => void;
  }) {
  const [open, setOpen] = useState(false);
  const descriptionId = useId();
  return (
    <>
      <button
        {...buttonProps}
        type="button"
        disabled={disabled}
        onClick={() => {
          if (!disabled) setOpen(true);
        }}
      >
        {children}
      </button>
      {open && (
        <ConfirmDialogView
          locale={locale}
          title={title}
          description={description}
          descriptionId={descriptionId}
          confirmLabel={confirmLabel}
          destructive={destructive}
          onClose={(confirmed) => {
            setOpen(false);
            if (confirmed && !disabled) onConfirm();
          }}
        />
      )}
    </>
  );
}

export function useConfirmDialog(
  locale: Locale,
): [ReactNode, (request: ConfirmRequest) => Promise<boolean>] {
  const [request, setRequest] = useState<ConfirmRequest | null>(null);
  const resolve = useRef<((confirmed: boolean) => void) | null>(null);
  const descriptionId = useId();
  useEffect(() => () => resolve.current?.(false), []);
  const confirm = useCallback((next: ConfirmRequest) => {
    resolve.current?.(false);
    return new Promise<boolean>((done) => {
      resolve.current = done;
      setRequest(next);
    });
  }, []);
  return [
    request && (
      <ConfirmDialogView
        {...request}
        locale={locale}
        descriptionId={descriptionId}
        onClose={(confirmed) => {
          resolve.current?.(confirmed);
          resolve.current = null;
          setRequest(null);
        }}
      />
    ),
    confirm,
  ];
}

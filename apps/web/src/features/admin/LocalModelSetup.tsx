import { useCallback, useEffect, useRef, useState } from "react";

import type { Locale } from "../../i18n/messages";
import { BuiltinModelPanel } from "./BuiltinModelPanel";

type Info = NonNullable<Parameters<typeof BuiltinModelPanel>[0]["info"]>;
type Operation = NonNullable<
  Parameters<typeof BuiltinModelPanel>[0]["operation"]
>;
type Request = <T>(path: string, init?: RequestInit) => Promise<T>;

export function LocalModelSetup({
  locale,
  request,
  onProfilesChanged,
  onLater,
}: {
  locale: Locale;
  request: Request;
  onProfilesChanged: () => Promise<void>;
  onLater?: () => void;
}) {
  const [info, setInfo] = useState<Info | null>(null);
  const [operation, setOperation] = useState<Operation | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const lifetime = useRef(0);
  const operationId = operation?.operation_id;
  const active =
    operation?.status === "queued" || operation?.status === "running";
  const failure =
    locale === "zh-TW"
      ? "模型設定暫時無法完成。請重新整理或重試；手動編輯仍可使用。"
      : "Model setup could not finish. Refresh or retry; manual editing remains available.";

  const refresh = useCallback(async () => {
    const generation = lifetime.current;
    try {
      const value = await request<Info & { operation: Operation | null }>(
        "/api/admin/embedding-models/builtin",
      );
      if (generation !== lifetime.current) return;
      setInfo(value);
      setOperation(value.operation);
      setError("");
    } catch {
      if (generation === lifetime.current) setError(failure);
    }
  }, [request, failure]);

  useEffect(() => {
    const generation = ++lifetime.current;
    void refresh();
    return () => {
      lifetime.current = generation + 1;
    };
  }, [refresh]);

  useEffect(() => {
    if (!active || !operationId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const value = await request<Operation>(
          `/api/admin/embedding-model-operations/${encodeURIComponent(operationId)}`,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        setOperation(value);
        if (value.status === "queued" || value.status === "running")
          timer = setTimeout(() => void poll(), 1000);
        else {
          await onProfilesChanged();
          await refresh();
        }
      } catch {
        if (!controller.signal.aborted) setError(failure);
      }
    };
    timer = setTimeout(() => void poll(), 1000);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [active, operationId, request, onProfilesChanged, refresh, failure]);

  async function download() {
    const generation = lifetime.current;
    setPending(true);
    setError("");
    try {
      const value = await request<Operation>(
        "/api/admin/embedding-models/builtin/download",
        { method: "POST", body: JSON.stringify({ confirmed: true }) },
      );
      if (generation !== lifetime.current) return;
      setOperation(value);
      await onProfilesChanged();
      await refresh();
    } catch {
      if (generation === lifetime.current) setError(failure);
    } finally {
      if (generation === lifetime.current) setPending(false);
    }
  }

  async function cancel() {
    if (!operationId) return;
    const generation = lifetime.current;
    setPending(true);
    try {
      const value = await request<Operation>(
        `/api/admin/embedding-model-operations/${encodeURIComponent(operationId)}`,
        { method: "DELETE" },
      );
      if (generation === lifetime.current) setOperation(value);
    } catch {
      if (generation === lifetime.current) setError(failure);
    } finally {
      if (generation === lifetime.current) setPending(false);
    }
  }

  return (
    <>
      <BuiltinModelPanel
        locale={locale}
        info={info}
        operation={operation}
        pending={pending}
        error={error}
        onDownload={() => void download()}
        onCancel={() => void cancel()}
        onRefresh={() => void refresh()}
        onExternal={() => {
          const target = document.getElementById("embedding-external-setup");
          target?.scrollIntoView({ block: "start" });
          const summary = target?.querySelector<HTMLElement>("summary");
          if (summary && !summary.parentElement?.hasAttribute("open"))
            summary.click();
          (
            target?.querySelector<HTMLElement>("input") ??
            summary ??
            target?.querySelector<HTMLElement>("button")
          )?.focus();
        }}
        onLater={() => {
          if (onLater) onLater();
          else document.getElementById("admin-config-draft")?.focus();
        }}
      />
    </>
  );
}

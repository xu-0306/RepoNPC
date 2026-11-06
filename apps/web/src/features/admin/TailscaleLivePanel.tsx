import {
  cloneElement,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactElement,
} from "react";
import { chromeLocale } from "../../i18n/languages";
import type { AdminLocale } from "./AdminWorkspace";
import { ModelSetupRequests } from "./modelSetupRequests";
import { sectionRef } from "./sharingSections";
import {
  tailscaleErrorMessage,
  tailscaleGuide,
  type TailscaleActionResult,
  type TailscaleStatus,
} from "./tailscaleFunnel";
import type {
  VisitorGatewayRequest,
  VisitorGatewayStatus,
} from "./VisitorGatewayPanel";

export function TailscaleLivePanel({
  locale,
  request,
  pagesOrigin,
  gateway,
  onChanged,
  children,
}: {
  locale: AdminLocale;
  request: VisitorGatewayRequest;
  pagesOrigin: string | null;
  gateway: VisitorGatewayStatus | null;
  onChanged: () => void;
  /** Keep the manual disclosure's default in sync without adding parent hooks. */
  children?: ReactElement<{ open?: boolean }>;
}) {
  const zh = chromeLocale(locale) === "zh-TW";
  const [status, setStatus] = useState<TailscaleStatus | null>(null);
  const [pending, setPending] = useState(false);
  const [errorCode, setErrorCode] = useState<unknown>(null);
  const requests = useRef(new ModelSetupRequests());
  const mounted = useRef(false);
  const pendingCount = useRef(0);
  const mutating = useRef(false);

  const refresh = useCallback(async () => {
    if (mutating.current) return;
    pendingCount.current += 1;
    setPending(true);
    try {
      await requests.current.read(
        () => request<TailscaleStatus>("/api/admin/tailscale/status"),
        (next) => {
          if (mounted.current) setStatus(next);
        },
      );
    } catch (error) {
      if (mounted.current) {
        setStatus({
          state: "error",
          funnel_url: null,
          port: null,
          version: null,
        });
        setErrorCode(error instanceof Error ? error.message : error);
      }
    } finally {
      pendingCount.current -= 1;
      if (mounted.current) setPending(pendingCount.current > 0);
    }
  }, [request]);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const focus = () => void refresh();
    window.addEventListener("focus", focus);
    return () => {
      mounted.current = false;
      window.removeEventListener("focus", focus);
    };
  }, [refresh]);

  const running = Boolean(
    gateway?.listener_ready && gateway.gateway_origin === status?.funnel_url,
  );
  const canStart = status?.state === "ready" || status?.state === "live";
  const canStop = status?.state === "live" || gateway?.enabled;

  async function act(action: "start" | "stop") {
    if (
      pendingCount.current > 0 ||
      !gateway ||
      (action === "start" &&
        (!pagesOrigin || !gateway.local_ready || !canStart || running)) ||
      (action === "stop" && !canStop)
    )
      return;
    pendingCount.current += 1;
    mutating.current = true;
    setPending(true);
    setErrorCode(null);
    try {
      await requests.current.mutate(
        () =>
          request<TailscaleActionResult>(
            `/api/admin/tailscale/funnel/${action}`,
            {
              method: "POST",
              body: JSON.stringify({ revision: gateway.revision }),
            },
          ),
        (next) => {
          if (!mounted.current) return;
          setStatus(next.tailscale);
          onChanged();
        },
      );
    } catch (error) {
      if (mounted.current)
        setErrorCode(error instanceof Error ? error.message : error);
    } finally {
      pendingCount.current -= 1;
      mutating.current = false;
      if (mounted.current) await refresh();
    }
  }

  const advanced = children
    ? cloneElement(children, {
        open:
          status?.state === "unavailable_profile" &&
          Boolean(gateway?.gateway_origin),
      })
    : null;
  if (!status || status.state === "unavailable_profile") return advanced;

  const guide = tailscaleGuide(status.state, locale);
  const instruction =
    status.state === "live" && !running
      ? zh
        ? "Funnel 已開啟，但訪客連線已停止。按「開啟即時聊天」重新啟動。"
        : "Funnel is on, but the visitor connection is stopped. Select Turn on live chat to start it again."
      : guide.text;
  const needsPages = zh
    ? `請先在${sectionRef(locale, "pages")}儲存 Pages 網址，再開啟即時聊天。`
    : `Save your Pages URL in ${sectionRef(locale, "pages")} before you turn on live chat.`;

  const needsPrepared = zh
    ? `請先在${sectionRef(locale, "prepare")}準備好 NPC，再開啟即時聊天。`
    : `Prepare the NPC in ${sectionRef(locale, "prepare")} before you turn on live chat.`;

  return (
    <>
      <div className="px-panel px-panel--inset">
        <p role="status">
          {status.state === "live"
            ? zh
              ? "即時聊天：已開啟。"
              : "Live chat: on."
            : zh
              ? "即時聊天：未開啟。"
              : "Live chat: off."}
          {status.state === "live" &&
            status.funnel_url &&
            ` ${status.funnel_url}`}
        </p>
        <p id="tailscale-live-instruction">
          {instruction}
          {guide.link && (
            <>
              {" "}
              <a
                href={guide.link.href}
                target="_blank"
                rel="noreferrer noopener"
              >
                {guide.link.label}
              </a>
            </>
          )}
        </p>
        {!pagesOrigin && canStart && !running && (
          <p id="tailscale-live-pages">{needsPages}</p>
        )}
        {pagesOrigin &&
          gateway &&
          !gateway.local_ready &&
          canStart &&
          !running && <p id="tailscale-live-prepared">{needsPrepared}</p>}
        {errorCode !== null && (
          <p role="alert">{tailscaleErrorMessage(errorCode, locale)}</p>
        )}
        <div className="publication-actions">
          {canStart && !running && (
            <button
              className="px-button px-button--primary"
              type="button"
              aria-describedby={
                !pagesOrigin
                  ? "tailscale-live-instruction tailscale-live-pages"
                  : gateway && !gateway.local_ready
                    ? "tailscale-live-instruction tailscale-live-prepared"
                    : "tailscale-live-instruction"
              }
              disabled={
                !pagesOrigin || !gateway || !gateway.local_ready || pending
              }
              onClick={() => void act("start")}
            >
              {zh ? "開啟即時聊天" : "Turn on live chat"}
            </button>
          )}
          {canStop && (
            <button
              className="px-button px-button--secondary"
              type="button"
              aria-describedby="tailscale-live-instruction"
              disabled={!gateway || pending}
              onClick={() => void act("stop")}
            >
              {zh ? "關閉即時聊天" : "Turn off live chat"}
            </button>
          )}
          <button
            className="px-button px-button--secondary"
            type="button"
            aria-describedby="tailscale-live-instruction"
            disabled={pending}
            onClick={() => {
              if (pendingCount.current > 0) return;
              setErrorCode(null);
              void refresh();
            }}
          >
            {zh ? "重新檢查" : "Check again"}
          </button>
        </div>
      </div>
      {advanced}
    </>
  );
}

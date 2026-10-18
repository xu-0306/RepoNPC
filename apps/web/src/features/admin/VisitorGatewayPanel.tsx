import { useCallback, useEffect, useRef, useState } from "react";
import type { AdminLocale } from "./AdminWorkspace";
import { ModelSetupRequests } from "./modelSetupRequests";
import { funnelHttpsPort } from "./visitorGatewayPort";

export interface VisitorGatewayStatus {
  revision: number;
  gateway_origin: string | null;
  pages_origin: string | null;
  enabled: boolean;
  listener_ready: boolean;
  error_code: string | null;
  local_ready: boolean;
  entry_configured: boolean;
  external_verified: boolean;
  verified_at: string | null;
  verification_method: "owner_reported" | null;
  active_bundle_id: string | null;
  client_identity_mode: "aggregate" | "trusted_proxy";
}

export type VisitorGatewayRequest = <T>(
  path: string,
  options?: RequestInit,
) => Promise<T>;
type Request = VisitorGatewayRequest;
type GatewayError =
  | "conflict"
  | "configuration"
  | "unavailable"
  | "auth"
  | "csrf"
  | "validation"
  | "service"
  | "unknown";

const ERROR_MESSAGES: Record<GatewayError, Record<AdminLocale, string>> = {
  conflict: {
    "zh-TW": "設定已在其他位置變更。請載入最新設定後再編輯。",
    en: "The settings changed elsewhere. Load the latest settings before editing.",
  },
  configuration: {
    "zh-TW":
      "網址或 gateway 狀態不符合設定條件；請檢查兩個網址，並在變更前先停止 gateway。",
    en: "The origins or gateway state do not meet the configuration requirements. Check both origins and stop the gateway before changing them.",
  },
  unavailable: {
    "zh-TW": "本機 gateway 無法完成操作。請確認本機就緒狀態與連接埠後重試。",
    en: "The local gateway could not complete the operation. Check local readiness and the port, then retry.",
  },
  auth: {
    "zh-TW": "管理工作階段已失效。請重新登入後再試。",
    en: "The admin session has expired. Sign in again and retry.",
  },
  csrf: {
    "zh-TW": "安全工作階段已過期。請重新載入管理頁後再試。",
    en: "The security session has expired. Reload the admin page and retry.",
  },
  validation: {
    "zh-TW": "設定格式不正確。請檢查輸入的兩個來源網址。",
    en: "The settings are invalid. Check both origin values.",
  },
  service: {
    "zh-TW": "本機訪客服務尚未就緒。請先準備內容並確認回答服務可用。",
    en: "The local visitor service is not ready. Prepare the portfolio and make sure the answer service is available.",
  },
  unknown: {
    "zh-TW": "操作未完成。請檢查管理工作階段與本機服務狀態後重試。",
    en: "The operation could not be completed. Check the admin session and local service, then retry.",
  },
};

function gatewayErrorKind(code: unknown): GatewayError {
  switch (code) {
    case "GATEWAY_CONFLICT":
      return "conflict";
    case "GATEWAY_CONFIGURATION_INVALID":
      return "configuration";
    case "GATEWAY_UNAVAILABLE":
      return "unavailable";
    case "AUTHENTICATION_REQUIRED":
      return "auth";
    case "CSRF_FAILED":
      return "csrf";
    case "VALIDATION_ERROR":
      return "validation";
    case "SERVICE_NOT_READY":
      return "service";
    default:
      return "unknown";
  }
}

export function visitorGatewayErrorMessage(
  code: unknown,
  locale: AdminLocale,
): string {
  return ERROR_MESSAGES[gatewayErrorKind(code)][locale];
}

function useVisitorGateway(request: Request, locale: AdminLocale) {
  const [status, setStatus] = useState<VisitorGatewayStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const pendingRef = useRef(false);
  const mounted = useRef(false);
  const requests = useRef(new ModelSetupRequests());

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    if (pendingRef.current) return null;
    let response: VisitorGatewayStatus | null = null;
    try {
      await requests.current.read(
        () => request<VisitorGatewayStatus>("/api/admin/visitor-gateway"),
        (next) => {
          if (!mounted.current) return;
          response = next;
          setStatus(next);
          setLoadFailed(false);
        },
      );
    } catch {
      if (mounted.current) setLoadFailed(true);
    } finally {
      if (mounted.current) setLoading(false);
    }
    return response;
  }, [request]);

  useEffect(() => {
    let closed = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      await refresh();
      if (!closed) timer = setTimeout(() => void poll(), 3000);
    };
    void poll();
    return () => {
      closed = true;
      clearTimeout(timer);
    };
  }, [refresh]);

  const mutate = useCallback(
    async (
      path: string,
      method: "PUT" | "POST",
      body: Record<string, string | number | boolean | null>,
    ) => {
      if (pendingRef.current) return null;
      pendingRef.current = true;
      setPending(true);
      setNotice("");
      let refreshAfterMutation = false;
      try {
        return await requests.current.mutate(
          () =>
            request<VisitorGatewayStatus>(path, {
              method,
              body: JSON.stringify(body),
            }),
          (next) => {
            if (!mounted.current) return;
            setStatus(next);
            setLoadFailed(false);
          },
        );
      } catch (error) {
        if (mounted.current) {
          const code = error instanceof Error ? error.message : error;
          setNotice(visitorGatewayErrorMessage(code, locale));
          refreshAfterMutation = true;
        }
        return null;
      } finally {
        pendingRef.current = false;
        if (mounted.current) {
          setPending(false);
          if (refreshAfterMutation) void refresh();
        }
      }
    },
    [locale, refresh, request],
  );

  return { status, loading, loadFailed, pending, notice, refresh, mutate };
}

interface GatewayDraft {
  gateway: string;
  pages: string;
  revision: number;
  baseGateway: string;
  basePages: string;
}

function originValue(value: string | null | undefined) {
  return value?.trim() ?? "";
}

function draftChanged(
  draft: GatewayDraft | null,
  status: VisitorGatewayStatus | null,
) {
  return Boolean(
    draft &&
      status &&
      (originValue(draft.gateway) !== (status.gateway_origin ?? "") ||
        originValue(draft.pages) !== (status.pages_origin ?? "")),
  );
}

export function VisitorGatewayPanel({
  locale,
  request,
  publicSharingAvailable = true,
}: {
  locale: AdminLocale;
  request: Request;
  /** False under the loopback evaluation profile, which cannot run the gateway. */
  publicSharingAvailable?: boolean;
}) {
  const zh = locale === "zh-TW";
  const gateway = useVisitorGateway(request, locale);
  const status = gateway.status;
  const [draft, setDraft] = useState<GatewayDraft | null>(null);
  const serverGateway = status?.gateway_origin ?? "";
  const serverPages = status?.pages_origin ?? "";
  const changed = draftChanged(draft, status);
  const gatewayValue = changed ? (draft?.gateway ?? "") : serverGateway;
  const pagesValue = changed ? (draft?.pages ?? "") : serverPages;
  const hasBothOrNeither =
    Boolean(gatewayValue.trim()) === Boolean(pagesValue.trim());
  const localListenerActive = Boolean(
    status?.enabled || status?.listener_ready,
  );
  const funnelPort = funnelHttpsPort(gatewayValue);
  const funnelPortText = funnelPort ?? "<https-port>";
  const canStart = Boolean(
    status &&
      publicSharingAvailable &&
      !gateway.pending &&
      !changed &&
      status.local_ready &&
      status.gateway_origin &&
      status.pages_origin &&
      !status.listener_ready,
  );
  const canStop = Boolean(status && !gateway.pending && localListenerActive);
  const [checks, setChecks] = useState([false, false, false, false]);
  const checksComplete = checks.every(Boolean);
  const canVerify = Boolean(
    status &&
      !gateway.pending &&
      !changed &&
      status.local_ready &&
      status.listener_ready &&
      status.gateway_origin &&
      status.pages_origin &&
      status.active_bundle_id &&
      checksComplete,
  );

  function edit(field: "gateway" | "pages", value: string) {
    if (!status) return;
    setDraft((current) => {
      const keepCurrent = draftChanged(current, status);
      const base =
        keepCurrent && current
          ? current
          : {
              gateway: status.gateway_origin ?? "",
              pages: status.pages_origin ?? "",
              revision: status.revision,
              baseGateway: status.gateway_origin ?? "",
              basePages: status.pages_origin ?? "",
            };
      return { ...base, [field]: value };
    });
  }

  async function save() {
    if (!status || !draft || !changed || !hasBothOrNeither) return;
    const saved = await gateway.mutate("/api/admin/visitor-gateway", "PUT", {
      revision: draft.revision,
      gateway_origin: draft.gateway.trim() || null,
      pages_origin: draft.pages.trim() || null,
    });
    if (saved) {
      setDraft(null);
      setChecks([false, false, false, false]);
    }
  }

  function rebaseDraft(next: VisitorGatewayStatus) {
    setDraft((current) => {
      if (!draftChanged(current, status) || !current) return null;
      return {
        ...current,
        revision: next.revision,
        baseGateway: next.gateway_origin ?? "",
        basePages: next.pages_origin ?? "",
      };
    });
  }

  async function start() {
    if (!status) return;
    const next = await gateway.mutate(
      "/api/admin/visitor-gateway/start",
      "POST",
      { revision: status.revision },
    );
    if (next) {
      rebaseDraft(next);
      setChecks([false, false, false, false]);
    }
  }

  async function stop() {
    if (!status) return;
    const next = await gateway.mutate(
      "/api/admin/visitor-gateway/stop",
      "POST",
      { revision: status.revision },
    );
    if (next) {
      rebaseDraft(next);
      setChecks([false, false, false, false]);
    }
  }

  async function verify() {
    if (!status || !canVerify) return;
    const next = await gateway.mutate(
      "/api/admin/visitor-gateway/verify",
      "POST",
      {
        revision: status.revision,
        external_checks_confirmed: true,
      },
    );
    if (next) {
      setDraft(null);
      setChecks([false, false, false, false]);
    }
  }

  const checklist = zh
    ? [
        "使用非 tailnet 的獨立外網檢查",
        "開啟公開狀態頁與個人資料頁",
        "實際使用聊天並檢查引用來源",
        "確認管理、模型與未知路徑無法從公開入口存取",
      ]
    : [
        "Check from an independent network outside your tailnet",
        "Open the public status and profile pages",
        "Use chat and inspect its citations",
        "Confirm admin, model, and unknown paths are unavailable publicly",
      ];
  const fact = (ready: boolean) =>
    ready ? (zh ? "就緒" : "Ready") : zh ? "未就緒" : "Not ready";

  return (
    <section
      aria-labelledby="visitor-gateway-heading"
      className="admin-surface visitor-gateway"
    >
      <h2 id="visitor-gateway-heading">
        {zh ? "2. 設定訪客連線" : "2. Set up visitor access"}
      </h2>
      <p>
        {zh
          ? "這裡只設定 RepoNPC 的訪客入口。主機與已選回答模型必須保持可用；停止分享不會影響本機預覽、準備內容、FAQ 審核或一般編輯。"
          : "Configure only the RepoNPC visitor entry here. The host and selected answer model must stay available. Stopping sharing does not affect local preview, preparation, FAQ review, or ordinary editing."}
      </p>
      {!publicSharingAvailable && (
        <p role="note">
          {zh
            ? "目前是本機試用模式，無法公開分享。本機預覽和卡片圖仍可使用；要公開分享，請改用正式模式啟動 RepoNPC。"
            : "RepoNPC is running in local trial mode, so public sharing is unavailable. Local preview and the card image still work; to share publicly, start RepoNPC in production mode."}
        </p>
      )}

      {gateway.loading && !status && (
        <p role="status">
          {zh ? "正在載入 gateway 狀態…" : "Loading gateway status…"}
        </p>
      )}
      {gateway.loadFailed && (
        <p role="alert">
          {zh
            ? "目前無法讀取 gateway 狀態；請確認管理工作階段後重新整理。"
            : "Gateway status could not be read. Check the admin session and refresh."}
        </p>
      )}
      {gateway.notice && <p role="alert">{gateway.notice}</p>}

      {status && (
        <>
          <dl className="visitor-gateway__facts">
            <div>
              <dt>{zh ? "本機內容與聊天" : "Local content and chat"}</dt>
              <dd>{fact(status.local_ready)}</dd>
            </div>
            <div>
              <dt>{zh ? "訪客網址設定" : "Visitor address configuration"}</dt>
              <dd>{fact(status.entry_configured)}</dd>
            </div>
            <div>
              <dt>
                {zh ? "擁有者回報的外網檢查" : "Owner-reported external check"}
              </dt>
              <dd>{fact(status.external_verified)}</dd>
            </div>
            <div>
              <dt>{zh ? "本機訪客服務" : "Local visitor service"}</dt>
              <dd>
                {status.listener_ready
                  ? zh
                    ? "執行中"
                    : "Running"
                  : status.enabled
                    ? zh
                      ? "已要求啟動，但尚未就緒"
                      : "Start requested, but not ready"
                    : zh
                      ? "已停止"
                      : "Stopped"}
              </dd>
            </div>
          </dl>

          {status.error_code && (
            <p role="alert">
              {visitorGatewayErrorMessage(status.error_code, locale)}
            </p>
          )}
          {status.local_ready === false && (
            <p>
              {zh
                ? "先在本機準備可用版本，並確認已選回答模型可用，再啟動訪客入口。"
                : "Prepare a local version and make sure the selected answer model is available before starting the visitor entry."}
            </p>
          )}

          <p>
            {status.client_identity_mode === "aggregate"
              ? zh
                ? "訪客保護模式：共用每日額度與同時工作上限；不採用轉送的訪客身分。"
                : "Visitor protection: shared daily and concurrency limits; forwarded visitor identity is ignored."
              : zh
                ? "訪客保護模式：使用已設定的 loopback proxy 身分限制。依賴該 proxy 的來源位址覆寫行為；未完成外網確認前請勿依賴個別 IP 保護。"
                : "Visitor protection: configured loopback-proxy identity limits. These depend on the proxy's source-address overwrite behavior; do not rely on per-IP protection until externally confirmed."}
          </p>
        </>
      )}

      <fieldset
        className="visitor-gateway__origins"
        disabled={!status || gateway.pending || !publicSharingAvailable}
      >
        <legend>
          {zh
            ? "填入聊天入口與網站網域"
            : "Enter the chat address and site domain"}
        </legend>
        <label htmlFor="visitor-gateway-origin">
          {zh ? "Tailscale Funnel 訪客網址" : "Tailscale Funnel visitor origin"}
          <input
            autoCapitalize="none"
            autoComplete="url"
            id="visitor-gateway-origin"
            maxLength={2048}
            onChange={(event) => edit("gateway", event.target.value)}
            spellCheck={false}
            type="url"
            value={gatewayValue}
          />
        </label>
        <label htmlFor="visitor-pages-origin">
          {zh
            ? "GitHub Pages 網域（不含專案路徑）"
            : "GitHub Pages domain (without a project path)"}
          <input
            aria-describedby="visitor-pages-origin-help"
            placeholder="https://account.github.io"
            autoCapitalize="none"
            autoComplete="url"
            id="visitor-pages-origin"
            maxLength={2048}
            onChange={(event) => edit("pages", event.target.value)}
            spellCheck={false}
            type="url"
            value={pagesValue}
          />
        </label>
      </fieldset>
      <p id="visitor-pages-origin-help">
        {zh
          ? "例如網站是 https://account.github.io/project/，這裡只填 https://account.github.io。下一步再填完整網站網址。儲存後啟動本機訪客服務，並依下方說明在 Tailscale 啟用 Funnel。"
          : "For https://account.github.io/project/, enter only https://account.github.io here. Enter the full site URL in the next step. After saving, start the local visitor service and enable Funnel in Tailscale using the instructions below."}
      </p>
      <p>
        {zh
          ? "必須同時填入兩個網址，或同時清空。儲存不會驗證 Pages 託管狀態、GitHub 卡片或外網連線。gateway 執行中時，須先停止才能變更來源。"
          : "Enter both origins or clear both. Saving does not verify Pages hosting, GitHub cards, or external reachability. Stop the gateway before changing origins while it is running."}
      </p>
      {changed && status?.external_verified && (
        <p role="status">
          {zh
            ? "外網檢查狀態只適用於已儲存的網址；目前未儲存的編輯尚未檢查。"
            : "The external-check status applies only to the saved origins. These unsaved edits have not been checked."}
        </p>
      )}
      {changed && !hasBothOrNeither && (
        <p role="alert">
          {zh
            ? "請同時填入兩個來源網址，或同時清空。"
            : "Enter both origins or clear both."}
        </p>
      )}
      {changed && status?.enabled && (
        <p role="status">
          {zh
            ? "請先停止 gateway，再儲存來源變更。"
            : "Stop the gateway before saving origin changes."}
        </p>
      )}

      <div className="admin-workspace__actions visitor-gateway__actions">
        <button
          disabled={
            !status ||
            !publicSharingAvailable ||
            !changed ||
            !hasBothOrNeither ||
            localListenerActive ||
            gateway.pending
          }
          onClick={() => void save()}
          type="button"
        >
          {zh ? "儲存來源網址" : "Save origins"}
        </button>
        {changed && (
          <button
            disabled={gateway.pending}
            onClick={() => {
              setDraft(null);
              void gateway.refresh();
            }}
            type="button"
          >
            {zh
              ? "捨棄變更並載入最新設定"
              : "Discard changes and load latest settings"}
          </button>
        )}
        <button disabled={!canStart} onClick={() => void start()} type="button">
          {status?.enabled
            ? zh
              ? "重試啟動訪客連線"
              : "Retry starting visitor access"
            : zh
              ? "啟動訪客連線"
              : "Start visitor access"}
        </button>
        <button disabled={!canStop} onClick={() => void stop()} type="button">
          {zh ? "停止本機訪客連線" : "Stop local visitor access"}
        </button>
        <button
          disabled={!status || gateway.pending}
          onClick={() => void gateway.refresh()}
          type="button"
        >
          {zh ? "重新整理狀態" : "Refresh status"}
        </button>
      </div>

      {status && (
        <section aria-labelledby="visitor-gateway-verification-heading">
          <h3 id="visitor-gateway-verification-heading">
            {zh ? "由擁有者確認外網連線" : "Owner-confirmed external checks"}
          </h3>
          <p>
            {status.external_verified &&
            status.verification_method === "owner_reported"
              ? zh
                ? `目前訪客服務啟動期間已由擁有者回報檢查完成；時間：${status.verified_at ?? "未知"}。這是當時的觀察，不是持續連線監控。`
                : `The owner reported completing the checks during this visitor service start at ${status.verified_at ?? "an unknown time"}. This is a dated observation, not ongoing uptime monitoring.`
              : status.verified_at &&
                  status.verification_method === "owner_reported"
                ? zh
                  ? `上次擁有者回報檢查時間：${status.verified_at}。目前檢查已失效，請重新完成清單。`
                  : `Last owner-reported check: ${status.verified_at}. It is no longer current; complete the checklist again.`
                : zh
                  ? "尚無擁有者回報的外網檢查。"
                  : "No owner-reported external check is recorded."}
          </p>
          {status.active_bundle_id && (
            <p>
              {zh ? "目前版本：" : "Active bundle: "}
              <code>{status.active_bundle_id}</code>
            </p>
          )}
          <fieldset
            className="visitor-gateway__checklist"
            disabled={gateway.pending}
          >
            <legend>
              {zh
                ? "只有完成所有獨立外網檢查後才勾選"
                : "Check each item only after completing the independent external test"}
            </legend>
            {checklist.map((item, index) => (
              <label key={item}>
                <input
                  checked={checks[index]}
                  onChange={(event) =>
                    setChecks(
                      checks.map((checked, itemIndex) =>
                        itemIndex === index ? event.target.checked : checked,
                      ),
                    )
                  }
                  type="checkbox"
                />
                <span>{item}</span>
              </label>
            ))}
          </fieldset>
          <button
            disabled={!canVerify}
            onClick={() => void verify()}
            type="button"
          >
            {zh ? "記錄擁有者回報檢查" : "Record owner-reported check"}
          </button>
          <p>
            {zh
              ? "重新啟動、停止或來源變更會清除檢查；版本與本機就緒變更不會清除這筆當時的觀察；Funnel 或網際網路的未觀察中斷不會被偵測。這不會驗證 GitHub Pages 或卡片。"
              : "Restart, stop or origin changes clear the check. Bundle and local readiness changes do not clear this dated observation. Unobserved Funnel or internet outages are not detected. This does not verify GitHub Pages or cards."}
          </p>
        </section>
      )}

      <details className="visitor-gateway__commands">
        <summary>
          {zh
            ? "官方 Tailscale Funnel 指令（僅顯示）"
            : "Official Tailscale Funnel commands (display only)"}
        </summary>
        <p>
          {zh
            ? "請自行在 Tailscale 官方流程安裝、登入、授權並執行指令。RepoNPC 不會執行命令或管理 Tailscale。"
            : "Install, sign in, authorize, and run these commands yourself through Tailscale's official flow. RepoNPC does not run commands or manage Tailscale."}
        </p>
        <p>
          {funnelPort
            ? zh
              ? "請將 <visitor-port> 替換為 REPONPC_VISITOR_GATEWAY_PORT；預設值為 8001。"
              : "Replace <visitor-port> with REPONPC_VISITOR_GATEWAY_PORT; the default is 8001."
            : zh
              ? "請將 <https-port> 替換為訪客網址的連接埠（443、8443 或 10000），<visitor-port> 替換為 REPONPC_VISITOR_GATEWAY_PORT（預設 8001）。"
              : "Replace <https-port> with the visitor origin's port (443, 8443, or 10000) and <visitor-port> with REPONPC_VISITOR_GATEWAY_PORT (default 8001)."}
        </p>
        <pre>
          <code>
            {`tailscale funnel --bg --https=${funnelPortText} http://127.0.0.1:<visitor-port>`}
          </code>
        </pre>
        <p>
          {zh
            ? "停用 Funnel 的官方指令："
            : "Official command to turn Funnel off:"}
        </p>
        <pre>
          <code>{`tailscale funnel --https=${funnelPortText} off`}</code>
        </pre>
        <p>
          {zh
            ? "停止本機 Gateway 不代表 Funnel 已停用。Funnel 可能有 beta 狀態、使用限制與方案資格條件；啟用前請確認 Tailscale 官方最新說明與你的方案。"
            : "Stopping the local gateway does not turn Funnel off. Funnel may have beta status, usage limits, or plan eligibility requirements; check Tailscale's current official guidance and your plan before enabling it."}
        </p>
      </details>
    </section>
  );
}

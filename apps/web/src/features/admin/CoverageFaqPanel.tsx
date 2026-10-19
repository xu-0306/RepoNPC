import { useEffect, useRef, useState } from "react";
import type { ClaimKind } from "./ClaimEditor";

const noMatchLabels = {
  MODEL_INSUFFICIENT_EVIDENCE: {
    "zh-TW": "模型判斷證據不足",
    en: "Model found too little evidence",
  },
  ENVELOPE_SCHEMA_INVALID: {
    "zh-TW": "回覆格式不符",
    en: "Reply format invalid",
  },
  SOURCE_ID_UNKNOWN: {
    "zh-TW": "引用了不存在的來源",
    en: "Cited an unknown source",
  },
  MODEL_AUTHORED_MARKUP: {
    "zh-TW": "回覆含不允許的連結或標記",
    en: "Reply contained links or markup",
  },
  INFERENCE_CYCLE: {
    "zh-TW": "推論引用了推論",
    en: "Inference cited an inference",
  },
  ALL_SEGMENTS_DROPPED: {
    "zh-TW": "每段都未通過檢查",
    en: "Every part failed checks",
  },
  SELECTED_MAP_INVALID: {
    "zh-TW": "系統檢查錯誤",
    en: "Internal check error",
  },
  VALIDATION_UNEXPECTED: {
    "zh-TW": "系統檢查錯誤",
    en: "Internal check error",
  },
  NO_EVIDENCE_SELECTED: {
    "zh-TW": "沒有找到相關資料",
    en: "No relevant content found",
  },
} as const;

type Request = <T>(path: string, options?: RequestInit) => Promise<T>;
interface FaqEntry {
  entry_id: string;
  bundle_id: string;
  question: string;
  variants: string[];
  topic: string | null;
  claim_kind: ClaimKind;
  answer_markdown: string | null;
  citations: { title: string; url: string }[];
  dropped_segments: { segment_index: number; reason_codes: string[] }[];
  no_match_reason: keyof typeof noMatchLabels | null;
  coverage_status:
    | "unchecked"
    | "answered"
    | "partially_answered"
    | "no_relevant_content";
  review_state: "pending" | "approved" | "rejected";
  needs_reconfirmation: boolean;
  error_code: string | null;
  revision: number;
}
interface FaqView {
  bundle_id: string | null;
  locale: string;
  entries: FaqEntry[];
}
export function CoverageFaqPanel({
  locale,
  request,
  repositories,
  bundleId,
  draftChanged,
  onAddClaim,
}: {
  locale: "zh-TW" | "en";
  request: Request;
  repositories: string[];
  bundleId: string | null;
  draftChanged: boolean;
  onAddClaim: (repository: string, kind: ClaimKind) => void;
}) {
  const zh = locale === "zh-TW";
  const mounted = useRef(true);
  const currentLocale = useRef(locale);
  const generation = useRef(0);
  if (currentLocale.current !== locale) {
    currentLocale.current = locale;
    generation.current += 1;
  }
  const requestGeneration = generation.current;
  const active = () =>
    mounted.current && generation.current === requestGeneration;
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const [view, setView] = useState<FaqView | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [notice, setNotice] = useState("");
  const [repository, setRepository] = useState(repositories[0] ?? "");
  const [variantsEntryId, setVariantsEntryId] = useState<string | null>(null);
  const [variantsText, setVariantsText] = useState("");
  useEffect(() => {
    busyRef.current = false;
    setBusy(false);
    setNotice("");
    setVariantsEntryId(null);
    setVariantsText("");
    setView(null);
  }, [locale]);
  const refresh = () =>
    request<FaqView>(`/api/admin/portfolio/faq?locale=${locale}`).then(
      (value) => {
        if (active()) setView(value);
      },
    );
  useEffect(() => {
    let closed = false;
    void request<FaqView>(`/api/admin/portfolio/faq?locale=${locale}`)
      .then((value) => {
        if (!closed) setView(value);
      })
      .catch(() => {
        if (!closed) setView(null);
      });
    return () => {
      closed = true;
    };
  }, [request, locale, bundleId]);
  const statusNames = {
    unchecked: zh ? "尚未檢查" : "Not checked",
    answered: zh ? "已回答" : "Answered",
    partially_answered: zh ? "部分回答" : "Partially answered",
    no_relevant_content: zh ? "沒有相關內容" : "No relevant content",
  };
  function errorText(code: string) {
    if (code === "FAQ_VARIANTS_INVALID")
      return zh
        ? "替代問法最多八個，每個不超過二百字，且必須彼此不同並與主問題不同。"
        : "Use at most eight alternatives of 200 characters each; they must be unique and differ from the main question.";
    if (code.includes("CONFLICT") || code.includes("STALE"))
      return zh
        ? "內容版本已變更，請重新檢查後操作。"
        : "The content version changed. Refresh and review again.";
    return zh
      ? "操作未完成。請檢查模型與本機準備狀態後重試。"
      : "Could not complete. Check models and local preparation, then retry.";
  }
  async function run(operation: () => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setNotice("");
    try {
      if (active()) await operation();
    } catch (error) {
      if (active())
        setNotice(
          errorText(error instanceof Error ? error.message : "REQUEST_FAILED"),
        );
    } finally {
      if (active()) {
        await refresh().catch(() => undefined);
        if (active()) {
          busyRef.current = false;
          setBusy(false);
        }
      }
    }
  }
  async function generate(entry: FaqEntry) {
    return request<FaqEntry>(
      `/api/admin/portfolio/faq/${entry.entry_id}/regenerate`,
      {
        method: "POST",
        body: JSON.stringify({ revision: entry.revision }),
      },
    );
  }
  async function check() {
    const queue = await request<FaqView>("/api/admin/portfolio/faq/check", {
      method: "POST",
      body: JSON.stringify({ locale }),
    });
    if (!active()) return;
    setView(queue);
    for (const entry of queue.entries.filter((entry) => entry.topic !== null)) {
      if (!active()) return;
      setNotice(
        `${zh ? "使用模型檢查" : "Checking with models"}: ${entry.question}`,
      );
      await generate(entry);
      if (!active()) return;
      await refresh();
    }
    if (!active()) return;
    setNotice(
      zh
        ? "涵蓋檢查已完成；建議 FAQ 可逐題生成與審核。"
        : "Coverage checked. Generate and review suggested FAQ entries individually.",
    );
  }
  return (
    <section className="admin-surface" aria-labelledby="faq-heading">
      <h2 id="faq-heading">
        {zh ? "涵蓋檢查與 FAQ 審核" : "Coverage and FAQ review"}
      </h2>
      <p>
        {zh
          ? "檢查目前已準備的本機版本，會使用已選模型。缺口不會阻擋發布；FAQ 只有核准後才提供給訪客。"
          : "Check the prepared local version using your selected models. Gaps never block publication. Visitors receive only approved FAQ answers."}
      </p>
      <p>
        {zh
          ? "改寫會開啟貢獻編輯器。儲存陳述並更新 NPC 後，請重新生成及審核 FAQ；新回答不保證引用這段陳述。"
          : "Rewrite opens the contribution editor. Save the statement and update the NPC, then regenerate and review the FAQ; the new answer may not cite this statement."}
      </p>
      {draftChanged && (
        <p>
          {zh
            ? "草稿已變更。檢查結果仍對應目前版本；更新 NPC 後再檢查新內容。"
            : "The draft changed. Results refer to the current version; update the NPC to check the new content."}
        </p>
      )}
      <button
        type="button"
        disabled={busy || !bundleId}
        onClick={() => void run(check)}
      >
        {zh
          ? "使用模型檢查六個標準問題"
          : "Check six standard questions with models"}
      </button>
      <button type="button" disabled={busy} onClick={() => void run(refresh)}>
        {zh ? "重新整理審核佇列" : "Refresh review queue"}
      </button>
      <button
        type="button"
        disabled={busy || !bundleId}
        onClick={() =>
          void run(async () => {
            const payload = await request(
              `/api/admin/portfolio/faq/export?locale=${locale}`,
            );
            const url = URL.createObjectURL(
              new Blob([JSON.stringify(payload, null, 2)], {
                type: "application/json",
              }),
            );
            const link = document.createElement("a");
            link.href = url;
            link.download = `faq-${locale}.json`;
            link.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
          })
        }
      >
        {zh ? "下載已核准 FAQ JSON" : "Download approved FAQ JSON"}
      </button>
      <label htmlFor="faq-repository">
        {zh ? "補充陳述的專案" : "Project for the new statement"}
      </label>
      <select
        id="faq-repository"
        value={
          repositories.includes(repository)
            ? repository
            : (repositories[0] ?? "")
        }
        onChange={(event) => setRepository(event.target.value)}
      >
        {repositories.map((slug) => (
          <option key={slug} value={slug}>
            {slug}
          </option>
        ))}
      </select>
      <p role="status">{notice}</p>
      {view?.entries.map((entry) => (
        <article key={entry.entry_id} aria-label={entry.question}>
          <h3>{entry.question}</h3>
          {entry.variants.length > 0 && (
            <p>
              {zh ? "核准的替代問法：" : "Approved alternate questions: "}
              {entry.variants.join(zh ? "、" : " · ")}
            </p>
          )}
          <p>
            {statusNames[entry.coverage_status]}
            {entry.no_match_reason && (
              <span> · {noMatchLabels[entry.no_match_reason][locale]}</span>
            )}
          </p>
          {entry.needs_reconfirmation && (
            <p>
              {zh
                ? "版本已變更，需要重新生成與確認；目前不提供給訪客。"
                : "The version changed. Regenerate and reconfirm; visitors cannot receive this answer."}
            </p>
          )}
          <p>
            {entry.review_state === "approved"
              ? zh
                ? "已核准"
                : "Approved"
              : entry.review_state === "rejected"
                ? zh
                  ? "已拒絕"
                  : "Rejected"
                : zh
                  ? "待審核"
                  : "Pending review"}
          </p>
          {entry.answer_markdown && (
            <p style={{ whiteSpace: "pre-wrap" }}>{entry.answer_markdown}</p>
          )}
          <ul>
            {entry.citations.map((citation, index) => (
              <li key={index}>
                <a href={citation.url} target="_blank" rel="noreferrer">
                  {citation.title}
                </a>
              </li>
            ))}
          </ul>
          {entry.dropped_segments.length > 0 && (
            <details>
              <summary>
                {zh
                  ? "僅作者可見的略過段落原因"
                  : "Owner-only dropped segment reasons"}
              </summary>
              <ul>
                {entry.dropped_segments.map((segment) => (
                  <li key={segment.segment_index}>
                    {segment.segment_index + 1}:{" "}
                    {segment.reason_codes.join(", ")}
                  </li>
                ))}
              </ul>
            </details>
          )}
          {entry.error_code && (
            <p role="alert">{errorText(entry.error_code)}</p>
          )}
          <button
            type="button"
            disabled={
              busy ||
              entry.needs_reconfirmation ||
              !entry.answer_markdown ||
              !!entry.error_code
            }
            onClick={() =>
              void run(async () => {
                await request(
                  `/api/admin/portfolio/faq/${entry.entry_id}/review`,
                  {
                    method: "POST",
                    body: JSON.stringify({
                      revision: entry.revision,
                      action: "approve",
                    }),
                  },
                );
              })
            }
          >
            {zh ? "核准" : "Approve"}
          </button>
          <button
            type="button"
            disabled={busy || entry.needs_reconfirmation}
            onClick={() =>
              void run(async () => {
                await request(
                  `/api/admin/portfolio/faq/${entry.entry_id}/review`,
                  {
                    method: "POST",
                    body: JSON.stringify({
                      revision: entry.revision,
                      action: "reject",
                    }),
                  },
                );
              })
            }
          >
            {zh ? "拒絕" : "Reject"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                await generate(entry);
              })
            }
          >
            {zh ? "使用模型重新生成" : "Regenerate with models"}
          </button>
          <button
            type="button"
            disabled={busy || entry.needs_reconfirmation}
            onClick={() => {
              setVariantsEntryId(entry.entry_id);
              setVariantsText(entry.variants.join("\n"));
            }}
          >
            {zh ? "編輯替代問法" : "Edit alternate questions"}
          </button>
          {variantsEntryId === entry.entry_id && (
            <div>
              <label htmlFor={`faq-variants-${entry.entry_id}`}>
                {zh
                  ? "每行輸入一個替代問法（最多八個，每個 200 字）"
                  : "Enter one alternate question per line (up to eight, 200 characters each)"}
              </label>
              <textarea
                id={`faq-variants-${entry.entry_id}`}
                maxLength={1607}
                onChange={(event) => setVariantsText(event.target.value)}
                rows={4}
                value={variantsText}
              />
              <p>
                {zh
                  ? "儲存後這題會回到待審核；答案不會被修改。"
                  : "Saving returns this item to pending review; its answer is not changed."}
              </p>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  void run(async () => {
                    await request<FaqEntry>(
                      `/api/admin/portfolio/faq/${entry.entry_id}/variants`,
                      {
                        method: "PUT",
                        body: JSON.stringify({
                          revision: entry.revision,
                          bundle_id: entry.bundle_id,
                          variants: variantsText
                            .split(/\r?\n/)
                            .map((variant) => variant.trim())
                            .filter(Boolean),
                        }),
                      },
                    );
                    setVariantsEntryId(null);
                    setVariantsText("");
                  })
                }
              >
                {zh ? "儲存替代問法" : "Save alternate questions"}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  setVariantsEntryId(null);
                  setVariantsText("");
                }}
              >
                {zh ? "取消" : "Cancel"}
              </button>
            </div>
          )}
          <button
            type="button"
            disabled={busy || !repositories.length}
            onClick={() =>
              onAddClaim(repository || repositories[0], entry.claim_kind)
            }
          >
            {zh ? "改寫為作者陳述" : "Rewrite as owner statement"}
          </button>
          {entry.coverage_status !== "answered" && entry.topic && (
            <button
              type="button"
              disabled={busy || !repositories.length}
              onClick={() =>
                onAddClaim(repository || repositories[0], entry.claim_kind)
              }
            >
              {zh ? "補一段自述" : "Add owner statement to fill gap"}
            </button>
          )}
        </article>
      ))}
    </section>
  );
}

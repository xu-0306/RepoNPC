import { useEffect, useRef, useState } from "react";
import type { AnalysisSelectionView } from "./AnalysisSelectionPanel";
import { ClaimEditor, type ClaimKind } from "./ClaimEditor";
import type { LocalDraftBody } from "./LocalPublishingWorkspace";

type Request = <T>(path: string, options?: RequestInit) => Promise<T>;
interface FaqEntry {
  entry_id: string;
  bundle_id: string;
  question: string;
  topic: string | null;
  claim_kind: ClaimKind;
  answer_markdown: string | null;
  citations: { title: string; url: string }[];
  dropped_segments: { segment_index: number; reason_codes: string[] }[];
  coverage_status:
    | "unchecked"
    | "answered"
    | "partially_answered"
    | "no_relevant_content";
  review_state: "pending" | "approved" | "rejected";
  needs_reconfirmation: boolean;
  error_code: string | null;
  revision: number;
  rewrite: {
    draft_revision: string;
    claim_id: string;
    source_bundle_id: string;
  } | null;
}
interface FaqView {
  bundle_id: string | null;
  locale: string;
  entries: FaqEntry[];
}
interface PublicationStatus {
  state: string;
  draft_changed: boolean;
  active_bundle_id: string | null;
  error_code: string | null;
}

export function CoverageFaqPanel({
  locale,
  request,
  revision,
  repositories,
  selection,
  bundleId,
  draftChanged,
  onStored,
  onAddClaim,
}: {
  locale: "zh-TW" | "en";
  request: Request;
  revision: string | null;
  repositories: string[];
  selection: AnalysisSelectionView | null;
  bundleId: string | null;
  draftChanged: boolean;
  onStored: (draft: LocalDraftBody) => void;
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
  const [rewriteId, setRewriteId] = useState<string | null>(null);
  const [kind, setKind] = useState<ClaimKind>("context");
  const [statement, setStatement] = useState({ "zh-TW": "", en: "" });
  useEffect(() => {
    busyRef.current = false;
    setBusy(false);
    setNotice("");
    setRewriteId(null);
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
    if (code === "FAQ_CONTEXT_INSUFFICIENT")
      return zh
        ? "模型可用內容空間不足。請縮短自述或調整回答模型，再繼續生成。"
        : "The model has insufficient context space. Shorten the statement or adjust the answer model, then continue generation.";
    if (code.includes("NOT_INDEXED"))
      return zh
        ? "新增陳述尚未完成索引。請更新 NPC 後再繼續。"
        : "The new statement has not been indexed. Update the NPC, then continue.";
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
    for (const entry of queue.entries.filter(
      (entry) => entry.topic !== null && !entry.rewrite,
    )) {
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
  async function resume(
    entry: FaqEntry,
    savedRevision = entry.rewrite?.draft_revision,
  ) {
    if (!savedRevision || !selection?.eligible) throw new Error("NOT_INDEXED");
    const current = await request<PublicationStatus>(
      "/api/admin/portfolio/status",
    );
    if (!active()) return;
    if (
      current.draft_changed ||
      current.active_bundle_id === entry.rewrite?.source_bundle_id
    ) {
      await request("/api/admin/portfolio/prepare", {
        method: "POST",
        body: JSON.stringify({
          expected_revision: savedRevision,
          selection_generation: selection.selection.generation,
          confirmed: true,
        }),
      });
      const deadline = Date.now() + 180000;
      while (Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 500));
        if (!active()) return;
        const status = await request<PublicationStatus>(
          "/api/admin/portfolio/status",
        );
        if (status.state === "failed")
          throw new Error(status.error_code ?? "PREPARE_FAILED");
        if (status.state === "ready" && !status.draft_changed) break;
        if (Date.now() >= deadline) throw new Error("NOT_INDEXED");
      }
    }
    if (!active()) return;
    await generate(entry);
    if (!active()) return;
    setNotice(
      zh
        ? "已使用新陳述重新生成。請再次審核回答。"
        : "Regenerated using the new statement. Review the answer again.",
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
          <p>{statusNames[entry.coverage_status]}</p>
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
              !!entry.rewrite ||
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
                      bundle_id: entry.bundle_id,
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
                      bundle_id: entry.bundle_id,
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
            disabled={busy || !!entry.rewrite}
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
            disabled={busy || !repositories.length}
            onClick={() => {
              setRewriteId(entry.entry_id);
              setKind(entry.claim_kind);
              setStatement({ "zh-TW": "", en: "" });
            }}
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
          {entry.rewrite && (
            <>
              <p>
                {zh
                  ? "作者陳述已存為本機草稿。下一步更新索引並重新生成；會使用模型。離開後可在此繼續。"
                  : "The statement is saved in the local draft. Update the index and regenerate using models. You can return here to continue."}
              </p>
              <button
                type="button"
                disabled={busy || !selection?.eligible}
                onClick={() => void run(() => resume(entry))}
              >
                {zh
                  ? "使用模型更新 NPC 並繼續生成"
                  : "Update NPC and continue generation with models"}
              </button>
            </>
          )}
          {rewriteId === entry.entry_id && (
            <div>
              <ClaimEditor
                locale={locale}
                id={`faq-statement-${entry.entry_id}`}
                kind={kind}
                statement={statement}
                disabled={busy}
                onChange={(nextKind, next) => {
                  setKind(nextKind);
                  setStatement(next);
                }}
              />
              <p>
                {zh
                  ? "保存的是作者陳述，不能直接修改 FAQ 答案。會先更新 NPC，再用新索引與模型重新生成。"
                  : "This saves an owner statement, not an edited FAQ answer. The NPC is updated before models regenerate using the new index."}
              </p>
              <button
                type="button"
                disabled={
                  busy ||
                  !revision ||
                  !selection?.eligible ||
                  !statement["zh-TW"].trim() ||
                  !statement.en.trim()
                }
                onClick={() =>
                  void run(async () => {
                    const result = await request<{
                      draft: LocalDraftBody;
                      entry: FaqEntry;
                    }>(`/api/admin/portfolio/faq/${entry.entry_id}/rewrite`, {
                      method: "POST",
                      body: JSON.stringify({
                        revision: entry.revision,
                        expected_draft_revision: revision,
                        repository: repository || repositories[0],
                        kind,
                        statement,
                      }),
                    });
                    if (!active()) return;
                    onStored(result.draft);
                    setRewriteId(null);
                    await refresh();
                    await resume(
                      result.entry,
                      result.draft.revision ?? undefined,
                    );
                  })
                }
              >
                {zh
                  ? "儲存陳述、更新 NPC 並使用模型生成"
                  : "Save statement, update NPC and generate with models"}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setRewriteId(null)}
              >
                {zh ? "取消" : "Cancel"}
              </button>
            </div>
          )}
        </article>
      ))}
    </section>
  );
}

import { useState } from "react";
import type { DragEvent, FormEvent } from "react";
import { Button, FileTrigger } from "react-aria-components";

import {
  CHARACTER_FRAME_COUNT,
  CHARACTER_FRAME_SIZE,
  CHARACTER_STATES,
  getCharacterStateRow,
  type CharacterState,
} from "../character/CharacterRenderer";
import type { AdminLocale } from "./AdminWorkspace";
import { Base64PngCanvas } from "./Base64PngCanvas";
import { suggestedCharacterFilename } from "./characterAssetFilename";
import {
  automaticFrameAlignment,
  canShiftFrame,
  composeAlignedPng,
  emptyFrameOffsets,
  inspectFrameAlignment,
  parseFramePixelOffset,
  type FrameAlignmentAnalysis,
  type FrameOffset,
} from "./characterFrameAlignment";

export type CharacterConversionStrategy = "pixel_exact" | "pixelize";

export interface CharacterConversionWarning {
  code: string;
  items: string[];
}

export interface CharacterAssetBody {
  sha256: string;
  width: number;
  height: number;
  png_base64: string;
  png_url?: string;
}

interface CharacterConversionBody {
  source_kind: "grid" | "manifest" | "bundle";
  strategy: CharacterConversionStrategy;
  source_frame_sizes: number[][];
  candidate_id: string | null;
  source_path: string | null;
  warnings: CharacterConversionWarning[];
}

export interface CharacterConversionResult {
  status: "converted";
  asset: CharacterAssetBody;
  edge_cleanup: {
    asset: CharacterAssetBody;
    affected_frames: Array<{ state: CharacterState; frame: number }>;
    removed_source_pixels: number;
  } | null;
  conversion: CharacterConversionBody;
}

export interface CharacterCandidate {
  candidate_id: string;
  source_path: string;
  asset: CharacterAssetBody;
  conversion: {
    source_frame_sizes: number[][];
    warnings: CharacterConversionWarning[];
  };
}

export interface CharacterSelectionResult {
  status: "selection_required";
  discovery: {
    source_kind: "bundle";
    strategy: CharacterConversionStrategy;
    ignored_count: number;
    candidates: CharacterCandidate[];
  };
}

export type CharacterPreparationResult =
  | CharacterConversionResult
  | CharacterSelectionResult;

export type CharacterMaterialSource =
  | { kind: "file"; file: File; displayName: string }
  | {
      kind: "folder";
      displayName: string;
      entries: Array<{ file: File; path: string }>;
    };

export interface CharacterAssetConverterProps {
  locale: AdminLocale;
  disabled?: boolean;
  onConvert: (
    source: CharacterMaterialSource,
    strategy: CharacterConversionStrategy,
    candidateId?: string,
  ) => Promise<CharacterPreparationResult>;
  onValidate: (png: Blob) => Promise<CharacterAssetBody>;
  onApply?: (asset: CharacterAssetBody) => Promise<void>;
}

const COPY = {
  "zh-TW": {
    heading: "製作角色動畫",
    eyebrow: "WORKSHOP / CHARACTER",
    subtitle: "上傳素材，預覽七種動作後套用到作品集。",
    howTo: "製作步驟",
    empty: "上傳素材後即可預覽角色。",
    apply: "套用到作品集",
    introduction:
      "上傳你手上的圖片、ZIP 或整個素材資料夾，RepoNPC 會自動找出可用的角色圖。找到多張時，請看預覽選擇。RepoNPC 不會修改原始檔。",
    steps: ["選擇素材", "選擇角色", "預覽並儲存"],
    drop: "將 PNG 或 ZIP 拖到這裡",
    chooseFile: "選擇 PNG 或 ZIP",
    chooseFolder: "選擇整個資料夾",
    selected: "已選擇",
    folderFiles: "個檔案",
    advancedSettings: "進階轉換設定",
    strategy: "圖片處理方式",
    pixelize: "像素化（適合高解析度或抗鋸齒素材）",
    pixelExact: "像素精確（只接受整數倍率）",
    convert: "尋找角色動畫",
    converting: "正在尋找角色圖…",
    candidates: "選擇角色圖",
    candidatesFound: "系統找到可轉換的角色圖。請看縮圖選擇完整角色。",
    ignored: "其他檔案已安全略過",
    useCandidate: "使用這張角色圖",
    animationPreview: "動畫預覽",
    animationState: "預覽動作",
    reducedMotionNote: "若系統已啟用減少動態效果，預覽會停在第一格。",
    technicalDetails: "查看完整角色圖與技術資訊",
    sheetPreview: "完整角色圖",
    report: "技術資訊",
    sourceKind: "來源格式",
    sourcePath: "來源檔案",
    dimensions: "輸出尺寸",
    warnings: "需檢查項目",
    noWarnings: "未偵測到需人工檢查的項目。",
    download: "下載角色圖",
    filename: "角色檔案名稱",
    filenameHelp: "僅接受小寫英數、底線或連字號，並以 .png 結尾。",
    converted: "角色動畫已準備好。請切換動作預覽，確認後再下載或儲存。",
    cleanupSuggested:
      "發現可能來自上一列的邊界殘影。請比較清理前後，再選擇要使用的版本。",
    cleanupAccepted: "已選擇清理版。請檢查各個動作，確認後可下載或儲存。",
    cleanupKept: "已保留原版。請檢查各個動作，確認後可下載或儲存。",
    cleanupHeading: "清理邊界殘影",
    cleanupHelp:
      "偵測到上一列像素延伸進此影格，且與角色之間有透明間隔。原始檔不會修改；不確定的圖案不會自動清除。切換版本會還原位置校正。",
    cleanupFrames: "格可能受到影響",
    cleanupBefore: "原版",
    cleanupAfter: "清理版",
    cleanupUse: "使用清理版",
    cleanupKeep: "保留原版",
    applied:
      "角色已選用，將套用到目前作品集草稿。完成內容後可在「預覽與分享」查看。",
    failed: "角色素材處理失敗，未儲存素材。請換檔案重試。",
    previewFailed: "圖片預覽無法顯示，請重新轉換或換一個檔案。",
    alignmentHeading: "角色位置跳動？",
    alignmentHelp:
      "轉換時會自動校正跨動作一致的位移。可逐格輸入 X、Y 像素微調；調整後按套用並驗證。原始檔不會修改。",
    alignmentSuggest: "預覽所有對齊建議",
    alignmentInspecting: "正在分析位置…",
    alignmentAutomatic:
      "已自動校正一致的影格位移並通過驗證；請檢查各個動作。不合適時可還原或逐格調整。",
    alignmentManualReview:
      "沒有足夠一致的位移可自動校正。可預覽建議或逐格輸入偏移。",
    alignmentReady: "校正圖已通過驗證；可逐格檢查或還原。",
    alignmentSuggested: "已顯示對齊預覽。請切換動作檢查後再套用。",
    alignmentNoSuggestion: "沒有可安全自動修正的位移；仍可逐格微調。",
    alignmentEdit: "逐格微調",
    alignmentFrame: "影格",
    alignmentPlay: "繼續播放",
    alignmentLeft: "向左移",
    alignmentRight: "向右移",
    alignmentUp: "向上移",
    alignmentDown: "向下移",
    alignmentPosition: "目前位置",
    alignmentPixels: "像素偏移",
    alignmentInvalid: "請輸入不會裁切角色的整數像素。",
    alignmentApply: "套用校正並驗證",
    alignmentApplying: "正在驗證校正圖…",
    alignmentRestore: "還原位置校正",
    alignmentRestored: "已還原位置校正；素材版本的選擇不變。",
    alignmentUnapplied: "校正尚未套用；請先按「套用校正並驗證」再下載或儲存。",
    alignmentApplied: "校正圖已通過驗證。現在可下載或儲存。",
    alignmentFailed: "位置校正未成功；原始轉換圖仍保留。",
    alignmentNote: "自動建議只調整左右位置，不會刪除游離像素或猜測動作意圖。",
    stateLabels: {
      idle: "待機",
      walk: "移動",
      listen: "聆聽",
      think: "思考",
      talk: "說話",
      success: "完成",
      offline: "離線",
    },
  },
  en: {
    heading: "Create character animation",
    eyebrow: "WORKSHOP / CHARACTER",
    subtitle:
      "Upload art, preview seven actions and apply it to your portfolio.",
    howTo: "Creation steps",
    empty: "Upload art to preview your character.",
    apply: "Apply to portfolio",
    introduction:
      "Upload an image, ZIP, or whole asset folder. RepoNPC finds usable character art automatically and displays visual choices when several match. RepoNPC never changes your original files.",
    steps: ["Choose assets", "Choose a character", "Preview and save"],
    drop: "Drop a PNG or ZIP here",
    chooseFile: "Choose PNG or ZIP",
    chooseFolder: "Choose a folder",
    selected: "Selected",
    folderFiles: "files",
    advancedSettings: "Advanced conversion settings",
    strategy: "Image processing",
    pixelize: "Pixelize (for high-resolution or antialiased art)",
    pixelExact: "Pixel exact (integer scale only)",
    convert: "Find character animation",
    converting: "Finding character art…",
    candidates: "Choose the character grid",
    candidatesFound:
      "RepoNPC found convertible character grids. Choose the complete character by its preview.",
    ignored: "Other files safely ignored",
    useCandidate: "Use this character grid",
    animationPreview: "Animation preview",
    animationState: "Preview action",
    reducedMotionNote:
      "The preview stays on its first frame when your system uses reduced motion.",
    technicalDetails: "View full character sheet and technical details",
    sheetPreview: "Full character sheet",
    report: "Technical details",
    sourceKind: "Source format",
    sourcePath: "Source file",
    dimensions: "Output dimensions",
    warnings: "Review required",
    noWarnings: "The automatic review found no warnings.",
    download: "Download character image",
    filename: "Character filename",
    filenameHelp:
      "Use lowercase letters, digits, underscores, or hyphens and end with .png.",
    converted:
      "Your character animation is ready. Preview each action and confirm your choice before downloading or saving.",
    cleanupSuggested:
      "Possible edge spill from the row above was found. Compare both versions and choose one.",
    cleanupAccepted:
      "Cleaned version selected. Check each action before downloading or saving.",
    cleanupKept:
      "Original conversion selected. Check each action before downloading or saving.",
    cleanupHeading: "Clean up edge spill",
    cleanupHelp:
      "Pixels from the row above extend into this frame with a transparent gap before the character. Your source file stays untouched; uncertain artwork is not removed automatically. Switching versions resets alignment edits.",
    cleanupFrames: "frames may be affected",
    cleanupBefore: "Original conversion",
    cleanupAfter: "Cleaned version",
    cleanupUse: "Use cleaned version",
    cleanupKeep: "Keep original conversion",
    applied:
      "Character selected for your portfolio draft. Finish your content, then open Preview & share.",
    failed:
      "RepoNPC could not process the art and did not save it. Try another file.",
    previewFailed:
      "The image preview could not be shown. Try converting again or choose another file.",
    alignmentHeading: "Does the character jump around?",
    alignmentHelp:
      "Conversion automatically corrects displacement shared across actions. Enter X/Y pixel offsets for each frame if needed, then apply and check. Your source file stays untouched.",
    alignmentSuggest: "Preview all alignment suggestions",
    alignmentInspecting: "Checking frame positions…",
    alignmentAutomatic:
      "Consistent frame displacement was corrected and validated. Check each action; you can restore or adjust individual frames.",
    alignmentManualReview:
      "There is not enough consistent displacement for automatic correction. Preview suggestions or enter offsets per frame.",
    alignmentReady:
      "The adjusted image passed validation. Review each frame or restore it.",
    alignmentSuggested:
      "Alignment preview is ready. Check each action before applying it.",
    alignmentNoSuggestion:
      "No safe automatic shift was found; you can still adjust frames manually.",
    alignmentEdit: "Adjust individual frames",
    alignmentFrame: "Frame",
    alignmentPlay: "Resume animation",
    alignmentLeft: "Move left",
    alignmentRight: "Move right",
    alignmentUp: "Move up",
    alignmentDown: "Move down",
    alignmentPosition: "Current offset",
    alignmentPixels: "Pixel offset",
    alignmentInvalid:
      "Enter whole-pixel offsets that do not crop the character.",
    alignmentApply: "Apply and check alignment",
    alignmentApplying: "Validating aligned image…",
    alignmentRestore: "Restore alignment",
    alignmentRestored:
      "Alignment restored; your material-version choice is unchanged.",
    alignmentUnapplied:
      "The alignment has not been applied. Apply and validate before downloading or saving.",
    alignmentApplied:
      "The aligned image passed validation. You can now download or save it.",
    alignmentFailed:
      "Alignment failed; the original converted image is still available.",
    alignmentNote:
      "Suggestions adjust horizontal position only. They do not remove stray pixels or guess intended motion.",
    stateLabels: {
      idle: "Idle",
      walk: "Move",
      listen: "Listen",
      think: "Think",
      talk: "Talk",
      success: "Success",
      offline: "Offline",
    },
  },
} as const;

type StatusKey =
  | "candidatesFound"
  | "converted"
  | "applied"
  | "cleanupSuggested"
  | "cleanupAccepted"
  | "cleanupKept"
  | "alignmentSuggested"
  | "alignmentAutomatic"
  | "alignmentManualReview"
  | "alignmentNoSuggestion"
  | "alignmentApplied"
  | "alignmentRestored";

type ErrorKind = "failed" | "alignmentFailed";

function folderSource(files: File[]): CharacterMaterialSource | null {
  if (!files.length) return null;
  const entries = files.map((file) => ({
    file,
    path: file.webkitRelativePath || file.name,
  }));
  const firstPath = entries[0]?.path ?? "character-folder";
  const root = firstPath.includes("/")
    ? firstPath.split("/", 1)[0]
    : "character-folder";
  return { kind: "folder", displayName: root || "character-folder", entries };
}

export function CharacterAssetConverter({
  locale,
  disabled = false,
  onConvert,
  onValidate,
  onApply,
}: CharacterAssetConverterProps) {
  const copy = COPY[locale];
  const [source, setSource] = useState<CharacterMaterialSource | null>(null);
  const [strategy, setStrategy] =
    useState<CharacterConversionStrategy>("pixelize");
  const [selection, setSelection] = useState<CharacterSelectionResult | null>(
    null,
  );
  const [result, setResult] = useState<CharacterConversionResult | null>(null);
  const [cleanupChoice, setCleanupChoice] = useState<
    "review" | "original" | "cleaned"
  >("original");
  const [filename, setFilename] = useState("character.png");
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState<StatusKey | null>(null);
  const [error, setError] = useState<{
    kind: ErrorKind;
    detail: string;
  } | null>(null);
  const [previewState, setPreviewState] = useState<CharacterState>("idle");
  const [alignmentAnalysis, setAlignmentAnalysis] =
    useState<FrameAlignmentAnalysis | null>(null);
  const [alignmentOffsets, setAlignmentOffsets] =
    useState<FrameOffset[]>(emptyFrameOffsets);
  const [alignedAsset, setAlignedAsset] = useState<CharacterAssetBody | null>(
    null,
  );
  const [selectedFrame, setSelectedFrame] = useState<number | null>(null);
  const [offsetDraft, setOffsetDraft] = useState({ x: "0", y: "0" });
  const [alignmentOperation, setAlignmentOperation] = useState<
    "inspect" | "apply" | null
  >(null);

  function resetAlignment() {
    setAlignmentAnalysis(null);
    setAlignmentOffsets(emptyFrameOffsets());
    setAlignedAsset(null);
    setSelectedFrame(null);
    setOffsetDraft({ x: "0", y: "0" });
  }

  function resetOutput(nextSource: CharacterMaterialSource | null) {
    setSource(nextSource);
    setSelection(null);
    setResult(null);
    setCleanupChoice("original");
    resetAlignment();
    setStatus(null);
    setError(null);
    if (nextSource) {
      setFilename(suggestedCharacterFilename(nextSource.displayName));
    }
  }

  function chooseFile(files: FileList | null) {
    const selected = files?.[0] ?? null;
    resetOutput(
      selected
        ? { kind: "file", file: selected, displayName: selected.name }
        : null,
    );
  }

  function chooseFolder(files: FileList | null) {
    resetOutput(folderSource(Array.from(files ?? [])));
  }

  function dropMaterial(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    if (disabled || pending) return;
    const files = Array.from(event.dataTransfer.files);
    if (!files.length) return;
    if (
      files.length > 1 ||
      files.some((file) => file.webkitRelativePath.includes("/"))
    ) {
      resetOutput(folderSource(files));
      return;
    }
    const file = files[0];
    if (file) resetOutput({ kind: "file", file, displayName: file.name });
  }

  async function initializeAlignment(
    asset: CharacterAssetBody,
  ): Promise<boolean> {
    setAlignmentOperation("inspect");
    try {
      const analysis = await inspectFrameAlignment(asset.png_base64);
      const automatic = automaticFrameAlignment(analysis);
      setAlignmentAnalysis(analysis);
      setAlignmentOffsets(automatic.offsets);
      if (!automatic.alignedStates) return false;
      const png = await composeAlignedPng(asset.png_base64, automatic.offsets);
      setAlignedAsset(await onValidate(png));
      return true;
    } catch (alignmentError) {
      resetAlignment();
      setError({
        kind: "alignmentFailed",
        detail:
          alignmentError instanceof Error
            ? alignmentError.message
            : "REQUEST_FAILED",
      });
      return false;
    } finally {
      setAlignmentOperation(null);
    }
  }

  async function applyPreparation(preparation: CharacterPreparationResult) {
    resetAlignment();
    if (preparation.status === "selection_required") {
      setSelection(preparation);
      setResult(null);
      setStatus("candidatesFound");
      return;
    }
    setSelection(null);
    setResult(preparation);
    setCleanupChoice(preparation.edge_cleanup ? "review" : "original");
    setPreviewState(
      preparation.edge_cleanup?.affected_frames[0]?.state ?? "idle",
    );
    if (preparation.edge_cleanup) {
      setStatus("cleanupSuggested");
    } else {
      setStatus(
        (await initializeAlignment(preparation.asset))
          ? "alignmentAutomatic"
          : "converted",
      );
    }
  }

  async function chooseCleanup(choice: "original" | "cleaned") {
    if (cleanupChoice === choice) return;
    if (!result) return;
    setPending(true);
    resetAlignment();
    setCleanupChoice(choice);
    setError(null);
    try {
      const asset =
        choice === "cleaned" ? result.edge_cleanup?.asset : result.asset;
      setStatus(
        asset && (await initializeAlignment(asset))
          ? "alignmentAutomatic"
          : choice === "cleaned"
            ? "cleanupAccepted"
            : "cleanupKept",
      );
    } finally {
      setPending(false);
    }
  }

  async function prepare(candidateId?: string) {
    if (!source) return;
    setPending(true);
    setError(null);
    setStatus(null);
    try {
      await applyPreparation(await onConvert(source, strategy, candidateId));
    } catch (conversionError) {
      setResult(null);
      resetAlignment();
      if (!candidateId) setSelection(null);
      setError({
        kind: "failed",
        detail:
          conversionError instanceof Error
            ? conversionError.message
            : "REQUEST_FAILED",
      });
    } finally {
      setPending(false);
    }
  }

  function convert(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void prepare();
  }

  function download() {
    if (!downloadableAsset || !offsetDraftValid) return;
    const binary = window.atob(downloadableAsset.png_base64);
    const bytes = Uint8Array.from(binary, (character) =>
      character.charCodeAt(0),
    );
    const url = URL.createObjectURL(new Blob([bytes], { type: "image/png" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function suggestAlignment() {
    if (!baseAsset || cleanupReviewPending) return;
    setPending(true);
    setAlignmentOperation("inspect");
    setError(null);
    try {
      const analysis = await inspectFrameAlignment(baseAsset.png_base64);
      setAlignmentAnalysis(analysis);
      setAlignmentOffsets(analysis.suggestedOffsets);
      setAlignedAsset(null);
      setSelectedFrame(null);
      setStatus(
        analysis.suggestedOffsets.some((offset) => offset.x !== 0)
          ? "alignmentSuggested"
          : "alignmentNoSuggestion",
      );
    } catch (alignmentError) {
      setError({
        kind: "alignmentFailed",
        detail:
          alignmentError instanceof Error
            ? alignmentError.message
            : "REQUEST_FAILED",
      });
    } finally {
      setPending(false);
      setAlignmentOperation(null);
    }
  }

  function nudgeFrame(dx: number, dy: number) {
    if (!alignmentAnalysis || selectedFrame === null) return;
    const index =
      getCharacterStateRow(previewState) * CHARACTER_FRAME_COUNT +
      selectedFrame;
    const current = alignmentOffsets[index];
    const bounds = alignmentAnalysis.bounds[index];
    if (!current || !bounds) return;
    const next = { x: current.x + dx, y: current.y + dy };
    if (!canShiftFrame(bounds, next)) return;
    setAlignmentOffsets(
      alignmentOffsets.map((offset, frameIndex) =>
        frameIndex === index ? next : offset,
      ),
    );
    setOffsetDraft({ x: String(next.x), y: String(next.y) });
    setAlignedAsset(null);
    setStatus(null);
  }

  function selectFrame(frame: number) {
    const index =
      getCharacterStateRow(previewState) * CHARACTER_FRAME_COUNT + frame;
    const offset = alignmentOffsets[index] ?? { x: 0, y: 0 };
    setSelectedFrame(frame);
    setOffsetDraft({ x: String(offset.x), y: String(offset.y) });
  }

  function updateOffsetDraft(axis: "x" | "y", value: string) {
    const draft = { ...offsetDraft, [axis]: value };
    setOffsetDraft(draft);
    if (selectedFrame === null || !alignmentAnalysis) return;
    const index =
      getCharacterStateRow(previewState) * CHARACTER_FRAME_COUNT +
      selectedFrame;
    const bounds = alignmentAnalysis.bounds[index];
    const next = bounds ? parseFramePixelOffset(draft, bounds) : null;
    if (!next) return;
    const current = alignmentOffsets[index];
    if (current?.x === next.x && current.y === next.y) return;
    setAlignmentOffsets(
      alignmentOffsets.map((offset, frameIndex) =>
        frameIndex === index ? next : offset,
      ),
    );
    setAlignedAsset(null);
    setStatus(null);
  }

  async function applyAlignment() {
    if (!baseAsset || !hasAlignmentEdits) return;
    setPending(true);
    setAlignmentOperation("apply");
    setError(null);
    try {
      const png = await composeAlignedPng(
        baseAsset.png_base64,
        alignmentOffsets,
      );
      setAlignedAsset(await onValidate(png));
      setStatus("alignmentApplied");
    } catch (alignmentError) {
      setError({
        kind: "alignmentFailed",
        detail:
          alignmentError instanceof Error
            ? alignmentError.message
            : "REQUEST_FAILED",
      });
    } finally {
      setPending(false);
      setAlignmentOperation(null);
    }
  }

  function restoreOriginal() {
    setAlignmentOffsets(emptyFrameOffsets());
    setAlignedAsset(null);
    setSelectedFrame(null);
    setStatus("alignmentRestored");
    setError(null);
  }

  const filenameValid = /^[a-z][a-z0-9_-]{0,63}\.png$/.test(filename);
  const cleanupReviewPending = Boolean(
    result?.edge_cleanup && cleanupChoice === "review",
  );
  const baseAsset =
    cleanupChoice === "cleaned" && result?.edge_cleanup
      ? result.edge_cleanup.asset
      : result?.asset;
  const hasAlignmentEdits = alignmentOffsets.some(
    (offset) => offset.x !== 0 || offset.y !== 0,
  );
  const alignmentNeedsApply = hasAlignmentEdits && !alignedAsset;
  const downloadableAsset =
    result && !cleanupReviewPending
      ? hasAlignmentEdits
        ? alignedAsset
        : baseAsset
      : null;
  const previewAsset = alignedAsset?.png_base64 ?? baseAsset?.png_base64 ?? "";
  const previewAssetUrl = alignedAsset ? undefined : baseAsset?.png_url;
  const previewOffsets = alignedAsset ? undefined : alignmentOffsets;
  const comparisonFrame =
    result?.edge_cleanup?.affected_frames.find(
      (affected) => affected.state === previewState,
    )?.frame ?? 0;
  const selectedFrameIndex =
    selectedFrame === null
      ? null
      : getCharacterStateRow(previewState) * CHARACTER_FRAME_COUNT +
        selectedFrame;
  const selectedOffset =
    selectedFrameIndex === null ? null : alignmentOffsets[selectedFrameIndex];
  const selectedBounds =
    selectedFrameIndex === null
      ? null
      : alignmentAnalysis?.bounds[selectedFrameIndex];
  const offsetDraftValid =
    selectedBounds === undefined || selectedBounds === null
      ? true
      : parseFramePixelOffset(offsetDraft, selectedBounds) !== null;
  const automaticPatternAvailable =
    alignmentAnalysis !== null &&
    automaticFrameAlignment(alignmentAnalysis).alignedStates > 0;
  const canNudge = (dx: number, dy: number) =>
    Boolean(
      selectedOffset &&
        selectedBounds &&
        canShiftFrame(selectedBounds, {
          x: selectedOffset.x + dx,
          y: selectedOffset.y + dy,
        }),
    );

  return (
    <section
      aria-labelledby="admin-character-converter-heading"
      className="character-converter"
      lang={locale}
    >
      <header className="character-converter__heading">
        <p className="px-display" aria-hidden="true">
          {copy.eyebrow}
        </p>
        <h1 id="admin-character-converter-heading">{copy.heading}</h1>
        <p>{copy.subtitle}</p>
      </header>
      <div className="character-converter__workbench px-panel px-panel--raised">
        <div className="character-converter__editor">
          <div className="character-converter__animation-preview">
            <h2>{copy.animationPreview}</h2>
            <div className="character-converter__pedestal px-panel px-panel--inset">
              <span className="character-converter__state-tab px-badge">
                {copy.stateLabels[previewState]}
              </span>
              {result ? (
                <div className="character-converter__plinth">
                  <Base64PngCanvas
                    className="character-converter__animated-canvas"
                    failureText={copy.previewFailed}
                    frame={selectedFrame}
                    frameOffsets={previewOffsets}
                    height={64}
                    label={copy.stateLabels[previewState]}
                    pngBase64={previewAsset}
                    pngUrl={previewAssetUrl}
                    state={previewState}
                    width={64}
                  />
                </div>
              ) : (
                <p>{copy.empty}</p>
              )}
            </div>
            <div
              aria-label={copy.animationState}
              className="character-converter__state-picker"
              role="group"
            >
              {CHARACTER_STATES.map((state) => (
                <button
                  className="px-button px-button--secondary"
                  disabled={!result}
                  aria-pressed={previewState === state}
                  key={state}
                  onClick={() => {
                    setPreviewState(state);
                    setSelectedFrame(null);
                  }}
                  type="button"
                >
                  {result && (
                    <span aria-hidden="true">
                      <Base64PngCanvas
                        className="character-converter__thumbnail"
                        failureText={copy.previewFailed}
                        frame={0}
                        frameOffsets={previewOffsets}
                        height={64}
                        label={copy.stateLabels[state]}
                        pngBase64={previewAsset}
                        pngUrl={previewAssetUrl}
                        state={state}
                        width={64}
                      />
                    </span>
                  )}
                  <span>{copy.stateLabels[state]}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="character-converter__source-result">
            {status && <p role="status">{copy[status]}</p>}
            <details className="character-converter__instructions px-info">
              <summary>ⓘ {copy.howTo}</summary>
              <p>{copy.introduction}</p>
              <ol>
                {copy.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              <p>{copy.reducedMotionNote}</p>
            </details>
            <form onSubmit={convert}>
              <div
                className="character-converter__dropzone"
                onDragOver={(event) => event.preventDefault()}
                onDrop={dropMaterial}
              >
                <strong>{copy.drop}</strong>
                <FileTrigger
                  acceptedFileTypes={[
                    ".png",
                    ".zip",
                    "image/png",
                    "application/zip",
                  ]}
                  onSelect={chooseFile}
                >
                  <Button
                    id="admin-character-source"
                    isDisabled={disabled || pending}
                    className={`px-button ${!source && !result ? "px-button--primary" : "px-button--secondary"}`}
                  >
                    {copy.chooseFile}
                  </Button>
                </FileTrigger>
                <FileTrigger
                  acceptDirectory
                  allowsMultiple
                  onSelect={chooseFolder}
                >
                  <Button
                    id="admin-character-folder"
                    isDisabled={disabled || pending}
                    className="px-button px-button--secondary"
                  >
                    {copy.chooseFolder}
                  </Button>
                </FileTrigger>
              </div>
              {source && (
                <p className="character-converter__source" role="status">
                  {copy.selected}: <strong>{source.displayName}</strong>
                  {source.kind === "folder"
                    ? ` · ${source.entries.length} ${copy.folderFiles}`
                    : ""}
                </p>
              )}
              <details className="character-converter__advanced">
                <summary>{copy.advancedSettings}</summary>
                <label htmlFor="admin-character-strategy">
                  {copy.strategy}
                </label>
                <select
                  disabled={disabled || pending}
                  id="admin-character-strategy"
                  onChange={(event) => {
                    setStrategy(
                      event.target.value as CharacterConversionStrategy,
                    );
                    setSelection(null);
                    setResult(null);
                    resetAlignment();
                    setStatus(null);
                  }}
                  value={strategy}
                >
                  <option value="pixelize">{copy.pixelize}</option>
                  <option value="pixel_exact">{copy.pixelExact}</option>
                </select>
              </details>
              <button
                className={`px-button ${source && !result ? "px-button--primary" : "px-button--secondary"}`}
                disabled={disabled || pending || !source}
                type="submit"
              >
                {pending ? copy.converting : copy.convert}
              </button>
            </form>{" "}
            {error && (
              <p role="alert">
                {copy[error.kind]} ({error.detail})
              </p>
            )}
            {selection && (
              <section aria-labelledby="character-candidate-heading">
                <h2 id="character-candidate-heading">{copy.candidates}</h2>
                <p>
                  {selection.discovery.candidates.length} · {copy.ignored}:{" "}
                  {selection.discovery.ignored_count}
                </p>
                <ul className="character-converter__candidates">
                  {selection.discovery.candidates.map((candidate, index) => (
                    <li key={candidate.candidate_id}>
                      <Base64PngCanvas
                        failureText={copy.previewFailed}
                        height={candidate.asset.height}
                        label={`${copy.candidates} ${index + 1}: ${candidate.source_path}`}
                        pngBase64={candidate.asset.png_base64}
                        pngUrl={candidate.asset.png_url}
                        width={candidate.asset.width}
                      />
                      <code>{candidate.source_path}</code>
                      <button
                        aria-label={`${copy.useCandidate}: ${candidate.source_path}`}
                        disabled={pending || disabled}
                        onClick={() => void prepare(candidate.candidate_id)}
                        type="button"
                      >
                        {copy.useCandidate}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {result && (
              <>
                {result.edge_cleanup && (
                  <section
                    aria-labelledby="character-edge-cleanup-heading"
                    className="character-converter__cleanup"
                  >
                    <h3 id="character-edge-cleanup-heading">
                      {copy.cleanupHeading}
                    </h3>
                    <p>{copy.cleanupHelp}</p>
                    <p>
                      {result.edge_cleanup.affected_frames.length}{" "}
                      {copy.cleanupFrames}
                    </p>
                    <div className="character-converter__cleanup-comparison">
                      {(
                        [
                          [copy.cleanupBefore, result.asset],
                          [copy.cleanupAfter, result.edge_cleanup.asset],
                        ] as const
                      ).map(([label, asset]) => (
                        <figure key={label}>
                          <figcaption>{label}</figcaption>
                          <div className="character-converter__animation-stage">
                            <Base64PngCanvas
                              className="character-converter__animated-canvas"
                              failureText={copy.previewFailed}
                              frame={comparisonFrame}
                              height={64}
                              label={`${label} · ${copy.stateLabels[previewState]} · ${copy.alignmentFrame} ${comparisonFrame + 1}`}
                              pngBase64={asset.png_base64}
                              pngUrl={asset.png_url}
                              state={previewState}
                              width={64}
                            />
                          </div>
                        </figure>
                      ))}
                    </div>
                    <div
                      aria-label={copy.cleanupHeading}
                      className="character-converter__cleanup-actions"
                      role="group"
                    >
                      <button
                        aria-pressed={cleanupChoice === "cleaned"}
                        disabled={pending || disabled}
                        onClick={() => void chooseCleanup("cleaned")}
                        type="button"
                      >
                        {copy.cleanupUse}
                      </button>
                      <button
                        aria-pressed={cleanupChoice === "original"}
                        disabled={pending || disabled}
                        onClick={() => void chooseCleanup("original")}
                        type="button"
                      >
                        {copy.cleanupKeep}
                      </button>
                    </div>
                  </section>
                )}
                {!cleanupReviewPending && (
                  <section
                    aria-labelledby="character-alignment-heading"
                    className="character-converter__alignment"
                  >
                    <h3 id="character-alignment-heading">
                      {copy.alignmentHeading}
                    </h3>
                    <p>{copy.alignmentHelp}</p>
                    <button
                      disabled={pending || disabled}
                      onClick={() => void suggestAlignment()}
                      type="button"
                    >
                      {alignmentOperation === "inspect"
                        ? copy.alignmentInspecting
                        : copy.alignmentSuggest}
                    </button>
                    {alignmentAnalysis && (
                      <>
                        <p className="character-converter__alignment-note">
                          {copy.alignmentNote}
                        </p>
                        {(alignedAsset ||
                          (!automaticPatternAvailable &&
                            !hasAlignmentEdits)) && (
                          <p role="status">
                            {alignedAsset
                              ? copy.alignmentReady
                              : copy.alignmentManualReview}
                          </p>
                        )}
                        <details
                          className="character-converter__alignment-details"
                          open
                          onToggle={(event) => {
                            if (!event.currentTarget.open)
                              setSelectedFrame(null);
                          }}
                        >
                          <summary>{copy.alignmentEdit}</summary>
                          <div
                            aria-label={`${copy.stateLabels[previewState]} · ${copy.alignmentFrame}`}
                            className="character-converter__frame-picker"
                            role="group"
                          >
                            {Array.from(
                              { length: CHARACTER_FRAME_COUNT },
                              (_, frame) => (
                                <button
                                  aria-pressed={selectedFrame === frame}
                                  disabled={pending}
                                  key={frame}
                                  onClick={() => selectFrame(frame)}
                                  type="button"
                                >
                                  {copy.alignmentFrame} {frame + 1}
                                </button>
                              ),
                            )}
                          </div>
                          {selectedFrame !== null && selectedOffset && (
                            <>
                              <p role="status">
                                {copy.alignmentPosition}: X {selectedOffset.x},
                                Y {selectedOffset.y}
                              </p>
                              <div className="character-converter__offset-fields">
                                {(["x", "y"] as const).map((axis) => {
                                  const minimum =
                                    axis === "x"
                                      ? -(selectedBounds?.left ?? 0)
                                      : -(selectedBounds?.top ?? 0);
                                  const maximum =
                                    axis === "x"
                                      ? CHARACTER_FRAME_SIZE -
                                        (selectedBounds?.right ??
                                          CHARACTER_FRAME_SIZE)
                                      : CHARACTER_FRAME_SIZE -
                                        (selectedBounds?.bottom ??
                                          CHARACTER_FRAME_SIZE);
                                  return (
                                    <label key={axis}>
                                      <span>
                                        {copy.stateLabels[previewState]} ·{" "}
                                        {copy.alignmentFrame}{" "}
                                        {selectedFrame + 1} ·{" "}
                                        {axis.toUpperCase()}{" "}
                                        {copy.alignmentPixels}
                                      </span>
                                      <input
                                        aria-invalid={!offsetDraftValid}
                                        disabled={pending || disabled}
                                        max={maximum}
                                        min={minimum}
                                        onBlur={() => {
                                          if (!offsetDraftValid) {
                                            setOffsetDraft({
                                              x: String(selectedOffset.x),
                                              y: String(selectedOffset.y),
                                            });
                                          }
                                        }}
                                        onChange={(event) =>
                                          updateOffsetDraft(
                                            axis,
                                            event.target.value,
                                          )
                                        }
                                        step={1}
                                        type="number"
                                        value={offsetDraft[axis]}
                                      />
                                    </label>
                                  );
                                })}
                              </div>
                              {!offsetDraftValid && (
                                <p role="alert">{copy.alignmentInvalid}</p>
                              )}
                              <div className="character-converter__nudge-controls">
                                {(
                                  [
                                    [copy.alignmentLeft, -1, 0],
                                    [copy.alignmentRight, 1, 0],
                                    [copy.alignmentUp, 0, -1],
                                    [copy.alignmentDown, 0, 1],
                                  ] as const
                                ).map(([label, dx, dy]) => (
                                  <button
                                    disabled={pending || !canNudge(dx, dy)}
                                    key={label}
                                    onClick={() => nudgeFrame(dx, dy)}
                                    type="button"
                                  >
                                    {label}
                                  </button>
                                ))}
                              </div>
                              <button
                                onClick={() => setSelectedFrame(null)}
                                type="button"
                              >
                                {copy.alignmentPlay}
                              </button>
                            </>
                          )}
                        </details>
                        <div className="character-converter__alignment-actions">
                          <button
                            disabled={
                              pending ||
                              disabled ||
                              !alignmentNeedsApply ||
                              !offsetDraftValid
                            }
                            onClick={() => void applyAlignment()}
                            type="button"
                          >
                            {alignmentOperation === "apply"
                              ? copy.alignmentApplying
                              : copy.alignmentApply}
                          </button>
                          <button
                            disabled={
                              pending || (!hasAlignmentEdits && !alignedAsset)
                            }
                            onClick={restoreOriginal}
                            type="button"
                          >
                            {copy.alignmentRestore}
                          </button>
                        </div>
                        {alignmentNeedsApply && (
                          <p role="status">{copy.alignmentUnapplied}</p>
                        )}
                      </>
                    )}
                  </section>
                )}
                <details className="character-converter__technical">
                  <summary>{copy.technicalDetails}</summary>
                  <h2>{copy.sheetPreview}</h2>
                  <Base64PngCanvas
                    failureText={copy.previewFailed}
                    frameOffsets={previewOffsets}
                    height={result.asset.height}
                    label={copy.sheetPreview}
                    pngBase64={previewAsset}
                    pngUrl={previewAssetUrl}
                    width={result.asset.width}
                  />
                  <h2>{copy.report}</h2>
                  <dl>
                    <div>
                      <dt>{copy.sourceKind}</dt>
                      <dd>{result.conversion.source_kind}</dd>
                    </div>
                    {result.conversion.source_path && (
                      <div>
                        <dt>{copy.sourcePath}</dt>
                        <dd>{result.conversion.source_path}</dd>
                      </div>
                    )}
                    <div>
                      <dt>{copy.dimensions}</dt>
                      <dd>
                        {result.asset.width}×{result.asset.height}
                      </dd>
                    </div>
                  </dl>
                  <h3>{copy.warnings}</h3>
                  {result.conversion.warnings.length ? (
                    <ul>
                      {result.conversion.warnings.map((warning) => (
                        <li key={warning.code}>
                          <code>{warning.code}</code>
                          {warning.items.length
                            ? `: ${warning.items.join(", ")}`
                            : ""}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>{copy.noWarnings}</p>
                  )}
                </details>
                <label htmlFor="admin-character-filename">
                  {copy.filename}
                </label>
                <input
                  aria-describedby="admin-character-filename-help"
                  disabled={pending}
                  id="admin-character-filename"
                  onChange={(event) => setFilename(event.target.value)}
                  value={filename}
                />
                <small id="admin-character-filename-help">
                  {copy.filenameHelp}
                </small>
              </>
            )}
          </div>
        </div>
        {result && (
          <footer
            className="character-converter__confirm"
            ref={reserveCharacterConfirmationSpace}
          >
            {onApply && (
              <button
                className="px-button px-button--primary"
                type="button"
                disabled={
                  pending || disabled || !downloadableAsset || !offsetDraftValid
                }
                onClick={async () => {
                  if (!downloadableAsset) return;
                  setPending(true);
                  setError(null);
                  try {
                    await onApply(downloadableAsset);
                    setStatus("applied");
                  } catch (error) {
                    setError({
                      kind: "failed",
                      detail:
                        error instanceof Error
                          ? error.message
                          : "REQUEST_FAILED",
                    });
                  } finally {
                    setPending(false);
                  }
                }}
              >
                {copy.apply}
              </button>
            )}
            <button
              className="px-button px-button--secondary"
              disabled={
                pending ||
                !filenameValid ||
                !downloadableAsset ||
                !offsetDraftValid
              }
              onClick={download}
              type="button"
            >
              {copy.download}
            </button>
          </footer>
        )}
      </div>
    </section>
  );
}

function reserveCharacterConfirmationSpace(footer: HTMLElement | null) {
  if (!footer) return;
  const editor = footer.previousElementSibling as HTMLElement;
  const reserve = () => {
    editor.style.setProperty(
      "--character-confirm-height",
      `${footer.getBoundingClientRect().height}px`,
    );
  };
  reserve();
  const observer =
    typeof ResizeObserver === "undefined" ? null : new ResizeObserver(reserve);
  observer?.observe(footer);
  return () => observer?.disconnect();
}

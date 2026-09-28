"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Icon } from "@/components/icon";
import {
  type AssistantResultView,
  ResultsTabs,
  type ResultTab,
} from "@/components/workspace/results-tabs";
import type { SelectedAoi } from "@/lib/aoi";
import {
  type InferenceClient,
  type InferenceJobStatus,
  inferenceJobStatusSchema,
  inferenceClient,
} from "@/lib/inference-client";
import {
  geoAgentClient,
  GeoAgentClientError,
  type GeoAgentClient,
  type GeoAgentExecution,
  type GeoAgentSelection,
} from "@/lib/geoagent-client";
import {
  groundingOverlayFromEvidence,
  type InferenceGroundingOverlay,
} from "@/lib/inference-grounding-map-layer";
import type { SelectedCatalogueScene } from "@/lib/scene-selection";
import {
  changeClient,
  changeResultSchema,
  type ChangeClient,
  type ChangeResult,
} from "@/lib/change-client";
import {
  opticalSarClient,
  opticalSarResultSchema,
  type OpticalSarClient,
  type OpticalSarResult,
  type SarScene,
} from "@/lib/optical-sar-client";
import type { ProcessingJobStatus } from "@/lib/preparation-client";

type Pair = { sceneA: SelectedCatalogueScene; sceneB: SelectedCatalogueScene };
type SarSelection = { scene: SarScene; polarization: string };
export type AssistantSelectionAction = "aoi" | "scene" | "pair" | "sar";

export const suggestedQuestions = [
  "What surface types are visible?",
  "Describe the visible land cover.",
  "Where is vegetation visible?",
];

export function suggestionsForSelection(
  pair: Pair | null,
  sar: SarSelection | null,
  scene: SelectedCatalogueScene | null,
) {
  if (sar && scene)
    return ["Summarize optical and SAR observations.", "What is visible in the optical image?"];
  if (pair) return ["What changed between these dates?", "Show that change on the map"];
  return scene ? suggestedQuestions : ["What is visible in this image?"];
}

const identity = (scene: SelectedCatalogueScene) => ({
  provider: scene.identity.providerId,
  collection: scene.identity.collectionId,
  item: scene.identity.itemId,
});
const selectedOptical = (scene: SelectedCatalogueScene) => ({
  source: identity(scene),
  modality: "optical" as const,
  acquired_at: scene.scene.acquisition.start,
  polarization: null,
});
const sameSource = (
  a: { provider: string; collection: string; item: string },
  b: { provider: string; collection: string; item: string },
) => a.provider === b.provider && a.collection === b.collection && a.item === b.item;

const EMPTY_RESULT: AssistantResultView = {
  phase: "idle",
  status: null,
  evidence: null,
  error: null,
  retryable: false,
  sourceSceneKey: null,
  stale: false,
};

function wait(milliseconds: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(resolve, milliseconds);
    signal.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

export function AssistantPanel({
  visible,
  draft,
  activeTab,
  selectedAoi,
  selectedScene,
  comparison = null,
  sarSelection = null,
  onDraftChange,
  onTabChange,
  onClose,
  onGroundingOverlayChange,
  onSelectionAction = () => {},
  onOpenChangeResult = () => {},
  onOpenOpticalSarResult = () => {},
  client = geoAgentClient,
  inference = inferenceClient,
  change = changeClient,
  opticalSar = opticalSarClient,
}: {
  visible: boolean;
  draft: string;
  activeTab: ResultTab;
  selectedAoi: SelectedAoi | null;
  selectedScene: SelectedCatalogueScene | null;
  comparison?: Pair | null;
  sarSelection?: SarSelection | null;
  onDraftChange: (draft: string) => void;
  onTabChange: (tab: ResultTab) => void;
  onClose: () => void;
  onGroundingOverlayChange: (overlay: InferenceGroundingOverlay | null) => void;
  onSelectionAction?: (action: AssistantSelectionAction) => void;
  onOpenChangeResult?: (result: ChangeResult) => void;
  onOpenOpticalSarResult?: (result: OpticalSarResult) => void;
  client?: GeoAgentClient;
  inference?: InferenceClient;
  change?: ChangeClient;
  opticalSar?: OpticalSarClient;
}) {
  const [operation, setOperation] = useState<"question" | "caption" | "locate">("question");
  const [result, setResult] = useState<AssistantResultView>(EMPTY_RESULT);
  const [overlayVisible, setOverlayVisible] = useState(false);
  const [computedChange, setComputedChange] = useState<ChangeResult | null>(null);
  const [computedOpticalSar, setComputedOpticalSar] = useState<OpticalSarResult | null>(null);
  const [resultBinding, setResultBinding] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [activity, setActivity] = useState<{
    tool: string;
    jobId: string | null;
    state: string;
    stage: string | null;
    completed: number | null;
    total: number | null;
    scenes: string[];
  } | null>(null);
  const conversationId = useRef<string | null>(null);
  const retryId = useRef<string | null>(null);
  const requestRef = useRef<{
    sequence: number;
    controller: AbortController;
    binding: string;
  } | null>(null);
  const sequenceRef = useRef(0);
  const binding = JSON.stringify({
    aoi: selectedAoi?.feature.geometry ?? null,
    scene: selectedScene?.key ?? null,
    pair: comparison ? [comparison.sceneA.key, comparison.sceneB.key] : null,
    sar: sarSelection ? [sarSelection.scene.source, sarSelection.polarization] : null,
  });
  const priorBinding = useRef(binding);
  const stale = resultBinding !== null && resultBinding !== binding;
  const displayedResult = useMemo(() => ({ ...result, stale }), [result, stale]);
  const needsText = operation !== "caption";
  const asksWhatChanged =
    operation === "question" &&
    /\b(change|changed|changes|before|after|difference|earlier image)\b/i.test(draft.trim());
  const asksOpticalSar =
    operation === "question" && /\b(sar|radar|sentinel[- ]?1)\b/i.test(draft.trim());
  const supportedScene = (scene: SelectedCatalogueScene) =>
    scene.identity.providerId === "earth-search" &&
    scene.identity.collectionId === "sentinel-2-c1-l2a";
  const supported =
    asksWhatChanged && comparison
      ? supportedScene(comparison.sceneA) && supportedScene(comparison.sceneB)
      : selectedScene
        ? supportedScene(selectedScene)
        : false;
  const missing = !selectedAoi
    ? { text: "Select an AOI before analysis.", action: "aoi" as const, label: "Choose an AOI" }
    : asksWhatChanged && !comparison
      ? {
          text: "Assign two dated optical scenes to compare.",
          action: "pair" as const,
          label: "Select two dates",
        }
      : asksOpticalSar && !sarSelection
        ? {
            text: "Choose a SAR scene and polarization.",
            action: "sar" as const,
            label: "Select SAR imagery",
          }
        : (!selectedScene && !(asksWhatChanged && comparison)) || !supported
          ? {
              text: "Select a supported Sentinel-2 L2A image.",
              action: "scene" as const,
              label: "Find imagery",
            }
          : null;
  const canSubmit = Boolean(!missing && (!needsText || draft.trim()) && result.phase !== "loading");

  useEffect(() => {
    if (conversationId.current) return;
    try {
      const stored = window.sessionStorage.getItem("satquery.geoagent.conversation.v1");
      conversationId.current =
        stored && /^[0-9a-f-]{36}$/i.test(stored) ? stored : crypto.randomUUID();
      window.sessionStorage.setItem("satquery.geoagent.conversation.v1", conversationId.current);
    } catch {
      conversationId.current = crypto.randomUUID();
    }
  }, []);

  useEffect(() => {
    if (priorBinding.current === binding) return;
    priorBinding.current = binding;
    if (requestRef.current && requestRef.current.binding !== binding) {
      requestRef.current.controller.abort();
      requestRef.current = null;
    }
    sequenceRef.current += 1;
    retryId.current = null;
    setOverlayVisible(false);
    onGroundingOverlayChange(null);
    setNotice(null);
  }, [binding, onGroundingOverlayChange]);

  useEffect(() => () => requestRef.current?.controller.abort(), []);

  const selectionForQuestion = (): GeoAgentSelection => ({
    aoi: selectedAoi?.feature.geometry ?? null,
    scenes:
      asksWhatChanged && comparison
        ? [selectedOptical(comparison.sceneA), selectedOptical(comparison.sceneB)]
        : asksOpticalSar && sarSelection && selectedScene
          ? [
              selectedOptical(selectedScene),
              {
                source: sarSelection.scene.source,
                modality: "sar",
                acquired_at: sarSelection.scene.acquisition.start,
                polarization: sarSelection.polarization as "HH" | "HV" | "VH" | "VV",
              },
            ]
          : selectedScene
            ? [selectedOptical(selectedScene)]
            : [],
  });
  const effectiveMessage = () => {
    if (operation === "caption") return "Caption this image.";
    if (operation === "locate" && !/\b(where|locate|find)\b/i.test(draft))
      return `Where is ${draft.trim().replace(/[?.!]+$/, "")}?`;
    return draft.trim();
  };
  const isCurrent = (run: number, sourceBinding: string, controller: AbortController) =>
    !controller.signal.aborted &&
    requestRef.current?.sequence === run &&
    requestRef.current.binding === sourceBinding;
  const updateProgress = (status: InferenceJobStatus | ProcessingJobStatus) => {
    setActivity((previous) =>
      previous
        ? {
            ...previous,
            state: status.state,
            stage: status.current_stage,
            completed: status.progress?.completed_units ?? null,
            total: status.progress?.total_units ?? null,
          }
        : null,
    );
  };
  const acceptChange = (raw: unknown, expectedArtifact: string | null, sourceBinding: string) => {
    const parsed = changeResultSchema.safeParse(raw);
    if (
      !parsed.success ||
      (expectedArtifact && parsed.data.classification_artifact_id !== expectedArtifact)
    )
      throw new Error("The committed change result does not match its artifact reference.");
    const selected = selectionForQuestion().scenes;
    if (
      !selectedAoi ||
      selected.length !== 2 ||
      JSON.stringify(parsed.data.aoi) !== JSON.stringify(selectedAoi.feature.geometry) ||
      parsed.data.sources.some(
        (source) =>
          !selected.some(
            (item) =>
              sameSource(item.source, source.scene) &&
              Date.parse(item.acquired_at ?? "") === Date.parse(source.acquired_at),
          ),
      )
    )
      throw new Error("Change result provenance does not match the selected AOI and dates.");
    setComputedChange(parsed.data);
    setComputedOpticalSar(null);
    setResultBinding(sourceBinding);
    setResult(EMPTY_RESULT);
    setNotice(null);
    return parsed.data;
  };
  const acceptOpticalSar = (
    raw: unknown,
    expectedArtifact: string | null,
    sourceBinding: string,
  ) => {
    const parsed = opticalSarResultSchema.safeParse(raw);
    if (
      !parsed.success ||
      (expectedArtifact && parsed.data.evidence_artifact_id !== expectedArtifact)
    )
      throw new Error("The committed optical/SAR result does not match its artifact reference.");
    const selected = selectionForQuestion().scenes;
    if (
      selected.length !== 2 ||
      ![parsed.data.optical, parsed.data.sar].every((source) =>
        selected.some(
          (item) =>
            sameSource(item.source, source.source) &&
            Date.parse(item.acquired_at ?? "") === Date.parse(source.acquired_at),
        ),
      )
    )
      throw new Error("Optical/SAR result provenance does not match the selected scenes.");
    setComputedOpticalSar(parsed.data);
    setComputedChange(null);
    setResultBinding(sourceBinding);
    setResult(EMPTY_RESULT);
    setNotice(null);
    return parsed.data;
  };
  const receiveExecution = async (
    execution: GeoAgentExecution,
    run: number,
    sourceBinding: string,
    controller: AbortController,
  ) => {
    setActivity({
      tool: execution.summary.tool ?? "none",
      jobId: execution.job_id,
      state: execution.status,
      stage: null,
      completed: null,
      total: null,
      scenes: execution.summary.input_scenes.map((scene) => scene.item),
    });
    if (
      [
        "failed",
        "unavailable",
        "unsupported",
        "clarification_required",
        "submission_unknown",
      ].includes(execution.status)
    ) {
      setNotice(execution.message);
      setResult({
        ...EMPTY_RESULT,
        phase: "failed",
        error: execution.message,
        retryable: execution.retry_same_request_id || execution.status === "failed",
      });
      return;
    }
    const tool = execution.summary.tool;
    if (!tool) throw new Error("No analysis tool was recorded.");
    if (execution.status === "completed") {
      if (tool.startsWith("inference_")) {
        const parsed = inferenceJobStatusSchema.safeParse(execution.output);
        if (!parsed.success) throw new Error("Committed model evidence is unavailable.");
        finish(parsed.data, selectedScene?.key ?? "", sourceBinding);
      } else if (tool === "optical_change")
        acceptChange(execution.output, execution.result_id, sourceBinding);
      else if (tool === "optical_sar_observation")
        acceptOpticalSar(execution.output, execution.result_id, sourceBinding);
      else {
        setResult(EMPTY_RESULT);
        setNotice("Imagery metadata is available; open the source image in the viewer.");
      }
      return;
    }
    if (!execution.job_id) throw new Error("The running tool did not provide a job ID.");
    let jobState = "queued";
    while (
      isCurrent(run, sourceBinding, controller) &&
      !["succeeded", "failed", "cancelled"].includes(jobState)
    ) {
      await wait(750, controller.signal);
      if (!isCurrent(run, sourceBinding, controller)) return;
      if (tool.startsWith("inference_")) {
        const status = await inference.status(execution.job_id, controller.signal);
        if (!isCurrent(run, sourceBinding, controller)) return;
        jobState = status.state;
        updateProgress(status);
        setResult((previous) => ({ ...previous, status }));
        if (["succeeded", "failed", "cancelled"].includes(jobState))
          finish(status, selectedScene?.key ?? "", sourceBinding);
      } else if (tool === "optical_change" || tool === "optical_sar_observation") {
        const status =
          tool === "optical_change"
            ? await change.status(execution.job_id, controller.signal)
            : await opticalSar.status(execution.job_id, controller.signal);
        if (!isCurrent(run, sourceBinding, controller)) return;
        jobState = status.state;
        updateProgress(status);
        if (jobState === "succeeded") {
          const raw =
            tool === "optical_change"
              ? await change.result(execution.job_id, controller.signal)
              : await opticalSar.result(execution.job_id, controller.signal);
          if (!isCurrent(run, sourceBinding, controller)) return;
          if (tool === "optical_change") acceptChange(raw, null, sourceBinding);
          else acceptOpticalSar(raw, null, sourceBinding);
        } else if (jobState === "failed" || jobState === "cancelled") {
          const explanation =
            status.safe_error_message ?? `The ${tool.replaceAll("_", " ")} job ${jobState}.`;
          setNotice(explanation);
          setResult({
            ...EMPTY_RESULT,
            phase: "failed",
            error: explanation,
            retryable: jobState === "failed",
          });
        }
      } else return;
    }
  };
  const submit = async (requestId?: string) => {
    if (!selectedAoi || !canSubmit) return;
    requestRef.current?.controller.abort();
    const controller = new AbortController();
    const sequence = ++sequenceRef.current;
    const sourceBinding = binding;
    requestRef.current = { sequence, controller, binding: sourceBinding };
    const id = requestId ?? crypto.randomUUID();
    retryId.current = id;
    setComputedChange(null);
    setComputedOpticalSar(null);
    setOverlayVisible(false);
    onGroundingOverlayChange(null);
    setResult({ ...EMPTY_RESULT, phase: "loading", sourceSceneKey: selectedScene?.key ?? null });
    setResultBinding(sourceBinding);
    setNotice(null);
    setActivity(null);
    onTabChange("answer");
    try {
      const session = conversationId.current ?? crypto.randomUUID();
      conversationId.current = session;
      let revision = 0;
      try {
        revision = (await client.get(session, controller.signal)).selection_revision;
      } catch (error) {
        if (!(error instanceof GeoAgentClientError && error.code === "CONVERSATION_NOT_FOUND"))
          throw error;
      }
      if (!isCurrent(sequence, sourceBinding, controller)) return;
      const inheritCurrentSelection =
        /\bwhat about this area\b/i.test(draft.trim()) && resultBinding === sourceBinding;
      const response = await client.turn(
        session,
        {
          request_id: id,
          expected_selection_revision: revision,
          message: effectiveMessage(),
          ...(inheritCurrentSelection ? {} : { selection: selectionForQuestion() }),
        },
        controller.signal,
      );
      if (!isCurrent(sequence, sourceBinding, controller)) return;
      if (response.status === "clarification_required" || response.status === "stale") {
        setNotice(response.message);
        setResult(EMPTY_RESULT);
      } else if (response.resolved_result?.tool === "optical_change") {
        const raw = await change.result(response.resolved_result.job_id, controller.signal);
        if (!isCurrent(sequence, sourceBinding, controller)) return;
        const result = acceptChange(raw, response.resolved_result.result_id, sourceBinding);
        onOpenChangeResult(result);
        setNotice("Opened the verified change layer on the map.");
      } else if (response.execution) {
        await receiveExecution(response.execution, sequence, sourceBinding, controller);
      } else {
        setResult(EMPTY_RESULT);
        setNotice(response.message);
      }
    } catch (error) {
      if (!isCurrent(sequence, sourceBinding, controller)) return;
      const clientError = error instanceof GeoAgentClientError ? error : null;
      const message =
        clientError?.message ?? (error instanceof Error ? error.message : "Analysis failed.");
      setNotice(message);
      setResult({
        ...EMPTY_RESULT,
        phase: "failed",
        error: message,
        retryable: clientError?.retryable ?? true,
        sourceSceneKey: selectedScene?.key ?? null,
      });
    } finally {
      if (requestRef.current?.sequence === sequence) requestRef.current = null;
    }
  };

  const finish = (status: InferenceJobStatus, sourceSceneKey: string, sourceBinding: string) => {
    updateProgress(status);
    if (
      status.state === "succeeded" &&
      status.result &&
      selectedScene &&
      (!sameSource(status.result.source_chip.scene, identity(selectedScene)) ||
        Date.parse(status.result.source_chip.acquired_at) !==
          Date.parse(selectedScene.scene.acquisition.start))
    )
      throw new Error("Model evidence does not match the selected image and acquisition date.");
    if (status.state !== "succeeded" || !status.result) {
      setResult({
        phase: "failed",
        status,
        evidence: null,
        error:
          status.safe_error_message ??
          (status.state === "cancelled"
            ? "Inference was cancelled."
            : "Inference ended without a result."),
        retryable: status.state === "failed",
        sourceSceneKey,
        stale: false,
      });
      return;
    }
    setResult({
      phase: "succeeded",
      status,
      evidence: status.result,
      error: null,
      retryable: false,
      sourceSceneKey,
      stale: false,
    });
    setResultBinding(sourceBinding);
    setNotice(null);
    if (status.result.grounding?.candidates.length) onTabChange("evidence");
  };

  const changeOverlay = (visible: boolean) => {
    setOverlayVisible(visible);
    if (!visible || stale || !result.evidence || !result.sourceSceneKey) {
      onGroundingOverlayChange(null);
      return;
    }
    onGroundingOverlayChange(groundingOverlayFromEvidence(result.evidence, result.sourceSceneKey));
  };

  return (
    <aside className="assistant-panel" aria-label="SatQuery assistant" hidden={!visible}>
      <div className="assistant-header">
        <div>
          <p className="panel-kicker">
            <Icon name="spark" /> Assistant
          </p>
          <h2>Ask about the scene</h2>
        </div>
        <button
          className="icon-button"
          type="button"
          aria-label="Hide assistant panel"
          onClick={onClose}
        >
          <Icon name="close" />
        </button>
      </div>
      <div className="composer-section">
        <fieldset className="inference-operation">
          <legend>Operation</legend>
          <label>
            <input
              type="radio"
              name="inference-operation"
              checked={operation === "question"}
              onChange={() => setOperation("question")}
            />{" "}
            Question
          </label>
          <label>
            <input
              type="radio"
              name="inference-operation"
              checked={operation === "caption"}
              onChange={() => setOperation("caption")}
            />{" "}
            Caption
          </label>
          <label>
            <input
              type="radio"
              name="inference-operation"
              checked={operation === "locate"}
              onChange={() => setOperation("locate")}
            />{" "}
            Locate
          </label>
        </fieldset>
        <label htmlFor="analysis-question">
          {operation === "locate" ? "Feature to locate" : "Question"}
        </label>
        <div className="composer-field">
          <textarea
            id="analysis-question"
            value={draft}
            rows={4}
            disabled={!needsText}
            maxLength={500}
            placeholder={
              needsText
                ? "Ask one question about selected imagery…"
                : "Captioning uses the selected scientific image."
            }
            onChange={(event) => onDraftChange(event.target.value)}
          />
          <span className="composer-status">
            Draft kept in this browser tab · {draft.length}/500
          </span>
        </div>
        {operation === "question" ? (
          <fieldset className="suggestions">
            <legend id="suggestions-title">Try a question</legend>
            <div className="suggestion-list">
              {suggestionsForSelection(comparison, sarSelection, selectedScene).map((question) => (
                <button key={question} type="button" onClick={() => onDraftChange(question)}>
                  {question}
                </button>
              ))}
            </div>
          </fieldset>
        ) : null}
        <div className="composer-actions">
          <button
            className="button button-quiet"
            type="button"
            disabled={!draft.length || result.phase === "loading"}
            onClick={() => onDraftChange("")}
          >
            Clear draft
          </button>
          <button
            className="button button-primary"
            type="button"
            disabled={!canSubmit}
            onClick={() => void submit()}
          >
            {result.phase === "loading"
              ? "Processing…"
              : operation === "caption"
                ? "Generate caption"
                : operation === "locate"
                  ? "Locate feature"
                  : "Ask question"}
          </button>
        </div>
        {missing ? (
          <p className="availability-note">
            <Icon name="help" />
            <span>
              {missing.text}{" "}
              <button
                type="button"
                className="button button-quiet"
                onClick={() => onSelectionAction(missing.action)}
              >
                {missing.label}
              </button>
            </span>
          </p>
        ) : (
          <p className="availability-note">
            <Icon name="help" />
            <span>
              {comparison && asksWhatChanged
                ? `Comparing ${comparison.sceneA.identity.itemId} and ${comparison.sceneB.identity.itemId}.`
                : sarSelection && asksOpticalSar
                  ? `Optical ${selectedScene?.identity.itemId} and SAR ${sarSelection.scene.source.item} (${sarSelection.polarization}).`
                  : `Uses scene ${selectedScene?.identity.itemId} acquired ${selectedScene ? new Date(selectedScene.scene.acquisition.start).toLocaleString() : "unknown"}.`}
            </span>
          </p>
        )}
        {activity ? (
          <p className="availability-note" role="status">
            {activity.tool}: {activity.state}
            {activity.stage ? ` · ${activity.stage}` : ""}
            {activity.completed !== null && activity.total !== null
              ? ` · ${activity.completed}/${activity.total} stages`
              : ""}
            . {activity.scenes.length ? `Sources: ${activity.scenes.join(", ")}.` : ""}
            {activity.jobId ? ` Job ${activity.jobId}.` : ""}
          </p>
        ) : null}
        {notice && !result.error ? (
          <p className="availability-note" role="status">
            {notice}
          </p>
        ) : null}
        {stale ? (
          <p className="availability-note" role="status">
            Selection changed. This answer belongs to the previous imagery; run it again for the
            current selection.
          </p>
        ) : null}
        {result.phase === "failed" && result.retryable && !stale ? (
          <button
            className="button button-quiet"
            type="button"
            onClick={() => void submit(retryId.current ?? undefined)}
          >
            Retry analysis
          </button>
        ) : null}
      </div>
      {!stale && computedOpticalSar && activeTab === "answer" ? (
        <section aria-label="Computed optical and SAR answer">
          <p className="interpretation-label">
            Computed separate source observations · not a fusion or model confidence result
          </p>
          <p>{computedOpticalSar.answer}</p>
          <p>
            Optical: {computedOpticalSar.optical.source.item} (
            {computedOpticalSar.optical.acquired_at}); evidence{" "}
            {computedOpticalSar.optical.evidence_bounds?.join(", ") ?? "unavailable"}{" "}
            {computedOpticalSar.optical.evidence_crs ?? ""}.
          </p>
          <p>
            SAR: {computedOpticalSar.sar.source.item} ({computedOpticalSar.sar.acquired_at});
            evidence {computedOpticalSar.sar.evidence_bounds?.join(", ") ?? "unavailable"}{" "}
            {computedOpticalSar.sar.evidence_crs ?? ""}.
          </p>
          <p>
            Joint observed coverage {computedOpticalSar.joint_usable_percent_of_aoi.toFixed(2)}% of
            AOI. Alignment {computedOpticalSar.alignment_state}; agreement not assessed.
          </p>
          {computedOpticalSar.limitations.map((item) => (
            <p key={item}>Limitation: {item}</p>
          ))}
          <button
            type="button"
            className="button button-quiet"
            onClick={() => onOpenOpticalSarResult(computedOpticalSar)}
          >
            Inspect selected SAR layer (if prepared)
          </button>
        </section>
      ) : !stale && computedChange && activeTab === "answer" ? (
        <section className="computed-change-answer" aria-label="Computed change answer">
          <p className="interpretation-label">
            Computed two-date raster result · not a single-image model interpretation
          </p>
          {computedChange.statements.map((statement) => (
            <p key={statement}>{statement}</p>
          ))}
          <p>
            <strong>Before/after:</strong>{" "}
            {new Date(computedChange.sources[0].acquired_at).toLocaleDateString()} →{" "}
            {new Date(computedChange.sources[1].acquired_at).toLocaleDateString()}
          </p>
          <p>
            <strong>Source pair:</strong> {computedChange.sources[0].scene.item} →{" "}
            {computedChange.sources[1].scene.item}
          </p>
          <p>
            <strong>Computed evidence:</strong> {computedChange.method} (
            {computedChange.method_version}); processing {computedChange.processing_version}; job{" "}
            {computedChange.job_id}
          </p>
          {computedChange.warnings.map((warning) => (
            <p key={warning.code}>
              <strong>Warning:</strong> {warning.statement}
            </p>
          ))}
          <button
            type="button"
            className="button button-quiet"
            onClick={() => onOpenChangeResult(computedChange)}
          >
            Open change layer on map
          </button>
        </section>
      ) : (
        <ResultsTabs
          activeTab={activeTab}
          onChange={onTabChange}
          result={displayedResult}
          overlayVisible={overlayVisible}
          onOverlayVisibleChange={changeOverlay}
        />
      )}
    </aside>
  );
}

"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { SelectedAoi } from "@/lib/aoi";
import {
  type PreparationClient,
  PreparationClientError,
  type PreparationManifest,
  type ProcessingJobStatus,
  preparationArtifactUrl,
  preparationClient,
  preparationQualityReportUrl,
  type QualityReport,
} from "@/lib/preparation-client";
import type { SelectedCatalogueScene } from "@/lib/scene-selection";

export type PreparationMaskOverlay = {
  qualityArtifactIds: string[];
  bounds: [number, number, number, number];
  usable: boolean;
  exclusions: boolean;
};

type Pair = { sceneA: SelectedCatalogueScene; sceneB: SelectedCatalogueScene };
type Result = {
  binding: string;
  status: ProcessingJobStatus;
  report: QualityReport;
  manifest: PreparationManifest;
};
export interface PreparationPanelProps {
  selectedAoi: SelectedAoi | null;
  selectedScene: SelectedCatalogueScene | null;
  comparison: Pair | null;
  client?: PreparationClient;
  onOverlayChange?: (overlay: PreparationMaskOverlay | null) => void;
}

const PROFILE = "sentinel-2-l2a-surface-reflectance-v1" as const;
const MAX_PIXELS = 4_000_000;
const terminal = new Set(["succeeded", "failed", "cancelled"]);
const noopOverlay = () => {};

function identity(scene: SelectedCatalogueScene) {
  return {
    provider: scene.identity.providerId,
    collection: scene.identity.collectionId,
    item: scene.identity.itemId,
  };
}

function fingerprint(value: string) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1)
    hash = Math.imul(hash ^ value.charCodeAt(index), 16777619);
  return (hash >>> 0).toString(36);
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}

function formatMeasured(check: QualityReport["checks"][number]) {
  if (check.measured_value === null) return check.measured_text ?? "Unavailable";
  const value = Number.isInteger(check.measured_value)
    ? check.measured_value
    : check.measured_value.toFixed(2);
  const denominator =
    check.denominator_name && check.denominator_value !== null
      ? ` of ${check.denominator_value.toLocaleString()} ${check.denominator_name}`
      : "";
  return `${value}${check.units ? ` ${check.units}` : ""}${denominator}`;
}

export function PreparationPanel({
  selectedAoi,
  selectedScene,
  comparison,
  client = preparationClient,
  onOverlayChange = noopOverlay,
}: PreparationPanelProps) {
  const [mode, setMode] = useState<"single" | "pair">("single");
  const [status, setStatus] = useState<ProcessingJobStatus | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [messageKind, setMessageKind] = useState<"blocked" | "failure" | null>(null);
  const [outdated, setOutdated] = useState(false);
  const [usable, setUsable] = useState(false);
  const [exclusions, setExclusions] = useState(false);
  const sequence = useRef(0);
  const active = useRef<AbortController | null>(null);
  const previousBinding = useRef<string | null>(null);
  const completedBinding = useRef<string | null>(null);
  const scenes =
    mode === "pair" && comparison
      ? [comparison.sceneA, comparison.sceneB]
      : selectedScene
        ? [selectedScene]
        : [];
  const binding = useMemo(
    () =>
      JSON.stringify({
        aoi: selectedAoi?.feature.geometry ?? null,
        scenes: scenes.map((scene) => scene.key),
        profile: PROFILE,
        version: "6H-ui-v1",
      }),
    [selectedAoi, scenes],
  );
  const readyToSubmit = Boolean(selectedAoi && scenes.length === (mode === "pair" ? 2 : 1));
  const processing = status ? !terminal.has(status.state) : false;

  useEffect(() => {
    if (!comparison && mode === "pair") setMode("single");
  }, [comparison, mode]);

  useEffect(() => {
    if (previousBinding.current !== null && previousBinding.current !== binding) {
      sequence.current += 1;
      active.current?.abort();
      setSubmitting(false);
      setStatus(null);
      if (completedBinding.current && completedBinding.current !== binding) setOutdated(true);
      setUsable(false);
      setExclusions(false);
      onOverlayChange(null);
    }
    previousBinding.current = binding;
  }, [binding, onOverlayChange]);

  useEffect(() => {
    if (!result || outdated || (!usable && !exclusions)) {
      onOverlayChange(null);
      return;
    }
    onOverlayChange({
      qualityArtifactIds: result.manifest.scenes.map((scene) => scene.quality_artifact_id),
      bounds: selectedAoi?.bounds ?? [0, 0, 0, 0],
      usable,
      exclusions,
    });
  }, [exclusions, outdated, result, selectedAoi?.bounds, usable, onOverlayChange]);

  useEffect(() => () => active.current?.abort(), []);

  async function loadResult(
    next: ProcessingJobStatus,
    runBinding: string,
    requestSequence: number,
    signal: AbortSignal,
  ) {
    const manifestArtifact = next.artifacts.find(
      (artifact) =>
        artifact.kind === "provenance_manifest" && artifact.access.state === "available",
    );
    if (!manifestArtifact)
      throw new PreparationClientError(
        "failure",
        "The completed job did not expose its provenance manifest.",
      );
    const [report, manifest] = await Promise.all([
      client.report(next.job_id, signal),
      client.manifest(manifestArtifact.artifact_id, signal),
    ]);
    if (sequence.current !== requestSequence || binding !== runBinding) return;
    setResult({ binding: runBinding, status: next, report, manifest });
    completedBinding.current = runBinding;
    setOutdated(false);
  }

  async function poll(
    initial: ProcessingJobStatus,
    runBinding: string,
    requestSequence: number,
    signal: AbortSignal,
  ) {
    let next = initial;
    while (!terminal.has(next.state)) {
      await new Promise<void>((resolve, reject) => {
        const timer = window.setTimeout(resolve, 750);
        signal.addEventListener(
          "abort",
          () => {
            window.clearTimeout(timer);
            reject(new DOMException("Aborted", "AbortError"));
          },
          { once: true },
        );
      });
      next = await client.status(next.job_id, signal);
      if (sequence.current !== requestSequence || binding !== runBinding) return;
      setStatus(next);
    }
    if (next.state === "succeeded") await loadResult(next, runBinding, requestSequence, signal);
    else
      setMessage(
        next.safe_error_message ??
          (next.state === "cancelled" ? "Preparation was cancelled." : "Preparation failed."),
      );
  }

  async function start() {
    if (!selectedAoi || !readyToSubmit) return;
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    const requestSequence = ++sequence.current;
    const runBinding = binding;
    setMessage(null);
    setMessageKind(null);
    setResult(null);
    setOutdated(false);
    setUsable(false);
    setExclusions(false);
    onOverlayChange(null);
    setSubmitting(true);
    const request = {
      schema_version: "1.0" as const,
      scenes: scenes.map(identity),
      aoi: selectedAoi.feature.geometry,
      required_bands: [
        { role: "red", common_name: "red" as const },
        { role: "green", common_name: "green" as const },
        { role: "blue", common_name: "blue" as const },
      ],
      intended_task: (mode === "pair" ? "optical_pair" : "optical_single_scene") as
        | "optical_pair"
        | "optical_single_scene",
      processing_profile: PROFILE,
      options: {
        grid_policy: "common_utm" as const,
        target_resolution_metres: 10,
        continuous_resampling: "bilinear" as const,
        mask_resampling: "nearest" as const,
        calibration: "source_metadata" as const,
        clip_to_aoi: true as const,
        preserve_originals: true as const,
        max_output_pixels: MAX_PIXELS,
      },
    };
    try {
      const next = await client.start(
        request,
        `prep-${fingerprint(runBinding)}-${Date.now().toString(36)}`,
        controller.signal,
      );
      if (sequence.current !== requestSequence || binding !== runBinding) return;
      setSubmitting(false);
      setStatus(next);
      await poll(next, runBinding, requestSequence, controller.signal);
    } catch (error) {
      if (
        sequence.current !== requestSequence ||
        (error instanceof PreparationClientError && error.kind === "cancelled")
      )
        return;
      setSubmitting(false);
      setStatus(null);
      setMessage(error instanceof Error ? error.message : "Preparation failed.");
      setMessageKind(
        error instanceof PreparationClientError && error.kind === "blocked" ? "blocked" : "failure",
      );
    }
  }

  const displayed = result?.report;
  const noteworthy =
    displayed?.checks.filter((check) => ["warning", "fail", "unknown"].includes(check.outcome)) ??
    [];
  const coverage =
    displayed?.checks.filter((check) =>
      /coverage|cloud|shadow|missing|usable/i.test(`${check.check_id} ${check.category}`),
    ) ?? [];

  return (
    <section className="map-tool-section preparation-panel" aria-labelledby="preparation-title">
      <div className="preparation-heading">
        <div>
          <p className="panel-kicker">Scientific preparation</p>
          <h3 id="preparation-title">Prepare imagery</h3>
        </div>
        {status ? (
          <span className={`preparation-state state-${status.state}`}>{status.state}</span>
        ) : null}
      </div>
      <p>
        Clip, calibrate, mask, and place selected Sentinel-2 L2A imagery on a measured grid before
        analysis.
      </p>
      <fieldset className="preparation-mode">
        <legend>Inputs</legend>
        <label>
          <input type="radio" checked={mode === "single"} onChange={() => setMode("single")} />{" "}
          Selected scene
        </label>
        <label>
          <input
            type="radio"
            checked={mode === "pair"}
            disabled={!comparison}
            onChange={() => setMode("pair")}
          />{" "}
          Comparison pair
        </label>
      </fieldset>
      <dl className="preparation-inputs">
        <div className="preparation-definition">
          <dt>Area</dt>
          <dd>{selectedAoi?.name ?? "Select an AOI"}</dd>
        </div>
        {scenes.map((scene) => (
          <div className="preparation-definition" key={scene.key}>
            <dt>{scenes.length === 2 ? (scene === scenes[0] ? "Earlier" : "Later") : "Scene"}</dt>
            <dd title={scene.identity.itemId}>
              {scene.identity.itemId}
              <br />
              <span>{formatDate(scene.scene.acquisition.start)}</span>
            </dd>
          </div>
        ))}
      </dl>
      <details>
        <summary>Profile and limits</summary>
        <div className="preparation-detail-list">
          <p>Profile: Sentinel-2 L2A surface reflectance v1; red, green, blue.</p>
          <p>Common UTM grid at 10 m; bilinear data and nearest-neighbour categorical masks.</p>
          <p>
            Request limit: {MAX_PIXELS.toLocaleString("en-US")} output pixels. Server runtime,
            memory, and storage limits also apply.
          </p>
          <p>
            Upsampling does not create spatial detail; calibrated source values remain preserved.
          </p>
        </div>
      </details>
      <button
        className="preparation-submit"
        type="button"
        disabled={!readyToSubmit || submitting || processing}
        onClick={() => void start()}
      >
        {submitting || processing
          ? "Preparing…"
          : result || message
            ? "Retry preparation"
            : "Prepare imagery"}
      </button>
      {!readyToSubmit ? (
        <p className="preparation-guidance" role="status">
          Select an AOI and {mode === "pair" ? "assign two comparison scenes" : "select a scene"}{" "}
          first.
        </p>
      ) : null}
      {status && processing ? (
        <div className="preparation-progress" role="status" aria-live="polite">
          <strong>{status.current_stage?.replaceAll("_", " ") ?? status.state}</strong>
          {status.progress ? (
            <span>
              {status.progress.completed_units} of {status.progress.total_units} actual stages
              completed
            </span>
          ) : (
            <span>Waiting for recorded stage progress</span>
          )}
        </div>
      ) : null}
      {message ? (
        <div className={`preparation-message ${messageKind ?? "failure"}`} role="alert">
          <strong>
            {messageKind === "blocked" ? "Preparation blocked" : "Processing did not complete"}
          </strong>
          <span>{message}</span>
        </div>
      ) : null}
      {result ? (
        <div className={`preparation-result ${outdated ? "outdated" : ""}`}>
          {outdated ? (
            <div className="preparation-message stale" role="status">
              <strong>Result out of date</strong>
              <span>
                The AOI, scenes, or profile changed. Run preparation again; this result cannot
                replace the current selection.
              </span>
            </div>
          ) : null}
          <div className="preparation-readiness">
            <span className={`readiness-${displayed?.readiness}`}>
              {displayed?.readiness.replaceAll("_", " ")}
            </span>
            <div>
              <strong>Task readiness</strong>
              <p className="preparation-explanation">{displayed?.readiness_reason}</p>
            </div>
          </div>
          <h4>Measured coverage and quality</h4>
          {coverage.length ? (
            <dl className="preparation-metrics">
              {coverage.map((check) => (
                <div className="preparation-definition" key={check.check_id}>
                  <dt>{check.check_id.replaceAll("_", " ")}</dt>
                  <dd>{formatMeasured(check)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p>AOI quality statistics are unavailable.</p>
          )}
          <h4>Resolution and alignment</h4>
          <p>
            {result.manifest.scenes
              .map(
                (scene) =>
                  `${scene.output_resolution_metres} m output from ${scene.native_resolutions_metres.join("/")} m native${scene.upsampled ? " (upsampled; no new detail)" : ""}`,
              )
              .join("; ")}
            .
          </p>
          <p>
            {String(
              result.manifest.registration.explanation ??
                result.manifest.registration.state ??
                "Registration evidence unavailable.",
            )}
          </p>
          {noteworthy.length ? (
            <div className="preparation-checks">
              <h4>Warnings and unknowns</h4>
              {noteworthy.map((check) => (
                <article key={check.check_id} className={`check-${check.outcome}`}>
                  <strong>
                    {check.outcome}: {check.check_id.replaceAll("_", " ")}
                  </strong>
                  <p className="preparation-explanation">{check.reason}</p>
                  {check.corrective_action ? (
                    <p className="preparation-explanation">Action: {check.corrective_action}</p>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <p className="preparation-clear">
              No warning, failed, or unknown checks were recorded.
            </p>
          )}
          {!outdated ? (
            <fieldset className="preparation-overlays">
              <legend>Map overlays</legend>
              <label>
                <input
                  type="checkbox"
                  checked={usable}
                  onChange={(event) => setUsable(event.target.checked)}
                />{" "}
                <i className="legend-usable" /> Usable data
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={exclusions}
                  onChange={(event) => setExclusions(event.target.checked)}
                />{" "}
                <i className="legend-exclusions" /> Quality exclusions
              </label>
            </fieldset>
          ) : null}
          <details>
            <summary>Technical details and artifacts</summary>
            <p>
              Processing {result.manifest.code_version}; configuration{" "}
              {result.manifest.configuration_version}; thresholds {displayed?.threshold_version}{" "}
              (provisional engineering limits).
            </p>
            <p>
              Grid: {result.manifest.grid.crs}, {result.manifest.grid.width} ×{" "}
              {result.manifest.grid.height} pixels at{" "}
              {result.manifest.grid.resolution_metres.join(" × ")} m.
            </p>
            <p>
              <a href={preparationQualityReportUrl(result.status.job_id)}>quality report</a>
            </p>
            <div className="preparation-artifact-list">
              {result.status.artifacts.map((artifact) => (
                <p key={artifact.artifact_id}>
                  <a href={preparationArtifactUrl(artifact.artifact_id)}>
                    {artifact.kind.replaceAll("_", " ")}
                  </a>{" "}
                  · {(artifact.byte_size / 1024).toFixed(1)} KiB · SHA-256{" "}
                  {artifact.checksum_sha256.slice(0, 12)}…
                </p>
              ))}
            </div>
          </details>
          <button
            type="button"
            disabled
            title="Analysis actions will be enabled only when their backend pipeline exists."
          >
            Run future analysis (unavailable)
          </button>
        </div>
      ) : null}
    </section>
  );
}

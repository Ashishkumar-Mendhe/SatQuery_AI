"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import type { SelectedAoi } from "@/lib/aoi";
import { changeClient, type ChangeClient, type ChangeResult } from "@/lib/change-client";
import type { PreparationRequest, ProcessingJobStatus } from "@/lib/preparation-client";
import type { SelectedCatalogueScene } from "@/lib/scene-selection";

export type ChangeOverlay = {
  artifactId: string;
  bounds: [number, number, number, number];
  opacity: number;
  visible: boolean;
};
type Pair = { sceneA: SelectedCatalogueScene; sceneB: SelectedCatalogueScene };
const terminal = new Set(["succeeded", "failed", "cancelled"]);
const identity = (scene: SelectedCatalogueScene) => ({
  provider: scene.identity.providerId,
  collection: scene.identity.collectionId,
  item: scene.identity.itemId,
});
const wait = (signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
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

export function ChangeAnalysisPanel({
  selectedAoi,
  comparison,
  client = changeClient,
  onOverlayChange = () => {},
  onResultChange = () => {},
}: {
  selectedAoi: SelectedAoi | null;
  comparison: Pair | null;
  client?: ChangeClient;
  onOverlayChange?: (value: ChangeOverlay | null) => void;
  onResultChange?: (value: ChangeResult | null) => void;
}) {
  const [status, setStatus] = useState<ProcessingJobStatus | null>(null);
  const [result, setResult] = useState<ChangeResult | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [opacity, setOpacity] = useState(0.7);
  const [visible, setVisible] = useState(true);
  const controller = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  const binding = useMemo(
    () =>
      JSON.stringify({
        aoi: selectedAoi?.feature.geometry ?? null,
        scenes: comparison ? [comparison.sceneA.key, comparison.sceneB.key] : [],
        version: "8e-ui-v1",
      }),
    [selectedAoi, comparison],
  );
  const previous = useRef(binding);
  useEffect(() => {
    if (previous.current !== binding) {
      previous.current = binding;
      sequence.current += 1;
      controller.current?.abort();
      setStatus(null);
      setResult(null);
      setMessage("Inputs changed. Run change analysis again.");
      onOverlayChange(null);
      onResultChange(null);
    }
  }, [binding, onOverlayChange, onResultChange]);
  useEffect(() => {
    if (!result || !selectedAoi) onOverlayChange(null);
    else
      onOverlayChange({
        artifactId: result.classification_artifact_id,
        bounds: selectedAoi.bounds,
        opacity,
        visible,
      });
  }, [result, selectedAoi, opacity, visible, onOverlayChange]);
  useEffect(() => () => controller.current?.abort(), []);
  async function start() {
    if (!selectedAoi || !comparison) return;
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    const run = ++sequence.current;
    const runBinding = binding;
    setMessage(null);
    setResult(null);
    onResultChange(null);
    onOverlayChange(null);
    const request: PreparationRequest = {
      schema_version: "1.0",
      scenes: [identity(comparison.sceneA), identity(comparison.sceneB)],
      aoi: selectedAoi.feature.geometry,
      required_bands: [
        { role: "red", common_name: "red" },
        { role: "green", common_name: "green" },
        { role: "blue", common_name: "blue" },
      ],
      intended_task: "optical_pair",
      processing_profile: "sentinel-2-l2a-surface-reflectance-v1",
      options: {
        grid_policy: "common_utm",
        target_resolution_metres: 10,
        continuous_resampling: "bilinear",
        mask_resampling: "nearest",
        calibration: "source_metadata",
        clip_to_aoi: true,
        preserve_originals: true,
        max_output_pixels: 4_000_000,
      },
    };
    try {
      let next = await client.start(request, crypto.randomUUID(), abort.signal);
      setStatus(next);
      while (!terminal.has(next.state)) {
        await wait(abort.signal);
        next = await client.status(next.job_id, abort.signal);
        if (run !== sequence.current || runBinding !== binding) return;
        setStatus(next);
      }
      if (next.state !== "succeeded") {
        setMessage(next.safe_error_message ?? "Change analysis did not complete.");
        return;
      }
      const computed = await client.result(next.job_id, abort.signal);
      if (run !== sequence.current || runBinding !== binding) return;
      setResult(computed);
      onResultChange(computed);
      setVisible(true);
    } catch (error) {
      if (!abort.signal.aborted && run === sequence.current)
        setMessage(error instanceof Error ? error.message : "Change analysis failed.");
    }
  }
  const before = result?.sources.find((item) => item.temporal_role === "before");
  const after = result?.sources.find((item) => item.temporal_role === "after");
  return (
    <section
      className="map-tool-section change-analysis-panel"
      aria-labelledby="change-analysis-title"
    >
      <h3 id="change-analysis-title">Two-date change</h3>
      <p>
        Measures observed calibrated RGB spectral change. Cause or land-cover category is not
        determined.
      </p>
      <button
        type="button"
        disabled={!selectedAoi || !comparison || (status ? !terminal.has(status.state) : false)}
        onClick={() => void start()}
      >
        Start change analysis
      </button>
      {status && !terminal.has(status.state) ? (
        <p role="status">
          {status.current_stage?.replaceAll("_", " ") ?? status.state}
          {status.progress
            ? ` — ${status.progress.completed_units} of ${status.progress.total_units} stages`
            : ""}
        </p>
      ) : null}
      {message ? <p role="alert">{message}</p> : null}
      {result ? (
        <div className="change-result-card">
          <p>
            <strong>Dates:</strong> {new Date(before?.acquired_at ?? "").toLocaleDateString()} →{" "}
            {new Date(after?.acquired_at ?? "").toLocaleDateString()}
          </p>
          <p>
            <strong>Source pair:</strong> {before?.scene.item} → {after?.scene.item}
          </p>
          <p>
            <strong>Method:</strong> {result.method} ({result.method_version}); processing{" "}
            {result.processing_version}
          </p>
          <p>
            <strong>Changed:</strong> {result.area.changed_area_square_metres.toLocaleString()} m² (
            {result.area.changed_percent_of_joint_valid_observed_area.toFixed(2)}% of joint-valid
            observed area)
          </p>
          <p>
            <strong>Observed coverage:</strong>{" "}
            {result.area.observed_coverage_percent_of_aoi.toFixed(2)}% (
            {result.area.joint_valid_observed_area_square_metres.toLocaleString()} m²)
          </p>
          <p>
            <strong>Unknown:</strong> {result.area.unknown_area_square_metres.toLocaleString()} m² (
            {result.area.unknown_percent_of_aoi.toFixed(2)}% of AOI)
          </p>
          <p>{result.alignment_statement}</p>
          {result.warnings.map((warning) => (
            <p role="status" key={warning.code}>
              <strong>Warning:</strong> {warning.statement}
            </p>
          ))}
          <div
            role="img"
            aria-label="Change legend: red is changed, gray is unknown, and unchanged is transparent"
          >
            <span className="change-swatch changed" /> Changed{" "}
            <span className="change-swatch unknown" /> Unknown; unchanged is transparent
          </div>
          <label>
            <input
              type="checkbox"
              checked={visible}
              onChange={(event) => setVisible(event.target.checked)}
            />{" "}
            Show change overlay
          </label>
          <label>
            Overlay opacity{" "}
            <input
              type="range"
              min="0.1"
              max="1"
              step="0.1"
              value={opacity}
              onChange={(event) => setOpacity(Number(event.target.value))}
              aria-label="Change overlay opacity"
            />{" "}
            {Math.round(opacity * 100)}%
          </label>
        </div>
      ) : null}
    </section>
  );
}

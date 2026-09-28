"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { SelectedAoi } from "@/lib/aoi";
import { apiBaseUrl } from "@/lib/health-client";
import {
  opticalSarClient,
  type OpticalSarClient,
  type OpticalSarResult,
  type SarPreparation,
  type SarScene,
} from "@/lib/optical-sar-client";
import type { SarMapOverlay } from "@/lib/sar-map-layer";
import type { SelectedCatalogueScene } from "@/lib/scene-selection";

const QUESTION = "Summarize the separate optical and SAR observations.";
const terminal = new Set(["succeeded", "failed", "cancelled"]);
const sameSource = (
  left: { provider: string; collection: string; item: string },
  right: { provider: string; collection: string; item: string },
) =>
  left.provider === right.provider &&
  left.collection === right.collection &&
  left.item === right.item;
const sameAcquisition = (left: string, right: string) =>
  Number.isFinite(Date.parse(left)) && Date.parse(left) === Date.parse(right);
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

export function OpticalSarPanel({
  selectedAoi,
  selectedScene,
  onOverlayChange,
  onResultChange,
  onSarSelectionChange = () => {},
  client = opticalSarClient,
}: {
  selectedAoi: SelectedAoi | null;
  selectedScene: SelectedCatalogueScene | null;
  onOverlayChange: (overlay: SarMapOverlay | null) => void;
  onResultChange: (result: OpticalSarResult | null) => void;
  onSarSelectionChange?: (scene: SarScene | null, polarization: string | null) => void;
  client?: OpticalSarClient;
}) {
  const [startDate, setStartDate] = useState("2024-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [scenes, setScenes] = useState<SarScene[]>([]);
  const [sceneIndex, setSceneIndex] = useState(0);
  const [polarization, setPolarization] = useState("VV");
  const [preparation, setPreparation] = useState<SarPreparation | null>(null);
  const [result, setResult] = useState<OpticalSarResult | null>(null);
  const [status, setStatus] = useState("Select an AOI and Sentinel-2 scene, then find SAR scenes.");
  const [busy, setBusy] = useState(false);
  const [visible, setVisible] = useState(true);
  const [opacity, setOpacity] = useState(0.6);
  const controller = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  const scene = scenes[sceneIndex] ?? null;
  useEffect(() => {
    onSarSelectionChange(scene, scene ? polarization : null);
  }, [scene, polarization, onSarSelectionChange]);
  const discoveryBinding = useMemo(
    () =>
      JSON.stringify({
        aoi: selectedAoi?.feature.geometry ?? null,
        optical: selectedScene?.key ?? null,
        dates: [startDate, endDate],
      }),
    [selectedAoi, selectedScene, startDate, endDate],
  );
  const priorDiscovery = useRef(discoveryBinding);
  const binding = useMemo(
    () =>
      JSON.stringify({
        aoi: selectedAoi?.feature.geometry ?? null,
        optical: selectedScene?.key ?? null,
        sar: scene?.source ?? null,
        polarization,
        sarDates: [startDate, endDate],
        version: "9e-observation-v1",
      }),
    [selectedAoi, selectedScene, scene, polarization, startDate, endDate],
  );
  const priorBinding = useRef(binding);
  const bindingRef = useRef(binding);
  bindingRef.current = binding;
  const priorScene = useRef(scene?.source.item ?? null);
  useEffect(() => {
    if (priorDiscovery.current === discoveryBinding) return;
    priorDiscovery.current = discoveryBinding;
    setScenes([]);
    setSceneIndex(0);
    setPolarization("VV");
  }, [discoveryBinding]);
  useEffect(() => {
    if (priorBinding.current === binding) return;
    const initialDiscovery = priorScene.current === null && scene !== null;
    priorScene.current = scene?.source.item ?? null;
    priorBinding.current = binding;
    sequence.current += 1;
    controller.current?.abort();
    setBusy(false);
    setPreparation(null);
    setResult(null);
    onResultChange(null);
    onOverlayChange(null);
    setStatus(
      initialDiscovery
        ? `${scenes.length} SAR scene(s) found. Select a layer to view.`
        : "Inputs changed. Prepare the SAR layer and run analysis again.",
    );
  }, [binding, scene, scenes.length, onOverlayChange, onResultChange]);
  useEffect(() => {
    if (!preparation || !selectedAoi) onOverlayChange(null);
    else
      onOverlayChange({
        previewUrl: preparation.preview_url,
        preparationId: preparation.preparation_id,
        bounds: preparation.bounds,
        opacity,
        visible,
      });
  }, [preparation, selectedAoi, opacity, visible, onOverlayChange]);
  useEffect(() => () => controller.current?.abort(), []);

  function begin() {
    controller.current?.abort();
    const next = new AbortController();
    controller.current = next;
    setBusy(true);
    return { abort: next, run: ++sequence.current, input: binding };
  }
  function current(run: number, input: string, abort: AbortController) {
    return !abort.signal.aborted && run === sequence.current && input === bindingRef.current;
  }
  async function search() {
    if (!selectedAoi) return;
    const { abort, run, input } = begin();
    setStatus("Searching real INPE Sentinel-1 RTC scenes…");
    try {
      const response = await client.search(
        selectedAoi.feature.geometry,
        `${startDate}T00:00:00Z`,
        `${endDate}T23:59:59Z`,
        abort.signal,
      );
      if (!current(run, input, abort)) return;
      setScenes(response.scenes);
      setSceneIndex(0);
      setPolarization(response.scenes[0]?.polarizations[0] ?? "VV");
      setStatus(
        response.scenes.length
          ? `${response.scenes.length} SAR scene(s) found.`
          : "No accessible SAR scenes cover this AOI and date range.",
      );
    } catch (error) {
      if (current(run, input, abort))
        setStatus(error instanceof Error ? error.message : "SAR search failed.");
    } finally {
      if (run === sequence.current) setBusy(false);
    }
  }
  async function prepare() {
    if (!selectedAoi || !scene) return;
    const { abort, run, input } = begin();
    setStatus("Preparing calibrated SAR backscatter and map preview…");
    try {
      const next = await client.prepare(
        scene.source,
        selectedAoi.feature.geometry,
        polarization,
        abort.signal,
      );
      if (!current(run, input, abort)) return;
      if (
        !sameSource(next.source, scene.source) ||
        !sameAcquisition(next.acquisition_time, scene.acquisition.start) ||
        next.polarization !== polarization
      ) {
        setStatus("Prepared SAR layer does not match the current scene and polarization.");
        return;
      }
      setPreparation(next);
      setStatus("SAR layer prepared. Preview is display-scaled; analysis uses gamma-0 power.");
    } catch (error) {
      if (current(run, input, abort))
        setStatus(error instanceof Error ? error.message : "SAR preparation failed.");
    } finally {
      if (run === sequence.current) setBusy(false);
    }
  }
  async function analyze() {
    if (!selectedAoi || !selectedScene || !scene || !preparation) return;
    const { abort, run, input } = begin();
    setResult(null);
    onResultChange(null);
    setStatus("Submitting optical + SAR observation job…");
    const body = {
      schema_version: "1.0",
      request_id: crypto.randomUUID(),
      optical_scene: {
        provider: selectedScene.identity.providerId,
        collection: selectedScene.identity.collectionId,
        item: selectedScene.identity.itemId,
      },
      sar_scene: scene.source,
      aoi: selectedAoi.feature.geometry,
      polarization,
      target_resolution_metres: 20.0,
      question: QUESTION,
    };
    try {
      let job = await client.start(body, crypto.randomUUID(), abort.signal);
      while (!terminal.has(job.state)) {
        if (!current(run, input, abort)) return;
        setStatus(`Analysis ${job.state}: ${job.current_stage ?? "waiting"}`);
        await wait(abort.signal);
        job = await client.status(job.job_id, abort.signal);
      }
      if (!current(run, input, abort)) return;
      if (job.state !== "succeeded") {
        setStatus(job.safe_error_message ?? `Analysis ${job.state}.`);
        return;
      }
      const measured = await client.result(job.job_id, abort.signal);
      if (!current(run, input, abort)) return;
      const opticalSource = {
        provider: selectedScene.identity.providerId,
        collection: selectedScene.identity.collectionId,
        item: selectedScene.identity.itemId,
      };
      const opticalEvidence = measured.source_evidence.find(
        (entry) => sameSource(entry.source, opticalSource) && entry.polarization === null,
      );
      const sarEvidence = measured.source_evidence.find(
        (entry) => sameSource(entry.source, scene.source) && entry.polarization === polarization,
      );
      if (
        measured.job_id !== job.job_id ||
        measured.request_id !== body.request_id ||
        measured.processing_version !== "9e-observation-v1" ||
        measured.optical.modality !== "optical" ||
        measured.sar.modality !== "sar" ||
        !sameSource(measured.optical.source, opticalSource) ||
        !sameSource(measured.sar.source, scene.source) ||
        !sameAcquisition(measured.optical.acquired_at, selectedScene.scene.acquisition.start) ||
        !sameAcquisition(measured.sar.acquired_at, scene.acquisition.start) ||
        !opticalEvidence ||
        !sarEvidence ||
        !sameAcquisition(opticalEvidence.acquired_at, measured.optical.acquired_at) ||
        !sameAcquisition(sarEvidence.acquired_at, measured.sar.acquired_at) ||
        !measured.sar.layer.includes(polarization)
      ) {
        setStatus("Result provenance does not match the current scene selection or request.");
        return;
      }
      setResult(measured);
      onResultChange(measured);
      setStatus(
        measured.state === "limited"
          ? "Separate observations ready; joint interpretation limited."
          : "Insufficient joint evidence; inspect limitations.",
      );
    } catch (error) {
      if (current(run, input, abort))
        setStatus(error instanceof Error ? error.message : "Analysis failed.");
    } finally {
      if (run === sequence.current) setBusy(false);
    }
  }
  const supportedOptical =
    selectedScene?.identity.providerId === "earth-search" &&
    selectedScene.identity.collectionId === "sentinel-2-c1-l2a";
  return (
    <section className="map-tool-section optical-sar-panel" aria-labelledby="optical-sar-title">
      <h3 id="optical-sar-title" tabIndex={-1}>
        Optical + SAR
      </h3>
      <p>Compare source-bound observations, not sensor values or display colours.</p>
      <p>
        <strong>Optical:</strong>{" "}
        {selectedScene
          ? `Sentinel-2 L2A · ${selectedScene.scene.acquisition.start.slice(0, 10)} · ${selectedScene.identity.itemId}`
          : "Select a catalogue scene first."}
      </p>
      <div className="optical-sar-dates">
        <label>
          SAR from{" "}
          <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </label>
        <label>
          to <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </label>
      </div>
      <button
        type="button"
        disabled={!selectedScene}
        onClick={() => {
          if (!selectedScene) return;
          const centre = Date.parse(selectedScene.scene.acquisition.start);
          if (!Number.isFinite(centre)) return;
          setStartDate(new Date(centre - 30 * 86400000).toISOString().slice(0, 10));
          setEndDate(new Date(centre + 30 * 86400000).toISOString().slice(0, 10));
        }}
      >
        Use optical date ±30 days
      </button>
      <button
        type="button"
        disabled={!selectedAoi || !supportedOptical || busy || startDate > endDate}
        onClick={() => void search()}
      >
        Find SAR scenes
      </button>
      {scenes.length > 0 && (
        <>
          <label>
            SAR scene{" "}
            <select
              value={sceneIndex}
              onChange={(e) => {
                const next = Number(e.target.value);
                setSceneIndex(next);
                setPolarization(scenes[next]?.polarizations[0] ?? "VV");
              }}
            >
              {scenes.map((entry, index) => (
                <option value={index} key={entry.source.item}>
                  {entry.acquisition.start.slice(0, 10)} · {entry.source.item}
                </option>
              ))}
            </select>
          </label>
          <label>
            Polarization{" "}
            <select value={polarization} onChange={(e) => setPolarization(e.target.value)}>
              {scene?.polarizations.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <button type="button" disabled={busy} onClick={() => void prepare()}>
            View SAR layer
          </button>
        </>
      )}
      {preparation && (
        <>
          <p>
            <strong>SAR:</strong> Sentinel-1 RTC {preparation.polarization} ·{" "}
            {preparation.acquisition_time.slice(0, 10)} · {preparation.source.item}
          </p>
          <label>
            <input
              type="checkbox"
              checked={visible}
              onChange={(e) => setVisible(e.target.checked)}
            />{" "}
            Show SAR on map
          </label>
          <label>
            SAR opacity <output>{Math.round(opacity * 100)}%</output>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={opacity}
              onChange={(e) => setOpacity(Number(e.target.value))}
            />
          </label>
          <p>
            <small>
              {preparation.display_scaling} Display only; analysis uses calibrated gamma-0 power.
            </small>
          </p>
          {preparation.warnings.map((warning) => (
            <p key={warning} role="note">
              {warning}
            </p>
          ))}
          <button type="button" disabled={!supportedOptical || busy} onClick={() => void analyze()}>
            Analyze optical + SAR
          </button>
        </>
      )}
      <p role="status" aria-live="polite">
        {status}
      </p>
      {result && (
        <article className="optical-sar-result" aria-label="Optical and SAR observations">
          <h4>{result.state === "limited" ? "Limited observations" : "Insufficient evidence"}</h4>
          <p>{result.answer}</p>
          <p>
            Joint observed coverage: {result.joint_usable_percent_of_aoi.toFixed(2)}% of AOI;{" "}
            {result.joint_usable_area_square_metres.toFixed(0)} m². Time gap:{" "}
            {result.time_gap_hours.toFixed(1)} hours. Alignment: {result.alignment_state}.
          </p>
          {[result.optical, result.sar].map((item) => (
            <details key={item.modality}>
              <summary>{item.modality === "optical" ? "Optical evidence" : "SAR evidence"}</summary>
              <p>{item.statement}</p>
              <p>
                Source: {item.source.provider}/{item.source.collection}/{item.source.item};{" "}
                {item.acquired_at}.
              </p>
              <p>
                Evidence bounds: {item.evidence_bounds?.join(", ") ?? "unavailable"}{" "}
                {item.evidence_crs ?? ""}. Valid {item.valid_pixels}/{item.denominator_pixels} AOI
                cells.
              </p>
            </details>
          ))}
          <details>
            <summary>Limitations and provenance</summary>
            <ul>
              {result.limitations.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
            <p>
              Processing version: {result.processing_version}. Evidence is source-bound, not proof
              of interpretation.
            </p>
            {result.source_evidence.map((entry) => (
              <p key={entry.source.item}>
                {entry.source.item}: source version {entry.source_version ?? "unavailable"}.
                Preparation version {entry.preparation_version ?? "not applicable"}. Checksum{" "}
                {entry.checksum ?? "unavailable"}.
              </p>
            ))}
            <a href={`${apiBaseUrl()}/optical-sar/artifacts/${result.evidence_artifact_id}`}>
              Download authorized evidence record
            </a>
          </details>
        </article>
      )}
    </section>
  );
}

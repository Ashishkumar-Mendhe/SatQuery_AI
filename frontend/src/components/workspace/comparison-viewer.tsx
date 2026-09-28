"use client";

import type { Map as MapLibreMap } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import type { SelectedAoi } from "@/lib/aoi";
import {
  bindImageryLayerEvents,
  type ImageryMapState,
  syncImageryLayer,
} from "@/lib/imagery-map-layer";
import { comparisonDifferences, sharedSceneBounds } from "@/lib/scene-comparison";
import type { SelectedCatalogueScene } from "@/lib/scene-selection";
import type {
  ImageryDisplaySettings,
  TileMetadata,
  ViewerSceneIdentity,
} from "@/lib/viewer-contracts";

type Side = "A" | "B";
type ComparisonMode = "swipe" | "split" | "blink";
type SideState = {
  phase: "loading" | ImageryMapState;
  message: string;
  metadata: TileMetadata | null;
};

export interface ComparisonViewerProps {
  sceneA: SelectedCatalogueScene;
  sceneB: SelectedCatalogueScene;
  selectedAoi: SelectedAoi | null;
  tileClient: (scene: ViewerSceneIdentity, signal?: AbortSignal) => Promise<TileMetadata>;
  onClose: () => void;
}

const defaults: ImageryDisplaySettings = {
  visible: true,
  opacity: 1,
  brightness_min: 0,
  brightness_max: 1,
  contrast: 0,
  saturation: 0,
};

function identity(scene: SelectedCatalogueScene): ViewerSceneIdentity {
  return {
    provider: scene.identity.providerId,
    collection: scene.identity.collectionId,
    item: scene.identity.itemId,
  };
}

function sceneLabel(side: Side, scene: SelectedCatalogueScene, state: SideState) {
  return (
    <section className="comparison-scene-label" aria-label={`Comparison scene ${side}`}>
      <strong>
        {side} · {new Date(scene.scene.acquisition.start).toISOString()}
      </strong>
      <span>{scene.identity.itemId}</span>
      <span>{scene.identity.collectionId} · Natural colour</span>
      <span role={state.phase === "failed" ? "alert" : "status"}>{state.message}</span>
      <small>
        Platform {scene.scene.platform ?? "not reported"} · Resolution{" "}
        {scene.scene.spatial_resolution.map((value) => `${value.value} m`).join(", ") ||
          "not reported"}{" "}
        · Cloud{" "}
        {scene.scene.cloud_cover
          ? `${scene.scene.cloud_cover.percent.toFixed(1)}%`
          : "not reported"}{" "}
        · {scene.scene.processing_level ?? "Processing level not reported"}
      </small>
      {state.metadata ? (
        <small>Attribution: {state.metadata.attributions.join(" · ")}</small>
      ) : null}
    </section>
  );
}

export function ComparisonViewer({
  sceneA,
  sceneB,
  selectedAoi,
  tileClient,
  onClose,
}: ComparisonViewerProps) {
  const aRef = useRef<HTMLDivElement>(null);
  const bRef = useRef<HTMLDivElement>(null);
  const mapsRef = useRef<{ A: MapLibreMap | null; B: MapLibreMap | null }>({ A: null, B: null });
  const [metadata, setMetadata] = useState<{ A: SideState; B: SideState }>({
    A: { phase: "loading", message: "Resolving scene A…", metadata: null },
    B: { phase: "loading", message: "Resolving scene B…", metadata: null },
  });
  const [layout, setLayout] = useState<ComparisonMode>("swipe");
  const [divider, setDivider] = useState(50);
  const [blinkSide, setBlinkSide] = useState<Side>("A");
  const [blinkPlaying, setBlinkPlaying] = useState(true);
  const [reversed, setReversed] = useState(false);
  const [linked, setLinked] = useState(true);
  const [display, setDisplay] = useState({ A: defaults, B: defaults });
  const overlap = useMemo(
    () => sharedSceneBounds(sceneA.scene.bbox, sceneB.scene.bbox),
    [sceneA, sceneB],
  );
  const differences = useMemo(() => comparisonDifferences({ sceneA, sceneB }), [sceneA, sceneB]);
  const metadataA = metadata.A.metadata;
  const metadataB = metadata.B.metadata;
  const failedA = metadata.A.phase === "failed";
  const failedB = metadata.B.phase === "failed";

  useEffect(() => {
    if (layout !== "blink" || !blinkPlaying) return;
    const timer = window.setInterval(
      () => setBlinkSide((current) => (current === "A" ? "B" : "A")),
      1_200,
    );
    return () => window.clearInterval(timer);
  }, [blinkPlaying, layout]);

  useEffect(() => {
    const controller = new AbortController();
    setMetadata({
      A: { phase: "loading", message: "Resolving scene A…", metadata: null },
      B: { phase: "loading", message: "Resolving scene B…", metadata: null },
    });
    (["A", "B"] as const).forEach((side) => {
      const scene = side === "A" ? sceneA : sceneB;
      void tileClient(identity(scene), controller.signal).then(
        (value) =>
          setMetadata((current) => ({
            ...current,
            [side]: { phase: "loading", message: `Loading scene ${side} tiles…`, metadata: value },
          })),
        (error) => {
          if (!controller.signal.aborted)
            setMetadata((current) => ({
              ...current,
              [side]: {
                phase: "failed",
                message: error instanceof Error ? error.message : `Scene ${side} is unavailable.`,
                metadata: null,
              },
            }));
        },
      );
    });
    return () => controller.abort();
  }, [sceneA, sceneB, tileClient]);

  useEffect(() => {
    if (
      !overlap ||
      !aRef.current ||
      !bRef.current ||
      (!metadataA && !failedA) ||
      (!metadataB && !failedB)
    )
      return;
    let disposed = false;
    let mapA: MapLibreMap | null = null;
    let mapB: MapLibreMap | null = null;
    let resizeObserver: ResizeObserver | null = null;
    const detachImageryEvents: Array<() => void> = [];
    const syncing = { value: false };
    void import("maplibre-gl").then((maplibre) => {
      if (disposed || !aRef.current || !bRef.current) return;
      maplibre.setWorkerUrl("/maplibre-gl-worker.mjs");
      const style =
        process.env.NEXT_PUBLIC_BASEMAP_STYLE_URL?.trim() ||
        "https://tiles.openfreemap.org/styles/liberty";
      const options = {
        style,
        center: [(overlap[0] + overlap[2]) / 2, (overlap[1] + overlap[3]) / 2] as [number, number],
        zoom: 8,
        bearing: 0,
        pitch: 0,
        maxPitch: 0,
        attributionControl: false as const,
        renderWorldCopies: false,
      };
      mapA = new maplibre.Map({ ...options, container: aRef.current });
      mapB = new maplibre.Map({ ...options, container: bRef.current });
      mapsRef.current = { A: mapA, B: mapB };
      const sync = (source: MapLibreMap, target: MapLibreMap) => {
        if (syncing.value) return;
        syncing.value = true;
        target.jumpTo({
          center: source.getCenter(),
          zoom: source.getZoom(),
          bearing: source.getBearing(),
          pitch: source.getPitch(),
        });
        syncing.value = false;
      };
      mapA.on("move", () => mapB && sync(mapA as MapLibreMap, mapB));
      mapB.on("move", () => mapA && sync(mapB as MapLibreMap, mapA));
      ([mapA, mapB] as MapLibreMap[]).forEach((map, index) => {
        const side = index === 0 ? "A" : "B";
        detachImageryEvents.push(
          bindImageryLayerEvents(map, (phase, message) =>
            setMetadata((current) => ({
              ...current,
              [side]: { ...current[side], phase, message: `Scene ${side}: ${message}` },
            })),
          ),
        );
        map.on("load", () => {
          const side = index === 0 ? "A" : "B";
          const sideMetadata = side === "A" ? metadataA : metadataB;
          try {
            if (sideMetadata) syncImageryLayer(map, sideMetadata, defaults);
            if (selectedAoi) {
              map.addSource("satquery-comparison-aoi", {
                type: "geojson",
                data: selectedAoi.feature,
              });
              map.addLayer({
                id: "satquery-aoi-polygon",
                type: "fill",
                source: "satquery-comparison-aoi",
                paint: { "fill-color": "#42a5f5", "fill-opacity": 0.14 },
              });
              map.addLayer({
                id: "satquery-comparison-aoi-outline",
                type: "line",
                source: "satquery-comparison-aoi",
                paint: { "line-color": "#42a5f5", "line-width": 3 },
              });
            }
          } catch (error) {
            setMetadata((current) => ({
              ...current,
              [side]: {
                ...current[side],
                phase: "failed",
                message:
                  error instanceof Error
                    ? `Scene ${side}: ${error.message}`
                    : `Scene ${side} could not be added to the map.`,
              },
            }));
          }
          map.fitBounds(
            [
              [overlap[0], overlap[1]],
              [overlap[2], overlap[3]],
            ],
            { padding: 36, duration: 0 },
          );
        });
      });
      resizeObserver = new ResizeObserver(() => {
        mapA?.resize();
        mapB?.resize();
      });
      resizeObserver.observe(aRef.current);
      resizeObserver.observe(bRef.current);
    });
    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      detachImageryEvents.forEach((detach) => {
        detach();
      });
      mapsRef.current = { A: null, B: null };
      mapA?.remove();
      mapB?.remove();
    };
  }, [failedA, failedB, metadataA, metadataB, overlap, selectedAoi]);

  useEffect(() => {
    (["A", "B"] as const).forEach((side) => {
      const map = mapsRef.current[side];
      if (!map?.getLayer("satquery-imagery-raster")) return;
      map.setPaintProperty("satquery-imagery-raster", "raster-opacity", display[side].opacity);
    });
  }, [display]);

  function setOpacity(side: Side, opacity: number) {
    setDisplay((current) =>
      linked
        ? { A: { ...current.A, opacity }, B: { ...current.B, opacity } }
        : { ...current, [side]: { ...current[side], opacity } },
    );
  }

  return (
    <section
      className={`comparison-viewer comparison-${layout} ${reversed ? "comparison-reversed" : ""}`}
      aria-label="Two-date imagery comparison"
    >
      <header>
        <div>
          <p className="panel-kicker">Visual comparison</p>
          <h2>Two acquisition dates</h2>
        </div>
        <div className="comparison-actions">
          <fieldset className="comparison-mode" aria-label="Comparison mode">
            <legend className="sr-only">Comparison mode</legend>
            {(["swipe", "split", "blink"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                aria-pressed={layout === mode}
                onClick={() => {
                  setLayout(mode);
                  if (mode === "blink") {
                    setBlinkSide("A");
                    setBlinkPlaying(true);
                  }
                }}
              >
                {mode[0].toUpperCase() + mode.slice(1)}
              </button>
            ))}
          </fieldset>
          <button type="button" onClick={() => setReversed((v) => !v)}>
            Swap display sides
          </button>
          <button type="button" onClick={onClose}>
            Leave comparison
          </button>
        </div>
      </header>
      {!overlap ? (
        <div className="comparison-unavailable" role="alert">
          These scenes do not share a viewable geographic area. Comparison imagery was not opened.
        </div>
      ) : (
        <div className="comparison-visuals">
          <div className="comparison-labels">
            {sceneLabel("A", sceneA, metadata.A)}
            {sceneLabel("B", sceneB, metadata.B)}
          </div>
          <div className="comparison-map-frame">
            <div
              className="comparison-map comparison-map-a"
              ref={aRef}
              style={
                layout === "swipe" && reversed
                  ? { clipPath: `inset(0 0 0 ${divider}%)` }
                  : layout === "blink" && blinkSide !== "A"
                    ? { visibility: "hidden" }
                    : undefined
              }
            />
            <div
              className="comparison-map comparison-map-b"
              ref={bRef}
              style={
                layout === "swipe" && !reversed
                  ? { clipPath: `inset(0 0 0 ${divider}%)` }
                  : layout === "blink" && blinkSide !== "B"
                    ? { visibility: "hidden" }
                    : undefined
              }
            />
            {layout === "swipe" ? (
              <label className="comparison-divider" style={{ left: `${divider}%` }}>
                Comparison divider{" "}
                <input
                  aria-label="Comparison swipe divider"
                  type="range"
                  min="5"
                  max="95"
                  value={divider}
                  onChange={(event) => setDivider(Number(event.currentTarget.value))}
                />
              </label>
            ) : null}
            {layout === "blink" ? (
              <div className="comparison-blink-controls">
                <span role="status">Showing scene {blinkSide}</span>
                <button type="button" onClick={() => setBlinkPlaying((current) => !current)}>
                  {blinkPlaying ? "Pause blink" : "Resume blink"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setBlinkPlaying(false);
                    setBlinkSide((current) => (current === "A" ? "B" : "A"));
                  }}
                >
                  Show next scene
                </button>
              </div>
            ) : null}
          </div>
        </div>
      )}
      <fieldset className="comparison-display">
        <legend>Display settings</legend>
        <label>
          <input
            type="checkbox"
            checked={linked}
            onChange={(event) => setLinked(event.currentTarget.checked)}
          />{" "}
          Link comparable settings
        </label>
        {(["A", "B"] as const).map((side) => (
          <label key={side}>
            Scene {side} opacity <output>{Math.round(display[side].opacity * 100)}%</output>
            <input
              aria-label={`Scene ${side} opacity`}
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={display[side].opacity}
              onChange={(event) => setOpacity(side, Number(event.currentTarget.value))}
            />
          </label>
        ))}
      </fieldset>
      <div className="comparison-caveat">
        <strong>Visual comparison only.</strong> Correct placement does not establish scientific
        co-registration. Uncovered pixels remain transparent.{" "}
        {differences.length
          ? differences.join(" ")
          : "Reported resolution and processing level match; cloud metadata may still affect appearance."}{" "}
        Automated change maps, percentages, and confidence are unavailable.
      </div>
    </section>
  );
}

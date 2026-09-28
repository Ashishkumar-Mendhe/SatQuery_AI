"use client";

import {
  forwardRef,
  type Ref,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

import type { AoiBounds, AoiSource, SelectedAoi } from "@/lib/aoi";
import { createSelectedAoi } from "@/lib/aoi";
import {
  applyImageryDisplaySettings,
  bindImageryLayerEvents,
  IMAGERY_LAYER_ID,
  IMAGERY_SOURCE_ID,
  type ImageryMapState,
  syncImageryLayer,
} from "@/lib/imagery-map-layer";
import {
  type InferenceGroundingOverlay,
  syncInferenceGroundingLayer,
} from "@/lib/inference-grounding-map-layer";
import {
  PREPARATION_MASK_SOURCE_PREFIX,
  syncPreparationMaskLayers,
} from "@/lib/preparation-mask-map-layer";
import { bindSceneFootprintInteractions, syncSceneFootprintLayers } from "@/lib/scene-map-layers";
import type { CatalogueSceneContext, SelectedCatalogueScene } from "@/lib/scene-selection";
import type { ImageryDisplaySettings, TileMetadata, ViewerCamera } from "@/lib/viewer-contracts";
import type { PreparationMaskOverlay } from "./preparation-panel";
import type { ChangeOverlay } from "./change-analysis-panel";
import { syncChangeLayer } from "@/lib/change-map-layer";
import { SAR_IMAGE_SOURCE_ID, syncSarLayer, type SarMapOverlay } from "@/lib/sar-map-layer";

import "maplibre-gl/dist/maplibre-gl.css";
import "@watergis/maplibre-gl-terradraw/dist/maplibre-gl-terradraw.css";

export type MapInteraction = "idle" | "rectangle" | "polygon" | "edit";
export type MapLifecycle = "loading" | "ready" | "error" | "unsupported";

export interface MapCanvasHandle {
  startDrawing: (mode: "rectangle" | "polygon") => void;
  cancelDrawing: () => void;
  beginEdit: () => void;
  finishEdit: () => void;
  cancelEdit: () => void;
  fitSelectedAoi: () => void;
  prepareImageryView: (bounds: AoiBounds) => void;
  fitScene: (bounds: AoiBounds) => void;
  navigateTo: (longitude: number, latitude: number) => void;
  navigateToBounds: (bounds: AoiBounds) => void;
  retry: () => void;
  getCamera: () => ViewerCamera | null;
  restoreCamera: (camera: ViewerCamera) => void;
}

export interface MapCanvasProps {
  selectedAoi: SelectedAoi | null;
  sceneContext: CatalogueSceneContext | null;
  selectedScene: SelectedCatalogueScene | null;
  hoveredSceneKey: string | null;
  imageryMetadata: TileMetadata | null;
  imageryDisplaySettings: ImageryDisplaySettings;
  preparationMaskOverlay?: PreparationMaskOverlay | null;
  changeOverlay?: ChangeOverlay | null;
  sarOverlay?: SarMapOverlay | null;
  inferenceGroundingOverlay?: InferenceGroundingOverlay | null;
  onCommitAoi: (aoi: SelectedAoi) => boolean;
  onPreviewAoi: (aoi: SelectedAoi | null) => void;
  onInteractionChange: (interaction: MapInteraction) => void;
  onLifecycleChange: (lifecycle: MapLifecycle, message: string) => void;
  onCoordinateChange: (coordinates: [number, number]) => void;
  onGeometryError: (message: string) => void;
  onSceneHover: (sceneKey: string | null) => void;
  onSceneSelect: (sceneKey: string) => void;
  onImageryStateChange: (state: ImageryMapState, message: string) => void;
  onCameraChange?: (camera: ViewerCamera) => void;
}

type TerraDrawControl = import("@watergis/maplibre-gl-terradraw").MaplibreTerradrawControl;
type TerraDrawInstance = NonNullable<ReturnType<TerraDrawControl["getTerraDrawInstance"]>>;
type MapLibreMap = import("maplibre-gl").Map;

const ACTIVE_FEATURE_ID = "00000000-0000-4000-8000-000000000003";
const DEFAULT_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";
const DEFAULT_CENTER: [number, number] = [78.9629, 20.5937];

function resolveStyleUrl(): string {
  const configured = process.env.NEXT_PUBLIC_BASEMAP_STYLE_URL?.trim() || DEFAULT_STYLE_URL;
  const parsed = new URL(configured);
  if (parsed.username || parsed.password)
    throw new Error("Basemap URLs must not contain credentials.");
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    throw new Error("The basemap style URL must use HTTP or HTTPS.");
  }
  return parsed.toString();
}

function asTerraFeature(aoi: SelectedAoi) {
  return {
    type: "Feature" as const,
    id: ACTIVE_FEATURE_ID,
    geometry: aoi.feature.geometry,
    properties: {
      mode: "polygon",
      name: aoi.name,
      source: aoi.source,
    },
  };
}

function MapCanvasInner(
  {
    selectedAoi,
    sceneContext,
    selectedScene,
    hoveredSceneKey,
    imageryMetadata,
    imageryDisplaySettings,
    preparationMaskOverlay = null,
    changeOverlay = null,
    sarOverlay = null,
    inferenceGroundingOverlay = null,
    onCommitAoi,
    onPreviewAoi,
    onInteractionChange,
    onLifecycleChange,
    onCoordinateChange,
    onGeometryError,
    onSceneHover,
    onSceneSelect,
    onImageryStateChange,
    onCameraChange = () => {},
  }: MapCanvasProps,
  ref: Ref<MapCanvasHandle>,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const drawControlRef = useRef<TerraDrawControl | null>(null);
  const drawRef = useRef<TerraDrawInstance | null>(null);
  const selectedAoiRef = useRef(selectedAoi);
  const sceneContextRef = useRef(sceneContext);
  const selectedSceneRef = useRef(selectedScene);
  const hoveredSceneKeyRef = useRef(hoveredSceneKey);
  const imageryMetadataRef = useRef(imageryMetadata);
  const imageryDisplaySettingsRef = useRef(imageryDisplaySettings);
  const preparationMaskOverlayRef = useRef(preparationMaskOverlay);
  const changeOverlayRef = useRef(changeOverlay);
  const sarOverlayRef = useRef(sarOverlay);
  const inferenceGroundingOverlayRef = useRef(inferenceGroundingOverlay);
  const imageryDisplayTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const syncedImageryTileSetRef = useRef<string | null>(null);
  const interactionRef = useRef<MapInteraction>("idle");
  const editOriginalRef = useRef<SelectedAoi | null>(null);
  const suppressDrawEventsRef = useRef(false);
  const editPreviewTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const coordinateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const callbacksRef = useRef({
    onCommitAoi,
    onPreviewAoi,
    onInteractionChange,
    onLifecycleChange,
    onCoordinateChange,
    onGeometryError,
    onSceneHover,
    onSceneSelect,
    onImageryStateChange,
    onCameraChange,
  });
  const [lifecycleKey, setLifecycleKey] = useState(0);

  selectedAoiRef.current = selectedAoi;
  sceneContextRef.current = sceneContext;
  selectedSceneRef.current = selectedScene;
  hoveredSceneKeyRef.current = hoveredSceneKey;
  imageryMetadataRef.current = imageryMetadata;
  imageryDisplaySettingsRef.current = imageryDisplaySettings;
  preparationMaskOverlayRef.current = preparationMaskOverlay;
  changeOverlayRef.current = changeOverlay;
  sarOverlayRef.current = sarOverlay;
  inferenceGroundingOverlayRef.current = inferenceGroundingOverlay;
  callbacksRef.current = {
    onCommitAoi,
    onPreviewAoi,
    onInteractionChange,
    onLifecycleChange,
    onCoordinateChange,
    onGeometryError,
    onSceneHover,
    onSceneSelect,
    onImageryStateChange,
    onCameraChange,
  };

  const setInteraction = useCallback((interaction: MapInteraction) => {
    interactionRef.current = interaction;
    callbacksRef.current.onInteractionChange(interaction);
  }, []);

  const syncSelectedAoi = useCallback(() => {
    const draw = drawRef.current;
    if (!draw?.enabled) {
      return;
    }
    suppressDrawEventsRef.current = true;
    try {
      draw.setMode("default");
      draw.clear();
      const current = selectedAoiRef.current;
      if (current) {
        const result = draw.addFeatures([asTerraFeature(current)]);
        if (result.some((entry) => !entry.valid)) {
          callbacksRef.current.onGeometryError(
            "The map editor could not display the selected AOI.",
          );
        }
      }
    } finally {
      suppressDrawEventsRef.current = false;
    }
  }, []);

  const syncSceneFootprints = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    syncSceneFootprintLayers(
      map,
      sceneContextRef.current,
      selectedSceneRef.current,
      hoveredSceneKeyRef.current,
    );
  }, []);

  const syncImagery = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const metadata = imageryMetadataRef.current;
    if (metadata?.expires_at && Date.parse(metadata.expires_at) <= Date.now()) {
      syncImageryLayer(map, null);
      syncedImageryTileSetRef.current = null;
      callbacksRef.current.onImageryStateChange(
        "expired",
        "Imagery tile access expired. Retry to request fresh access.",
      );
      return;
    }
    if (
      metadata &&
      syncedImageryTileSetRef.current === metadata.tile_set_id &&
      map.getSource(IMAGERY_SOURCE_ID) &&
      map.getLayer(IMAGERY_LAYER_ID)
    ) {
      return;
    }
    syncImageryLayer(map, metadata, imageryDisplaySettingsRef.current);
    syncedImageryTileSetRef.current = metadata?.tile_set_id ?? null;
  }, []);

  const syncPreparationMasks = useCallback(() => {
    const map = mapRef.current;
    if (map) syncPreparationMaskLayers(map, preparationMaskOverlayRef.current);
  }, []);

  const syncChange = useCallback(() => {
    const map = mapRef.current;
    if (map) syncChangeLayer(map, changeOverlayRef.current);
  }, []);

  const syncSar = useCallback(() => {
    const map = mapRef.current;
    if (map) syncSarLayer(map, sarOverlayRef.current);
  }, []);

  const syncInferenceGrounding = useCallback(() => {
    const map = mapRef.current;
    if (map) syncInferenceGroundingLayer(map, inferenceGroundingOverlayRef.current);
  }, []);

  const readActiveFeature = useCallback((source: AoiSource): SelectedAoi => {
    const feature = drawRef.current?.getSnapshotFeature(ACTIVE_FEATURE_ID);
    if (feature?.geometry.type !== "Polygon") {
      throw new Error("The active AOI geometry is unavailable.");
    }
    return createSelectedAoi(
      { type: "Feature", properties: {}, geometry: feature.geometry },
      source,
      selectedAoiRef.current?.name,
    );
  }, []);

  useImperativeHandle(
    ref,
    () => ({
      startDrawing(mode) {
        const draw = drawRef.current;
        if (!draw?.enabled) {
          callbacksRef.current.onGeometryError("The map editor is not ready yet.");
          return;
        }
        callbacksRef.current.onPreviewAoi(null);
        draw.setMode(mode);
        setInteraction(mode);
      },
      cancelDrawing() {
        const draw = drawRef.current;
        if (draw?.enabled) draw.setMode("default");
        setInteraction("idle");
        callbacksRef.current.onPreviewAoi(null);
        if (draw?.enabled) queueMicrotask(syncSelectedAoi);
      },
      beginEdit() {
        const draw = drawRef.current;
        if (!selectedAoiRef.current || !draw?.enabled) {
          return;
        }
        editOriginalRef.current = selectedAoiRef.current;
        draw.setMode("select");
        draw.selectFeature(ACTIVE_FEATURE_ID);
        setInteraction("edit");
      },
      finishEdit() {
        if (interactionRef.current !== "edit") {
          return;
        }
        try {
          const edited = readActiveFeature(selectedAoiRef.current?.source ?? "polygon");
          if (!callbacksRef.current.onCommitAoi(edited)) return;
          selectedAoiRef.current = edited;
          callbacksRef.current.onPreviewAoi(null);
          editOriginalRef.current = null;
          drawRef.current?.setMode("default");
          setInteraction("idle");
        } catch (error) {
          callbacksRef.current.onGeometryError(
            error instanceof Error ? error.message : "The edited AOI is invalid.",
          );
          selectedAoiRef.current = editOriginalRef.current;
          callbacksRef.current.onPreviewAoi(null);
          syncSelectedAoi();
          setInteraction("idle");
        }
      },
      cancelEdit() {
        if (interactionRef.current !== "edit") {
          return;
        }
        selectedAoiRef.current = editOriginalRef.current;
        callbacksRef.current.onPreviewAoi(null);
        editOriginalRef.current = null;
        syncSelectedAoi();
        setInteraction("idle");
      },
      fitSelectedAoi() {
        const aoi = selectedAoiRef.current;
        if (aoi) {
          mapRef.current?.fitBounds(
            [
              [aoi.bounds[0], aoi.bounds[1]],
              [aoi.bounds[2], aoi.bounds[3]],
            ],
            { padding: 72, maxZoom: 13, duration: 700 },
          );
        }
      },
      prepareImageryView(bounds) {
        mapRef.current?.fitBounds(
          [
            [bounds[0], bounds[1]],
            [bounds[2], bounds[3]],
          ],
          { padding: 72, maxZoom: 8, duration: 0 },
        );
      },
      fitScene(bounds) {
        mapRef.current?.fitBounds(
          [
            [bounds[0], bounds[1]],
            [bounds[2], bounds[3]],
          ],
          { padding: 72, maxZoom: 12, duration: 700 },
        );
      },
      navigateTo(longitude, latitude) {
        mapRef.current?.flyTo({ center: [longitude, latitude], zoom: 10, duration: 900 });
      },
      navigateToBounds(bounds) {
        mapRef.current?.fitBounds(
          [
            [bounds[0], bounds[1]],
            [bounds[2], bounds[3]],
          ],
          { padding: 72, maxZoom: 13, duration: 900 },
        );
      },
      retry() {
        setInteraction("idle");
        callbacksRef.current.onPreviewAoi(null);
        setLifecycleKey((current) => current + 1);
      },
      getCamera() {
        const map = mapRef.current;
        if (!map) return null;
        const center = map.getCenter();
        return {
          center: [center.lng, center.lat],
          zoom: map.getZoom(),
          bearing: map.getBearing(),
          pitch: map.getPitch(),
        };
      },
      restoreCamera(camera) {
        mapRef.current?.jumpTo(camera);
      },
    }),
    [readActiveFeature, setInteraction, syncSelectedAoi],
  );

  useEffect(() => {
    // Retry deliberately creates a fresh map, even when provider configuration is unchanged.
    containerRef.current?.setAttribute("data-map-attempt", String(lifecycleKey));
    let disposed = false;
    const container = containerRef.current;
    if (!container) {
      return;
    }
    callbacksRef.current.onLifecycleChange("loading", "Loading the basemap…");

    let resizeObserver: ResizeObserver | null = null;
    let draw: TerraDrawInstance | null = null;
    let drawControl: TerraDrawControl | null = null;
    let map: MapLibreMap | null = null;
    let detachDrawListeners = () => {};
    let detachSceneListeners = () => {};
    let detachImageryListeners = () => {};
    let styleReadyTimer: ReturnType<typeof setInterval> | null = null;
    const loadingTimer = setTimeout(() => {
      if (!disposed)
        callbacksRef.current.onLifecycleChange(
          "error",
          "Map loading timed out. Check the connection and retry.",
        );
    }, 20_000);

    async function createMap(container: HTMLDivElement) {
      try {
        const maplibre = await import("maplibre-gl");
        const terraDraw = await import("@watergis/maplibre-gl-terradraw");
        if (disposed) {
          return;
        }
        const probe = document.createElement("canvas");
        const context = probe.getContext("webgl2");
        if (!context) {
          clearTimeout(loadingTimer);
          callbacksRef.current.onLifecycleChange(
            "unsupported",
            "This browser cannot provide the WebGL features required by the map.",
          );
          return;
        }
        context.getExtension("WEBGL_lose_context")?.loseContext();

        const style = resolveStyleUrl();
        maplibre.setWorkerUrl("/maplibre-gl-worker.mjs");
        map = new maplibre.Map({
          container,
          style,
          center: DEFAULT_CENTER,
          zoom: 3.5,
          bearing: 0,
          pitch: 0,
          maxPitch: 0,
          attributionControl: false,
          cooperativeGestures: true,
          renderWorldCopies: false,
        });
        mapRef.current = map;
        map.addControl(
          new maplibre.NavigationControl({
            showCompass: true,
            showZoom: true,
            visualizePitch: false,
          }),
          "top-right",
        );
        map.addControl(new maplibre.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-left");
        map.addControl(
          new maplibre.AttributionControl({
            compact: true,
            customAttribution:
              style === DEFAULT_STYLE_URL
                ? '<a href="https://openfreemap.org/" target="_blank" rel="noreferrer">OpenFreeMap</a> · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors</a>'
                : undefined,
          }),
          "bottom-right",
        );

        class WorkspaceDrawControl extends terraDraw.MaplibreTerradrawControl {
          onAdd(map: MapLibreMap) {
            const control = super.onAdd(map);
            // React owns modes; global shortcuts must not bypass committed/draft state.
            this.modeKeyboardShortcutController?.destroy();
            control.hidden = true;
            return control;
          }
        }
        drawControl = new WorkspaceDrawControl({
          modes: ["rectangle", "polygon", "select"],
          open: false,
          showDeleteConfirmation: false,
          adapterOptions: { coordinatePrecision: 15, prefixId: "satquery-aoi" },
          keyboardShortcuts: {},
        });
        drawControlRef.current = drawControl;
        map.addControl(drawControl, "top-left");
        draw = drawControl.getTerraDrawInstance() ?? null;
        drawRef.current = draw;
        const internalControl = container
          .querySelector(".maplibregl-terradraw-add-rectangle-button")
          ?.closest<HTMLElement>(".maplibregl-ctrl-group");
        if (internalControl) {
          internalControl.hidden = true;
        }

        const handleFinish = (id: string | number) => {
          if (disposed || suppressDrawEventsRef.current) {
            return;
          }
          const source = interactionRef.current;
          if (source !== "rectangle" && source !== "polygon") {
            return;
          }
          const feature = draw?.getSnapshotFeature(id);
          try {
            if (feature?.geometry.type !== "Polygon") {
              throw new Error("The completed drawing did not produce a Polygon.");
            }
            const committed = createSelectedAoi(
              { type: "Feature", properties: {}, geometry: feature.geometry },
              source,
            );
            if (callbacksRef.current.onCommitAoi(committed)) {
              selectedAoiRef.current = committed;
            }
            callbacksRef.current.onPreviewAoi(null);
            setInteraction("idle");
            queueMicrotask(syncSelectedAoi);
          } catch (error) {
            if (draw?.hasFeature(id)) {
              draw.removeFeatures([id]);
            }
            callbacksRef.current.onGeometryError(
              error instanceof Error ? error.message : "The completed drawing is invalid.",
            );
            setInteraction("idle");
            queueMicrotask(syncSelectedAoi);
          }
        };
        const handleChange = () => {
          if (disposed || suppressDrawEventsRef.current || interactionRef.current !== "edit") {
            return;
          }
          if (editPreviewTimerRef.current) {
            clearTimeout(editPreviewTimerRef.current);
          }
          editPreviewTimerRef.current = setTimeout(() => {
            if (disposed || interactionRef.current !== "edit") return;
            try {
              callbacksRef.current.onPreviewAoi(
                readActiveFeature(selectedAoiRef.current?.source ?? "polygon"),
              );
            } catch (error) {
              callbacksRef.current.onPreviewAoi(null);
              callbacksRef.current.onGeometryError(
                error instanceof Error ? error.message : "The edited AOI is invalid.",
              );
            }
          }, 120);
        };
        draw?.on("finish", handleFinish);
        draw?.on("change", handleChange);
        detachDrawListeners = () => {
          draw?.off("finish", handleFinish);
          draw?.off("change", handleChange);
        };

        const handleStyleLoad = () => {
          syncImagery();
          syncPreparationMasks();
          syncChange();
          syncSar();
          syncInferenceGrounding();
          syncSceneFootprints();
          if (interactionRef.current === "idle") syncSelectedAoi();
          handleMapLoad();
        };
        const detachFootprintInteractions = bindSceneFootprintInteractions(
          map,
          (sceneKey) => callbacksRef.current.onSceneHover(sceneKey),
          (sceneKey) => callbacksRef.current.onSceneSelect(sceneKey),
        );
        map.on("style.load", handleStyleLoad);
        detachSceneListeners = () => {
          detachFootprintInteractions();
          map?.off("style.load", handleStyleLoad);
        };
        detachImageryListeners = bindImageryLayerEvents(map, (state, message) =>
          callbacksRef.current.onImageryStateChange(state, message),
        );

        let mapReadyNotified = false;
        const handleMapLoad = () => {
          if (disposed || mapReadyNotified) return;
          mapReadyNotified = true;
          if (styleReadyTimer) clearInterval(styleReadyTimer);
          styleReadyTimer = null;
          clearTimeout(loadingTimer);
          callbacksRef.current.onLifecycleChange("ready", "Map ready");
          syncImagery();
          syncPreparationMasks();
          syncChange();
          syncSar();
          syncInferenceGrounding();
          syncSceneFootprints();
          syncSelectedAoi();
          const current = selectedAoiRef.current;
          if (current)
            map?.fitBounds(
              [
                [current.bounds[0], current.bounds[1]],
                [current.bounds[2], current.bounds[3]],
              ],
              { padding: 72, maxZoom: 13, duration: 0 },
            );
        };
        map.on("load", handleMapLoad);
        if (map.isStyleLoaded()) queueMicrotask(handleMapLoad);
        else {
          // A very fast local style can finish between map construction and listener setup.
          styleReadyTimer = setInterval(() => {
            if (map?.isStyleLoaded()) handleMapLoad();
          }, 50);
        }
        map.on("error", (event) => {
          if (disposed) return;
          const sourceId = (event as ErrorEvent & { sourceId?: string }).sourceId;
          if (
            sourceId === IMAGERY_SOURCE_ID ||
            sourceId?.startsWith(PREPARATION_MASK_SOURCE_PREFIX) ||
            sourceId === SAR_IMAGE_SOURCE_ID
          )
            return;
          callbacksRef.current.onLifecycleChange(
            "error",
            "A basemap resource failed to load. Check the connection or retry the map.",
          );
        });
        map.on("moveend", () => {
          if (!map || disposed) return;
          const center = map.getCenter();
          callbacksRef.current.onCoordinateChange([center.lng, center.lat]);
          callbacksRef.current.onCameraChange({
            center: [center.lng, center.lat],
            zoom: map.getZoom(),
            bearing: map.getBearing(),
            pitch: map.getPitch(),
          });
        });
        map.on("mousemove", (event) => {
          if (coordinateTimerRef.current) {
            return;
          }
          coordinateTimerRef.current = setTimeout(() => {
            coordinateTimerRef.current = null;
            callbacksRef.current.onCoordinateChange([event.lngLat.lng, event.lngLat.lat]);
          }, 100);
        });
        resizeObserver = new ResizeObserver(() => map?.resize());
        resizeObserver.observe(container);
      } catch (error) {
        if (disposed) return;
        clearTimeout(loadingTimer);
        callbacksRef.current.onLifecycleChange(
          "error",
          error instanceof Error ? `Map could not start: ${error.message}` : "Map could not start.",
        );
      }
    }

    void createMap(container);
    return () => {
      disposed = true;
      clearTimeout(loadingTimer);
      if (styleReadyTimer) clearInterval(styleReadyTimer);
      if (editPreviewTimerRef.current) {
        clearTimeout(editPreviewTimerRef.current);
      }
      if (coordinateTimerRef.current) {
        clearTimeout(coordinateTimerRef.current);
      }
      if (imageryDisplayTimerRef.current) {
        clearTimeout(imageryDisplayTimerRef.current);
      }
      coordinateTimerRef.current = null;
      editPreviewTimerRef.current = null;
      imageryDisplayTimerRef.current = null;
      resizeObserver?.disconnect();
      detachDrawListeners();
      detachSceneListeners();
      detachImageryListeners();
      if (map && drawControl && map.hasControl(drawControl)) {
        map.removeControl(drawControl);
      }
      map?.remove();
      drawRef.current = null;
      drawControlRef.current = null;
      mapRef.current = null;
      syncedImageryTileSetRef.current = null;
    };
  }, [
    lifecycleKey,
    readActiveFeature,
    setInteraction,
    syncImagery,
    syncInferenceGrounding,
    syncPreparationMasks,
    syncChange,
    syncSar,
    syncSceneFootprints,
    syncSelectedAoi,
  ]);

  useEffect(() => {
    selectedAoiRef.current = selectedAoi;
    if (interactionRef.current === "idle") {
      syncSelectedAoi();
    }
  }, [selectedAoi, syncSelectedAoi]);

  useEffect(() => {
    sceneContextRef.current = sceneContext;
    selectedSceneRef.current = selectedScene;
    hoveredSceneKeyRef.current = hoveredSceneKey;
    syncSceneFootprints();
  }, [hoveredSceneKey, sceneContext, selectedScene, syncSceneFootprints]);

  useEffect(() => {
    imageryMetadataRef.current = imageryMetadata;
    syncImagery();
  }, [imageryMetadata, syncImagery]);

  useEffect(() => {
    preparationMaskOverlayRef.current = preparationMaskOverlay;
    syncPreparationMasks();
  }, [preparationMaskOverlay, syncPreparationMasks]);

  useEffect(() => {
    changeOverlayRef.current = changeOverlay;
    syncChange();
  }, [changeOverlay, syncChange]);

  useEffect(() => {
    sarOverlayRef.current = sarOverlay;
    syncSar();
  }, [sarOverlay, syncSar]);

  useEffect(() => {
    inferenceGroundingOverlayRef.current = inferenceGroundingOverlay;
    syncInferenceGrounding();
  }, [inferenceGroundingOverlay, syncInferenceGrounding]);

  useEffect(() => {
    imageryDisplaySettingsRef.current = imageryDisplaySettings;
    if (imageryDisplayTimerRef.current) clearTimeout(imageryDisplayTimerRef.current);
    imageryDisplayTimerRef.current = setTimeout(() => {
      const map = mapRef.current;
      if (map?.isStyleLoaded()) applyImageryDisplaySettings(map, imageryDisplaySettingsRef.current);
    }, 120);
    return () => {
      if (imageryDisplayTimerRef.current) clearTimeout(imageryDisplayTimerRef.current);
    };
  }, [imageryDisplaySettings]);

  return <section className="map-canvas" ref={containerRef} aria-label="Interactive Earth map" />;
}

export const MapCanvas = forwardRef(MapCanvasInner);

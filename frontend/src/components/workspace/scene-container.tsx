"use client";

import {
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { Icon } from "@/components/icon";
import {
  type ImageryDiscoveryClient,
  ImageryDiscoveryPanel,
} from "@/components/workspace/imagery-discovery-panel";
import { buildAcquisitionTimeline } from "@/lib/acquisition-timeline";
import {
  AOI_MAX_FILE_BYTES,
  type AoiBounds,
  createAoiFromBounds,
  formatAoiArea,
  formatAoiBounds,
  getMapDisplayIssue,
  parseGeoJsonText,
  type SelectedAoi,
  serializeAoi,
} from "@/lib/aoi";
import {
  getGeocoderProviderName,
  isGeocoderConfigured,
  type PlaceSearchResult,
  searchPlaces,
} from "@/lib/geocoder";
import { DEFAULT_IMAGERY_DISPLAY_SETTINGS, type ImageryMapState } from "@/lib/imagery-map-layer";
import { createImageryTileSet, ImageryTileClientError } from "@/lib/imagery-tile-client";
import type { InferenceGroundingOverlay } from "@/lib/inference-grounding-map-layer";
import { orderComparisonScenes } from "@/lib/scene-comparison";
import {
  type CatalogueSceneContext,
  catalogueSceneKey,
  createCatalogueSceneSelection,
  type SelectedCatalogueScene,
} from "@/lib/scene-selection";
import type { SceneSelectionPersistenceState } from "@/lib/use-scene-selection-draft";
import {
  type ImageryDisplaySettings,
  imageryDisplaySettingsSchema,
  type SavedViewerState,
  type TileMetadata,
  type ViewerCamera,
  type ViewerSceneIdentity,
} from "@/lib/viewer-contracts";
import {
  parseViewerState,
  serializeViewerState,
  VIEWER_STATE_STORAGE_KEY,
} from "@/lib/viewer-state-storage";
import { ComparisonViewer, type ComparisonViewerProps } from "./comparison-viewer";
import {
  MapCanvas,
  type MapCanvasHandle,
  type MapInteraction,
  type MapLifecycle,
} from "./map-canvas";
import { type PreparationMaskOverlay, PreparationPanel } from "./preparation-panel";
import { ChangeAnalysisPanel, type ChangeOverlay } from "./change-analysis-panel";
import type { ChangeResult } from "@/lib/change-client";
import type { OpticalSarResult, SarScene } from "@/lib/optical-sar-client";
import type { SarMapOverlay } from "@/lib/sar-map-layer";
import { OpticalSarPanel } from "./optical-sar-panel";

export interface SceneContainerProps {
  selectedAoi: SelectedAoi | null;
  onSelectAoi: (aoi: SelectedAoi) => void;
  onClearAoi: () => void;
  persistenceMessage: string;
  sceneContext: CatalogueSceneContext | null;
  selectedScene: SelectedCatalogueScene | null;
  hoveredSceneKey: string | null;
  sceneSelectionMessage: string | null;
  scenePersistenceState: SceneSelectionPersistenceState;
  onSceneContextChange: (context: CatalogueSceneContext | null) => void;
  onHoverScene: (sceneKey: string | null) => void;
  onSelectScene: (scene: SelectedCatalogueScene) => void;
  onClearScene: (message?: string) => void;
  onRefreshScene: () => void;
  catalogueClient?: ImageryDiscoveryClient;
  mapCanvasComponent?: typeof MapCanvas;
  imageryTileClient?: (scene: ViewerSceneIdentity, signal?: AbortSignal) => Promise<TileMetadata>;
  comparisonViewerComponent?: (props: ComparisonViewerProps) => ReactNode;
  preparationClient?: import("@/lib/preparation-client").PreparationClient;
  inferenceGroundingOverlay?: InferenceGroundingOverlay | null;
  onChangeResultChange?: (result: ChangeResult | null) => void;
  onOpticalSarResultChange?: (result: OpticalSarResult | null) => void;
  onComparisonChange?: (
    pair: { sceneA: SelectedCatalogueScene; sceneB: SelectedCatalogueScene } | null,
  ) => void;
  onSarSelectionChange?: (scene: SarScene | null, polarization: string | null) => void;
  assistantAction?: { id: number; kind: "aoi" | "scene" | "pair" | "sar" | "zoom_aoi" } | null;
  assistantChangeResult?: { id: number; result: ChangeResult } | null;
  assistantSarResult?: { id: number; result: OpticalSarResult } | null;
}

type ViewerLayerState = {
  selection: SelectedCatalogueScene;
  phase: "metadata" | ImageryMapState;
  message: string;
  metadata: TileMetadata | null;
  requestId: string | null;
};

const sourceLabels: Record<SelectedAoi["source"], string> = {
  rectangle: "Drawn rectangle",
  polygon: "Drawn polygon",
  bbox: "Entered bounds",
  geojson: "Imported GeoJSON",
};

function parseCoordinate(value: string, label: string, minimum: number, maximum: number): number {
  const parsed = Number(value);
  if (!value.trim() || !Number.isFinite(parsed) || parsed < minimum || parsed > maximum) {
    throw new Error(`${label} must be a number from ${minimum} to ${maximum}.`);
  }
  return parsed;
}

export function SceneContainer({
  selectedAoi,
  onSelectAoi,
  onClearAoi,
  persistenceMessage,
  sceneContext,
  selectedScene,
  hoveredSceneKey,
  sceneSelectionMessage,
  scenePersistenceState,
  onSceneContextChange,
  onHoverScene,
  onSelectScene,
  onClearScene,
  onRefreshScene,
  catalogueClient,
  mapCanvasComponent,
  imageryTileClient = createImageryTileSet,
  comparisonViewerComponent,
  preparationClient,
  inferenceGroundingOverlay = null,
  onChangeResultChange = () => {},
  onOpticalSarResultChange = () => {},
  onComparisonChange = () => {},
  onSarSelectionChange = () => {},
  assistantAction = null,
  assistantChangeResult = null,
  assistantSarResult = null,
}: SceneContainerProps) {
  const MapSurface = mapCanvasComponent ?? MapCanvas;
  const mapRef = useRef<MapCanvasHandle>(null);
  const importRef = useRef<HTMLInputElement>(null);
  const mutationRef = useRef(0);
  const imageryRequestRef = useRef<{ id: number; controller: AbortController } | null>(null);
  const imageryRequestSequence = useRef(0);
  const selectedSceneRef = useRef(selectedScene);
  const [previewAoi, setPreviewAoi] = useState<SelectedAoi | null>(null);
  const [interaction, setInteraction] = useState<MapInteraction>("idle");
  const [mapLifecycle, setMapLifecycle] = useState<MapLifecycle>("loading");
  const [mapMessage, setMapMessage] = useState("Loading the basemap…");
  const [geometryMessage, setGeometryMessage] = useState<string | null>(null);
  const [coordinateMessage, setCoordinateMessage] = useState<string | null>(null);
  const [pointerCoordinates, setPointerCoordinates] = useState<[number, number] | null>(null);
  const [longitude, setLongitude] = useState("77.5946");
  const [latitude, setLatitude] = useState("12.9716");
  const [west, setWest] = useState("77.50");
  const [south, setSouth] = useState("12.90");
  const [east, setEast] = useState("77.70");
  const [north, setNorth] = useState("13.05");
  const [placeQuery, setPlaceQuery] = useState("");
  const [placeResults, setPlaceResults] = useState<PlaceSearchResult[]>([]);
  const [placeState, setPlaceState] = useState<"idle" | "loading" | "empty" | "error">("idle");
  const [placeMessage, setPlaceMessage] = useState<string | null>(null);
  const [mobileToolsOpen, setMobileToolsOpen] = useState(false);
  const [viewerLayer, setViewerLayer] = useState<ViewerLayerState | null>(null);
  const [imageryDisplay, setImageryDisplay] = useState<ImageryDisplaySettings>(
    DEFAULT_IMAGERY_DISPLAY_SETTINGS,
  );
  const [comparisonDraft, setComparisonDraft] = useState<{
    A: SelectedCatalogueScene | null;
    B: SelectedCatalogueScene | null;
  }>({ A: null, B: null });
  const [comparisonOpen, setComparisonOpen] = useState(false);
  const [preparationOverlay, setPreparationOverlay] = useState<PreparationMaskOverlay | null>(null);
  const [changeOverlay, setChangeOverlay] = useState<ChangeOverlay | null>(null);
  const [sarOverlay, setSarOverlay] = useState<SarMapOverlay | null>(null);
  const [selectedSar, setSelectedSar] = useState<{ scene: SarScene; polarization: string } | null>(
    null,
  );
  const handledChangeResult = useRef<number | null>(null);
  const overlayInputBinding = JSON.stringify({
    aoi: selectedAoi?.feature.geometry ?? null,
    scene: selectedScene?.key ?? null,
    pair:
      comparisonDraft.A && comparisonDraft.B
        ? [comparisonDraft.A.key, comparisonDraft.B.key]
        : null,
    sar: selectedSar ? [selectedSar.scene.source, selectedSar.polarization] : null,
  });
  const priorOverlayInputBinding = useRef(overlayInputBinding);
  useEffect(() => {
    if (priorOverlayInputBinding.current === overlayInputBinding) return;
    priorOverlayInputBinding.current = overlayInputBinding;
    setChangeOverlay(null);
    setSarOverlay(null);
  }, [overlayInputBinding]);
  const handledSarResult = useRef<number | null>(null);
  const handleSarSelection = useCallback(
    (scene: SarScene | null, polarization: string | null) => {
      setSelectedSar(scene && polarization ? { scene, polarization } : null);
      onSarSelectionChange(scene, polarization);
    },
    [onSarSelectionChange],
  );
  const [activeTimelineKey, setActiveTimelineKey] = useState<string | null>(null);
  const [viewerCamera, setViewerCamera] = useState<ViewerCamera | null>(null);
  const [viewerPersistenceMessage, setViewerPersistenceMessage] = useState(
    "Viewer state is saved only in this browser.",
  );
  const [pendingViewerRestore, setPendingViewerRestore] = useState<SavedViewerState | null>(null);
  const viewerStateHydrated = useRef(false);
  const cameraRestorePendingRef = useRef<ViewerCamera | null>(null);
  selectedSceneRef.current = selectedScene;
  const displayedAoi = previewAoi ?? selectedAoi;
  const basemapName =
    process.env.NEXT_PUBLIC_BASEMAP_NAME?.trim() ||
    (process.env.NEXT_PUBLIC_BASEMAP_STYLE_URL?.trim()
      ? "Configured basemap"
      : "OpenFreeMap Liberty");
  const geocoderName = getGeocoderProviderName();
  const timeline = useMemo(
    () => (sceneContext?.isCurrent ? buildAcquisitionTimeline(sceneContext.scenes) : []),
    [sceneContext],
  );

  const openSceneInViewer = useCallback(
    async (selection: SelectedCatalogueScene) => {
      imageryRequestRef.current?.controller.abort();
      const controller = new AbortController();
      const requestId = ++imageryRequestSequence.current;
      imageryRequestRef.current = { id: requestId, controller };
      setViewerLayer({
        selection,
        phase: "metadata",
        message: "Resolving georeferenced imagery tiles…",
        metadata: null,
        requestId: null,
      });
      try {
        const metadata = await imageryTileClient(
          {
            provider: selection.identity.providerId,
            collection: selection.identity.collectionId,
            item: selection.identity.itemId,
          },
          controller.signal,
        );
        if (
          imageryRequestRef.current?.id !== requestId ||
          controller.signal.aborted ||
          selectedSceneRef.current?.key !== selection.key
        ) {
          return;
        }
        // Move synchronously before mounting the source so MapLibre does not first fan out
        // requests for the previous, potentially much closer AOI viewport.
        mapRef.current?.prepareImageryView(metadata.bounds);
        setViewerLayer({
          selection,
          phase: "loading",
          message: "Loading georeferenced imagery tiles…",
          metadata,
          requestId: null,
        });
        setMobileToolsOpen(false);
      } catch (error) {
        if (error instanceof ImageryTileClientError && error.kind === "cancelled") return;
        if (
          imageryRequestRef.current?.id !== requestId ||
          selectedSceneRef.current?.key !== selection.key
        ) {
          return;
        }
        const imageryError = error instanceof ImageryTileClientError ? error : null;
        setViewerLayer({
          selection,
          phase: imageryError?.kind === "expired" ? "expired" : "failed",
          message: error instanceof Error ? error.message : "Imagery is unavailable.",
          metadata: null,
          requestId: imageryError?.requestId ?? null,
        });
      } finally {
        if (imageryRequestRef.current?.id === requestId) imageryRequestRef.current = null;
      }
    },
    [imageryTileClient],
  );

  const selectAndOpenScene = useCallback(
    (selection: SelectedCatalogueScene) => {
      selectedSceneRef.current = selection;
      onSelectScene(selection);
      void openSceneInViewer(selection);
    },
    [onSelectScene, openSceneInViewer],
  );

  function removeViewerLayer() {
    imageryRequestRef.current?.controller.abort();
    imageryRequestRef.current = null;
    imageryRequestSequence.current += 1;
    setViewerLayer(null);
    setImageryDisplay(DEFAULT_IMAGERY_DISPLAY_SETTINGS);
  }

  function updateImageryDisplay(patch: Partial<ImageryDisplaySettings>) {
    setImageryDisplay((current) => {
      const parsed = imageryDisplaySettingsSchema.safeParse({ ...current, ...patch });
      return parsed.success ? parsed.data : current;
    });
  }

  function resetImageryDisplay() {
    setImageryDisplay(DEFAULT_IMAGERY_DISPLAY_SETTINGS);
  }

  function fitViewerImagery() {
    if (viewerLayer?.metadata) mapRef.current?.fitScene(viewerLayer.metadata.bounds);
  }

  function assignComparison(selection: SelectedCatalogueScene, slot: "A" | "B") {
    setComparisonDraft((current) => ({ ...current, [slot]: selection }));
  }

  function selectTimelineEntry(key: string) {
    if (!sceneContext?.isCurrent) return;
    const entry = timeline.find((candidate) => candidate.key === key);
    if (!entry) return;
    const selection = createCatalogueSceneSelection(
      entry.scene,
      sceneContext.fingerprint,
      sceneContext.query,
    );
    setActiveTimelineKey(key);
    selectAndOpenScene(selection);
  }

  function moveTimeline(offset: -1 | 1) {
    const currentIndex = timeline.findIndex((entry) => entry.key === activeTimelineKey);
    const nextIndex =
      currentIndex < 0 ? (offset > 0 ? 0 : timeline.length - 1) : currentIndex + offset;
    const next = timeline[nextIndex];
    if (next) selectTimelineEntry(next.key);
  }

  const orderedComparison = useMemo(
    () =>
      comparisonDraft.A && comparisonDraft.B
        ? orderComparisonScenes(comparisonDraft.A, comparisonDraft.B)
        : null,
    [comparisonDraft.A, comparisonDraft.B],
  );

  useEffect(() => {
    onComparisonChange(orderedComparison);
  }, [orderedComparison, onComparisonChange]);

  useEffect(() => {
    if (!assistantAction) return;
    if (assistantAction.kind === "zoom_aoi") {
      if (selectedAoi) mapRef.current?.fitSelectedAoi();
      return;
    }
    if (window.matchMedia?.("(max-width: 760px)").matches && !mobileToolsOpen) {
      setMobileToolsOpen(true);
      return;
    }
    const targetId = {
      aoi: "draw-tools-title",
      scene: "imagery-discovery-title",
      pair: "comparison-selection-title",
      sar: "optical-sar-title",
    }[assistantAction.kind];
    const target = document.getElementById(targetId);
    target?.scrollIntoView({ block: "center", behavior: "smooth" });
    target?.focus();
  }, [assistantAction, selectedAoi, mobileToolsOpen]);

  useEffect(() => {
    if (!assistantChangeResult || !selectedAoi || !orderedComparison) return;
    if (handledChangeResult.current === assistantChangeResult.id) return;
    const { result } = assistantChangeResult;
    const selected = [orderedComparison.sceneA, orderedComparison.sceneB];
    if (
      result.sources.some(
        (source) =>
          !selected.some(
            (scene) =>
              source.scene.provider === scene.identity.providerId &&
              source.scene.collection === scene.identity.collectionId &&
              source.scene.item === scene.identity.itemId &&
              Date.parse(source.acquired_at) === Date.parse(scene.scene.acquisition.start),
          ),
      ) ||
      JSON.stringify(result.aoi) !== JSON.stringify(selectedAoi.feature.geometry)
    )
      return;
    handledChangeResult.current = assistantChangeResult.id;
    setChangeOverlay({
      artifactId: result.classification_artifact_id,
      bounds: result.grid.bounds as AoiBounds,
      opacity: 0.7,
      visible: true,
    });
    mapRef.current?.navigateToBounds(result.grid.bounds as AoiBounds);
  }, [assistantChangeResult, selectedAoi, orderedComparison]);

  useEffect(() => {
    if (!assistantSarResult || !sarOverlay || !selectedSar) return;
    if (handledSarResult.current === assistantSarResult.id) return;
    if (
      selectedSar.scene.source.item !== assistantSarResult.result.sar.source.item ||
      !assistantSarResult.result.sar.layer.includes(selectedSar.polarization)
    )
      return;
    handledSarResult.current = assistantSarResult.id;
    setSarOverlay((current) => (current ? { ...current, visible: true } : null));
    mapRef.current?.navigateToBounds(sarOverlay.bounds);
  }, [assistantSarResult, sarOverlay, selectedSar]);

  useEffect(() => {
    if (!inferenceGroundingOverlay || inferenceGroundingOverlay.sceneKey !== selectedScene?.key)
      return;
    const points = inferenceGroundingOverlay.geometry.features.flatMap((feature) =>
      feature.geometry.coordinates.flat(),
    );
    if (!points.length || points.some(([x, y]) => !Number.isFinite(x) || !Number.isFinite(y)))
      return;
    const west = Math.min(...points.map(([x]) => x));
    const east = Math.max(...points.map(([x]) => x));
    const south = Math.min(...points.map(([, y]) => y));
    const north = Math.max(...points.map(([, y]) => y));
    if (west < east && south < north) mapRef.current?.navigateToBounds([west, south, east, north]);
  }, [inferenceGroundingOverlay, selectedScene]);

  useEffect(() => {
    if (activeTimelineKey && !timeline.some((entry) => entry.key === activeTimelineKey)) {
      setActiveTimelineKey(null);
    }
  }, [activeTimelineKey, timeline]);

  useEffect(() => {
    if (viewerLayer && selectedScene?.key !== viewerLayer.selection.key) {
      imageryRequestRef.current?.controller.abort();
      imageryRequestRef.current = null;
      imageryRequestSequence.current += 1;
      setViewerLayer(null);
      setImageryDisplay(DEFAULT_IMAGERY_DISPLAY_SETTINGS);
    }
  }, [selectedScene, viewerLayer]);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(VIEWER_STATE_STORAGE_KEY);
      if (stored) setPendingViewerRestore(parseViewerState(stored));
    } catch (error) {
      setViewerPersistenceMessage(
        error instanceof Error
          ? `${error.message} Viewer state was not restored.`
          : "Viewer state was not restored.",
      );
    } finally {
      viewerStateHydrated.current = true;
    }
  }, []);

  useEffect(() => {
    if (!pendingViewerRestore || !selectedAoi || (!sceneContext?.isCurrent && !selectedScene))
      return;
    const fingerprint = JSON.stringify(selectedAoi.feature.geometry);
    if (pendingViewerRestore.aoi_reference?.geometry_fingerprint !== fingerprint) {
      setViewerPersistenceMessage(
        "Saved viewer state belongs to a different AOI and was not restored.",
      );
      setPendingViewerRestore(null);
      return;
    }
    const byIdentity = (identity: ViewerSceneIdentity) => {
      const loaded = sceneContext?.isCurrent
        ? sceneContext.scenes.find(
            (scene) =>
              scene.provider.id === identity.provider &&
              scene.collection.id === identity.collection &&
              scene.provider_asset_id === identity.item,
          )
        : null;
      if (loaded) return loaded;
      return selectedScene?.identity.providerId === identity.provider &&
        selectedScene.identity.collectionId === identity.collection &&
        selectedScene.identity.itemId === identity.item
        ? selectedScene.scene
        : null;
    };
    const restoreSelection = (identity: ViewerSceneIdentity) => {
      const scene = byIdentity(identity);
      if (!scene) return null;
      if (selectedScene?.key === catalogueSceneKey(scene)) return selectedScene;
      return sceneContext?.isCurrent
        ? createCatalogueSceneSelection(scene, sceneContext.fingerprint, sceneContext.query)
        : null;
    };
    const activeIdentity = pendingViewerRestore.active_layer?.asset.scene;
    const active = activeIdentity ? restoreSelection(activeIdentity) : null;
    const restoredSlots = pendingViewerRestore.comparison_slots ?? pendingViewerRestore.comparison;
    const comparisonA = restoredSlots?.scene_a
      ? restoreSelection(restoredSlots.scene_a.scene)
      : null;
    const comparisonB = restoredSlots?.scene_b
      ? restoreSelection(restoredSlots.scene_b.scene)
      : null;
    const timelineIdentity = pendingViewerRestore.timeline?.selected_scene;
    const timelineScene = timelineIdentity ? restoreSelection(timelineIdentity) : null;
    if (pendingViewerRestore.camera) {
      setViewerCamera(pendingViewerRestore.camera);
      cameraRestorePendingRef.current = pendingViewerRestore.camera;
    }
    if (pendingViewerRestore.active_layer)
      setImageryDisplay(pendingViewerRestore.active_layer.display);
    setComparisonDraft({ A: comparisonA, B: comparisonB });
    if (timelineScene) setActiveTimelineKey(timelineScene.key);
    if (active) {
      selectedSceneRef.current = active;
      onSelectScene(active);
      void openSceneInViewer(active);
    }
    const missing = Boolean(
      (activeIdentity && !active) ||
        (restoredSlots &&
          ((restoredSlots.scene_a && !comparisonA) || (restoredSlots.scene_b && !comparisonB))) ||
        (timelineIdentity && !timelineScene),
    );
    setViewerPersistenceMessage(
      missing
        ? "Viewer state restored partially; some saved scenes are not in the loaded catalogue pages. No substitute was used."
        : "Viewer state restored from this browser; imagery access was re-resolved.",
    );
    setPendingViewerRestore(null);
  }, [
    onSelectScene,
    openSceneInViewer,
    pendingViewerRestore,
    sceneContext,
    selectedAoi,
    selectedScene,
  ]);

  useEffect(() => {
    if (mapLifecycle !== "ready" || !cameraRestorePendingRef.current) return;
    mapRef.current?.restoreCamera(cameraRestorePendingRef.current);
    cameraRestorePendingRef.current = null;
  }, [mapLifecycle]);

  useEffect(() => {
    if (!viewerStateHydrated.current || pendingViewerRestore) return;
    const timer = window.setTimeout(() => {
      const timelineSelected = timeline.find((entry) => entry.key === activeTimelineKey);
      const timelineSelectedIndex = timelineSelected
        ? timeline.findIndex((entry) => entry.key === timelineSelected.key)
        : -1;
      const savedTimelineEntries =
        timelineSelectedIndex < 0
          ? []
          : timeline.slice(Math.max(0, timelineSelectedIndex - 99), timelineSelectedIndex + 1);
      const state: SavedViewerState = {
        version: 1,
        saved_at: new Date().toISOString(),
        aoi_reference: selectedAoi
          ? {
              storage_key: "satquery.aoi-draft.v1",
              geometry_fingerprint: JSON.stringify(selectedAoi.feature.geometry),
            }
          : null,
        camera: viewerCamera ?? mapRef.current?.getCamera() ?? null,
        active_layer: viewerLayer?.metadata
          ? {
              layer_id: "primary_imagery",
              asset: viewerLayer.metadata.asset,
              acquisition: viewerLayer.selection.scene.acquisition,
              render_preset: viewerLayer.metadata.render_preset,
              display: imageryDisplay,
            }
          : null,
        comparison_slots:
          comparisonDraft.A || comparisonDraft.B
            ? {
                scene_a: comparisonDraft.A
                  ? {
                      scene: {
                        provider: comparisonDraft.A.identity.providerId,
                        collection: comparisonDraft.A.identity.collectionId,
                        item: comparisonDraft.A.identity.itemId,
                      },
                      acquisition: comparisonDraft.A.scene.acquisition,
                    }
                  : null,
                scene_b: comparisonDraft.B
                  ? {
                      scene: {
                        provider: comparisonDraft.B.identity.providerId,
                        collection: comparisonDraft.B.identity.collectionId,
                        item: comparisonDraft.B.identity.itemId,
                      },
                      acquisition: comparisonDraft.B.scene.acquisition,
                    }
                  : null,
              }
            : null,
        comparison: orderedComparison
          ? {
              scene_a: {
                scene: {
                  provider: orderedComparison.sceneA.identity.providerId,
                  collection: orderedComparison.sceneA.identity.collectionId,
                  item: orderedComparison.sceneA.identity.itemId,
                },
                acquisition: orderedComparison.sceneA.scene.acquisition,
              },
              scene_b: {
                scene: {
                  provider: orderedComparison.sceneB.identity.providerId,
                  collection: orderedComparison.sceneB.identity.collectionId,
                  item: orderedComparison.sceneB.identity.itemId,
                },
                acquisition: orderedComparison.sceneB.scene.acquisition,
              },
            }
          : null,
        timeline: timelineSelected
          ? {
              scenes: savedTimelineEntries.map((entry) => ({
                scene: {
                  provider: entry.scene.provider.id,
                  collection: entry.scene.collection.id,
                  item: entry.scene.provider_asset_id,
                },
                acquisition: entry.scene.acquisition,
              })),
              selected_scene: {
                provider: timelineSelected.scene.provider.id,
                collection: timelineSelected.scene.collection.id,
                item: timelineSelected.scene.provider_asset_id,
              },
            }
          : null,
      };
      try {
        window.localStorage.setItem(VIEWER_STATE_STORAGE_KEY, serializeViewerState(state));
        setViewerPersistenceMessage(
          "Viewer state saved in this browser. Imagery access is never stored.",
        );
      } catch {
        setViewerPersistenceMessage(
          "Browser storage is unavailable; viewer state remains in this tab only.",
        );
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [
    activeTimelineKey,
    imageryDisplay,
    orderedComparison,
    comparisonDraft.A,
    comparisonDraft.B,
    pendingViewerRestore,
    selectedAoi,
    timeline,
    viewerCamera,
    viewerLayer,
  ]);

  useEffect(
    () => () => {
      imageryRequestRef.current?.controller.abort();
    },
    [],
  );

  function selectSceneByKey(sceneKey: string) {
    if (!sceneContext?.isCurrent) return;
    const scene = sceneContext.scenes.find(
      (candidate) => catalogueSceneKey(candidate) === sceneKey,
    );
    if (scene)
      selectAndOpenScene(
        createCatalogueSceneSelection(scene, sceneContext.fingerprint, sceneContext.query),
      );
  }

  function keepFormShortcutsLocal(event: KeyboardEvent<HTMLElement>) {
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
      event.stopPropagation();
    }
  }

  function commitAoi(aoi: SelectedAoi, fit = true) {
    const displayIssue = getMapDisplayIssue(aoi);
    if (displayIssue) {
      setGeometryMessage(`${displayIssue} Reduce the latitude extent and try again.`);
      return false;
    }
    setGeometryMessage(null);
    setPreviewAoi(null);
    mutationRef.current += 1;
    if (fit) {
      mapRef.current?.cancelEdit();
      mapRef.current?.cancelDrawing();
    }
    onSelectAoi(aoi);
    if (fit) {
      mapRef.current?.navigateToBounds(aoi.bounds);
    }
    return true;
  }

  function handleCoordinateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const parsedLongitude = parseCoordinate(longitude, "Longitude", -180, 180);
      const parsedLatitude = parseCoordinate(latitude, "Latitude", -85.051129, 85.051129);
      setCoordinateMessage(
        `Navigated to ${parsedLongitude.toFixed(5)}, ${parsedLatitude.toFixed(5)}.`,
      );
      mapRef.current?.navigateTo(parsedLongitude, parsedLatitude);
    } catch (error) {
      setCoordinateMessage(error instanceof Error ? error.message : "Coordinates are invalid.");
    }
  }

  function handleBoundsSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const bounds: AoiBounds = [
        parseCoordinate(west, "West", -180, 180),
        parseCoordinate(south, "South", -90, 90),
        parseCoordinate(east, "East", -180, 180),
        parseCoordinate(north, "North", -90, 90),
      ];
      commitAoi(createAoiFromBounds(bounds));
    } catch (error) {
      setGeometryMessage(error instanceof Error ? error.message : "The bounding box is invalid.");
    }
  }

  async function handlePlaceSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPlaceState("loading");
    setPlaceMessage("Searching…");
    setPlaceResults([]);
    try {
      const results = await searchPlaces(placeQuery);
      setPlaceResults(results);
      setPlaceState(results.length > 0 ? "idle" : "empty");
      setPlaceMessage(
        results.length > 0 ? `${results.length} places found.` : "No places matched that search.",
      );
    } catch (error) {
      setPlaceState("error");
      setPlaceMessage(error instanceof Error ? error.message : "Place search failed.");
    }
  }

  function choosePlace(result: PlaceSearchResult) {
    if (Math.abs(result.latitude) > 85.051129) {
      setPlaceMessage("This place is outside the map's latitude display limit.");
      return;
    }
    setPlaceMessage(`Showing ${result.label}.`);
    if (result.bounds) {
      mapRef.current?.navigateToBounds(result.bounds);
    } else {
      mapRef.current?.navigateTo(result.longitude, result.latitude);
    }
  }

  async function handleImport(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }
    if (file.size > AOI_MAX_FILE_BYTES) {
      setGeometryMessage("GeoJSON files may be at most 1 MB. The current AOI was preserved.");
      return;
    }
    try {
      const revision = ++mutationRef.current;
      const imported = parseGeoJsonText(await file.text());
      if (revision !== mutationRef.current) return;
      if (!commitAoi(imported)) {
        return;
      }
      setGeometryMessage("GeoJSON imported and validated.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "The GeoJSON import failed.";
      setGeometryMessage(`${message} The current AOI was preserved.`);
    }
  }

  function exportAoi() {
    if (!selectedAoi) {
      return;
    }
    const blob = new Blob([serializeAoi(selectedAoi)], { type: "application/geo+json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "satquery-selected-aoi.geojson";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
    setGeometryMessage("Exported satquery-selected-aoi.geojson.");
  }

  function startAoiDrawing(mode: "rectangle" | "polygon") {
    setGeometryMessage(null);
    mapRef.current?.startDrawing(mode);
    setMobileToolsOpen(false);
  }

  function clearAoi() {
    mutationRef.current += 1;
    mapRef.current?.cancelEdit();
    mapRef.current?.cancelDrawing();
    setPreviewAoi(null);
    setGeometryMessage("Selected AOI cleared. See the storage status below.");
    onClearAoi();
  }

  return (
    <main className="workspace-main" id="main-content" aria-label="Map and AOI workspace">
      <div className="scene-header">
        <div>
          <p className="panel-kicker">Map workspace</p>
          <h1>Explore Earth and define an area</h1>
        </div>
        <fieldset className="scene-context-pills">
          <legend className="sr-only">Current scene context</legend>
          <span
            className={`scene-context-pill ${selectedScene ? "active" : ""}`}
            title={selectedScene?.identity.itemId}
          >
            <i aria-hidden="true" />{" "}
            {selectedScene ? "Catalogue scene selected" : "No imagery selected"}
          </span>
          <span className={`scene-context-pill ${displayedAoi ? "active" : ""}`}>
            <i aria-hidden="true" /> {displayedAoi ? displayedAoi.name : "No area selected"}
          </span>
        </fieldset>
      </div>

      <section className="map-stage" aria-label="Interactive map and area tools">
        {comparisonOpen && orderedComparison ? (
          comparisonViewerComponent ? (
            comparisonViewerComponent({
              ...orderedComparison,
              selectedAoi,
              tileClient: imageryTileClient,
              onClose: () => setComparisonOpen(false),
            })
          ) : (
            <ComparisonViewer
              {...orderedComparison}
              selectedAoi={selectedAoi}
              tileClient={imageryTileClient}
              onClose={() => setComparisonOpen(false)}
            />
          )
        ) : null}
        <MapSurface
          ref={mapRef}
          selectedAoi={selectedAoi}
          sceneContext={sceneContext}
          selectedScene={selectedScene}
          hoveredSceneKey={hoveredSceneKey}
          imageryMetadata={viewerLayer?.metadata ?? null}
          imageryDisplaySettings={imageryDisplay}
          preparationMaskOverlay={preparationOverlay}
          changeOverlay={changeOverlay}
          sarOverlay={sarOverlay}
          inferenceGroundingOverlay={inferenceGroundingOverlay}
          onCommitAoi={(aoi) => commitAoi(aoi, false)}
          onPreviewAoi={setPreviewAoi}
          onInteractionChange={setInteraction}
          onLifecycleChange={(lifecycle, message) => {
            setMapLifecycle(lifecycle);
            setMapMessage(message);
          }}
          onCoordinateChange={setPointerCoordinates}
          onGeometryError={setGeometryMessage}
          onSceneHover={onHoverScene}
          onSceneSelect={selectSceneByKey}
          onImageryStateChange={(phase, message) => {
            setViewerLayer((current) =>
              current?.metadata && (current.phase !== phase || current.message !== message)
                ? { ...current, phase, message }
                : current,
            );
          }}
          onCameraChange={setViewerCamera}
        />

        <div className="map-aoi-controls" role="toolbar" aria-label="AOI drawing controls">
          <button
            className={interaction === "rectangle" ? "active" : ""}
            type="button"
            disabled={mapLifecycle !== "ready" || interaction === "edit"}
            aria-pressed={interaction === "rectangle"}
            onClick={() => startAoiDrawing("rectangle")}
          >
            Draw rectangle
          </button>
          <button
            className={interaction === "polygon" ? "active" : ""}
            type="button"
            disabled={mapLifecycle !== "ready" || interaction === "edit"}
            aria-pressed={interaction === "polygon"}
            onClick={() => startAoiDrawing("polygon")}
          >
            Draw polygon
          </button>
          <button className="danger" type="button" disabled={!selectedAoi} onClick={clearAoi}>
            Clear AOI
          </button>
        </div>

        <div
          className={`map-lifecycle map-lifecycle-${mapLifecycle}`}
          role="status"
          aria-live="polite"
        >
          <span className="map-status-dot" aria-hidden="true" />
          <span>{mapMessage}</span>
          {mapLifecycle === "error" || mapLifecycle === "unsupported" ? (
            <button type="button" onClick={() => mapRef.current?.retry()}>
              Retry map
            </button>
          ) : null}
        </div>

        {viewerLayer ? (
          <aside
            className={`imagery-viewer-summary imagery-viewer-${viewerLayer.phase}`}
            aria-label="Active imagery overlay"
          >
            <div>
              <p>Imagery overlay · context basemap beneath</p>
              <strong>{viewerLayer.selection.scene.provider_asset_id}</strong>
              <small>
                Acquired {new Date(viewerLayer.selection.scene.acquisition.start).toISOString()} ·{" "}
                {viewerLayer.selection.identity.providerId}/
                {viewerLayer.selection.identity.collectionId}
              </small>
              <span role={viewerLayer.phase === "failed" ? "alert" : "status"}>
                {viewerLayer.message}
                {viewerLayer.requestId ? ` Request ${viewerLayer.requestId}.` : ""}
              </span>
              {viewerLayer.metadata ? (
                <small>Attribution: {viewerLayer.metadata.attributions.join(" · ")}</small>
              ) : null}
              {viewerLayer.metadata ? (
                <details className="imagery-display-controls">
                  <summary>Display controls</summary>
                  <fieldset>
                    <legend className="sr-only">Imagery display controls</legend>
                    <label className="imagery-visibility-control">
                      <input
                        type="checkbox"
                        checked={imageryDisplay.visible}
                        onChange={(event) =>
                          updateImageryDisplay({ visible: event.currentTarget.checked })
                        }
                      />
                      Layer visible
                    </label>
                    <label>
                      Render preset
                      <select
                        aria-label="Render preset"
                        value={viewerLayer.metadata.render_preset}
                        onChange={(event) => {
                          if (event.currentTarget.value !== "natural-color") {
                            event.currentTarget.value = viewerLayer.metadata?.render_preset ?? "";
                          }
                        }}
                      >
                        <option value="natural-color">Natural colour · red / green / blue</option>
                        <option value="false-color" disabled>
                          False colour unavailable · near-infrared not resolved
                        </option>
                        <option value="single-band" disabled>
                          Single band unavailable · not approved for this renderer
                        </option>
                      </select>
                    </label>
                    <label>
                      Opacity <output>{Math.round(imageryDisplay.opacity * 100)}%</output>
                      <input
                        aria-label="Imagery opacity"
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        value={imageryDisplay.opacity}
                        onChange={(event) =>
                          updateImageryDisplay({ opacity: Number(event.currentTarget.value) })
                        }
                      />
                    </label>
                    <label>
                      Brightness floor{" "}
                      <output>{Math.round(imageryDisplay.brightness_min * 100)}%</output>
                      <input
                        aria-label="Imagery brightness floor"
                        type="range"
                        min="0"
                        max={imageryDisplay.brightness_max}
                        step="0.05"
                        value={imageryDisplay.brightness_min}
                        onChange={(event) =>
                          updateImageryDisplay({
                            brightness_min: Number(event.currentTarget.value),
                          })
                        }
                      />
                    </label>
                    <label>
                      Brightness ceiling{" "}
                      <output>{Math.round(imageryDisplay.brightness_max * 100)}%</output>
                      <input
                        aria-label="Imagery brightness ceiling"
                        type="range"
                        min={imageryDisplay.brightness_min}
                        max="1"
                        step="0.05"
                        value={imageryDisplay.brightness_max}
                        onChange={(event) =>
                          updateImageryDisplay({
                            brightness_max: Number(event.currentTarget.value),
                          })
                        }
                      />
                    </label>
                    <label>
                      Contrast <output>{imageryDisplay.contrast.toFixed(1)}</output>
                      <input
                        aria-label="Imagery contrast"
                        type="range"
                        min="-1"
                        max="1"
                        step="0.1"
                        value={imageryDisplay.contrast}
                        onChange={(event) =>
                          updateImageryDisplay({ contrast: Number(event.currentTarget.value) })
                        }
                      />
                    </label>
                    <label>
                      Saturation <output>{imageryDisplay.saturation.toFixed(1)}</output>
                      <input
                        aria-label="Imagery saturation"
                        type="range"
                        min="-1"
                        max="1"
                        step="0.1"
                        value={imageryDisplay.saturation}
                        onChange={(event) =>
                          updateImageryDisplay({ saturation: Number(event.currentTarget.value) })
                        }
                      />
                    </label>
                    <small className="imagery-display-note">
                      Display only. Server RGB uses fixed reflectance 0.00–0.30 after each
                      band&apos;s scale/offset; controls do not change source values or perform
                      analysis.
                    </small>
                    <button type="button" onClick={resetImageryDisplay}>
                      Reset display
                    </button>
                  </fieldset>
                </details>
              ) : null}
            </div>
            <div className="imagery-viewer-actions">
              {viewerLayer.metadata ? (
                <button type="button" onClick={fitViewerImagery}>
                  Fit imagery
                </button>
              ) : null}
              <button
                type="button"
                disabled={!selectedAoi}
                onClick={() => mapRef.current?.fitSelectedAoi()}
              >
                Fit AOI
              </button>
              {viewerLayer.phase === "failed" ||
              viewerLayer.phase === "partial" ||
              viewerLayer.phase === "expired" ? (
                <button type="button" onClick={() => void openSceneInViewer(viewerLayer.selection)}>
                  Retry imagery
                </button>
              ) : null}
              <button type="button" onClick={removeViewerLayer}>
                Remove imagery
              </button>
            </div>
          </aside>
        ) : null}

        <button
          className="map-tools-mobile-toggle"
          type="button"
          aria-expanded={mobileToolsOpen}
          aria-controls="map-tools-panel"
          onClick={() => setMobileToolsOpen((current) => !current)}
        >
          <Icon name="map" /> {mobileToolsOpen ? "Hide tools" : "Workspace tools"}
        </button>

        <aside
          className={`map-tools-panel ${mobileToolsOpen ? "open" : ""}`}
          id="map-tools-panel"
          aria-label="Map, AOI, and imagery tools"
          onKeyDownCapture={keepFormShortcutsLocal}
          onKeyUpCapture={keepFormShortcutsLocal}
        >
          <div className="map-tools-heading">
            <div>
              <p className="panel-kicker">Workspace tools</p>
              <h2>Map &amp; imagery</h2>
            </div>
            <button
              className="icon-button map-tools-mobile-close"
              type="button"
              aria-label="Close map tools"
              onClick={() => setMobileToolsOpen(false)}
            >
              <Icon name="close" />
            </button>
          </div>

          <ImageryDiscoveryPanel
            selectedAoi={selectedAoi}
            client={catalogueClient}
            selectedScene={selectedScene}
            hoveredSceneKey={hoveredSceneKey}
            selectionMessage={sceneSelectionMessage}
            selectionPersistenceState={scenePersistenceState}
            onSceneContextChange={onSceneContextChange}
            onHoverScene={onHoverScene}
            onSelectScene={selectAndOpenScene}
            onClearScene={onClearScene}
            onRefreshScene={onRefreshScene}
            onOpenScene={(selection) => void openSceneInViewer(selection)}
            onAssignComparison={assignComparison}
            viewerSceneKey={viewerLayer?.selection.key ?? null}
            viewerLoading={viewerLayer?.phase === "metadata" || viewerLayer?.phase === "loading"}
            onFitScene={(scene) => {
              mapRef.current?.fitScene(scene.bbox);
              setMobileToolsOpen(false);
            }}
          />

          <section
            className="map-tool-section comparison-selection"
            aria-labelledby="comparison-selection-title"
          >
            <h3 id="comparison-selection-title" tabIndex={-1}>
              Compare two dates
            </h3>
            <p>A is the earlier acquisition and B the later acquisition when comparison opens.</p>
            <dl>
              <div>
                <dt>A assignment</dt>
                <dd>
                  {comparisonDraft.A
                    ? `${new Date(comparisonDraft.A.scene.acquisition.start).toISOString()} · ${comparisonDraft.A.identity.itemId}`
                    : "Not assigned"}
                </dd>
              </div>
              <div>
                <dt>B assignment</dt>
                <dd>
                  {comparisonDraft.B
                    ? `${new Date(comparisonDraft.B.scene.acquisition.start).toISOString()} · ${comparisonDraft.B.identity.itemId}`
                    : "Not assigned"}
                </dd>
              </div>
            </dl>
            {comparisonDraft.A?.key === comparisonDraft.B?.key ? (
              <p role="alert">Comparison scenes must be distinct.</p>
            ) : null}
            <button
              type="button"
              disabled={!orderedComparison}
              onClick={() => {
                if (!orderedComparison) return;
                setComparisonDraft({ A: orderedComparison.sceneA, B: orderedComparison.sceneB });
                setComparisonOpen(true);
              }}
            >
              Open comparison
            </button>
            <button
              type="button"
              disabled={!comparisonDraft.A && !comparisonDraft.B}
              onClick={() => {
                setComparisonOpen(false);
                setComparisonDraft({ A: null, B: null });
              }}
            >
              Clear comparison
            </button>
          </section>

          <PreparationPanel
            selectedAoi={selectedAoi}
            selectedScene={selectedScene}
            comparison={orderedComparison}
            client={preparationClient}
            onOverlayChange={setPreparationOverlay}
          />
          <ChangeAnalysisPanel
            selectedAoi={selectedAoi}
            comparison={orderedComparison}
            onOverlayChange={setChangeOverlay}
            onResultChange={onChangeResultChange}
          />
          <OpticalSarPanel
            selectedAoi={selectedAoi}
            selectedScene={selectedScene}
            onOverlayChange={setSarOverlay}
            onResultChange={onOpticalSarResultChange}
            onSarSelectionChange={handleSarSelection}
          />

          <section
            className="map-tool-section acquisition-timeline"
            aria-labelledby="timeline-title"
          >
            <h3 id="timeline-title">Acquisition timeline</h3>
            <p>{viewerPersistenceMessage}</p>
            {!sceneContext?.isCurrent ? (
              <p role="status">
                Run or update the catalogue search to load the current AOI timeline.
              </p>
            ) : timeline.length === 0 ? (
              <p role="status">No acquisitions are loaded for the current search.</p>
            ) : (
              <>
                <div className="timeline-navigation">
                  <button
                    type="button"
                    disabled={!activeTimelineKey || timeline[0]?.key === activeTimelineKey}
                    onClick={() => moveTimeline(-1)}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    disabled={!activeTimelineKey || timeline.at(-1)?.key === activeTimelineKey}
                    onClick={() => moveTimeline(1)}
                  >
                    Next
                  </button>
                </div>
                <ol aria-label="Loaded acquisitions in chronological order">
                  {timeline.map((entry) => {
                    const selection = createCatalogueSceneSelection(
                      entry.scene,
                      sceneContext.fingerprint,
                      sceneContext.query,
                    );
                    return (
                      <li key={entry.key}>
                        <button
                          type="button"
                          aria-current={activeTimelineKey === entry.key ? "true" : undefined}
                          onClick={() => selectTimelineEntry(entry.key)}
                        >
                          <time dateTime={entry.timestamp}>
                            {new Date(entry.timestamp).toISOString()}
                          </time>
                          {entry.sameDateCount > 1
                            ? ` · acquisition ${entry.sameDateIndex} of ${entry.sameDateCount} on this date`
                            : ""}
                          <small>{entry.scene.provider_asset_id}</small>
                        </button>
                        <span className="timeline-assignment-actions">
                          <button type="button" onClick={() => assignComparison(selection, "A")}>
                            Assign A
                          </button>
                          <button type="button" onClick={() => assignComparison(selection, "B")}>
                            Assign B
                          </button>
                        </span>
                      </li>
                    );
                  })}
                </ol>
                {sceneContext.hasMore ? (
                  <p role="status">
                    More catalogue pages remain unloaded; this timeline is incomplete and does not
                    imply absent dates.
                  </p>
                ) : (
                  <p>All pages returned for this search are loaded.</p>
                )}
              </>
            )}
          </section>

          <section className="map-tool-section" aria-labelledby="draw-tools-title">
            <h3 id="draw-tools-title" tabIndex={-1}>
              Draw or edit
            </h3>
            <div className="map-tool-button-grid">
              <button
                className={interaction === "rectangle" ? "active" : ""}
                type="button"
                disabled={mapLifecycle !== "ready" || interaction === "edit"}
                onClick={() => startAoiDrawing("rectangle")}
              >
                Rectangle
              </button>
              <button
                className={interaction === "polygon" ? "active" : ""}
                type="button"
                disabled={mapLifecycle !== "ready" || interaction === "edit"}
                onClick={() => startAoiDrawing("polygon")}
              >
                Polygon
              </button>
              {interaction === "rectangle" || interaction === "polygon" ? (
                <button type="button" onClick={() => mapRef.current?.cancelDrawing()}>
                  Cancel drawing
                </button>
              ) : null}
              {selectedAoi && interaction === "idle" ? (
                <button
                  type="button"
                  disabled={mapLifecycle !== "ready"}
                  onClick={() => {
                    mapRef.current?.beginEdit();
                    setMobileToolsOpen(false);
                  }}
                >
                  Edit vertices
                </button>
              ) : null}
              {interaction === "edit" ? (
                <>
                  <button
                    className="active"
                    type="button"
                    onClick={() => mapRef.current?.finishEdit()}
                  >
                    Finish edit
                  </button>
                  <button type="button" onClick={() => mapRef.current?.cancelEdit()}>
                    Cancel edit
                  </button>
                </>
              ) : null}
            </div>
            <p className="map-tool-help">
              Rectangle: choose two corners. Polygon: choose at least three vertices, then click the
              first point. Cancel drawing preserves the prior AOI. Reopen tools to finish or cancel
              an edit.
            </p>
          </section>

          <details className="map-tool-section">
            <summary>Go to coordinates</summary>
            <form className="compact-map-form" onSubmit={handleCoordinateSubmit} noValidate>
              <label>
                Longitude
                <input
                  value={longitude}
                  onChange={(event) => setLongitude(event.target.value)}
                  inputMode="decimal"
                />
              </label>
              <label>
                Latitude
                <input
                  value={latitude}
                  onChange={(event) => setLatitude(event.target.value)}
                  inputMode="decimal"
                />
              </label>
              <button type="submit" disabled={mapLifecycle !== "ready"}>
                Go to coordinate
              </button>
            </form>
            {coordinateMessage ? (
              <p className="map-form-message" role="status">
                {coordinateMessage}
              </p>
            ) : null}
          </details>

          <details className="map-tool-section">
            <summary>Search for a place</summary>
            <form className="place-search-form" onSubmit={handlePlaceSubmit}>
              <label htmlFor="place-query">Place name</label>
              <div>
                <input
                  id="place-query"
                  value={placeQuery}
                  maxLength={160}
                  placeholder="Search on submit"
                  onChange={(event) => setPlaceQuery(event.target.value)}
                />
                <button
                  type="submit"
                  disabled={placeState === "loading" || !isGeocoderConfigured()}
                >
                  Search
                </button>
              </div>
            </form>
            {placeMessage ? (
              <p
                className={`map-form-message ${placeState === "error" ? "error" : ""}`}
                role="status"
              >
                {placeMessage}
              </p>
            ) : null}
            {placeResults.length > 0 ? (
              <ul className="place-results">
                {placeResults.map((result) => (
                  <li key={result.id}>
                    <button type="button" onClick={() => choosePlace(result)}>
                      {result.label}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            <p className="provider-note">
              {isGeocoderConfigured()
                ? `Explicit searches use ${geocoderName}; no autocomplete. © OpenStreetMap contributors.`
                : "Place search unavailable: no supported provider configured. Use coordinates instead."}
            </p>
          </details>

          <details className="map-tool-section">
            <summary>Enter bounding box</summary>
            <form className="bbox-form" onSubmit={handleBoundsSubmit} noValidate>
              {(
                [
                  ["West", west, setWest],
                  ["South", south, setSouth],
                  ["East", east, setEast],
                  ["North", north, setNorth],
                ] as const
              ).map(([label, value, setter]) => (
                <label key={label}>
                  {label}
                  <input
                    value={value}
                    onChange={(event) => setter(event.target.value)}
                    inputMode="decimal"
                  />
                </label>
              ))}
              <button type="submit">Use bounds</button>
            </form>
            <p className="provider-note">
              Order: west, south, east, north. Coordinates are WGS84 longitude/latitude.
            </p>
          </details>

          <section className="map-tool-section" aria-labelledby="geojson-tools-title">
            <h3 id="geojson-tools-title">GeoJSON</h3>
            <input
              className="sr-only"
              ref={importRef}
              type="file"
              aria-label="Import AOI GeoJSON"
              accept=".geojson,.json,application/geo+json,application/json"
              onChange={handleImport}
            />
            <div className="map-tool-button-grid">
              <button type="button" onClick={() => importRef.current?.click()}>
                Import
              </button>
              <button type="button" disabled={!selectedAoi} onClick={exportAoi}>
                Export
              </button>
              <button
                type="button"
                disabled={!selectedAoi}
                onClick={() => mapRef.current?.fitSelectedAoi()}
              >
                Fit AOI
              </button>
            </div>
            <p className="provider-note">
              One Polygon, one exterior ring, at most 500 positions and 1 MB. Holes, MultiPolygons,
              and antimeridian crossings are rejected.
            </p>
          </section>
        </aside>

        <div className="map-coordinate-readout" aria-live="off">
          {pointerCoordinates
            ? `Lon ${pointerCoordinates[0].toFixed(5)} · Lat ${pointerCoordinates[1].toFixed(5)}`
            : "Move over the map to read coordinates"}
        </div>

        <aside
          className={`aoi-summary ${displayedAoi ? "has-aoi" : ""}`}
          aria-label="Selected AOI summary"
        >
          {displayedAoi ? (
            <>
              <div className="aoi-summary-heading">
                <span className="context-card-icon">
                  <Icon name="target" />
                </span>
                <div>
                  <p>Active AOI</p>
                  <strong>{displayedAoi.name}</strong>
                </div>
                {previewAoi ? <span className="planned-badge">Editing</span> : null}
              </div>
              <dl>
                <div>
                  <dt>Approx. area</dt>
                  <dd>{formatAoiArea(displayedAoi.areaSquareMeters)}</dd>
                </div>
                <div>
                  <dt>Bounds</dt>
                  <dd>{formatAoiBounds(displayedAoi.bounds)}</dd>
                </div>
                <div>
                  <dt>Source</dt>
                  <dd>{sourceLabels[displayedAoi.source]}</dd>
                </div>
              </dl>
              <p className="aoi-persistence">{persistenceMessage}</p>
            </>
          ) : (
            <>
              <p>Area of interest</p>
              <strong>No area selected</strong>
              <span>Draw, enter bounds, or import GeoJSON. {persistenceMessage}</span>
            </>
          )}
        </aside>

        {geometryMessage ? (
          <div className="map-feedback" role="status" aria-live="polite">
            <span>{geometryMessage}</span>
            <button
              type="button"
              aria-label="Dismiss AOI message"
              onClick={() => setGeometryMessage(null)}
            >
              <Icon name="close" />
            </button>
          </div>
        ) : null}

        <div className="basemap-label">Basemap: {basemapName} · geographic context only</div>
      </section>
    </main>
  );
}

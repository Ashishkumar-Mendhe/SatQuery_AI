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
import type { AnalysisMode, SatelliteScene } from "@/lib/analysis-contracts";
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
import { validateAoiWithBackend } from "@/lib/aoi-validation-client";
import type { AoiValidationResponse } from "@/lib/aoi-validation-contracts";
import {
  getGeocoderProviderName,
  isGeocoderConfigured,
  type PlaceSearchResult,
  searchPlaces,
} from "@/lib/geocoder";
import { DEFAULT_IMAGERY_DISPLAY_SETTINGS, type ImageryMapState } from "@/lib/imagery-map-layer";
import { createImageryTileSet, ImageryTileClientError } from "@/lib/imagery-tile-client";
import { orderComparisonScenes } from "@/lib/scene-comparison";
import {
  type CatalogueSceneContext,
  catalogueSceneKey,
  createCatalogueSceneSelection,
  type SelectedCatalogueScene,
} from "@/lib/scene-selection";
import type { PairingPreferences } from "@/lib/temporal-contracts";
import type { SceneSelectionPersistenceState } from "@/lib/use-scene-selection-draft";
import { useTemporalPairing } from "@/lib/use-temporal-pairing";
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
import type { SceneFiltersDraft } from "@/lib/workspace-draft-storage";
import { ComparisonViewer, type ComparisonViewerProps } from "./comparison-viewer";
import {
  MapCanvas,
  type MapCanvasHandle,
  type MapInteraction,
  type MapLifecycle,
} from "./map-canvas";
import { selectedAoiToContract } from "@/lib/aoi";
import type { ChangeDetectionResult } from "@/lib/change-contracts";
import type { FusionResult } from "@/lib/fusion-contracts";
import { useChangeDetection } from "@/lib/use-change-detection";
import { useMultimodalFusion } from "@/lib/use-multimodal-fusion";
import { useRasterPreparation } from "@/lib/use-raster-preparation";
import { ChangeDetectionPanel } from "./change-detection-panel";
import { ImageryPreviewPanel } from "./imagery-preview-panel";
import { ModeSelector } from "./mode-selector";
import { MultimodalFusionPanel } from "./multimodal-fusion-panel";
import { RasterPreparationPanel } from "./raster-preparation-panel";
import { TemporalPairingPanel } from "./temporal-pairing-panel";
import { WorkflowDateFilterPanel } from "./workflow-date-filter-panel";
import { type BasemapId, getStoredBasemap } from "@/lib/basemap-config";
import { useImagery } from "@/lib/use-imagery";

export interface SceneContainerProps {
  selectedAoi: SelectedAoi | null;
  onSelectAoi: (aoi: SelectedAoi) => void;
  onClearAoi: () => void;
  persistenceMessage: string;
  mode?: AnalysisMode;
  onSelectMode?: (mode: AnalysisMode) => void;
  dateRange?: { start_date: string; end_date: string } | null;
  onDateRangeChange?: (dates: { start_date: string; end_date: string } | null) => void;
  beforeWindow?: { start_date: string; end_date: string } | null;
  onBeforeWindowChange?: (dates: { start_date: string; end_date: string } | null) => void;
  afterWindow?: { start_date: string; end_date: string } | null;
  onAfterWindowChange?: (dates: { start_date: string; end_date: string } | null) => void;
  selectedBeforeScene?: SatelliteScene | null;
  selectedAfterScene?: SatelliteScene | null;
  onSelectBeforeScene?: (scene: SatelliteScene | null) => void;
  onSelectAfterScene?: (scene: SatelliteScene | null) => void;
  pairingPreferences?: PairingPreferences | null;
  onPairingPreferencesChange?: (prefs: PairingPreferences | null) => void;
  sceneFilters?: SceneFiltersDraft;
  onSceneFiltersChange?: (filters: SceneFiltersDraft) => void;
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
  onChangeResult?: (result: ChangeDetectionResult | null) => void;
  onFusionResult?: (result: FusionResult | null) => void;
  onRasterPrepared?: (isPrepared: boolean) => void;
  onPairSelected?: (hasPair: boolean) => void;
  catalogueClient?: ImageryDiscoveryClient;
  mapCanvasComponent?: typeof MapCanvas;
  imageryTileClient?: (scene: ViewerSceneIdentity, signal?: AbortSignal) => Promise<TileMetadata>;
  comparisonViewerComponent?: (props: ComparisonViewerProps) => ReactNode;
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
  persistenceMessage: _persistenceMessage,
  mode,
  onSelectMode,
  dateRange,
  onDateRangeChange,
  beforeWindow,
  onBeforeWindowChange,
  afterWindow,
  onAfterWindowChange,
  selectedBeforeScene: _selectedBeforeScene,
  selectedAfterScene: _selectedAfterScene,
  onSelectBeforeScene,
  onSelectAfterScene,
  pairingPreferences,
  onPairingPreferencesChange: _onPairingPreferencesChange,
  sceneFilters,
  onSceneFiltersChange,
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
  onChangeResult,
  onFusionResult,
  onRasterPrepared,
  onPairSelected,
  catalogueClient,
  mapCanvasComponent,
  imageryTileClient = createImageryTileSet,
  comparisonViewerComponent,
}: SceneContainerProps) {
  const MapSurface = mapCanvasComponent ?? MapCanvas;
  const mapRef = useRef<MapCanvasHandle>(null);
  const importRef = useRef<HTMLInputElement>(null);
  const mutationRef = useRef(0);
  const imageryRequestRef = useRef<{ id: number; controller: AbortController } | null>(null);
  const imageryRequestSequence = useRef(0);
  const selectedSceneRef = useRef(selectedScene);
  const cameraRestorePendingRef = useRef<ViewerCamera | null>(null);
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
  const [activeTimelineKey, setActiveTimelineKey] = useState<string | null>(null);
  const [viewerCamera, setViewerCamera] = useState<ViewerCamera | null>(null);
  const [viewerPersistenceMessage, setViewerPersistenceMessage] = useState(
    "Scene selections and local settings are saved in this browser; temporary provider imagery URLs are refreshed dynamically on demand.",
  );
  const [pendingViewerRestore, setPendingViewerRestore] = useState<SavedViewerState | null>(null);
  const [validationResult, setValidationResult] = useState<AoiValidationResponse | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const viewerStateHydrated = useRef(false);
  selectedSceneRef.current = selectedScene;
  const displayedAoi = previewAoi ?? selectedAoi;
  const [activeBasemap, setActiveBasemap] = useState<BasemapId>("default");

  useEffect(() => {
    const stored = getStoredBasemap();
    if (stored !== "default") {
      setActiveBasemap(stored);
    }
  }, []);
  const [aoiCardCollapsed, setAoiCardCollapsed] = useState(false);
  const basemapDisplayName = useMemo(() => {
    switch (activeBasemap) {
      case "satellite":
        return "Satellite Hybrid (Esri Imagery + Boundaries)";
      case "terrain":
        return "Terrain (OpenTopoMap)";
      default:
        return (
          process.env.NEXT_PUBLIC_BASEMAP_NAME?.trim() ||
          (process.env.NEXT_PUBLIC_BASEMAP_STYLE_URL?.trim()
            ? "Configured basemap"
            : "Default (OpenFreeMap Liberty)")
        );
    }
  }, [activeBasemap]);
  const geocoderName = getGeocoderProviderName();
  const timeline = useMemo(
    () => (sceneContext?.isCurrent ? buildAcquisitionTimeline(sceneContext.scenes) : []),
    [sceneContext],
  );

  const phase3aImagery = useImagery({
    selectedAoi,
    sceneId: selectedScene?.scene.provider_asset_id,
    sensorType:
      (selectedScene?.scene as unknown as { sensor_type?: string })?.sensor_type ?? "optical",
  });

  const temporalPairing = useTemporalPairing({
    selectedAoi,
    beforeWindow: beforeWindow ?? null,
    afterWindow: afterWindow ?? null,
    sceneFilters: sceneFilters ?? {
      maxCloudCover: 20,
      sensorType: "optical",
      limit: 12,
    },
    preferences: pairingPreferences ?? null,
  });

  const effectiveBeforeScene = temporalPairing.selectedBeforeScene ?? _selectedBeforeScene;
  const effectiveAfterScene = temporalPairing.selectedAfterScene ?? _selectedAfterScene;

  const rasterPreparation = useRasterPreparation({
    aoi: selectedAoi ? selectedAoiToContract(selectedAoi) : null,
    mode: mode === "change_detection" || mode === "multimodal_analysis" ? "temporal" : "single",
    singleSceneId: selectedScene?.scene.provider_asset_id,
    beforeSceneId: effectiveBeforeScene?.id,
    afterSceneId: effectiveAfterScene?.id,
  });

  const changeDetection = useChangeDetection({
    aoi: selectedAoi ? selectedAoiToContract(selectedAoi) : null,
    preparedPair: rasterPreparation.preparedPair,
  });

  const multimodalFusion = useMultimodalFusion({
    aoi: selectedAoi ? selectedAoiToContract(selectedAoi) : null,
    initialOpticalResultId: changeDetection.result?.result_id ?? null,
  });

  useEffect(() => {
    onChangeResult?.(changeDetection.result);
  }, [changeDetection.result, onChangeResult]);

  useEffect(() => {
    onFusionResult?.(multimodalFusion.result);
  }, [multimodalFusion.result, onFusionResult]);

  useEffect(() => {
    onRasterPrepared?.(
      Boolean(
        rasterPreparation.preparedPair?.ready_for_analysis || rasterPreparation.preparedSingleAsset,
      ),
    );
  }, [rasterPreparation.preparedPair, rasterPreparation.preparedSingleAsset, onRasterPrepared]);

  useEffect(() => {
    onPairSelected?.(Boolean(effectiveBeforeScene && effectiveAfterScene));
  }, [effectiveBeforeScene, effectiveAfterScene, onPairSelected]);

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
    if (!selectedAoi) {
      setValidationResult(null);
      setIsValidating(false);
      return;
    }
    const controller = new AbortController();
    setIsValidating(true);
    const timer = window.setTimeout(async () => {
      try {
        const res = await validateAoiWithBackend(selectedAoi, undefined, controller.signal);
        if (!controller.signal.aborted) {
          setValidationResult(res);
          setIsValidating(false);
        }
      } catch {
        if (!controller.signal.aborted) {
          setIsValidating(false);
        }
      }
    }, 150);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [selectedAoi]);

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
        <div className="scene-header-title">
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
          imageryAsset={phase3aImagery.activeAsset}
          imageryDisplaySettings={{
            ...imageryDisplay,
            visible: phase3aImagery.activeAsset ? phase3aImagery.visible : imageryDisplay.visible,
            opacity: phase3aImagery.activeAsset ? phase3aImagery.opacity : imageryDisplay.opacity,
          }}
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
          onBasemapChange={setActiveBasemap}
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

          {mode && onSelectMode ? (
            <ModeSelector selectedMode={mode} onSelectMode={onSelectMode} />
          ) : null}

          {onDateRangeChange && onSceneFiltersChange ? (
            <WorkflowDateFilterPanel
              mode={mode ?? "visual_question_answering"}
              dateRange={dateRange ?? null}
              beforeWindow={beforeWindow ?? null}
              afterWindow={afterWindow ?? null}
              sceneFilters={
                sceneFilters ?? {
                  maxCloudCover: 20,
                  sensorType: "optical",
                  limit: 12,
                }
              }
              onDateRangeChange={onDateRangeChange}
              onBeforeWindowChange={onBeforeWindowChange}
              onAfterWindowChange={onAfterWindowChange}
              onSceneFiltersChange={onSceneFiltersChange}
            />
          ) : null}

          {mode === "change_detection" ? (
            <>
              <TemporalPairingPanel
                selectedAoi={selectedAoi}
                candidates={temporalPairing.candidates}
                searchState={temporalPairing.searchState}
                searchError={temporalPairing.searchError}
                selectedBeforeScene={temporalPairing.selectedBeforeScene}
                selectedAfterScene={temporalPairing.selectedAfterScene}
                validationResult={temporalPairing.validationResult}
                validationState={temporalPairing.validationState}
                validationError={temporalPairing.validationError}
                onSearchCandidates={temporalPairing.searchCandidates}
                onSelectBeforeScene={(scene) => {
                  temporalPairing.selectBeforeScene(scene);
                  onSelectBeforeScene?.(scene);
                }}
                onSelectAfterScene={(scene) => {
                  temporalPairing.selectAfterScene(scene);
                  onSelectAfterScene?.(scene);
                }}
                onApplyRecommendedPair={temporalPairing.applyRecommendedPair}
                onClearSelection={temporalPairing.clearSelection}
                disabled={!selectedAoi}
              />

              {effectiveBeforeScene && effectiveAfterScene ? (
                <RasterPreparationPanel
                  mode="temporal"
                  beforeSceneId={effectiveBeforeScene.id}
                  afterSceneId={effectiveAfterScene.id}
                  targetCrs={rasterPreparation.targetCrs}
                  onTargetCrsChange={rasterPreparation.setTargetCrs}
                  targetResolutionMeters={rasterPreparation.targetResolutionMeters}
                  onTargetResolutionChange={rasterPreparation.setTargetResolutionMeters}
                  resamplingMethod={rasterPreparation.resamplingMethod}
                  onResamplingMethodChange={rasterPreparation.setResamplingMethod}
                  strategy={rasterPreparation.strategy}
                  onStrategyChange={rasterPreparation.setStrategy}
                  isPreparing={rasterPreparation.isPreparing}
                  status={rasterPreparation.status}
                  preparedSingleAsset={rasterPreparation.preparedSingleAsset}
                  preparedPair={rasterPreparation.preparedPair}
                  error={rasterPreparation.error}
                  warnings={rasterPreparation.warnings}
                  blockingIssues={rasterPreparation.blockingIssues}
                  isReadyForAnalysis={rasterPreparation.isReadyForAnalysis}
                  showPreparedPreview={rasterPreparation.showPreparedPreview}
                  onTogglePreparedPreview={rasterPreparation.setShowPreparedPreview}
                  onStartPreparation={rasterPreparation.startPreparation}
                  onCancelPreparation={rasterPreparation.cancelPreparation}
                />
              ) : null}

              {rasterPreparation.preparedPair ? (
                <ChangeDetectionPanel
                  preparedPair={rasterPreparation.preparedPair}
                  methods={changeDetection.methods}
                  selectedMethod={changeDetection.selectedMethod}
                  onSelectMethod={changeDetection.setSelectedMethod}
                  currentDefinition={changeDetection.currentDefinition}
                  thresholdConfig={changeDetection.thresholdConfig}
                  onThresholdStrategyChange={changeDetection.setThresholdStrategy}
                  onPositiveThresholdChange={changeDetection.setPositiveThreshold}
                  onNegativeThresholdChange={changeDetection.setNegativeThreshold}
                  onStdMultiplierChange={changeDetection.setStdMultiplier}
                  onMinClusterSizeChange={changeDetection.setMinClusterSizePixels}
                  isCalculating={changeDetection.isCalculating}
                  result={changeDetection.result}
                  error={changeDetection.error}
                  warnings={changeDetection.warnings}
                  selectedRegion={changeDetection.selectedRegion}
                  onSelectRegion={changeDetection.setSelectedRegion}
                  overlayMode={changeDetection.overlayMode}
                  onOverlayModeChange={changeDetection.setOverlayMode}
                  overlayOpacity={changeDetection.overlayOpacity}
                  onOverlayOpacityChange={changeDetection.setOverlayOpacity}
                  onCalculateChange={changeDetection.calculateChange}
                  onCancelCalculation={changeDetection.cancelCalculation}
                  onReset={changeDetection.reset}
                />
              ) : null}
            </>
          ) : mode === "multimodal_analysis" ? (
            <MultimodalFusionPanel
              opticalResultId={multimodalFusion.opticalResultId}
              onSelectOpticalResultId={multimodalFusion.setOpticalResultId}
              sarBeforeAssetId={multimodalFusion.sarBeforeAssetId}
              onSelectSarBeforeAssetId={multimodalFusion.setSarBeforeAssetId}
              sarAfterAssetId={multimodalFusion.sarAfterAssetId}
              onSelectSarAfterAssetId={multimodalFusion.setSarAfterAssetId}
              temporalToleranceDays={multimodalFusion.temporalToleranceDays}
              onTemporalToleranceDaysChange={multimodalFusion.setTemporalToleranceDays}
              sarThresholdConfig={multimodalFusion.sarThresholdConfig}
              onSarThresholdConfigChange={multimodalFusion.setSarThresholdConfig}
              allowPartial={multimodalFusion.allowPartial}
              onAllowPartialChange={multimodalFusion.setAllowPartial}
              capabilities={multimodalFusion.capabilities}
              isExecuting={multimodalFusion.isExecuting}
              result={multimodalFusion.result}
              error={multimodalFusion.error}
              selectedRegionId={multimodalFusion.selectedRegionId}
              onSelectRegionId={multimodalFusion.selectRegion}
              overlayVisible={multimodalFusion.overlayVisible}
              onOverlayVisibleChange={multimodalFusion.setOverlayVisible}
              overlayOpacity={multimodalFusion.overlayOpacity}
              onOverlayOpacityChange={multimodalFusion.setOverlayOpacity}
              onExecuteFusion={() => multimodalFusion.executeFusion()}
              onClearResult={multimodalFusion.clearResult}
            />
          ) : (
            <>
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
                viewerLoading={
                  viewerLayer?.phase === "metadata" || viewerLayer?.phase === "loading"
                }
                onFitScene={(scene) => {
                  mapRef.current?.fitScene(scene.bbox);
                  setMobileToolsOpen(false);
                }}
              />
              {selectedScene ? (
                <ImageryPreviewPanel
                  scene={selectedScene.scene}
                  selectedAoi={selectedAoi}
                  activeAsset={phase3aImagery.activeAsset}
                  status={phase3aImagery.singleStatus}
                  error={phase3aImagery.singleError}
                  selectedPreset={phase3aImagery.selectedPreset}
                  productType={phase3aImagery.productType}
                  opacity={phase3aImagery.opacity}
                  visible={phase3aImagery.visible}
                  onRequestImagery={(preset, product) => {
                    if (selectedAoi) {
                      void phase3aImagery.fetchImagery(
                        selectedScene.scene.provider_asset_id,
                        selectedAoi,
                        preset,
                        product,
                      );
                    }
                  }}
                  onClearImagery={phase3aImagery.clearImagery}
                  onPresetChange={phase3aImagery.setSelectedPreset}
                  onProductTypeChange={phase3aImagery.setProductType}
                  onOpacityChange={phase3aImagery.setOpacity}
                  onVisibilityToggle={() => phase3aImagery.setVisible(!phase3aImagery.visible)}
                  onFitImagery={() => {
                    if (phase3aImagery.activeAsset) {
                      const b = phase3aImagery.activeAsset.bbox;
                      mapRef.current?.fitScene([b[0], b[1], b[2], b[3]]);
                    }
                  }}
                />
              ) : null}
              {mode === "spectral_analysis" && selectedScene ? (
                <RasterPreparationPanel
                  mode="single"
                  sceneId={selectedScene.scene.provider_asset_id}
                  targetCrs={rasterPreparation.targetCrs}
                  onTargetCrsChange={rasterPreparation.setTargetCrs}
                  targetResolutionMeters={rasterPreparation.targetResolutionMeters}
                  onTargetResolutionChange={rasterPreparation.setTargetResolutionMeters}
                  resamplingMethod={rasterPreparation.resamplingMethod}
                  onResamplingMethodChange={rasterPreparation.setResamplingMethod}
                  strategy={rasterPreparation.strategy}
                  onStrategyChange={rasterPreparation.setStrategy}
                  isPreparing={rasterPreparation.isPreparing}
                  status={rasterPreparation.status}
                  preparedSingleAsset={rasterPreparation.preparedSingleAsset}
                  preparedPair={rasterPreparation.preparedPair}
                  error={rasterPreparation.error}
                  warnings={rasterPreparation.warnings}
                  blockingIssues={rasterPreparation.blockingIssues}
                  isReadyForAnalysis={rasterPreparation.isReadyForAnalysis}
                  showPreparedPreview={rasterPreparation.showPreparedPreview}
                  onTogglePreparedPreview={rasterPreparation.setShowPreparedPreview}
                  onStartPreparation={rasterPreparation.startPreparation}
                  onCancelPreparation={rasterPreparation.cancelPreparation}
                />
              ) : null}
            </>
          )}

          <section
            className="map-tool-section comparison-selection"
            aria-labelledby="comparison-selection-title"
          >
            <h3 id="comparison-selection-title">Temporal Pair Comparison</h3>
            <p>
              Chronological ordering: Before is the earlier acquisition and After is the later
              acquisition.
            </p>
            <dl>
              <div>
                <dt>Before acquisition</dt>
                <dd>
                  {comparisonDraft.A
                    ? `${new Date(comparisonDraft.A.scene.acquisition.start).toISOString()} · ${comparisonDraft.A.identity.itemId}`
                    : "Not assigned"}
                </dd>
              </div>
              <div>
                <dt>After acquisition</dt>
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

          <section
            className="map-tool-section acquisition-timeline"
            aria-labelledby="timeline-title"
          >
            <h3 id="timeline-title">Acquisition timeline</h3>
            <p className="timeline-persistence-note">{viewerPersistenceMessage}</p>
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
                <ol
                  aria-label="Loaded acquisitions in chronological order"
                  className="timeline-list"
                >
                  {timeline.map((entry) => {
                    const selection = createCatalogueSceneSelection(
                      entry.scene,
                      sceneContext.fingerprint,
                      sceneContext.query,
                    );
                    const isSelected = selectedScene?.key === entry.key;
                    return (
                      <li
                        key={entry.key}
                        className={`timeline-entry ${isSelected ? "selected" : ""}`}
                      >
                        <button
                          type="button"
                          aria-current={activeTimelineKey === entry.key ? "true" : undefined}
                          onClick={() => selectTimelineEntry(entry.key)}
                          className="timeline-entry-btn"
                        >
                          <time dateTime={entry.timestamp}>
                            {new Date(entry.timestamp).toISOString()}
                          </time>
                          {entry.sameDateCount > 1
                            ? ` · acquisition ${entry.sameDateIndex} of ${entry.sameDateCount} on this date`
                            : ""}
                          <small title={entry.scene.provider_asset_id}>
                            {entry.scene.provider_asset_id}
                            {entry.scene.cloud_cover
                              ? ` · ${entry.scene.cloud_cover.percent.toFixed(1)}% cloud`
                              : ""}
                          </small>
                        </button>
                        <span className="timeline-assignment-actions">
                          {mode === "change_detection" ? (
                            <>
                              <button
                                type="button"
                                className={comparisonDraft.A?.key === entry.key ? "active" : ""}
                                onClick={() => assignComparison(selection, "A")}
                              >
                                Set Before
                              </button>
                              <button
                                type="button"
                                className={comparisonDraft.B?.key === entry.key ? "active" : ""}
                                onClick={() => assignComparison(selection, "B")}
                              >
                                Set After
                              </button>
                            </>
                          ) : mode === "multimodal_analysis" ? (
                            <>
                              <button
                                type="button"
                                className={comparisonDraft.A?.key === entry.key ? "active" : ""}
                                onClick={() => assignComparison(selection, "A")}
                              >
                                Set Optical
                              </button>
                              <button
                                type="button"
                                className={comparisonDraft.B?.key === entry.key ? "active" : ""}
                                onClick={() => assignComparison(selection, "B")}
                              >
                                Set SAR
                              </button>
                            </>
                          ) : (
                            <button
                              type="button"
                              className={isSelected ? "active" : ""}
                              onClick={() => {
                                onSelectScene(selection);
                                void openSceneInViewer(selection);
                              }}
                            >
                              {isSelected ? "Selected" : "Select image"}
                            </button>
                          )}
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
            <h3 id="draw-tools-title">Draw or edit</h3>
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

        {displayedAoi ? (
          <aside
            className={`aoi-summary has-aoi ${aoiCardCollapsed ? "collapsed" : ""}`}
            aria-label="Selected AOI summary"
          >
            <div className="aoi-summary-heading">
              <span className="context-card-icon">
                <Icon name="target" />
              </span>
              <div className="aoi-summary-title">
                <p>Active AOI</p>
                <strong>{displayedAoi.name}</strong>
              </div>
              {previewAoi ? (
                <span className="aoi-badge editing">Editing</span>
              ) : isValidating ? (
                <span className="aoi-badge validating">Validating…</span>
              ) : validationResult?.valid === false ? (
                <span className="aoi-badge invalid">Invalid</span>
              ) : validationResult && validationResult.warnings.length > 0 ? (
                <span className="aoi-badge warning">Valid (Notice)</span>
              ) : validationResult?.valid === true ? (
                <span className="aoi-badge valid">Valid</span>
              ) : null}
              <button
                type="button"
                className="icon-button aoi-collapse-toggle"
                aria-label={aoiCardCollapsed ? "Expand AOI details" : "Collapse AOI details"}
                onClick={() => setAoiCardCollapsed((c) => !c)}
              >
                <Icon name="chevron" className={aoiCardCollapsed ? "rotate-180" : undefined} />
              </button>
            </div>

            {!aoiCardCollapsed && (
              <>
                <dl>
                  <div>
                    <dt>Area</dt>
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

                <div className="aoi-card-actions">
                  {interaction === "edit" ? (
                    <>
                      <button
                        type="button"
                        className="aoi-action-btn active"
                        onClick={() => mapRef.current?.finishEdit()}
                      >
                        Finish edit
                      </button>
                      <button
                        type="button"
                        className="aoi-action-btn"
                        onClick={() => mapRef.current?.cancelEdit()}
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="aoi-action-btn"
                        onClick={() => mapRef.current?.beginEdit()}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="aoi-action-btn"
                        onClick={() => mapRef.current?.fitSelectedAoi()}
                      >
                        Fit AOI
                      </button>
                      <button type="button" className="aoi-action-btn danger" onClick={clearAoi}>
                        Remove
                      </button>
                    </>
                  )}
                </div>

                {validationResult?.errors && validationResult.errors.length > 0 ? (
                  <div className="aoi-validation-issues aoi-errors" role="alert">
                    {validationResult.errors.map((err) => (
                      <p key={`${err.code}-${err.message}`} className="aoi-issue-msg error">
                        <strong>{err.code}:</strong> {err.message}
                      </p>
                    ))}
                  </div>
                ) : null}

                {validationResult?.warnings && validationResult.warnings.length > 0 ? (
                  <div className="aoi-validation-issues aoi-warnings">
                    {validationResult.warnings.map((warn) => (
                      <p key={`${warn.code}-${warn.message}`} className="aoi-issue-msg warning">
                        <strong>{warn.code}:</strong> {warn.message}
                      </p>
                    ))}
                  </div>
                ) : null}
              </>
            )}
          </aside>
        ) : null}

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

        <div className="basemap-label">Basemap: {basemapDisplayName} · geographic context only</div>
      </section>
    </main>
  );
}

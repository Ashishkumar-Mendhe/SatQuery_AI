import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createAoiFromBounds, type SelectedAoi, serializeAoi } from "@/lib/aoi";
import type {
  CatalogueScene,
  CatalogueSearchRequest,
  CatalogueSearchResponse,
} from "@/lib/catalog-client";
import { DEFAULT_IMAGERY_DISPLAY_SETTINGS } from "@/lib/imagery-map-layer";
import {
  type CatalogueSceneContext,
  catalogueSceneKey,
  createCatalogueSceneSelection,
  type SelectedCatalogueScene,
} from "@/lib/scene-selection";
import type { TileMetadata, ViewerSceneIdentity } from "@/lib/viewer-contracts";
import { serializeViewerState, VIEWER_STATE_STORAGE_KEY } from "@/lib/viewer-state-storage";
import type { ComparisonViewerProps } from "./comparison-viewer";
import type { MapCanvasHandle, MapCanvasProps } from "./map-canvas";
import { SceneContainer } from "./scene-container";

const syntheticFitScene = vi.fn();
const syntheticPrepareImageryView = vi.fn();
const syntheticStartDrawing = vi.fn();

// This component checks UI/geometry boundaries only. Real WebGL/drawing needs browser verification.
const SyntheticMapCanvas = forwardRef<MapCanvasHandle, MapCanvasProps>(function SyntheticMap(
  {
    onLifecycleChange,
    sceneContext,
    selectedScene,
    hoveredSceneKey,
    imageryMetadata,
    imageryDisplaySettings,
    onSceneHover,
    onSceneSelect,
    onImageryStateChange,
  },
  ref,
) {
  const firstScene = sceneContext?.scenes[0];
  const firstKey = firstScene ? catalogueSceneKey(firstScene) : null;
  const notifiedTileSet = useRef<string | null>(null);
  useImperativeHandle(
    ref,
    () => ({
      startDrawing: syntheticStartDrawing,
      cancelEdit() {},
      cancelDrawing() {},
      beginEdit() {},
      finishEdit() {},
      fitSelectedAoi() {},
      prepareImageryView: syntheticPrepareImageryView,
      navigateToBounds() {},
      navigateTo() {},
      fitScene: syntheticFitScene,
      retry() {},
      getCamera() {
        return { center: [77.6, 13], zoom: 8, bearing: 0, pitch: 0 };
      },
      restoreCamera() {},
    }),
    [],
  );
  useEffect(() => {
    onLifecycleChange("ready", "Synthetic map ready");
  }, [onLifecycleChange]);
  useEffect(() => {
    if (imageryMetadata && notifiedTileSet.current !== imageryMetadata.tile_set_id) {
      notifiedTileSet.current = imageryMetadata.tile_set_id;
      onImageryStateChange("ready", "Imagery rendered from georeferenced raster tiles.");
    }
  }, [imageryMetadata, onImageryStateChange]);
  return (
    <div
      data-testid="synthetic-map"
      data-selected-scene={selectedScene?.key ?? ""}
      data-hovered-scene={hoveredSceneKey ?? ""}
      data-imagery-tile-set={imageryMetadata?.tile_set_id ?? ""}
      data-imagery-visible={String(imageryDisplaySettings.visible)}
      data-imagery-opacity={imageryDisplaySettings.opacity}
      data-imagery-brightness-min={imageryDisplaySettings.brightness_min}
      data-imagery-brightness-max={imageryDisplaySettings.brightness_max}
      data-imagery-contrast={imageryDisplaySettings.contrast}
      data-imagery-saturation={imageryDisplaySettings.saturation}
    >
      <button type="button" disabled={!firstKey} onClick={() => onSceneHover(firstKey)}>
        Hover first footprint
      </button>
      <button
        type="button"
        disabled={!firstKey}
        onClick={() => firstKey && onSceneSelect(firstKey)}
      >
        Select first footprint
      </button>
    </div>
  );
});

function Harness() {
  const [aoi, setAoi] = useState<SelectedAoi | null>(createAoiFromBounds([1, 1, 2, 2]));
  return (
    <SceneContainer
      selectedAoi={aoi}
      onSelectAoi={setAoi}
      onClearAoi={() => setAoi(null)}
      persistenceMessage="Synthetic local draft"
      sceneContext={null}
      selectedScene={null}
      hoveredSceneKey={null}
      sceneSelectionMessage={null}
      scenePersistenceState="empty"
      onSceneContextChange={() => {}}
      onHoverScene={() => {}}
      onSelectScene={() => {}}
      onClearScene={() => {}}
      onRefreshScene={() => {}}
      mapCanvasComponent={SyntheticMapCanvas}
    />
  );
}

function catalogueScene(itemId = "SHARED_ITEM_ID"): CatalogueScene {
  return {
    provider: { id: "earth-search", name: "Earth Search" },
    provider_asset_id: itemId,
    provider_asset_version: null,
    collection: { id: "sentinel-2-c1-l2a", title: "Sentinel-2 L2A" },
    acquisition: { start: "2025-06-01T05:30:00Z", end: "2025-06-01T05:30:00Z" },
    platform: "sentinel-2b",
    instruments: ["msi"],
    product_type: null,
    processing_level: "L2A",
    footprint: {
      type: "Polygon",
      coordinates: [
        [
          [77.5, 12.9],
          [77.7, 12.9],
          [77.7, 13.05],
          [77.5, 12.9],
        ],
      ],
    },
    bbox: [77.5, 12.9, 77.7, 13.05],
    cloud_cover: { percent: 4.2, source_field: "eo:cloud_cover", semantics: "scene" },
    spatial_resolution: [{ value: 10, unit: "metre", axis: "nominal", source_field: "gsd" }],
    bands: [],
    polarizations: [],
    preview: null,
    license: null,
    asset_access: { state: "provider_accessible", method: "provider_reference", reason: null },
    provenance: {
      adapter: "synthetic-test-adapter",
      adapter_version: "1.0",
      retrieved_at: "2025-06-01T06:00:00Z",
      source_record_id: itemId,
      source_record_version: null,
      metadata_digest_sha256: "c".repeat(64),
      fields: [
        {
          normalized_field: "provider_asset_id",
          source: "provider_record",
          source_field: "id",
          method: null,
        },
      ],
    },
    unavailable_fields: [],
  };
}

const syntheticCatalogueItem = catalogueScene();
const syntheticCatalogueClient = {
  listCollections: vi.fn().mockResolvedValue({
    schema_version: "1.0",
    provider: syntheticCatalogueItem.provider,
    items: [
      {
        id: syntheticCatalogueItem.collection.id,
        title: syntheticCatalogueItem.collection.title,
        description: null,
        license_name: null,
        license_url: null,
        temporal_start: null,
        temporal_end: null,
        platforms: [],
        instruments: ["msi"],
        spatial_resolutions_metres: [10],
      },
    ],
    returned_count: 1,
  }),
  search: vi.fn().mockImplementation(
    async (request: CatalogueSearchRequest) =>
      ({
        schema_version: "1.0",
        search_id: "11111111-1111-4111-8111-111111111111",
        status: "succeeded",
        query: request,
        provider: syntheticCatalogueItem.provider,
        items: [syntheticCatalogueItem],
        returned_count: 1,
        next_cursor: null,
        searched_at: "2025-06-01T06:00:00Z",
        attributions: ["Synthetic test attribution"],
        warnings: [],
      }) satisfies CatalogueSearchResponse,
  ),
};

function tileMetadata(item = "SHARED_ITEM_ID", tileSetId = "11111111-1111-4111-8111-111111111111") {
  return {
    schema_version: "1.0",
    tile_set_id: tileSetId,
    asset: {
      scene: {
        provider: "earth-search",
        collection: "sentinel-2-c1-l2a",
        item,
      },
      asset: "rgb-synthetic",
      asset_version: null,
    },
    render_preset: "natural-color",
    bounds: [77.5, 12.9, 77.7, 13.05] as [number, number, number, number],
    min_zoom: 0,
    max_zoom: 16,
    tile_size: 256 as const,
    media_type: "image/png" as const,
    url_template: "/api/v1/imagery/tiles/11111111-1111-4111-8111-111111111111/{z}/{x}/{y}.png",
    expires_at: "2099-01-01T00:00:00Z",
    attributions: ["Synthetic imagery attribution"],
    access: { state: "available" as const, reason: null },
  } satisfies TileMetadata;
}
const syntheticImageryTileClient = vi.fn().mockResolvedValue(tileMetadata());

beforeEach(() => {
  localStorage.clear();
  syntheticImageryTileClient.mockClear();
});

const viewerQuery: CatalogueSearchRequest = {
  schema_version: "1.0",
  provider: "earth-search",
  aoi: catalogueScene().footprint,
  acquisition: { start: "2025-01-01T00:00:00Z", end: "2025-12-31T23:59:59Z" },
  collections: ["sentinel-2-c1-l2a"],
  cloud_cover: null,
  limit: 6,
  cursor: null,
  sort: "acquired_desc",
};

function SwitchingViewerHarness({
  tileClient,
}: {
  tileClient: (scene: ViewerSceneIdentity, signal?: AbortSignal) => Promise<TileMetadata>;
}) {
  const first = createCatalogueSceneSelection(
    catalogueScene("FIRST_ITEM"),
    "viewer-query",
    viewerQuery,
  );
  const second = createCatalogueSceneSelection(
    catalogueScene("SECOND_ITEM"),
    "viewer-query",
    viewerQuery,
  );
  const [selected, setSelected] = useState(first);
  return (
    <>
      <button type="button" onClick={() => setSelected(second)}>
        Switch selected scene
      </button>
      <SceneContainer
        selectedAoi={createAoiFromBounds([77.5, 12.9, 77.7, 13.05])}
        onSelectAoi={() => {}}
        onClearAoi={() => {}}
        persistenceMessage="Synthetic local draft"
        sceneContext={null}
        selectedScene={selected}
        hoveredSceneKey={null}
        sceneSelectionMessage={null}
        scenePersistenceState="saved"
        onSceneContextChange={() => {}}
        onHoverScene={() => {}}
        onSelectScene={setSelected}
        onClearScene={() => {}}
        onRefreshScene={() => {}}
        catalogueClient={syntheticCatalogueClient}
        imageryTileClient={tileClient}
        mapCanvasComponent={SyntheticMapCanvas}
      />
    </>
  );
}

function ComparisonHarness() {
  const earlierScene = catalogueScene("EARLIER_ITEM");
  earlierScene.acquisition = { start: "2025-06-01T05:30:00Z", end: "2025-06-01T05:30:00Z" };
  const laterScene = catalogueScene("LATER_ITEM");
  laterScene.acquisition = { start: "2025-07-01T05:30:00Z", end: "2025-07-01T05:30:00Z" };
  const earlier = createCatalogueSceneSelection(earlierScene, "viewer-query", viewerQuery);
  const later = createCatalogueSceneSelection(laterScene, "viewer-query", viewerQuery);
  const [selected, setSelected] = useState(earlier);
  const SyntheticComparison = ({ sceneA, sceneB, onClose }: ComparisonViewerProps) => (
    <section aria-label="Two-date imagery comparison">
      <span>
        Comparison {sceneA.identity.itemId} then {sceneB.identity.itemId}
      </span>
      <button type="button" onClick={onClose}>
        Leave comparison
      </button>
    </section>
  );
  return (
    <>
      <button type="button" onClick={() => setSelected(later)}>
        Select later date
      </button>
      <SceneContainer
        selectedAoi={createAoiFromBounds([77.5, 12.9, 77.7, 13.05])}
        onSelectAoi={() => {}}
        onClearAoi={() => {}}
        persistenceMessage="Synthetic local draft"
        sceneContext={null}
        selectedScene={selected}
        hoveredSceneKey={null}
        sceneSelectionMessage={null}
        scenePersistenceState="saved"
        onSceneContextChange={() => {}}
        onHoverScene={() => {}}
        onSelectScene={setSelected}
        onClearScene={() => {}}
        onRefreshScene={() => {}}
        catalogueClient={syntheticCatalogueClient}
        imageryTileClient={syntheticImageryTileClient}
        mapCanvasComponent={SyntheticMapCanvas}
        comparisonViewerComponent={SyntheticComparison}
      />
    </>
  );
}

function CatalogueHarness() {
  const [aoi, setAoi] = useState<SelectedAoi | null>(
    createAoiFromBounds([77.5, 12.9, 77.7, 13.05]),
  );
  const [sceneContext, setSceneContext] = useState<CatalogueSceneContext | null>(null);
  const [selectedScene, setSelectedScene] = useState<SelectedCatalogueScene | null>(null);
  const [hoveredSceneKey, setHoveredSceneKey] = useState<string | null>(null);
  const [routeKey, setRouteKey] = useState(0);
  return (
    <>
      <button type="button" onClick={() => setRouteKey((current) => current + 1)}>
        Remount scene route
      </button>
      <SceneContainer
        key={routeKey}
        selectedAoi={aoi}
        onSelectAoi={(next) => {
          setAoi(next);
          setSceneContext((current) => (current ? { ...current, isCurrent: false } : null));
          setSelectedScene(null);
        }}
        onClearAoi={() => {
          setAoi(null);
          setSelectedScene(null);
        }}
        persistenceMessage="Synthetic local draft"
        sceneContext={sceneContext}
        selectedScene={selectedScene}
        hoveredSceneKey={hoveredSceneKey}
        sceneSelectionMessage={null}
        scenePersistenceState="saved"
        onSceneContextChange={setSceneContext}
        onHoverScene={setHoveredSceneKey}
        onSelectScene={setSelectedScene}
        onClearScene={() => setSelectedScene(null)}
        onRefreshScene={() => {}}
        catalogueClient={syntheticCatalogueClient}
        imageryTileClient={syntheticImageryTileClient}
        mapCanvasComponent={SyntheticMapCanvas}
      />
    </>
  );
}

function TimelineHarness({ hasMore = true }: { hasMore?: boolean }) {
  const firstScene = catalogueScene("TIMELINE_FIRST");
  firstScene.acquisition = { start: "2025-06-01T05:30:00Z", end: "2025-06-01T05:30:00Z" };
  const secondScene = catalogueScene("TIMELINE_SECOND");
  secondScene.acquisition = { start: "2025-06-01T08:30:00Z", end: "2025-06-01T08:30:00Z" };
  const [current, setCurrent] = useState(true);
  const [selected, setSelected] = useState<SelectedCatalogueScene | null>(null);
  const context: CatalogueSceneContext = {
    fingerprint: "viewer-query",
    isCurrent: current,
    scenes: [secondScene, firstScene],
    query: viewerQuery,
    hasMore,
  };
  return (
    <>
      <button type="button" onClick={() => setCurrent(false)}>
        Invalidate timeline
      </button>
      <output aria-label="Timeline selection">{selected?.identity.itemId ?? "none"}</output>
      <SceneContainer
        selectedAoi={createAoiFromBounds([77.5, 12.9, 77.7, 13.05])}
        onSelectAoi={() => {}}
        onClearAoi={() => {}}
        persistenceMessage="Synthetic local draft"
        sceneContext={context}
        selectedScene={selected}
        hoveredSceneKey={null}
        sceneSelectionMessage={null}
        scenePersistenceState="saved"
        onSceneContextChange={() => {}}
        onHoverScene={() => {}}
        onSelectScene={setSelected}
        onClearScene={() => setSelected(null)}
        onRefreshScene={() => {}}
        imageryTileClient={syntheticImageryTileClient}
        mapCanvasComponent={SyntheticMapCanvas}
      />
    </>
  );
}

describe("AOI workspace integration", () => {
  it("exposes persistent AOI drawing controls and clears the selection", () => {
    syntheticStartDrawing.mockClear();
    render(<Harness />);

    expect(screen.getByRole("toolbar", { name: "AOI drawing controls" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    fireEvent.click(screen.getByRole("button", { name: "Draw polygon" }));
    expect(syntheticStartDrawing).toHaveBeenNthCalledWith(1, "rectangle");
    expect(syntheticStartDrawing).toHaveBeenNthCalledWith(2, "polygon");

    fireEvent.click(screen.getByRole("button", { name: "Clear AOI" }));
    expect(screen.getAllByText("No area selected").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Search imagery" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Clear AOI" })).toBeDisabled();
  });

  it("restores stable viewer state and re-resolves imagery without stored tile access", async () => {
    const aoi = createAoiFromBounds([77.5, 12.9, 77.7, 13.05]);
    const restoredScene = catalogueScene("TIMELINE_SECOND");
    restoredScene.acquisition = { start: "2025-06-01T08:30:00Z", end: "2025-06-01T08:30:00Z" };
    localStorage.setItem(
      VIEWER_STATE_STORAGE_KEY,
      serializeViewerState({
        version: 1,
        saved_at: "2026-01-12T11:05:00Z",
        aoi_reference: {
          storage_key: "satquery.aoi-draft.v1",
          geometry_fingerprint: JSON.stringify(aoi.feature.geometry),
        },
        camera: { center: [77.6, 13], zoom: 8, bearing: 0, pitch: 0 },
        active_layer: {
          layer_id: "primary_imagery",
          asset: tileMetadata("TIMELINE_SECOND").asset,
          acquisition: restoredScene.acquisition,
          render_preset: "natural-color",
          display: DEFAULT_IMAGERY_DISPLAY_SETTINGS,
        },
        comparison_slots: null,
        comparison: null,
        timeline: {
          scenes: [
            {
              scene: tileMetadata("TIMELINE_SECOND").asset.scene,
              acquisition: restoredScene.acquisition,
            },
          ],
          selected_scene: tileMetadata("TIMELINE_SECOND").asset.scene,
        },
      }),
    );
    render(<TimelineHarness hasMore={false} />);
    await waitFor(() =>
      expect(syntheticImageryTileClient).toHaveBeenCalledWith(
        tileMetadata("TIMELINE_SECOND").asset.scene,
        expect.any(AbortSignal),
      ),
    );
    expect(screen.getByText(/imagery access was re-resolved/)).toBeVisible();
    expect(screen.getByRole("button", { name: /2025-06-01T08:30:00.000Z/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(localStorage.getItem(VIEWER_STATE_STORAGE_KEY)).not.toContain("url_template");
  });
  it("navigates actual duplicate-date timeline entries and invalidates stale results", async () => {
    render(<TimelineHarness />);
    const entries = screen.getAllByRole("listitem");
    expect(entries[0]).toHaveTextContent("TIMELINE_FIRST");
    expect(entries[0]).toHaveTextContent("acquisition 1 of 2 on this date");
    expect(screen.getByText(/More catalogue pages remain unloaded/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /2025-06-01T05:30:00.000Z/ }));
    await waitFor(() =>
      expect(screen.getByLabelText("Timeline selection")).toHaveTextContent("TIMELINE_FIRST"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() =>
      expect(screen.getByLabelText("Timeline selection")).toHaveTextContent("TIMELINE_SECOND"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Invalidate timeline" }));
    expect(
      screen.queryByRole("list", { name: "Loaded acquisitions in chronological order" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/load the current AOI timeline/)).toBeVisible();
  });
  it("assigns two dates, orders them, opens comparison, and cleans up on leave", async () => {
    render(<ComparisonHarness />);
    fireEvent.click(await screen.findByRole("button", { name: "Assign to comparison A" }));
    fireEvent.click(screen.getByRole("button", { name: "Select later date" }));
    fireEvent.click(await screen.findByRole("button", { name: "Assign to comparison B" }));
    fireEvent.click(screen.getByRole("button", { name: "Open comparison" }));
    expect(screen.getByText("Comparison EARLIER_ITEM then LATER_ITEM")).toBeVisible();
    expect(screen.getByText(/Before acquisition/).parentElement).toHaveTextContent("EARLIER_ITEM");
    expect(screen.getByText(/After acquisition/).parentElement).toHaveTextContent("LATER_ITEM");
    fireEvent.click(screen.getByRole("button", { name: "Leave comparison" }));
    expect(screen.queryByLabelText("Two-date imagery comparison")).not.toBeInTheDocument();
    expect(screen.getByText(/EARLIER_ITEM/)).toBeVisible();
    expect(screen.getAllByText(/LATER_ITEM/).length).toBeGreaterThan(0);
  });
  it("disregards outdated tile metadata after the selected scene changes", async () => {
    const pending: Array<(metadata: TileMetadata) => void> = [];
    const tileClient = vi.fn(
      () =>
        new Promise<TileMetadata>((resolve) => {
          pending.push(resolve);
        }),
    );
    render(<SwitchingViewerHarness tileClient={tileClient} />);

    fireEvent.click(await screen.findByRole("button", { name: "Open in viewer" }));
    await waitFor(() => expect(tileClient).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: "Switch selected scene" }));
    expect((await screen.findAllByText("SECOND_ITEM")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Open in viewer" }));
    await waitFor(() => expect(tileClient).toHaveBeenCalledTimes(2));

    await act(async () => {
      pending[0]?.(tileMetadata("FIRST_ITEM"));
      await Promise.resolve();
    });
    expect(screen.getByText("Resolving georeferenced imagery tiles…")).toBeVisible();
    await act(async () => {
      pending[1]?.(tileMetadata("SECOND_ITEM", "22222222-2222-4222-8222-222222222222"));
      await Promise.resolve();
    });
    await screen.findByText("Imagery rendered from georeferenced raster tiles.");
    expect(screen.getByLabelText("Active imagery overlay")).toHaveTextContent("SECOND_ITEM");
    expect(screen.getByLabelText("Active imagery overlay")).not.toHaveTextContent("FIRST_ITEM");
  });

  it("preserves selection on invalid bounds and accepts valid bounds", () => {
    render(<Harness />);
    fireEvent.click(screen.getByText("Enter bounding box"));
    fireEvent.change(screen.getByLabelText("West"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Use bounds" }));
    expect(screen.getByText(/West must be a number/)).toBeInTheDocument();
    expect(screen.getByText("1.00000, 1.00000, 2.00000, 2.00000")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("West"), { target: { value: "77.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Use bounds" }));
    expect(screen.getByText("77.50000, 12.90000, 77.70000, 13.05000")).toBeInTheDocument();
  });

  it("preserves selection on invalid import and accepts exported geometry", async () => {
    render(<Harness />);
    const input = screen.getByLabelText("Import AOI GeoJSON");
    fireEvent.change(input, {
      target: { files: [{ size: 10, text: async () => "invalid JSON" }] },
    });
    expect(await screen.findByText(/current AOI was preserved/)).toBeInTheDocument();
    expect(screen.getByText("1.00000, 1.00000, 2.00000, 2.00000")).toBeInTheDocument();
    const exported = serializeAoi(createAoiFromBounds([3, 3, 4, 4]));
    fireEvent.change(input, {
      target: { files: [{ size: exported.length, text: async () => exported }] },
    });
    expect(await screen.findByText("3.00000, 3.00000, 4.00000, 4.00000")).toBeInTheDocument();
  });

  it("does not resurrect a delayed import after clearing the AOI", async () => {
    render(<Harness />);
    let resolveImport: (value: string) => void = () => {};
    const pending = new Promise<string>((resolve) => {
      resolveImport = resolve;
    });
    fireEvent.change(screen.getByLabelText("Import AOI GeoJSON"), {
      target: { files: [{ size: 100, text: () => pending }] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Clear AOI" }));
    await act(async () => {
      resolveImport(serializeAoi(createAoiFromBounds([3, 3, 4, 4])));
      await pending;
    });
    expect(screen.getByRole("button", { name: "Export" })).toBeDisabled();
  });

  it("synchronizes footprint hover and selection, fitting, clearing, and remounts", async () => {
    syntheticFitScene.mockClear();
    syntheticPrepareImageryView.mockClear();
    render(<CatalogueHarness />);
    await screen.findByRole("option", { name: "Sentinel-2 L2A" });
    fireEvent.click(screen.getByRole("button", { name: "Search imagery" }));
    const itemId = await screen.findByText("SHARED_ITEM_ID");
    const card = itemId.closest("li");
    expect(card).not.toBeNull();

    fireEvent.mouseEnter(card as HTMLElement);
    await waitFor(() => expect(card).toHaveClass("hovered"));
    expect(screen.getByTestId("synthetic-map")).toHaveAttribute(
      "data-hovered-scene",
      catalogueSceneKey(catalogueScene()),
    );
    fireEvent.click(screen.getByRole("button", { name: "Select scene" }));
    await waitFor(() => expect(card).toHaveClass("selected"));
    expect(screen.getByText("Catalogue scene selected")).toBeVisible();
    expect(
      screen.getByText(/Selecting a scene opens its georeferenced raster tiles/),
    ).toBeVisible();
    expect(screen.getAllByText("77.50000, 12.90000, 77.70000, 13.05000").length).toBeGreaterThan(0);

    await screen.findByText("Imagery rendered from georeferenced raster tiles.");
    expect(syntheticPrepareImageryView).toHaveBeenCalledWith([77.5, 12.9, 77.7, 13.05]);
    expect(syntheticImageryTileClient).toHaveBeenCalledWith(
      {
        provider: "earth-search",
        collection: "sentinel-2-c1-l2a",
        item: "SHARED_ITEM_ID",
      },
      expect.any(AbortSignal),
    );

    fireEvent.click(screen.getByRole("button", { name: "Fit scene" }));
    expect(syntheticFitScene).toHaveBeenCalledWith([77.5, 12.9, 77.7, 13.05]);

    expect(screen.getByRole("button", { name: "Reload imagery" })).toBeEnabled();
    expect(screen.getByText("Attribution: Synthetic imagery attribution")).toBeVisible();
    fireEvent.click(screen.getByText("Display controls"));
    expect(
      screen.getByRole("option", { name: "Natural colour · red / green / blue" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("option", { name: "False colour unavailable · near-infrared not resolved" }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: "Layer visible" }));
    fireEvent.change(screen.getByRole("slider", { name: "Imagery opacity" }), {
      target: { value: "0.45" },
    });
    fireEvent.change(screen.getByRole("slider", { name: "Imagery brightness floor" }), {
      target: { value: "0.1" },
    });
    fireEvent.change(screen.getByRole("slider", { name: "Imagery brightness ceiling" }), {
      target: { value: "0.85" },
    });
    fireEvent.change(screen.getByRole("slider", { name: "Imagery contrast" }), {
      target: { value: "0.3" },
    });
    fireEvent.change(screen.getByRole("slider", { name: "Imagery saturation" }), {
      target: { value: "-0.2" },
    });
    expect(screen.getByTestId("synthetic-map")).toHaveAttribute("data-imagery-visible", "false");
    expect(screen.getByTestId("synthetic-map")).toHaveAttribute("data-imagery-opacity", "0.45");
    expect(screen.getByTestId("synthetic-map")).toHaveAttribute(
      "data-imagery-brightness-min",
      "0.1",
    );
    expect(screen.getByTestId("synthetic-map")).toHaveAttribute(
      "data-imagery-brightness-max",
      "0.85",
    );
    fireEvent.click(screen.getByRole("button", { name: "Reset display" }));
    expect(screen.getByTestId("synthetic-map")).toHaveAttribute("data-imagery-visible", "true");
    expect(screen.getByTestId("synthetic-map")).toHaveAttribute("data-imagery-opacity", "1");
    expect(screen.getByTestId("synthetic-map")).toHaveAttribute("data-imagery-brightness-min", "0");
    expect(screen.getByTestId("synthetic-map")).toHaveAttribute("data-imagery-brightness-max", "1");
    fireEvent.click(screen.getByRole("button", { name: "Remove imagery" }));
    expect(screen.queryByLabelText("Active imagery overlay")).not.toBeInTheDocument();
    expect(screen.getByText("Catalogue scene selected")).toBeVisible();
    expect(screen.getByText("Active AOI")).toBeVisible();
    expect(screen.getByText("1 scene loaded")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    await waitFor(() => expect(screen.getByText("No imagery selected")).toBeVisible());
    fireEvent.click(screen.getByRole("button", { name: "Select scene" }));

    fireEvent.click(screen.getByRole("button", { name: "Remount scene route" }));
    await waitFor(() =>
      expect(screen.getByTestId("synthetic-map")).toHaveAttribute(
        "data-selected-scene",
        catalogueSceneKey(catalogueScene()),
      ),
    );
    expect(
      screen.getByText(/Selecting a scene opens its georeferenced raster tiles/),
    ).toBeVisible();

    fireEvent.click(screen.getByText("Enter bounding box"));
    fireEvent.change(screen.getByLabelText("West"), { target: { value: "78" } });
    fireEvent.change(screen.getByLabelText("South"), { target: { value: "13" } });
    fireEvent.change(screen.getByLabelText("East"), { target: { value: "78.2" } });
    fireEvent.change(screen.getByLabelText("North"), { target: { value: "13.2" } });
    fireEvent.click(screen.getByRole("button", { name: "Use bounds" }));
    await waitFor(() => expect(screen.getByText("No imagery selected")).toBeVisible());
    expect(screen.getAllByText("78.00000, 13.00000, 78.20000, 13.20000").length).toBeGreaterThan(0);
  });
});

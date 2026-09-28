import type { Map as MapLibreMap } from "maplibre-gl";
import { describe, expect, it, vi } from "vitest";

import type { CatalogueScene, CatalogueSearchRequest } from "@/lib/catalog-client";
import {
  SCENE_FOOTPRINT_FILL_LAYER_ID,
  SCENE_FOOTPRINT_LINE_LAYER_ID,
  SCENE_FOOTPRINT_SOURCE_ID,
} from "@/lib/scene-footprints";
import { bindSceneFootprintInteractions, syncSceneFootprintLayers } from "@/lib/scene-map-layers";
import { catalogueSceneKey, createCatalogueSceneSelection } from "@/lib/scene-selection";

function scene(): CatalogueScene {
  return {
    provider: { id: "earth-search", name: "Earth Search" },
    provider_asset_id: "SCENE_MAP_TEST",
    provider_asset_version: null,
    collection: { id: "collection-a", title: null },
    acquisition: { start: "2025-01-01T00:00:00Z", end: "2025-01-01T00:00:00Z" },
    platform: null,
    instruments: [],
    product_type: null,
    processing_level: null,
    footprint: {
      type: "Polygon",
      coordinates: [
        [
          [10, 10],
          [11, 10],
          [11, 11],
          [10, 10],
        ],
      ],
    },
    bbox: [10, 10, 11, 11],
    cloud_cover: null,
    spatial_resolution: [],
    bands: [],
    polarizations: [],
    preview: null,
    license: null,
    asset_access: { state: "metadata_only", method: "none", reason: null },
    provenance: {
      adapter: "synthetic-test-adapter",
      adapter_version: "1.0",
      retrieved_at: "2025-01-01T01:00:00Z",
      source_record_id: "SCENE_MAP_TEST",
      source_record_version: null,
      metadata_digest_sha256: "e".repeat(64),
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

const query: CatalogueSearchRequest = {
  schema_version: "1.0",
  provider: "earth-search",
  aoi: scene().footprint,
  acquisition: { start: "2025-01-01T00:00:00Z", end: "2025-01-02T00:00:00Z" },
  collections: ["collection-a"],
  cloud_cover: null,
  limit: 6,
  cursor: null,
  sort: "acquired_desc",
};

class SyntheticMap {
  readonly sources = new Map<string, { setData: ReturnType<typeof vi.fn>; data: unknown }>();
  readonly layers = new Map<string, unknown>();
  readonly featureStates: Array<{ target: unknown; state: unknown }> = [];
  readonly listeners = new Map<string, (...args: never[]) => void>();
  readonly canvas = { style: { cursor: "" } };

  isStyleLoaded() {
    return true;
  }

  getSource(id: string) {
    return this.sources.get(id);
  }

  addSource(id: string, source: { data: unknown }) {
    this.sources.set(id, { data: source.data, setData: vi.fn() });
  }

  getLayer(id: string) {
    return this.layers.get(id);
  }

  addLayer(layer: { id: string }) {
    this.layers.set(layer.id, layer);
  }

  setFeatureState(target: unknown, state: unknown) {
    this.featureStates.push({ target, state });
  }

  getCanvas() {
    return this.canvas;
  }

  on(event: string, layer: string, listener: (...args: never[]) => void) {
    this.listeners.set(`${event}:${layer}`, listener);
  }

  off(event: string, layer: string, _listener: (...args: never[]) => void) {
    this.listeners.delete(`${event}:${layer}`);
  }

  emit(event: string, layer: string, sceneKey?: string) {
    this.listeners.get(`${event}:${layer}`)?.({
      features: sceneKey ? [{ properties: { sceneKey } }] : [],
    } as never);
  }
}

describe("MapLibre scene footprint layers", () => {
  it("uses real geometries, feature state, and restores layers after a style reset", () => {
    const item = scene();
    const selection = createCatalogueSceneSelection(item, "query-a", query);
    const map = new SyntheticMap();
    const context = { fingerprint: "query-a", isCurrent: true, scenes: [item], query };

    syncSceneFootprintLayers(map as unknown as MapLibreMap, context, selection, selection.key);

    expect(map.sources.has(SCENE_FOOTPRINT_SOURCE_ID)).toBe(true);
    expect(map.layers.has(SCENE_FOOTPRINT_FILL_LAYER_ID)).toBe(true);
    expect(map.layers.has(SCENE_FOOTPRINT_LINE_LAYER_ID)).toBe(true);
    expect(map.featureStates.at(-1)?.state).toEqual({ selected: true, hovered: true });

    map.sources.clear();
    map.layers.clear();
    syncSceneFootprintLayers(map as unknown as MapLibreMap, context, selection, null);
    expect(map.sources.has(SCENE_FOOTPRINT_SOURCE_ID)).toBe(true);
    expect(map.layers.has(SCENE_FOOTPRINT_FILL_LAYER_ID)).toBe(true);
    expect(map.layers.has(SCENE_FOOTPRINT_LINE_LAYER_ID)).toBe(true);
  });

  it("synchronizes delegated map hover/click and removes every listener", () => {
    const map = new SyntheticMap();
    const onHover = vi.fn();
    const onSelect = vi.fn();
    const key = catalogueSceneKey(scene());
    const cleanup = bindSceneFootprintInteractions(
      map as unknown as MapLibreMap,
      onHover,
      onSelect,
    );

    map.emit("mouseenter", SCENE_FOOTPRINT_FILL_LAYER_ID, key);
    map.emit("click", SCENE_FOOTPRINT_FILL_LAYER_ID, key);
    map.emit("mouseleave", SCENE_FOOTPRINT_FILL_LAYER_ID);
    expect(onHover).toHaveBeenNthCalledWith(1, key);
    expect(onHover).toHaveBeenLastCalledWith(null);
    expect(onSelect).toHaveBeenCalledWith(key);
    expect(map.canvas.style.cursor).toBe("");

    cleanup();
    expect(map.listeners.size).toBe(0);
  });
});

import type { Map as MapLibreMap } from "maplibre-gl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  applyImageryDisplaySettings,
  bindImageryLayerEvents,
  IMAGERY_LAYER_ID,
  IMAGERY_SOURCE_ID,
  removeImageryLayer,
  syncImageryLayer,
} from "@/lib/imagery-map-layer";
import type { TileMetadata } from "@/lib/viewer-contracts";

function metadata(): TileMetadata {
  return {
    schema_version: "1.0",
    tile_set_id: "11111111-1111-4111-8111-111111111111",
    asset: {
      scene: {
        provider: "earth-search",
        collection: "sentinel-2-c1-l2a",
        item: "S2_SYNTHETIC_MAP_LAYER",
      },
      asset: "rgb-synthetic",
      asset_version: null,
    },
    render_preset: "natural-color",
    bounds: [77.5, 12.9, 77.7, 13.05],
    min_zoom: 0,
    max_zoom: 16,
    tile_size: 256,
    media_type: "image/png",
    url_template: "/api/v1/imagery/tiles/11111111-1111-4111-8111-111111111111/{z}/{x}/{y}.png",
    expires_at: "2099-01-01T00:00:00Z",
    attributions: ["Earth & Search <unsafe>"],
    access: { state: "available", reason: null },
  };
}

class SyntheticMap {
  readonly sources = new Map<string, unknown>();
  readonly layers = new Map<string, unknown>();
  readonly beforeIds: Array<string | undefined> = [];
  readonly listeners = new Map<string, Set<(event: unknown) => void>>();
  readonly layoutProperties = new Map<string, unknown>();
  readonly paintProperties = new Map<string, unknown>();
  repaintCount = 0;

  isStyleLoaded() {
    return true;
  }
  getSource(id: string) {
    return this.sources.get(id);
  }
  addSource(id: string, source: unknown) {
    this.sources.set(id, source);
  }
  removeSource(id: string) {
    this.sources.delete(id);
  }
  getLayer(id: string) {
    return this.layers.get(id);
  }
  addLayer(layer: { id: string }, before?: string) {
    this.layers.set(layer.id, layer);
    this.beforeIds.push(before);
  }
  removeLayer(id: string) {
    this.layers.delete(id);
  }
  setLayoutProperty(_id: string, property: string, value: unknown) {
    this.layoutProperties.set(property, value);
  }
  setPaintProperty(_id: string, property: string, value: unknown) {
    this.paintProperties.set(property, value);
  }
  triggerRepaint() {
    this.repaintCount += 1;
  }
  on(event: string, listener: (event: unknown) => void) {
    const listeners = this.listeners.get(event) ?? new Set();
    listeners.add(listener);
    this.listeners.set(event, listeners);
  }
  off(event: string, listener: (event: unknown) => void) {
    this.listeners.get(event)?.delete(listener);
  }
  emit(event: string, payload: unknown) {
    for (const listener of this.listeners.get(event) ?? []) listener(payload);
  }
}

beforeEach(() => vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1"));
afterEach(() => vi.unstubAllEnvs());

describe("MapLibre imagery raster layer", () => {
  it("matches backend metadata and stays below scene/AOI overlays", () => {
    const map = new SyntheticMap();
    map.layers.set("satquery-scene-footprints-fill", {});
    syncImageryLayer(map as unknown as MapLibreMap, metadata());

    expect(map.sources.get(IMAGERY_SOURCE_ID)).toEqual(
      expect.objectContaining({
        type: "raster",
        tileSize: 256,
        bounds: [77.5, 12.9, 77.7, 13.05],
        minzoom: 0,
        maxzoom: 16,
        scheme: "xyz",
        attribution: "Earth &amp; Search &lt;unsafe&gt;",
      }),
    );
    expect(map.layers.has(IMAGERY_LAYER_ID)).toBe(true);
    expect(map.beforeIds).toEqual(["satquery-scene-footprints-fill"]);
    expect(map.repaintCount).toBe(1);
    expect(map.layers.get(IMAGERY_LAYER_ID)).toEqual(
      expect.objectContaining({
        layout: { visibility: "visible" },
        paint: expect.objectContaining({ "raster-opacity": 1 }),
      }),
    );

    removeImageryLayer(map as unknown as MapLibreMap);
    expect(map.sources.has(IMAGERY_SOURCE_ID)).toBe(false);
    expect(map.layers.has("satquery-scene-footprints-fill")).toBe(true);
  });

  it("applies bounded display settings without replacing the raster source", () => {
    const map = new SyntheticMap();
    syncImageryLayer(map as unknown as MapLibreMap, metadata());
    const source = map.sources.get(IMAGERY_SOURCE_ID);

    applyImageryDisplaySettings(map as unknown as MapLibreMap, {
      visible: false,
      opacity: 0.45,
      brightness_min: 0.1,
      brightness_max: 0.85,
      contrast: 0.3,
      saturation: -0.2,
    });

    expect(map.sources.get(IMAGERY_SOURCE_ID)).toBe(source);
    expect(map.layoutProperties.get("visibility")).toBe("none");
    expect(map.paintProperties.get("raster-opacity")).toBe(0.45);
    expect(map.paintProperties.get("raster-brightness-min")).toBe(0.1);
    expect(map.paintProperties.get("raster-brightness-max")).toBe(0.85);
    expect(map.paintProperties.get("raster-contrast")).toBe(0.3);
    expect(map.paintProperties.get("raster-saturation")).toBe(-0.2);
    expect(() =>
      applyImageryDisplaySettings(map as unknown as MapLibreMap, {
        visible: true,
        opacity: 1.1,
        brightness_min: 0,
        brightness_max: 1,
        contrast: 0,
        saturation: 0,
      }),
    ).toThrow();
  });

  it("classifies complete and partial loads and removes listeners", () => {
    const map = new SyntheticMap();
    const onState = vi.fn();
    const cleanup = bindImageryLayerEvents(map as unknown as MapLibreMap, onState);

    map.emit("error", { sourceId: IMAGERY_SOURCE_ID });
    expect(onState).toHaveBeenLastCalledWith("failed", expect.stringContaining("failed"));
    map.emit("sourcedata", { sourceId: IMAGERY_SOURCE_ID, sourceDataType: "content" });
    map.emit("error", { sourceId: IMAGERY_SOURCE_ID });
    expect(onState).toHaveBeenLastCalledWith("partial", expect.stringContaining("incomplete"));
    map.emit("sourcedata", { sourceId: IMAGERY_SOURCE_ID, isSourceLoaded: true });
    expect(onState).toHaveBeenLastCalledWith("ready", expect.stringContaining("rendered"));

    cleanup();
    expect([...map.listeners.values()].every((listeners) => listeners.size === 0)).toBe(true);
  });
});

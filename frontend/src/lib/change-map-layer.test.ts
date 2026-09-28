import type { Map as MapLibreMap } from "maplibre-gl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CHANGE_SOURCE_ID, syncChangeLayer } from "@/lib/change-map-layer";

class SyntheticMap {
  readonly sources = new Map<string, unknown>();
  readonly layers = new Map<string, unknown>();
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
  addLayer(layer: { id: string }) {
    this.layers.set(layer.id, layer);
  }
  removeLayer(id: string) {
    this.layers.delete(id);
  }
}

beforeEach(() => vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1"));
afterEach(() => vi.unstubAllEnvs());

describe("computed change map layer", () => {
  it("uses the authorized categorical tile route, exact bounds, and requested opacity", () => {
    const map = new SyntheticMap();
    syncChangeLayer(map as unknown as MapLibreMap, {
      artifactId: "10000000-0000-4000-8000-000000000091",
      bounds: [77.5, 12.9, 77.7, 13.1],
      opacity: 0.6,
      visible: true,
    });

    expect(map.sources.get(CHANGE_SOURCE_ID)).toEqual(
      expect.objectContaining({
        type: "raster",
        bounds: [77.5, 12.9, 77.7, 13.1],
        tiles: [
          "http://localhost:8000/api/v1/processing/artifacts/10000000-0000-4000-8000-000000000091/tiles/change/{z}/{x}/{y}.png",
        ],
      }),
    );
    expect(map.layers.get(CHANGE_SOURCE_ID)).toEqual(
      expect.objectContaining({ paint: { "raster-opacity": 0.6, "raster-fade-duration": 0 } }),
    );

    syncChangeLayer(map as unknown as MapLibreMap, null);
    expect(map.sources.size).toBe(0);
    expect(map.layers.size).toBe(0);
  });
});

import type { Map as MapLibreMap } from "maplibre-gl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  PREPARATION_MASK_SOURCE_PREFIX,
  syncPreparationMaskLayers,
} from "@/lib/preparation-mask-map-layer";

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

describe("prepared mask map layers", () => {
  it("uses only authorized artifact tile routes and preserves separate legends", () => {
    const map = new SyntheticMap();
    syncPreparationMaskLayers(map as unknown as MapLibreMap, {
      qualityArtifactIds: ["10000000-0000-4000-8000-000000000002"],
      bounds: [77.5, 12.9, 77.7, 13.1],
      usable: true,
      exclusions: true,
    });
    expect(map.sources.size).toBe(2);
    const sources = [...map.sources.values()] as Array<{ tiles: string[]; bounds: number[] }>;
    expect(
      sources.every((source) =>
        source.tiles[0].startsWith("http://localhost:8000/api/v1/processing/artifacts/"),
      ),
    ).toBe(true);
    expect(sources.map((source) => source.tiles[0])).toEqual(
      expect.arrayContaining([
        expect.stringContaining("/usable/{z}/{x}/{y}.png"),
        expect.stringContaining("/exclusions/{z}/{x}/{y}.png"),
      ]),
    );
    expect(sources.every((source) => source.bounds.join(",") === "77.5,12.9,77.7,13.1")).toBe(true);

    syncPreparationMaskLayers(map as unknown as MapLibreMap, null);
    expect(map.sources.size).toBe(0);
    expect(map.layers.size).toBe(0);
    expect(
      [...map.sources.keys()].some((id) => id.startsWith(PREPARATION_MASK_SOURCE_PREFIX)),
    ).toBe(false);
  });
});

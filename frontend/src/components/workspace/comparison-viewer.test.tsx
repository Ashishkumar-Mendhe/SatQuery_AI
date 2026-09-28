import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createAoiFromBounds } from "@/lib/aoi";
import type { CatalogueScene } from "@/lib/catalog-client";
import { createCatalogueSceneSelection } from "@/lib/scene-selection";
import type { TileMetadata } from "@/lib/viewer-contracts";

const maps: SyntheticMap[] = [];
class SyntheticMap {
  listeners = new Map<string, Array<(event?: unknown) => void>>();
  layers = new Set<string>();
  sources = new Set<string>();
  removed = false;
  resized = 0;
  jumps = 0;
  paint = new Map<string, unknown>();
  constructor() {
    maps.push(this);
    queueMicrotask(() => this.emit("load"));
  }
  on(name: string, callback: (event?: unknown) => void) {
    this.listeners.set(name, [...(this.listeners.get(name) ?? []), callback]);
  }
  off(name: string, callback: (event?: unknown) => void) {
    this.listeners.set(
      name,
      (this.listeners.get(name) ?? []).filter((entry) => entry !== callback),
    );
  }
  emit(name: string, event?: unknown) {
    this.listeners.get(name)?.forEach((callback) => {
      callback(event);
    });
  }
  isStyleLoaded() {
    return true;
  }
  addSource(id: string) {
    this.sources.add(id);
    queueMicrotask(() => {
      this.emit("sourcedataloading", { sourceId: id, sourceDataType: "metadata" });
      this.emit("sourcedata", { sourceId: id, sourceDataType: "content", isSourceLoaded: true });
    });
  }
  getSource(id: string) {
    return this.sources.has(id) ? {} : undefined;
  }
  removeSource(id: string) {
    this.sources.delete(id);
  }
  addLayer(layer: { id: string }) {
    this.layers.add(layer.id);
  }
  getLayer(id: string) {
    return this.layers.has(id) ? {} : undefined;
  }
  removeLayer(id: string) {
    this.layers.delete(id);
  }
  setPaintProperty(_id: string, property: string, value: unknown) {
    this.paint.set(property, value);
  }
  setLayoutProperty() {}
  triggerRepaint() {}
  fitBounds() {}
  jumpTo() {
    this.jumps += 1;
  }
  getCenter() {
    return { lng: 77.6, lat: 13 };
  }
  getZoom() {
    return 8;
  }
  getBearing() {
    return 0;
  }
  getPitch() {
    return 0;
  }
  resize() {
    this.resized += 1;
  }
  remove() {
    this.removed = true;
  }
}

vi.mock("maplibre-gl", () => ({ Map: SyntheticMap, setWorkerUrl: vi.fn() }));

import { ComparisonViewer } from "./comparison-viewer";

class SyntheticResizeObserver {
  static latest: SyntheticResizeObserver | null = null;
  callback: () => void;
  disconnected = false;
  constructor(callback: () => void) {
    this.callback = callback;
    SyntheticResizeObserver.latest = this;
  }
  observe() {}
  disconnect() {
    this.disconnected = true;
  }
}

function scene(item: string, acquired: string) {
  const value = {
    provider: { id: "earth-search", name: "Earth Search" },
    provider_asset_id: item,
    provider_asset_version: null,
    collection: { id: "sentinel-2-c1-l2a", title: "Sentinel-2 L2A" },
    acquisition: { start: acquired, end: acquired },
    platform: "sentinel-2",
    instruments: ["msi"],
    product_type: null,
    processing_level: "L2A",
    footprint: {
      type: "Polygon",
      coordinates: [
        [
          [77.5, 12.9],
          [77.7, 12.9],
          [77.7, 13.1],
          [77.5, 12.9],
        ],
      ],
    },
    bbox: [77.5, 12.9, 77.7, 13.1],
    cloud_cover: {
      percent: item === "A" ? 5 : 15,
      source_field: "eo:cloud_cover",
      semantics: "scene",
    },
    spatial_resolution: [{ value: 10, unit: "metre", axis: "nominal", source_field: "gsd" }],
    bands: [],
    polarizations: [],
    preview: null,
    license: null,
    asset_access: { state: "provider_accessible", method: "provider_reference", reason: null },
    provenance: {
      adapter: "synthetic",
      adapter_version: "1",
      retrieved_at: acquired,
      source_record_id: item,
      source_record_version: null,
      metadata_digest_sha256: "a".repeat(64),
      fields: [],
    },
    unavailable_fields: [],
  } as CatalogueScene;
  return createCatalogueSceneSelection(value, "query", {} as never);
}

function tile(item: string, id: string): TileMetadata {
  return {
    schema_version: "1.0",
    tile_set_id: id,
    asset: {
      scene: { provider: "earth-search", collection: "sentinel-2-c1-l2a", item },
      asset: `rgb-${item}`,
      asset_version: null,
    },
    render_preset: "natural-color",
    bounds: [77.5, 12.9, 77.7, 13.1],
    min_zoom: 0,
    max_zoom: 16,
    tile_size: 256,
    media_type: "image/png",
    url_template: `/api/v1/imagery/tiles/${id}/{z}/{x}/{y}.png`,
    expires_at: "2099-01-01T00:00:00Z",
    attributions: ["Synthetic"],
    access: { state: "available", reason: null },
  };
}

describe("comparison viewer", () => {
  beforeEach(() => {
    maps.length = 0;
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
    vi.stubGlobal("ResizeObserver", SyntheticResizeObserver);
  });
  it("renders two synchronized maps, supports divider/layout/settings, resize, and cleanup", async () => {
    const client = vi.fn(async ({ item }: { item: string }) =>
      tile(
        item,
        item === "A"
          ? "11111111-1111-4111-8111-111111111111"
          : "22222222-2222-4222-8222-222222222222",
      ),
    );
    const view = render(
      <ComparisonViewer
        sceneA={scene("A", "2025-01-01T00:00:00Z")}
        sceneB={scene("B", "2025-02-01T00:00:00Z")}
        selectedAoi={createAoiFromBounds([77.5, 12.9, 77.7, 13.1])}
        tileClient={client}
        onClose={() => {}}
      />,
    );
    await waitFor(() =>
      expect(
        screen.getByText("Scene A: Imagery rendered from georeferenced raster tiles."),
      ).toBeVisible(),
    );
    expect(maps).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Swipe" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Comparison scene A")).toHaveTextContent("A");
    expect(screen.getByLabelText("Comparison scene A")).toHaveTextContent("sentinel-2");
    expect(maps.every((map) => map.getLayer("satquery-aoi-polygon"))).toBe(true);
    fireEvent.change(screen.getByRole("slider", { name: "Comparison swipe divider" }), {
      target: { value: "70" },
    });
    expect(screen.getByRole("slider", { name: "Comparison swipe divider" })).toHaveValue("70");
    fireEvent.change(screen.getByRole("slider", { name: "Scene A opacity" }), {
      target: { value: "0.5" },
    });
    expect(screen.getByRole("slider", { name: "Scene B opacity" })).toHaveValue("0.5");
    fireEvent.click(screen.getByRole("checkbox", { name: "Link comparable settings" }));
    fireEvent.change(screen.getByRole("slider", { name: "Scene B opacity" }), {
      target: { value: "0.3" },
    });
    expect(screen.getByRole("slider", { name: "Scene A opacity" })).toHaveValue("0.5");
    fireEvent.click(screen.getByRole("button", { name: "Split" }));
    expect(screen.getByLabelText("Two-date imagery comparison")).toHaveClass("comparison-split");
    fireEvent.click(screen.getByRole("button", { name: "Blink" }));
    expect(screen.getByText("Showing scene A")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Show next scene" }));
    expect(screen.getByText("Showing scene B")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Swap display sides" }));
    maps[0].emit("move");
    expect(maps[1].jumps).toBe(1);
    SyntheticResizeObserver.latest?.callback();
    expect(maps[1].resized).toBe(1);
    view.unmount();
    expect(maps.every((map) => map.removed)).toBe(true);
    expect(SyntheticResizeObserver.latest?.disconnected).toBe(true);
  });

  it("keeps one side explicit when its asset is unavailable", async () => {
    const client = vi.fn(async ({ item }: { item: string }) => {
      if (item === "B") throw new Error("Scene B asset unavailable.");
      return tile("A", "11111111-1111-4111-8111-111111111111");
    });
    render(
      <ComparisonViewer
        sceneA={scene("A", "2025-01-01T00:00:00Z")}
        sceneB={scene("B", "2025-02-01T00:00:00Z")}
        selectedAoi={createAoiFromBounds([77.5, 12.9, 77.7, 13.1])}
        tileClient={client}
        onClose={() => {}}
      />,
    );
    expect(await screen.findByText("Scene B asset unavailable.")).toBeVisible();
    await waitFor(() =>
      expect(
        screen.getByText("Scene A: Imagery rendered from georeferenced raster tiles."),
      ).toBeVisible(),
    );
  });
});

import { describe, expect, it } from "vitest";

import type { CatalogueScene, CatalogueSearchRequest } from "@/lib/catalog-client";
import { buildSceneFootprintCollection } from "@/lib/scene-footprints";
import { catalogueSceneKey, createCatalogueSceneSelection } from "@/lib/scene-selection";

function scene(providerId: string, collectionId: string, itemId: string): CatalogueScene {
  return {
    provider: { id: providerId, name: providerId },
    provider_asset_id: itemId,
    provider_asset_version: null,
    collection: { id: collectionId, title: collectionId },
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
      source_record_id: itemId,
      source_record_version: null,
      metadata_digest_sha256: "d".repeat(64),
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

function query(collectionId: string): CatalogueSearchRequest {
  return {
    schema_version: "1.0",
    provider: "earth-search",
    aoi: scene("earth-search", collectionId, "query-scene").footprint,
    acquisition: { start: "2025-01-01T00:00:00Z", end: "2025-01-02T00:00:00Z" },
    collections: [collectionId],
    cloud_cover: null,
    limit: 6,
    cursor: null,
    sort: "acquired_desc",
  };
}

describe("catalogue scene workspace identity", () => {
  it("prevents collisions across providers and collections", () => {
    const first = scene("earth-search", "collection-a", "shared-item");
    const second = scene("earth-search", "collection-b", "shared-item");
    const third = scene("other-provider", "collection-a", "shared-item");

    expect(
      new Set([catalogueSceneKey(first), catalogueSceneKey(second), catalogueSceneKey(third)]).size,
    ).toBe(3);
    expect(createCatalogueSceneSelection(first, "query-a", query("collection-a")).identity).toEqual(
      {
        providerId: "earth-search",
        collectionId: "collection-a",
        itemId: "shared-item",
      },
    );
  });

  it("uses actual scene geometry and keeps stale and selected context distinct", () => {
    const currentScene = scene("earth-search", "collection-a", "current");
    const retainedScene = scene("earth-search", "collection-b", "retained");
    const collection = buildSceneFootprintCollection(
      {
        fingerprint: "query-a",
        isCurrent: false,
        scenes: [currentScene],
        query: query("collection-a"),
      },
      retainedScene,
    );

    expect(collection.features).toHaveLength(2);
    expect(collection.features[0].geometry).toBe(currentScene.footprint);
    expect(collection.features[0].properties.current).toBe(false);
    expect(collection.features[1].properties).toEqual({
      sceneKey: catalogueSceneKey(retainedScene),
      current: false,
    });
  });

  it("does not duplicate a selected scene already present in the current result set", () => {
    const selected = scene("earth-search", "collection-a", "selected");
    const collection = buildSceneFootprintCollection(
      {
        fingerprint: "query-a",
        isCurrent: true,
        scenes: [selected],
        query: query("collection-a"),
      },
      selected,
    );

    expect(collection.features).toHaveLength(1);
    expect(collection.features[0].properties.current).toBe(true);
  });
});

import { describe, expect, it } from "vitest";
import { buildAcquisitionTimeline } from "@/lib/acquisition-timeline";
import type { CatalogueScene } from "@/lib/catalog-client";

function scene(item: string, start: string): CatalogueScene {
  return {
    provider: { id: "earth-search", name: "Earth Search" },
    provider_asset_id: item,
    provider_asset_version: null,
    collection: { id: "sentinel-2-c1-l2a", title: "Sentinel-2" },
    acquisition: { start, end: start },
    platform: null,
    instruments: [],
    product_type: null,
    processing_level: null,
    footprint: {
      type: "Polygon",
      coordinates: [
        [
          [0, 0],
          [1, 0],
          [0, 1],
          [0, 0],
        ],
      ],
    },
    bbox: [0, 0, 1, 1],
    cloud_cover: null,
    spatial_resolution: [],
    bands: [],
    polarizations: [],
    preview: null,
    license: null,
    asset_access: { state: "provider_accessible", method: "provider_reference", reason: null },
    provenance: {
      adapter: "test",
      adapter_version: "1",
      retrieved_at: "2026-01-01T00:00:00Z",
      source_record_id: item,
      source_record_version: null,
      metadata_digest_sha256: "a".repeat(64),
      fields: [],
    },
    unavailable_fields: [],
  };
}

describe("acquisition timeline", () => {
  it("orders exact acquisitions and identifies multiple scenes on one calendar date", () => {
    const result = buildAcquisitionTimeline([
      scene("late", "2026-01-02T18:00:00Z"),
      scene("next", "2026-01-03T01:00:00Z"),
      scene("early", "2026-01-02T05:00:00Z"),
    ]);
    expect(result.map((entry) => entry.scene.provider_asset_id)).toEqual(["early", "late", "next"]);
    expect(result.slice(0, 2).map((entry) => [entry.sameDateIndex, entry.sameDateCount])).toEqual([
      [1, 2],
      [2, 2],
    ]);
  });

  it("uses stable identity to order distinct scenes with the same timestamp", () => {
    expect(
      buildAcquisitionTimeline([
        scene("b", "2026-01-02T05:00:00Z"),
        scene("a", "2026-01-02T05:00:00Z"),
      ]).map((entry) => entry.scene.provider_asset_id),
    ).toEqual(["a", "b"]);
  });
});

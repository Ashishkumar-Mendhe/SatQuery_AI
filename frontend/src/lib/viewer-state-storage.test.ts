import { describe, expect, it } from "vitest";
import { parseViewerState, serializeViewerState } from "@/lib/viewer-state-storage";

const state = {
  version: 1 as const,
  saved_at: "2026-01-12T11:05:00Z",
  aoi_reference: { storage_key: "satquery.aoi-draft.v1" as const, geometry_fingerprint: "polygon" },
  camera: { center: [77.6, 13] as [number, number], zoom: 8, bearing: 0, pitch: 0 },
  active_layer: null,
  comparison_slots: null,
  comparison: null,
  timeline: null,
};

describe("viewer state storage", () => {
  it("round trips validated browser-only state", () => {
    expect(parseViewerState(serializeViewerState(state))).toEqual(state);
  });

  it("rejects transient URLs and malformed state", () => {
    expect(() =>
      parseViewerState(JSON.stringify({ ...state, tile_url: "https://example.test/signed" })),
    ).toThrow("invalid");
    expect(() => parseViewerState("not-json")).toThrow("corrupt");
  });
});

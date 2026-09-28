import { describe, expect, it } from "vitest";

import { createAoiFromBounds } from "./aoi";
import { parseStoredAoi, serializeStoredAoi } from "./aoi-storage";

describe("AOI browser persistence", () => {
  it("round-trips a versioned validated draft", () => {
    const aoi = createAoiFromBounds([76, 12, 77, 13]);
    const stored = serializeStoredAoi(aoi, new Date("2026-09-09T00:00:00Z"));

    expect(parseStoredAoi(stored)).toEqual(aoi);
  });

  it.each([
    ["corrupt JSON", "{"],
    ["unknown version", JSON.stringify({ version: 2, aoi: {} })],
    ["invalid geometry", JSON.stringify({ version: 1, aoi: { source: "bbox", feature: {} } })],
  ])("rejects %s", (_label, value) => {
    expect(() => parseStoredAoi(value)).toThrow();
  });
});

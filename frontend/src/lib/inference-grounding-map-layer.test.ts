import { describe, expect, it } from "vitest";

import { utmToWgs84 } from "./inference-grounding-map-layer";

describe("inference grounding map coordinates", () => {
  it("converts supported northern and southern UTM coordinates to WGS84", () => {
    const [greenwichLongitude, equatorLatitude] = utmToWgs84("EPSG:32631", 166021.4431, 0);
    expect(greenwichLongitude).toBeCloseTo(0, 5);
    expect(equatorLatitude).toBeCloseTo(0, 5);

    const [southernLongitude, southernLatitude] = utmToWgs84("EPSG:32731", 166021.4431, 10_000_000);
    expect(southernLongitude).toBeCloseTo(0, 5);
    expect(southernLatitude).toBeCloseTo(0, 5);
  });

  it("rejects unsupported coordinate systems instead of inventing map placement", () => {
    expect(utmToWgs84("EPSG:3857", 0, 0)).toEqual([Number.NaN, Number.NaN]);
  });
});

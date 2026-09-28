import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearGeocoderCacheForTests, GeocoderError, searchPlaces } from "./geocoder";

beforeEach(() => {
  clearGeocoderCacheForTests();
  vi.stubEnv("NEXT_PUBLIC_GEOCODER_URL", "https://nominatim.example.test/search");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("place search", () => {
  it("does not request an unconfigured or public Nominatim provider", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("NEXT_PUBLIC_GEOCODER_URL", "");
    await expect(searchPlaces("Bengaluru")).rejects.toThrow(/no provider/);
    vi.stubEnv("NEXT_PUBLIC_GEOCODER_URL", "https://nominatim.openstreetmap.org/search");
    await expect(searchPlaces("Bengaluru")).rejects.toThrow(/application-wide/);
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("validates and converts provider coordinate and bbox ordering", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            place_id: 42,
            display_name: "Bengaluru, Karnataka, India",
            lon: "77.5946",
            lat: "12.9716",
            boundingbox: ["12.83", "13.14", "77.46", "77.78"],
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const results = await searchPlaces(" Bengaluru ");

    expect(results[0]).toMatchObject({
      longitude: 77.5946,
      latitude: 12.9716,
      bounds: [77.46, 12.83, 77.78, 13.14],
    });
    expect(String(fetchMock.mock.calls[0][0])).toContain("q=Bengaluru");
  });

  it("caches repeated explicit searches", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await searchPlaces("Pune");
    await searchPlaces(" pune ");

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("returns bounded validation and provider errors", async () => {
    await expect(searchPlaces("x")).rejects.toBeInstanceOf(GeocoderError);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("busy", { status: 429 })));
    await expect(searchPlaces("Mumbai")).rejects.toThrow(/HTTP 429/);
  });
});

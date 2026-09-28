import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  absoluteTileTemplate,
  createImageryTileSet,
  type ImageryTileClientError,
} from "./imagery-tile-client";

const scene = {
  provider: "earth-search",
  collection: "sentinel-2-c1-l2a",
  item: "S2_SYNTHETIC_VIEWER_CLIENT",
} as const;

function metadata(item: string = scene.item) {
  return {
    schema_version: "1.0",
    tile_set_id: "11111111-1111-4111-8111-111111111111",
    asset: {
      scene: { ...scene, item },
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
    expires_at: "2026-09-12T20:00:00Z",
    attributions: ["Synthetic test attribution"],
    access: { state: "available", reason: null },
  };
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("imagery tile client", () => {
  it("posts stable identity and returns a same-origin mediated template", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(metadata()), {
        status: 200,
        headers: { "Content-Type": "application/json", "X-Request-ID": "tiles-1" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await createImageryTileSet(scene);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      schema_version: "1.0",
      scene,
      render_preset: "natural-color",
      tile_size: 256,
    });
    expect(absoluteTileTemplate(result)).toBe(
      "http://localhost:8000/api/v1/imagery/tiles/11111111-1111-4111-8111-111111111111/{z}/{x}/{y}.png",
    );
  });

  it("rejects metadata for another scene and preserves classified API failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify(metadata("OTHER_ITEM")), { status: 200 }),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              error: {
                code: "TILE_ACCESS_EXPIRED",
                message: "Tile access expired.",
                request_id: "tiles-2",
                details: null,
                retryable: true,
              },
            }),
            { status: 410 },
          ),
        ),
    );

    await expect(createImageryTileSet(scene)).rejects.toMatchObject({
      kind: "unexpected_response",
    });
    await expect(createImageryTileSet(scene)).rejects.toEqual(
      expect.objectContaining<Partial<ImageryTileClientError>>({
        kind: "expired",
        requestId: "tiles-2",
        retryable: true,
      }),
    );
  });
});

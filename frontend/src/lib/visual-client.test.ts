import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  askVisualQuery,
  getImageManifest,
  getVisualCapabilities,
  VisualClientError,
} from "./visual-client";

describe("visual-client", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("fetches visual capabilities successfully", async () => {
    const mockCap = {
      supported_operations: ["describe", "locate", "compare"],
      supports_bounding_boxes: true,
      supports_temporal_comparison: true,
      max_images_per_query: 2,
      example_questions: ["Highlight the water body"],
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "X-Request-ID": "test-req" }),
      json: async () => mockCap,
    } as Response);

    const caps = await getVisualCapabilities();
    expect(caps.supports_bounding_boxes).toBe(true);
    expect(caps.max_images_per_query).toBe(2);
  });

  it("submits visual query and parses response", async () => {
    const mockResp = {
      answer_id: "vans-test-1",
      request_id: "vreq-1",
      context_fingerprint: "fp-test",
      answer: "A large water reservoir is visible.",
      observations: [
        {
          observation_id: "obs-1",
          input_image_id: "img-1",
          label: "Reservoir",
          description: "Clear water reflection",
          canonical_box: [0.1, 0.2, 0.5, 0.6],
        },
      ],
      manifests: [],
      grounded_regions: [],
      evidence_references: [],
      generation_mode: "llm_explanation",
      data_origin: "real",
      warnings: [],
      limitations: [],
      created_at: new Date().toISOString(),
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "X-Request-ID": "test-req" }),
      json: async () => mockResp,
    } as Response);

    const res = await askVisualQuery({
      question: "Highlight the water reservoir",
      context_snapshot: {
        snapshot_id: "snap-1",
        fingerprint: "fp-test",
      },
      selected_image_asset_ids: ["ast-1"],
      operation: "locate",
    });

    expect(res.answer_id).toBe("vans-test-1");
    expect(res.observations[0].label).toBe("Reservoir");
  });

  it("throws VisualClientError on 404/500 API errors", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      headers: new Headers({ "X-Request-ID": "test-err" }),
      json: async () => ({
        error: {
          code: "ASSET_NOT_FOUND",
          message: "Asset 'img-missing' not found.",
        },
      }),
    } as Response);

    await expect(
      askVisualQuery({
        question: "Where is the building?",
        context_snapshot: {
          snapshot_id: "snap-1",
          fingerprint: "fp-test",
        },
        selected_image_asset_ids: ["img-missing"],
      }),
    ).rejects.toThrow(VisualClientError);
  });

  it("fetches image manifest by id", async () => {
    const mockManifest = {
      manifest_id: "mf-1234",
      input_image_id: "img-single-5678",
      source_scene_id: "S2A_20260920",
      source_asset_id: "ast-preview-1",
      role: "single",
      content_hash: "sha256:abcdef123456",
      submitted_width: 800,
      submitted_height: 600,
      content_rectangle: [0, 0, 800, 600],
      rendering_type: "true_color",
      padding: [0, 0, 0, 0],
      data_origin: "real",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "X-Request-ID": "test-req" }),
      json: async () => mockManifest,
    } as Response);

    const mf = await getImageManifest("mf-1234");
    expect(mf.manifest_id).toBe("mf-1234");
  });
});

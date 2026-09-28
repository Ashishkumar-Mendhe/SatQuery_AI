import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useVisualQA } from "./use-visual-qa";

describe("useVisualQA", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("initializes with default state", () => {
    const { result } = renderHook(() =>
      useVisualQA({
        selectedAssetIds: ["ast-1"],
      }),
    );

    expect(result.current.question).toBe("");
    expect(result.current.operation).toBe("describe");
    expect(result.current.isSubmitting).toBe(false);
    expect(result.current.currentResponse).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("handles question submission and response", async () => {
    const mockResp = {
      answer_id: "vans-123",
      request_id: "vreq-1",
      context_fingerprint: "fp-1",
      answer: "A visible water reservoir.",
      observations: [
        {
          observation_id: "obs-1",
          input_image_id: "img-1",
          label: "Water Reservoir",
          description: "Clear water reflection",
          canonical_box: [0.1, 0.2, 0.4, 0.5],
        },
      ],
      manifests: [],
      grounded_regions: [
        {
          region_id: "greg-1",
          observation_id: "obs-1",
          manifest_id: "mf-1",
          canonical_box: [0.1, 0.2, 0.4, 0.5],
          pixel_box: [80, 120, 320, 300],
          clipping_status: "valid",
          transform_provenance: {},
          matched_evidence_ids: [],
          limitations: [],
        },
      ],
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

    const { result } = renderHook(() =>
      useVisualQA({
        selectedAssetIds: ["ast-1"],
      }),
    );

    await act(async () => {
      await result.current.askQuestion("Where is the water reservoir?");
    });

    expect(result.current.currentResponse?.answer_id).toBe("vans-123");
    expect(result.current.highlightedObservationId).toBe("obs-1");
    expect(result.current.highlightedRegion?.region_id).toBe("greg-1");
  });

  it("sets error when attempting to ask without selected assets", async () => {
    const { result } = renderHook(() =>
      useVisualQA({
        selectedAssetIds: [],
      }),
    );

    await act(async () => {
      await result.current.askQuestion("Where is the building?");
    });

    expect(result.current.error).toContain("Please select at least 1 image asset");
  });
});

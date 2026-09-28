import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { QueryClientError, askQuery, getQueryCapabilities } from "./query-client";

describe("query-client", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("getQueryCapabilities fetches and returns valid capabilities", async () => {
    const mockResponse = {
      supported_intents: ["change_summary", "spectral_summary"],
      supported_generation_modes: ["deterministic_summary"],
      example_questions: ["What changed between these dates?"],
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "X-Request-ID": "test-req-cap" }),
      json: async () => mockResponse,
    });

    const res = await getQueryCapabilities();
    expect(res.supported_intents).toHaveLength(2);
    expect(res.example_questions[0]).toBe("What changed between these dates?");
  });

  it("askQuery posts query and returns parsed answer", async () => {
    const mockAnswer = {
      answer_id: "ans-mock-1",
      request_id: "req-mock-1",
      context_fingerprint: "fp-mock",
      answer_status: "answerable",
      generation_mode: "deterministic_summary",
      plan: {
        intent: "change_summary",
        scope: "AOI",
        required_evidence: ["change_detection"],
        missing_inputs: [],
        approved_operations: [],
        routing_reason: "User asked about change",
        context_fingerprint: "fp-mock",
      },
      summary: "Vegetation decrease was measured across 20% of valid comparison area.",
      claims: [],
      evidence_references: ["ev-1"],
      spatial_references: ["reg-1"],
      quality_factors: [],
      warnings: [],
      limitations: [],
      suggested_actions: [],
      processing_trace: [],
      data_origin: "real",
      created_at: "2026-09-20T12:00:00Z",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "X-Request-ID": "req-mock-1" }),
      json: async () => mockAnswer,
    });

    const res = await askQuery({
      question: "What changed between these dates?",
      context_snapshot: {
        snapshot_id: "snap-1",
        fingerprint: "fp-mock",
        scene_ids: [],
      },
    });

    expect(res.answer_id).toBe("ans-mock-1");
    expect(res.summary).toContain("20% of valid comparison area");
  });

  it("throws QueryClientError on network failure", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network offline"));

    await expect(getQueryCapabilities()).rejects.toThrow(QueryClientError);
  });
});

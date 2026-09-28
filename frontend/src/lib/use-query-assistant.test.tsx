import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as queryClient from "./query-client";
import type { QueryAnswer } from "./query-contracts";
import { useQueryAssistant } from "./use-query-assistant";

const sampleAnswer: QueryAnswer = {
  answer_id: "ans-test-1",
  request_id: "req-test-1",
  context_fingerprint: "fp-test",
  answer_status: "answerable",
  generation_mode: "deterministic_summary",
  plan: {
    intent: "change_summary",
    scope: "AOI",
    required_evidence: ["change_detection"],
    missing_inputs: [],
    approved_operations: [],
    routing_reason: "User asked about change",
    context_fingerprint: "fp-test",
  },
  summary: "Measured decrease over 20% of valid comparison area.",
  claims: [
    {
      claim_id: "claim-1",
      kind: "measurement",
      evidence_ids: ["ev-1"],
      metric_references: ["loss_percent"],
      resolved_measurement: { loss_percent: 20.0 },
      region_ids: ["reg-1"],
      display_text: "Vegetation decreased across 20% of valid comparison area.",
      validation_status: "valid",
    },
  ],
  evidence_references: ["ev-1"],
  spatial_references: ["reg-1"],
  quality_factors: [],
  warnings: [],
  limitations: [],
  suggested_actions: [],
  processing_trace: [],
  data_origin: "real",
  created_at: new Date().toISOString(),
};

describe("useQueryAssistant", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(queryClient, "getQueryCapabilities").mockResolvedValue({
      supported_intents: ["change_summary", "spectral_summary"],
      supported_generation_modes: ["deterministic_summary"],
      example_questions: ["What changed between these dates?"],
    });
  });

  it("initializes with default state", () => {
    const { result } = renderHook(() => useQueryAssistant());
    expect(result.current.question).toBe("");
    expect(result.current.isSubmitting).toBe(false);
    expect(result.current.currentAnswer).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("handles askQuestion successfully", async () => {
    vi.spyOn(queryClient, "askQuery").mockResolvedValue(sampleAnswer);

    const { result } = renderHook(() =>
      useQueryAssistant({
        activeMode: "change_detection",
        activeChangeResultId: "chg-1",
      }),
    );

    act(() => {
      result.current.setQuestion("What changed between these dates?");
    });

    let ans: QueryAnswer | null = null;
    await act(async () => {
      ans = await result.current.askQuestion();
    });

    expect(ans).not.toBeNull();
    expect(result.current.currentAnswer?.answer_id).toBe("ans-test-1");
    expect(result.current.isSubmitting).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("rejects questions shorter than 3 characters", async () => {
    const { result } = renderHook(() => useQueryAssistant());

    act(() => {
      result.current.setQuestion("hi");
    });

    let ans: QueryAnswer | null = null;
    await act(async () => {
      ans = await result.current.askQuestion();
    });

    expect(ans).toBeNull();
    expect(result.current.error).toContain("at least 3 characters");
  });

  it("supports map highlight selection and clearing", () => {
    const { result } = renderHook(() => useQueryAssistant());

    act(() => {
      result.current.selectHighlight("reg-1", "ev-1");
    });
    expect(result.current.highlightedRegionId).toBe("reg-1");
    expect(result.current.highlightedEvidenceId).toBe("ev-1");

    act(() => {
      result.current.clearAnswer();
    });
    expect(result.current.highlightedRegionId).toBeNull();
    expect(result.current.currentAnswer).toBeNull();
  });
});

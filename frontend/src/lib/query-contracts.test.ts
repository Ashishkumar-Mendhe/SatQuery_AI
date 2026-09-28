import { describe, expect, it } from "vitest";

import {
  answerClaimSchema,
  queryAnswerSchema,
  queryCapabilitiesResponseSchema,
  queryPlanSchema,
  queryRequestSchema,
  workspaceContextSnapshotSchema,
} from "./query-contracts";

describe("query-contracts", () => {
  it("validates a complete WorkspaceContextSnapshot", () => {
    const snapshot = workspaceContextSnapshotSchema.parse({
      snapshot_id: "snap-123",
      fingerprint: "abc-xyz-789",
      aoi_geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.59, 12.97],
            [77.6, 12.97],
            [77.6, 12.98],
            [77.59, 12.98],
            [77.59, 12.97],
          ],
        ],
      },
      scene_ids: ["scene-1", "scene-2"],
      active_mode: "change_detection",
      active_change_result_id: "chg-123",
    });
    expect(snapshot.snapshot_id).toBe("snap-123");
    expect(snapshot.active_mode).toBe("change_detection");
  });

  it("validates QueryRequest constraints", () => {
    const validReq = queryRequestSchema.parse({
      question: "What changed between these two dates?",
      context_snapshot: {
        snapshot_id: "snap-1",
        fingerprint: "fp-1",
      },
    });
    expect(validReq.question).toBe("What changed between these two dates?");

    // Too short question
    expect(() =>
      queryRequestSchema.parse({
        question: "Hi",
        context_snapshot: { snapshot_id: "snap-1", fingerprint: "fp-1" },
      }),
    ).toThrow();
  });

  it("validates QueryPlan and AnswerClaim schemas", () => {
    const plan = queryPlanSchema.parse({
      intent: "change_summary",
      scope: "Temporal change over active AOI",
      required_evidence: ["change_detection"],
      missing_inputs: [],
      approved_operations: ["retrieve_change_metrics"],
      routing_reason: "User asked about temporal changes.",
      context_fingerprint: "fp-1",
    });
    expect(plan.intent).toBe("change_summary");

    const claim = answerClaimSchema.parse({
      claim_id: "claim-1",
      kind: "measurement",
      evidence_ids: ["ev-chg-1"],
      metric_references: ["loss_percent"],
      resolved_measurement: {
        loss_percent: 20.0,
        denominator: "1.0000 km² valid comparison area",
      },
      display_text:
        "Vegetation-related spectral response decreased across 20.0% of the valid comparison area.",
      validation_status: "valid",
    });
    expect(claim.kind).toBe("measurement");
    expect(claim.validation_status).toBe("valid");
  });

  it("validates a full QueryAnswer response", () => {
    const answer = queryAnswerSchema.parse({
      answer_id: "ans-1",
      request_id: "req-1",
      context_fingerprint: "fp-1",
      answer_status: "answerable",
      generation_mode: "deterministic_summary",
      plan: {
        intent: "change_summary",
        scope: "AOI",
        required_evidence: ["change_detection"],
        missing_inputs: [],
        approved_operations: [],
        routing_reason: "Detected change question",
        context_fingerprint: "fp-1",
      },
      summary: "Vegetation response decreased over 0.2000 km².",
      claims: [],
      evidence_references: ["ev-1"],
      spatial_references: ["region-1"],
      quality_factors: [],
      warnings: [],
      limitations: ["Spectral difference does not prove ground construction."],
      suggested_actions: [],
      processing_trace: [
        {
          stage: "query_routing",
          status: "success",
          duration_ms: 2,
          description: "Routed to change_summary",
        },
      ],
      data_origin: "real",
      created_at: "2026-09-20T12:00:00Z",
    });
    expect(answer.answer_id).toBe("ans-1");
    expect(answer.answer_status).toBe("answerable");
  });

  it("validates queryCapabilitiesResponseSchema", () => {
    const caps = queryCapabilitiesResponseSchema.parse({
      supported_intents: ["change_summary", "explain_quality"],
      supported_generation_modes: ["deterministic_summary", "llm_explanation"],
      example_questions: ["What changed?", "Why is confidence low?"],
    });
    expect(caps.supported_intents).toHaveLength(2);
  });
});

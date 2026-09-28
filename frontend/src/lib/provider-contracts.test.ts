import { describe, expect, it } from "vitest";
import {
  providerExecutionMetadataSchema,
  providerInfoSchema,
  providersStatusResponseSchema,
} from "./provider-contracts";

describe("provider-contracts schema suite", () => {
  it("validates ProviderInfo schema", () => {
    const validInfo = {
      provider_id: "mock",
      display_name: "Mock Satellite Provider",
      provider_type: "satellite",
      mode: "mock",
      status: "ready",
      capabilities: ["scene_search", "scene_metadata"],
      configured: true,
      healthy: true,
      data_origin: "mock",
      last_checked_at: "2026-09-18T12:00:00Z",
      message: "Ready for offline demonstration",
      limitations: ["Synthetic scenes only"],
    };

    const parsed = providerInfoSchema.safeParse(validInfo);
    expect(parsed.success).toBe(true);
  });

  it("validates ProviderExecutionMetadata schema", () => {
    const validExecution = {
      provider_id: "gemini",
      provider_mode: "real",
      data_origin: "fallback",
      requested_at: "2026-09-18T12:00:00Z",
      completed_at: "2026-09-18T12:00:02Z",
      duration_milliseconds: 2000,
      attempt_count: 1,
      fallback_used: true,
      fallback_reason: "Gemini API key not configured",
      cached: false,
      limitations: ["Synthetic reasoning fallback"],
    };

    const parsed = providerExecutionMetadataSchema.safeParse(validExecution);
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.fallback_used).toBe(true);
      expect(parsed.data.data_origin).toBe("fallback");
    }
  });

  it("validates complete ProvidersStatusResponse schema", () => {
    const validStatus = {
      environment: "development",
      contract_version: "1.0",
      satellite_provider: {
        provider_id: "earth-search",
        display_name: "Earth Search STAC",
        provider_type: "satellite",
        mode: "real",
        status: "ready",
        capabilities: ["scene_search", "optical_imagery"],
        configured: true,
        healthy: true,
        data_origin: "real",
      },
      ai_provider: {
        provider_id: "mock",
        display_name: "Mock AI Assistant",
        provider_type: "ai",
        mode: "mock",
        status: "ready",
        capabilities: ["visual_question_answering"],
        configured: true,
        healthy: true,
        data_origin: "mock",
      },
      processing_mode: "standard",
      mock_fallback_enabled: true,
      overall_readiness: true,
      timestamp: "2026-09-18T12:00:00Z",
    };

    const parsed = providersStatusResponseSchema.safeParse(validStatus);
    expect(parsed.success).toBe(true);
  });
});

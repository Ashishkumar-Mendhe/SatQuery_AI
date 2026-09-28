import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FusionClientError, getFusionCapabilities, getFusionOverlayUrl } from "./fusion-client";

describe("fusion-client", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("getFusionCapabilities fetches and returns valid capabilities", async () => {
    const mockResponse = {
      rules: [
        {
          rule_id: "co_observed_response_change",
          name: "Co-Observed Response Change",
          version: "1.0.0",
          description: "Test rule description",
          supported_modalities: ["Optical", "SAR"],
          disclaimer: "Evidence-level fusion only.",
        },
      ],
      supported_polarizations: ["VV", "VH"],
      supported_coefficients: ["sigma0", "gamma0"],
      version: "1.0.0",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "X-Request-ID": "test-req-1" }),
      json: async () => mockResponse,
    });

    const res = await getFusionCapabilities();
    expect(res.rules).toHaveLength(1);
    expect(res.rules[0].rule_id).toBe("co_observed_response_change");
  });

  it("getFusionOverlayUrl returns correct endpoint URL", () => {
    const url = getFusionOverlayUrl("fusion-12345");
    expect(url).toContain("/fusion/results/fusion-12345/overlay");
  });

  it("throws FusionClientError on network failure", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network connection dropped"));

    await expect(getFusionCapabilities()).rejects.toThrow(FusionClientError);
  });
});

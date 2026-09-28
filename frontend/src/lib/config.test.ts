import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { apiBaseUrl, getPublicConfig, PublicConfigError } from "./config";

describe("frontend public config", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it("returns default API base URL when not configured", () => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    expect(apiBaseUrl()).toBe("http://localhost:8000/api/v1");
  });

  it("validates valid NEXT_PUBLIC_API_BASE_URL", () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.satquery.ai/api/v1/";
    expect(apiBaseUrl()).toBe("https://api.satquery.ai/api/v1");
  });

  it("rejects invalid NEXT_PUBLIC_API_BASE_URL with credentials or wrong path", () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "https://user:pass@api.satquery.ai/api/v2";
    expect(() => apiBaseUrl()).toThrow(PublicConfigError);
  });

  it("parses environment and demo mode flags", () => {
    process.env.NEXT_PUBLIC_ENVIRONMENT = "staging";
    process.env.NEXT_PUBLIC_CONTRACT_VERSION = "1.0";
    process.env.NEXT_PUBLIC_DEMO_MODE = "true";

    const config = getPublicConfig();
    expect(config.environment).toBe("staging");
    expect(config.contractVersion).toBe("1.0");
    expect(config.isDemoMode).toBe(true);
  });
});

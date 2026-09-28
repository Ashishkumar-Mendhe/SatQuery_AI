import { describe, expect, it } from "vitest";
import { DATA_ORIGIN_CONFIG, getDataOriginDisplay } from "./data-origin";

describe("data-origin visual mapping", () => {
  it("provides distinct visual tokens for all data origins", () => {
    const origins = ["real", "mock", "fallback", "uploaded", "cached"] as const;

    for (const origin of origins) {
      const display = getDataOriginDisplay(origin);
      expect(display.label).toBeDefined();
      expect(display.badgeClass).toBeDefined();
      expect(display.dotColor).toBeDefined();
      expect(display.description).toBeDefined();
    }
  });

  it("accurately flags synthetic vs real data", () => {
    expect(getDataOriginDisplay("real").isSynthetic).toBe(false);
    expect(getDataOriginDisplay("uploaded").isSynthetic).toBe(false);
    expect(getDataOriginDisplay("cached").isSynthetic).toBe(false);

    expect(getDataOriginDisplay("mock").isSynthetic).toBe(true);
    expect(getDataOriginDisplay("fallback").isSynthetic).toBe(true);
  });

  it("distinguishes DEMO DATA from FALLBACK DATA", () => {
    expect(DATA_ORIGIN_CONFIG.mock.label).toBe("DEMO DATA");
    expect(DATA_ORIGIN_CONFIG.fallback.label).toBe("FALLBACK DATA");
  });
});

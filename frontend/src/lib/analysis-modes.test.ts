import { describe, expect, it } from "vitest";
import {
  ANALYSIS_MODE_DEFINITIONS,
  ANALYSIS_MODE_OPTIONS,
  PRIMARY_ANALYSIS_MODES,
  getAnalysisModeDefinition,
} from "./analysis-modes";

describe("analysis-modes", () => {
  it("provides definitions for primary analysis modes", () => {
    expect(ANALYSIS_MODE_OPTIONS.length).toBe(3);
    expect(ANALYSIS_MODE_DEFINITIONS.visual_question_answering.label).toBe("Single Image Analysis");
    expect(ANALYSIS_MODE_DEFINITIONS.change_detection.temporalRequirement).toBe("bi_temporal");
    expect(ANALYSIS_MODE_DEFINITIONS.spectral_analysis.badge).toBe("Multi-Band");
  });

  it("exposes the 3 primary workflow modes with correct descriptions and requirements", () => {
    expect(PRIMARY_ANALYSIS_MODES.length).toBe(3);
    const keys = PRIMARY_ANALYSIS_MODES.map((m) => m.key);
    expect(keys).toEqual(["visual_question_answering", "change_detection", "multimodal_analysis"]);

    const singleImage = PRIMARY_ANALYSIS_MODES.find((m) => m.key === "visual_question_answering");
    expect(singleImage).toBeDefined();
    expect(singleImage?.label).toBe("Single Image Analysis");
    expect(singleImage?.temporalRequirement).toBe("single");

    const changeDetection = PRIMARY_ANALYSIS_MODES.find((m) => m.key === "change_detection");
    expect(changeDetection).toBeDefined();
    expect(changeDetection?.label).toBe("Change Detection");
    expect(changeDetection?.temporalRequirement).toBe("bi_temporal");

    const multimodal = PRIMARY_ANALYSIS_MODES.find((m) => m.key === "multimodal_analysis");
    expect(multimodal).toBeDefined();
    expect(multimodal?.label).toBe("Optical + SAR Analysis");
  });

  it("returns correct definition by mode key", () => {
    const vqa = getAnalysisModeDefinition("visual_question_answering");
    expect(vqa.key).toBe("visual_question_answering");
    expect(vqa.status).toBe("ready");

    const change = getAnalysisModeDefinition("change_detection");
    expect(change.key).toBe("change_detection");
    expect(change.requiredInputs).toContain("Before & After Dates");
  });

  it("falls back gracefully for unknown keys", () => {
    // @ts-expect-error testing fallback for invalid key
    const fallback = getAnalysisModeDefinition("invalid_mode");
    expect(fallback.key).toBe("visual_question_answering");
  });
});

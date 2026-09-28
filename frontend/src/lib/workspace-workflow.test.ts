import { describe, expect, it } from "vitest";
import { createAoiFromBounds } from "./aoi";
import { deriveWorkflowState, isDateRangeValid } from "./workspace-workflow";

describe("workspace-workflow", () => {
  const sampleAoi = createAoiFromBounds([77.5, 12.9, 77.7, 13.1]);

  describe("isDateRangeValid", () => {
    it("validates correct date ranges", () => {
      expect(isDateRangeValid({ start_date: "2026-01-01", end_date: "2026-01-31" })).toBe(true);
      expect(
        isDateRangeValid({
          start_date: "2026-01-01T00:00:00Z",
          end_date: "2026-01-31T23:59:59Z",
        }),
      ).toBe(true);
    });

    it("rejects invalid date orders or empty strings", () => {
      expect(isDateRangeValid(null)).toBe(false);
      expect(isDateRangeValid({ start_date: "2026-02-01", end_date: "2026-01-01" })).toBe(false);
      expect(isDateRangeValid({ start_date: "", end_date: "2026-01-01" })).toBe(false);
      expect(isDateRangeValid({ start_date: "invalid", end_date: "2026-01-01" })).toBe(false);
    });
  });

  describe("deriveWorkflowState", () => {
    it("returns awaiting_aoi when no AOI is present", () => {
      const state = deriveWorkflowState({
        mode: "visual_question_answering",
        selectedAoi: null,
      });
      expect(state.step).toBe("awaiting_aoi");
      expect(state.stepNumber).toBe(1);
      expect(state.readiness.isAoiReady).toBe(false);
      expect(state.readiness.canDiscoverScenes).toBe(false);
      expect(state.nextAction.actionType).toBe("draw_aoi");
    });

    it("returns drawing_aoi when isDrawingAoi is true", () => {
      const state = deriveWorkflowState({
        mode: "visual_question_answering",
        selectedAoi: null,
        isDrawingAoi: true,
      });
      expect(state.step).toBe("drawing_aoi");
      expect(state.nextAction.actionLabel).toBe("Complete Drawing");
    });

    it("returns validating_aoi when isValidatingAoi is true", () => {
      const state = deriveWorkflowState({
        mode: "visual_question_answering",
        selectedAoi: sampleAoi,
        isValidatingAoi: true,
      });
      expect(state.step).toBe("validating_aoi");
      expect(state.readiness.isAoiReady).toBe(false);
    });

    it("returns aoi_invalid when validation response indicates invalid geometry", () => {
      const state = deriveWorkflowState({
        mode: "visual_question_answering",
        selectedAoi: sampleAoi,
        aoiValidationResult: {
          valid: false,
          normalized_geometry: null,
          bbox: null,
          area_km2: null,
          geometry_type: null,
          coordinate_count: 0,
          warnings: [],
          errors: [
            {
              code: "AOI_SELF_INTERSECTION",
              message: "Edges cross",
              severity: "error",
              field: null,
            },
          ],
          validation_version: "1.0",
        },
      });
      expect(state.step).toBe("aoi_invalid");
      expect(state.readiness.isAoiReady).toBe(false);
      expect(state.nextAction.actionType).toBe("fix_aoi");
    });

    it("returns awaiting_date_range when AOI is valid but dates are missing", () => {
      const state = deriveWorkflowState({
        mode: "visual_question_answering",
        selectedAoi: sampleAoi,
        aoiValidationResult: {
          valid: true,
          normalized_geometry: {
            type: "Polygon",
            coordinates: sampleAoi.feature.geometry.coordinates,
            crs: "EPSG:4326",
          },
          bbox: sampleAoi.bounds,
          area_km2: 50.5,
          geometry_type: "Polygon",
          coordinate_count: 5,
          warnings: [],
          errors: [],
          validation_version: "1.0",
        },
        dateRange: null,
      });
      expect(state.step).toBe("awaiting_date_range");
      expect(state.stepNumber).toBe(2);
      expect(state.readiness.isAoiReady).toBe(true);
      expect(state.readiness.isDateRangeReady).toBe(false);
      expect(state.nextAction.actionType).toBe("set_dates");
    });

    it("returns ready_for_scene_discovery when single scene mode has valid AOI and dates", () => {
      const state = deriveWorkflowState({
        mode: "visual_question_answering",
        selectedAoi: sampleAoi,
        dateRange: { start_date: "2026-01-01", end_date: "2026-01-31" },
        questionDraft: "Are there changes here?",
      });
      expect(state.step).toBe("ready_for_scene_discovery");
      expect(state.stepNumber).toBe(3);
      expect(state.readiness.isAoiReady).toBe(true);
      expect(state.readiness.isDateRangeReady).toBe(true);
      expect(state.readiness.isQuestionReady).toBe(true);
      expect(state.readiness.canDiscoverScenes).toBe(true);
      expect(state.nextAction.actionType).toBe("discover_scenes");
    });

    it("guides through change_detection pairing, raster preparation, and calculation", () => {
      // Step 3: Pairing
      const pairingState = deriveWorkflowState({
        mode: "change_detection",
        selectedAoi: sampleAoi,
        beforeWindow: { start_date: "2025-01-01", end_date: "2025-01-31" },
        afterWindow: { start_date: "2026-01-01", end_date: "2026-01-31" },
        hasSelectedPair: false,
      });
      expect(pairingState.step).toBe("ready_for_pairing");
      expect(pairingState.stepNumber).toBe(3);
      expect(pairingState.totalSteps).toBe(5);
      expect(pairingState.nextAction.actionType).toBe("pair_scenes");

      // Step 4: Raster Preparation
      const prepState = deriveWorkflowState({
        mode: "change_detection",
        selectedAoi: sampleAoi,
        beforeWindow: { start_date: "2025-01-01", end_date: "2025-01-31" },
        afterWindow: { start_date: "2026-01-01", end_date: "2026-01-31" },
        hasSelectedPair: true,
        isPairValidated: true,
        isRasterPrepared: false,
      });
      expect(prepState.step).toBe("ready_for_raster_prep");
      expect(prepState.stepNumber).toBe(4);
      expect(prepState.nextAction.actionType).toBe("prepare_raster");

      // Step 5: Change Calculation
      const calcState = deriveWorkflowState({
        mode: "change_detection",
        selectedAoi: sampleAoi,
        beforeWindow: { start_date: "2025-01-01", end_date: "2025-01-31" },
        afterWindow: { start_date: "2026-01-01", end_date: "2026-01-31" },
        hasSelectedPair: true,
        isPairValidated: true,
        isRasterPrepared: true,
        hasAnalysisResult: false,
      });
      expect(calcState.step).toBe("ready_for_analysis");
      expect(calcState.stepNumber).toBe(5);
      expect(calcState.nextAction.actionType).toBe("calculate_change");

      // Completed: Export Dossier
      const completedState = deriveWorkflowState({
        mode: "change_detection",
        selectedAoi: sampleAoi,
        beforeWindow: { start_date: "2025-01-01", end_date: "2025-01-31" },
        afterWindow: { start_date: "2026-01-01", end_date: "2026-01-31" },
        hasSelectedPair: true,
        isPairValidated: true,
        isRasterPrepared: true,
        hasAnalysisResult: true,
      });
      expect(completedState.step).toBe("analysis_completed");
      expect(completedState.stepNumber).toBe(5);
      expect(completedState.nextAction.actionType).toBe("export_report");
    });
  });
});

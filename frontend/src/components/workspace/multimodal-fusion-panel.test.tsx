import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DEFAULT_SAR_THRESHOLD_CONFIG, type FusionResult } from "@/lib/fusion-contracts";
import { MultimodalFusionPanel } from "./multimodal-fusion-panel";

describe("MultimodalFusionPanel", () => {
  const mockResult: FusionResult = {
    result_id: "fusion-123",
    rule_id: "co_observed_response_change",
    rule_definition: {
      rule_id: "co_observed_response_change",
      name: "Co-Observed Response Change",
      version: "1.0.0",
      description: "Test description",
      supported_modalities: ["Optical", "SAR"],
      disclaimer: "Evidence only",
    },
    compatibility: {
      status: "valid",
      timing: {
        optical_before_timestamp: "2026-09-01T10:00:00Z",
        optical_after_timestamp: "2026-09-15T10:00:00Z",
        sar_before_timestamp: "2026-09-03T10:00:00Z",
        sar_after_timestamp: "2026-09-17T10:00:00Z",
        optical_duration_days: 14.0,
        sar_duration_days: 14.0,
        before_offset_days: 2.0,
        after_offset_days: 2.0,
        interval_overlap_ratio: 0.8,
      },
      blocking_issues: [],
      warnings: [],
      method_version: "1.0.0",
    },
    coverage: {
      total_aoi_area_km2: 1.6,
      jointly_observable_area_km2: 1.0,
      optical_only_area_km2: 0.2,
      sar_only_area_km2: 0.1,
      neither_area_km2: 0.3,
      joint_percent_of_aoi: 62.5,
      optical_only_percent_of_aoi: 12.5,
      sar_only_percent_of_aoi: 6.25,
      neither_percent_of_aoi: 18.75,
      pixel_counts: {
        total_aoi_pixels: 16,
        jointly_observable_pixels: 10,
        optical_only_pixels: 2,
        sar_only_pixels: 1,
        neither_pixels: 3,
      },
    },
    joint_metrics: {
      joint_area_km2: 1.0,
      both_detect_change_area_km2: 0.2,
      optical_response_only_area_km2: 0.3,
      sar_response_only_area_km2: 0.1,
      neither_above_threshold_area_km2: 0.3,
      uncertain_area_km2: 0.1,
      both_detect_change_percent: 20.0,
      optical_response_only_percent: 30.0,
      sar_response_only_percent: 10.0,
      neither_above_threshold_percent: 30.0,
      uncertain_percent: 10.0,
      pixel_counts: {
        both_detect_change_pixels: 2,
        optical_response_only_pixels: 3,
        sar_response_only_pixels: 1,
        neither_above_threshold_pixels: 3,
        uncertain_pixels: 1,
      },
    },
    regions: [
      {
        id: "reg-1",
        state: "both_detect_change",
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [0, 0],
              [1, 0],
              [1, 1],
              [0, 1],
              [0, 0],
            ],
          ],
          crs: "EPSG:4326",
        },
        area_km2: 0.2,
        pixel_count: 2,
        rule_explanation: "Co-observed response change detected by both sensors.",
        confidence: 0.85,
        warnings: [],
      },
    ],
    observations: [
      {
        role: "optical_before",
        scene_id: "S2-B",
        acquisition_timestamp: "2026-09-01T10:00:00Z",
        prepared_asset_id: "opt-b",
        sensor: "Optical",
        data_origin: "real",
      },
      {
        role: "optical_after",
        scene_id: "S2-A",
        acquisition_timestamp: "2026-09-15T10:00:00Z",
        prepared_asset_id: "opt-a",
        sensor: "Optical",
        data_origin: "real",
      },
      {
        role: "sar_before",
        scene_id: "S1-B",
        acquisition_timestamp: "2026-09-03T10:00:00Z",
        prepared_asset_id: "sar-b",
        sensor: "Sentinel-1 SAR",
        data_origin: "real",
      },
      {
        role: "sar_after",
        scene_id: "S1-A",
        acquisition_timestamp: "2026-09-17T10:00:00Z",
        prepared_asset_id: "sar-a",
        sensor: "Sentinel-1 SAR",
        data_origin: "real",
      },
    ],
    evidence: [],
    quality: {
      score: 0.85,
      temporal_alignment_factor: 1.0,
      spatial_resolution_factor: 1.0,
      calibration_certainty_factor: 1.0,
      valid_coverage_factor: 0.625,
      factors: {},
      limitations: [],
    },
    warnings: [],
    blocking_issues: [],
    provenance: {
      pipeline_version: "1.0.0",
      source_asset_ids: ["opt-1", "sar-b", "sar-a"],
      source_scene_ids: ["S2", "S1"],
      operations: [],
      parameters: {},
      software: "SatQuery",
      started_at: "2026-09-20T10:00:00Z",
      completed_at: "2026-09-20T10:00:01Z",
      duration_milliseconds: 100.0,
      data_origin: "real",
    },
    data_origin: "real",
    created_at: "2026-09-20T10:00:01Z",
    interpretation_readiness: true,
  };

  it("renders observation stream inputs and action button", () => {
    render(
      <MultimodalFusionPanel
        opticalResultId={null}
        onSelectOpticalResultId={vi.fn()}
        sarBeforeAssetId={null}
        onSelectSarBeforeAssetId={vi.fn()}
        sarAfterAssetId={null}
        onSelectSarAfterAssetId={vi.fn()}
        temporalToleranceDays={30.0}
        onTemporalToleranceDaysChange={vi.fn()}
        sarThresholdConfig={DEFAULT_SAR_THRESHOLD_CONFIG}
        onSarThresholdConfigChange={vi.fn()}
        allowPartial={true}
        onAllowPartialChange={vi.fn()}
        capabilities={null}
        isExecuting={false}
        result={null}
        error={null}
        selectedRegionId={null}
        onSelectRegionId={vi.fn()}
        overlayVisible={true}
        onOverlayVisibleChange={vi.fn()}
        overlayOpacity={0.85}
        onOverlayOpacityChange={vi.fn()}
        onExecuteFusion={vi.fn()}
        onClearResult={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Multimodal Evidence Fusion" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run Multimodal Evidence Fusion/i })).toBeDisabled();
    expect(screen.getByText(/Scientific Grounding Disclaimer/i)).toBeInTheDocument();
  });

  it("renders coverage partitions, joint table, and fused candidate regions when result is provided", async () => {
    const onSelectRegionId = vi.fn();
    render(
      <MultimodalFusionPanel
        opticalResultId="opt-1"
        onSelectOpticalResultId={vi.fn()}
        sarBeforeAssetId="sar-b"
        onSelectSarBeforeAssetId={vi.fn()}
        sarAfterAssetId="sar-a"
        onSelectSarAfterAssetId={vi.fn()}
        temporalToleranceDays={30.0}
        onTemporalToleranceDaysChange={vi.fn()}
        sarThresholdConfig={DEFAULT_SAR_THRESHOLD_CONFIG}
        onSarThresholdConfigChange={vi.fn()}
        allowPartial={true}
        onAllowPartialChange={vi.fn()}
        capabilities={null}
        isExecuting={false}
        result={mockResult}
        error={null}
        selectedRegionId={null}
        onSelectRegionId={onSelectRegionId}
        overlayVisible={true}
        onOverlayVisibleChange={vi.fn()}
        overlayOpacity={0.85}
        onOverlayOpacityChange={vi.fn()}
        onExecuteFusion={vi.fn()}
        onClearResult={vi.fn()}
      />,
    );

    expect(screen.getByText(/AOI Coverage Partitioning/i)).toBeInTheDocument();
    expect(screen.getByText(/Jointly Observable \(J\)/i)).toBeInTheDocument();
    expect(screen.getAllByText(/1.0000 km²/i).length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText(/Both Sensors Detected Response Change/i).length,
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/20.0%/i)).toBeInTheDocument();

    const regionBtn = screen.getByRole("button", {
      name: /Both Sensors Detected Response Change/i,
    });
    await userEvent.click(regionBtn);
    expect(onSelectRegionId).toHaveBeenCalledWith("reg-1");
  });
});

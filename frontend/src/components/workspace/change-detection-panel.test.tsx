import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ChangeDetectionDefinition, ChangeDetectionResult } from "@/lib/change-contracts";
import type { PreparedTemporalPair } from "@/lib/preparation-contracts";
import { ChangeDetectionPanel } from "./change-detection-panel";

const mockDefinition: ChangeDetectionDefinition = {
  method: "ndvi_difference",
  display_name: "NDVI Difference",
  formula: "NDVI_after - NDVI_before",
  input_type: "spectral_index",
  directionality: "bidirectional",
  expected_range: [-2.0, 2.0],
  default_threshold_config: {
    strategy: "fixed",
    positive_threshold: 0.15,
    negative_threshold: -0.15,
    std_multiplier: 1.5,
    percentile_cutoff: 95.0,
    min_cluster_size_pixels: 5,
    simplify_tolerance_meters: 5.0,
  },
  supported_sensors: ["Sentinel-2"],
  description: "Detects vegetation changes.",
  limitations: "Phenology effects.",
  default_color_ramp: "RdYlGn",
  version: "1.0.0",
};

const mockPreparedPair: PreparedTemporalPair = {
  preparation_id: "prep-pair-1",
  pair_id: "pair-1",
  before_asset: {
    asset_id: "ast-bef",
    source_asset_ids: ["src-1"],
    scene_ids: ["S2A_before"],
    role: "single",
    format: "geotiff",
    crs: "EPSG:32643",
    bbox: [77.58, 12.96, 77.62, 13.0],
    width: 100,
    height: 100,
    pixel_size_x: 10.0,
    pixel_size_y: 10.0,
    transform: [10.0, 0.0, 500000.0, 0.0, -10.0, 1400000.0],
    band_count: 4,
    band_names: ["B02", "B03", "B04", "B08"],
    data_type: "float32",
    no_data_values: [-9999.0],
    valid_pixel_count: 10000,
    invalid_pixel_count: 0,
    valid_data_percent: 100.0,
    resolution_meters: 10.0,
    resampling_method: "bilinear",
    clip_applied: true,
    mask_applied: true,
    created_at: new Date().toISOString(),
    data_origin: "real",
    provenance: {
      pipeline_version: "1.0",
      source_asset_ids: ["src-1"],
      source_scene_ids: ["S2A_before"],
      operations: ["reproject"],
      parameters: {},
      software: "SatQuery Raster Harmonizer Engine v1.0",
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      duration_milliseconds: 500,
      data_origin: "real",
    },
    warnings: [],
  },
  after_asset: {
    asset_id: "ast-aft",
    source_asset_ids: ["src-2"],
    scene_ids: ["S2A_after"],
    role: "single",
    format: "geotiff",
    crs: "EPSG:32643",
    bbox: [77.58, 12.96, 77.62, 13.0],
    width: 100,
    height: 100,
    pixel_size_x: 10.0,
    pixel_size_y: 10.0,
    transform: [10.0, 0.0, 500000.0, 0.0, -10.0, 1400000.0],
    band_count: 4,
    band_names: ["B02", "B03", "B04", "B08"],
    data_type: "float32",
    no_data_values: [-9999.0],
    valid_pixel_count: 10000,
    invalid_pixel_count: 0,
    valid_data_percent: 100.0,
    resolution_meters: 10.0,
    resampling_method: "bilinear",
    clip_applied: true,
    mask_applied: true,
    created_at: new Date().toISOString(),
    data_origin: "real",
    provenance: {
      pipeline_version: "1.0",
      source_asset_ids: ["src-2"],
      source_scene_ids: ["S2A_after"],
      operations: ["reproject"],
      parameters: {},
      software: "SatQuery Raster Harmonizer Engine v1.0",
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      duration_milliseconds: 500,
      data_origin: "real",
    },
    warnings: [],
  },
  common_crs: "EPSG:32643",
  common_bbox: [77.58, 12.96, 77.62, 13.0],
  common_width: 100,
  common_height: 100,
  common_transform: [10.0, 0.0, 500000.0, 0.0, -10.0, 1400000.0],
  common_resolution_meters: 10.0,
  shared_valid_pixel_count: 10000,
  shared_valid_percent: 100.0,
  alignment_status: "aligned",
  quality: {
    valid_data_percent: 100.0,
    no_data_percent: 0.0,
    aoi_coverage_percent: 100.0,
    shared_coverage_percent: 100.0,
    resolution_consistency: 1.0,
    grid_alignment_score: 1.0,
    metadata_completeness: 1.0,
    quality_score: 1.0,
    factors: {},
    limitations: [],
  },
  warnings: [],
  blocking_issues: [],
  ready_for_analysis: true,
  created_at: new Date().toISOString(),
  processing_metadata: {},
};

const mockResult: ChangeDetectionResult = {
  result_id: "res-chg-101",
  pair_id: "pair-1",
  method: "ndvi_difference",
  definition: mockDefinition,
  before_scene_id: "S2A_before",
  after_scene_id: "S2A_after",
  before_asset_id: "ast-bef",
  after_asset_id: "ast-aft",
  difference_asset_id: "ast-diff",
  preview_asset_id: "ast-prev",
  classified_preview_asset_id: "ast-cls",
  metrics: {
    gain_area_km2: 0.25,
    loss_area_km2: 0.1,
    stable_area_km2: 0.65,
    net_change_area_km2: 0.15,
    shared_valid_area_km2: 1.0,
    pixel_counts: {
      total_aoi_pixels: 10000,
      shared_valid_pixels: 10000,
      gain_pixels: 2500,
      loss_pixels: 1000,
      stable_pixels: 6500,
      uncertain_pixels: 0,
      gain_percent: 25.0,
      loss_percent: 10.0,
      stable_percent: 65.0,
      uncertain_percent: 0.0,
    },
    positive_threshold_applied: 0.15,
    negative_threshold_applied: -0.15,
    threshold_strategy: "fixed",
  },
  regions: [
    {
      id: "reg-01",
      category: "spectral_gain",
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.58, 12.96],
            [77.59, 12.96],
            [77.59, 12.97],
            [77.58, 12.97],
            [77.58, 12.96],
          ],
        ],
        crs: "EPSG:4326",
      },
      area_km2: 0.12,
      pixel_count: 1200,
      mean_magnitude: 0.28,
      min_magnitude: 0.16,
      max_magnitude: 0.45,
      threshold_rule: "delta > 0.15",
      evidence_id: "evi-01",
      confidence: 0.94,
      warnings: [],
    },
  ],
  overlay: null,
  classified_overlay: null,
  evidence: [],
  confidence_breakdown: {
    overall: 0.92,
    data_quality: 0.95,
    temporal_quality: 0.9,
    spatial_quality: 0.95,
    model_confidence: 0.9,
    evidence_agreement: 0.9,
    factors: [],
    methodology: "Multi-factor",
    limitations: [],
  },
  confidence: 0.92,
  warnings: [],
  provenance: {
    pipeline_version: "1.0",
    source_asset_ids: ["ast-bef", "ast-aft"],
    source_scene_ids: ["S2A_before", "S2A_after"],
    operations: ["spectral_differencing"],
    parameters: {},
    software: "SatQuery Change Engine v1.0",
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
    duration_milliseconds: 850,
    data_origin: "real",
  },
  data_origin: "real",
  created_at: new Date().toISOString(),
};

describe("ChangeDetectionPanel", () => {
  it("renders panel header and initial state", () => {
    render(
      <ChangeDetectionPanel
        preparedPair={mockPreparedPair}
        methods={[mockDefinition]}
        selectedMethod="ndvi_difference"
        onSelectMethod={vi.fn()}
        currentDefinition={mockDefinition}
        thresholdConfig={{
          strategy: "fixed",
          positive_threshold: 0.15,
          negative_threshold: -0.15,
          std_multiplier: 1.5,
          percentile_cutoff: 95.0,
          min_cluster_size_pixels: 5,
          simplify_tolerance_meters: 5.0,
        }}
        onThresholdStrategyChange={vi.fn()}
        onPositiveThresholdChange={vi.fn()}
        onNegativeThresholdChange={vi.fn()}
        onStdMultiplierChange={vi.fn()}
        onMinClusterSizeChange={vi.fn()}
        isCalculating={false}
        result={null}
        error={null}
        warnings={[]}
        selectedRegion={null}
        onSelectRegion={vi.fn()}
        overlayMode="continuous"
        onOverlayModeChange={vi.fn()}
        overlayOpacity={0.85}
        onOverlayOpacityChange={vi.fn()}
        onCalculateChange={vi.fn()}
        onCancelCalculation={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByText(/Pixel-Level Change Detection & Evidence/i)).toBeInTheDocument();
    expect(screen.getByText(/Co-Registered & Ready/i)).toBeInTheDocument();
  });

  it("calls onCalculateChange when button is clicked", () => {
    const onCalc = vi.fn();
    render(
      <ChangeDetectionPanel
        preparedPair={mockPreparedPair}
        methods={[mockDefinition]}
        selectedMethod="ndvi_difference"
        onSelectMethod={vi.fn()}
        currentDefinition={mockDefinition}
        thresholdConfig={{
          strategy: "fixed",
          positive_threshold: 0.15,
          negative_threshold: -0.15,
          std_multiplier: 1.5,
          percentile_cutoff: 95.0,
          min_cluster_size_pixels: 5,
          simplify_tolerance_meters: 5.0,
        }}
        onThresholdStrategyChange={vi.fn()}
        onPositiveThresholdChange={vi.fn()}
        onNegativeThresholdChange={vi.fn()}
        onStdMultiplierChange={vi.fn()}
        onMinClusterSizeChange={vi.fn()}
        isCalculating={false}
        result={null}
        error={null}
        warnings={[]}
        selectedRegion={null}
        onSelectRegion={vi.fn()}
        overlayMode="continuous"
        onOverlayModeChange={vi.fn()}
        overlayOpacity={0.85}
        onOverlayOpacityChange={vi.fn()}
        onCalculateChange={onCalc}
        onCancelCalculation={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    const button = screen.getByRole("button", { name: /Calculate Change Detection/i });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(onCalc).toHaveBeenCalledTimes(1);
  });

  it("displays metrics and scientific disclaimer when result is present", () => {
    render(
      <ChangeDetectionPanel
        preparedPair={mockPreparedPair}
        methods={[mockDefinition]}
        selectedMethod="ndvi_difference"
        onSelectMethod={vi.fn()}
        currentDefinition={mockDefinition}
        thresholdConfig={{
          strategy: "fixed",
          positive_threshold: 0.15,
          negative_threshold: -0.15,
          std_multiplier: 1.5,
          percentile_cutoff: 95.0,
          min_cluster_size_pixels: 5,
          simplify_tolerance_meters: 5.0,
        }}
        onThresholdStrategyChange={vi.fn()}
        onPositiveThresholdChange={vi.fn()}
        onNegativeThresholdChange={vi.fn()}
        onStdMultiplierChange={vi.fn()}
        onMinClusterSizeChange={vi.fn()}
        isCalculating={false}
        result={mockResult}
        error={null}
        warnings={[]}
        selectedRegion={null}
        onSelectRegion={vi.fn()}
        overlayMode="continuous"
        onOverlayModeChange={vi.fn()}
        overlayOpacity={0.85}
        onOverlayOpacityChange={vi.fn()}
        onCalculateChange={vi.fn()}
        onCancelCalculation={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByText(/Scientific Change Evidence:/i)).toBeInTheDocument();
    expect(screen.getByText(/0.250 km²/i)).toBeInTheDocument();
    expect(screen.getByText(/25.0% of valid/i)).toBeInTheDocument();
    expect(screen.getByText(/Candidate Change Regions/i)).toBeInTheDocument();
    expect(screen.getByText("reg-01")).toBeInTheDocument();
  });
});

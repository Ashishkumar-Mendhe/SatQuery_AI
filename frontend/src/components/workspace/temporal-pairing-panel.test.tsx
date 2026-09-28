import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { SatelliteScene } from "@/lib/analysis-contracts";
import type {
  TemporalPairValidationResult,
  TemporalSceneCandidates,
} from "@/lib/temporal-contracts";
import { TemporalPairingPanel } from "./temporal-pairing-panel";

describe("TemporalPairingPanel Component", () => {
  const sampleBeforeScene: SatelliteScene = {
    id: "S2A_20250101",
    provider: "earth-search",
    collection: "sentinel-2-c1-l2a",
    acquisition_time: "2025-01-01T05:20:00Z",
    sensor_type: "multispectral",
    platform: "Sentinel-2A",
    cloud_cover: 2.5,
    bbox: [77.5, 12.8, 77.7, 13.1],
    available_bands: ["B02", "B03", "B04", "B08"],
    resolution_meters: 10,
    metadata: { data_origin: "real" },
  };

  const sampleAfterScene: SatelliteScene = {
    id: "S2B_20250120",
    provider: "earth-search",
    collection: "sentinel-2-c1-l2a",
    acquisition_time: "2025-01-20T05:20:00Z",
    sensor_type: "multispectral",
    platform: "Sentinel-2B",
    cloud_cover: 3.5,
    bbox: [77.5, 12.8, 77.7, 13.1],
    available_bands: ["B02", "B03", "B04", "B08"],
    resolution_meters: 10,
    metadata: { data_origin: "real" },
  };

  const sampleCandidates: TemporalSceneCandidates = {
    search_id: "search-123",
    before_scenes: [sampleBeforeScene],
    after_scenes: [sampleAfterScene],
    provider_id: "earth-search",
    execution: {
      provider_id: "earth-search",
      provider_mode: "real",
      data_origin: "real",
      requested_at: "2026-09-20T00:00:00Z",
      completed_at: "2026-09-20T00:00:01Z",
      duration_milliseconds: 100,
      attempt_count: 1,
      fallback_used: false,
      cached: false,
      limitations: [],
    },
    warnings: [],
    data_origin: "real",
    generated_at: "2026-09-20T00:00:00Z",
    recommended_pair: {
      before_scene_id: "S2A_20250101",
      after_scene_id: "S2B_20250120",
      compatibility_score: 0.95,
      status: "compatible",
      reason: "Optimal match with identical platform and minimal clouds",
      explanation: [],
    },
  };

  const sampleValidationResult: TemporalPairValidationResult = {
    valid: true,
    status: "compatible",
    before_scene_id: "S2A_20250101",
    after_scene_id: "S2B_20250120",
    temporal_gap_days: 19.0,
    compatibility_score: 0.95,
    factors: [
      {
        name: "collection_platform",
        score: 1.0,
        weight: 0.25,
        weighted_score: 0.25,
        status: "optimal",
        details: "Identical collection",
      },
      {
        name: "spatial_coverage",
        score: 1.0,
        weight: 0.25,
        weighted_score: 0.25,
        status: "optimal",
        details: "100% mutual AOI coverage",
      },
    ],
    issues: [
      {
        code: "LOW_SEASONAL_VARIANCE",
        severity: "info",
        title: "Same season acquisition",
        message: "Acquisitions are within the same month of year.",
        blocking: false,
      },
    ],
    warnings: [],
    spatial_metrics: {
      before_aoi_coverage_percent: 100,
      after_aoi_coverage_percent: 100,
      mutual_aoi_coverage_percent: 100,
      scene_overlap_percent: 100,
    },
    data_origin_status: "real",
    validation_version: "1.0",
  };

  it("renders empty placeholder when no candidates are loaded", () => {
    render(
      <TemporalPairingPanel
        candidates={null}
        searchState="idle"
        searchError={null}
        selectedBeforeScene={null}
        selectedAfterScene={null}
        validationResult={null}
        validationState="idle"
        validationError={null}
        onSearchCandidates={vi.fn()}
        onSelectBeforeScene={vi.fn()}
        onSelectAfterScene={vi.fn()}
        onApplyRecommendedPair={vi.fn()}
        onClearSelection={vi.fn()}
      />,
    );

    expect(screen.getByText("Select Before & After Satellite Scenes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Discover Scene Candidates" })).toBeInTheDocument();
    expect(screen.getByText("1. Baseline Period (Before / T_A)")).toBeInTheDocument();
    expect(screen.getByText("2. Comparative Period (After / T_B)")).toBeInTheDocument();
  });

  it("renders candidate cards and recommended pair banner", () => {
    const onApplyRecommendedPair = vi.fn();
    const onSelectBefore = vi.fn();
    const onSelectAfter = vi.fn();

    render(
      <TemporalPairingPanel
        candidates={sampleCandidates}
        searchState="idle"
        searchError={null}
        selectedBeforeScene={sampleBeforeScene}
        selectedAfterScene={null}
        validationResult={null}
        validationState="idle"
        validationError={null}
        onSearchCandidates={vi.fn()}
        onSelectBeforeScene={onSelectBefore}
        onSelectAfterScene={onSelectAfter}
        onApplyRecommendedPair={onApplyRecommendedPair}
        onClearSelection={vi.fn()}
      />,
    );

    expect(screen.getByText("RECOMMENDED PAIR")).toBeInTheDocument();
    expect(screen.getByText("95% Match")).toBeInTheDocument();

    const applyBtn = screen.getByRole("button", { name: "Apply Recommended Pair" });
    fireEvent.click(applyBtn);
    expect(onApplyRecommendedPair).toHaveBeenCalledTimes(1);

    expect(screen.getByText("S2A_20250101")).toBeInTheDocument();
    expect(screen.getByText("S2B_20250120")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "✓ Selected as BEFORE" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Select for AFTER" })).toBeInTheDocument();
  });

  it("renders authoritative compatibility summary with factors and metrics", () => {
    const onClear = vi.fn();
    const onContinue = vi.fn();

    render(
      <TemporalPairingPanel
        candidates={sampleCandidates}
        searchState="idle"
        searchError={null}
        selectedBeforeScene={sampleBeforeScene}
        selectedAfterScene={sampleAfterScene}
        validationResult={sampleValidationResult}
        validationState="idle"
        validationError={null}
        onSearchCandidates={vi.fn()}
        onSelectBeforeScene={vi.fn()}
        onSelectAfterScene={vi.fn()}
        onApplyRecommendedPair={vi.fn()}
        onClearSelection={onClear}
        onContinue={onContinue}
      />,
    );

    expect(screen.getByText("Authoritative Pair Compatibility")).toBeInTheDocument();
    expect(screen.getByText("Strong Match (Compatible)")).toBeInTheDocument();
    expect(screen.getByText("19.0 days")).toBeInTheDocument();
    expect(screen.getAllByText(/100/).length).toBeGreaterThan(0);
    expect(screen.getByText("Same season acquisition")).toBeInTheDocument();

    const continueBtn = screen.getByRole("button", {
      name: "Continue to Imagery Preparation →",
    });
    expect(continueBtn).toBeEnabled();
    fireEvent.click(continueBtn);
    expect(onContinue).toHaveBeenCalledTimes(1);

    const clearBtn = screen.getByRole("button", { name: "Clear Selection" });
    fireEvent.click(clearBtn);
    expect(onClear).toHaveBeenCalledTimes(1);
  });
});

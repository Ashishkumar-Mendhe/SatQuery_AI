import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createAoiFromBounds } from "@/lib/aoi";
import type { CatalogueScene } from "@/lib/catalog-client";
import {
  type PreparationClient,
  PreparationClientError,
  type ProcessingJobStatus,
  type QualityReport,
} from "@/lib/preparation-client";
import { createCatalogueSceneSelection } from "@/lib/scene-selection";
import { PreparationPanel } from "./preparation-panel";

const ARTIFACT_ID = "10000000-0000-4000-8000-000000000001";
const MASK_ID = "10000000-0000-4000-8000-000000000002";
const JOB_ID = "10000000-0000-4000-8000-000000000003";

function scene(item = "S2_TEST") {
  const value = {
    provider: { id: "earth-search", name: "Earth Search" },
    provider_asset_id: item,
    provider_asset_version: null,
    collection: { id: "sentinel-2-c1-l2a", title: "Sentinel-2 L2A" },
    acquisition: { start: "2025-06-01T05:30:00Z", end: "2025-06-01T05:30:00Z" },
    platform: "sentinel-2b",
    instruments: ["msi"],
    product_type: "S2MSI2A",
    processing_level: "L2A",
    footprint: {
      type: "Polygon",
      coordinates: [
        [
          [77.5, 12.9],
          [77.7, 12.9],
          [77.7, 13.1],
          [77.5, 12.9],
        ],
      ],
    },
    bbox: [77.5, 12.9, 77.7, 13.1],
    cloud_cover: null,
    spatial_resolution: [],
    bands: [],
    polarizations: [],
    preview: null,
    license: null,
    asset_access: { state: "provider_accessible", method: "provider_reference", reason: null },
    provenance: {
      adapter: "test",
      adapter_version: "1",
      retrieved_at: "2025-06-01T06:00:00Z",
      source_record_id: item,
      source_record_version: null,
      metadata_digest_sha256: "a".repeat(64),
      fields: [
        { normalized_field: "id", source: "provider_record", source_field: "id", method: null },
      ],
    },
    unavailable_fields: [],
  } as CatalogueScene;
  return createCatalogueSceneSelection(value, "query", {
    schema_version: "1.0",
    provider: "earth-search",
    aoi: value.footprint,
    acquisition: value.acquisition,
    collections: [],
    cloud_cover: null,
    limit: 10,
    cursor: null,
    sort: "acquired_desc",
  });
}

function succeeded(): ProcessingJobStatus {
  return {
    schema_version: "1.0",
    job_id: JOB_ID,
    state: "succeeded",
    submitted_at: "2025-06-01T06:00:00Z",
    started_at: "2025-06-01T06:00:01Z",
    finished_at: "2025-06-01T06:00:02Z",
    attempt: 1,
    current_stage: "complete",
    progress: { completed_units: 6, total_units: 6, units: "stages" },
    artifacts: [
      {
        artifact_id: ARTIFACT_ID,
        kind: "provenance_manifest",
        media_type: "application/json",
        checksum_sha256: "b".repeat(64),
        byte_size: 1024,
        access: { state: "available", reason: null },
      },
      {
        artifact_id: MASK_ID,
        kind: "quality_mask",
        media_type: "image/tiff",
        checksum_sha256: "c".repeat(64),
        byte_size: 2048,
        access: { state: "available", reason: null },
      },
    ],
    error_code: null,
    safe_error_message: null,
  };
}

function report(outcome: "pass" | "warning" | "fail" | "unknown" = "pass"): QualityReport {
  return {
    profile: {
      profile_id: "optical",
      version: "1",
      intended_task: "optical_single_scene",
      processing_profile: "sentinel-2-l2a-surface-reflectance-v1",
      required_bands: ["red", "green", "blue"],
      required_capabilities: ["calibration"],
      requires_registration: false,
    },
    threshold_version: "provisional-engineering-v1",
    thresholds_are_provisional_engineering_limits: true,
    readiness:
      outcome === "fail"
        ? "not_ready"
        : outcome === "unknown"
          ? "unknown"
          : outcome === "warning"
            ? "limited"
            : "ready",
    readiness_reason: `${outcome} readiness`,
    blocking_check_ids: outcome === "fail" ? ["usable_coverage"] : [],
    warning_check_ids: outcome === "warning" ? ["cloud_coverage"] : [],
    minimum_supported_spatial_scale_metres: 20,
    requested_spatial_scale_metres: null,
    map_viewing_affected: false,
    catalogue_search_affected: false,
    checks: [
      {
        check_id:
          outcome === "unknown"
            ? "quality_information"
            : outcome === "warning"
              ? "cloud_coverage"
              : "usable_coverage",
        category: "quality coverage",
        outcome,
        required: true,
        measured_value: outcome === "unknown" ? null : 82.5,
        measured_text: null,
        units: outcome === "unknown" ? null : "percent",
        denominator_name: outcome === "unknown" ? null : "inside AOI pixels",
        denominator_value: outcome === "unknown" ? null : 1000,
        threshold_description: ">= 70 percent",
        reason: `${outcome} evidence`,
        corrective_action: outcome === "pass" ? null : "Choose a clearer scene.",
        evidence_source: "measured mask",
        provisional_threshold: true,
      },
    ],
  };
}

function client(outcome: "pass" | "warning" | "fail" | "unknown" = "pass"): PreparationClient {
  return {
    start: vi.fn().mockResolvedValue(succeeded()),
    status: vi.fn(),
    report: vi.fn().mockResolvedValue(report(outcome)),
    manifest: vi.fn().mockResolvedValue({
      schema_version: "1.0",
      job_id: JOB_ID,
      code_version: "satquery-test",
      configuration_version: "test-v1",
      request: {
        scenes: [{ provider: "earth-search", collection: "sentinel-2-c1-l2a", item: "S2_TEST" }],
        intended_task: "optical_single_scene",
        processing_profile: "sentinel-2-l2a-surface-reflectance-v1",
      },
      grid: {
        crs: "EPSG:32643",
        width: 100,
        height: 100,
        resolution_metres: [10, 10],
        bounds: [0, 0, 1000, 1000],
      },
      registration: {
        state: "not_applicable",
        explanation: "Single scene; registration is not applicable.",
      },
      pair_coverage: [],
      scenes: [
        {
          scene: { provider: "earth-search", collection: "sentinel-2-c1-l2a", item: "S2_TEST" },
          quality_information: outcome === "unknown" ? "unavailable" : "available",
          native_resolutions_metres: [10],
          output_resolution_metres: 10,
          upsampled: false,
          upsampling_explanation: null,
          coverage: [],
          quality_artifact_id: MASK_ID,
        },
      ],
      completed_at: "2025-06-01T06:00:02Z",
      manifest_artifact_id: ARTIFACT_ID,
    }),
  } as unknown as PreparationClient;
}

const aoi = createAoiFromBounds([77.5, 12.9, 77.7, 13.1]);

describe("PreparationPanel", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000/api/v1";
  });
  it("submits from the keyboard and shows successful measured results and overlays", async () => {
    const service = client();
    const overlay = vi.fn();
    const user = userEvent.setup();
    render(
      <PreparationPanel
        selectedAoi={aoi}
        selectedScene={scene()}
        comparison={null}
        client={service}
        onOverlayChange={overlay}
      />,
    );
    await user.tab();
    await user.tab();
    await user.tab();
    await user.keyboard("{Enter}");
    expect(await screen.findByText("pass readiness")).toBeInTheDocument();
    expect(screen.getByText(/82.50 percent of 1,000 inside AOI pixels/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "quality report" })).toHaveAttribute(
      "href",
      expect.stringContaining(`/processing/jobs/${JOB_ID}/quality-report`),
    );
    fireEvent.click(screen.getByLabelText("Usable data"));
    await waitFor(() =>
      expect(overlay).toHaveBeenLastCalledWith(
        expect.objectContaining({ usable: true, qualityArtifactIds: [MASK_ID] }),
      ),
    );
    expect(screen.getByRole("button", { name: /future analysis/i })).toBeDisabled();
  });

  it("shows only the backend-recorded stage units while work is running", async () => {
    const service = client();
    vi.mocked(service.start).mockResolvedValue({
      ...succeeded(),
      state: "running",
      finished_at: null,
      current_stage: "quality_masking",
      progress: { completed_units: 2, total_units: 6, units: "stages" },
      artifacts: [],
    });
    vi.mocked(service.status).mockReturnValue(new Promise(() => {}));
    render(
      <PreparationPanel
        selectedAoi={aoi}
        selectedScene={scene()}
        comparison={null}
        client={service}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Prepare imagery" }));
    expect(await screen.findByText("quality masking")).toBeInTheDocument();
    expect(screen.getByText("2 of 6 actual stages completed")).toBeInTheDocument();
    expect(screen.queryByText(/% complete/)).not.toBeInTheDocument();
  });

  it.each([
    ["warning", "warning readiness"],
    ["fail", "fail readiness"],
    ["unknown", "Unavailable"],
  ] as const)("renders %s task evidence", async (outcome, expected) => {
    render(
      <PreparationPanel
        selectedAoi={aoi}
        selectedScene={scene()}
        comparison={null}
        client={client(outcome)}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Prepare imagery" }));
    expect(await screen.findByText(expected)).toBeInTheDocument();
    if (outcome !== "warning")
      expect(screen.getByText(/Choose a clearer scene/)).toBeInTheDocument();
  });

  it("shows blocked and processing-failure states with retry", async () => {
    const blocked = client();
    vi.mocked(blocked.start).mockRejectedValue(
      new PreparationClientError("blocked", "Durable processing is unavailable.", true),
    );
    const { rerender } = render(
      <PreparationPanel
        selectedAoi={aoi}
        selectedScene={scene()}
        comparison={null}
        client={blocked}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Prepare imagery" }));
    expect(await screen.findByText("Preparation blocked")).toBeInTheDocument();
    const failed = client();
    vi.mocked(failed.start).mockResolvedValue({
      ...succeeded(),
      state: "failed",
      artifacts: [],
      error_code: "raster_read_failed",
      safe_error_message: "Raster read failed.",
    });
    rerender(
      <PreparationPanel
        selectedAoi={aoi}
        selectedScene={scene()}
        comparison={null}
        client={failed}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry preparation" }));
    expect(await screen.findByText("Raster read failed.")).toBeInTheDocument();
  });

  it("marks a completed result stale when its scene changes", async () => {
    const service = client();
    const { rerender } = render(
      <PreparationPanel
        selectedAoi={aoi}
        selectedScene={scene()}
        comparison={null}
        client={service}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Prepare imagery" }));
    expect(await screen.findByText("pass readiness")).toBeInTheDocument();
    rerender(
      <PreparationPanel
        selectedAoi={aoi}
        selectedScene={scene("S2_OTHER")}
        comparison={null}
        client={service}
      />,
    );
    expect(await screen.findByText("Result out of date")).toBeInTheDocument();
    expect(screen.queryByLabelText("Usable data")).not.toBeInTheDocument();
  });

  it("does not let a delayed response replace the current scene", async () => {
    let resolveStart: ((value: ProcessingJobStatus) => void) | undefined;
    const delayed = new Promise<ProcessingJobStatus>((resolve) => {
      resolveStart = resolve;
    });
    const service = client();
    vi.mocked(service.start).mockReturnValue(delayed);
    const { rerender } = render(
      <PreparationPanel
        selectedAoi={aoi}
        selectedScene={scene()}
        comparison={null}
        client={service}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Prepare imagery" }));
    rerender(
      <PreparationPanel
        selectedAoi={aoi}
        selectedScene={scene("S2_CURRENT")}
        comparison={null}
        client={service}
      />,
    );
    resolveStart?.(succeeded());
    await waitFor(() => expect(screen.getByText("S2_CURRENT")).toBeInTheDocument());
    expect(screen.queryByText("Task readiness")).not.toBeInTheDocument();
  });
});

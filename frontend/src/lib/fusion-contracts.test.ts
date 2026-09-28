import { describe, expect, it } from "vitest";

import {
  coveragePartitionsSchema,
  fusionCapabilitiesResponseSchema,
  jointStateMetricsSchema,
  sarThresholdConfigSchema,
} from "./fusion-contracts";

describe("fusion-contracts", () => {
  it("validates valid SAR threshold config", () => {
    const parsed = sarThresholdConfigSchema.parse({
      increase_threshold_db: 3.0,
      decrease_threshold_db: -3.0,
      min_cluster_size_pixels: 8,
      simplify_tolerance_meters: 2.0,
    });
    expect(parsed.increase_threshold_db).toBe(3.0);
    expect(parsed.decrease_threshold_db).toBe(-3.0);
  });

  it("rejects SAR threshold config where increase <= decrease", () => {
    expect(() =>
      sarThresholdConfigSchema.parse({
        increase_threshold_db: -1.0,
        decrease_threshold_db: 2.0,
      }),
    ).toThrow();
  });

  it("validates coverage partitions and joint state metrics schema", () => {
    const cov = coveragePartitionsSchema.parse({
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
    });
    expect(cov.jointly_observable_area_km2).toBe(1.0);

    const metrics = jointStateMetricsSchema.parse({
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
    });
    expect(metrics.both_detect_change_percent).toBe(20.0);
  });

  it("allows null percentages when joint area is zero", () => {
    const metrics = jointStateMetricsSchema.parse({
      joint_area_km2: 0.0,
      both_detect_change_area_km2: 0.0,
      optical_response_only_area_km2: 0.0,
      sar_response_only_area_km2: 0.0,
      neither_above_threshold_area_km2: 0.0,
      uncertain_area_km2: 0.0,
      both_detect_change_percent: null,
      optical_response_only_percent: null,
      sar_response_only_percent: null,
      neither_above_threshold_percent: null,
      uncertain_percent: null,
      pixel_counts: {
        both_detect_change_pixels: 0,
        optical_response_only_pixels: 0,
        sar_response_only_pixels: 0,
        neither_above_threshold_pixels: 0,
        uncertain_pixels: 0,
      },
    });
    expect(metrics.both_detect_change_percent).toBeNull();
  });

  it("validates fusion capabilities response", () => {
    const caps = fusionCapabilitiesResponseSchema.parse({
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
    });
    expect(caps.rules).toHaveLength(1);
    expect(caps.supported_polarizations).toContain("VV");
  });
});

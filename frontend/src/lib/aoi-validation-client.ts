import type { SelectedAoi } from "./aoi";
import { selectedAoiToContract } from "./aoi";
import {
  type AoiValidationResponse,
  aoiValidationResponseSchema,
} from "./aoi-validation-contracts";
import { apiBaseUrl } from "./config";

export class AoiClientError extends Error {
  readonly status?: number;
  readonly code?: string;

  constructor(message: string, status?: number, code?: string) {
    super(message);
    this.name = "AoiClientError";
    this.status = status;
    this.code = code;
  }
}

export async function validateAoiWithBackend(
  aoi: SelectedAoi,
  intendedMode?: string,
  signal?: AbortSignal,
): Promise<AoiValidationResponse> {
  const url = `${apiBaseUrl()}/aoi/validate`;
  const payload = {
    geometry: selectedAoiToContract(aoi),
    client_area_km2: Number((aoi.areaSquareMeters / 1_000_000).toFixed(6)),
    intended_mode: intendedMode || null,
  };

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
      signal,
    });

    if (!response.ok) {
      const text = await response.text();
      let errorMessage = `Backend validation returned HTTP ${response.status}`;
      try {
        const errorJson = JSON.parse(text);
        if (errorJson?.error?.message) {
          errorMessage = errorJson.error.message;
        }
      } catch {
        // use default message
      }
      throw new AoiClientError(errorMessage, response.status);
    }

    const data = await response.json();
    return aoiValidationResponseSchema.parse(data);
  } catch (error) {
    if (signal?.aborted) {
      throw error;
    }
    if (error instanceof AoiClientError) {
      throw error;
    }
    // Return a graceful offline fallback if backend is unreachable
    return {
      valid: true,
      normalized_geometry: selectedAoiToContract(aoi),
      bbox: aoi.bounds,
      area_km2: Number((aoi.areaSquareMeters / 1_000_000).toFixed(6)),
      geometry_type: "Polygon",
      coordinate_count: aoi.feature.geometry.coordinates[0].length,
      warnings: [
        {
          code: "AOI_REQUIRED",
          message: "Backend validation service unreachable; using local geometric validation.",
          severity: "warning",
          field: null,
        },
      ],
      errors: [],
      validation_version: "1.0",
    };
  }
}

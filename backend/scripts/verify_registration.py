"""Verify Task 6E against a real same-sensor optical pair when provider reads succeed."""

from __future__ import annotations

import asyncio
import json

from verify_common_grid import AOI, SCENES, prepare_real_pair

from satquery.processing import RegistrationService


async def verify() -> None:
    pair = await prepare_real_pair()
    result = RegistrationService().assess_and_correct(pair)
    assessment = result.assessment
    print(
        json.dumps(
            {
                "scenes": SCENES,
                "aoi_wgs84": AOI,
                "state": assessment.state,
                "explanation": assessment.explanation,
                "method": assessment.method,
                "coordinate_convention": assessment.coordinate_convention,
                "band_role": assessment.band_role,
                "estimated_displacement_pixels": {
                    "row": assessment.estimated_row_shift_pixels,
                    "column": assessment.estimated_column_shift_pixels,
                },
                "estimated_displacement_map_units": {
                    "x": assessment.estimated_x_shift_map_units,
                    "y": assessment.estimated_y_shift_map_units,
                    "units": assessment.map_displacement_units,
                    "crs": pair.grid.crs,
                },
                "distribution": {
                    "total_patches": assessment.distribution.total_patches,
                    "usable_patches": assessment.distribution.usable_patches,
                    "usable_estimation_patches": (
                        assessment.distribution.usable_estimation_patches
                    ),
                    "usable_validation_patches": (
                        assessment.distribution.usable_validation_patches
                    ),
                    "represented_rows": assessment.distribution.represented_rows,
                    "represented_columns": assessment.distribution.represented_columns,
                    "centre_extent_fraction": assessment.distribution.centre_extent_fraction,
                },
                "agreement": {
                    "estimate_count": assessment.agreement.estimate_count,
                    "inlier_count": assessment.agreement.inlier_count,
                    "inlier_fraction": assessment.agreement.inlier_fraction,
                    "agrees": assessment.agreement.agrees,
                },
                "residual": {
                    "validation_patch_count": assessment.residual.validation_patch_count,
                    "median_correlation_before": assessment.residual.median_correlation_before,
                    "median_correlation_after": assessment.residual.median_correlation_after,
                    "median_improvement": assessment.residual.median_improvement,
                    "improved_patch_count": assessment.residual.improved_patch_count,
                    "improved": assessment.residual.improved,
                },
                "correction_state": assessment.correction_state,
                "correction": (
                    None
                    if assessment.correction is None
                    else {
                        "model": assessment.correction.model,
                        "row_shift_pixels": assessment.correction.row_shift_pixels,
                        "column_shift_pixels": assessment.correction.column_shift_pixels,
                        "x_shift_map_units": assessment.correction.x_shift_map_units,
                        "y_shift_map_units": assessment.correction.y_shift_map_units,
                        "map_units": assessment.correction.map_units,
                        "affine_matrix": assessment.correction.affine_matrix,
                        "interpolation": assessment.correction.interpolation,
                    }
                ),
                "ground_truth_accuracy_available": False,
                "provider_locations_exposed": False,
                "source_arrays_preserved": True,
            },
            indent=2,
        )
    )


def main() -> None:
    asyncio.run(verify())


if __name__ == "__main__":
    main()

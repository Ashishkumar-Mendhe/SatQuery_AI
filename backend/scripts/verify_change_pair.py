"""Run the bounded 8B comparability assessment on one real Sentinel-2 pair."""

from __future__ import annotations

import asyncio
import json

import numpy as np

from satquery.api.schemas.processing import PreparationRequest
from satquery.core.config import load_settings
from satquery.processing import (
    ChangeSummaryService,
    CommonGridService,
    OpticalChangeDetector,
    PairPreparationService,
    QualityMaskService,
    RasterInputError,
    RasterInputService,
    RegistrationService,
    SceneAcquisitionEvidence,
    ScenePreparationInput,
)
from satquery.providers.catalog import EarthSearchCatalogueProvider

SCENES = [
    {
        "provider": "earth-search",
        "collection": "sentinel-2-c1-l2a",
        "item": "S2B_T43PGQ_20251213T052354_L2A",
    },
    {
        "provider": "earth-search",
        "collection": "sentinel-2-c1-l2a",
        "item": "S2B_T43PGQ_20251223T051848_L2A",
    },
]
AOI = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.5850, 12.9650],
            [77.6050, 12.9650],
            [77.6050, 12.9850],
            [77.5850, 12.9850],
            [77.5850, 12.9650],
        ]
    ],
}
BANDS = [
    {"role": "red", "common_name": "red"},
    {"role": "green", "common_name": "green"},
    {"role": "blue", "common_name": "blue"},
]


def _request(scenes: list[dict[str, str]], *, pair: bool) -> PreparationRequest:
    return PreparationRequest.model_validate(
        {
            "scenes": scenes,
            "aoi": AOI,
            "required_bands": BANDS,
            "intended_task": "optical_pair" if pair else "optical_single_scene",
            "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
            "options": {
                "grid_policy": "common_utm" if pair else "source_aligned",
                "target_resolution_metres": 10.0,
                "continuous_resampling": "bilinear" if pair else "nearest",
                "max_output_pixels": 60_000,
            },
        }
    )


async def verify() -> None:
    provider = EarthSearchCatalogueProvider.from_settings(load_settings())
    raster_service = RasterInputService(provider)
    quality_service = QualityMaskService(provider)
    inputs: list[ScenePreparationInput] = []
    acquisitions: list[SceneAcquisitionEvidence] = []
    scene_quality: list[dict[str, object]] = []
    attempted_scene: dict[str, str] | None = None
    try:
        for scene_value in SCENES:
            attempted_scene = scene_value
            request = _request([scene_value], pair=False)
            metadata = await provider.item(scene_value["collection"], scene_value["item"])
            raster = await raster_service.extract(request)
            quality = await quality_service.decode(raster)
            inputs.append(ScenePreparationInput(raster, quality))
            scene_quality.append(
                {
                    "scene": scene_value,
                    "quality_information": quality.quality_information,
                    "inside_aoi_pixels": int(raster.inside_aoi_mask.sum()),
                    "all_band_valid_pixels": int(np.all(raster.band_validity, axis=0).sum()),
                    "usable_pixels": int(quality.usable.sum()),
                    "cloud_or_cirrus_pixels": int(quality.clouds_or_cirrus.sum()),
                    "cloud_shadow_pixels": int(quality.cloud_shadows.sum()),
                    "missing_or_invalid_pixels": int(quality.missing_or_invalid.sum()),
                    "unknown_quality_pixels": int(quality.unknown_quality.sum()),
                    "scl_classes": {
                        str(value): int((quality.scl_classes == value).sum())
                        for value in sorted(set(quality.scl_classes.ravel().tolist()))
                    },
                }
            )
            acquisitions.append(
                SceneAcquisitionEvidence(
                    scene=request.scenes[0],
                    acquired_at=metadata.acquisition.start,
                    sensor="MSI",
                    platform=metadata.platform,
                    processing_level=metadata.processing_level,
                )
            )
        pair_request = _request(SCENES, pair=True)
        grid = CommonGridService(max_pixels=60_000).prepare(pair_request, tuple(inputs))
        harmonized_quality = [
            {
                "scene": scene.scene.model_dump(mode="json"),
                "valid_pixels": int(scene.valid_data.sum()),
                "usable_pixels": int(scene.quality.usable.sum()),
                "cloud_or_cirrus_pixels": int(scene.quality.clouds_or_cirrus.sum()),
                "cloud_shadow_pixels": int(scene.quality.cloud_shadows.sum()),
                "unknown_quality_pixels": int(scene.quality.unknown_quality.sum()),
            }
            for scene in grid.scenes
        ]
        registration = RegistrationService().assess_and_correct(grid)
        outcome = PairPreparationService().prepare(
            pair_request,
            grid,
            registration,
            tuple(acquisitions),
        )
        detection = OpticalChangeDetector().detect(outcome, grid, registration)
        summary = (
            ChangeSummaryService().summarize(pair_request, outcome, detection, grid, registration)
            if detection.state == "completed"
            else None
        )
        print(
            json.dumps(
                {
                    "state": outcome.state,
                    "comparison_allowed": outcome.comparison_allowed,
                    "processing_version": outcome.processing_version,
                    "sources": [source.model_dump(mode="json") for source in outcome.sources],
                    "acquired_at": [
                        value.isoformat() if value is not None else None
                        for value in outcome.acquired_at
                    ],
                    "aoi_wgs84": AOI,
                    "band_order": list(outcome.band_order),
                    "grid": outcome.grid.model_dump(mode="json"),
                    "registration_state": outcome.registration_state,
                    "correction_state": outcome.correction_state,
                    "registration": {
                        "explanation": registration.assessment.explanation,
                        "pixel_displacement": [
                            registration.assessment.estimated_row_shift_pixels,
                            registration.assessment.estimated_column_shift_pixels,
                        ],
                        "distribution": {
                            "usable_patches": (registration.assessment.distribution.usable_patches),
                            "estimation_patches": (
                                registration.assessment.distribution.usable_estimation_patches
                            ),
                            "validation_patches": (
                                registration.assessment.distribution.usable_validation_patches
                            ),
                        },
                        "agreement": {
                            "estimate_count": registration.assessment.agreement.estimate_count,
                            "inlier_count": registration.assessment.agreement.inlier_count,
                            "inlier_fraction": registration.assessment.agreement.inlier_fraction,
                            "agrees": registration.assessment.agreement.agrees,
                        },
                        "patch_reasons": sorted(
                            {
                                patch.reason
                                for patch in registration.assessment.patches
                                if patch.reason is not None
                            }
                        ),
                    },
                    "coverage": {
                        "denominator": outcome.coverage.denominator_name,
                        "aoi_pixels": outcome.coverage.aoi_pixels,
                        "joint_valid_pixels": outcome.coverage.joint_valid_pixels,
                        "joint_valid_percent": outcome.coverage.joint_valid_percent,
                        "joint_usable_pixels": outcome.coverage.joint_usable_pixels,
                        "joint_usable_percent": outcome.coverage.joint_usable_percent,
                        "joint_valid_area_square_metres": (
                            outcome.coverage.joint_valid_area_square_metres
                        ),
                        "joint_usable_area_square_metres": (
                            outcome.coverage.joint_usable_area_square_metres
                        ),
                    },
                    "scene_quality": scene_quality,
                    "harmonized_scene_quality": harmonized_quality,
                    "parameters": {
                        "joint_valid_policy": outcome.parameters.joint_valid_policy,
                        "joint_usable_policy": outcome.parameters.joint_usable_policy,
                        "required_registration_state": (
                            outcome.parameters.required_registration_state
                        ),
                    },
                    "reasons": [
                        {
                            "code": reason.code,
                            "explanation": reason.explanation,
                            "corrective_action": reason.corrective_action,
                        }
                        for reason in outcome.reasons
                    ],
                    "detection": {
                        "state": detection.state,
                        "method": detection.parameters.method,
                        "version": detection.parameters.version,
                        "threshold": detection.parameters.threshold,
                        "classes": [
                            {
                                "classification": item.classification,
                                "pixel_count": item.pixel_count,
                                "area_square_metres": item.area_square_metres,
                            }
                            for item in detection.classes
                        ],
                        "reasons": [
                            {
                                "code": reason.code,
                                "explanation": reason.explanation,
                            }
                            for reason in detection.reasons
                        ],
                    },
                    "summary": (
                        {
                            "changed_area_square_metres": (summary.area.changed_area_square_metres),
                            "changed_percent_of_joint_valid_observed_area": (
                                summary.area.changed_percent_of_joint_valid_observed_area
                            ),
                            "joint_valid_observed_area_square_metres": (
                                summary.area.joint_valid_observed_area_square_metres
                            ),
                            "unknown_area_square_metres": summary.area.unknown_area_square_metres,
                            "cause_or_land_cover_category": (summary.cause_or_land_cover_category),
                            "statements": list(summary.statements),
                            "warnings": [
                                {"code": item.code, "statement": item.statement}
                                for item in summary.warnings
                            ],
                        }
                        if summary is not None
                        else None
                    ),
                    "change_map_produced": detection.classification is not None,
                    "provider_locations_exposed": False,
                },
                indent=2,
            )
        )
    except RasterInputError as error:
        print(
            json.dumps(
                {
                    "state": "unavailable",
                    "comparison_allowed": False,
                    "stage": "trusted_raster_extraction",
                    "attempted_scene": attempted_scene,
                    "completed_scene_quality": scene_quality,
                    "error_code": error.code,
                    "reason": str(error),
                    "real_pair_outcome_available": False,
                    "change_map_produced": False,
                    "provider_locations_exposed": False,
                },
                indent=2,
            )
        )
    finally:
        await provider.aclose()


def main() -> None:
    asyncio.run(verify())


if __name__ == "__main__":
    main()

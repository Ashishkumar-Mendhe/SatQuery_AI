from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from satquery.api.schemas.catalog import AcquisitionInterval, CatalogGeometry
from satquery.api.schemas.scene_metadata import SceneMetadataResponse
from satquery.api.schemas.viewer import StrictViewerModel, ViewerBounds, ViewerSceneIdentity

NISAR_GCOV_COLLECTION: Literal["NISAR_L2_GCOV_PROVISIONAL_V1"] = "NISAR_L2_GCOV_PROVISIONAL_V1"
NisarFrequency = Literal["A", "B"]
NisarPolarization = Literal["HH", "HV", "VH", "VV", "RH", "RV", "LH", "LV"]
NisarDiagonalTerm = Literal["HHHH", "HVHV", "VHVH", "VVVV", "RHRH", "RVRV"]


class NisarDiscoveryRequest(StrictViewerModel):
    provider: Literal["nasa-cmr-asf"] = "nasa-cmr-asf"
    aoi: CatalogGeometry
    acquisition: AcquisitionInterval
    limit: int = Field(default=10, ge=1, le=25, strict=True)


class NisarFrequencyMetadata(StrictViewerModel):
    frequency: NisarFrequency
    range_bandwidth_mhz: int = Field(gt=0, strict=True)
    nominal_pixel_spacing_metres: int = Field(gt=0, strict=True)
    polarizations: list[NisarPolarization] = Field(min_length=1, max_length=4)
    diagonal_covariance_terms: list[NisarDiagonalTerm] = Field(max_length=4)


class NisarQualityEvidence(StrictViewerModel):
    full_frame: bool
    joint_observation: bool
    orbit_fidelity: Literal["precise", "medium", "near_real_time", "forecast", "unknown"]
    qa_summary_available: bool
    qa_report_available: bool
    provisional_known_limitations: list[str] = Field(min_length=1, max_length=16)


class NisarGcovScene(StrictViewerModel):
    source: ViewerSceneIdentity
    concept_id: str = Field(pattern=r"^G[0-9]+-ASF$")
    granule_ur: str = Field(min_length=20, max_length=220)
    acquisition: AcquisitionInterval
    footprint: CatalogGeometry
    mission: Literal["NISAR"] = "NISAR"
    instrument: Literal["L-SAR"] = "L-SAR"
    processing_level: Literal["L2"] = "L2"
    product_type: Literal["GCOV"] = "GCOV"
    product_maturity: Literal["provisional"] = "provisional"
    product_version: str = Field(min_length=1, max_length=40)
    pge_version: str = Field(min_length=1, max_length=40)
    composite_release_id: str = Field(pattern=r"^P[0-9]{5}$")
    frequencies: list[NisarFrequencyMetadata] = Field(min_length=1, max_length=2)
    quality: NisarQualityEvidence
    metadata: SceneMetadataResponse


class NisarDiscoveryResponse(StrictViewerModel):
    scenes: list[NisarGcovScene] = Field(max_length=25)
    collection: Literal["NISAR_L2_GCOV_PROVISIONAL_V1"] = NISAR_GCOV_COLLECTION
    provider_attribution: str


class NisarIngestionRequest(StrictViewerModel):
    scene: ViewerSceneIdentity
    aoi: CatalogGeometry
    frequency: NisarFrequency
    covariance_term: NisarDiagonalTerm
    max_pixels: int = Field(default=1_000_000, ge=1, le=1_000_000, strict=True)


class NisarMaskStatistics(StrictViewerModel):
    aoi_pixels: int = Field(ge=0)
    valid_pixels: int = Field(ge=0)
    invalid_ensemble_pixels: int = Field(ge=0)
    outside_acquisition_pixels: int = Field(ge=0)
    nodata_or_nonfinite_backscatter_pixels: int = Field(ge=0)


class NisarIngestedResult(StrictViewerModel):
    state: Literal["ingested"]
    source: ViewerSceneIdentity
    acquisition_time: datetime
    frequency: NisarFrequency
    covariance_term: NisarDiagonalTerm
    polarization: NisarPolarization
    crs: str = Field(min_length=3, max_length=80)
    transform: tuple[float, float, float, float, float, float]
    bounds: ViewerBounds
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    pixel_spacing_metres: float = Field(gt=0)
    units: Literal["gamma0_power"]
    calibration: Literal["source_calibrated_rtc_gamma0_no_additional_scale"]
    product_maturity: Literal["provisional"]
    composite_release_id: str
    product_version: str
    pge_version: str
    mask: NisarMaskStatistics
    quality: NisarQualityEvidence
    available_dataset_paths: list[str] = Field(min_length=2, max_length=32)
    quality_warnings: list[str] = Field(min_length=1, max_length=32)
    processing_version: str


class NisarIngestionUnavailable(StrictViewerModel):
    state: Literal["unavailable"]
    source: ViewerSceneIdentity
    reason_code: Literal[
        "earthdata_authentication_required",
        "requested_layer_unavailable",
        "invalid_product",
        "empty_intersection",
        "resource_limit",
    ]
    retryable: bool
    reason: str = Field(min_length=1, max_length=1000)
    corrective_action: str = Field(min_length=1, max_length=1500)


NisarIngestionOutcome = Annotated[
    NisarIngestedResult | NisarIngestionUnavailable, Field(discriminator="state")
]


class NisarIngestionResponse(StrictViewerModel):
    outcome: NisarIngestionOutcome

    @model_validator(mode="after")
    def keep_unavailable_non_retryable(self) -> NisarIngestionResponse:
        if self.outcome.state == "unavailable" and self.outcome.retryable:
            raise ValueError(
                "operator configuration and staging failures are not automatic retries"
            )
        return self

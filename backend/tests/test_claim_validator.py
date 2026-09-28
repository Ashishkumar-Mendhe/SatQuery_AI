from __future__ import annotations

from datetime import UTC, datetime

from satquery.api.schemas.analysis import (
    EvidenceItem,
    EvidenceProvenance,
    EvidenceType,
)
from satquery.api.schemas.query import (
    AnswerClaim,
    ClaimKind,
    ClaimValidationStatus,
)
from satquery.services.claim_validator import ClaimValidator
from satquery.services.evidence_retriever import EvidenceBundle


def create_known_change_bundle() -> EvidenceBundle:
    """Creates the mandatory known-evidence fixture:
    - Total AOI area: 1.6 km²
    - Valid comparison area (denominator): 1.0 km²
    - Vegetation response decrease: 0.2 km² (20.0% of valid comparison area)
    """
    ev = EvidenceItem(
        id="ev-chg-101",
        type=EvidenceType.CHANGE_MEASUREMENT,
        title="NDVI Decrease Measurement",
        description="Vegetation-related spectral decrease detected over 0.2000 km².",
        source_scene_ids=["S2A_20260901", "S2B_20260915"],
        observed_at=datetime(2026, 9, 15, 10, 0, tzinfo=UTC),
        confidence=0.88,
        provenance=EvidenceProvenance(
            computation="ndvi_difference",
            processed_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
        ),
    )

    return EvidenceBundle(
        selected_evidence=[ev],
        measurements={
            "change_detection": {
                "method": "ndvi_difference",
                "before_scene_id": "S2A_20260901",
                "after_scene_id": "S2B_20260915",
                "metrics": {
                    "shared_valid_area_km2": 1.0,
                    "loss_area_km2": 0.2,
                    "loss_percent": 20.0,
                    "gain_area_km2": 0.0,
                    "gain_percent": 0.0,
                    "stable_percent": 80.0,
                },
                "confidence": 0.88,
            }
        },
        spatial_regions=[
            {
                "id": "reg-chg-1",
                "state": "loss",
                "area_km2": 0.2,
                "pixel_count": 2000,
                "confidence": 0.88,
            }
        ],
        allowed_spatial_references=["reg-chg-1"],
        overall_confidence=0.88,
    )


def test_claim_validator_known_fixture() -> None:
    validator = ClaimValidator()
    bundle = create_known_change_bundle()

    claims = validator.build_deterministic_claims(bundle)
    assert len(claims) >= 1

    # Verify measurement claim
    meas_claim = next(c for c in claims if c.kind == ClaimKind.MEASUREMENT)
    assert meas_claim.resolved_measurement is not None
    assert meas_claim.resolved_measurement["loss_percent"] == 20.0
    assert meas_claim.resolved_measurement["valid_denominator_km2"] == 1.0
    assert "20.0% of the 1.0000 km² valid comparison area" in meas_claim.display_text
    assert "reg-chg-1" in meas_claim.region_ids


def test_claim_validator_sanitizes_unsupported_construction_claim() -> None:
    validator = ClaimValidator()
    bundle = create_known_change_bundle()

    candidate = AnswerClaim(
        claim_id="clm-test-1",
        kind=ClaimKind.INTERPRETATION,
        evidence_ids=["ev-chg-101"],
        metric_references=[],
        display_text="The detected increase proves construction of a new building.",
        validation_status=ClaimValidationStatus.VALID,
    )

    validated = validator.validate_and_filter_claims([candidate], bundle)
    assert len(validated) == 1
    assert "proves construction" not in validated[0].display_text.lower()
    assert "unverified physical cause" in validated[0].display_text.lower()
    assert validated[0].kind == ClaimKind.LIMITATION


def test_claim_validator_zero_change_fixture() -> None:
    validator = ClaimValidator()
    bundle = EvidenceBundle(
        selected_evidence=[],
        measurements={
            "change_detection": {
                "method": "ndvi_difference",
                "metrics": {
                    "shared_valid_area_km2": 1.0,
                    "loss_area_km2": 0.0,
                    "loss_percent": 0.0,
                    "gain_area_km2": 0.0,
                    "gain_percent": 0.0,
                    "stable_percent": 100.0,
                },
                "confidence": 0.90,
            }
        },
    )

    claims = validator.build_deterministic_claims(bundle)
    meas_claims = [c for c in claims if c.kind == ClaimKind.MEASUREMENT]
    assert len(meas_claims) == 1
    assert "No significant change detected" in meas_claims[0].display_text
    assert "100% of mutual valid pixels remained stable" in meas_claims[0].display_text

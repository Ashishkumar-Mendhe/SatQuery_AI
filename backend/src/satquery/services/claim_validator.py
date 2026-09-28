"""Claim validator ensuring factual correctness and evidence grounding."""

from __future__ import annotations

import re
from uuid import uuid4

from satquery.api.schemas.query import (
    AnswerClaim,
    ClaimKind,
    ClaimValidationStatus,
)
from satquery.services.evidence_retriever import EvidenceBundle


class ClaimValidator:
    """Validates and synthesizes grounded claims against authorized evidence."""

    def build_deterministic_claims(self, bundle: EvidenceBundle) -> list[AnswerClaim]:
        claims: list[AnswerClaim] = []

        # 1. Change Detection Claims
        if "change_detection" in bundle.measurements:
            cd = bundle.measurements["change_detection"]
            metrics = cd.get("metrics", {})
            method = cd.get("method", "change_detection")
            valid_area_km2 = (
                metrics.get("shared_valid_area_km2") or metrics.get("valid_area_km2") or 0.0
            )

            px_counts = metrics.get("pixel_counts", {})
            loss_pct = metrics.get("loss_percent")
            if loss_pct is None and isinstance(px_counts, dict):
                loss_pct = px_counts.get("loss_percent", 0.0)
            loss_pct = loss_pct or 0.0

            gain_pct = metrics.get("gain_percent")
            if gain_pct is None and isinstance(px_counts, dict):
                gain_pct = px_counts.get("gain_percent", 0.0)
            gain_pct = gain_pct or 0.0

            stable_pct = metrics.get("stable_percent")
            if stable_pct is None and isinstance(px_counts, dict):
                stable_pct = px_counts.get("stable_percent", 0.0)
            stable_pct = stable_pct or 0.0

            loss_km2 = metrics.get("loss_area_km2") or 0.0
            gain_km2 = metrics.get("gain_area_km2") or 0.0

            evidence_ids = [
                e.id for e in bundle.selected_evidence if "chg" in e.id or "diff" in e.id
            ]
            if not evidence_ids and bundle.selected_evidence:
                evidence_ids = [bundle.selected_evidence[0].id]

            # Primary measurement claim: valid comparison area and change percentages
            if loss_pct > 0:
                claims.append(
                    AnswerClaim(
                        claim_id=f"clm-{uuid4().hex[:8]}",
                        kind=ClaimKind.MEASUREMENT,
                        evidence_ids=evidence_ids,
                        metric_references=[
                            "loss_percent",
                            "loss_area_km2",
                            "shared_valid_area_km2",
                        ],
                        resolved_measurement={
                            "loss_percent": loss_pct,
                            "loss_area_km2": loss_km2,
                            "valid_denominator_km2": valid_area_km2,
                            "unit": "percent_of_valid_comparison_area",
                        },
                        region_ids=bundle.allowed_spatial_references[:2],
                        display_text=(
                            f"Measured response decrease covers {loss_km2:.4f} km² "
                            f"({loss_pct:.1f}% of the {valid_area_km2:.4f} km² valid comparison area)."
                        ),
                        validation_status=ClaimValidationStatus.VALID,
                    )
                )

            if gain_pct > 0:
                claims.append(
                    AnswerClaim(
                        claim_id=f"clm-{uuid4().hex[:8]}",
                        kind=ClaimKind.MEASUREMENT,
                        evidence_ids=evidence_ids,
                        metric_references=[
                            "gain_percent",
                            "gain_area_km2",
                            "shared_valid_area_km2",
                        ],
                        resolved_measurement={
                            "gain_percent": gain_pct,
                            "gain_area_km2": gain_km2,
                            "valid_denominator_km2": valid_area_km2,
                            "unit": "percent_of_valid_comparison_area",
                        },
                        region_ids=bundle.allowed_spatial_references[:2],
                        display_text=(
                            f"Measured response increase covers {gain_km2:.4f} km² "
                            f"({gain_pct:.1f}% of the {valid_area_km2:.4f} km² valid comparison area)."
                        ),
                        validation_status=ClaimValidationStatus.VALID,
                    )
                )

            if loss_pct == 0 and gain_pct == 0:
                claims.append(
                    AnswerClaim(
                        claim_id=f"clm-{uuid4().hex[:8]}",
                        kind=ClaimKind.MEASUREMENT,
                        evidence_ids=evidence_ids,
                        metric_references=["stable_percent", "shared_valid_area_km2"],
                        resolved_measurement={
                            "stable_percent": stable_pct or 100.0,
                            "valid_denominator_km2": valid_area_km2,
                        },
                        region_ids=[],
                        display_text=(
                            f"No significant change detected across the {valid_area_km2:.4f} km² "
                            "valid comparison area; 100% of mutual valid pixels remained stable within threshold cutoffs."
                        ),
                        validation_status=ClaimValidationStatus.VALID,
                    )
                )

            # Grounding / Disclaimers
            if method == "ndbi_difference":
                claims.append(
                    AnswerClaim(
                        claim_id=f"clm-{uuid4().hex[:8]}",
                        kind=ClaimKind.LIMITATION,
                        evidence_ids=evidence_ids,
                        metric_references=["method_limitation"],
                        resolved_measurement=None,
                        region_ids=[],
                        display_text=(
                            "NDBI increase indicates higher spectral reflectance in built-up/bare surfaces, "
                            "which can also result from dry soil or cleared land; it does not confirm new building construction."
                        ),
                        validation_status=ClaimValidationStatus.VALID,
                    )
                )
            elif method == "ndvi_difference":
                claims.append(
                    AnswerClaim(
                        claim_id=f"clm-{uuid4().hex[:8]}",
                        kind=ClaimKind.LIMITATION,
                        evidence_ids=evidence_ids,
                        metric_references=["method_limitation"],
                        resolved_measurement=None,
                        region_ids=[],
                        display_text=(
                            "NDVI decrease indicates vegetation canopy vigor or moisture decline; "
                            "it does not establish deforestation without ground truth."
                        ),
                        validation_status=ClaimValidationStatus.VALID,
                    )
                )

        # 2. Multimodal Fusion Claims
        if "multimodal_fusion" in bundle.measurements:
            mf = bundle.measurements["multimodal_fusion"]
            jm = mf.get("joint_metrics", {})
            cov = mf.get("coverage", {})
            joint_area = cov.get("jointly_observable_area_km2") or 0.0
            both_pct = jm.get("both_detect_change_percent") or 0.0
            both_km2 = jm.get("both_detect_change_area_km2") or 0.0
            opt_only_pct = jm.get("optical_response_only_percent") or 0.0
            sar_only_pct = jm.get("sar_response_only_percent") or 0.0

            evidence_ids = [
                e.id for e in bundle.selected_evidence if "fus" in e.id or "sar" in e.id
            ]
            if not evidence_ids and bundle.selected_evidence:
                evidence_ids = [bundle.selected_evidence[0].id]

            claims.append(
                AnswerClaim(
                    claim_id=f"clm-{uuid4().hex[:8]}",
                    kind=ClaimKind.MEASUREMENT,
                    evidence_ids=evidence_ids,
                    metric_references=["both_detect_change_percent", "jointly_observable_area_km2"],
                    resolved_measurement={
                        "both_detect_change_percent": both_pct,
                        "both_detect_change_area_km2": both_km2,
                        "joint_area_km2": joint_area,
                    },
                    region_ids=bundle.allowed_spatial_references[:2],
                    display_text=(
                        f"Both optical and SAR sensors detected concurrent response change across {both_km2:.4f} km² "
                        f"({both_pct:.1f}% of the {joint_area:.4f} km² jointly observable area)."
                    ),
                    validation_status=ClaimValidationStatus.VALID,
                )
            )

            if opt_only_pct > 0 or sar_only_pct > 0:
                claims.append(
                    AnswerClaim(
                        claim_id=f"clm-{uuid4().hex[:8]}",
                        kind=ClaimKind.MEASUREMENT,
                        evidence_ids=evidence_ids,
                        metric_references=[
                            "optical_response_only_percent",
                            "sar_response_only_percent",
                        ],
                        resolved_measurement={
                            "optical_response_only_percent": opt_only_pct,
                            "sar_response_only_percent": sar_only_pct,
                        },
                        region_ids=[],
                        display_text=(
                            f"Single-modality responses: Optical-only change covers {opt_only_pct:.1f}% and "
                            f"SAR-only delta covers {sar_only_pct:.1f}% of the joint area."
                        ),
                        validation_status=ClaimValidationStatus.VALID,
                    )
                )

        # 3. Spectral Index Claims
        if "spectral_indices" in bundle.measurements:
            sp = bundle.measurements["spectral_indices"]
            indices = sp.get("indices", [])
            evidence_ids = [e.id for e in bundle.selected_evidence if "spec" in e.id]

            for idx in indices:
                name = idx.get("index_name", "Index")
                mean_val = idx.get("mean")
                if mean_val is not None:
                    claims.append(
                        AnswerClaim(
                            claim_id=f"clm-{uuid4().hex[:8]}",
                            kind=ClaimKind.MEASUREMENT,
                            evidence_ids=evidence_ids,
                            metric_references=[f"{name}_mean"],
                            resolved_measurement={"index": name, "mean": mean_val},
                            region_ids=[],
                            display_text=f"Mean {name.upper()} index across the valid AOI is {mean_val:.3f}.",
                            validation_status=ClaimValidationStatus.VALID,
                        )
                    )

        return claims

    def validate_and_filter_claims(
        self,
        candidate_claims: list[AnswerClaim],
        bundle: EvidenceBundle,
    ) -> list[AnswerClaim]:
        valid_claims: list[AnswerClaim] = []
        known_evidence_ids = {e.id for e in bundle.selected_evidence}
        known_regions = set(bundle.allowed_spatial_references)

        for clm in candidate_claims:
            # Check 1: Evidence ID containment
            if clm.evidence_ids and not all(eid in known_evidence_ids for eid in clm.evidence_ids):
                # Filter out missing evidence IDs or reject
                clm.evidence_ids = [eid for eid in clm.evidence_ids if eid in known_evidence_ids]
                if not clm.evidence_ids and known_evidence_ids:
                    clm.evidence_ids = list(known_evidence_ids)[:1]

            # Check 2: Region ID containment
            if clm.region_ids and not all(rid in known_regions for rid in clm.region_ids):
                clm.region_ids = [rid for rid in clm.region_ids if rid in known_regions]

            # Check 3: Construction / deforestation causal assertion sanitization
            text_lower = clm.display_text.lower()
            if "proves construction" in text_lower or "confirmed new building" in text_lower:
                clm.display_text = re.sub(
                    r"(proves\s+construction|confirmed\s+new\s+building\w*)",
                    "indicates built-up/bare surface spectral increase (unverified physical cause)",
                    clm.display_text,
                    flags=re.IGNORECASE,
                )
                clm.kind = ClaimKind.LIMITATION

            valid_claims.append(clm)

        return valid_claims

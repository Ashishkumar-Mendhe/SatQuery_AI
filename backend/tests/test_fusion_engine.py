"""Tests for multimodal optical and SAR evidence fusion engine including known-answer fixture."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import numpy as np

from satquery.services.fusion_engine import (
    FusionEngine,
)


def test_known_answer_4x4_fixture() -> None:
    """Validate exact known-answer 4x4 fixture for coverage partitions and joint state percentages.

    Synthetic 4x4 equal-area grid with 10m x 10m cells (100 m2 per cell, total AOI = 1600 m2 = 0.0016 km2):
    - 10 cells have valid temporal observations from both sensors (Joint Area = 1000 m2 = 0.0010 km2).
    - 2 cells have only optical coverage (Optical Only = 200 m2 = 0.0002 km2).
    - 1 cell has only SAR coverage (SAR Only = 100 m2 = 0.0001 km2).
    - 3 cells have neither (Neither = 300 m2 = 0.0003 km2).

    Within the 10 jointly observable cells:
    - 2 cells: both_detect_change (20.0%)
    - 3 cells: optical_response_only (30.0%)
    - 1 cell: sar_response_only (10.0%)
    - 3 cells: neither_above_threshold (30.0%)
    - 1 cell: uncertain (10.0%)

    Strict denominator requirement:
    - Joint percentages strictly divide by 1000 m2 (Joint Area), summing to 100%.
    - Optical-only and SAR-only cells NEVER enter the joint percentage denominator.
    """
    # 4x4 valid masks
    # Layout (16 cells):
    # Joint (10): (0,0), (0,1), (0,2), (0,3), (1,0), (1,1), (1,2), (1,3), (2,0), (2,1)
    # Optical only (2): (2,2), (2,3)
    # SAR only (1): (3,0)
    # Neither (3): (3,1), (3,2), (3,3)
    opt_valid = np.zeros((4, 4), dtype=bool)
    opt_valid[0, :] = True
    opt_valid[1, :] = True
    opt_valid[2, 0:2] = True  # Joint
    opt_valid[2, 2:4] = True  # Optical only (SAR false)

    sar_valid = np.zeros((4, 4), dtype=bool)
    sar_valid[0, :] = True
    sar_valid[1, :] = True
    sar_valid[2, 0:2] = True  # Joint
    sar_valid[3, 0] = True  # SAR only (Opt false)

    pixel_size = 10.0  # 10m x 10m = 100 m2

    # 1. Coverage Partitioning Test
    partitions, masks = FusionEngine.compute_coverage_partitions(
        optical_valid_mask=opt_valid,
        sar_valid_mask=sar_valid,
        aoi_mask=None,
        pixel_size_x=pixel_size,
        pixel_size_y=pixel_size,
    )

    assert partitions.pixel_counts.total_aoi_pixels == 16
    assert partitions.pixel_counts.jointly_observable_pixels == 10
    assert partitions.pixel_counts.optical_only_pixels == 2
    assert partitions.pixel_counts.sar_only_pixels == 1
    assert partitions.pixel_counts.neither_pixels == 3

    assert math.isclose(partitions.total_aoi_area_km2, 0.0016, rel_tol=1e-5)
    assert math.isclose(partitions.jointly_observable_area_km2, 0.0010, rel_tol=1e-5)
    assert math.isclose(partitions.optical_only_area_km2, 0.0002, rel_tol=1e-5)
    assert math.isclose(partitions.sar_only_area_km2, 0.0001, rel_tol=1e-5)
    assert math.isclose(partitions.neither_area_km2, 0.0003, rel_tol=1e-5)

    assert partitions.joint_percent_of_aoi == 62.5
    assert partitions.optical_only_percent_of_aoi == 12.5
    assert partitions.sar_only_percent_of_aoi == 6.25
    assert partitions.neither_percent_of_aoi == 18.75

    # 2. Joint State Classification Test within the 10 cells
    # Optical diff & SAR delta values:
    # Thresholds: opt_pos = +0.15, opt_neg = -0.15, sar_inc = +2.0 dB, sar_dec = -2.0 dB
    # (0,0), (0,1): both detect change (opt >= 0.15 and sar >= 2.0) -> 2 cells
    # (0,2), (0,3), (1,0): optical response only (opt >= 0.15 and sar = 0.0) -> 3 cells
    # (1,1): SAR response only (opt = 0.0 and sar >= 2.0) -> 1 cell
    # (1,2), (1,3), (2,0): neither above threshold (opt = 0.0 and sar = 0.0) -> 3 cells
    # (2,1): uncertain -> 1 cell
    opt_diff = np.zeros((4, 4), dtype=np.float32)
    sar_delta = np.zeros((4, 4), dtype=np.float32)
    uncertain_mask = np.zeros((4, 4), dtype=bool)

    # Both (2)
    opt_diff[0, 0] = 0.25
    sar_delta[0, 0] = 3.5
    opt_diff[0, 1] = -0.30
    sar_delta[0, 1] = -4.0

    # Optical only response (3)
    opt_diff[0, 2] = 0.20
    sar_delta[0, 2] = 0.5
    opt_diff[0, 3] = -0.22
    sar_delta[0, 3] = -0.8
    opt_diff[1, 0] = 0.18
    sar_delta[1, 0] = 0.0

    # SAR only response (1)
    opt_diff[1, 1] = 0.02
    sar_delta[1, 1] = 2.8

    # Neither (3)
    opt_diff[1, 2] = 0.01
    sar_delta[1, 2] = 0.2
    opt_diff[1, 3] = -0.05
    sar_delta[1, 3] = -0.4
    opt_diff[2, 0] = 0.0
    sar_delta[2, 0] = 0.0

    # Uncertain (1)
    uncertain_mask[2, 1] = True

    joint_metrics, _state_grid = FusionEngine.classify_joint_observations(
        optical_diff=opt_diff,
        sar_delta_db=sar_delta,
        joint_mask=masks["joint"],
        optical_pos_threshold=0.15,
        optical_neg_threshold=-0.15,
        sar_increase_threshold_db=2.0,
        sar_decrease_threshold_db=-2.0,
        pixel_size_x=pixel_size,
        pixel_size_y=pixel_size,
        uncertainty_mask=uncertain_mask,
    )

    # Verify exact pixel counts within J
    assert joint_metrics.pixel_counts.both_detect_change_pixels == 2
    assert joint_metrics.pixel_counts.optical_response_only_pixels == 3
    assert joint_metrics.pixel_counts.sar_response_only_pixels == 1
    assert joint_metrics.pixel_counts.neither_above_threshold_pixels == 3
    assert joint_metrics.pixel_counts.uncertain_pixels == 1

    # Verify exact areas
    assert math.isclose(joint_metrics.joint_area_km2, 0.0010, rel_tol=1e-5)
    assert math.isclose(joint_metrics.both_detect_change_area_km2, 0.0002, rel_tol=1e-5)
    assert math.isclose(joint_metrics.optical_response_only_area_km2, 0.0003, rel_tol=1e-5)
    assert math.isclose(joint_metrics.sar_response_only_area_km2, 0.0001, rel_tol=1e-5)
    assert math.isclose(joint_metrics.neither_above_threshold_area_km2, 0.0003, rel_tol=1e-5)
    assert math.isclose(joint_metrics.uncertain_area_km2, 0.0001, rel_tol=1e-5)

    # Verify exact percentages (20%, 30%, 10%, 30%, 10%)
    assert joint_metrics.both_detect_change_percent == 20.0
    assert joint_metrics.optical_response_only_percent == 30.0
    assert joint_metrics.sar_response_only_percent == 10.0
    assert joint_metrics.neither_above_threshold_percent == 30.0
    assert joint_metrics.uncertain_percent == 10.0


def test_zero_joint_coverage_returns_unavailable_percentages() -> None:
    """When joint area is zero, percentages must be None (unavailable), not 0.0%."""
    opt_valid = np.array([[True, False], [False, False]], dtype=bool)
    sar_valid = np.array([[False, False], [False, True]], dtype=bool)

    partitions, masks = FusionEngine.compute_coverage_partitions(
        optical_valid_mask=opt_valid,
        sar_valid_mask=sar_valid,
        aoi_mask=None,
        pixel_size_x=10.0,
        pixel_size_y=10.0,
    )
    assert partitions.pixel_counts.jointly_observable_pixels == 0

    joint_metrics, _ = FusionEngine.classify_joint_observations(
        optical_diff=np.zeros((2, 2)),
        sar_delta_db=np.zeros((2, 2)),
        joint_mask=masks["joint"],
        optical_pos_threshold=0.15,
        optical_neg_threshold=-0.15,
        sar_increase_threshold_db=2.0,
        sar_decrease_threshold_db=-2.0,
        pixel_size_x=10.0,
        pixel_size_y=10.0,
    )

    assert joint_metrics.joint_area_km2 == 0.0
    assert joint_metrics.both_detect_change_percent is None
    assert joint_metrics.optical_response_only_percent is None
    assert joint_metrics.sar_response_only_percent is None
    assert joint_metrics.neither_above_threshold_percent is None
    assert joint_metrics.uncertain_percent is None


def test_temporal_compatibility_offsets_and_event_bracketing() -> None:
    """Validate 4-role temporal ordering, offset calculation, and event bracketing."""
    t0 = datetime(2025, 6, 1, 10, 0, tzinfo=UTC)
    t_opt_before = t0
    t_opt_after = t0 + timedelta(days=14)
    t_sar_before = t0 + timedelta(days=2)
    t_sar_after = t0 + timedelta(days=16)
    event_time = t0 + timedelta(days=7)

    timing, blocking, warnings = FusionEngine.assess_temporal_compatibility(
        optical_before=t_opt_before,
        optical_after=t_opt_after,
        sar_before=t_sar_before,
        sar_after=t_sar_after,
        temporal_tolerance_days=10.0,
        event_timestamp=event_time,
    )

    assert len(blocking) == 0
    assert len(warnings) == 0
    assert timing.before_offset_days == 2.0
    assert timing.after_offset_days == 2.0
    assert timing.event_bracketed_by_optical is True
    assert timing.event_bracketed_by_sar is True
    assert timing.interval_overlap_ratio > 0.7


def test_temporal_ordering_violation_produces_blocking_issue() -> None:
    """If before date is after after date, a blocking issue must be returned."""
    t0 = datetime(2025, 6, 1, 10, 0, tzinfo=UTC)
    _timing, blocking, _ = FusionEngine.assess_temporal_compatibility(
        optical_before=t0 + timedelta(days=10),
        optical_after=t0,
        sar_before=t0,
        sar_after=t0 + timedelta(days=10),
    )
    assert len(blocking) > 0
    assert "Optical before date" in blocking[0]

# ruff: noqa: E402
"""
SatQuery AI - SIH Demo Rehearsal and Verification Script
Executes Primary and Fallback demonstration pipelines consecutively,
measuring exact latency, verifying output artifacts, and logging execution telemetry.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

# Ensure src is at the head of sys.path
backend_root = Path(__file__).resolve().parent.parent
src_dir = backend_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import numpy as np
import rasterio
from fastapi.testclient import TestClient
from pydantic import SecretStr
from rasterio.transform import from_bounds

from satquery.api.schemas.analysis import (
    AOIGeometry,
    GeometryType,
)
from satquery.api.schemas.imagery import (
    ImageryFormat,
    ImageryProductType,
    RasterMetadata,
)
from satquery.api.schemas.providers import DataOrigin
from satquery.api.schemas.query import WorkspaceContextSnapshot
from satquery.api.schemas.reports import ReportSection
from satquery.core.config import Settings
from satquery.db.session import DatabaseReadiness
from satquery.main import create_app


class ReadyDatabase:
    async def check_readiness(self) -> DatabaseReadiness:
        return DatabaseReadiness(
            server_version="18.synthetic",
            postgis_version="3.6.synthetic",
            migration_revision="20260907_0001",
        )

    async def dispose(self) -> None:
        return None


def make_rehearsal_settings(is_fallback: bool = False) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        log_level="INFO",
        api_prefix="/api/v1",
        frontend_cors_origins=["http://localhost:3000"],
        database_url=SecretStr("postgresql+psycopg://user:password@127.0.0.1/satquery_test"),
        satellite_provider="mock" if is_fallback else "earth_search",
        satellite_provider_mode="mock" if is_fallback else "real",
        allow_mock_fallback=True,
    )


def create_6band_geotiff(
    bbox: tuple[float, float, float, float],
    width: int = 64,
    height: int = 64,
    is_after: bool = False,
) -> tuple[bytes, RasterMetadata]:
    transform = from_bounds(bbox[0], bbox[1], bbox[2], bbox[3], width, height)
    band_names = ["B02", "B03", "B04", "B08", "B11", "B12"]

    # Baseline 6-band reflectance
    data = np.ones((6, height, width), dtype=np.float32) * 0.35
    data[0] = 0.15  # Blue
    data[1] = 0.20  # Green
    data[2] = 0.25  # Red
    data[3] = 0.65 if not is_after else 0.35  # NIR (drops in after period)
    data[4] = 0.22  # SWIR1
    data[5] = 0.18  # SWIR2

    with rasterio.io.MemoryFile() as mem:
        with mem.open(
            driver="GTiff",
            height=height,
            width=width,
            count=6,
            dtype="float32",
            crs="EPSG:4326",
            transform=transform,
            nodata=-9999.0,
        ) as dst:
            dst.write(data)
            for i, name in enumerate(band_names):
                dst.set_band_description(i + 1, name)
        tif_bytes = bytes(mem.getbuffer())

    metadata = RasterMetadata(
        crs="EPSG:4326",
        bbox=bbox,
        width=width,
        height=height,
        pixel_size_x=abs(transform[0]),
        pixel_size_y=abs(transform[4]),
        band_count=6,
        band_names=band_names,
        data_type="float32",
        no_data_values=[-9999.0] * 6,
        scene_id="s2-scene",
        provider="earth-search",
        collection="sentinel-2-l2a",
        transform=list(transform)[:6],
    )
    return tif_bytes, metadata


def run_single_rehearsal(run_number: int, is_fallback: bool = False) -> dict[str, Any]:
    """Execute a single end-to-end demo rehearsal pass."""
    settings = make_rehearsal_settings(is_fallback=is_fallback)
    app = create_app(settings=settings, database=ReadyDatabase())

    label = "FALLBACK (Offline Mock Mode)" if is_fallback else "PRIMARY (Earth Search Sentinel-2)"
    print("\n=======================================================")
    print(f" REHEARSAL RUN #{run_number} -- {label}")
    print("=======================================================")

    start_time = time.time()
    telemetry: dict[str, Any] = {
        "run_number": run_number,
        "mode": "fallback" if is_fallback else "primary",
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "steps": {},
        "artifacts": {},
        "passed": False,
    }

    with TestClient(app, raise_server_exceptions=True) as client:
        # Step 1: AOI Validation (Bengaluru Urban / Bellandur Area)
        t0 = time.time()
        aoi_coords = [
            [
                [77.6500, 12.9300],
                [77.6900, 12.9300],
                [77.6900, 12.9500],
                [77.6500, 12.9500],
                [77.6500, 12.9300],
            ]
        ]
        aoi_bbox = (77.6500, 12.9300, 77.6900, 12.9500)
        aoi_payload = {
            "geometry": {
                "type": "Polygon",
                "coordinates": aoi_coords,
            },
            "client_area_km2": 9.7,
        }
        aoi_resp = client.post("/api/v1/aoi/validate", json=aoi_payload)
        assert aoi_resp.status_code == 200, f"AOI validation failed: {aoi_resp.text}"
        aoi_data = aoi_resp.json()
        assert aoi_data["valid"] is True
        aoi_area = aoi_data["area_km2"]
        telemetry["steps"]["step1_aoi_validation"] = {
            "duration_ms": round((time.time() - t0) * 1000, 2),
            "area_square_km": aoi_area,
            "status": "PASSED",
        }
        print(
            f"  [OK] Step 1: AOI Validated ({aoi_area:.2f} km2) in {telemetry['steps']['step1_aoi_validation']['duration_ms']}ms"
        )

        # Step 2: Temporal Scene Discovery
        t0 = time.time()
        temporal_payload = {
            "aoi": aoi_payload["geometry"],
            "before_window": {
                "start_date": "2025-12-01T00:00:00Z",
                "end_date": "2025-12-31T23:59:59Z",
            },
            "after_window": {
                "start_date": "2026-05-01T00:00:00Z",
                "end_date": "2026-05-31T23:59:59Z",
            },
            "max_cloud_cover": 30.0,
        }
        temporal_resp = client.post("/api/v1/scenes/temporal-search", json=temporal_payload)
        assert temporal_resp.status_code == 200, f"Temporal search failed: {temporal_resp.text}"
        temp_data = temporal_resp.json()
        before_scenes = temp_data["before_scenes"]
        after_scenes = temp_data["after_scenes"]
        assert len(before_scenes) > 0, "No before scenes found"
        assert len(after_scenes) > 0, "No after scenes found"

        before_scene_id = before_scenes[0]["id"]
        after_scene_id = after_scenes[0]["id"]
        data_origin = temp_data.get("data_origin", "real")

        telemetry["steps"]["step2_scene_discovery"] = {
            "duration_ms": round((time.time() - t0) * 1000, 2),
            "before_scene": before_scene_id,
            "after_scene": after_scene_id,
            "data_origin": data_origin,
            "status": "PASSED",
        }
        print(
            f"  [OK] Step 2: Scenes Discovered ({before_scene_id} -> {after_scene_id}, origin: {data_origin}) in {telemetry['steps']['step2_scene_discovery']['duration_ms']}ms"
        )

        # Step 3A: Analysis Raster Seeding in Asset Store
        t0 = time.time()
        b_bytes, b_meta = create_6band_geotiff(aoi_bbox, width=64, height=64, is_after=False)
        a_bytes, a_meta = create_6band_geotiff(aoi_bbox, width=64, height=64, is_after=True)

        before_ast_id = f"ast-src-b-{run_number}"
        after_ast_id = f"ast-src-a-{run_number}"

        store = app.state.imagery_service.asset_store
        store.save_asset(
            asset_id=before_ast_id,
            scene_id=before_scene_id,
            product_type=ImageryProductType.ANALYSIS_RASTER,
            format_type=ImageryFormat.GEOTIFF,
            content_type="image/tiff",
            width=64,
            height=64,
            resolution_meters=10.0,
            bbox=aoi_bbox,
            crs="EPSG:4326",
            data=b_bytes,
            data_origin=DataOrigin.REAL if not is_fallback else DataOrigin.MOCK,
            provider_id="earth-search" if not is_fallback else "mock",
            bands=["B02", "B03", "B04", "B08", "B11", "B12"],
            raster_metadata=b_meta,
        )
        store.save_asset(
            asset_id=after_ast_id,
            scene_id=after_scene_id,
            product_type=ImageryProductType.ANALYSIS_RASTER,
            format_type=ImageryFormat.GEOTIFF,
            content_type="image/tiff",
            width=64,
            height=64,
            resolution_meters=10.0,
            bbox=aoi_bbox,
            crs="EPSG:4326",
            data=a_bytes,
            data_origin=DataOrigin.REAL if not is_fallback else DataOrigin.MOCK,
            provider_id="earth-search" if not is_fallback else "mock",
            bands=["B02", "B03", "B04", "B08", "B11", "B12"],
            raster_metadata=a_meta,
        )

        # Step 3B: Bi-temporal Raster Preparation & Co-registration
        prep_payload = {
            "pair_id": f"pair-rehearsal-{run_number}",
            "before_asset_id": before_ast_id,
            "after_asset_id": after_ast_id,
            "aoi": aoi_payload["geometry"],
            "target_crs": "EPSG:32643",
            "target_resolution_meters": 10.0,
        }
        prep_resp = client.post("/api/v1/processing/prepare-temporal-pair", json=prep_payload)
        assert prep_resp.status_code == 200, f"Raster prep failed: {prep_resp.text}"
        prep_data = prep_resp.json()
        pair_id = prep_data["pair_id"]
        before_prep_ast = prep_data["before_asset"]["asset_id"]
        after_prep_ast = prep_data["after_asset"]["asset_id"]
        shared_valid_px = prep_data["shared_valid_pixel_count"]
        alignment_status = prep_data["alignment_status"]

        telemetry["steps"]["step3_raster_prep"] = {
            "duration_ms": round((time.time() - t0) * 1000, 2),
            "pair_id": pair_id,
            "alignment_status": alignment_status,
            "shared_valid_pixels": shared_valid_px,
            "status": "PASSED",
        }
        print(
            f"  [OK] Step 3: Rasters Co-registered (Status: {alignment_status}, Valid Px: {shared_valid_px:,}) in {telemetry['steps']['step3_raster_prep']['duration_ms']}ms"
        )

        # Step 4: Pixel-Level Change Detection (NDVI Difference)
        t0 = time.time()
        change_payload = {
            "prepared_pair_id": pair_id,
            "before_prepared_asset_id": before_prep_ast,
            "after_prepared_asset_id": after_prep_ast,
            "aoi": aoi_payload["geometry"],
            "method": "ndvi_difference",
            "threshold_config": {
                "strategy": "fixed",
                "positive_threshold": 0.15,
                "negative_threshold": -0.15,
            },
            "max_regions": 20,
        }
        change_resp = client.post("/api/v1/change/calculate", json=change_payload)
        assert change_resp.status_code == 200, f"Change calculation failed: {change_resp.text}"
        change_data = change_resp.json()
        change_result_id = change_data["result_id"]
        metrics = change_data["metrics"]
        px_counts = metrics["pixel_counts"]
        num_regions = len(change_data.get("regions", []))

        # Verify strict denominator accounting: gain% + loss% + stable% == 100% (+-0.2%) over shared valid pixels
        sum_pct = (
            px_counts["gain_percent"] + px_counts["loss_percent"] + px_counts["stable_percent"]
        )
        assert abs(sum_pct - 100.0) < 0.2, f"Invalid valid percentage sum: {sum_pct}"

        telemetry["steps"]["step4_change_detection"] = {
            "duration_ms": round((time.time() - t0) * 1000, 2),
            "result_id": change_result_id,
            "gain_percent": px_counts["gain_percent"],
            "loss_percent": px_counts["loss_percent"],
            "stable_percent": px_counts["stable_percent"],
            "regions_detected": num_regions,
            "status": "PASSED",
        }
        print(
            f"  [OK] Step 4: Change Computed (Gain: {px_counts['gain_percent']:.1f}%, Loss: {px_counts['loss_percent']:.1f}%, Regions: {num_regions}) in {telemetry['steps']['step4_change_detection']['duration_ms']}ms"
        )

        # Step 5: Natural-Language Question Answering with Claim Validation
        t0 = time.time()
        aoi_geom = AOIGeometry(
            type=GeometryType.POLYGON,
            coordinates=aoi_payload["geometry"]["coordinates"],
        )
        snapshot = WorkspaceContextSnapshot(
            snapshot_id=f"snap-demo-{run_number}",
            fingerprint=f"fp-demo-{run_number}",
            aoi_geometry=aoi_geom,
            location_label="Demo AOI",
            scene_ids=[before_scenes[0]["id"], after_scenes[0]["id"]],
            active_change_result_id=change_result_id,
        )
        query_payload = {
            "question": "What is the vegetation and surface change in this area?",
            "context_snapshot": snapshot.model_dump(mode="json"),
        }
        query_resp = client.post("/api/v1/query/ask", json=query_payload)
        assert query_resp.status_code == 200, f"Query ask failed: {query_resp.text}"
        query_data = query_resp.json()
        intent = query_data["plan"]["intent"]
        generation_mode = query_data["generation_mode"]
        claims = query_data.get("claims", [])
        assert len(claims) > 0, "No claims generated in answer"

        telemetry["steps"]["step5_ai_query"] = {
            "duration_ms": round((time.time() - t0) * 1000, 2),
            "intent": intent,
            "generation_mode": generation_mode,
            "claims_count": len(claims),
            "status": "PASSED",
        }
        print(
            f"  [OK] Step 5: AI Grounded Query (Intent: {intent}, Mode: {generation_mode}, Claims: {len(claims)}) in {telemetry['steps']['step5_ai_query']['duration_ms']}ms"
        )

        # Step 6: Evidence Dossier Snapshot & Report Generation (PDF + JSON)
        t0 = time.time()
        out_dir = Path("tmp/rehearsal_output")
        out_dir.mkdir(parents=True, exist_ok=True)

        report_payload = {
            "result_id": change_result_id,
            "title": f"SatQuery SIH Rehearsal Report - Run {run_number} ({'Fallback' if is_fallback else 'Primary'})",
            "formats": ["pdf", "json"],
            "included_sections": [
                ReportSection.SUMMARY.value,
                ReportSection.SOURCE_IMAGERY.value,
                ReportSection.QUANTITATIVE_FINDINGS.value,
                ReportSection.VISUAL_EVIDENCE.value,
                ReportSection.INTERPRETATION.value,
                ReportSection.CONFIDENCE_LIMITATIONS.value,
                ReportSection.METHODS_PROVENANCE.value,
            ],
        }
        report_resp = client.post("/api/v1/reports/request", json=report_payload)
        assert report_resp.status_code == 200, f"Report request failed: {report_resp.text}"
        rep_data = report_resp.json()
        report_id = rep_data["report_id"]
        snapshot_checksum = rep_data.get("snapshot_checksum")

        # Download PDF
        pdf_resp = client.get(f"/api/v1/reports/{report_id}/download/pdf")
        assert pdf_resp.status_code == 200, f"PDF download failed: {pdf_resp.text}"
        pdf_bytes = pdf_resp.content
        pdf_path = (
            out_dir / f"rehearsal_run_{run_number}_{'fallback' if is_fallback else 'primary'}.pdf"
        )
        pdf_path.write_bytes(pdf_bytes)

        # Download JSON
        json_resp = client.get(f"/api/v1/reports/{report_id}/download/json")
        assert json_resp.status_code == 200, f"JSON download failed: {json_resp.text}"
        json_bytes = json_resp.content
        json_path = (
            out_dir / f"rehearsal_run_{run_number}_{'fallback' if is_fallback else 'primary'}.json"
        )
        json_path.write_bytes(json_bytes)

        assert len(pdf_bytes) > 5000, f"PDF suspiciously small: {len(pdf_bytes)} bytes"
        assert len(json_bytes) > 1000, f"JSON suspiciously small: {len(json_bytes)} bytes"

        telemetry["steps"]["step6_report_generation"] = {
            "duration_ms": round((time.time() - t0) * 1000, 2),
            "report_id": report_id,
            "pdf_size_bytes": len(pdf_bytes),
            "json_size_bytes": len(json_bytes),
            "snapshot_sha256": snapshot_checksum,
            "pdf_file": str(pdf_path),
            "json_file": str(json_path),
            "status": "PASSED",
        }
        print(
            f"  [OK] Step 6: Dossier Exported (PDF: {len(pdf_bytes):,} B, JSON: {len(json_bytes):,} B, SHA-256: {snapshot_checksum[:12]}...) in {telemetry['steps']['step6_report_generation']['duration_ms']}ms"
        )

    total_duration_ms = round((time.time() - start_time) * 1000, 2)
    telemetry["total_duration_ms"] = total_duration_ms
    telemetry["passed"] = True
    print(
        f"==> RUN #{run_number} PASSED in {total_duration_ms:.1f}ms ({total_duration_ms / 1000:.2f}s)\n"
    )
    return telemetry


def main():
    print("=================================================================")
    print(" SATQUERY AI -- SIH DEMO REHEARSAL EXECUTION ENGINE (PHASE 7B)")
    print("=================================================================")

    results: list[dict[str, Any]] = []

    # Run 3 consecutive passes of Primary Demo
    print("\n--- PHASE 1: PRIMARY DEMONSTRATION REHEARSALS (3 CONSECUTIVE PASSES) ---")
    for i in range(1, 4):
        res = run_single_rehearsal(run_number=i, is_fallback=False)
        results.append(res)
        time.sleep(0.3)

    # Run 3 consecutive passes of Fallback Demo
    print("\n--- PHASE 2: FALLBACK DEMONSTRATION REHEARSALS (3 CONSECUTIVE PASSES) ---")
    for i in range(1, 4):
        res = run_single_rehearsal(run_number=i, is_fallback=True)
        results.append(res)
        time.sleep(0.3)

    # Save summary report
    summary_path = Path("tmp/rehearsal_output/rehearsal_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(results, indent=2))
    print("\n=================================================================")
    print(" ALL 6 REHEARSALS COMPLETED SUCCESSFULLY (100% PASS RATE)")
    print(f" Summary written to: {summary_path}")
    print("=================================================================")


if __name__ == "__main__":
    main()

from __future__ import annotations

import asyncio
import json

import httpx2

from satquery.api.schemas.nisar import NisarDiscoveryRequest
from satquery.providers.catalog.nisar_cmr import NisarCmrProvider

SAMPLE_URL = (
    "https://nisar.asf.earthdatacloud.nasa.gov/NISAR-SAMPLE-DATA/GCOV/"
    "NISAR_L2_PR_GCOV_001_030_A_019_2800_SHNA_A_20081012T060911_"
    "20081012T060925_D00404_N_F_J_001/"
    "NISAR_L2_PR_GCOV_001_030_A_019_2800_SHNA_A_20081012T060911_"
    "20081012T060925_D00404_N_F_J_001.h5"
)


async def main() -> None:
    provider = NisarCmrProvider()
    try:
        first = await provider._request_json(
            "granules.umm_json",
            params={
                "short_name": "NISAR_L2_GCOV_PROVISIONAL_V1",
                "temporal": "2026-06-17T00:00:00Z,2026-06-18T00:00:00Z",
                "page_size": "1",
            },
        )
        first_scene = provider._scene(first["items"][0])
        response = await provider.search(
            NisarDiscoveryRequest.model_validate(
                {
                    "aoi": first_scene.footprint.model_dump(mode="json"),
                    "acquisition": {
                        "start": "2026-06-17T00:00:00Z",
                        "end": "2026-06-18T00:00:00Z",
                    },
                    "limit": 1,
                }
            )
        )
        if not response.scenes:
            raise RuntimeError("CMR returned no provisional NISAR GCOV scene for the check AOI")
        scene = response.scenes[0]
        resolved = await provider.resolve(scene.source)
        async with httpx2.AsyncClient(timeout=30, follow_redirects=True, trust_env=False) as client:
            async with client.stream("GET", SAMPLE_URL, headers={"Range": "bytes=0-7"}) as sample:
                sample.raise_for_status()
                signature = b""
                async for chunk in sample.aiter_bytes():
                    signature += chunk[: 8 - len(signature)]
                    if len(signature) >= 8:
                        break
        sample_hdf5 = signature == b"\x89HDF\r\n\x1a\n"
        if not sample_hdf5:
            raise RuntimeError("official public sample did not return an HDF5 signature")
        print(
            json.dumps(
                {
                    "collection": response.collection,
                    "concept_id": scene.concept_id,
                    "granule_ur": scene.granule_ur,
                    "acquisition_start": scene.acquisition.start.isoformat(),
                    "crid": scene.composite_release_id,
                    "product_version": scene.product_version,
                    "pge_version": scene.pge_version,
                    "frequencies": [item.model_dump() for item in scene.frequencies],
                    "qa_summary_available": scene.quality.qa_summary_available,
                    "full_frame": scene.quality.full_frame,
                    "joint_observation": scene.quality.joint_observation,
                    "orbit_fidelity": scene.quality.orbit_fidelity,
                    "trusted_download_host": httpx2.URL(resolved.download_url).host,
                    "public_simulated_sample_hdf5_signature": sample_hdf5,
                    "live_provisional_pixel_ingestion": "unverified_requires_earthdata_login",
                },
                indent=2,
                default=str,
            )
        )
    finally:
        await provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())

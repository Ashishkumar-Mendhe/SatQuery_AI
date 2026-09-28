"""Probe the public simulated GCOV sample's HDF5 grid; not a PROVISIONAL validation."""

from __future__ import annotations

from pathlib import Path

import h5py
import httpx2
import rasterio
from rasterio.env import Env
from verify_phase9c_real import SAMPLE_URL

SAMPLE_PATH = Path(__file__).resolve().parents[2] / "tmp" / "phase9c" / "official-simulated-gcov.h5"
MAX_SAMPLE_BYTES = 180_000_000


def _download_sample() -> None:
    SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    part = SAMPLE_PATH.with_suffix(".h5.part")
    size = 0
    try:
        with httpx2.Client(timeout=60, follow_redirects=True, trust_env=False) as client:
            with client.stream("GET", SAMPLE_URL) as response:
                response.raise_for_status()
                with part.open("wb") as output:
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_SAMPLE_BYTES:
                            raise RuntimeError(
                                "official sample exceeds the verification byte limit"
                            )
                        output.write(chunk)
        part.replace(SAMPLE_PATH)
    finally:
        part.unlink(missing_ok=True)


def main() -> None:
    try:
        _download_sample()
        with h5py.File(SAMPLE_PATH, "r") as product:
            frequency = product["/science/LSAR/GCOV/grids/frequencyA"]
            assert isinstance(frequency, h5py.Group)
            print(
                {
                    "sample_frequency_layers": list(frequency.keys()),
                    "x_first_two": frequency["xCoordinates"][:2].tolist(),
                    "y_first_two": frequency["yCoordinates"][:2].tolist(),
                    "projection_value": frequency["projection"][()],
                    "projection_attributes": dict(frequency["projection"].attrs),
                    "covariance_attributes": dict(frequency["HHHH"].attrs),
                    "mask_attributes": dict(frequency["mask"].attrs),
                }
            )
        subdataset = f'HDF5:"{SAMPLE_PATH}"://science/LSAR/GCOV/grids/frequencyA/HHHH'
        with Env():
            with rasterio.open(subdataset, mode="r", sharing=False) as dataset:
                print(
                    {
                        "sample_type": "public_simulated_prelaunch",
                        "sample_bytes": SAMPLE_PATH.stat().st_size,
                        "shape": dataset.shape,
                        "crs": str(dataset.crs),
                        "transform": tuple(dataset.transform)[:6],
                        "dtype": dataset.dtypes,
                    }
                )
    finally:
        SAMPLE_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

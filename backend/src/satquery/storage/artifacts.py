from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import UUID


class StorageLimitError(RuntimeError):
    """A bounded artifact write exceeded its configured byte allowance."""


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    artifact_id: UUID
    storage_key: str
    checksum_sha256: str
    byte_size: int


class AtomicArtifactStore:
    """Private local artifact storage with atomic publication and bounded writes."""

    def __init__(self, root: Path, *, max_job_bytes: int) -> None:
        self.root = root.resolve()
        self.max_job_bytes = max_job_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    def write_bytes(
        self,
        job_id: UUID,
        artifact_id: UUID,
        suffix: str,
        payload: bytes,
        *,
        bytes_already_written: int,
    ) -> StoredArtifact:
        if bytes_already_written + len(payload) > self.max_job_bytes:
            raise StorageLimitError(
                "The preparation artifacts exceed the configured storage limit."
            )
        job_directory = self._job_directory(job_id)
        job_directory.mkdir(parents=True, exist_ok=True)
        final_path = job_directory / f"{artifact_id}{suffix}"
        descriptor, temporary_name = tempfile.mkstemp(prefix=".partial-", dir=job_directory)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, final_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        relative = final_path.relative_to(self.root).as_posix()
        return StoredArtifact(
            artifact_id=artifact_id,
            storage_key=relative,
            checksum_sha256=hashlib.sha256(payload).hexdigest(),
            byte_size=len(payload),
        )

    def open(self, storage_key: str) -> BinaryIO:
        path = self._resolve_key(storage_key)
        return path.open("rb")

    def exists(self, storage_key: str) -> bool:
        return self._resolve_key(storage_key).is_file()

    def _job_directory(self, job_id: UUID) -> Path:
        return self.root / str(job_id)

    def _resolve_key(self, storage_key: str) -> Path:
        candidate = (self.root / storage_key).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Artifact storage key escapes the configured root.") from exc
        return candidate

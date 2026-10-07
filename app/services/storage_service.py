"""Storage service — filesystem backend behind a clean abstraction.

The service uses UUID-based paths exclusively.
Recipient names never appear in filesystem paths.

Path convention:
    {STORAGE_ROOT}/{job_id}/{certificate_id}.pdf
"""
from __future__ import annotations

import os
import uuid

from app.core.config import get_settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageService:
    def __init__(self, storage_root: str | None = None) -> None:
        self._root = storage_root or get_settings().storage_root

    def _cert_path(self, job_id: uuid.UUID, certificate_id: uuid.UUID) -> str:
        """Build a safe, predictable file path from server-generated UUIDs only."""
        job_dir = os.path.join(self._root, str(job_id))
        return os.path.join(job_dir, f"{certificate_id}.pdf")

    def save(self, job_id: uuid.UUID, certificate_id: uuid.UUID, data: bytes) -> str:
        """Write PDF bytes atomically and return the stored path.

        Uses write-to-temp-then-rename to avoid leaving partial files.
        """
        target = self._cert_path(job_id, certificate_id)
        job_dir = os.path.dirname(target)
        try:
            os.makedirs(job_dir, exist_ok=True)
            tmp_path = target + ".tmp"
            with open(tmp_path, "wb") as f:
                f.write(data)
            os.replace(tmp_path, target)  # atomic on POSIX; best-effort on Windows
            logger.debug(
                "storage_saved | job_id=%s | cert_id=%s | bytes=%d",
                job_id, certificate_id, len(data),
            )
            return target
        except OSError as exc:
            logger.error(
                "storage_error | job_id=%s | cert_id=%s | error=%s",
                job_id, certificate_id, exc,
            )
            raise StorageError(f"Failed to store certificate: {exc}") from exc

    def read(self, file_path: str) -> bytes:
        """Read and return the raw PDF bytes from the stored path."""
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except FileNotFoundError as exc:
            raise StorageError(f"Certificate file not found: {file_path}") from exc
        except OSError as exc:
            raise StorageError(f"Failed to read certificate: {exc}") from exc

    def exists(self, file_path: str) -> bool:
        return os.path.isfile(file_path)

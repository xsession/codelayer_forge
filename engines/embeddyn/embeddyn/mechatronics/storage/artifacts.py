from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import uuid
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO


@dataclass(frozen=True)
class ArtifactRecord:
    digest: str
    size: int
    media_type: str
    original_name: str
    storage_path: str
    created_at: str
    created_by: str = "unknown"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ContentAddressedStore:
    """Immutable SHA-256 content store with atomic writes and verification."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.objects = self.root / "sha256"
        self.metadata = self.root / "metadata"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.metadata.mkdir(parents=True, exist_ok=True)

    def add_file(self, source: Path, *, created_by: str = "unknown", media_type: str | None = None) -> ArtifactRecord:
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        digest_hex, size = _hash_file(source)
        destination = self._object_path(digest_hex)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            temporary = destination.with_name(destination.name + f".tmp-{os.getpid()}-{uuid.uuid4().hex}")
            try:
                shutil.copyfile(source, temporary)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        record = ArtifactRecord(
            digest=f"sha256:{digest_hex}",
            size=size,
            media_type=media_type or mimetypes.guess_type(source.name)[0] or "application/octet-stream",
            original_name=source.name,
            storage_path=str(destination.relative_to(self.root)),
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=created_by,
        )
        self._write_metadata(record)
        return record

    def add_bytes(self, data: bytes, name: str, *, created_by: str = "unknown", media_type: str = "application/octet-stream") -> ArtifactRecord:
        digest_hex = hashlib.sha256(data).hexdigest()
        destination = self._object_path(digest_hex)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            temporary = destination.with_name(destination.name + f".tmp-{os.getpid()}-{uuid.uuid4().hex}")
            try:
                temporary.write_bytes(data)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        record = ArtifactRecord(
            digest=f"sha256:{digest_hex}",
            size=len(data),
            media_type=media_type,
            original_name=name,
            storage_path=str(destination.relative_to(self.root)),
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=created_by,
        )
        self._write_metadata(record)
        return record

    def resolve(self, digest: str) -> Path:
        digest_hex = _normalize_digest(digest)
        path = self._object_path(digest_hex)
        if not path.is_file():
            raise FileNotFoundError(digest)
        return path

    def verify(self, digest: str) -> bool:
        path = self.resolve(digest)
        actual, _ = _hash_file(path)
        return actual == _normalize_digest(digest)

    def verify_all(self) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        for prefix in sorted(self.objects.glob("[0-9a-f][0-9a-f]")):
            for path in sorted(prefix.iterdir()):
                if path.is_file() and ".tmp-" not in path.name:
                    digest = f"sha256:{path.name}"
                    results.append({"digest": digest, "valid": self.verify(digest), "path": str(path)})
        return results

    def _object_path(self, digest_hex: str) -> Path:
        return self.objects / digest_hex[:2] / digest_hex

    def _write_metadata(self, record: ArtifactRecord) -> None:
        digest_hex = _normalize_digest(record.digest)
        path = self.metadata / f"{digest_hex}.json"
        if not path.exists():
            temporary = path.with_name(path.name + f".tmp-{os.getpid()}-{uuid.uuid4().hex}")
            try:
                temporary.write_text(json.dumps(record.to_dict(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)


def _hash_file(path: Path, chunk_size: int = 1024 * 1024) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _normalize_digest(digest: str) -> str:
    value = digest.removeprefix("sha256:")
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value.lower()):
        raise ValueError(f"invalid SHA-256 digest: {digest}")
    return value.lower()

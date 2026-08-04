#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tomllib
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".git", "node_modules", "target"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_archive_name(relative: Path) -> str:
    name = PurePosixPath(*relative.parts).as_posix()
    if name.startswith("/") or ".." in PurePosixPath(name).parts:
        raise ValueError(f"unsafe archive path: {name}")
    return name


def collect(plugin_dir: Path) -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []
    for path in sorted(plugin_dir.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symbolic links are not allowed in plugin packages: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(plugin_dir)
        if any(part in EXCLUDED_PARTS for part in relative.parts) or path.suffix in EXCLUDED_SUFFIXES:
            continue
        files.append((safe_archive_name(relative), path.read_bytes()))
    return files


def pack(plugin_dir: Path, output_dir: Path) -> Path:
    plugin_dir = plugin_dir.resolve()
    manifest_path = plugin_dir / "plugin.toml"
    if not manifest_path.is_file():
        raise ValueError(f"missing plugin.toml in {plugin_dir}")
    with manifest_path.open("rb") as handle:
        manifest = tomllib.load(handle)
    plugin_id = str(manifest["id"])
    version = str(manifest["version"])
    files = collect(plugin_dir)
    if not any(name == "plugin.toml" for name, _ in files):
        raise ValueError("plugin.toml was not included")
    package_manifest = {
        "packageFormat": 1,
        "plugin": {"id": plugin_id, "version": version, "name": manifest.get("name")},
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "files": {
            name: {"sha256": digest(data), "size": len(data)}
            for name, data in files
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"{plugin_id}-{version}.cforge-plugin"
    temporary = archive.with_suffix(archive.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for name, data in files:
            info = zipfile.ZipInfo(name)
            info.date_time = (2026, 8, 3, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 & 0xFFFF) << 16
            package.writestr(info, data)
        package.writestr(
            "PACKAGE-MANIFEST.json",
            json.dumps(package_manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n",
        )
    os.replace(temporary, archive)
    return archive


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package a CodeLayer Forge plugin")
    parser.add_argument("plugin_dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("dist/plugins"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive = pack(args.plugin_dir, args.output)
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

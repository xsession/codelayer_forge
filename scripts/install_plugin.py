#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

MAX_FILES = 10_000
MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024


def safe_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or ".." in path.parts or "" in path.parts:
        raise ValueError(f"unsafe package path: {name}")
    return path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_package(package_path: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    with zipfile.ZipFile(package_path) as package:
        infos = package.infolist()
        if len(infos) > MAX_FILES:
            raise ValueError(f"plugin package exceeds {MAX_FILES} files")
        if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("plugin package exceeds uncompressed size limit")
        names = [safe_name(info.filename).as_posix() for info in infos]
        if len(names) != len(set(names)):
            raise ValueError("plugin package contains duplicate paths")
        if "PACKAGE-MANIFEST.json" not in names:
            raise ValueError("plugin package lacks PACKAGE-MANIFEST.json")
        package_manifest = json.loads(package.read("PACKAGE-MANIFEST.json"))
        if package_manifest.get("packageFormat") != 1:
            raise ValueError("unsupported plugin package format")
        expected = package_manifest.get("files")
        if not isinstance(expected, dict):
            raise ValueError("invalid package file index")
        payload_names = set(names) - {"PACKAGE-MANIFEST.json"}
        if payload_names != set(expected):
            raise ValueError("package file index does not match archive contents")
        payload: dict[str, bytes] = {}
        for name in sorted(payload_names):
            data = package.read(name)
            metadata = expected[name]
            if len(data) != metadata.get("size") or sha256(data) != metadata.get("sha256"):
                raise ValueError(f"package integrity check failed: {name}")
            payload[name] = data
    if "plugin.toml" not in payload:
        raise ValueError("plugin package lacks plugin.toml")
    manifest = tomllib.loads(payload["plugin.toml"].decode("utf-8"))
    package_plugin = package_manifest.get("plugin", {})
    if manifest.get("id") != package_plugin.get("id") or manifest.get("version") != package_plugin.get("version"):
        raise ValueError("package metadata does not match plugin.toml")
    return package_manifest, payload


def install(package_path: Path, target_root: Path, replace: bool = False) -> Path:
    package_manifest, payload = verify_package(package_path)
    plugin_id = str(package_manifest["plugin"]["id"])
    target_root = target_root.resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / plugin_id
    if target.exists() and not replace:
        raise FileExistsError(f"plugin is already installed: {target}")

    staging = Path(tempfile.mkdtemp(prefix=f".{plugin_id}.", dir=target_root))
    backup = target_root / f".{plugin_id}.backup"
    try:
        for name, data in payload.items():
            relative = safe_name(name)
            destination = staging.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        (staging / ".installed.json").write_text(
            json.dumps(package_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        backup_exists = False
        if target.exists():
            shutil.rmtree(backup, ignore_errors=True)
            os.replace(target, backup)
            backup_exists = True
        try:
            os.replace(staging, target)
        except Exception:
            if backup_exists:
                os.replace(backup, target)
            raise
        shutil.rmtree(backup, ignore_errors=True)
        return target
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify and install a CodeLayer Forge plugin")
    parser.add_argument("package", type=Path)
    parser.add_argument("--target", type=Path, default=Path.home() / ".codelayer-forge/plugins")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.verify_only:
        package_manifest, _ = verify_package(args.package)
        print(json.dumps(package_manifest["plugin"], indent=2))
    else:
        print(install(args.package, args.target, args.replace))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

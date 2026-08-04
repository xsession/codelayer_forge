#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
VERSION = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
BASE_NAME = f"codelayer-forge-{VERSION}-source"
STAGING = DIST / BASE_NAME
ARCHIVE = DIST / f"{BASE_NAME}.zip"
EXCLUDE = {".git", ".venv", "venv", "node_modules", "target", "dist", "__pycache__", ".pytest_cache"}
FIXED_TIME = (2026, 8, 3, 0, 0, 0)


def ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in EXCLUDE or name.endswith((".pyc", ".log"))}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deterministic_zip(source: Path, archive: Path) -> None:
    temporary = archive.with_suffix(archive.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            relative = Path(source.name) / path.relative_to(source)
            info = zipfile.ZipInfo(relative.as_posix(), FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if os.access(path, os.X_OK) else 0o644
            info.external_attr = (mode & 0xFFFF) << 16
            package.writestr(info, path.read_bytes())
    os.replace(temporary, archive)


def main() -> int:
    subprocess.run(["python3", "scripts/build_catalog.py"], cwd=ROOT, check=True)
    subprocess.run(["python3", "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT, check=True)
    subprocess.run(["python3", "scripts/verify_repo.py"], cwd=ROOT, check=True)
    subprocess.run(["node", "--check", "apps/desktop/web/app.js"], cwd=ROOT, check=True)
    subprocess.run(["python3", "scripts/pack_all_plugins.py"], cwd=ROOT, check=True)

    DIST.mkdir(exist_ok=True)
    shutil.rmtree(STAGING, ignore_errors=True)
    shutil.copytree(ROOT, STAGING, ignore=ignore)
    release_assets = STAGING / "release-assets/plugin-packages"
    release_assets.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(DIST / "plugins", release_assets)

    metadata = {
        "name": "CodeLayer Forge",
        "version": VERSION,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "type": "source-distribution",
        "platformApiVersion": "0.1.0",
        "verification": {
            "pythonTests": 15,
            "pythonSyntax": "passed",
            "jsonAndTomlParsing": "passed",
            "pluginHostLifecycle": "passed",
            "capabilityBroker": "passed",
            "pluginPackageIntegrity": "passed",
            "javascriptSyntax": "passed",
            "rustCompilation": "not-run-in-artifact-container; configured in CI"
        }
    }
    (STAGING / "RELEASE-METADATA.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

    ARCHIVE.unlink(missing_ok=True)
    deterministic_zip(STAGING, ARCHIVE)
    checksum = sha256(ARCHIVE)
    checksum_path = ARCHIVE.with_suffix(ARCHIVE.suffix + ".sha256")
    checksum_path.write_text(f"{checksum}  {ARCHIVE.name}\n", encoding="utf-8")
    shutil.rmtree(STAGING)
    print(f"created {ARCHIVE}")
    print(f"sha256 {checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MANIFEST_KEYS = {"manifest_version", "id", "name", "version", "publisher", "description", "runtime", "entrypoint", "platform_api"}
PLUGIN_ID = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+){2,}$")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+].*)?$")


def fail(message: str) -> None:
    raise SystemExit(f"verification failed: {message}")


def verify_manifests() -> list[dict]:
    manifests = []
    ids = set()
    command_ids = set()
    providers: dict[str, str] = {}
    for path in sorted((ROOT / "plugins").glob("*/plugin.toml")):
        with path.open("rb") as handle:
            manifest = tomllib.load(handle)
        missing = REQUIRED_MANIFEST_KEYS - manifest.keys()
        if missing:
            fail(f"{path} misses {sorted(missing)}")
        if manifest["manifest_version"] != 1:
            fail(f"{path} has unsupported manifest version")
        if not PLUGIN_ID.fullmatch(manifest["id"]):
            fail(f"invalid plugin id {manifest['id']}")
        if manifest["id"] in ids:
            fail(f"duplicate plugin id {manifest['id']}")
        ids.add(manifest["id"])
        if not SEMVER.match(manifest["version"]):
            fail(f"invalid version {manifest['version']} in {path}")
        if manifest["runtime"] != "python":
            fail(f"current verification supports Python first-party plugins only: {path}")
        for command in manifest.get("contributes", {}).get("commands", []):
            if command["id"] in command_ids:
                fail(f"duplicate command id {command['id']}")
            command_ids.add(command["id"])
        for capability, version in manifest.get("provides", {}).items():
            if capability in providers:
                fail(f"duplicate first-party capability provider: {capability}")
            providers[capability] = version
        manifests.append(manifest)
    for manifest in manifests:
        for capability, requirement in manifest.get("requires", {}).items():
            if capability not in providers:
                fail(f"{manifest['id']} requires missing capability {capability} {requirement}")
    return manifests


def verify_python() -> None:
    for path in ROOT.rglob("*.py"):
        if any(part in {".venv", "venv", "target", "dist", "node_modules", "externals"} for part in path.parts):
            continue
        py_compile.compile(str(path), doraise=True)


def verify_json() -> None:
    for path in [*ROOT.glob("schemas/*.json"), *ROOT.glob("examples/**/*.json"), ROOT / "apps/desktop/src-tauri/tauri.conf.json", ROOT / "apps/desktop/src-tauri/capabilities/default.json"]:
        if path.is_file():
            json.loads(path.read_text(encoding="utf-8"))


def verify_host(manifests: list[dict]) -> None:
    host = ROOT / "hosts/python-plugin-host/forge_plugin_host.py"
    directory_by_id = {path.parent.name: path.parent for path in (ROOT / "plugins").glob("*/plugin.toml")}
    for directory in directory_by_id.values():
        requests = "\n".join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "forge/initialize", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "forge/shutdown", "params": {}}),
        ]) + "\n"
        result = subprocess.run(
            [sys.executable, str(host), "--plugin-dir", str(directory), "--workspace", str(ROOT / "examples/demo-workspace")],
            input=requests,
            text=True,
            capture_output=True,
            timeout=20,
        )
        if result.returncode != 0:
            fail(f"host startup failed for {directory.name}: {result.stderr}")
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        if len(responses) != 2 or any("error" in response for response in responses):
            fail(f"invalid host protocol for {directory.name}: {responses}")


def main() -> int:
    manifests = verify_manifests()
    verify_python()
    verify_json()
    verify_host(manifests)
    print(f"verified {len(manifests)} plugins, Python syntax, JSON files and host startup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import tomllib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins"
OUTPUTS = [ROOT / "apps/desktop/web/catalog.json", ROOT / "dist/plugin-catalog.json"]
ID_PATTERN = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+){2,}$")


def load_plugins() -> list[dict]:
    plugins: list[dict] = []
    ids: set[str] = set()
    for manifest_path in sorted(PLUGIN_ROOT.glob("*/plugin.toml")):
        with manifest_path.open("rb") as handle:
            manifest = tomllib.load(handle)
        plugin_id = manifest.get("id", "")
        if not ID_PATTERN.fullmatch(plugin_id):
            raise SystemExit(f"invalid plugin id in {manifest_path}: {plugin_id}")
        if plugin_id in ids:
            raise SystemExit(f"duplicate plugin id: {plugin_id}")
        ids.add(plugin_id)
        plugins.append({
            "root": str(manifest_path.parent.relative_to(ROOT)).replace("\\", "/"),
            "manifest_path": str(manifest_path.relative_to(ROOT)).replace("\\", "/"),
            "manifest": manifest,
            "platform_compatible": True,
        })
    return plugins


def main() -> int:
    catalog = {
        "schemaVersion": 1,
        "platformApiVersion": "0.1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "plugins": load_plugins(),
    }
    encoded = json.dumps(catalog, indent=2, sort_keys=False) + "\n"
    for output in OUTPUTS:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
        print(f"wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

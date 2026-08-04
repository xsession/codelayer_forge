#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_pack():
    path = ROOT / "scripts/pack_plugin.py"
    spec = importlib.util.spec_from_file_location("forge_pack_plugin", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.pack


def main() -> int:
    pack = load_pack()
    output = ROOT / "dist/plugins"
    for plugin in sorted((ROOT / "plugins").iterdir()):
        if (plugin / "plugin.toml").is_file():
            print(pack(plugin, output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

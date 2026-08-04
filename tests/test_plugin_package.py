from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pack_plugin = load_module("pack_plugin", ROOT / "scripts/pack_plugin.py")
install_plugin = load_module("install_plugin", ROOT / "scripts/install_plugin.py")


class PluginPackageTests(unittest.TestCase):
    def test_pack_verify_and_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            archive = pack_plugin.pack(ROOT / "plugins/route-core", temporary / "packages")
            metadata, payload = install_plugin.verify_package(archive)
            self.assertEqual(metadata["plugin"]["id"], "hu.codelayer.route-core")
            self.assertIn("plugin.toml", payload)
            installed = install_plugin.install(archive, temporary / "installed")
            self.assertTrue((installed / "plugin.toml").is_file())
            self.assertTrue((installed / ".installed.json").is_file())

    def test_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "unsafe.cforge-plugin"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("../escape", b"bad")
                package.writestr("PACKAGE-MANIFEST.json", b'{"packageFormat":1,"files":{}}')
            with self.assertRaises(ValueError):
                install_plugin.verify_package(archive)


if __name__ == "__main__":
    unittest.main()

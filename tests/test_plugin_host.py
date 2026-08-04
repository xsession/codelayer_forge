from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "hosts/python-plugin-host/forge_plugin_host.py"


class PluginHostTests(unittest.TestCase):
    def test_initialize_and_shutdown_all_plugins(self) -> None:
        for plugin_dir in sorted((ROOT / "plugins").iterdir()):
            if not (plugin_dir / "plugin.toml").is_file():
                continue
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "forge/initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "forge/shutdown", "params": {}},
            ]
            completed = subprocess.run(
                [sys.executable, str(HOST), "--plugin-dir", str(plugin_dir), "--workspace", str(ROOT / "examples/demo-workspace")],
                input="".join(json.dumps(item) + "\n" for item in requests),
                text=True,
                capture_output=True,
                timeout=20,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            responses = [json.loads(line) for line in completed.stdout.splitlines()]
            self.assertEqual(len(responses), 2)
            self.assertIn("plugin", responses[0]["result"])
            self.assertTrue(responses[1]["result"]["shutdown"])

    def test_unknown_method_returns_json_rpc_error(self) -> None:
        request = {"jsonrpc": "2.0", "id": 7, "method": "missing/method", "params": {}}
        completed = subprocess.run(
            [sys.executable, str(HOST), "--plugin-dir", str(ROOT / "plugins/route-core")],
            input=json.dumps(request) + "\n",
            text=True,
            capture_output=True,
            timeout=20,
        )
        response = json.loads(completed.stdout)
        self.assertEqual(response["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()

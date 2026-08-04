from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROKER = ROOT / "hosts/plugin-broker/forge_broker.py"


class BrokerTests(unittest.TestCase):
    def test_capability_dispatch_and_lazy_processes(self) -> None:
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "forge/initialize", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "forge/callCapability",
                "params": {
                    "capability": "codelayer.routing.orthogonal",
                    "method": "route",
                    "params": {
                        "source": {"x": 0, "y": 0},
                        "target": {"x": 100, "y": 0},
                        "obstacles": [{"x": 40, "y": -10, "width": 20, "height": 20}],
                        "grid": 10,
                    },
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "forge/callCapability",
                "params": {
                    "capability": "codelayer.hdl.graph",
                    "method": "summarize",
                    "params": {"name": "demo", "nodes": [], "nets": [], "topPorts": []},
                },
            },
            {"jsonrpc": "2.0", "id": 4, "method": "forge/listProcesses", "params": {}},
            {"jsonrpc": "2.0", "id": 5, "method": "forge/shutdown", "params": {}},
        ]
        completed = subprocess.run(
            [
                sys.executable,
                str(BROKER),
                "--plugins-root",
                str(ROOT / "plugins"),
                "--workspace",
                str(ROOT / "examples/demo-workspace"),
            ],
            input="".join(json.dumps(item) + "\n" for item in requests),
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        responses = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual(len(responses), 5, completed.stdout)
        self.assertIn("codelayer.routing.orthogonal", responses[0]["result"]["capabilities"])
        self.assertTrue(responses[1]["result"]["result"]["routed"])
        self.assertEqual(responses[2]["result"]["result"]["name"], "demo")
        self.assertEqual(len(responses[3]["result"]), 2)
        self.assertTrue(responses[4]["result"]["shutdown"])


if __name__ == "__main__":
    unittest.main()

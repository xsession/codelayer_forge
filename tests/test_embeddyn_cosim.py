"""embeddyn co-simulation plugin: JSON-RPC through the Python plugin host, and pin plan -> Renode bindings."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "hosts/python-plugin-host/forge_plugin_host.py"
PLUGIN = ROOT / "plugins/embeddyn-cosim"
WORKSPACE = ROOT / "examples/demo-workspace"
ENGINE = ROOT / "engines/embeddyn"

try:
    import yaml  # noqa: F401  (the engine needs PyYAML)
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


def session(*calls: tuple[str, dict]) -> list[dict]:
    requests = [{"jsonrpc": "2.0", "id": 1, "method": "forge/initialize", "params": {}}]
    requests += [{"jsonrpc": "2.0", "id": i + 2, "method": method, "params": params} for i, (method, params) in enumerate(calls)]
    requests.append({"jsonrpc": "2.0", "id": len(requests) + 1, "method": "forge/shutdown", "params": {}})
    completed = subprocess.run(
        [sys.executable, str(HOST), "--plugin-dir", str(PLUGIN), "--workspace", str(WORKSPACE)],
        input="".join(json.dumps(item) + "\n" for item in requests), text=True, capture_output=True, timeout=120)
    if completed.returncode != 0:
        raise AssertionError(completed.stderr)
    return [json.loads(line) for line in completed.stdout.splitlines()]


@unittest.skipUnless(HAVE_YAML, "PyYAML is required by the embeddyn engine")
class EmbeddynPluginTests(unittest.TestCase):
    def test_capabilities_and_run_through_the_host(self) -> None:
        responses = session(
            ("forge/listCapabilities", {}),
            ("forge/callService", {"service": "codelayer.simulation.cosim", "method": "validate",
                                   "params": {"path": "simulation/rc-servo-lab.cosim.yaml"}}),
            ("forge/callService", {"service": "codelayer.simulation.cosim", "method": "run",
                                   "params": {"path": "simulation/rc-servo-lab.cosim.yaml", "duration": 0.5}}),
        )
        self.assertFalse([r for r in responses if "error" in r], responses)
        capabilities = json.dumps(responses[1]["result"])
        for name in ("codelayer.simulation.cosim", "codelayer.simulation.analysis", "codelayer.simulation.renode-bindings"):
            self.assertIn(name, capabilities)
        self.assertTrue(responses[2]["result"]["valid"])
        run = responses[3]["result"]
        self.assertEqual(run["rows"], 501)
        self.assertAlmostEqual(run["final"]["servo.angle_deg"], 45.0, delta=1.5)
        self.assertIn("current.rms", run["metrics"])

    def test_workspace_boundary_is_enforced(self) -> None:
        responses = session(("forge/callService", {"service": "codelayer.simulation.cosim", "method": "run",
                                                   "params": {"path": "../../engines/embeddyn/examples/mechatronics/dc-motor.yaml"}}))
        self.assertIn("error", responses[1])

    def test_pin_plan_regenerates_the_rc_servo_bindings(self) -> None:
        responses = session(("forge/callService", {
            "service": "codelayer.simulation.renode-bindings", "method": "from_pin_plan",
            "params": {"plan": "pin-plans/rc-servo.pinplan.json", "device": "devices/stm32l476-servo.json"}}))
        result = responses[1]["result"]
        generated = {b["signal"]: b["endpoint"] for b in result["bindings"]}
        import yaml
        reference = yaml.safe_load((ENGINE / "examples/mechatronics/bindings/renode-rc-servo.yaml").read_text())
        expected = {b["signal"]: b["endpoint"] for b in reference["bindings"] if b["endpoint"].get("property") != "sysbus"}
        self.assertEqual(set(generated), set(expected))
        def normal(endpoint: dict) -> dict:     # PyYAML reads `1.0e6` as a string; the adapter float()s it
            result = {}
            for key, value in endpoint.items():
                try:
                    result[key] = value if isinstance(value, bool) else float(value)
                except (TypeError, ValueError):
                    result[key] = value
            return result

        for signal, endpoint in expected.items():
            self.assertEqual(normal(generated[signal]), normal(endpoint), signal)
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["bus-not-bindable"])
        self.assertTrue(result["valid"])

    def test_pin_plan_is_solvable_by_the_pin_configurator(self) -> None:
        sys.path.insert(0, str(ROOT / "sdk/python"))
        sys.path.insert(0, str(ROOT / "plugins/pin-configurator/src"))
        from pin_configurator import solver
        device = json.loads((WORKSPACE / "devices/stm32l476-servo.json").read_text())
        plan = json.loads((WORKSPACE / "pin-plans/rc-servo.pinplan.json").read_text())
        solved = solver.solve({"pins": device["pins"], "signals": plan["signals"]})
        self.assertEqual(solved["assignments"]["servo_pulse"], "PA0")
        self.assertEqual(solved["assignments"]["command_pot"], "PC0")


if __name__ == "__main__":
    unittest.main()

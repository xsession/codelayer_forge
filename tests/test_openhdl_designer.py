from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sdk/python"))
sys.path.insert(0, str(ROOT / "plugins/openhdl-designer/src"))

from openhdl_designer.graph import generate_verilog, validate_graph  # noqa: E402


def valid_graph() -> dict:
    return {
        "name": "demo_top",
        "topPorts": [
            {"name": "clk", "direction": "input"},
            {"name": "enable", "direction": "input"},
            {"name": "pwm", "direction": "output"},
        ],
        "nodes": [{
            "id": "controller",
            "module": "pwm_controller",
            "sequential": True,
            "ports": {"inputs": ["clk", "enable"], "outputs": ["pwm_out"]},
        }],
        "nets": [
            {"from": "top.clk", "to": "controller.clk"},
            {"from": "top.enable", "to": "controller.enable"},
            {"from": "controller.pwm_out", "to": "top.pwm"},
        ],
    }


class OpenHdlDesignerTests(unittest.TestCase):
    def test_valid_graph_generates_verilog(self) -> None:
        result = generate_verilog(valid_graph())
        self.assertIn("module demo_top", result["content"])
        self.assertIn("pwm_controller controller", result["content"])
        self.assertIn("assign pwm = w_controller_pwm_out", result["content"])

    def test_detects_multiple_drivers(self) -> None:
        graph = valid_graph()
        graph["nets"].append({"from": "top.enable", "to": "top.pwm"})
        result = validate_graph(graph)
        self.assertFalse(result["valid"])
        self.assertIn("HDL_MULTIPLE_DRIVERS", {item["code"] for item in result["diagnostics"]})

    def test_detects_combinational_cycle(self) -> None:
        graph = {
            "name": "cycle",
            "nodes": [
                {"id": "a", "module": "gate", "ports": {"inputs": ["i"], "outputs": ["o"]}},
                {"id": "b", "module": "gate", "ports": {"inputs": ["i"], "outputs": ["o"]}},
            ],
            "nets": [
                {"from": "a.o", "to": "b.i"},
                {"from": "b.o", "to": "a.i"},
            ],
        }
        result = validate_graph(graph)
        self.assertIn("HDL_COMBINATIONAL_CYCLE", {item["code"] for item in result["diagnostics"]})


if __name__ == "__main__":
    unittest.main()

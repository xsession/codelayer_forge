from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sdk/python"))
sys.path.insert(0, str(ROOT / "plugins/pin-configurator/src"))

from pin_configurator.solver import generate, solve, validate  # noqa: E402


class PinConfiguratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "pins": [
                {"name": "A1", "capabilities": ["GPIO", "UART_TX"]},
                {"name": "A2", "capabilities": ["GPIO", "UART_RX"]},
                {"name": "B1", "capabilities": ["GPIO", "PWM"]},
                {"name": "VCC", "capabilities": ["POWER"], "reserved": True},
            ],
            "signals": [
                {"id": "tx", "requires": ["UART_TX"]},
                {"id": "rx", "requires": ["UART_RX"]},
                {"id": "led", "requires": ["GPIO"], "preferred": ["B1"]},
            ],
        }

    def test_solver_finds_complete_assignment(self) -> None:
        result = solve(self.payload)
        self.assertTrue(result["solved"])
        self.assertEqual(result["assignments"], {"led": "B1", "rx": "A2", "tx": "A1"})

    def test_validation_rejects_duplicate_pin(self) -> None:
        result = validate({**self.payload, "assignments": {"tx": "A1", "led": "A1", "rx": "A2"}})
        self.assertFalse(result["valid"])
        self.assertIn("PIN_DUPLICATE_ASSIGNMENT", {item["code"] for item in result["diagnostics"]})

    def test_xdc_generation_is_deterministic(self) -> None:
        result = generate({"format": "xdc", "assignments": {"tx": "A1", "rx": "A2"}})
        self.assertIn("PACKAGE_PIN A2", result["content"])
        self.assertTrue(result["content"].endswith("\n"))


if __name__ == "__main__":
    unittest.main()

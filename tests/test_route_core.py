from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sdk/python"))
sys.path.insert(0, str(ROOT / "plugins/route-core/src"))

from route_core.router import route, validate_route  # noqa: E402


class RouteCoreTests(unittest.TestCase):
    def test_routes_around_obstacle(self) -> None:
        result = route({
            "source": {"x": 0, "y": 0},
            "target": {"x": 100, "y": 0},
            "obstacles": [{"x": 30, "y": -20, "width": 40, "height": 40}],
            "grid": 10,
            "clearance": 0,
            "bendPenalty": 20,
        })
        self.assertTrue(result["routed"])
        self.assertTrue(result["validation"]["valid"])
        self.assertGreaterEqual(result["bends"], 2)
        self.assertGreater(result["length"], 100)

    def test_diagonal_segment_is_invalid(self) -> None:
        result = validate_route({"points": [{"x": 0, "y": 0}, {"x": 10, "y": 10}]})
        self.assertFalse(result["valid"])
        self.assertEqual(result["diagnostics"][0]["code"], "ROUTE_NOT_ORTHOGONAL")


if __name__ == "__main__":
    unittest.main()

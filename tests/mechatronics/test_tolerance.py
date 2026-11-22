import math
import random
from pathlib import Path

import pytest
import yaml

from embeddyn.mechatronics.tolerance import (
    Distribution,
    analyse,
    load_tolerance_spec,
    parse_distribution,
    sobol_indices,
    unit_samples,
    wilson,
)

ROOT = Path(__file__).resolve().parents[2]
DC_MOTOR = ROOT / "examples/mechatronics/dc-motor.yaml"


def test_distributions():
    normal = parse_distribution("r", {"nominal": 2.0, "tolerance": 0.06, "distribution": "normal"})
    assert normal.quantile(0.5) == pytest.approx(2.0) and normal.b == pytest.approx(0.04)   # 3 sigma = 6 %
    uniform = parse_distribution("r", {"nominal": 10.0, "tolerance": 0.1, "distribution": "uniform"})
    assert (uniform.quantile(0.0), uniform.quantile(1.0)) == pytest.approx((9.0, 11.0), abs=1e-9)
    tri = parse_distribution("f", {"distribution": "triangular", "minimum": 0.0, "mode": 1.0, "maximum": 4.0})
    assert tri.quantile(0.25) == pytest.approx(1.0)                  # CDF(mode) = (mode-lo)/(hi-lo)
    lognormal = Distribution("lognormal", 2.0, 0.1)
    assert lognormal.quantile(0.5) == pytest.approx(2.0)
    assert Distribution("choice", values=(1.0, 2.0)).quantile(0.75) == 2.0
    for bad, message in [({"distribution": "triangular", "minimum": 0, "mode": 5, "maximum": 4}, "mode"),
                         ({"distribution": "uniform", "minimum": 1}, "needs 'maximum'"),
                         ({"distribution": "weibull"}, "unsupported")]:
        with pytest.raises(ValueError, match=message):
            parse_distribution("x", bad)


def test_latin_hypercube_stratifies_each_dimension():
    rows = unit_samples(50, 3, random.Random(1), "lhs")
    for d in range(3):
        assert sorted(int(row[d] * 50) for row in rows) == list(range(50))


def test_wilson_interval():
    low, high = wilson(95, 100)
    assert low == pytest.approx(0.8882, abs=1e-3) and high == pytest.approx(0.9785, abs=1e-3)
    assert wilson(0, 0) == (0.0, 1.0)


def _sobol(function, k, n=6000, seed=3):
    rng = random.Random(seed)
    a, b = unit_samples(n, k, rng), unit_samples(n, k, rng)
    fa, fb = [function(x) for x in a], [function(x) for x in b]
    fab = [[function([b[j][c] if c == i else a[j][c] for c in range(k)]) for j in range(n)] for i in range(k)]
    return sobol_indices(fa, fb, fab)


def test_sobol_linear_model():
    first, total = _sobol(lambda x: x[0] + 2 * x[1], 2)           # variances 1/12 and 4/12
    assert first == pytest.approx([0.2, 0.8], abs=0.04)
    assert total == pytest.approx([0.2, 0.8], abs=0.04)


def test_sobol_ishigami_benchmark():
    def ishigami(u, a=7.0, b=0.1):
        x = [math.pi * (2 * v - 1) for v in u]
        return math.sin(x[0]) + a * math.sin(x[1]) ** 2 + b * x[2] ** 4 * math.sin(x[0])
    first, total = _sobol(ishigami, 3, n=10000)
    assert first == pytest.approx([0.314, 0.442, 0.0], abs=0.05)
    assert total == pytest.approx([0.558, 0.442, 0.244], abs=0.05)


def _spec(tmp_path, **extra) -> Path:
    spec = {"project": str(DC_MOTOR), "mock": True, "duration": 0.15, "seed": 2,
            "parameters": {"electrical.motor_resistance": {"nominal": 2.0, "tolerance": 0.1, "distribution": "uniform"},
                           "mechanical.inertia": {"nominal": 0.02, "tolerance": 0.2, "distribution": "uniform"}},
            "outputs": ["speed.final_value"],
            "limits": [{"metric": "current.peak", "max": 12.5}], **extra}
    path = tmp_path / "tol.yaml"
    path.write_text(yaml.safe_dump(spec))
    return path


def test_monte_carlo_yield_and_parallel_equivalence(tmp_path):
    spec = load_tolerance_spec(_spec(tmp_path, monte_carlo={"samples": 12, "sampling": "lhs"}))
    assert spec.outputs == ["speed.final_value", "current.peak"]          # limits add their metrics
    serial = analyse(spec)["monte_carlo"]
    assert serial["samples"] == 12 and serial["errors"] == 0
    peaks = [s["metrics"]["current.peak"] for s in serial["sample_set"]]
    assert serial["yield"] == pytest.approx(sum(p <= 12.5 for p in peaks) / 12)
    # current peak = V / R: a lower resistance raises it, so some samples fail the limit
    assert 0 < serial["yield"] < 1
    resistances = [s["parameters"]["electrical.motor_resistance"] for s in serial["sample_set"]]
    mr, mp = sum(resistances) / 12, sum(peaks) / 12
    correlation = sum((r - mr) * (p - mp) for r, p in zip(resistances, peaks)) / math.sqrt(
        sum((r - mr) ** 2 for r in resistances) * sum((p - mp) ** 2 for p in peaks))
    assert correlation < -0.9
    spec.workers = 2
    parallel = analyse(spec)["monte_carlo"]
    assert [s["metrics"] for s in parallel["sample_set"]] == [s["metrics"] for s in serial["sample_set"]]


def test_sensitivity_ranks_the_dominant_tolerance(tmp_path):
    spec = load_tolerance_spec(_spec(tmp_path, sensitivity={"base_samples": 16, "bootstrap": 50}))
    result = analyse(spec)["sensitivity"]
    assert result["runs"] == 16 * (2 + 2)
    peak = result["outputs"]["current.peak"]
    # The current peak depends on R only (the inertia acts later): R explains almost all variance.
    assert peak["ranking"][0] == "electrical.motor_resistance"
    assert peak["indices"]["electrical.motor_resistance"]["total"] > 0.9


def test_spec_requires_analysis(tmp_path):
    with pytest.raises(ValueError, match="monte_carlo"):
        load_tolerance_spec(_spec(tmp_path))

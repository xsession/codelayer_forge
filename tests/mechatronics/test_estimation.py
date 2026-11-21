import csv
import importlib.util
from pathlib import Path

import pytest
import yaml

from embeddyn.mechatronics.adapters.replay import ReplayAdapter, sample
from embeddyn.mechatronics.estimation import (
    _inverse,
    build_project,
    estimate,
    load_estimation_spec,
)

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "examples/mechatronics/estimation/dc-motor.yaml"
GENERATOR = ROOT / "examples/mechatronics/estimation/make_bench_data.py"


def _write(path: Path, rows, header):
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def test_replay_sampling_and_validation(tmp_path):
    times, values = [0.0, 1.0, 2.0], [0.0, 10.0, 20.0]
    assert sample(times, values, 0.5, "linear") == 5.0
    assert sample(times, values, 0.5, "previous") == 0.0
    assert sample(times, values, 9.0) == 20.0
    path = _write(tmp_path / "r.csv", [[0.0, 1.0], [0.001, 2.0], [0.002, 3.0]], ["time", "duty"])
    adapter = ReplayAdapter(str(path), {"duty": "x"})
    adapter.start({})
    # sample-and-hold: the step ending at 2 ms uses the value from its start (1 ms)
    assert adapter.step(0.002, 0.001, {}).outputs == {"x": 2.0}
    with pytest.raises(ValueError, match="no columns"):
        ReplayAdapter(str(path), {"nope": "x"})
    bad = _write(tmp_path / "bad.csv", [[0.0, 1.0], [0.0, 2.0]], ["time", "duty"])
    with pytest.raises(ValueError, match="strictly increasing"):
        ReplayAdapter(str(bad), {"duty": "x"})


def test_inverse():
    inv = _inverse([[4.0, 7.0], [2.0, 6.0]])
    assert [x for row in inv for x in row] == pytest.approx([0.6, -0.7, -0.2, 0.4])


def test_spec_validation(tmp_path):
    raw = yaml.safe_load(SPEC.read_text())
    raw["project"] = str((SPEC.parent / raw["project"]).resolve())
    raw["parameters"]["mechanical.inertia"] = {"min": 0.0, "max": 1.0, "scale": "log"}
    path = tmp_path / "s.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="min > 0"):
        load_estimation_spec(path)
    spec = load_estimation_spec(SPEC)
    spec.disable = ["nope"]
    with pytest.raises(ValueError, match="unknown simulator instance"):
        build_project(spec, {}, 0.1)


def test_open_loop_project_replays_duty_and_sets_values():
    spec = load_estimation_spec(SPEC)
    project = build_project(spec, {"electrical.motor_resistance": 3.0}, 0.05)
    instances = project.simulator_instances()
    assert not instances["firmware"].enabled and instances["estimation_replay"].options["backend"] == "replay"
    assert project.signals["electrical.motor_resistance"].initial == 3.0


@pytest.fixture(scope="module")
def bench(tmp_path_factory):
    module_spec = importlib.util.spec_from_file_location("make_bench_data", GENERATOR)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    path = tmp_path_factory.mktemp("bench") / "bench.csv"
    module.main(path)
    return module, path


def test_estimation_recovers_true_parameters_within_ci(bench, tmp_path):
    module, data = bench
    raw = yaml.safe_load(SPEC.read_text())
    raw["project"] = str((SPEC.parent / raw["project"]).resolve())
    raw["measurements"] = str(data)
    keep = ["electrical.motor_resistance", "mechanical.inertia", "mechanical.load_torque"]
    raw["parameters"] = {name: raw["parameters"][name] for name in keep}
    raw["max_iterations"] = 8
    # The parameters not being estimated are known: hold them at their true values.
    raw["fixed"] = {k: v for k, v in module.TRUE.items() if k not in keep}
    path = tmp_path / "spec.yaml"
    path.write_text(yaml.safe_dump(raw))
    result = estimate(load_estimation_spec(path))
    for name in keep:
        item = result["parameters"][name]
        lo, hi = item["ci95"]
        assert lo <= module.TRUE[name] <= hi, (name, item)
        assert not item["at_bound"]
    assert 0.7 < result["cost"]["reduced_chi_square"] < 1.3
    assert result["fit"]["electrical.motor_current"]["rmse"] == pytest.approx(module.NOISE["current"], rel=0.2)
    assert result["cost"]["final"] < result["cost"]["initial"] / 100


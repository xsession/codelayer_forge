"""Write a synthetic open-loop bench recording for dc-motor.yaml.

The DC motor model runs with known "true" parameters (deliberately different
from the project's nominal values), driven by a duty-cycle profile; current and
speed get Gaussian noise. Re-running gives identical data (fixed seed).

Usage: python make_bench_data.py [output.csv]
"""
import csv
import random
import sys
from pathlib import Path

from embeddyn.mechatronics.estimation import build_project, load_estimation_spec
from embeddyn.mechatronics.factory import build_adapters
from embeddyn.mechatronics.orchestrator import CoSimulationOrchestrator

HERE = Path(__file__).resolve().parent
TRUE = {
    "electrical.motor_resistance": 2.4,
    "electrical.motor_inductance": 0.0045,
    "mechanical.inertia": 0.025,
    "mechanical.damping": 0.06,
    "mechanical.load_torque": 0.05,
}
NOISE = {"current": 0.05, "speed": 0.02}
PROFILE = [(0.0, 0.0), (0.02, 0.4), (0.15, 0.9), (0.30, 0.2), (0.45, -0.3)]   # (from time, duty)
DURATION, SAMPLE = 0.6, 0.001


def duty_at(t: float) -> float:
    return [duty for start, duty in PROFILE if t >= start - 1e-12][-1]


def main(output: Path) -> None:
    times = [round(i * SAMPLE, 9) for i in range(int(round(DURATION / SAMPLE)) + 1)]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:               # input-only file for the replay
        writer = csv.writer(handle)
        writer.writerow(["time", "duty"])
        writer.writerows([t, duty_at(t)] for t in times)
    spec = load_estimation_spec(HERE / "dc-motor.yaml")
    spec.measurements = output
    project = build_project(spec, TRUE, DURATION)
    rows = CoSimulationOrchestrator(project, build_adapters(project)).run()
    by_time = {round(float(row["time"]), 9): row for row in rows}
    rng = random.Random(20261121)
    with output.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time", "duty", "current", "speed"])
        for t in times:
            row = by_time[t]
            writer.writerow([t, duty_at(t),
                             round(row["electrical.motor_current"] + rng.gauss(0, NOISE["current"]), 6),
                             round(row["mechanical.velocity"] + rng.gauss(0, NOISE["speed"]), 6)])
    print(output)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "bench" / "dc-motor-step-test.csv")

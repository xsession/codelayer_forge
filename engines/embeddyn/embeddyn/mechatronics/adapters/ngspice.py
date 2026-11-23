from __future__ import annotations

import csv
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Mapping

from .base import SimulatorAdapter, StepResult


class NgspiceAdapter(SimulatorAdapter):
    """Portable SPICE adapter used as the open-source/default electrical backend."""

    name = "ngspice"

    def __init__(self, netlist: Path, executable: str | None = None, output_csv: str = "cosim.csv",
                 timeout: float = 30.0) -> None:
        self.netlist = netlist
        self.executable = executable or shutil.which("ngspice") or "ngspice"
        self.output_csv = output_csv
        self.timeout = timeout
        self.workdir: Path | None = None

    def start(self, initial_signals: Mapping[str, float]) -> None:
        self.workdir = Path(tempfile.mkdtemp(prefix="embeddyn-ngspice-"))

    def step(self, time_seconds: float, step_seconds: float, inputs: Mapping[str, float]) -> StepResult:
        if self.workdir is None:
            raise RuntimeError("ngspice adapter is not started")
        text = self.netlist.read_text(encoding="utf-8")
        for key, value in {"time": time_seconds, "dt": step_seconds, **inputs}.items():
            text = text.replace("{{" + key + "}}", format(float(value), ".17g"))
        generated = self.workdir / self.netlist.name
        generated.write_text(text, encoding="utf-8")
        log = self.workdir / "ngspice.log"
        subprocess.run([self.executable, "-b", "-o", str(log), str(generated)], cwd=self.workdir,
                       check=True, timeout=self.timeout, capture_output=True, text=True)
        csv_path = self.workdir / self.output_csv
        if not csv_path.exists():
            return StepResult({}, {"log": str(log), "warning": "no co-simulation CSV was generated"})
        with csv_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        return StepResult({k: float(v) for k, v in rows[-1].items() if k and v} if rows else {})

    def capabilities(self) -> dict[str, bool]:
        return {"deterministic_step": True, "variable_step": True, "checkpoint": False, "real_time": False, "events": False, "electrical_transient": True}

    def stop(self) -> None:
        pass

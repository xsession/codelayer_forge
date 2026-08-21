from __future__ import annotations

import csv
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Mapping

from .base import SimulatorAdapter, StepResult


class LTspiceAdapter(SimulatorAdapter):
    """File-exchange adapter for LTspice batch simulation.

    It renders a netlist template on every macro step, executes LTspice in batch
    mode and reads a CSV exported by a `.meas`/waveform post-processing script.
    For high-rate runs, use ngspice shared-library or the persistent process
    bridge; LTspice is best suited to validation checkpoints and detailed runs.
    """

    name = "ltspice"

    def __init__(self, netlist: Path, executable: str | None = None, output_csv: str = "cosim.csv",
                 timeout: float = 60.0) -> None:
        self.netlist = netlist
        self.executable = executable or shutil.which("ltspice") or shutil.which("XVIIx64.exe") or "ltspice"
        self.output_csv = output_csv
        self.timeout = timeout
        self.workdir: Path | None = None

    def start(self, initial_signals: Mapping[str, float]) -> None:
        self.workdir = Path(tempfile.mkdtemp(prefix="embeddyn-ltspice-"))

    def step(self, time_seconds: float, step_seconds: float, inputs: Mapping[str, float]) -> StepResult:
        if self.workdir is None:
            raise RuntimeError("LTspice adapter is not started")
        text = self.netlist.read_text(encoding="utf-8")
        values = {"time": time_seconds, "dt": step_seconds, **inputs}
        for key, value in values.items():
            text = text.replace("{{" + key + "}}", format(float(value), ".17g"))
        generated = self.workdir / self.netlist.name
        generated.write_text(text, encoding="utf-8")
        subprocess.run([self.executable, "-b", str(generated)], cwd=self.workdir, check=True,
                       timeout=self.timeout, capture_output=True, text=True)
        csv_path = self.workdir / self.output_csv
        if not csv_path.exists():
            return StepResult({}, {"warning": f"LTspice did not create {csv_path}"})
        with csv_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            return StepResult({})
        return StepResult({k: float(v) for k, v in rows[-1].items() if k and v not in (None, "")})

    def capabilities(self) -> dict[str, bool]:
        return {"deterministic_step": True, "variable_step": True, "checkpoint": False, "real_time": False, "events": False, "vendor_models": True}

    def stop(self) -> None:
        pass

    def health(self) -> dict[str, object]:
        return {
            "name": self.name,
            "executable": shutil.which(self.executable) or self.executable,
            "netlist": str(self.netlist),
            "netlist_exists": self.netlist.exists(),
        }

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .analysis import RFAnalysisError


@dataclass(frozen=True)
class OpenEMSBuildResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    prefix: Path


@dataclass(frozen=True)
class OpenEMSRunResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def run_openems_xml(
    model: Path,
    *,
    executable: str | None = None,
    extra_args: Sequence[str] = (),
    timeout_seconds: float = 3600.0,
    workdir: Path | None = None,
) -> OpenEMSRunResult:
    """Run a pre-generated openEMS XML model without invoking arbitrary scripts.

    Geometry generation/post-processing is intentionally separate. This runner
    accepts only an XML solver input and executes the native openEMS engine.
    """
    model = Path(model).resolve()
    if model.suffix.lower() != ".xml":
        raise RFAnalysisError("openEMS solver input must be an XML file")
    if not model.is_file():
        raise RFAnalysisError(f"openEMS model not found: {model}")
    if not timeout_seconds or timeout_seconds <= 0:
        raise RFAnalysisError("openEMS timeout must be positive")
    binary = executable or shutil.which("openEMS") or shutil.which("openems")
    if not binary:
        raise RFAnalysisError("openEMS executable was not found on PATH")
    command = (str(binary), str(model), *(str(arg) for arg in extra_args))
    try:
        proc = subprocess.run(
            command,
            cwd=str(Path(workdir).resolve()) if workdir else str(model.parent),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RFAnalysisError(f"openEMS exceeded the {timeout_seconds:g} second timeout") from error
    return OpenEMSRunResult(command, proc.returncode, proc.stdout, proc.stderr)


def build_openems_project(
    source: Path,
    prefix: Path,
    *,
    python_bindings: bool = True,
    gui: bool = False,
    jobs: int | None = None,
    timeout_seconds: float = 7200.0,
) -> OpenEMSBuildResult:
    """Build a checked-out openEMS-Project using its upstream build driver.

    This is a CLI/local operation only. It deliberately does not expose build
    script execution through Local Studio's web API.
    """
    source = Path(source).resolve()
    prefix = Path(prefix).resolve()
    driver = source / "update_openEMS.sh"
    if not driver.is_file():
        raise RFAnalysisError(f"openEMS-Project build driver not found: {driver}")
    if jobs is not None and jobs < 1:
        raise RFAnalysisError("openEMS build jobs must be at least 1")
    if not timeout_seconds or timeout_seconds <= 0:
        raise RFAnalysisError("openEMS build timeout must be positive")
    bash = shutil.which("bash")
    if not bash:
        raise RFAnalysisError("bash is required to run openEMS-Project/update_openEMS.sh")
    prefix.mkdir(parents=True, exist_ok=True)
    args = [bash, str(driver), str(prefix)]
    if python_bindings:
        args.append("--python")
    if not gui:
        args.append("--disable-GUI")
    if jobs is not None:
        args.append(f"--njobs={jobs}")
    try:
        proc = subprocess.run(
            args,
            cwd=str(source),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RFAnalysisError(f"openEMS build exceeded the {timeout_seconds:g} second timeout") from error
    return OpenEMSBuildResult(tuple(args), proc.returncode, proc.stdout, proc.stderr, prefix)

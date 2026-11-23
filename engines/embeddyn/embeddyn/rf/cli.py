from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .analysis import (
    RFAnalysisError,
    analyze_touchstone,
    analyze_waveform_noise,
    load_waveform_csv,
    solver_capabilities,
)
from .openems import build_openems_project, run_openems_xml
from .models import RectangularPatchSpec, rectangular_patch_seed, render_openems_patch_script, resolved_patch_geometry


rf_app = typer.Typer(name="rf", help="RF, antenna tuning and EMC pre-compliance analysis.")


@rf_app.command("status")
def status() -> None:
    """Show available RF/network/full-wave backends."""
    typer.echo(json.dumps(solver_capabilities(), indent=2))


@rf_app.command("touchstone")
def touchstone(
    path: Path = typer.Argument(..., exists=True, dir_okay=False),
    target_hz: Optional[float] = typer.Option(None, "--target-hz", help="Target antenna frequency in Hz."),
    return_loss_db: float = typer.Option(10.0, "--return-loss-db", min=0.1),
    z0: Optional[float] = typer.Option(None, "--z0", min=0.001, help="Override reference impedance."),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
) -> None:
    """Analyze Touchstone data for S11, VSWR, impedance and antenna tuning hints."""
    try:
        report = analyze_touchstone(
            path,
            target_frequency_hz=target_hz,
            return_loss_threshold_db=return_loss_db,
            reference_impedance_ohms=z0,
        )
    except RFAnalysisError as error:
        raise typer.BadParameter(str(error)) from error
    text = json.dumps(report, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
        typer.echo(str(output))
    else:
        typer.echo(text)


@rf_app.command("noise")
def noise(
    path: Path = typer.Argument(..., exists=True, dir_okay=False),
    sample_rate_hz: Optional[float] = typer.Option(None, "--sample-rate-hz", min=0.001),
    time_column: Optional[str] = typer.Option(None, "--time-column"),
    value_column: Optional[str] = typer.Option(None, "--value-column"),
    value_unit: str = typer.Option("V", "--value-unit"),
    impedance_ohms: float = typer.Option(50.0, "--impedance-ohms", min=0.001),
    max_fft_points: int = typer.Option(16384, "--max-fft-points", min=8),
    top_peaks: int = typer.Option(20, "--top-peaks", min=1, max=1000),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
) -> None:
    """FFT a simulated/measured waveform and report RF/EMI spectral peaks."""
    try:
        waveform = load_waveform_csv(
            path,
            time_column=time_column,
            value_column=value_column,
            sample_rate_hz=sample_rate_hz,
            value_unit=value_unit,
        )
        report = analyze_waveform_noise(
            waveform,
            impedance_ohms=impedance_ohms,
            max_fft_points=max_fft_points,
            top_peaks=top_peaks,
        )
    except RFAnalysisError as error:
        raise typer.BadParameter(str(error)) from error
    text = json.dumps(report, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
        typer.echo(str(output))
    else:
        typer.echo(text)


@rf_app.command("patch-seed")
def patch_seed(
    target_hz: float = typer.Option(..., "--target-hz", min=1.0),
    epsilon_r: float = typer.Option(..., "--epsilon-r", min=1.000001),
    substrate_mm: float = typer.Option(..., "--substrate-mm", min=0.001),
) -> None:
    """Calculate a rectangular microstrip patch starting geometry."""
    try:
        report = rectangular_patch_seed(target_hz, epsilon_r, substrate_mm * 1e-3)
    except RFAnalysisError as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(json.dumps(report, indent=2))


@rf_app.command("patch-openems-script")
def patch_openems_script(
    output: Path = typer.Argument(..., dir_okay=False),
    target_hz: float = typer.Option(..., "--target-hz", min=1.0),
    epsilon_r: float = typer.Option(..., "--epsilon-r", min=1.000001),
    substrate_mm: float = typer.Option(..., "--substrate-mm", min=0.001),
    loss_tangent: float = typer.Option(0.002, "--loss-tangent", min=0.0, max=1.0),
    z0: float = typer.Option(50.0, "--z0", min=0.001),
    width_mm: Optional[float] = typer.Option(None, "--width-mm", min=0.001),
    length_mm: Optional[float] = typer.Option(None, "--length-mm", min=0.001),
    feed_offset_mm: Optional[float] = typer.Option(None, "--feed-offset-mm"),
    sweep_span_hz: Optional[float] = typer.Option(None, "--sweep-span-hz", min=1.0),
    sweep_points: int = typer.Option(401, "--sweep-points", min=51, max=5001),
) -> None:
    """Generate a standalone openEMS full-wave rectangular patch model."""
    try:
        spec = RectangularPatchSpec(
            target_frequency_hz=target_hz,
            dielectric_constant=epsilon_r,
            substrate_thickness_m=substrate_mm * 1e-3,
            loss_tangent=loss_tangent,
            reference_impedance_ohms=z0,
            width_m=width_mm * 1e-3 if width_mm is not None else None,
            length_m=length_mm * 1e-3 if length_mm is not None else None,
            feed_offset_m=feed_offset_mm * 1e-3 if feed_offset_mm is not None else None,
            sweep_span_hz=sweep_span_hz,
            sweep_points=sweep_points,
        )
        geometry = resolved_patch_geometry(spec)
        script = render_openems_patch_script(spec)
    except RFAnalysisError as error:
        raise typer.BadParameter(str(error)) from error
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(script, encoding="utf-8")
    try:
        output.chmod(output.stat().st_mode | 0o111)
    except OSError:
        pass
    typer.echo(json.dumps({"script": str(output), "geometry": geometry}, indent=2))


@rf_app.command("openems-build")
def openems_build(
    source: Path = typer.Option(Path("externals/openEMS-Project"), "--source", file_okay=False),
    prefix: Path = typer.Option(Path(".embeddyn/tools/openems"), "--prefix", file_okay=False),
    gui: bool = typer.Option(False, "--gui/--no-gui"),
    python_bindings: bool = typer.Option(True, "--python/--no-python"),
    jobs: Optional[int] = typer.Option(None, "--jobs", min=1),
    timeout: float = typer.Option(7200.0, "--timeout", min=1.0),
) -> None:
    """Build the locked openEMS-Project checkout with its upstream build driver."""
    try:
        result = build_openems_project(
            source, prefix, python_bindings=python_bindings, gui=gui, jobs=jobs, timeout_seconds=timeout
        )
    except RFAnalysisError as error:
        raise typer.BadParameter(str(error)) from error
    if result.stdout:
        typer.echo(result.stdout, nl=not result.stdout.endswith("\n"))
    if result.stderr:
        typer.echo(result.stderr, err=True, nl=not result.stderr.endswith("\n"))
    if result.returncode:
        raise typer.Exit(result.returncode)
    typer.echo(f"openEMS installed under {result.prefix}")


@rf_app.command("openems-run")
def openems_run(
    model: Path = typer.Argument(..., exists=True, dir_okay=False),
    executable: Optional[str] = typer.Option(None, "--executable"),
    timeout: float = typer.Option(3600.0, "--timeout", min=0.1),
    extra: list[str] = typer.Option([], "--extra", help="Additional native openEMS option; repeat as needed."),
) -> None:
    """Run a trusted pre-generated openEMS XML full-wave model."""
    try:
        result = run_openems_xml(model, executable=executable, extra_args=extra, timeout_seconds=timeout)
    except RFAnalysisError as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(result.stdout, nl=not result.stdout.endswith("\n"))
    if result.stderr:
        typer.echo(result.stderr, err=True, nl=not result.stderr.endswith("\n"))
    if result.returncode:
        raise typer.Exit(result.returncode)

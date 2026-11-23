"""RF, antenna and EMC pre-compliance analysis helpers."""

from .openems import OpenEMSBuildResult, OpenEMSRunResult, build_openems_project, run_openems_xml
from .models import RectangularPatchSpec, rectangular_patch_seed, render_openems_patch_script, resolved_patch_geometry
from .analysis import (
    RFAnalysisError,
    TouchstoneNetwork,
    Waveform,
    analyze_touchstone,
    analyze_waveform_noise,
    antenna_tuning_recommendation,
    load_waveform_csv,
    parse_touchstone,
    solver_capabilities,
    waveform_from_points,
)

__all__ = [
    "OpenEMSBuildResult",
    "OpenEMSRunResult",
    "build_openems_project",
    "RFAnalysisError",
    "RectangularPatchSpec",
    "TouchstoneNetwork",
    "Waveform",
    "analyze_touchstone",
    "analyze_waveform_noise",
    "antenna_tuning_recommendation",
    "load_waveform_csv",
    "parse_touchstone",
    "rectangular_patch_seed",
    "render_openems_patch_script",
    "resolved_patch_geometry",
    "run_openems_xml",
    "solver_capabilities",
    "waveform_from_points",
]

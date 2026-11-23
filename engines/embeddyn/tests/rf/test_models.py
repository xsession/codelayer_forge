from __future__ import annotations

from pathlib import Path

import pytest

from embeddyn.rf import RFAnalysisError
from embeddyn.rf.models import (
    RectangularPatchSpec,
    rectangular_patch_seed,
    render_openems_patch_script,
    resolved_patch_geometry,
)


def test_rectangular_patch_seed_for_2450_mhz_fr4_is_plausible() -> None:
    result = rectangular_patch_seed(2.45e9, 4.4, 1.6e-3)
    assert result["patch_width_m"] == pytest.approx(0.03723, rel=0.01)
    assert result["patch_length_m"] == pytest.approx(0.02881, rel=0.01)
    assert 1.0 < result["effective_dielectric_constant"] < 4.4


def test_resolved_patch_geometry_uses_resonant_length_for_feed() -> None:
    spec = RectangularPatchSpec(2.45e9, 4.4, 1.6e-3)
    geometry = resolved_patch_geometry(spec)
    assert geometry["feed_offset_m"] == pytest.approx(-0.18 * geometry["patch_length_m"])
    assert abs(geometry["feed_offset_m"]) < geometry["patch_length_m"] / 2
    assert geometry["sweep_low_hz"] < 2.45e9 < geometry["sweep_high_hz"]


def test_patch_model_rejects_feed_outside_resonant_length() -> None:
    spec = RectangularPatchSpec(2.45e9, 4.4, 1.6e-3, length_m=0.03, feed_offset_m=0.016)
    with pytest.raises(RFAnalysisError, match="inside"):
        resolved_patch_geometry(spec)


def test_generated_openems_patch_script_is_valid_python_and_exports_results() -> None:
    spec = RectangularPatchSpec(2.45e9, 4.4, 1.6e-3, loss_tangent=0.02)
    script = render_openems_patch_script(spec)
    compile(script, "embeddyn_openems_patch.py", "exec")
    assert "patch.s1p" in script
    assert "farfield.csv" in script
    assert "summary.json" in script
    assert "fdtd.Run" in script
    assert "shell=True" not in script

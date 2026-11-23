from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .analysis import RFAnalysisError

C0 = 299_792_458.0
EPS0 = 8.8541878128e-12


@dataclass(frozen=True)
class RectangularPatchSpec:
    target_frequency_hz: float
    dielectric_constant: float
    substrate_thickness_m: float
    loss_tangent: float = 0.002
    reference_impedance_ohms: float = 50.0
    width_m: float | None = None
    length_m: float | None = None
    feed_offset_m: float | None = None
    sweep_span_hz: float | None = None
    sweep_points: int = 401

    def validated(self) -> "RectangularPatchSpec":
        values = {
            "target_frequency_hz": self.target_frequency_hz,
            "dielectric_constant": self.dielectric_constant,
            "substrate_thickness_m": self.substrate_thickness_m,
            "loss_tangent": self.loss_tangent,
            "reference_impedance_ohms": self.reference_impedance_ohms,
        }
        if any(not math.isfinite(float(value)) for value in values.values()):
            raise RFAnalysisError("Patch antenna inputs must be finite")
        if self.target_frequency_hz <= 0:
            raise RFAnalysisError("Target frequency must be positive")
        if self.dielectric_constant <= 1.0:
            raise RFAnalysisError("Relative dielectric constant must be greater than 1")
        if self.substrate_thickness_m <= 0:
            raise RFAnalysisError("Substrate thickness must be positive")
        if self.loss_tangent < 0 or self.loss_tangent > 1:
            raise RFAnalysisError("Loss tangent must be between 0 and 1")
        if self.reference_impedance_ohms <= 0:
            raise RFAnalysisError("Reference impedance must be positive")
        for name, value in (("width", self.width_m), ("length", self.length_m)):
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise RFAnalysisError(f"Patch {name} must be positive")
        if self.feed_offset_m is not None and not math.isfinite(self.feed_offset_m):
            raise RFAnalysisError("Feed offset must be finite")
        if self.sweep_span_hz is not None and (not math.isfinite(self.sweep_span_hz) or self.sweep_span_hz <= 0):
            raise RFAnalysisError("Sweep span must be positive")
        if not 51 <= int(self.sweep_points) <= 5001:
            raise RFAnalysisError("Sweep point count must be between 51 and 5001")
        return self


def rectangular_patch_seed(
    target_frequency_hz: float,
    dielectric_constant: float,
    substrate_thickness_m: float,
) -> dict[str, float]:
    """Return a standard transmission-line first estimate for a rectangular patch.

    The equations are useful for a starting geometry only. Full-wave simulation is
    still required because feed geometry, finite ground, copper, enclosure and the
    actual dielectric stack-up change the resonance and impedance.
    """
    spec = RectangularPatchSpec(
        target_frequency_hz=target_frequency_hz,
        dielectric_constant=dielectric_constant,
        substrate_thickness_m=substrate_thickness_m,
    ).validated()
    f0 = spec.target_frequency_hz
    er = spec.dielectric_constant
    h = spec.substrate_thickness_m
    width = C0 / (2.0 * f0) * math.sqrt(2.0 / (er + 1.0))
    ratio = width / h
    effective_er = (er + 1.0) / 2.0 + (er - 1.0) / 2.0 / math.sqrt(1.0 + 12.0 / ratio)
    delta_l_over_h = 0.412 * ((effective_er + 0.3) * (ratio + 0.264)) / ((effective_er - 0.258) * (ratio + 0.8))
    delta_l = delta_l_over_h * h
    effective_length = C0 / (2.0 * f0 * math.sqrt(effective_er))
    length = effective_length - 2.0 * delta_l
    if length <= 0:
        raise RFAnalysisError("Substrate parameters produce a non-physical patch length")
    return {
        "target_frequency_hz": f0,
        "dielectric_constant": er,
        "substrate_thickness_m": h,
        "effective_dielectric_constant": effective_er,
        "fringing_extension_m": delta_l,
        "effective_length_m": effective_length,
        "patch_width_m": width,
        "patch_length_m": length,
        "free_space_wavelength_m": C0 / f0,
        "guided_half_wavelength_m": effective_length,
    }


def resolved_patch_geometry(spec: RectangularPatchSpec) -> dict[str, Any]:
    spec = spec.validated()
    seed = rectangular_patch_seed(spec.target_frequency_hz, spec.dielectric_constant, spec.substrate_thickness_m)
    width = spec.width_m or seed["patch_width_m"]
    length = spec.length_m or seed["patch_length_m"]
    # Keep the default feed conservative and inside the conductor. It is a seed,
    # not an impedance optimizer; the resulting S11 determines the next move.
    feed = spec.feed_offset_m if spec.feed_offset_m is not None else -0.18 * length
    if abs(feed) >= length / 2.0:
        raise RFAnalysisError("Feed offset must remain inside the patch resonant length")
    span = spec.sweep_span_hz or max(spec.target_frequency_hz * 0.5, 1e6)
    low = max(1.0, spec.target_frequency_hz - span / 2.0)
    high = spec.target_frequency_hz + span / 2.0
    # Ground/substrate margins deliberately exceed the immediate patch footprint.
    margin = max(6.0 * spec.substrate_thickness_m, 0.10 * C0 / spec.target_frequency_hz)
    substrate_width = width + 2.0 * margin
    substrate_length = length + 2.0 * margin
    return {
        **seed,
        "patch_width_m": width,
        "patch_length_m": length,
        "feed_offset_m": feed,
        "substrate_width_m": substrate_width,
        "substrate_length_m": substrate_length,
        "sweep_low_hz": low,
        "sweep_high_hz": high,
        "sweep_points": int(spec.sweep_points),
        "reference_impedance_ohms": spec.reference_impedance_ohms,
        "loss_tangent": spec.loss_tangent,
        "warnings": [
            "Patch dimensions are an analytical seed; run the full-wave model before fabrication.",
            "Feed offset is only a starting point. Tune feed/matching after resonance is placed at the target frequency.",
            "Use the actual PCB stack-up dielectric constant/loss at the RF frequency, not a low-frequency nominal value.",
        ],
    }


def render_openems_patch_script(spec: RectangularPatchSpec) -> str:
    """Generate a standalone, trusted openEMS Python model for a patch antenna.

    The script is generated exclusively from validated numeric parameters. It runs
    a full-wave model, exports S11 as Touchstone RI, and attempts two principal
    far-field cuts at the best-S11 frequency.
    """
    spec = spec.validated()
    geometry = resolved_patch_geometry(spec)
    # openEMS examples commonly use millimetres as CSX delta units.
    mm = 1e3
    values = {
        "f0": spec.target_frequency_hz,
        "f_low": geometry["sweep_low_hz"],
        "f_high": geometry["sweep_high_hz"],
        "points": geometry["sweep_points"],
        "er": spec.dielectric_constant,
        "tan_delta": spec.loss_tangent,
        "h_mm": spec.substrate_thickness_m * mm,
        "pw_mm": geometry["patch_width_m"] * mm,
        "pl_mm": geometry["patch_length_m"] * mm,
        "feed_mm": geometry["feed_offset_m"] * mm,
        "sw_mm": geometry["substrate_width_m"] * mm,
        "sl_mm": geometry["substrate_length_m"] * mm,
        "z0": spec.reference_impedance_ohms,
    }
    return f'''#!/usr/bin/env python3
"""Generated by Embeddyn RF / EMC perspective.

Full-wave rectangular microstrip patch model for openEMS. The model exports
patch.s1p, summary.json and (when NF2FF succeeds) farfield.csv next to this
script in openems_patch_output/.
"""
from pathlib import Path
import csv
import json
import math
import numpy as np
from CSXCAD import ContinuousStructure
from openEMS import openEMS
from openEMS.physical_constants import C0, EPS0

ROOT = Path(__file__).resolve().parent
SIM = ROOT / "openems_patch_output"
SIM.mkdir(parents=True, exist_ok=True)

f0 = {values['f0']!r}
f_low = {values['f_low']!r}
f_high = {values['f_high']!r}
points = {values['points']!r}
er = {values['er']!r}
tan_delta = {values['tan_delta']!r}
h = {values['h_mm']!r}             # mm
patch_w = {values['pw_mm']!r}       # mm
patch_l = {values['pl_mm']!r}       # mm
feed_x = {values['feed_mm']!r}      # mm
substrate_w = {values['sw_mm']!r}   # mm
substrate_l = {values['sl_mm']!r}   # mm
z0 = {values['z0']!r}
unit = 1e-3

# Wideband Gaussian excitation spanning the requested post-processing range.
fc = max((f_high - f_low) / 2.0, f0 * 0.05)
excite_center = (f_high + f_low) / 2.0
fdtd = openEMS(NrTS=30000, EndCriteria=1e-4)
fdtd.SetGaussExcite(excite_center, fc)
fdtd.SetBoundaryCond(["MUR", "MUR", "MUR", "MUR", "MUR", "MUR"])
csx = ContinuousStructure()
fdtd.SetCSX(csx)
mesh = csx.GetGrid()
mesh.SetDeltaUnit(unit)

# Leave substantial air around the radiator and cap mesh size near lambda/20.
lambda_min_mm = C0 / f_high / unit
mesh_res = lambda_min_mm / 20.0
air_xy = max(substrate_w, substrate_l, 0.65 * C0 / f_low / unit)
air_z = max(0.45 * C0 / f_low / unit, 8.0 * h)
mesh.AddLine("x", [-air_xy / 2.0, air_xy / 2.0])
mesh.AddLine("y", [-air_xy / 2.0, air_xy / 2.0])
mesh.AddLine("z", [-air_z / 3.0, 2.0 * air_z / 3.0])

patch = csx.AddMetal("patch")
patch.AddBox(priority=10, start=[-patch_l/2, -patch_w/2, h], stop=[patch_l/2, patch_w/2, h])
fdtd.AddEdges2Grid(dirs="xy", properties=patch, metal_edge_res=mesh_res/2.0)

# openEMS material conductivity equivalent for dielectric loss tangent at f0.
kappa = 2.0 * math.pi * f0 * EPS0 * er * tan_delta
substrate = csx.AddMaterial("substrate", epsilon=er, kappa=kappa)
substrate.AddBox(priority=0, start=[-substrate_l/2, -substrate_w/2, 0], stop=[substrate_l/2, substrate_w/2, h])
mesh.AddLine("z", np.linspace(0, h, 5))

ground = csx.AddMetal("ground")
ground.AddBox(priority=10, start=[-substrate_l/2, -substrate_w/2, 0], stop=[substrate_l/2, substrate_w/2, 0])
fdtd.AddEdges2Grid(dirs="xy", properties=ground)

port = fdtd.AddLumpedPort(1, z0, [feed_x, 0, 0], [feed_x, 0, h], "z", 1.0, priority=5, edges2grid="xy")
mesh.SmoothMeshLines("all", mesh_res, 1.4)
nf2ff = fdtd.CreateNF2FFBox()

fdtd.Run(str(SIM), cleanup=True)
freq = np.linspace(f_low, f_high, points)
port.CalcPort(str(SIM), freq)
s11 = port.uf_ref / port.uf_inc
zin = port.uf_tot / port.if_tot
s11_db = 20.0 * np.log10(np.maximum(np.abs(s11), 1e-300))
best = int(np.argmin(s11_db))

with (SIM / "patch.s1p").open("w", encoding="utf-8", newline="") as handle:
    handle.write("! Generated by Embeddyn/openEMS\\n# Hz S RI R " + format(z0, ".12g") + "\\n")
    for f, gamma in zip(freq, s11):
        handle.write(f"{{float(f):.12g}} {{float(np.real(gamma)):.12g}} {{float(np.imag(gamma)):.12g}}\\n")

summary = {{
    "target_frequency_hz": f0,
    "best_frequency_hz": float(freq[best]),
    "best_s11_db": float(s11_db[best]),
    "best_impedance_ohms": {{"real": float(np.real(zin[best])), "imag": float(np.imag(zin[best]))}},
    "patch_width_mm": patch_w,
    "patch_length_mm": patch_l,
    "feed_offset_mm": feed_x,
    "substrate_epsilon_r": er,
    "substrate_thickness_mm": h,
}}

try:
    theta = np.arange(-180.0, 181.0, 2.0)
    phi = [0.0, 90.0]
    ff = nf2ff.CalcNF2FF(str(SIM), float(freq[best]), theta, phi, center=[0, 0, 1e-3])
    dmax_dbi = 10.0 * math.log10(max(float(ff.Dmax[0]), 1e-300))
    normalized = 20.0 * np.log10(np.maximum(ff.E_norm[0] / np.max(ff.E_norm[0]), 1e-300)) + dmax_dbi
    summary["directivity_max_dbi"] = dmax_dbi
    summary["radiated_power_w"] = float(ff.Prad[0])
    with (SIM / "farfield.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["theta_deg", "phi0_dbi", "phi90_dbi"])
        for i, angle in enumerate(theta):
            writer.writerow([float(angle), float(normalized[i, 0]), float(normalized[i, 1])])
except Exception as error:
    # S11 remains useful even if a far-field transform is unavailable/invalid.
    summary["farfield_warning"] = str(error)

(SIM / "summary.json").write_text(json.dumps(summary, indent=2) + "\\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
'''

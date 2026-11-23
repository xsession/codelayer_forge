from __future__ import annotations

import cmath
import csv
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


_C0 = 299_792_458.0
_FREQ_SCALE = {
    "hz": 1.0,
    "khz": 1e3,
    "mhz": 1e6,
    "ghz": 1e9,
}


class RFAnalysisError(ValueError):
    """Raised for malformed RF measurement/simulation data."""


@dataclass(frozen=True)
class TouchstoneNetwork:
    frequencies_hz: tuple[float, ...]
    s: tuple[tuple[tuple[complex, ...], ...], ...]
    nports: int
    z0_ohms: float
    parameter: str = "S"
    data_format: str = "MA"
    frequency_unit: str = "GHz"

    def s_parameter(self, output_port: int, input_port: int) -> tuple[complex, ...]:
        if not (1 <= output_port <= self.nports and 1 <= input_port <= self.nports):
            raise RFAnalysisError("S-parameter port index is out of range")
        return tuple(matrix[output_port - 1][input_port - 1] for matrix in self.s)


@dataclass(frozen=True)
class Waveform:
    values: tuple[float, ...]
    timestamps: tuple[float, ...] | None = None
    sample_rate_hz: float | None = None
    value_unit: str = "V"


def solver_capabilities() -> dict[str, Any]:
    import importlib.util
    import os
    import shutil

    candidates = []
    for variable in ("EMBEDDYN_OPENEMS_PREFIX", "OPENEMS_INSTALL_PATH"):
        if os.environ.get(variable):
            candidates.append(Path(os.environ[variable]) / "bin" / "openEMS")
    # Editable/source installs can discover the bootstrap-managed local prefix
    # without requiring users to mutate PATH before launching Studio.
    candidates.append(Path(__file__).resolve().parents[2] / ".embeddyn" / "tools" / "openems" / "bin" / "openEMS")
    openems_executable = shutil.which("openEMS") or shutil.which("openems")
    if not openems_executable:
        openems_executable = next((str(path) for path in candidates if path.is_file()), None)
    appcsxcad = shutil.which("AppCSXCAD")
    nec2c = shutil.which("nec2c")
    return {
        "openems": {
            "available": bool(openems_executable),
            "executable": openems_executable,
            "viewer": appcsxcad,
            "python_module": importlib.util.find_spec("openEMS") is not None,
            "purpose": "3-D full-wave antenna, near-field and far-field simulation",
        },
        "scikit_rf": {
            "available": importlib.util.find_spec("skrf") is not None,
            "purpose": "Touchstone, N-port and RF network analysis",
        },
        "nec2c": {
            "available": bool(nec2c),
            "executable": nec2c,
            "purpose": "wire-antenna method-of-moments simulation",
        },
        "builtin": {
            "available": True,
            "purpose": "Touchstone S11/VSWR/impedance and time-domain EMI spectrum analysis",
        },
    }


def parse_touchstone(path: Path, *, filename_hint: str | None = None) -> TouchstoneNetwork:
    path = Path(path)
    if path.stat().st_size > 32 * 1024 * 1024:
        raise RFAnalysisError("Touchstone file exceeds the 32 MiB analysis limit")
    suffix = Path(filename_hint).suffix.lower() if filename_hint else path.suffix.lower()
    if len(suffix) < 4 or not suffix.startswith(".s") or not suffix.endswith("p"):
        raise RFAnalysisError("Touchstone filename must use an .sNp extension, for example .s1p or .s2p")
    try:
        nports = int(suffix[2:-1])
    except ValueError as error:
        raise RFAnalysisError("Could not determine Touchstone port count from filename") from error
    if nports < 1 or nports > 32:
        raise RFAnalysisError("Touchstone port count must be between 1 and 32")

    frequency_unit = "ghz"
    parameter = "s"
    data_format = "ma"
    z0_ohms = 50.0
    numeric_tokens: list[float] = []
    in_network_data = True

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.split("!", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            keyword = line.split("]", 1)[0].lower() + "]"
            if keyword == "[network data]":
                in_network_data = True
            elif keyword in {"[noise data]", "[end]"}:
                in_network_data = False
            continue
        if line.startswith("#"):
            tokens = line[1:].strip().lower().split()
            if tokens:
                if tokens[0] not in _FREQ_SCALE:
                    raise RFAnalysisError(f"Unsupported Touchstone frequency unit: {tokens[0]}")
                frequency_unit = tokens[0]
            if len(tokens) >= 2:
                parameter = tokens[1]
            if len(tokens) >= 3:
                data_format = tokens[2]
            if "r" in tokens:
                index = tokens.index("r")
                if index + 1 >= len(tokens):
                    raise RFAnalysisError("Touchstone reference impedance is missing after R")
                z0_ohms = float(tokens[index + 1])
            continue
        if not in_network_data:
            continue
        try:
            numeric_tokens.extend(float(token.replace("D", "E").replace("d", "e")) for token in line.split())
        except ValueError as error:
            raise RFAnalysisError(f"Invalid numeric data in Touchstone file: {raw_line!r}") from error

    if parameter != "s":
        raise RFAnalysisError(f"Built-in Touchstone analyzer currently requires S-parameters, got {parameter.upper()}")
    if data_format not in {"ri", "ma", "db"}:
        raise RFAnalysisError(f"Unsupported Touchstone data format: {data_format.upper()}")
    if not math.isfinite(z0_ohms) or z0_ohms <= 0:
        raise RFAnalysisError("Touchstone reference impedance must be positive")

    record_size = 1 + 2 * nports * nports
    if len(numeric_tokens) < record_size:
        raise RFAnalysisError("Touchstone file does not contain a complete network data record")
    if len(numeric_tokens) % record_size != 0:
        raise RFAnalysisError(
            "Touchstone network data has an incomplete record; unsupported per-port impedances or mixed data may be present"
        )

    frequencies: list[float] = []
    matrices: list[tuple[tuple[complex, ...], ...]] = []
    scale = _FREQ_SCALE[frequency_unit]
    for offset in range(0, len(numeric_tokens), record_size):
        record = numeric_tokens[offset : offset + record_size]
        frequency = record[0] * scale
        if not math.isfinite(frequency) or frequency < 0:
            raise RFAnalysisError("Touchstone frequency values must be finite and non-negative")
        matrix = [[0j for _ in range(nports)] for _ in range(nports)]
        pair_index = 1
        # Touchstone ordering is S11,S21,...,SN1,S12,S22,...,SNN.
        for input_port in range(nports):
            for output_port in range(nports):
                first = record[pair_index]
                second = record[pair_index + 1]
                pair_index += 2
                matrix[output_port][input_port] = _pair_to_complex(first, second, data_format)
        frequencies.append(frequency)
        matrices.append(tuple(tuple(row) for row in matrix))

    if any(b <= a for a, b in zip(frequencies, frequencies[1:])):
        raise RFAnalysisError("Touchstone frequencies must be strictly increasing")

    return TouchstoneNetwork(
        frequencies_hz=tuple(frequencies),
        s=tuple(matrices),
        nports=nports,
        z0_ohms=z0_ohms,
        parameter=parameter.upper(),
        data_format=data_format.upper(),
        frequency_unit=frequency_unit.upper(),
    )


def analyze_touchstone(
    path: Path,
    *,
    target_frequency_hz: float | None = None,
    return_loss_threshold_db: float = 10.0,
    reference_impedance_ohms: float | None = None,
    filename_hint: str | None = None,
) -> dict[str, Any]:
    network = parse_touchstone(path, filename_hint=filename_hint)
    z0 = float(reference_impedance_ohms or network.z0_ohms)
    if not math.isfinite(z0) or z0 <= 0:
        raise RFAnalysisError("Reference impedance must be positive")

    s11 = network.s_parameter(1, 1)
    rows: list[dict[str, Any]] = []
    for frequency, gamma in zip(network.frequencies_hz, s11):
        magnitude = abs(gamma)
        s11_db = _db20(magnitude)
        impedance = _reflection_to_impedance(gamma, z0)
        rows.append({
            "frequency_hz": frequency,
            "s11_db": s11_db,
            "return_loss_db": -s11_db,
            "vswr": _vswr(magnitude),
            "accepted_power_percent": max(0.0, min(100.0, (1.0 - magnitude * magnitude) * 100.0)),
            "impedance_ohms": {"real": impedance.real, "imag": impedance.imag},
            "gamma": {"real": gamma.real, "imag": gamma.imag, "magnitude": magnitude, "phase_deg": math.degrees(cmath.phase(gamma))},
        })

    best_index = min(range(len(rows)), key=lambda index: rows[index]["s11_db"])
    resonances = _find_resonances(rows)
    if not resonances:
        resonances = [rows[best_index]]
    bandwidth = _threshold_bandwidth(rows, best_index, -abs(return_loss_threshold_db))
    target = None
    tuning = None
    if target_frequency_hz is not None:
        if not math.isfinite(target_frequency_hz) or target_frequency_hz <= 0:
            raise RFAnalysisError("Target frequency must be positive")
        target_index = min(range(len(rows)), key=lambda index: abs(rows[index]["frequency_hz"] - target_frequency_hz))
        target = rows[target_index]
        resonance = min(resonances, key=lambda row: abs(row["frequency_hz"] - target_frequency_hz))
        tuning = antenna_tuning_recommendation(
            resonance_frequency_hz=resonance["frequency_hz"],
            target_frequency_hz=target_frequency_hz,
            impedance=complex(target["impedance_ohms"]["real"], target["impedance_ohms"]["imag"]),
            reference_impedance_ohms=z0,
        )

    return {
        "source": str(Path(path)),
        "nports": network.nports,
        "points": len(rows),
        "reference_impedance_ohms": z0,
        "frequency_range_hz": [rows[0]["frequency_hz"], rows[-1]["frequency_hz"]],
        "best_match": rows[best_index],
        "resonances": resonances[:16],
        "bandwidth": bandwidth,
        "target": target,
        "tuning": tuning,
        "trace": rows,
        "notes": [
            "S11-derived impedance assumes the selected reference impedance.",
            "Geometry scaling is a first-order antenna tuning hint; full-wave re-simulation is required after each geometry/material change.",
        ],
    }


def antenna_tuning_recommendation(
    *,
    resonance_frequency_hz: float,
    target_frequency_hz: float,
    impedance: complex,
    reference_impedance_ohms: float = 50.0,
) -> dict[str, Any]:
    for value, name in (
        (resonance_frequency_hz, "resonance frequency"),
        (target_frequency_hz, "target frequency"),
        (reference_impedance_ohms, "reference impedance"),
    ):
        if not math.isfinite(value) or value <= 0:
            raise RFAnalysisError(f"{name} must be positive")
    scale = resonance_frequency_hz / target_frequency_hz
    percent = (scale - 1.0) * 100.0
    if abs(percent) < 0.25:
        geometry_direction = "hold resonant length; focus on feed/matching/ground geometry"
    elif percent < 0:
        geometry_direction = "shorten the dominant resonant current path"
    else:
        geometry_direction = "lengthen the dominant resonant current path"

    omega = 2.0 * math.pi * target_frequency_hz
    cancellation_reactance = -impedance.imag
    matching: dict[str, Any]
    if abs(cancellation_reactance) < 1e-6:
        matching = {"type": "none", "reason": "input reactance is already near zero at the target frequency"}
    elif cancellation_reactance > 0:
        matching = {
            "type": "series_inductor",
            "reactance_ohms": cancellation_reactance,
            "inductance_h": cancellation_reactance / omega,
        }
    else:
        matching = {
            "type": "series_capacitor",
            "reactance_ohms": cancellation_reactance,
            "capacitance_f": -1.0 / (omega * cancellation_reactance),
        }

    wavelength = _C0 / target_frequency_hz
    return {
        "geometry_scale": scale,
        "geometry_change_percent": percent,
        "geometry_direction": geometry_direction,
        "target_wavelength_m": wavelength,
        "quarter_wavelength_m": wavelength / 4.0,
        "input_impedance_ohms": {"real": impedance.real, "imag": impedance.imag},
        "resistance_error_ohms": impedance.real - reference_impedance_ohms,
        "series_reactance_cancellation": matching,
        "warning": (
            "The length-scale and single-reactance suggestions are first-order tuning aids, not a synthesized broadband match. "
            "Re-run a full-wave model or verify with a VNA after geometry/feed/ground changes."
        ),
    }


def load_waveform_csv(
    path: Path,
    *,
    time_column: str | None = None,
    value_column: str | None = None,
    sample_rate_hz: float | None = None,
    value_unit: str = "V",
) -> Waveform:
    path = Path(path)
    if path.stat().st_size > 64 * 1024 * 1024:
        raise RFAnalysisError("Waveform CSV exceeds the 64 MiB analysis limit")
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t ")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(handle, dialect)
        rows = [row for row in reader if row and any(cell.strip() for cell in row)]

    if not rows:
        raise RFAnalysisError("Waveform CSV is empty")

    has_header = False
    try:
        [float(cell.strip()) for cell in rows[0][:2]]
    except (ValueError, TypeError):
        has_header = True

    header = [cell.strip() for cell in rows[0]] if has_header else []
    data_rows = rows[1:] if has_header else rows
    if has_header:
        time_index = _resolve_column(header, time_column, preferred=("time", "timestamp", "t"), allow_none=True)
        value_index = _resolve_column(header, value_column, preferred=("value", "voltage", "current", "signal", "v", "i"), allow_none=False)
    else:
        if time_column or value_column:
            raise RFAnalysisError("Named CSV columns require a header row")
        if len(rows[0]) >= 2:
            time_index, value_index = 0, 1
        else:
            time_index, value_index = None, 0

    values: list[float] = []
    timestamps: list[float] = []
    required = max(value_index, time_index or 0)
    for row_number, row in enumerate(data_rows, start=2 if has_header else 1):
        if len(row) <= required:
            continue
        try:
            value = float(row[value_index].strip())
            timestamp = float(row[time_index].strip()) if time_index is not None else None
        except ValueError as error:
            raise RFAnalysisError(f"Invalid numeric waveform data on CSV row {row_number}") from error
        if not math.isfinite(value) or (timestamp is not None and not math.isfinite(timestamp)):
            raise RFAnalysisError(f"Non-finite waveform data on CSV row {row_number}")
        values.append(value)
        if timestamp is not None:
            timestamps.append(timestamp)

    if len(values) < 8:
        raise RFAnalysisError("At least 8 waveform samples are required")
    if sample_rate_hz is not None and (not math.isfinite(sample_rate_hz) or sample_rate_hz <= 0):
        raise RFAnalysisError("Sample rate must be positive")

    return Waveform(
        values=tuple(values),
        timestamps=tuple(timestamps) if timestamps else None,
        sample_rate_hz=sample_rate_hz,
        value_unit=value_unit,
    )


def analyze_waveform_noise(
    waveform: Waveform,
    *,
    impedance_ohms: float = 50.0,
    max_fft_points: int = 16384,
    top_peaks: int = 20,
    remove_dc: bool = True,
    limit_mask: Sequence[dict[str, float | str]] | None = None,
) -> dict[str, Any]:
    if not math.isfinite(impedance_ohms) or impedance_ohms <= 0:
        raise RFAnalysisError("Measurement impedance must be positive")
    if max_fft_points < 8:
        raise RFAnalysisError("max_fft_points must be at least 8")
    if top_peaks < 1:
        raise RFAnalysisError("top_peaks must be at least 1")

    sample_rate_hz, jitter = _sample_rate(waveform)
    source_values = list(waveform.values)
    n = min(_floor_power_of_two(len(source_values)), _floor_power_of_two(max_fft_points))
    if n < 8:
        raise RFAnalysisError("At least 8 samples are required after FFT sizing")
    values = source_values[:n]
    mean = sum(values) / len(values)
    if remove_dc:
        values = [value - mean for value in values]

    window = [0.5 - 0.5 * math.cos(2.0 * math.pi * index / (n - 1)) for index in range(n)]
    coherent_gain = sum(window) / n
    spectrum = _fft([complex(value * window[index], 0.0) for index, value in enumerate(values)])
    bin_hz = sample_rate_hz / n
    bins: list[dict[str, Any]] = []
    for index in range(1, n // 2 + 1):
        frequency = index * bin_hz
        peak_amplitude = 2.0 * abs(spectrum[index]) / (n * coherent_gain)
        if index == n // 2:
            peak_amplitude /= 2.0
        rms_amplitude = peak_amplitude / math.sqrt(2.0)
        dbv = _db20(rms_amplitude)
        dbuv = dbv + 120.0
        power_watts = (rms_amplitude * rms_amplitude) / impedance_ohms
        dbm = 10.0 * math.log10(max(power_watts / 1e-3, 1e-300))
        bins.append({
            "frequency_hz": frequency,
            "amplitude_peak": peak_amplitude,
            "amplitude_rms": rms_amplitude,
            "dbv_rms": dbv,
            "dbuv_rms": dbuv,
            "dbm": dbm,
        })

    peak_candidates: list[dict[str, Any]] = []
    for index, item in enumerate(bins):
        previous = bins[index - 1]["amplitude_rms"] if index > 0 else -1.0
        following = bins[index + 1]["amplitude_rms"] if index + 1 < len(bins) else -1.0
        if item["amplitude_rms"] >= previous and item["amplitude_rms"] >= following:
            peak_candidates.append(item.copy())
    peaks = sorted(peak_candidates, key=lambda row: row["amplitude_rms"], reverse=True)[:top_peaks]
    fundamental_hz = min((row["frequency_hz"] for row in peaks if row["amplitude_rms"] > 0), default=None)
    if peaks:
        strongest = max(peaks, key=lambda row: row["amplitude_rms"])
        # Prefer the lowest meaningful local maximum, but avoid an arbitrary low-level FFT bin.
        threshold = strongest["amplitude_rms"] * 0.02
        meaningful = [row for row in peak_candidates if row["amplitude_rms"] >= threshold]
        if meaningful:
            fundamental_hz = min(row["frequency_hz"] for row in meaningful)
    for row in peaks:
        if fundamental_hz:
            harmonic = max(1, round(row["frequency_hz"] / fundamental_hz))
            expected = harmonic * fundamental_hz
            row["harmonic"] = harmonic if abs(row["frequency_hz"] - expected) <= 1.5 * bin_hz else None
        else:
            row["harmonic"] = None

    exceedances = _apply_limit_mask(peaks, limit_mask or [])
    nyquist = sample_rate_hz / 2.0
    return {
        "samples_input": len(waveform.values),
        "samples_fft": n,
        "sample_rate_hz": sample_rate_hz,
        "sample_interval_jitter_percent": jitter * 100.0,
        "nyquist_hz": nyquist,
        "bin_width_hz": bin_hz,
        "dc_mean": mean,
        "value_unit": waveform.value_unit,
        "measurement_impedance_ohms": impedance_ohms,
        "fundamental_hz": fundamental_hz,
        "peaks": peaks,
        "limit_exceedances": exceedances,
        "trace": bins,
        "warnings": _noise_warnings(sample_rate_hz, jitter, waveform.value_unit, bool(limit_mask)),
        "compliance": {
            "is_compliance_measurement": False,
            "reason": (
                "FFT amplitude is a pre-compliance/simulation estimate. Regulatory EMI measurements require the specified "
                "fixture/LISN or antenna, detector, RBW/VBW, dwell time, calibration and site conditions."
            ),
        },
    }


def waveform_from_points(
    points: Iterable[dict[str, Any]],
    *,
    value_unit: str = "V",
) -> Waveform:
    values: list[float] = []
    timestamps: list[float] = []
    for point in points:
        try:
            value = float(point["value"])
            timestamp = float(point["timestamp"])
        except (KeyError, TypeError, ValueError) as error:
            raise RFAnalysisError("Telemetry points must contain numeric timestamp and value fields") from error
        if not math.isfinite(value) or not math.isfinite(timestamp):
            continue
        values.append(value)
        timestamps.append(timestamp)
    if len(values) < 8:
        raise RFAnalysisError("At least 8 numeric telemetry samples are required")
    return Waveform(tuple(values), tuple(timestamps), None, value_unit)


def _pair_to_complex(first: float, second: float, data_format: str) -> complex:
    if data_format == "ri":
        return complex(first, second)
    if data_format == "ma":
        return cmath.rect(first, math.radians(second))
    magnitude = 10.0 ** (first / 20.0)
    return cmath.rect(magnitude, math.radians(second))


def _db20(value: float) -> float:
    return 20.0 * math.log10(max(abs(value), 1e-300))


def _vswr(magnitude: float) -> float | None:
    if magnitude >= 1.0:
        return None
    return (1.0 + magnitude) / max(1.0 - magnitude, 1e-15)


def _reflection_to_impedance(gamma: complex, z0: float) -> complex:
    denominator = 1.0 - gamma
    if abs(denominator) < 1e-15:
        return complex(1e300, 0.0)
    return z0 * (1.0 + gamma) / denominator


def _find_resonances(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(rows) < 3:
        return []
    candidates = []
    for index in range(1, len(rows) - 1):
        current = rows[index]["s11_db"]
        if current <= rows[index - 1]["s11_db"] and current <= rows[index + 1]["s11_db"]:
            candidates.append(rows[index])
    return sorted(candidates, key=lambda row: row["s11_db"])


def _threshold_bandwidth(rows: Sequence[dict[str, Any]], best_index: int, threshold_db: float) -> dict[str, Any] | None:
    if rows[best_index]["s11_db"] > threshold_db:
        return None
    left = best_index
    right = best_index
    while left > 0 and rows[left - 1]["s11_db"] <= threshold_db:
        left -= 1
    while right + 1 < len(rows) and rows[right + 1]["s11_db"] <= threshold_db:
        right += 1
    low = rows[left]["frequency_hz"]
    high = rows[right]["frequency_hz"]
    center = (low + high) / 2.0
    return {
        "threshold_s11_db": threshold_db,
        "low_hz": low,
        "high_hz": high,
        "width_hz": high - low,
        "fractional_percent": ((high - low) / center * 100.0) if center > 0 else 0.0,
        "edge_limited": left == 0 or right == len(rows) - 1,
    }


def _resolve_column(header: Sequence[str], requested: str | None, *, preferred: Sequence[str], allow_none: bool) -> int | None:
    normalized = [item.strip().lower() for item in header]
    if requested:
        try:
            return normalized.index(requested.strip().lower())
        except ValueError as error:
            raise RFAnalysisError(f"CSV column not found: {requested}") from error
    for candidate in preferred:
        if candidate in normalized:
            return normalized.index(candidate)
    if allow_none:
        return None
    if len(header) >= 2:
        return 1
    if header:
        return 0
    raise RFAnalysisError("CSV does not contain a usable value column")


def _sample_rate(waveform: Waveform) -> tuple[float, float]:
    if waveform.sample_rate_hz:
        return waveform.sample_rate_hz, 0.0
    if not waveform.timestamps or len(waveform.timestamps) < 2:
        raise RFAnalysisError("Waveform needs timestamps or an explicit sample rate")
    deltas = [b - a for a, b in zip(waveform.timestamps, waveform.timestamps[1:])]
    if any(not math.isfinite(delta) or delta <= 0 for delta in deltas):
        raise RFAnalysisError("Waveform timestamps must be strictly increasing")
    median_delta = statistics.median(deltas)
    jitter = max(abs(delta - median_delta) for delta in deltas) / median_delta
    return 1.0 / median_delta, jitter


def _floor_power_of_two(value: int) -> int:
    return 1 << (int(value).bit_length() - 1) if value > 0 else 0


def _fft(values: Sequence[complex]) -> list[complex]:
    n = len(values)
    if n == 0 or n & (n - 1):
        raise RFAnalysisError("FFT input length must be a power of two")
    result = list(values)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            result[i], result[j] = result[j], result[i]
    length = 2
    while length <= n:
        angle = -2.0 * math.pi / length
        wlen = complex(math.cos(angle), math.sin(angle))
        half = length // 2
        for start in range(0, n, length):
            w = 1 + 0j
            for index in range(start, start + half):
                even = result[index]
                odd = result[index + half] * w
                result[index] = even + odd
                result[index + half] = even - odd
                w *= wlen
        length <<= 1
    return result


def _interpolate_limit(frequency_hz: float, mask: Sequence[dict[str, float | str]], unit: str) -> float | None:
    points = sorted(
        (float(item["frequency_hz"]), float(item["limit"]))
        for item in mask
        if str(item.get("unit", unit)).lower() == unit.lower()
    )
    if not points or frequency_hz < points[0][0] or frequency_hz > points[-1][0]:
        return None
    for (f0, v0), (f1, v1) in zip(points, points[1:]):
        if f0 <= frequency_hz <= f1:
            if f1 == f0:
                return v1
            # EMI masks are normally plotted against log-frequency.
            x = math.log10(max(frequency_hz, 1e-30))
            x0 = math.log10(max(f0, 1e-30))
            x1 = math.log10(max(f1, 1e-30))
            ratio = (x - x0) / (x1 - x0) if x1 != x0 else 0.0
            return v0 + ratio * (v1 - v0)
    return points[-1][1] if frequency_hz == points[-1][0] else None


def _apply_limit_mask(peaks: Sequence[dict[str, Any]], mask: Sequence[dict[str, float | str]]) -> list[dict[str, Any]]:
    if not mask:
        return []
    units = {str(item.get("unit", "dBuV")).lower() for item in mask}
    if len(units) != 1:
        raise RFAnalysisError("All limit-mask points must use the same unit")
    unit = next(iter(units))
    metric = {"dbuv": "dbuv_rms", "dbm": "dbm", "dbv": "dbv_rms"}.get(unit)
    if not metric:
        raise RFAnalysisError("Limit-mask unit must be dBuV, dBV or dBm")
    results = []
    for peak in peaks:
        limit = _interpolate_limit(peak["frequency_hz"], mask, unit)
        if limit is None:
            continue
        level = float(peak[metric])
        margin = limit - level
        results.append({
            "frequency_hz": peak["frequency_hz"],
            "unit": unit,
            "level": level,
            "limit": limit,
            "margin_db": margin,
            "exceeds": margin < 0,
        })
    return results


def _noise_warnings(sample_rate_hz: float, jitter: float, value_unit: str, has_limit: bool) -> list[str]:
    warnings = [
        f"Spectrum above {sample_rate_hz / 2.0:g} Hz cannot be inferred from this waveform (Nyquist limit).",
        "A simulated node voltage/current spectrum is not automatically equivalent to radiated or conducted EMC field strength.",
    ]
    if jitter > 0.01:
        warnings.append(
            f"Sample interval jitter is {jitter * 100.0:.2f}%; resample to a uniform time grid before relying on high-frequency bins."
        )
    if value_unit.lower() not in {"v", "volt", "volts"}:
        warnings.append("dBV/dBuV/dBm values are only directly meaningful when the waveform represents volts at the stated impedance.")
    if has_limit:
        warnings.append("Custom limit masks are engineering overlays only; they do not implement detector/RBW/VBW/site requirements of an EMC standard.")
    return warnings

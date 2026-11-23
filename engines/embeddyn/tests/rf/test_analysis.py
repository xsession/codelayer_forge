from __future__ import annotations

import math
from pathlib import Path

import pytest

from embeddyn.rf import (
    Waveform,
    analyze_touchstone,
    analyze_waveform_noise,
    antenna_tuning_recommendation,
    load_waveform_csv,
    parse_touchstone,
)


def test_parse_touchstone_s1p_db_and_antenna_tuning(tmp_path: Path) -> None:
    path = tmp_path / "antenna.s1p"
    path.write_text(
        "! fixture\n"
        "# MHz S DB R 50\n"
        "2300 -8 15\n"
        "2350 -14 5\n"
        "2400 -28 0\n"
        "2450 -16 -4\n"
        "2500 -7 -12\n",
        encoding="utf-8",
    )

    network = parse_touchstone(path)
    assert network.nports == 1
    assert network.frequencies_hz[2] == pytest.approx(2.4e9)
    assert abs(network.s_parameter(1, 1)[2]) == pytest.approx(10 ** (-28 / 20))

    report = analyze_touchstone(path, target_frequency_hz=2.45e9)
    assert report["best_match"]["frequency_hz"] == pytest.approx(2.4e9)
    assert report["best_match"]["s11_db"] == pytest.approx(-28.0)
    assert report["bandwidth"]["low_hz"] == pytest.approx(2.35e9)
    assert report["bandwidth"]["high_hz"] == pytest.approx(2.45e9)
    assert report["target"]["frequency_hz"] == pytest.approx(2.45e9)
    assert report["tuning"]["geometry_scale"] == pytest.approx(2.4 / 2.45)
    assert "shorten" in report["tuning"]["geometry_direction"]


def test_touchstone_s2p_ordering(tmp_path: Path) -> None:
    path = tmp_path / "filter.s2p"
    # Touchstone 2-port ordering: S11, S21, S12, S22.
    path.write_text("# GHz S RI R 50\n1 0.1 0 0.8 0 0.7 0 0.2 0\n", encoding="utf-8")
    network = parse_touchstone(path)
    assert network.s_parameter(1, 1)[0] == pytest.approx(0.1 + 0j)
    assert network.s_parameter(2, 1)[0] == pytest.approx(0.8 + 0j)
    assert network.s_parameter(1, 2)[0] == pytest.approx(0.7 + 0j)
    assert network.s_parameter(2, 2)[0] == pytest.approx(0.2 + 0j)


def test_reactance_tuning_recommends_series_component() -> None:
    inductive_cancel = antenna_tuning_recommendation(
        resonance_frequency_hz=2.3e9,
        target_frequency_hz=2.4e9,
        impedance=complex(40, -20),
    )
    assert inductive_cancel["series_reactance_cancellation"]["type"] == "series_inductor"
    assert inductive_cancel["series_reactance_cancellation"]["inductance_h"] > 0

    capacitive_cancel = antenna_tuning_recommendation(
        resonance_frequency_hz=2.5e9,
        target_frequency_hz=2.4e9,
        impedance=complex(60, 20),
    )
    assert capacitive_cancel["series_reactance_cancellation"]["type"] == "series_capacitor"
    assert capacitive_cancel["series_reactance_cancellation"]["capacitance_f"] > 0


def test_noise_fft_finds_tone_and_calibrates_50_ohm_level() -> None:
    sample_rate = 8192.0
    tone_hz = 1000.0
    values = tuple(math.sin(2 * math.pi * tone_hz * index / sample_rate) for index in range(8192))
    report = analyze_waveform_noise(Waveform(values=values, sample_rate_hz=sample_rate, value_unit="V"))

    strongest = report["peaks"][0]
    assert strongest["frequency_hz"] == pytest.approx(tone_hz, abs=report["bin_width_hz"])
    assert strongest["amplitude_peak"] == pytest.approx(1.0, rel=0.01)
    assert strongest["dbuv_rms"] == pytest.approx(116.99, abs=0.15)
    assert strongest["dbm"] == pytest.approx(10.0, abs=0.15)
    assert report["nyquist_hz"] == pytest.approx(sample_rate / 2)
    assert report["compliance"]["is_compliance_measurement"] is False


def test_waveform_csv_uses_timestamps_and_limit_mask(tmp_path: Path) -> None:
    path = tmp_path / "noise.csv"
    sample_rate = 4096.0
    rows = ["time,voltage"]
    for index in range(4096):
        t = index / sample_rate
        value = 0.2 * math.sin(2 * math.pi * 512 * t)
        rows.append(f"{t:.12f},{value:.12f}")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    waveform = load_waveform_csv(path)
    report = analyze_waveform_noise(
        waveform,
        limit_mask=[
            {"frequency_hz": 100.0, "limit": 80.0, "unit": "dBuV"},
            {"frequency_hz": 2000.0, "limit": 80.0, "unit": "dBuV"},
        ],
    )
    assert report["sample_rate_hz"] == pytest.approx(sample_rate, rel=1e-6)
    assert report["peaks"][0]["frequency_hz"] == pytest.approx(512.0, abs=1.0)
    assert any(item["exceeds"] for item in report["limit_exceedances"])


def test_rf_manifest_profile_pins_recursive_openems():
    from embeddyn.dependency_manager import load_manifest, projects_from_manifest

    root = Path(__file__).resolve().parents[2]
    manifest = load_manifest(root / "embeddyn.yml")
    projects = projects_from_manifest(manifest, root=root, profile="rf")
    openems = next(project for project in projects if project.name == "openems-project")
    assert openems.revision == "v0.0.36"
    assert openems.recursive is True
    import json
    lock = json.loads((root / "embeddyn.lock.json").read_text(encoding="utf-8"))
    assert lock["lock"]["projects"]["openems-project"]["commit"] == "d0d2e8dad8a02388f1919bbcdd29a67e9199dd2c"

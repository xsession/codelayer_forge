from __future__ import annotations

import math

from fastapi.testclient import TestClient

from embeddyn.local.api import create_app
from embeddyn.local.config import LocalConfig


def test_rf_api_touchstone_and_session_noise(tmp_path) -> None:
    config = LocalConfig.from_env(data_dir=tmp_path / "data", workspace=tmp_path / "workspace")
    with TestClient(create_app(config)) as client:
        capabilities = client.get("/api/rf/capabilities")
        assert capabilities.status_code == 200
        assert capabilities.json()["builtin"]["available"] is True


        patch_seed = client.post(
            "/api/rf/patch/seed",
            json={
                "target_frequency_hz": 2.45e9,
                "dielectric_constant": 4.4,
                "substrate_thickness_m": 0.0016,
                "loss_tangent": 0.02,
            },
        )
        assert patch_seed.status_code == 200
        patch = patch_seed.json()
        assert 0.02 < patch["patch_length_m"] < 0.04

        patch_script = client.post(
            "/api/rf/patch/openems-script",
            json={
                "target_frequency_hz": 2.45e9,
                "dielectric_constant": 4.4,
                "substrate_thickness_m": 0.0016,
            },
        )
        assert patch_script.status_code == 200
        generated = patch_script.json()
        assert generated["filename"].endswith(".py")
        compile(generated["script"], generated["filename"], "exec")

        touchstone = b"# MHz S DB R 50\n2300 -8 0\n2400 -25 0\n2500 -9 0\n"
        upload = client.post(
            "/api/assets",
            files={"file": ("antenna.s1p", touchstone, "application/octet-stream")},
        )
        assert upload.status_code == 200
        asset_id = upload.json()["id"]
        report = client.post(
            "/api/rf/touchstone/analyze",
            json={"asset_id": asset_id, "target_frequency_hz": 2.4e9},
        )
        assert report.status_code == 200
        assert report.json()["best_match"]["s11_db"] == -25.0
        assert report.json()["source"] == "antenna.s1p"

        store = client.app.state.store
        session_id = store.create_session(target="test", command=["test"])
        sample_rate = 4096.0
        points = [
            {
                "timestamp": index / sample_rate,
                "channel": "switch_node",
                "value": math.sin(2 * math.pi * 512 * index / sample_rate),
            }
            for index in range(4096)
        ]
        ingest = client.post(f"/api/sessions/{session_id}/telemetry", json={"points": points})
        assert ingest.status_code == 200
        noise = client.post(
            "/api/rf/noise/session",
            json={"session_id": session_id, "channel": "switch_node", "impedance_ohms": 50},
        )
        assert noise.status_code == 200
        body = noise.json()
        assert body["peaks"][0]["frequency_hz"] == 512.0
        assert body["nyquist_hz"] == 2048.0

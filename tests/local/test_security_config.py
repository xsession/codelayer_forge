import os

import pytest
from fastapi.testclient import TestClient

from embeddyn.local.api import create_app
from embeddyn.local.config import LocalConfig


def test_remote_bind_requires_explicit_opt_in(tmp_path, monkeypatch):
    for name in ("EMBEDDYN_STUDIO_TOKEN", "VSD_STUDIO_TOKEN", "EMBEDDYN_STUDIO_HOST", "VSD_STUDIO_HOST"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="--allow-remote"):
        LocalConfig.from_env(data_dir=tmp_path / "data", workspace=tmp_path, host="0.0.0.0")



def test_programmatic_remote_config_requires_token(tmp_path):
    with pytest.raises(ValueError, match="non-empty API token"):
        LocalConfig(
            data_dir=tmp_path / "data",
            workspace=tmp_path / "workspace",
            host="0.0.0.0",
            allow_remote=True,
        )


def test_programmatic_non_loopback_config_requires_remote_opt_in(tmp_path):
    with pytest.raises(ValueError, match="--allow-remote"):
        LocalConfig(
            data_dir=tmp_path / "data",
            workspace=tmp_path / "workspace",
            host="0.0.0.0",
        )

def test_empty_remote_token_file_is_regenerated(tmp_path, monkeypatch):
    for name in ("EMBEDDYN_STUDIO_TOKEN", "VSD_STUDIO_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    token_path = data_dir / "studio.token"
    token_path.write_text("\n", encoding="utf-8")
    config = LocalConfig.from_env(
        data_dir=data_dir,
        workspace=tmp_path,
        host="0.0.0.0",
        allow_remote=True,
    )
    assert config.api_token
    assert token_path.read_text(encoding="utf-8").strip() == config.api_token
    if os.name != "nt":
        assert token_path.stat().st_mode & 0o077 == 0


def test_remote_mode_protects_data_bearing_get_routes(tmp_path):
    config = LocalConfig(
        data_dir=tmp_path / "data",
        workspace=tmp_path / "workspace",
        host="0.0.0.0",
        api_token="top-secret-token",
        allow_remote=True,
    )
    with TestClient(create_app(config)) as client:
        unauthenticated_health = client.get("/api/health")
        assert unauthenticated_health.status_code == 200
        assert unauthenticated_health.json()["authenticated"] is False
        assert "data_dir" not in unauthenticated_health.json()
        assert client.get("/api/assets").status_code == 401
        assert client.get("/api/projects").status_code == 401
        assert client.get("/api/logs").status_code == 401

        headers = {"Authorization": "Bearer top-secret-token"}
        authenticated_health = client.get("/api/health", headers=headers)
        assert authenticated_health.json()["authenticated"] is True
        assert "data_dir" in authenticated_health.json()
        assert client.get("/api/assets", headers=headers).status_code == 200
        assert client.get("/api/projects", headers=headers).status_code == 200

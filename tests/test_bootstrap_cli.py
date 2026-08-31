from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "bootstrap.py"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.strip()


def _fixture_manifest(tmp_path: Path) -> tuple[Path, str]:
    seed = tmp_path / "seed"
    seed.mkdir()
    subprocess.run(["git", "init", str(seed)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    _git(seed, "config", "user.email", "bootstrap-tests@example.invalid")
    _git(seed, "config", "user.name", "Bootstrap tests")
    _git(seed, "checkout", "-b", "main")
    (seed / "hello.txt").write_text("hello\n", encoding="utf-8")
    _git(seed, "add", "hello.txt")
    _git(seed, "commit", "-m", "initial")
    commit = _git(seed, "rev-parse", "HEAD")

    remote = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "--bare", str(seed), str(remote)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    root = tmp_path / "workspace"
    root.mkdir()
    manifest = {
        "manifest": {
            "version": 1,
            "profiles": {"full": {"groups": ["core"], "python_extras": []}},
            "projects": [
                {
                    "name": "fixture",
                    "path": "deps/fixture",
                    "url": str(remote),
                    "revision": "main",
                    "groups": ["core"],
                }
            ],
        }
    }
    path = root / "embeddyn.yml"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, commit


def test_cli_sync_then_status_uses_generated_lock(tmp_path: Path) -> None:
    manifest, commit = _fixture_manifest(tmp_path)
    sync = subprocess.run(
        [sys.executable, str(BOOTSTRAP), "sync", "--manifest", str(manifest), "--profile", "full"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert sync.returncode == 0, sync.stderr
    assert commit[:12] in sync.stdout
    assert (manifest.parent / "embeddyn.lock.json").is_file()

    status = subprocess.run(
        [sys.executable, str(BOOTSTRAP), "status", "--manifest", str(manifest), "--profile", "full"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert status.returncode == 0, status.stderr
    assert "locked" in status.stdout


def test_cli_help_exposes_west_style_commands() -> None:
    result = subprocess.run(
        [sys.executable, str(BOOTSTRAP), "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0
    for command in ("sync", "update", "status", "lock", "freeze", "doctor"):
        assert command in result.stdout

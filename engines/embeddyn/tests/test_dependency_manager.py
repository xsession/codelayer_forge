from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from embeddyn.dependency_manager import (
    DependencyError,
    load_lock,
    load_manifest,
    lock_current_projects,
    projects_from_manifest,
    save_lock,
    status_projects,
    sync_projects,
)


def git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return proc.stdout.strip()


def make_remote(tmp_path: Path) -> tuple[Path, Path, str]:
    seed = tmp_path / "seed"
    seed.mkdir()
    subprocess.run(["git", "init", str(seed)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    git(seed, "config", "user.email", "tests@example.invalid")
    git(seed, "config", "user.name", "Embeddyn tests")
    git(seed, "checkout", "-b", "main")
    (seed / "version.txt").write_text("one\n", encoding="utf-8")
    git(seed, "add", "version.txt")
    git(seed, "commit", "-m", "v1")
    first = git(seed, "rev-parse", "HEAD")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "--bare", str(seed), str(remote)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    git(seed, "remote", "add", "origin", str(remote))
    return seed, remote, first


def advance_remote(seed: Path, text: str) -> str:
    (seed / "version.txt").write_text(text + "\n", encoding="utf-8")
    git(seed, "add", "version.txt")
    git(seed, "commit", "-m", text)
    git(seed, "push", "origin", "main")
    return git(seed, "rev-parse", "HEAD")


def write_manifest(root: Path, remote: Path, *, path: str = "deps/demo") -> Path:
    manifest = {
        "manifest": {
            "version": 1,
            "profiles": {"full": {"groups": ["core"], "python_extras": []}},
            "projects": [
                {
                    "name": "demo",
                    "path": path,
                    "url": str(remote),
                    "revision": "main",
                    "groups": ["core"],
                }
            ],
        }
    }
    target = root / "embeddyn.yml"
    target.write_text(json.dumps(manifest), encoding="utf-8")
    return target


def test_sync_uses_frozen_commit_until_explicit_update(tmp_path: Path) -> None:
    seed, remote, first = make_remote(tmp_path)
    root = tmp_path / "workspace"
    root.mkdir()
    manifest_path = write_manifest(root, remote)
    data = load_manifest(manifest_path)
    projects = projects_from_manifest(data, root=root, profile="full")
    lock_path = root / "embeddyn.lock.json"
    lock = load_lock(lock_path)

    lock, rows = sync_projects(projects, root=root, lock_data=lock)
    save_lock(lock, lock_path)
    assert rows[0].current == first
    assert lock["lock"]["projects"]["demo"]["commit"] == first

    second = advance_remote(seed, "two")
    assert second != first

    frozen = load_lock(lock_path)
    frozen, rows = sync_projects(projects, root=root, lock_data=frozen)
    assert rows[0].current == first
    assert git(root / "deps/demo", "rev-parse", "HEAD") == first

    updated = load_lock(lock_path)
    updated, rows = sync_projects(projects, root=root, lock_data=updated, update=True)
    assert rows[0].current == second
    assert updated["lock"]["projects"]["demo"]["commit"] == second


def test_dirty_git_project_is_not_overwritten(tmp_path: Path) -> None:
    _, remote, _ = make_remote(tmp_path)
    root = tmp_path / "workspace"
    root.mkdir()
    data = load_manifest(write_manifest(root, remote))
    projects = projects_from_manifest(data, root=root, profile="full")
    lock, _ = sync_projects(projects, root=root, lock_data={"lock": {"version": 1, "projects": {}}})
    (root / "deps/demo/version.txt").write_text("local edit\n", encoding="utf-8")

    with pytest.raises(DependencyError, match="dirty"):
        sync_projects(projects, root=root, lock_data=lock)


def test_bundled_tree_is_content_locked_and_drift_detected(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    remote = tmp_path / "not-used.git"
    data = load_manifest(write_manifest(root, remote))
    projects = projects_from_manifest(data, root=root, profile="full")
    bundled = root / "deps/demo"
    bundled.mkdir(parents=True)
    (bundled / "source.c").write_text("int value = 1;\n", encoding="utf-8")

    lock = {"lock": {"version": 1, "projects": {}}}
    lock_current_projects(projects, lock_data=lock)
    locked = status_projects(projects, root=root, lock_data=lock)
    assert locked[0].state == "locked"
    assert "tree_sha256" in lock["lock"]["projects"]["demo"]

    (bundled / "source.c").write_text("int value = 2;\n", encoding="utf-8")
    drifted = status_projects(projects, root=root, lock_data=lock)
    assert drifted[0].state == "drift"
    with pytest.raises(DependencyError, match="differs from lock"):
        sync_projects(projects, root=root, lock_data=lock)


def test_manifest_rejects_path_escape(tmp_path: Path) -> None:
    manifest_path = write_manifest(tmp_path, tmp_path / "remote.git", path="../outside")
    with pytest.raises(DependencyError, match="inside the repository|escapes repository"):
        load_manifest(manifest_path)


def test_lock_url_change_requires_explicit_update(tmp_path: Path) -> None:
    _, remote, _ = make_remote(tmp_path)
    root = tmp_path / "workspace"
    root.mkdir()
    data = load_manifest(write_manifest(root, remote))
    projects = projects_from_manifest(data, root=root, profile="full")
    lock, _ = sync_projects(projects, root=root, lock_data={"lock": {"version": 1, "projects": {}}})
    lock["lock"]["projects"]["demo"]["url"] = str(tmp_path / "other.git")

    with pytest.raises(DependencyError, match="lock URL"):
        sync_projects(projects, root=root, lock_data=lock)

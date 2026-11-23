"""Embeddyn source dependency manifest and lock handling.

This module intentionally depends only on the Python standard library so it can
be used by ``bootstrap.py`` before Embeddyn itself (or PyYAML) is installed.
The manifest file is JSON syntax stored as ``embeddyn.yml``. JSON is valid YAML
1.2, so it remains consumable by YAML tooling while keeping bootstrap zero-dep.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


MANIFEST_SCHEMA = 1
LOCK_SCHEMA = 1
DEFAULT_MANIFEST = "embeddyn.yml"
DEFAULT_LOCK = "embeddyn.lock.json"


class DependencyError(RuntimeError):
    """Raised when dependency state is invalid or cannot be synchronized."""


@dataclass(frozen=True)
class Project:
    name: str
    path: Path
    url: str
    revision: str
    groups: tuple[str, ...]
    submodule: bool = False
    recursive: bool = False


@dataclass(frozen=True)
class ProjectStatus:
    name: str
    path: Path
    state: str
    current: str | None
    expected: str | None
    dirty: bool = False
    detail: str = ""


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DependencyError(f"Manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DependencyError(f"Invalid JSON/YAML-compatible manifest {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise DependencyError(f"Manifest root must be an object: {path}")
    return data


def load_manifest(path: Path | str | None = None) -> dict[str, Any]:
    manifest_path = Path(path) if path else repository_root() / DEFAULT_MANIFEST
    data = _load_json(manifest_path)
    manifest = data.get("manifest")
    if not isinstance(manifest, dict):
        raise DependencyError("Manifest must contain a top-level 'manifest' object")
    if manifest.get("version") != MANIFEST_SCHEMA:
        raise DependencyError(
            f"Unsupported manifest schema {manifest.get('version')!r}; expected {MANIFEST_SCHEMA}"
        )
    validate_manifest(manifest, manifest_path.parent.resolve())
    return data


def validate_manifest(manifest: Mapping[str, Any], root: Path) -> None:
    projects = manifest.get("projects", [])
    if not isinstance(projects, list):
        raise DependencyError("manifest.projects must be a list")
    names: set[str] = set()
    paths: set[Path] = set()
    for raw in projects:
        if not isinstance(raw, dict):
            raise DependencyError("Each project entry must be an object")
        for required in ("name", "path", "url", "revision"):
            if not isinstance(raw.get(required), str) or not raw[required].strip():
                raise DependencyError(f"Project requires a non-empty '{required}' field: {raw!r}")
        name = raw["name"]
        if name in names:
            raise DependencyError(f"Duplicate project name: {name}")
        names.add(name)
        rel = Path(raw["path"])
        if rel.is_absolute() or ".." in rel.parts:
            raise DependencyError(f"Project path must stay inside the repository: {raw['path']}")
        resolved = (root / rel).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise DependencyError(f"Project path escapes repository: {raw['path']}") from exc
        if resolved in paths:
            raise DependencyError(f"Duplicate project path: {raw['path']}")
        paths.add(resolved)
        groups = raw.get("groups", [])
        if not isinstance(groups, list) or not all(isinstance(g, str) and g for g in groups):
            raise DependencyError(f"Project groups must be a string list: {name}")

    profiles = manifest.get("profiles", {})
    if not isinstance(profiles, dict):
        raise DependencyError("manifest.profiles must be an object")
    for profile_name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise DependencyError(f"Profile {profile_name!r} must be an object")
        for field in ("groups", "python_extras"):
            value = profile.get(field, [])
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise DependencyError(f"Profile {profile_name}.{field} must be a string list")


def manifest_root(manifest_path: Path | str | None = None) -> Path:
    return (Path(manifest_path) if manifest_path else repository_root() / DEFAULT_MANIFEST).resolve().parent


def projects_from_manifest(
    data: Mapping[str, Any],
    *,
    root: Path,
    profile: str | None = None,
    names: Sequence[str] | None = None,
) -> list[Project]:
    manifest = data["manifest"]
    profile_groups: set[str] | None = None
    if profile:
        profiles = manifest.get("profiles", {})
        if profile not in profiles:
            raise DependencyError(
                f"Unknown profile {profile!r}. Available: {', '.join(sorted(profiles)) or '(none)'}"
            )
        profile_groups = set(profiles[profile].get("groups", []))
    selected_names = set(names or [])
    result: list[Project] = []
    known_names: set[str] = set()
    for raw in manifest.get("projects", []):
        known_names.add(raw["name"])
        groups = tuple(raw.get("groups", []))
        if selected_names and raw["name"] not in selected_names:
            continue
        if profile_groups is not None and groups and not profile_groups.intersection(groups):
            continue
        result.append(
            Project(
                name=raw["name"],
                path=(root / raw["path"]).resolve(),
                url=raw["url"],
                revision=raw["revision"],
                groups=groups,
                submodule=bool(raw.get("submodule", False)),
                recursive=bool(raw.get("recursive", False)),
            )
        )
    unknown = selected_names - known_names
    if unknown:
        raise DependencyError(f"Unknown project(s): {', '.join(sorted(unknown))}")
    return result


def load_lock(path: Path | str) -> dict[str, Any]:
    lock_path = Path(path)
    if not lock_path.exists():
        return {"lock": {"version": LOCK_SCHEMA, "projects": {}}}
    data = _load_json(lock_path)
    lock = data.get("lock")
    if not isinstance(lock, dict) or lock.get("version") != LOCK_SCHEMA:
        raise DependencyError(f"Unsupported or malformed lock file: {lock_path}")
    if not isinstance(lock.get("projects", {}), dict):
        raise DependencyError(f"lock.projects must be an object: {lock_path}")
    return data


def save_lock(data: Mapping[str, Any], path: Path | str) -> None:
    path = Path(path)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run(
    args: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path | None = None,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [str(a) for a in args],
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=False,
    )
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise DependencyError(f"Command failed ({proc.returncode}): {' '.join(map(str, args))}\n{detail}")
    return proc


def _git(repo: Path, *args: str, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(("git", "-C", repo, *args), capture=capture, check=check)


def is_git_repo(path: Path) -> bool:
    if not path.exists():
        return False
    proc = _git(path, "rev-parse", "--is-inside-work-tree", capture=True, check=False)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def git_head(path: Path) -> str | None:
    if not is_git_repo(path):
        return None
    proc = _git(path, "rev-parse", "HEAD", capture=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None


def git_dirty(path: Path) -> bool:
    if not is_git_repo(path):
        return False
    proc = _git(path, "status", "--porcelain", "--untracked-files=all", capture=True)
    return bool(proc.stdout.strip())


def _git_origin(path: Path) -> str | None:
    if not is_git_repo(path):
        return None
    proc = _git(path, "remote", "get-url", "origin", capture=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None


def _normalize_git_url(url: str) -> str:
    value = url.rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    return value


def _verify_origin(project: Project) -> None:
    origin = _git_origin(project.path)
    if origin and _normalize_git_url(origin) != _normalize_git_url(project.url):
        raise DependencyError(
            f"{project.name}: origin mismatch. Expected {project.url!r}, found {origin!r}"
        )


def tree_digest(path: Path) -> str:
    """Return a deterministic digest of a source tree, excluding VCS/runtime noise."""
    if not path.is_dir():
        raise DependencyError(f"Cannot fingerprint missing directory: {path}")
    ignored_dirs = {".git", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache"}
    ignored_suffixes = {".pyc", ".pyo"}
    digest = hashlib.sha256()
    root = path.resolve()
    files: list[Path] = []
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in ignored_dirs)
        base = Path(current)
        for filename in sorted(filenames):
            file_path = base / filename
            if file_path.suffix in ignored_suffixes:
                continue
            files.append(file_path)
    for file_path in sorted(files, key=lambda p: p.relative_to(root).as_posix()):
        rel = file_path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(rel).to_bytes(8, "big"))
        digest.update(rel)
        try:
            metadata = file_path.lstat()
            mode = stat.S_IMODE(metadata.st_mode)
            if file_path.is_symlink():
                kind = b"L"
                content = os.readlink(file_path).encode("utf-8", errors="surrogateescape")
            else:
                kind = b"F"
                content = file_path.read_bytes()
        except OSError as exc:
            raise DependencyError(f"Cannot fingerprint {file_path}: {exc}") from exc
        digest.update(kind)
        digest.update(mode.to_bytes(4, "big"))
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _submodule_available(root: Path, project: Project) -> bool:
    if not project.submodule or not is_git_repo(root):
        return False
    rel = project.path.relative_to(root).as_posix()
    proc = _run(
        ("git", "-C", root, "config", "--file", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$"),
        capture=True,
        check=False,
    )
    if proc.returncode != 0:
        return False
    return any(line.split(maxsplit=1)[-1].strip() == rel for line in proc.stdout.splitlines() if line.strip())


def _sync_submodule(root: Path, project: Project, *, force: bool) -> str:
    if project.path.exists() and is_git_repo(project.path) and git_dirty(project.path) and not force:
        raise DependencyError(f"{project.name}: working tree is dirty; commit/stash changes or use --force")
    rel = project.path.relative_to(root).as_posix()
    args = ["git", "-C", str(root), "submodule", "update", "--init", "--recursive"]
    if force:
        args.append("--force")
    args.extend(("--", rel))
    _run(args)
    head = git_head(project.path)
    if not head:
        raise DependencyError(f"{project.name}: submodule checkout did not produce a Git repository")
    return head


def _clone(project: Project) -> None:
    project.path.parent.mkdir(parents=True, exist_ok=True)
    _run(("git", "clone", "--no-checkout", project.url, project.path))


def _resolve_and_checkout(project: Project, revision: str, *, force: bool) -> str:
    fresh_clone = not project.path.exists()
    if fresh_clone:
        _clone(project)
    if not is_git_repo(project.path):
        raise DependencyError(f"{project.name}: path exists but is not a Git repository: {project.path}")
    _verify_origin(project)
    # A --no-checkout clone intentionally has every indexed file absent from the
    # worktree, which Git reports as dirty until the first checkout.
    if not fresh_clone and git_dirty(project.path) and not force:
        raise DependencyError(f"{project.name}: working tree is dirty; commit/stash changes or use --force")
    # Fetch exactly the manifest/lock revision. Depth 1 keeps bootstrap lightweight.
    fetch = _git(project.path, "fetch", "--depth", "1", "origin", revision, capture=True, check=False)
    if fetch.returncode != 0:
        # Some servers do not allow fetching an unadvertised SHA. Fall back to a
        # normal fetch so an already-published lock commit can still be resolved.
        _git(project.path, "fetch", "origin")
        proc = _git(project.path, "rev-parse", f"{revision}^{{commit}}", capture=True, check=False)
        if proc.returncode != 0:
            proc = _git(project.path, "rev-parse", f"origin/{revision}^{{commit}}", capture=True, check=False)
        if proc.returncode != 0:
            raise DependencyError(f"{project.name}: cannot resolve revision {revision!r}")
        commit = proc.stdout.strip()
    else:
        commit = _git(project.path, "rev-parse", "FETCH_HEAD^{commit}", capture=True).stdout.strip()
    checkout_args = ["checkout", "--detach"]
    if force:
        checkout_args.append("--force")
    checkout_args.append(commit)
    _git(project.path, *checkout_args)
    if project.recursive:
        _git(project.path, "submodule", "sync", "--recursive")
        _git(project.path, "submodule", "update", "--init", "--recursive")
    return commit


def _lock_entry(lock_data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    lock = lock_data.get("lock", {})
    projects = lock.get("projects", {}) if isinstance(lock, Mapping) else {}
    entry = projects.get(name, {}) if isinstance(projects, Mapping) else {}
    return entry if isinstance(entry, Mapping) else {}


def sync_projects(
    projects: Iterable[Project],
    *,
    root: Path,
    lock_data: dict[str, Any],
    use_lock: bool = True,
    update: bool = False,
    force: bool = False,
    allow_bundled: bool = True,
) -> tuple[dict[str, Any], list[ProjectStatus]]:
    """Synchronize projects and return updated lock data plus statuses.

    Normal sync uses an exact lock commit when available. Update deliberately
    resolves the manifest revision and rewrites the lock, equivalent to moving
    a west manifest project revision and then freezing it.
    """
    lock = lock_data.setdefault("lock", {"version": LOCK_SCHEMA, "projects": {}})
    lock.setdefault("version", LOCK_SCHEMA)
    lock_projects = lock.setdefault("projects", {})
    statuses: list[ProjectStatus] = []

    for project in projects:
        entry = _lock_entry(lock_data, project.name)
        if entry and use_lock and not update and entry.get("url") not in (None, project.url):
            raise DependencyError(
                f"{project.name}: lock URL {entry.get('url')!r} differs from manifest URL {project.url!r}; "
                "run update after reviewing the manifest change"
            )
        expected_commit = entry.get("commit") if use_lock and not update else None
        expected_digest = entry.get("tree_sha256") if use_lock and not update else None

        if _submodule_available(root, project):
            # Initialize from the superproject gitlink first. Once a project has
            # an Embeddyn lock commit, that lock becomes authoritative. `update`
            # deliberately advances to the manifest ref and leaves the parent
            # gitlink modified so the dependency bump can be reviewed/committed.
            if not project.path.exists() or not is_git_repo(project.path):
                _sync_submodule(root, project, force=force)
            if update:
                commit = _resolve_and_checkout(project, project.revision, force=force)
            elif expected_commit:
                commit = _resolve_and_checkout(project, str(expected_commit), force=force)
            else:
                commit = _sync_submodule(root, project, force=force)
            lock_projects[project.name] = {
                "url": project.url,
                "revision": project.revision,
                "commit": commit,
                "source": "submodule",
            }
            statuses.append(ProjectStatus(project.name, project.path, "synced", commit, commit))
            continue

        if project.path.exists() and not is_git_repo(project.path):
            if not allow_bundled:
                raise DependencyError(
                    f"{project.name}: {project.path} is bundled/non-Git; use --allow-bundled or --adopt"
                )
            current_digest = tree_digest(project.path)
            if expected_digest and current_digest != expected_digest and not force:
                raise DependencyError(
                    f"{project.name}: bundled tree differs from lock ({current_digest[:12]} != {expected_digest[:12]})"
                )
            lock_projects[project.name] = {
                "url": project.url,
                "revision": project.revision,
                "tree_sha256": current_digest,
                "source": "bundled",
            }
            statuses.append(
                ProjectStatus(
                    project.name,
                    project.path,
                    "bundled",
                    current_digest,
                    expected_digest or current_digest,
                    detail="non-Git source archive; protected by content fingerprint",
                )
            )
            continue

        target_revision = str(expected_commit or project.revision)
        commit = _resolve_and_checkout(project, target_revision, force=force)
        lock_projects[project.name] = {
            "url": project.url,
            "revision": project.revision,
            "commit": commit,
            "source": "git",
        }
        statuses.append(ProjectStatus(project.name, project.path, "synced", commit, commit))

    return lock_data, statuses


def status_projects(
    projects: Iterable[Project],
    *,
    root: Path,
    lock_data: Mapping[str, Any],
) -> list[ProjectStatus]:
    statuses: list[ProjectStatus] = []
    for project in projects:
        entry = _lock_entry(lock_data, project.name)
        expected = entry.get("commit") or entry.get("tree_sha256")
        if not project.path.exists():
            statuses.append(ProjectStatus(project.name, project.path, "missing", None, expected))
            continue
        if is_git_repo(project.path):
            head = git_head(project.path)
            dirty = git_dirty(project.path)
            state = "dirty" if dirty else ("locked" if expected and head == expected else "drift")
            if not expected and not dirty:
                state = "unlocked"
            statuses.append(ProjectStatus(project.name, project.path, state, head, expected, dirty))
            continue
        digest = tree_digest(project.path)
        state = "locked" if expected and digest == expected else ("unlocked" if not expected else "drift")
        statuses.append(
            ProjectStatus(
                project.name,
                project.path,
                state,
                digest,
                expected,
                detail="bundled/non-Git tree",
            )
        )
    return statuses


def lock_current_projects(
    projects: Iterable[Project],
    *,
    lock_data: dict[str, Any],
) -> dict[str, Any]:
    lock = lock_data.setdefault("lock", {"version": LOCK_SCHEMA, "projects": {}})
    lock.setdefault("version", LOCK_SCHEMA)
    entries = lock.setdefault("projects", {})
    for project in projects:
        if not project.path.exists():
            continue
        if is_git_repo(project.path):
            commit = git_head(project.path)
            if not commit:
                raise DependencyError(f"{project.name}: cannot determine Git HEAD")
            entries[project.name] = {
                "url": project.url,
                "revision": project.revision,
                "commit": commit,
                "source": "submodule" if project.submodule else "git",
            }
        else:
            entries[project.name] = {
                "url": project.url,
                "revision": project.revision,
                "tree_sha256": tree_digest(project.path),
                "source": "bundled",
            }
    return lock_data


def adopt_project(project: Project, *, backup: bool = True) -> None:
    """Replace a bundled dependency with a managed Git checkout location."""
    if not project.path.exists() or is_git_repo(project.path):
        return
    if backup:
        candidate = project.path.with_name(project.path.name + ".bundled-backup")
        index = 1
        while candidate.exists():
            candidate = project.path.with_name(project.path.name + f".bundled-backup-{index}")
            index += 1
        project.path.rename(candidate)
    else:
        shutil.rmtree(project.path)

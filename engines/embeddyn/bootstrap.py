#!/usr/bin/env python3
"""Embeddyn zero-dependency bootstrap and dependency workspace manager.

The workflow deliberately mirrors Zephyr/west concepts:

* ``embeddyn.yml`` is the editable manifest (allowed/updatable revisions).
* ``embeddyn.lock.json`` is the frozen manifest (exact commits/fingerprints).
* ``sync`` materializes the lock, like ``west update``.
* ``update`` advances projects to manifest revisions and rewrites the lock.
* ``status`` reports local drift/dirty repositories.
* ``lock``/``freeze`` capture a known-good source and Python environment.

The script itself only uses the Python standard library and can run before the
Embeddyn package is installed.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embeddyn.dependency_manager import (  # noqa: E402
    DEFAULT_LOCK,
    DEFAULT_MANIFEST,
    DependencyError,
    Project,
    adopt_project,
    load_lock,
    load_manifest,
    lock_current_projects,
    manifest_root,
    projects_from_manifest,
    save_lock,
    status_projects,
    sync_projects,
)

BOOTSTRAP_VERSION = "1.0.0"


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def run(
    args: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    pretty = " ".join(shlex.quote(str(item)) for item in args)
    print(f"+ {pretty}")
    proc = subprocess.run(
        [str(item) for item in args],
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=False,
    )
    if check and proc.returncode:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise DependencyError(f"Command failed ({proc.returncode}): {pretty}\n{detail}")
    return proc


def read_context(args: argparse.Namespace):
    manifest_path = Path(args.manifest).resolve()
    root = manifest_root(manifest_path)
    data = load_manifest(manifest_path)
    lock_path = (root / args.lock).resolve() if not Path(args.lock).is_absolute() else Path(args.lock)
    lock_data = load_lock(lock_path)
    return root, data, lock_path, lock_data


def selected_projects(args: argparse.Namespace, root: Path, data: dict) -> list[Project]:
    names = list(getattr(args, "projects", []) or [])
    return projects_from_manifest(
        data,
        root=root,
        profile=getattr(args, "profile", None) if not names else None,
        names=names or None,
    )


def short(value: str | None) -> str:
    if not value:
        return "-"
    return value if len(value) <= 14 else value[:12]


def print_status(rows) -> None:
    headers = ("PROJECT", "STATE", "CURRENT", "EXPECTED", "PATH")
    materialized = [
        (row.name, row.state, short(row.current), short(row.expected), str(row.path)) for row in rows
    ]
    widths = [len(value) for value in headers]
    for row in materialized:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))
    print("  ".join(value.ljust(widths[idx]) for idx, value in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in materialized:
        print("  ".join(value.ljust(widths[idx]) for idx, value in enumerate(row)))


def cmd_list(args: argparse.Namespace) -> int:
    root, data, _, _ = read_context(args)
    projects = selected_projects(args, root, data)
    manifest = data["manifest"]
    print(f"Manifest: {Path(args.manifest).resolve()}")
    print(f"Schema:   {manifest['version']}  bootstrap: {manifest.get('bootstrap_version', '-')}")
    print("NAME                    REVISION       GROUPS          PATH")
    print("----------------------  -------------  --------------  ----")
    for project in projects:
        groups = ",".join(project.groups) or "-"
        rel = project.path.relative_to(root)
        print(f"{project.name:<22}  {project.revision:<13}  {groups:<14}  {rel}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root, data, _, lock_data = read_context(args)
    projects = selected_projects(args, root, data)
    rows = status_projects(projects, root=root, lock_data=lock_data)
    print_status(rows)
    bad = {"missing", "dirty", "drift"}
    return 1 if any(row.state in bad for row in rows) and not args.allow_drift else 0


def _maybe_adopt(projects: Iterable[Project], *, adopt: bool, discard: bool) -> None:
    if not adopt:
        return
    for project in projects:
        if project.path.exists():
            adopt_project(project, backup=not discard)


def _sync(args: argparse.Namespace, *, update: bool) -> int:
    root, data, lock_path, lock_data = read_context(args)
    projects = selected_projects(args, root, data)
    _maybe_adopt(projects, adopt=args.adopt, discard=args.discard_bundled)
    lock_data, rows = sync_projects(
        projects,
        root=root,
        lock_data=lock_data,
        use_lock=not args.no_lock,
        update=update,
        force=args.force,
        allow_bundled=not args.reject_bundled,
    )
    save_lock(lock_data, lock_path)
    print_status(rows)
    print(f"Lock file: {lock_path}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    return _sync(args, update=False)


def cmd_update(args: argparse.Namespace) -> int:
    return _sync(args, update=True)


def cmd_lock(args: argparse.Namespace) -> int:
    root, data, lock_path, lock_data = read_context(args)
    projects = selected_projects(args, root, data)
    lock_current_projects(projects, lock_data=lock_data)
    save_lock(lock_data, lock_path)
    print(f"Wrote source lock: {lock_path}")
    rows = status_projects(projects, root=root, lock_data=lock_data)
    print_status(rows)
    return 0


def _python_version_tuple(text: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in text.split("."))
    except ValueError as exc:
        raise DependencyError(f"Invalid Python version in manifest: {text!r}") from exc


def _profile(data: dict, profile: str) -> dict:
    profiles = data["manifest"].get("profiles", {})
    if profile not in profiles:
        raise DependencyError(f"Unknown profile {profile!r}; available: {', '.join(sorted(profiles))}")
    return profiles[profile]


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def ensure_venv(root: Path, data: dict, *, recreate: bool) -> tuple[Path, Path]:
    py_cfg = data["manifest"].get("python", {})
    minimum = _python_version_tuple(str(py_cfg.get("minimum", "3.9")))
    if sys.version_info[: len(minimum)] < minimum:
        raise DependencyError(
            f"Python {'.'.join(map(str, minimum))}+ is required; running {platform.python_version()}"
        )
    venv_dir = (root / py_cfg.get("venv", ".venv")).resolve()
    if recreate and venv_dir.exists():
        print(f"Removing virtual environment: {venv_dir}")
        shutil.rmtree(venv_dir)
    python = venv_python(venv_dir)
    if not python.exists():
        print(f"Creating virtual environment: {venv_dir}")
        venv.EnvBuilder(with_pip=True, clear=False).create(venv_dir)
    if not python.exists():
        raise DependencyError(f"Virtual environment Python was not created: {python}")
    return venv_dir, python


def install_python_dependencies(
    root: Path,
    data: dict,
    profile: str,
    *,
    recreate: bool,
    locked: bool,
    no_python: bool,
) -> tuple[Path | None, Path | None]:
    if no_python:
        return None, None
    venv_dir, python = ensure_venv(root, data, recreate=recreate)
    extras = _profile(data, profile).get("python_extras", [])
    py_cfg = data["manifest"].get("python", {})
    lock_file = (root / py_cfg.get("lock_file", "requirements.lock.txt")).resolve()
    if locked and not lock_file.exists():
        raise DependencyError(
            f"--locked requested but Python lock file does not exist: {lock_file}. "
            "Run 'python bootstrap.py freeze --profile dev' after creating a known-good environment."
        )
    run((python, "-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "pip", "setuptools", "wheel"))
    if lock_file.exists():
        print(f"Installing frozen Python dependencies from {lock_file.name}")
        run((python, "-m", "pip", "install", "--disable-pip-version-check", "-r", lock_file), cwd=root)
        editable = ".[{}]".format(",".join(extras)) if extras else "."
        run((python, "-m", "pip", "install", "--disable-pip-version-check", "--no-deps", "-e", editable), cwd=root)
    else:
        editable = ".[{}]".format(",".join(extras)) if extras else "."
        run((python, "-m", "pip", "install", "--disable-pip-version-check", "-e", editable), cwd=root)
    # Catch incomplete/stale lock files and mutually incompatible transitive
    # resolutions immediately instead of failing much later during a build.
    run((python, "-m", "pip", "check"), cwd=root)
    return venv_dir, python


def required_commands(data: dict) -> list[str]:
    return list(data["manifest"].get("system", {}).get("required_commands", []))


def missing_commands(data: dict) -> list[str]:
    return [command for command in required_commands(data) if shutil.which(command) is None]


def _debian_like() -> bool:
    if sys.platform != "linux":
        return False
    try:
        content = Path("/etc/os-release").read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return any(token in content for token in ("id=debian", "id=ubuntu", "debian", "ubuntu"))


def install_system_dependencies(data: dict, *, yes: bool) -> None:
    missing = missing_commands(data)
    if not missing:
        print("System prerequisites: OK")
        return
    print("Missing system commands: " + ", ".join(missing))
    if not yes:
        packages = data["manifest"].get("system", {}).get("debian_packages", [])
        if _debian_like() and packages:
            print("Install on Debian/Ubuntu with:")
            print("  sudo apt-get update && sudo apt-get install -y " + " ".join(packages))
        else:
            print("Automatic system-package installation is currently supported on Debian/Ubuntu.")
        return
    if not _debian_like():
        raise DependencyError(
            "--install-system currently supports Debian/Ubuntu only. "
            "Install the commands reported by 'doctor' with your platform package manager."
        )
    packages = data["manifest"].get("system", {}).get("debian_packages", [])
    if not packages:
        raise DependencyError("No Debian package list is present in the manifest")
    prefix: list[str] = [] if os.geteuid() == 0 else ["sudo"]
    run((*prefix, "apt-get", "update"))
    run((*prefix, "apt-get", "install", "-y", *packages))
    remaining = missing_commands(data)
    if remaining:
        raise DependencyError("System package install completed but commands are still missing: " + ", ".join(remaining))


def cmd_doctor(args: argparse.Namespace) -> int:
    root, data, lock_path, lock_data = read_context(args)
    print(f"Embeddyn bootstrap {BOOTSTRAP_VERSION}")
    print(f"Platform: {platform.platform()}")
    print(f"Python:   {platform.python_version()} ({sys.executable})")
    print(f"Manifest: {Path(args.manifest).resolve()}")
    print(f"Lock:     {lock_path} ({'present' if lock_path.exists() else 'not generated yet'})")
    missing = missing_commands(data)
    print("System prerequisites:")
    for command in required_commands(data):
        found = shutil.which(command)
        print(f"  {'OK' if found else 'MISSING':7} {command:<10} {found or ''}")
    projects = selected_projects(args, root, data)
    print("Source dependencies:")
    print_status(status_projects(projects, root=root, lock_data=lock_data))
    if missing:
        install_system_dependencies(data, yes=False)
    return 1 if missing and not args.allow_missing else 0


def cmd_system_deps(args: argparse.Namespace) -> int:
    _, data, _, _ = read_context(args)
    install_system_dependencies(data, yes=args.install)
    return 0


def _write_environment_helpers(root: Path, data: dict, venv_dir: Path | None) -> None:
    state_dir = root / ".embeddyn"
    state_dir.mkdir(parents=True, exist_ok=True)
    workspace = (root / data["manifest"].get("workspace", {}).get("path", "workspace")).resolve()
    venv_dir = venv_dir or (root / data["manifest"].get("python", {}).get("venv", ".venv")).resolve()
    sh_activate = venv_dir / "bin" / "activate"
    ps_activate = venv_dir / "Scripts" / "Activate.ps1"
    cmd_activate = venv_dir / "Scripts" / "activate.bat"
    (state_dir / "env.sh").write_text(
        "#!/usr/bin/env sh\n"
        f"export EMBEDDYN_WORKSPACE={shlex.quote(str(workspace))}\n"
        + (f". {shlex.quote(str(sh_activate))}\n" if sh_activate.exists() else ""),
        encoding="utf-8",
    )
    (state_dir / "env.ps1").write_text(
        f"$env:EMBEDDYN_WORKSPACE = {json.dumps(str(workspace))}\n"
        + (f"& {json.dumps(str(ps_activate))}\n" if ps_activate.exists() else ""),
        encoding="utf-8",
    )
    (state_dir / "env.cmd").write_text(
        f"@set \"EMBEDDYN_WORKSPACE={workspace}\"\r\n"
        + (f"@call \"{cmd_activate}\"\r\n" if cmd_activate.exists() else ""),
        encoding="utf-8",
    )


def _workspace_init(root: Path, data: dict, python: Path) -> None:
    cfg = data["manifest"].get("workspace", {})
    workspace = (root / cfg.get("path", "workspace")).resolve()
    env_file = workspace / "embeddyn-env.yml"
    if env_file.exists():
        print(f"Workspace already initialized: {workspace}")
        return
    sdk = str(cfg.get("zephyr_sdk", "0.16.3"))
    run((python, "-m", "embeddyn", "init", workspace, "--zephyr-sdk", sdk), cwd=root)


def cmd_bootstrap(args: argparse.Namespace) -> int:
    root, data, lock_path, lock_data = read_context(args)
    if args.install_system:
        install_system_dependencies(data, yes=True)
    elif not args.skip_doctor:
        missing = missing_commands(data)
        if missing:
            eprint("WARNING: missing system commands: " + ", ".join(missing))
            eprint("         run 'python bootstrap.py system-deps --install' on Debian/Ubuntu")

    venv_dir, python = install_python_dependencies(
        root,
        data,
        args.profile,
        recreate=args.recreate_venv,
        locked=args.locked,
        no_python=args.no_python,
    )

    if not args.no_sync:
        projects = projects_from_manifest(data, root=root, profile=args.profile)
        _maybe_adopt(projects, adopt=args.adopt, discard=args.discard_bundled)
        lock_data, rows = sync_projects(
            projects,
            root=root,
            lock_data=lock_data,
            use_lock=True,
            update=False,
            force=args.force,
            allow_bundled=not args.reject_bundled,
        )
        save_lock(lock_data, lock_path)
        print_status(rows)

    if args.workspace:
        if python is None:
            venv_path = (root / data["manifest"].get("python", {}).get("venv", ".venv")).resolve()
            python = venv_python(venv_path)
            if not python.exists():
                raise DependencyError("--workspace requires an initialized Python environment")
        _workspace_init(root, data, python)

    _write_environment_helpers(root, data, venv_dir)
    print("\nBootstrap complete.")
    if os.name == "nt":
        print(r"Activate with: .\.embeddyn\env.ps1")
    else:
        print("Activate with: . ./.embeddyn/env.sh")
    print("Check state with: python bootstrap.py status --profile " + args.profile)
    return 0


def _freeze_python(root: Path, data: dict) -> Path:
    py_cfg = data["manifest"].get("python", {})
    venv_dir = (root / py_cfg.get("venv", ".venv")).resolve()
    python = venv_python(venv_dir)
    if not python.exists():
        raise DependencyError(f"Virtual environment not found: {venv_dir}")
    proc = run((python, "-m", "pip", "freeze", "--all"), capture=True)
    lines: list[str] = []
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        lower = line.lower()
        if not line or line.startswith("-e ") or lower.startswith("embeddyn @ file:"):
            continue
        if lower.startswith(("pip==", "setuptools==", "wheel==")):
            continue
        lines.append(line)
    lock_file = (root / py_cfg.get("lock_file", "requirements.lock.txt")).resolve()
    header = (
        "# Generated by: python bootstrap.py freeze\n"
        "# Commit this file together with embeddyn.lock.json for reproducible installs.\n"
    )
    lock_file.write_text(header + "\n".join(sorted(lines, key=str.lower)) + "\n", encoding="utf-8")
    return lock_file


def cmd_freeze(args: argparse.Namespace) -> int:
    root, data, lock_path, lock_data = read_context(args)
    projects = selected_projects(args, root, data)
    lock_current_projects(projects, lock_data=lock_data)
    save_lock(lock_data, lock_path)
    print(f"Wrote source lock: {lock_path}")
    if not args.no_python_lock:
        py_lock = _freeze_python(root, data)
        print(f"Wrote Python lock: {py_lock}")
    return 0


def add_common(parser: argparse.ArgumentParser, *, projects: bool = False, profile: bool = True) -> None:
    parser.add_argument("--manifest", default=str(ROOT / DEFAULT_MANIFEST), help="Dependency manifest path")
    parser.add_argument("--lock", default=DEFAULT_LOCK, help="Dependency lock path (relative to manifest root)")
    if profile:
        parser.add_argument("--profile", default="full", help="Manifest profile (core/studio/rf/full/dev)")
    if projects:
        parser.add_argument("projects", nargs="*", help="Specific project names (overrides profile selection)")


def add_sync_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--force", action="store_true", help="Allow forced checkout of dirty Git worktrees")
    parser.add_argument("--no-lock", action="store_true", help="Ignore existing lock revisions and resolve manifest refs")
    parser.add_argument("--reject-bundled", action="store_true", help="Fail instead of accepting non-Git bundled trees")
    parser.add_argument("--adopt", action="store_true", help="Replace bundled trees with managed Git checkouts")
    parser.add_argument(
        "--discard-bundled",
        action="store_true",
        help="With --adopt, delete bundled trees instead of preserving *.bundled-backup",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Embeddyn west-like bootstrap and dependency manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""West-style mapping:
  west update              -> bootstrap.py sync
  advance manifest refs    -> bootstrap.py update
  west list                -> bootstrap.py list
  west status              -> bootstrap.py status
  west manifest --freeze   -> bootstrap.py freeze
""",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {BOOTSTRAP_VERSION}")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("bootstrap", help="Create venv, install Python deps and synchronize source deps")
    add_common(p, profile=True)
    p.add_argument("--workspace", action="store_true", help="Also initialize Zephyr/SDK/Renode workspace")
    p.add_argument("--install-system", action="store_true", help="Install Debian/Ubuntu system packages")
    p.add_argument("--skip-doctor", action="store_true", help="Do not warn about missing system tools")
    p.add_argument("--no-sync", action="store_true", help="Skip source dependency synchronization")
    p.add_argument("--no-python", action="store_true", help="Skip virtualenv/Python dependency installation")
    p.add_argument("--locked", action="store_true", help="Require and use requirements.lock.txt")
    p.add_argument("--recreate-venv", action="store_true", help="Delete and recreate the configured virtualenv")
    add_sync_options(p)
    p.set_defaults(func=cmd_bootstrap)

    p = sub.add_parser("sync", help="Materialize exact locked source revisions")
    add_common(p, projects=True)
    add_sync_options(p)
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("update", help="Advance selected projects to manifest refs and rewrite lock")
    add_common(p, projects=True)
    add_sync_options(p)
    p.set_defaults(func=cmd_update, no_lock=True)

    p = sub.add_parser("status", help="Compare working trees with the frozen lock")
    add_common(p, projects=True)
    p.add_argument("--allow-drift", action="store_true", help="Always return exit status 0")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("list", help="List dependency projects and manifest revisions")
    add_common(p, projects=True)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("lock", help="Freeze current source revisions/content into the source lock")
    add_common(p, projects=True)
    p.set_defaults(func=cmd_lock)

    p = sub.add_parser("freeze", help="Freeze source revisions and installed Python package versions")
    add_common(p, projects=True)
    p.add_argument("--no-python-lock", action="store_true", help="Only write embeddyn.lock.json")
    p.set_defaults(func=cmd_freeze)

    p = sub.add_parser("doctor", help="Check host tools and dependency workspace state")
    add_common(p, projects=True)
    p.add_argument("--allow-missing", action="store_true", help="Always return exit status 0")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("system-deps", help="Show or install host packages required by full Embeddyn")
    add_common(p, profile=False)
    p.add_argument("--install", action="store_true", help="Install packages on Debian/Ubuntu")
    p.set_defaults(func=cmd_system_deps)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not argv:
        argv = ["bootstrap"]
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    if getattr(args, "discard_bundled", False) and not getattr(args, "adopt", False):
        parser.error("--discard-bundled requires --adopt")
    try:
        return int(args.func(args))
    except DependencyError as exc:
        eprint(f"ERROR: {exc}")
        return 2
    except KeyboardInterrupt:
        eprint("Interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

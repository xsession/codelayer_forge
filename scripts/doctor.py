#!/usr/bin/env python3
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def version(command: list[str]) -> str | None:
    if shutil.which(command[0]) is None:
        return None
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=True, timeout=10)
    except (subprocess.SubprocessError, OSError):
        return "present, version unavailable"
    return (result.stdout or result.stderr).splitlines()[0]


def main() -> int:
    checks = {
        "Python": f"{platform.python_implementation()} {platform.python_version()}",
        "Node.js": version(["node", "--version"]),
        "npm": version(["npm", "--version"]),
        "Rust": version(["rustc", "--version"]),
        "Cargo": version(["cargo", "--version"]),
        "Git": version(["git", "--version"]),
        "Docker": version(["docker", "--version"]),
    }
    print("CodeLayer Forge environment doctor")
    print(f"Repository: {ROOT}")
    print(f"Platform:   {platform.platform()}")
    print()
    for name, value in checks.items():
        status = "OK" if value else "OPTIONAL/MISSING"
        print(f"{name:<10} {status:<17} {value or '-'}")
    if sys.version_info < (3, 11):
        print("\nERROR: Python 3.11 or newer is required.")
        return 1
    print("\nCore Python plugin development environment is ready.")
    if checks["Rust"] is None:
        print("Install Rust and Tauri platform prerequisites to build the desktop binary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

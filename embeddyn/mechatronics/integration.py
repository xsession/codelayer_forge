from __future__ import annotations

from pathlib import Path
from typing import Any
import shutil

from .bindings import validate_project_bindings
from .kicad import KiCadBridge
from .model import Domain, MechatronicProject


def validate_integrations(project: MechatronicProject) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    bindings = validate_project_bindings(project)
    checks.append({"name": "bindings", **bindings})
    for domain, config in project.simulators.items():
        if not config.enabled:
            continue
        backend = str(config.options.get("backend", domain.value))
        executable = config.executable or backend
        model = project.resolve(config.model)
        errors: list[str] = []
        warnings: list[str] = []
        if config.model and (model is None or not model.exists()):
            errors.append(f"model does not exist: {model}")
        if backend not in {"mock", "auto"} and shutil.which(executable) is None and not Path(executable).exists():
            warnings.append(f"executable not found in current environment: {executable}")
        check: dict[str, Any] = {"name": domain.value, "backend": backend, "model": str(model) if model else None,
                                 "valid": not errors, "errors": errors, "warnings": warnings}
        if domain is Domain.ELECTRICAL and model and model.exists() and model.suffix.lower() in {".cir", ".sp", ".spice", ".net"}:
            check["spice"] = KiCadBridge().validate_spice_netlist(model)
            check["valid"] = check["valid"] and bool(check["spice"]["valid"])
        checks.append(check)
    errors = [error for check in checks for error in check.get("errors", [])]
    errors.extend(bindings.get("errors", []))
    return {"valid": all(check.get("valid", True) for check in checks) and not errors, "checks": checks, "errors": errors}

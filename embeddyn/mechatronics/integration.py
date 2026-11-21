from __future__ import annotations

from pathlib import Path
from typing import Any
import os
import shutil

from .bindings import validate_project_bindings
from .kicad import KiCadBridge
from .model import Domain, MechatronicProject


def validate_integrations(project: MechatronicProject) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    bindings = validate_project_bindings(project)
    checks.append({"name": "bindings", **bindings})
    for instance_name, config in project.declared_instances().items():
        if not config.enabled:
            continue
        domain = config.domain
        backend = str(config.options.get("backend", domain.value))
        executable = config.executable or backend
        if backend == "renode":
            executable = config.executable or config.options.get("executable") or os.environ.get("RENODE_BIN") or "renode"
        model = project.resolve(config.model)
        errors: list[str] = []
        warnings: list[str] = []
        if backend == "python":
            # model is `module:Class` or `file.py:Class`: check it imports and matches the bindings.
            from .adapters.python_model import PythonModelAdapter
            from .factory import python_model_kwargs
            model = None
            try:
                kwargs = python_model_kwargs(project, config)
                PythonModelAdapter(**kwargs)
                known = set(project.signals) | set(project.parameters)
                for name in [*kwargs["inputs"].values(), *kwargs["outputs"].values()]:
                    if name not in known:
                        errors.append(f"python model maps unknown signal: {name}")
                for key, value in kwargs["parameters"].items():
                    if isinstance(value, str) and value.startswith("@") and value[1:] not in project.parameters:
                        errors.append(f"plant parameter {key} refers to unknown project parameter {value[1:]}")
            except Exception as exc:
                errors.append(f"python model: {exc}")
        elif backend == "fmu":
            from .adapters.fmu import FmuAdapter
            from .factory import fmu_kwargs
            try:
                kwargs = fmu_kwargs(project, config)
                FmuAdapter(**kwargs)
                known = set(project.signals) | set(project.parameters)
                for name in [*kwargs["inputs"].values(), *kwargs["outputs"].values()]:
                    if name not in known:
                        errors.append(f"FMU maps unknown signal: {name}")
            except Exception as exc:
                errors.append(f"fmu: {exc}")
        elif backend == "ngspice-shared":
            from .adapters.ngspice_shared import NgspiceError, find_library
            try:
                find_library(config.options.get("library") or config.executable)
            except NgspiceError as exc:
                warnings.append(str(exc))
        elif config.model and (model is None or not model.exists()):
            errors.append(f"model does not exist: {model}")
        if backend not in {"mock", "auto", "python", "ngspice-shared", "fmu"} and shutil.which(executable) is None and not Path(executable).exists():
            warnings.append(f"executable not found in current environment: {executable}")
        check: dict[str, Any] = {"name": instance_name, "domain": domain.value, "backend": backend, "model": str(model) if model else None,
                                 "valid": not errors, "errors": errors, "warnings": warnings}
        if domain is Domain.FIRMWARE and backend == "renode":
            from .adapters.renode import load_renode_bindings
            from .factory import renode_kwargs

            kwargs = renode_kwargs(project, config)
            if kwargs["launch"] and not (kwargs["script"] and Path(kwargs["script"]).exists()):
                errors.append(f"Renode launch script does not exist: {kwargs['script']}")
            if kwargs["firmware"] and not Path(kwargs["firmware"]).exists():
                warnings.append(f"firmware image not built yet: {kwargs['firmware']}")
            try:
                renode_bindings = load_renode_bindings(kwargs["bindings"], kwargs["machine"], kwargs["inline_bindings"])
                if not renode_bindings:
                    warnings.append("no Renode bindings: firmware will run but exchange no signals")
                unknown = [b.signal for b in renode_bindings
                           if b.signal not in project.signals and b.signal not in project.parameters]
                errors.extend(f"Renode binding for unknown signal or parameter: {name}" for name in unknown)
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
        if domain is Domain.ELECTRICAL and model and model.exists() and model.suffix.lower() in {".cir", ".sp", ".spice", ".net"}:
            check["spice"] = KiCadBridge().validate_spice_netlist(model)
            check["valid"] = check["valid"] and bool(check["spice"]["valid"])
        checks.append(check)
    errors = [error for check in checks for error in check.get("errors", [])]
    errors.extend(bindings.get("errors", []))
    return {"valid": all(check.get("valid", True) for check in checks) and not errors, "checks": checks, "errors": errors}

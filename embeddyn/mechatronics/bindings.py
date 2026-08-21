from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from .model import Domain, MechatronicProject, SignalKind


@dataclass(frozen=True)
class BindingEndpoint:
    adapter: str
    object: str
    property: str
    direction: str
    unit: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SignalBinding:
    signal: str
    endpoint: BindingEndpoint


@dataclass
class BindingManifest:
    bindings: list[SignalBinding]

    @classmethod
    def load(cls, path: Path) -> "BindingManifest":
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        items = []
        for item in raw.get("bindings", []):
            ep = item.get("endpoint") or item.get("target") or item.get("source") or {}
            items.append(SignalBinding(
                signal=str(item["signal"]),
                endpoint=BindingEndpoint(
                    adapter=str(ep.get("adapter", raw.get("adapter", ""))),
                    object=str(ep.get("object", ep.get("node", ep.get("device", ep.get("net", ""))))),
                    property=str(ep.get("property", ep.get("field", ep.get("command", "value")))),
                    direction=str(ep.get("direction", item.get("direction", "input"))),
                    unit=str(ep.get("unit", item.get("unit", ""))),
                    metadata={k: v for k, v in ep.items() if k not in {"adapter", "object", "node", "device", "net", "property", "field", "command", "direction", "unit"}},
                ),
            ))
        return cls(items)

    def validate(self, project: MechatronicProject, adapter: str | None = None) -> list[str]:
        errors: list[str] = []
        seen: set[tuple[str, str, str]] = set()
        for binding in self.bindings:
            if binding.signal not in project.signals:
                errors.append(f"unknown signal: {binding.signal}")
                continue
            ep = binding.endpoint
            if adapter and ep.adapter and ep.adapter != adapter:
                continue
            if ep.direction not in {"input", "output", "bidirectional"}:
                errors.append(f"invalid direction for {binding.signal}: {ep.direction}")
            if not ep.object:
                errors.append(f"missing endpoint object for {binding.signal}")
            key = (binding.signal, ep.adapter, ep.direction)
            if key in seen:
                errors.append(f"duplicate binding: {binding.signal}/{ep.adapter}/{ep.direction}")
            seen.add(key)
            signal = project.signals[binding.signal]
            if ep.unit and signal.unit and ep.unit != signal.unit:
                errors.append(f"unit mismatch for {binding.signal}: signal={signal.unit}, binding={ep.unit}")
            if signal.kind is SignalKind.BUS and ep.property == "value":
                errors.append(f"bus signal {binding.signal} requires a bus/frame property")
        return errors

    def for_adapter(self, name: str) -> list[SignalBinding]:
        return [b for b in self.bindings if b.endpoint.adapter == name]


def validate_project_bindings(project: MechatronicProject) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    for domain, config in project.simulators.items():
        binding_name = config.options.get("bindings")
        if not binding_name:
            continue
        path = project.resolve(str(binding_name))
        if path is None or not path.exists():
            reports.append({"domain": domain.value, "path": str(path), "errors": ["binding file does not exist"]})
            continue
        manifest = BindingManifest.load(path)
        backend = str(config.options.get("backend", domain.value))
        reports.append({"domain": domain.value, "path": str(path), "bindings": len(manifest.bindings), "errors": manifest.validate(project, backend)})
    errors = [error for report in reports for error in report.get("errors", [])]
    return {"valid": not errors, "reports": reports, "errors": errors}

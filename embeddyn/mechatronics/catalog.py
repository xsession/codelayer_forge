from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import yaml


@dataclass(frozen=True)
class ComponentDescriptor:
    component_id: str
    version: str
    category: str
    fidelity_levels: tuple[str, ...]
    definition: dict[str, Any]
    source: Path


class ComponentCatalog:
    def __init__(self, roots: list[Path]) -> None:
        self.roots = roots

    def scan(self) -> list[ComponentDescriptor]:
        result: list[ComponentDescriptor] = []
        for root in self.roots:
            if not root.exists():
                continue
            for path in sorted([*root.rglob("*.yaml"), *root.rglob("*.yml"), *root.rglob("*.json")]):
                try:
                    raw = json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else yaml.safe_load(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(raw, dict) or raw.get("kind") not in {"component-definition", "mechatronic-component"}:
                    continue
                identity = raw.get("identity", {})
                cid = str(identity.get("id") or ".".join(filter(None, [identity.get("namespace"), identity.get("name")])) or path.stem)
                models = raw.get("models", {})
                result.append(ComponentDescriptor(cid, str(identity.get("version", "0.0.0")), str(raw.get("category", "uncategorized")), tuple(sorted(models)), raw, path))
        return result

    def resolve(self, component_id: str, version: str | None = None) -> ComponentDescriptor:
        matches = [item for item in self.scan() if item.component_id == component_id and (version is None or item.version == version)]
        if not matches:
            raise KeyError(component_id)
        return sorted(matches, key=lambda item: item.version)[-1]

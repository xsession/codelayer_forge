from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class Checkpoint:
    time_seconds: float
    path: Path


class CheckpointManager:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, time_seconds: float, state: Mapping[str, Any]) -> Checkpoint:
        micros = int(round(time_seconds * 1_000_000))
        path = self.directory / f"checkpoint-{micros:016d}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        temporary.replace(path)
        return Checkpoint(time_seconds, path)

    @staticmethod
    def load(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

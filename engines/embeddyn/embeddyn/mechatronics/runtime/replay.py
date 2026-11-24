from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from ..storage.telemetry import read_telemetry_rows


def replay_run(run_directory: Path) -> Iterator[dict[str, Any]]:
    run_directory = run_directory.resolve()
    manifest = json.loads((run_directory / "manifest.json").read_text(encoding="utf-8"))
    datasets = manifest.get("telemetry") or {}
    combined = datasets.get("combined")
    if not combined:
        raise ValueError("run manifest does not contain combined telemetry")
    for row in read_telemetry_rows(Path(combined["path"])):
        yield row

def verify_replay(run_directory: Path) -> dict[str, Any]:
    rows = list(replay_run(run_directory))
    monotonic = all(rows[i]["time"] <= rows[i + 1]["time"] for i in range(len(rows) - 1))
    return {"run_directory": str(run_directory.resolve()), "rows": len(rows),
            "monotonic_time": monotonic, "first_time": rows[0]["time"] if rows else None,
            "last_time": rows[-1]["time"] if rows else None}

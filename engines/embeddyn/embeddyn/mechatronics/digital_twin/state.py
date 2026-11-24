from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analytics import read_measurements


def create_state_snapshot(measurement_path: Path) -> dict[str, Any]:
    rows = read_measurements(measurement_path)
    if not rows:
        raise ValueError("measurement dataset is empty")
    time_key = next((key for key in ("time_seconds", "time", "t") if key in rows[0]), None)
    latest = max(rows, key=lambda row: row[time_key]) if time_key else rows[-1]
    state = {key: value for key, value in latest.items() if key != time_key}
    return {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": str(measurement_path.resolve()),
        "source_time": latest.get(time_key) if time_key else None,
        "state": state,
    }

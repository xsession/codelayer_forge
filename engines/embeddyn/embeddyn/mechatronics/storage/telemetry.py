from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


class TelemetryWriter:
    """Streaming telemetry writer.

    Uses Parquet when pyarrow is installed. Otherwise writes newline-delimited
    JSON, preserving a stable storage interface without buffering the full run.
    """

    def __init__(self, path: Path, *, flush_rows: int = 1024) -> None:
        self.requested_path = path.resolve()
        self.flush_rows = max(1, flush_rows)
        self._buffer: list[dict[str, float]] = []
        self._rows = 0
        self._schema: list[str] = []
        self._parquet_writer: Any = None
        self._pyarrow: Any = None
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
            self._pyarrow = (pa, pq)
            self.path = self.requested_path.with_suffix(".parquet")
            self.format = "parquet"
        except ImportError:
            self.path = self.requested_path.with_suffix(".jsonl")
            self.format = "jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.path.unlink()

    @property
    def row_count(self) -> int:
        return self._rows

    @property
    def schema(self) -> dict[str, Any]:
        return {"columns": self._schema, "types": {name: "float64" for name in self._schema}}

    def append(self, row: Mapping[str, float]) -> None:
        normalized = {str(key): float(value) for key, value in row.items()}
        if not self._schema:
            self._schema = list(normalized.keys())
        elif list(normalized.keys()) != self._schema:
            raise ValueError("telemetry row schema changed during run")
        self._buffer.append(normalized)
        self._rows += 1
        if len(self._buffer) >= self.flush_rows:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        if self.format == "parquet":
            pa, pq = self._pyarrow
            table = pa.Table.from_pylist(self._buffer)
            if self._parquet_writer is None:
                self._parquet_writer = pq.ParquetWriter(self.path, table.schema, compression="zstd")
            self._parquet_writer.write_table(table)
        else:
            with self.path.open("a", encoding="utf-8") as handle:
                for row in self._buffer:
                    handle.write(json.dumps(row, separators=(",", ":"), sort_keys=False) + "\n")
        self._buffer.clear()

    def close(self) -> None:
        self.flush()
        if self._parquet_writer is not None:
            self._parquet_writer.close()
            self._parquet_writer = None

    def __enter__(self) -> "TelemetryWriter":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


def read_telemetry_rows(path: Path) -> list[dict[str, float]]:
    path = path.resolve()
    if path.suffix == ".jsonl":
        with path.open(encoding="utf-8") as handle:
            return [{key: float(value) for key, value in json.loads(line).items()} for line in handle if line.strip()]
    if path.suffix == ".parquet":
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError("pyarrow is required to read Parquet telemetry") from exc
        return [{key: float(value) for key, value in row.items()} for row in pq.read_table(path).to_pylist()]
    if path.suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            return [{key: float(value) for key, value in row.items()} for row in csv.DictReader(handle)]
    raise ValueError(f"unsupported telemetry format: {path}")


def export_telemetry_csv(source: Path, destination: Path) -> Path:
    rows = read_telemetry_rows(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        destination.write_text("", encoding="utf-8")
        return destination
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return destination


class StructuredRecordWriter:
    """Streaming JSONL writer for event and bus records with arbitrary payloads."""
    def __init__(self, path: Path) -> None:
        self.path = path.resolve().with_suffix(".jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.path.unlink()
        self.path.touch()
        self.row_count = 0

    @property
    def format(self) -> str:
        return "jsonl"

    @property
    def schema(self) -> dict[str, Any]:
        return {"type": "structured-record", "version": 1}

    def append(self, record: Mapping[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(record), separators=(",", ":"), sort_keys=True) + "\n")
        self.row_count += 1

    def close(self) -> None:
        pass

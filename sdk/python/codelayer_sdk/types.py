from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class DiagnosticSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFORMATION = "information"
    HINT = "hint"


@dataclass(slots=True, frozen=True)
class Diagnostic:
    code: str
    message: str
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR
    path: str | None = None
    source: str | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["severity"] = self.severity.value
        return result

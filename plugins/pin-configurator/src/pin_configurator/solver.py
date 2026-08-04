from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codelayer_sdk import Diagnostic, DiagnosticSeverity, ValidationError


@dataclass(slots=True, frozen=True)
class Pin:
    name: str
    capabilities: frozenset[str]
    reserved: bool = False
    bank: str | None = None
    voltage: float | None = None


@dataclass(slots=True, frozen=True)
class Signal:
    signal_id: str
    requires: frozenset[str]
    preferred: tuple[str, ...] = ()
    fixed_pin: str | None = None


def _parse_pin(value: dict[str, Any]) -> Pin:
    try:
        return Pin(
            name=str(value["name"]),
            capabilities=frozenset(map(str, value.get("capabilities", []))),
            reserved=bool(value.get("reserved", False)),
            bank=str(value["bank"]) if value.get("bank") is not None else None,
            voltage=float(value["voltage"]) if value.get("voltage") is not None else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError(f"invalid pin definition: {value!r}") from exc


def _parse_signal(value: dict[str, Any]) -> Signal:
    try:
        return Signal(
            signal_id=str(value["id"]),
            requires=frozenset(map(str, value.get("requires", []))),
            preferred=tuple(map(str, value.get("preferred", []))),
            fixed_pin=str(value["fixed_pin"]) if value.get("fixed_pin") else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError(f"invalid signal definition: {value!r}") from exc


def solve(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError("pin solver input must be an object")
    pins = [_parse_pin(pin) for pin in payload.get("pins", [])]
    signals = [_parse_signal(signal) for signal in payload.get("signals", [])]
    if not pins or not signals:
        raise ValidationError("pin solver requires non-empty pins and signals")
    if len({pin.name for pin in pins}) != len(pins):
        raise ValidationError("pin names must be unique")
    if len({signal.signal_id for signal in signals}) != len(signals):
        raise ValidationError("signal ids must be unique")

    pin_by_name = {pin.name: pin for pin in pins}
    candidates: dict[str, list[str]] = {}
    diagnostics: list[Diagnostic] = []

    for signal in signals:
        compatible = [
            pin.name
            for pin in pins
            if not pin.reserved and signal.requires.issubset(pin.capabilities)
        ]
        preferred_order = {name: index for index, name in enumerate(signal.preferred)}
        compatible.sort(key=lambda name: (preferred_order.get(name, 10_000), name))
        if signal.fixed_pin:
            pin = pin_by_name.get(signal.fixed_pin)
            if pin is None:
                diagnostics.append(Diagnostic(
                    code="PIN_FIXED_UNKNOWN",
                    message=f"{signal.signal_id} is fixed to unknown pin {signal.fixed_pin}",
                    path=signal.signal_id,
                    source="pin-configurator",
                ))
                compatible = []
            elif pin.reserved or not signal.requires.issubset(pin.capabilities):
                diagnostics.append(Diagnostic(
                    code="PIN_FIXED_INCOMPATIBLE",
                    message=f"{signal.signal_id} cannot use fixed pin {signal.fixed_pin}",
                    path=signal.signal_id,
                    source="pin-configurator",
                ))
                compatible = []
            else:
                compatible = [signal.fixed_pin]
        if not compatible:
            diagnostics.append(Diagnostic(
                code="PIN_NO_CANDIDATE",
                message=f"No compatible pin is available for {signal.signal_id}",
                path=signal.signal_id,
                source="pin-configurator",
            ))
        candidates[signal.signal_id] = compatible

    ordered = sorted(signals, key=lambda signal: (len(candidates[signal.signal_id]), signal.signal_id))
    assignment: dict[str, str] = {}
    used: set[str] = set()

    def backtrack(index: int) -> bool:
        if index == len(ordered):
            return True
        signal = ordered[index]
        for pin_name in candidates[signal.signal_id]:
            if pin_name in used:
                continue
            assignment[signal.signal_id] = pin_name
            used.add(pin_name)
            if backtrack(index + 1):
                return True
            used.remove(pin_name)
            assignment.pop(signal.signal_id, None)
        return False

    solved = backtrack(0)
    if not solved:
        assignment.clear()
        diagnostics.append(Diagnostic(
            code="PIN_UNSATISFIABLE",
            message="No complete assignment satisfies all pin constraints",
            source="pin-configurator",
            details={"candidateCounts": {key: len(value) for key, value in candidates.items()}},
        ))

    return {
        "solved": solved,
        "assignments": dict(sorted(assignment.items())),
        "unassigned": sorted(set(candidates) - set(assignment)),
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
        "candidateCounts": {key: len(value) for key, value in sorted(candidates.items())},
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    pins = {_parse_pin(pin).name: _parse_pin(pin) for pin in payload.get("pins", [])}
    signals = {_parse_signal(signal).signal_id: _parse_signal(signal) for signal in payload.get("signals", [])}
    assignments = payload.get("assignments", {})
    diagnostics: list[Diagnostic] = []
    occupied: dict[str, str] = {}

    for signal_id, pin_name in assignments.items():
        signal = signals.get(signal_id)
        pin = pins.get(pin_name)
        if signal is None:
            diagnostics.append(Diagnostic("PIN_SIGNAL_UNKNOWN", f"Unknown signal {signal_id}", path=signal_id))
            continue
        if pin is None:
            diagnostics.append(Diagnostic("PIN_UNKNOWN", f"Unknown pin {pin_name}", path=signal_id))
            continue
        if pin.reserved:
            diagnostics.append(Diagnostic("PIN_RESERVED", f"Pin {pin_name} is reserved", path=signal_id))
        if not signal.requires.issubset(pin.capabilities):
            missing = sorted(signal.requires - pin.capabilities)
            diagnostics.append(Diagnostic(
                "PIN_CAPABILITY_MISMATCH",
                f"Pin {pin_name} lacks capabilities: {', '.join(missing)}",
                path=signal_id,
            ))
        if pin_name in occupied:
            diagnostics.append(Diagnostic(
                "PIN_DUPLICATE_ASSIGNMENT",
                f"Pin {pin_name} is assigned to both {occupied[pin_name]} and {signal_id}",
                path=signal_id,
            ))
        occupied[pin_name] = signal_id

    for signal_id in signals:
        if signal_id not in assignments:
            diagnostics.append(Diagnostic(
                "PIN_SIGNAL_UNASSIGNED",
                f"Signal {signal_id} is not assigned",
                severity=DiagnosticSeverity.WARNING,
                path=signal_id,
            ))
    return {
        "valid": not any(d.severity == DiagnosticSeverity.ERROR for d in diagnostics),
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
    }


def generate(payload: dict[str, Any]) -> dict[str, Any]:
    assignments = payload.get("assignments", {})
    io_standard = payload.get("ioStandard", "LVCMOS33")
    fmt = str(payload.get("format", "xdc")).lower()
    if fmt == "xdc":
        lines = []
        for signal, pin in sorted(assignments.items()):
            lines.append(f"set_property PACKAGE_PIN {pin} [get_ports {{{signal}}}]")
            lines.append(f"set_property IOSTANDARD {io_standard} [get_ports {{{signal}}}]")
    elif fmt == "pcf":
        lines = [f"set_io {signal} {pin}" for signal, pin in sorted(assignments.items())]
    elif fmt in {"dts", "devicetree"}:
        lines = ["/ {", "    codelayer_pinmap: codelayer-pinmap {"]
        for signal, pin in sorted(assignments.items()):
            key = signal.lower().replace("_", "-")
            lines.append(f'        {key} = "{pin}";')
        lines.extend(["    };", "};"])
    else:
        raise ValidationError(f"unsupported output format: {fmt}")
    return {"format": fmt, "content": "\n".join(lines) + "\n", "lineCount": len(lines)}

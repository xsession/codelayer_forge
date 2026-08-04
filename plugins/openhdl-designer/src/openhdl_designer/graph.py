from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from codelayer_sdk import Diagnostic, DiagnosticSeverity, ValidationError

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _ports(node: dict[str, Any], direction: str) -> dict[str, int]:
    raw = node.get("ports", {}).get(direction, [])
    result: dict[str, int] = {}
    for item in raw:
        if isinstance(item, str):
            result[item] = 1
        elif isinstance(item, dict) and "name" in item:
            result[str(item["name"])] = int(item.get("width", 1))
        else:
            raise ValidationError(f"invalid {direction} port on node {node.get('id')}: {item!r}")
    return result


def _top_ports(graph: dict[str, Any]) -> dict[str, tuple[str, int]]:
    result: dict[str, tuple[str, int]] = {}
    for item in graph.get("topPorts", []):
        if not isinstance(item, dict) or "name" not in item or "direction" not in item:
            raise ValidationError(f"invalid top port: {item!r}")
        name = str(item["name"])
        direction = str(item["direction"])
        if direction not in {"input", "output", "inout"}:
            raise ValidationError(f"invalid direction for top port {name}: {direction}")
        result[name] = (direction, int(item.get("width", 1)))
    return result


def _endpoint(value: Any) -> tuple[str, str]:
    if not isinstance(value, str) or "." not in value:
        raise ValidationError(f"endpoint must use node.port syntax: {value!r}")
    owner, port = value.split(".", 1)
    return owner, port


def validate_graph(graph: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(graph, dict):
        raise ValidationError("HDL graph must be an object")
    diagnostics: list[Diagnostic] = []
    nodes = graph.get("nodes", [])
    if not isinstance(nodes, list):
        raise ValidationError("nodes must be an array")
    node_by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict) or "id" not in node or "module" not in node:
            diagnostics.append(Diagnostic("HDL_NODE_INVALID", f"Invalid node: {node!r}", source="openhdl-designer"))
            continue
        node_id = str(node["id"])
        if node_id in node_by_id:
            diagnostics.append(Diagnostic("HDL_NODE_DUPLICATE", f"Duplicate node id {node_id}", path=node_id, source="openhdl-designer"))
        if not _IDENTIFIER.match(node_id):
            diagnostics.append(Diagnostic("HDL_IDENTIFIER_INVALID", f"Node id is not a Verilog identifier: {node_id}", path=node_id, source="openhdl-designer"))
        node_by_id[node_id] = node
    top_ports = _top_ports(graph)
    if len(top_ports) != len(graph.get("topPorts", [])):
        diagnostics.append(Diagnostic("HDL_TOP_PORT_DUPLICATE", "Top port names must be unique", source="openhdl-designer"))

    target_drivers: dict[str, str] = {}
    adjacency: dict[str, set[str]] = defaultdict(set)
    for index, net in enumerate(graph.get("nets", [])):
        if not isinstance(net, dict) or "from" not in net or "to" not in net:
            diagnostics.append(Diagnostic("HDL_NET_INVALID", f"Net {index} is invalid", path=f"nets[{index}]", source="openhdl-designer"))
            continue
        try:
            source_owner, source_port = _endpoint(net["from"])
            target_owner, target_port = _endpoint(net["to"])
        except ValidationError as exc:
            diagnostics.append(Diagnostic("HDL_ENDPOINT_INVALID", str(exc), path=f"nets[{index}]", source="openhdl-designer"))
            continue

        source_valid = False
        if source_owner == "top":
            source_valid = source_port in top_ports and top_ports[source_port][0] in {"input", "inout"}
        elif source_owner in node_by_id:
            source_valid = source_port in _ports(node_by_id[source_owner], "outputs")
        if not source_valid:
            diagnostics.append(Diagnostic("HDL_SOURCE_UNKNOWN", f"Unknown or invalid source {net['from']}", path=f"nets[{index}]", source="openhdl-designer"))

        target_valid = False
        if target_owner == "top":
            target_valid = target_port in top_ports and top_ports[target_port][0] in {"output", "inout"}
        elif target_owner in node_by_id:
            target_valid = target_port in _ports(node_by_id[target_owner], "inputs")
        if not target_valid:
            diagnostics.append(Diagnostic("HDL_TARGET_UNKNOWN", f"Unknown or invalid target {net['to']}", path=f"nets[{index}]", source="openhdl-designer"))

        target_key = str(net["to"])
        if target_key in target_drivers:
            diagnostics.append(Diagnostic(
                "HDL_MULTIPLE_DRIVERS",
                f"{target_key} is driven by both {target_drivers[target_key]} and {net['from']}",
                path=f"nets[{index}]",
                source="openhdl-designer",
            ))
        target_drivers[target_key] = str(net["from"])
        if source_owner in node_by_id and target_owner in node_by_id:
            adjacency[source_owner].add(target_owner)

    # Detect cycles composed only of nodes not marked sequential.
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str, stack: list[str]) -> None:
        if node_id in visited or node_by_id.get(node_id, {}).get("sequential", False):
            return
        if node_id in visiting:
            cycle = stack[stack.index(node_id):] + [node_id]
            diagnostics.append(Diagnostic(
                "HDL_COMBINATIONAL_CYCLE",
                "Combinational cycle: " + " -> ".join(cycle),
                path=node_id,
                source="openhdl-designer",
            ))
            return
        visiting.add(node_id)
        stack.append(node_id)
        for target in sorted(adjacency[node_id]):
            visit(target, stack)
        stack.pop()
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in sorted(node_by_id):
        visit(node_id, [])

    connected_targets = set(target_drivers)
    for node_id, node in node_by_id.items():
        for port in _ports(node, "inputs"):
            endpoint = f"{node_id}.{port}"
            if endpoint not in connected_targets:
                diagnostics.append(Diagnostic(
                    "HDL_INPUT_UNCONNECTED",
                    f"Input {endpoint} is unconnected",
                    severity=DiagnosticSeverity.WARNING,
                    path=endpoint,
                    source="openhdl-designer",
                ))

    errors = [item for item in diagnostics if item.severity == DiagnosticSeverity.ERROR]
    return {
        "valid": not errors,
        "diagnostics": [item.to_dict() for item in diagnostics],
        "summary": summarize(graph),
    }


def summarize(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
    modules: dict[str, int] = defaultdict(int)
    sequential = 0
    for node in nodes:
        if isinstance(node, dict):
            modules[str(node.get("module", "<unknown>"))] += 1
            sequential += bool(node.get("sequential", False))
    return {
        "name": graph.get("name", "top") if isinstance(graph, dict) else "top",
        "nodes": len(nodes),
        "nets": len(graph.get("nets", [])) if isinstance(graph, dict) else 0,
        "topPorts": len(graph.get("topPorts", [])) if isinstance(graph, dict) else 0,
        "sequentialNodes": sequential,
        "moduleUsage": dict(sorted(modules.items())),
    }


def _width(width: int) -> str:
    return "" if width <= 1 else f"[{width - 1}:0] "


def _identifier(value: str, fallback: str = "top") -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_$]", "_", value)
    if not sanitized or not re.match(r"[A-Za-z_]", sanitized[0]):
        sanitized = "n_" + sanitized
    return sanitized or fallback


def generate_verilog(graph: dict[str, Any]) -> dict[str, Any]:
    validation = validate_graph(graph)
    if not validation["valid"]:
        raise ValidationError("HDL graph contains errors", data=validation)

    module_name = _identifier(str(graph.get("name", "top")))
    top_ports = _top_ports(graph)
    nodes = {str(node["id"]): node for node in graph.get("nodes", [])}
    source_signal: dict[str, str] = {}
    target_signal: dict[str, str] = {}
    wire_widths: dict[str, int] = {}

    for port_name, (direction, width) in top_ports.items():
        if direction in {"input", "inout"}:
            source_signal[f"top.{port_name}"] = port_name

    for node_id, node in nodes.items():
        for port, width in _ports(node, "outputs").items():
            signal = f"w_{_identifier(node_id)}_{_identifier(port)}"
            source_signal[f"{node_id}.{port}"] = signal
            wire_widths[signal] = width

    assignments: list[tuple[str, str]] = []
    for net in graph.get("nets", []):
        source = source_signal[str(net["from"])]
        target = str(net["to"])
        target_signal[target] = source
        if target.startswith("top."):
            assignments.append((target.split(".", 1)[1], source))

    port_list = ", ".join(top_ports)
    lines = [f"module {module_name}({port_list});"]
    for port_name, (direction, width) in top_ports.items():
        lines.append(f"    {direction} wire {_width(width)}{port_name};")
    if top_ports:
        lines.append("")
    for signal, width in sorted(wire_widths.items()):
        lines.append(f"    wire {_width(width)}{signal};")
    if wire_widths:
        lines.append("")
    for target, source in assignments:
        lines.append(f"    assign {target} = {source};")
    if assignments:
        lines.append("")

    for node_id, node in nodes.items():
        module = _identifier(str(node["module"]))
        parameters = node.get("parameters", {})
        if parameters:
            parameter_text = ", ".join(f".{_identifier(str(key))}({value})" for key, value in sorted(parameters.items()))
            header = f"    {module} #({parameter_text}) {_identifier(node_id)} ("
        else:
            header = f"    {module} {_identifier(node_id)} ("
        connections: list[str] = []
        for port in _ports(node, "inputs"):
            signal = target_signal.get(f"{node_id}.{port}", "1'b0")
            connections.append(f"        .{_identifier(port)}({signal})")
        for port in _ports(node, "outputs"):
            connections.append(f"        .{_identifier(port)}({source_signal[f'{node_id}.{port}']})")
        lines.append(header)
        lines.append(",\n".join(connections))
        lines.append("    );")
        lines.append("")
    lines.append("endmodule")
    lines.append("")
    return {
        "language": "verilog",
        "module": module_name,
        "content": "\n".join(lines),
        "validation": validation,
    }

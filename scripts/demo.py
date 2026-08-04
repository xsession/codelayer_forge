#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "hosts/python-plugin-host/forge_plugin_host.py"
WORKSPACE = ROOT / "examples/demo-workspace"

SESSIONS: dict[str, tuple[str, dict[str, Any]]] = {
    "pin-configurator": (
        "pinConfigurator.autoAssign",
        {
            "pins": [
                {"name": "A1", "capabilities": ["GPIO", "UART_TX"]},
                {"name": "A2", "capabilities": ["GPIO", "UART_RX"]},
                {"name": "B1", "capabilities": ["GPIO", "PWM"]},
            ],
            "signals": [
                {"id": "uart_tx", "requires": ["UART_TX"]},
                {"id": "uart_rx", "requires": ["UART_RX"]},
                {"id": "led", "requires": ["GPIO"], "preferred": ["B1"]},
            ],
        },
    ),
    "route-core": (
        "routeCore.routeSample",
        {
            "source": {"x": 20, "y": 40},
            "target": {"x": 420, "y": 240},
            "obstacles": [{"x": 140, "y": 20, "width": 120, "height": 180}],
            "grid": 10,
            "clearance": 10,
            "bendPenalty": 30,
        },
    ),
    "openhdl-designer": (
        "openHdl.generateVerilog",
        {
            "name": "demo_top",
            "topPorts": [
                {"name": "clk", "direction": "input"},
                {"name": "enable", "direction": "input"},
                {"name": "pwm", "direction": "output"},
            ],
            "nodes": [{
                "id": "controller",
                "module": "pwm_controller",
                "sequential": True,
                "ports": {"inputs": ["clk", "enable"], "outputs": ["pwm_out"]},
                "parameters": {"PERIOD": 1000},
            }],
            "nets": [
                {"from": "top.clk", "to": "controller.clk"},
                {"from": "top.enable", "to": "controller.enable"},
                {"from": "controller.pwm_out", "to": "top.pwm"},
            ],
        },
    ),
    "pyontust-adapter": (
        "pyontust.runWorkflow",
        {
            "workflow": {"steps": [
                {"id": "check", "action": "validate-json", "value": {"ok": True}},
                {"id": "message", "action": "render-template", "template": "Project {project} is ready"},
            ]},
            "variables": {"project": "CodeLayer Forge"},
        },
    ),
}


def run_session(plugin_directory: str, command: str, arguments: dict[str, Any]) -> dict[str, Any]:
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "forge/initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "forge/executeCommand", "params": {"command": command, "arguments": arguments}},
        {"jsonrpc": "2.0", "id": 3, "method": "forge/shutdown", "params": {}},
    ]
    process = subprocess.run(
        [sys.executable, str(HOST), "--plugin-dir", str(ROOT / "plugins" / plugin_directory), "--workspace", str(WORKSPACE)],
        input="".join(json.dumps(item) + "\n" for item in requests),
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    responses = [json.loads(line) for line in process.stdout.splitlines() if line.strip()]
    if len(responses) != 3 or "error" in responses[1]:
        raise RuntimeError(f"invalid response from {plugin_directory}: {responses}\n{process.stderr}")
    return responses[1]["result"]


def main() -> int:
    print("CodeLayer Forge verified plugin demonstration\n")
    for directory, (command, arguments) in SESSIONS.items():
        result = run_session(directory, command, arguments)
        summary = json.dumps(result, indent=2)
        if len(summary) > 1200:
            summary = summary[:1200] + "\n..."
        print(f"[{directory}] {command}\n{summary}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

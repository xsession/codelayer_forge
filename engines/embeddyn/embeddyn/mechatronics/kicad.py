from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class KiCadBridge:
    """Generate simulation artifacts from a KiCad project.

    The bridge intentionally uses `kicad-cli` for reproducible CI exports and
    emits an IPC-plugin manifest for interactive editor integration. The IPC
    plugin can call the Embeddyn local API without parsing KiCad's internal files.
    """

    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or shutil.which("kicad-cli") or "kicad-cli"

    def export_spice(self, schematic: Path, output: Path) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [self.executable, "sch", "export", "netlist", "--format", "spice", "-o", str(output), str(schematic)]
        subprocess.run(command, check=True, capture_output=True, text=True)
        return output

    def export_bom(self, schematic: Path, output: Path) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [self.executable, "sch", "export", "bom", "-o", str(output), str(schematic)]
        subprocess.run(command, check=True, capture_output=True, text=True)
        return output

    def write_plugin_skeleton(self, destination: Path) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "metadata.json").write_text(json.dumps({
            "name": "Embeddyn Mechatronic Bridge",
            "description": "Send KiCad schematic context to the local Embeddyn co-simulation workspace",
            "version": "0.1.0",
            "identifier": "hu.codelayer.embeddyn-mechatronic-bridge",
            "runtime": {"type": "python"},
        }, indent=2) + "\n", encoding="utf-8")
        (destination / "main.py").write_text('''"""KiCad IPC bridge skeleton.

Install the matching `kicad-python` package for your KiCad release, then use
its IPC API to query the active schematic/selection. This file deliberately
keeps HTTP communication dependency-free.
"""
from __future__ import annotations
import json
import urllib.request

EMBEDDYN_URL = "http://127.0.0.1:9010/api/mechatronics/kicad/sync"

def send_context(context: dict) -> dict:
    request = urllib.request.Request(
        EMBEDDYN_URL,
        data=json.dumps(context).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())

if __name__ == "__main__":
    print("Embeddyn KiCad IPC bridge installed; add release-specific kicad-python hookup here.")
''', encoding="utf-8")
        return destination

    def inspect_spice_netlist(self, netlist: Path) -> dict[str, object]:
        """Inspect a generated SPICE netlist without requiring KiCad at runtime."""
        lines = netlist.read_text(encoding="utf-8", errors="replace").splitlines()
        devices: list[dict[str, str]] = []
        models: set[str] = set()
        subcircuits: set[str] = set()
        nodes: set[str] = set()
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("*"):
                continue
            lower = stripped.lower()
            if lower.startswith(".model "):
                parts = stripped.split()
                if len(parts) > 1:
                    models.add(parts[1])
                continue
            if lower.startswith(".subckt "):
                parts = stripped.split()
                if len(parts) > 1:
                    subcircuits.add(parts[1])
                continue
            if stripped.startswith("."):
                continue
            parts = stripped.split()
            if len(parts) >= 3 and parts[0][0].upper() in "RCLVDQMXBIJSEFGHKTWUZ":
                ref = parts[0]
                device_nodes = parts[1:-1]
                nodes.update(device_nodes)
                devices.append({"reference": ref, "kind": ref[0].upper(), "model_or_value": parts[-1]})
        return {
            "netlist": str(netlist),
            "devices": devices,
            "device_count": len(devices),
            "nodes": sorted(nodes),
            "models": sorted(models),
            "subcircuits": sorted(subcircuits),
        }

    def validate_spice_netlist(self, netlist: Path) -> dict[str, object]:
        report = self.inspect_spice_netlist(netlist)
        errors: list[str] = []
        warnings: list[str] = []
        text = netlist.read_text(encoding="utf-8", errors="replace").lower()
        if ".end" not in text:
            errors.append("SPICE netlist has no .end directive")
        if report["device_count"] == 0:
            warnings.append("SPICE netlist contains no recognized devices")
        if "{{" in text or "}}" in text:
            warnings.append("SPICE netlist contains unresolved Embeddyn template variables")
        return {**report, "valid": not errors, "errors": errors, "warnings": warnings}

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HOST_VERSION = "0.1.0"


@dataclass(slots=True)
class PluginRecord:
    root: Path
    manifest: dict[str, Any]


class PluginProcess:
    def __init__(self, record: PluginRecord, host: Path, workspace: Path, debug: bool) -> None:
        command = [
            sys.executable,
            str(host),
            "--plugin-dir",
            str(record.root),
            "--workspace",
            str(workspace),
        ]
        if debug:
            command.append("--debug")
        self.record = record
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self.next_id = 1
        self.request("forge/initialize", {})

    def request(self, method: str, params: Any) -> Any:
        if self.process.poll() is not None:
            raise RuntimeError(
                f"plugin host for {self.record.manifest['id']} exited with {self.process.returncode}"
            )
        request_id = self.next_id
        self.next_id += 1
        request = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f"plugin host for {self.record.manifest['id']} closed stdout")
        response = json.loads(line)
        if response.get("id") != request_id:
            raise RuntimeError(f"plugin host returned unexpected response id: {response}")
        if "error" in response:
            error = response["error"]
            raise RuntimeError(f"{error.get('message', 'plugin error')} (code {error.get('code')})")
        return response.get("result")

    def close(self) -> None:
        if self.process.poll() is not None:
            return
        try:
            self.request("forge/shutdown", {})
        except Exception:
            self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


class Broker:
    def __init__(self, plugins_root: Path, workspace: Path, debug: bool = False) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.host = self.repo_root / "hosts/python-plugin-host/forge_plugin_host.py"
        self.workspace = workspace.resolve()
        self.debug = debug
        self.plugins: dict[str, PluginRecord] = {}
        self.capabilities: dict[str, tuple[str, str]] = {}
        self.commands: dict[str, str] = {}
        self.processes: dict[str, PluginProcess] = {}
        self._discover(plugins_root.resolve())

    def _discover(self, plugins_root: Path) -> None:
        for path in sorted(plugins_root.glob("*/plugin.toml")):
            with path.open("rb") as handle:
                manifest = tomllib.load(handle)
            plugin_id = str(manifest["id"])
            if plugin_id in self.plugins:
                raise ValueError(f"duplicate plugin id: {plugin_id}")
            record = PluginRecord(path.parent, manifest)
            self.plugins[plugin_id] = record
            for capability, version in manifest.get("provides", {}).items():
                if capability in self.capabilities:
                    raise ValueError(f"multiple providers for capability: {capability}")
                self.capabilities[capability] = (plugin_id, str(version))
            for command in manifest.get("contributes", {}).get("commands", []):
                command_id = str(command["id"])
                if command_id in self.commands:
                    raise ValueError(f"duplicate command id: {command_id}")
                self.commands[command_id] = plugin_id
        for plugin_id, record in self.plugins.items():
            for capability in record.manifest.get("requires", {}):
                if capability not in self.capabilities:
                    raise ValueError(f"{plugin_id} requires missing capability {capability}")

    def process_for(self, plugin_id: str) -> PluginProcess:
        if plugin_id not in self.plugins:
            raise LookupError(f"plugin not found: {plugin_id}")
        if plugin_id not in self.processes:
            self.processes[plugin_id] = PluginProcess(
                self.plugins[plugin_id], self.host, self.workspace, self.debug
            )
        return self.processes[plugin_id]

    def dispatch(self, method: str, params: Any) -> Any:
        params = params or {}
        if method == "forge/initialize":
            return {
                "brokerVersion": HOST_VERSION,
                "pid": os.getpid(),
                "plugins": sorted(self.plugins),
                "capabilities": {
                    name: {"plugin": plugin_id, "version": version}
                    for name, (plugin_id, version) in sorted(self.capabilities.items())
                },
                "commands": dict(sorted(self.commands.items())),
            }
        if method == "forge/executeCommand":
            command = str(params["command"])
            plugin_id = str(params.get("plugin") or self.commands.get(command, ""))
            if not plugin_id:
                raise LookupError(f"command not found: {command}")
            return self.process_for(plugin_id).request(
                "forge/executeCommand",
                {"command": command, "arguments": params.get("arguments")},
            )
        if method == "forge/callCapability":
            capability = str(params["capability"])
            try:
                plugin_id, version = self.capabilities[capability]
            except KeyError as exc:
                raise LookupError(f"capability not found: {capability}") from exc
            result = self.process_for(plugin_id).request(
                "forge/callService",
                {
                    "service": capability,
                    "method": str(params["method"]),
                    "params": params.get("params"),
                },
            )
            return {"provider": plugin_id, "version": version, "result": result}
        if method == "forge/listProcesses":
            return {
                plugin_id: {
                    "pid": process.process.pid,
                    "running": process.process.poll() is None,
                }
                for plugin_id, process in sorted(self.processes.items())
            }
        if method == "forge/shutdown":
            self.close()
            return {"shutdown": True}
        raise LookupError(f"method not found: {method}")

    def close(self) -> None:
        for process in list(self.processes.values()):
            process.close()
        self.processes.clear()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CodeLayer Forge plugin capability broker")
    parser.add_argument("--plugins-root", type=Path, default=Path("plugins"))
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def response_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        broker = Broker(args.plugins_root, args.workspace, args.debug)
    except Exception:
        logging.exception("failed to initialize plugin broker")
        return 2
    try:
        for line in sys.stdin:
            request_id = None
            request: dict[str, Any] = {}
            try:
                request = json.loads(line)
                request_id = request.get("id")
                if request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
                    response = response_error(request_id, -32600, "invalid JSON-RPC request")
                else:
                    result = broker.dispatch(request["method"], request.get("params"))
                    response = {"jsonrpc": "2.0", "id": request_id, "result": result}
            except KeyError as exc:
                response = response_error(request_id, -32602, f"missing parameter: {exc.args[0]}")
            except LookupError as exc:
                response = response_error(request_id, -32601, str(exc))
            except (TypeError, ValueError) as exc:
                response = response_error(request_id, -32602, str(exc))
            except Exception as exc:
                logging.exception("broker request failed")
                response = response_error(request_id, -32603, str(exc))
            if request_id is not None:
                sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
                sys.stdout.flush()
            if request.get("method") == "forge/shutdown":
                break
    finally:
        broker.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

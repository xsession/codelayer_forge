#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import logging
import os
import sys
import tomllib
import traceback
from pathlib import Path
from typing import Any

HOST_VERSION = "0.1.0"
PLATFORM_API_VERSION = "0.1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CodeLayer Forge Python plugin host")
    parser.add_argument("--plugin-dir", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def configure_imports(repo_root: Path, plugin_dir: Path) -> None:
    sdk_root = repo_root / "sdk" / "python"
    plugin_src = plugin_dir / "src"
    for path in (str(sdk_root), str(plugin_src)):
        if path not in sys.path:
            sys.path.insert(0, path)


def load_manifest(plugin_dir: Path) -> dict[str, Any]:
    manifest_path = plugin_dir / "plugin.toml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing plugin manifest: {manifest_path}")
    with manifest_path.open("rb") as handle:
        manifest = tomllib.load(handle)
    if manifest.get("manifest_version") != 1:
        raise ValueError("only manifest_version = 1 is supported")
    if manifest.get("runtime") != "python":
        raise ValueError("Python host can only load runtime = 'python' plugins")
    if not manifest.get("entrypoint"):
        raise ValueError("Python plugin requires an entrypoint")
    return manifest


def resolve_entrypoint(specification: str) -> Any:
    module_name, separator, attribute_name = specification.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("entrypoint must use module:attribute syntax")
    module = importlib.import_module(module_name)
    target = getattr(module, attribute_name)
    return target() if callable(target) else target


class PluginHost:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.plugin_dir = args.plugin_dir.resolve()
        self.repo_root = Path(__file__).resolve().parents[2]
        configure_imports(self.repo_root, self.plugin_dir)
        from codelayer_sdk import PluginContext

        self.manifest = load_manifest(self.plugin_dir)
        plugin_id = self.manifest["id"]
        self.logger = logging.getLogger(plugin_id)
        self.context = PluginContext(
            plugin_id=plugin_id,
            plugin_root=self.plugin_dir,
            workspace_root=args.workspace.resolve(),
            permissions=self.manifest.get("permissions", {}),
            logger=self.logger,
        )
        self.plugin = resolve_entrypoint(self.manifest["entrypoint"])
        activate = getattr(self.plugin, "activate", None)
        if not callable(activate):
            raise TypeError("plugin entrypoint must expose activate(context)")
        activate(self.context)
        self.running = True

    async def dispatch(self, method: str, params: Any) -> Any:
        if method == "forge/initialize":
            return {
                "hostVersion": HOST_VERSION,
                "platformApiVersion": PLATFORM_API_VERSION,
                "plugin": self.manifest,
                "commands": list(self.context.commands.ids),
                "services": self.context.services.capabilities,
                "pid": os.getpid(),
            }
        if method == "forge/listCapabilities":
            return {
                "commands": list(self.context.commands.ids),
                "services": self.context.services.capabilities,
            }
        if method == "forge/executeCommand":
            if not isinstance(params, dict) or "command" not in params:
                raise ValueError("forge/executeCommand requires command and optional arguments")
            return await self.context.commands.execute(params["command"], params.get("arguments"))
        if method == "forge/callService":
            if not isinstance(params, dict) or not {"service", "method"} <= params.keys():
                raise ValueError("forge/callService requires service, method and optional params")
            return await self.context.services.call(
                params["service"], params["method"], params.get("params")
            )
        if method == "forge/shutdown":
            deactivate = getattr(self.plugin, "deactivate", None)
            if callable(deactivate):
                result = deactivate()
                if asyncio.iscoroutine(result):
                    await result
            self.running = False
            return {"shutdown": True}
        raise LookupError(f"method not found: {method}")

    async def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        request_id = request.get("id")
        if request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            return self.error(request_id, -32600, "invalid JSON-RPC request")
        try:
            result = await self.dispatch(request["method"], request.get("params"))
            if request_id is None:
                return None
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except LookupError as exc:
            return self.error(request_id, -32601, str(exc))
        except (TypeError, ValueError) as exc:
            return self.error(request_id, -32602, str(exc))
        except Exception as exc:  # noqa: BLE001 - protocol boundary
            data = None
            try:
                from codelayer_sdk import ForgeError
                if isinstance(exc, ForgeError):
                    data = exc.data
                    return self.error(request_id, exc.code, str(exc), data)
            except ImportError:
                pass
            if self.args.debug:
                data = {"traceback": traceback.format_exc()}
            self.logger.exception("plugin request failed")
            return self.error(request_id, -32603, str(exc), data)

    @staticmethod
    def error(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
        error: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}


async def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        host = PluginHost(args)
    except Exception:  # noqa: BLE001 - startup boundary
        logging.exception("failed to initialize plugin host")
        return 2

    loop = asyncio.get_running_loop()
    while host.running:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = host.error(None, -32700, f"parse error: {exc}")
        else:
            if not isinstance(request, dict):
                response = host.error(None, -32600, "request must be an object")
            else:
                response = await host.handle(request)
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

from __future__ import annotations

import inspect
import json
import logging
import os
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .errors import PermissionDenied, ValidationError

CommandHandler = Callable[..., Any]


class CommandRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, CommandHandler] = {}

    def register(self, command_id: str, handler: CommandHandler) -> None:
        if not command_id or command_id in self._handlers:
            raise ValidationError(f"duplicate or empty command id: {command_id}")
        self._handlers[command_id] = handler

    async def execute(self, command_id: str, arguments: Any = None) -> Any:
        try:
            handler = self._handlers[command_id]
        except KeyError as exc:
            raise ValidationError(f"unknown command: {command_id}") from exc
        result = handler(arguments)
        if inspect.isawaitable(result):
            return await result
        return result

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))


class ServiceRegistry:
    def __init__(self) -> None:
        self._services: dict[str, tuple[str, object]] = {}

    def register(self, capability: str, version: str, service: object) -> None:
        if not capability or capability in self._services:
            raise ValidationError(f"duplicate or empty service capability: {capability}")
        self._services[capability] = (version, service)

    async def call(self, capability: str, method: str, params: Any = None) -> Any:
        try:
            _, service = self._services[capability]
        except KeyError as exc:
            raise ValidationError(f"unknown service: {capability}") from exc
        if method.startswith("_") or not hasattr(service, method):
            raise ValidationError(f"unknown service method: {capability}.{method}")
        handler = getattr(service, method)
        if not callable(handler):
            raise ValidationError(f"service attribute is not callable: {capability}.{method}")
        result = handler(params)
        if inspect.isawaitable(result):
            return await result
        return result

    @property
    def capabilities(self) -> dict[str, str]:
        return {name: version for name, (version, _) in sorted(self._services.items())}


class PluginContext:
    """Restricted host services exposed to a Python plugin."""

    def __init__(
        self,
        *,
        plugin_id: str,
        plugin_root: Path,
        workspace_root: Path,
        permissions: Mapping[str, Any],
        logger: logging.Logger,
    ) -> None:
        self.plugin_id = plugin_id
        self.plugin_root = plugin_root.resolve()
        self.workspace_root = workspace_root.resolve()
        self.permissions = dict(permissions)
        self.logger = logger
        self.commands = CommandRegistry()
        self.services = ServiceRegistry()

    def workspace_path(self, relative_path: str | os.PathLike[str], *, write: bool = False) -> Path:
        if write and not self.permissions.get("workspace_write", False):
            raise PermissionDenied("plugin does not have workspace_write permission")
        if not write and not self.permissions.get("workspace_read", False):
            raise PermissionDenied("plugin does not have workspace_read permission")
        candidate = (self.workspace_root / relative_path).resolve()
        try:
            candidate.relative_to(self.workspace_root)
        except ValueError as exc:
            raise PermissionDenied("path escapes workspace boundary") from exc
        return candidate

    def read_json(self, relative_path: str) -> Any:
        path = self.workspace_path(relative_path)
        return json.loads(path.read_text(encoding="utf-8"))

    def write_json_atomic(self, relative_path: str, value: Any) -> Path:
        path = self.workspace_path(relative_path, write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(value, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return path

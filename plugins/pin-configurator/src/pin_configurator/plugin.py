from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import solver


class PinMuxService:
    def solve(self, params: dict[str, Any]) -> dict[str, Any]:
        return solver.solve(params)

    def validate(self, params: dict[str, Any]) -> dict[str, Any]:
        return solver.validate(params)

    def generate(self, params: dict[str, Any]) -> dict[str, Any]:
        return solver.generate(params)


class DeviceDatabaseService:
    def __init__(self, plugin_root: Path) -> None:
        self.plugin_root = plugin_root

    def get_demo_device(self, _params: Any = None) -> dict[str, Any]:
        path = self.plugin_root / "resources" / "demo-device.json"
        return json.loads(path.read_text(encoding="utf-8"))


class PinConfiguratorPlugin:
    def activate(self, context: Any) -> None:
        self.context = context
        service = PinMuxService()
        context.services.register("codelayer.pinmux-solver", "1.0.0", service)
        context.services.register("codelayer.pin-codegen", "1.0.0", service)
        context.services.register(
            "codelayer.device-database", "1.0.0", DeviceDatabaseService(context.plugin_root)
        )
        context.commands.register("pinConfigurator.autoAssign", self.auto_assign)
        context.commands.register("pinConfigurator.validate", self.validate)
        context.commands.register("pinConfigurator.generate", self.generate)
        context.logger.info("Pin Configurator activated")

    def auto_assign(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return solver.solve(arguments or {})

    def validate(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return solver.validate(arguments or {})

    def generate(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return solver.generate(arguments or {})

    def deactivate(self) -> None:
        self.context.logger.info("Pin Configurator deactivated")


def create_plugin() -> PinConfiguratorPlugin:
    return PinConfiguratorPlugin()

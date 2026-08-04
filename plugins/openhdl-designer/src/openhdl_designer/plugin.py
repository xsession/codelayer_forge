from __future__ import annotations

from typing import Any

from .graph import generate_verilog, summarize, validate_graph


class HdlGraphService:
    def validate(self, params: dict[str, Any]) -> dict[str, Any]:
        return validate_graph(params)

    def summarize(self, params: dict[str, Any]) -> dict[str, Any]:
        return summarize(params)

    def generate_verilog(self, params: dict[str, Any]) -> dict[str, Any]:
        return generate_verilog(params)


class OpenHdlDesignerPlugin:
    def activate(self, context: Any) -> None:
        self.context = context
        service = HdlGraphService()
        context.services.register("codelayer.hdl.graph", "1.0.0", service)
        context.services.register("codelayer.hdl.codegen.verilog", "1.0.0", service)
        context.commands.register("openHdl.validateGraph", lambda args: validate_graph(args or {}))
        context.commands.register("openHdl.generateVerilog", lambda args: generate_verilog(args or {}))
        context.logger.info("OpenHDL Designer activated")

    def deactivate(self) -> None:
        self.context.logger.info("OpenHDL Designer deactivated")


def create_plugin() -> OpenHdlDesignerPlugin:
    return OpenHdlDesignerPlugin()

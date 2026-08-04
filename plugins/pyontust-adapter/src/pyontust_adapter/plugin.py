from __future__ import annotations

from typing import Any

from .workflow import WorkflowService


class PyOnTrustAdapterPlugin:
    def activate(self, context: Any) -> None:
        self.context = context
        self.service = WorkflowService(context)
        context.services.register("codelayer.automation.workflow", "1.0.0", self.service)
        context.commands.register("pyontust.runWorkflow", self.run_workflow)
        context.logger.info("PyOnTrust Adapter activated")

    def run_workflow(self, arguments: dict[str, Any] | None) -> dict[str, Any]:
        return self.service.run(arguments or {})

    def deactivate(self) -> None:
        self.context.logger.info("PyOnTrust Adapter deactivated")


def create_plugin() -> PyOnTrustAdapterPlugin:
    return PyOnTrustAdapterPlugin()

from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sdk/python"))
sys.path.insert(0, str(ROOT / "plugins/pyontust-adapter/src"))

from codelayer_sdk import PluginContext, ValidationError  # noqa: E402
from pyontust_adapter.workflow import WorkflowService  # noqa: E402


class WorkflowTests(unittest.TestCase):
    def test_runs_safe_workflow_and_writes_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = PluginContext(
                plugin_id="hu.codelayer.pyontust-adapter",
                plugin_root=ROOT / "plugins/pyontust-adapter",
                workspace_root=Path(directory),
                permissions={"workspace_read": True, "workspace_write": True},
                logger=logging.getLogger("test"),
            )
            service = WorkflowService(context)
            result = service.run({
                "workflow": {"steps": [
                    {"id": "message", "action": "render-template", "template": "Hello {name}"},
                    {"id": "artifact", "action": "write-json", "path": "out/result.json", "value": {"ok": True}},
                ]},
                "variables": {"name": "Forge"},
            })
            self.assertTrue(result["completed"])
            self.assertEqual(result["results"]["message"], "Hello Forge")
            self.assertTrue((Path(directory) / "out/result.json").is_file())

    def test_rejects_shell_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = PluginContext(
                plugin_id="hu.codelayer.pyontust-adapter",
                plugin_root=ROOT / "plugins/pyontust-adapter",
                workspace_root=Path(directory),
                permissions={"workspace_read": True, "workspace_write": True},
                logger=logging.getLogger("test"),
            )
            service = WorkflowService(context)
            with self.assertRaises(ValidationError):
                service.run({"workflow": {"steps": [{"action": "shell", "command": "rm -rf /"}]}})


if __name__ == "__main__":
    unittest.main()

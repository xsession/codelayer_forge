from __future__ import annotations

import json
import shutil
from string import Formatter
from typing import Any

from codelayer_sdk import PluginContext, ValidationError


class _StrictMap(dict[str, Any]):
    def __missing__(self, key: str) -> Any:
        raise ValidationError(f"template variable is missing: {key}")


class WorkflowService:
    def __init__(self, context: PluginContext) -> None:
        self.context = context

    def validate(self, params: dict[str, Any]) -> dict[str, Any]:
        workflow = params.get("workflow", params)
        if not isinstance(workflow, dict):
            raise ValidationError("workflow must be an object")
        steps = workflow.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValidationError("workflow.steps must be a non-empty array")
        allowed = {"validate-json", "render-template", "write-json", "copy-file"}
        errors = []
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                errors.append(f"step {index} must be an object")
                continue
            action = step.get("action")
            if action not in allowed:
                errors.append(f"step {index} uses unsupported action {action!r}")
        return {"valid": not errors, "errors": errors, "steps": len(steps)}

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        workflow = params.get("workflow", params)
        validation = self.validate({"workflow": workflow})
        if not validation["valid"]:
            raise ValidationError("invalid workflow", data=validation)
        variables = dict(params.get("variables", {}))
        results: dict[str, Any] = {}
        log: list[dict[str, Any]] = []
        for index, step in enumerate(workflow["steps"]):
            step_id = str(step.get("id", f"step-{index + 1}"))
            action = step["action"]
            if action == "validate-json":
                source = step.get("value", variables.get(step.get("variable")))
                if isinstance(source, str):
                    source = json.loads(source)
                if not isinstance(source, (dict, list)):
                    raise ValidationError(f"{step_id}: value is not a JSON object or array")
                result = {"valid": True, "type": type(source).__name__}
            elif action == "render-template":
                template = str(step.get("template", ""))
                available = _StrictMap({**variables, **results})
                # Parsing first rejects unsupported conversions/format specs that could obscure output.
                for _, field_name, format_spec, conversion in Formatter().parse(template):
                    if conversion or format_spec:
                        raise ValidationError(f"{step_id}: conversions and format specs are not allowed")
                    if field_name and any(character in field_name for character in ".[]"):
                        raise ValidationError(f"{step_id}: nested template access is not allowed")
                result = template.format_map(available)
            elif action == "write-json":
                value = step.get("value", variables.get(step.get("variable")))
                path = self.context.write_json_atomic(str(step["path"]), value)
                result = {"path": str(path.relative_to(self.context.workspace_root)), "written": True}
            elif action == "copy-file":
                source = self.context.workspace_path(str(step["source"]))
                target = self.context.workspace_path(str(step["target"]), write=True)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                result = {"path": str(target.relative_to(self.context.workspace_root)), "copied": True}
            else:  # guarded by validation
                raise AssertionError(action)
            results[step_id] = result
            log.append({"step": step_id, "action": action, "status": "completed"})
        return {"completed": True, "results": results, "log": log}

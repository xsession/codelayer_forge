"""CodeLayer Forge plugin around the embeddyn co-simulation engine (engines/embeddyn).

Capabilities:

* ``codelayer.simulation.cosim``: parts library, open/validate/run projects.
* ``codelayer.simulation.analysis``: verification, tuning, tolerance analysis.
* ``codelayer.simulation.renode-bindings``: Renode bindings from a Pin
  Configurator pin plan (``embeddyn.mechatronics.pinplan``).

All paths in parameters are workspace-relative and go through the SDK's
permission checks. Runs are synchronous: the platform's request/response
protocol has no progress events yet, so long jobs should use the Lab.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def engine_root(plugin_root: Path) -> Path | None:
    """`EMBEDDYN_ENGINE_ROOT`, else the monorepo's engines/embeddyn, else None
    (an installed `embeddyn` package)."""
    override = os.environ.get("EMBEDDYN_ENGINE_ROOT")
    if override:
        return Path(override).resolve()
    candidate = plugin_root.resolve().parents[1] / "engines" / "embeddyn"
    return candidate if (candidate / "embeddyn" / "mechatronics").is_dir() else None


def ensure_engine(plugin_root: Path) -> None:
    root = engine_root(plugin_root)
    if root is not None and str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import embeddyn.mechatronics  # noqa: F401  (fails early with a clear ImportError)


def _number(value: Any, default: float | None = None) -> float | None:
    return default if value is None else float(value)


class CosimService:
    def __init__(self, context: Any) -> None:
        self.context = context

    def _project_path(self, params: dict[str, Any]) -> Path:
        if not params or not params.get("path"):
            raise ValueError("expected {path: workspace-relative project .yaml}")
        return self.context.workspace_path(str(params["path"]))

    def parts(self, _params: Any = None) -> dict[str, Any]:
        from embeddyn.mechatronics.gui.parts import part_library
        return {"parts": part_library()}

    def open(self, params: dict[str, Any]) -> dict[str, Any]:
        from embeddyn.mechatronics.gui.document import load_graph
        return load_graph(self._project_path(params))

    def validate(self, params: dict[str, Any]) -> dict[str, Any]:
        from embeddyn.mechatronics.bindings import validate_project_bindings
        from embeddyn.mechatronics.model import MechatronicProject
        try:
            project = MechatronicProject.load(self._project_path(params))
        except (ValueError, KeyError, FileNotFoundError) as error:
            return {"valid": False, "errors": [f"{type(error).__name__}: {error}"], "instances": []}
        report = validate_project_bindings(project)
        return {"valid": report["valid"], "errors": report["errors"],
                "instances": sorted(project.simulator_instances()), "signals": len(project.signals)}

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        """Run a project; optional `duration`, `mock`, `output` (workspace CSV path)."""
        from embeddyn.mechatronics.factory import build_adapters
        from embeddyn.mechatronics.metrics import compute_metrics, parse_metric_specs
        from embeddyn.mechatronics.model import MechatronicProject
        from embeddyn.mechatronics.orchestrator import CoSimulationOrchestrator
        project = MechatronicProject.load(self._project_path(params))
        duration = _number(params.get("duration"))
        if duration:
            project.duration_seconds = duration
        orchestrator = CoSimulationOrchestrator(project, build_adapters(project, mock=bool(params.get("mock"))))
        rows = orchestrator.run()
        metrics = compute_metrics(rows, parse_metric_specs(project.metrics)) if project.metrics else {}
        result: dict[str, Any] = {
            "project": project.name, "rows": len(rows), "time": rows[-1]["time"] if rows else 0.0,
            "final": {k: v for k, v in (rows[-1] if rows else {}).items()
                      if k != "time" and isinstance(v, (int, float))},
            "metrics": metrics,
        }
        if params.get("output"):
            path = self.context.workspace_path(str(params["output"]), write=True)
            CoSimulationOrchestrator.write_csv(path, rows)
            result["output"] = str(params["output"])
        return result


class AnalysisService:
    def __init__(self, context: Any) -> None:
        self.context = context

    def verify(self, params: dict[str, Any]) -> dict[str, Any]:
        from embeddyn.mechatronics.verification import verify
        return verify(self.context.workspace_path(str(params["path"])), mock=bool(params.get("mock")),
                      only=params.get("only"))

    def tune(self, params: dict[str, Any]) -> dict[str, Any]:
        from embeddyn.mechatronics.tuning import load_tuning_spec, tune
        return tune(load_tuning_spec(self.context.workspace_path(str(params["spec"]))))

    def tolerance(self, params: dict[str, Any]) -> dict[str, Any]:
        from embeddyn.mechatronics.tolerance import analyse, load_tolerance_spec
        return analyse(load_tolerance_spec(self.context.workspace_path(str(params["spec"]))))


class RenodeBindingsService:
    def __init__(self, context: Any) -> None:
        self.context = context

    def _load(self, value: Any) -> Any:
        if isinstance(value, dict):
            return value
        from embeddyn.mechatronics.pinplan import load_json_or_yaml
        return load_json_or_yaml(self.context.workspace_path(str(value)))

    def from_pin_plan(self, params: dict[str, Any]) -> dict[str, Any]:
        """{plan, device: workspace path or object, merge?: bindings path, output?: path, machine?}."""
        from embeddyn.mechatronics.pinplan import merge_bindings, renode_bindings, to_yaml
        generated = renode_bindings(self._load(params["plan"]), self._load(params["device"]), params.get("machine"))
        manifest = merge_bindings(generated, self._load(params["merge"])) if params.get("merge") else generated
        text = to_yaml(manifest, str(params["plan"]) if isinstance(params["plan"], str) else "")
        result = {"bindings": manifest["bindings"], "diagnostics": generated["diagnostics"], "yaml": text,
                  "valid": not any(d["severity"] == "error" for d in generated["diagnostics"])}
        if params.get("output"):
            path = self.context.workspace_path(str(params["output"]), write=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            result["output"] = str(params["output"])
        return result


class EmbeddynPlugin:
    def __init__(self) -> None:
        self.lab = None
        self.lab_thread = None

    def activate(self, context: Any) -> None:
        self.context = context
        ensure_engine(context.plugin_root)
        self.cosim = CosimService(context)
        self.analysis = AnalysisService(context)
        self.bindings = RenodeBindingsService(context)
        context.services.register("codelayer.simulation.cosim", "1.0.0", self.cosim)
        context.services.register("codelayer.simulation.analysis", "1.0.0", self.analysis)
        context.services.register("codelayer.simulation.renode-bindings", "1.0.0", self.bindings)
        context.commands.register("embeddyn.runProject", lambda args: self.cosim.run(args or {}))
        context.commands.register("embeddyn.validateProject", lambda args: self.cosim.validate(args or {}))
        context.commands.register("embeddyn.bindingsFromPinPlan", lambda args: self.bindings.from_pin_plan(args or {}))
        context.commands.register("embeddyn.openLab", self.open_lab)
        context.commands.register("embeddyn.stopLab", self.stop_lab)
        context.logger.info("embeddyn co-simulation activated (engine %s)", engine_root(context.plugin_root) or "installed")

    def open_lab(self, arguments: dict[str, Any] | None) -> dict[str, Any]:
        """Start the Lab (127.0.0.1) in this plugin process; returns its URL."""
        import threading
        from embeddyn.mechatronics.gui.server import serve
        arguments = arguments or {}
        project = self.context.workspace_path(str(arguments["path"])) if arguments.get("path") else None
        if self.lab is None:
            self.lab = serve(project, "127.0.0.1", int(arguments.get("port", 0)))
            self.lab_thread = threading.Thread(target=self.lab.serve_forever, name="embeddyn-lab", daemon=True)
            self.lab_thread.start()
        url = f"http://127.0.0.1:{self.lab.server_address[1]}/"
        return {"url": url + (f"#open={project}" if project else ""), "running": True}

    def stop_lab(self, _arguments: Any = None) -> dict[str, Any]:
        if self.lab is not None:
            self.lab.shutdown()
            self.lab.lab_state.stop_all()
            self.lab.server_close()
            self.lab = None
        return {"running": False}

    def deactivate(self) -> None:
        self.stop_lab()
        self.context.logger.info("embeddyn co-simulation deactivated")


def create_plugin() -> EmbeddynPlugin:
    return EmbeddynPlugin()

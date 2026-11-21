from __future__ import annotations

from pathlib import Path

from .adapters import (
    LTspiceAdapter,
    MockElectricalAdapter,
    MockFirmwareAdapter,
    MockMechanicalAdapter,
    NgspiceAdapter,
    NgspiceSharedAdapter,
    PythonModelAdapter,
    RenodeAdapter,
    WebotsAdapter,
)
from .model import Domain, MechatronicProject


def renode_kwargs(project: MechatronicProject, cfg) -> dict:
    """Translate `simulators.firmware` options into RenodeAdapter keyword arguments."""
    options = dict(cfg.options)

    def path(key: str) -> str | None:
        resolved = project.resolve(options.get(key))
        return str(resolved) if resolved else None

    return {
        "host": str(options.get("host", "127.0.0.1")),
        "port": int(options.get("port", 21234)),
        "timeout": float(options.get("timeout", 10.0)),
        "machine": options.get("machine"),
        "bindings": path("bindings"),
        "inline_bindings": list(options.get("inline_bindings", [])),
        "launch": bool(options.get("launch", False)),
        "script": path("script") or (str(project.resolve(cfg.model)) if cfg.model else None),
        "firmware": path("firmware"),
        "variables": dict(options.get("variables", {})),
        "executable": cfg.executable or options.get("executable"),
        "renode_args": options.get("renode_args"),
        "server_name": str(options.get("server_name", "embeddyn")),
        "startup_timeout": float(options.get("startup_timeout", 120.0)),
        "log_path": path("log"),
    }


def ngspice_shared_kwargs(project: MechatronicProject, cfg) -> dict:
    """Translate `simulators.electrical` options into NgspiceSharedAdapter keyword arguments."""
    options = dict(cfg.options)
    bindings = project.resolve(options.get("bindings"))
    max_step = options.get("max_step")
    return {
        "netlist": str(project.resolve(cfg.model) or Path("circuit.cir")),
        "bindings": str(bindings) if bindings else None,
        "inline_bindings": list(options.get("inline_bindings", [])),
        "library": options.get("library") or cfg.executable,
        "max_step": float(max_step) if max_step is not None else project.step_seconds / 50,
        "duration": project.duration_seconds,
        "options": dict(options.get("spice_options", {})),
    }


def python_model_kwargs(project: MechatronicProject, cfg) -> dict:
    """Translate simulator options into PythonModelAdapter keyword arguments."""
    options = dict(cfg.options)
    if not cfg.model:
        raise ValueError("python backend needs `model: module:Class` or `file.py:Class`")
    return {
        "model": str(cfg.model),
        "root": str(project.root),
        "parameters": dict(options.get("parameters", {})),
        "inputs": dict(options.get("inputs", {})),
        "outputs": dict(options.get("outputs", {})),
        "max_step": float(options.get("max_step", project.step_seconds / 10)),
    }


def build_adapters(project: MechatronicProject, mock: bool = False, isolate: bool = False):
    adapters = {}
    for domain in Domain:
        cfg = project.simulators.get(domain)
        if cfg and not cfg.enabled:
            continue
        if domain in (Domain.THERMAL, Domain.ENVIRONMENT) and cfg is None:
            continue
        backend = str((cfg.options if cfg else {}).get("backend", "mock" if mock else "auto")).lower()
        options = dict(cfg.options if cfg else {})
        if backend == "python" and not (mock and domain in (Domain.FIRMWARE, Domain.ELECTRICAL, Domain.MECHANICAL)):
            adapters[domain] = PythonModelAdapter(**python_model_kwargs(project, cfg))
        elif domain in (Domain.THERMAL, Domain.ENVIRONMENT):
            raise ValueError(f"{domain.value} domain supports backend: python (got {backend})")
        elif domain is Domain.FIRMWARE:
            if mock or backend == "mock":
                adapters[domain] = MockFirmwareAdapter()
            elif backend == "renode":
                adapters[domain] = RenodeAdapter(**renode_kwargs(project, cfg))
        elif domain is Domain.ELECTRICAL:
            if mock or backend == "mock":
                adapters[domain] = MockElectricalAdapter()
            elif backend == "ltspice":
                adapters[domain] = LTspiceAdapter(
                    project.resolve(cfg.model) or Path("circuit.cir"),
                    executable=cfg.executable,
                    output_csv=str(options.get("output_csv", "cosim.csv")),
                )
            elif backend == "ngspice-shared":
                adapters[domain] = NgspiceSharedAdapter(**ngspice_shared_kwargs(project, cfg))
            elif backend in {"ngspice", "auto"}:
                adapters[domain] = NgspiceAdapter(
                    project.resolve(cfg.model) or Path("circuit.cir"),
                    executable=cfg.executable,
                    output_csv=str(options.get("output_csv", "cosim.csv")),
                )
        elif domain is Domain.MECHANICAL:
            if mock or backend == "mock":
                adapters[domain] = MockMechanicalAdapter()
            elif backend in {"webots", "auto"}:
                adapters[domain] = WebotsAdapter(
                    world=project.resolve(cfg.model) or Path("world.wbt"),
                    executable=cfg.executable,
                    host=str(options.get("host", "127.0.0.1")),
                    port=int(options.get("port", 8765)),
                    headless=bool(options.get("headless", True)),
                    launch=bool(options.get("launch", True)),
                )
    if isolate:
        from .runtime import AdapterWorkerSpec, ProcessAdapterProxy
        isolated = {}
        for domain, adapter in adapters.items():
            kwargs = {}
            if isinstance(adapter, (LTspiceAdapter, NgspiceAdapter)):
                kwargs = {"netlist": adapter.netlist, "executable": adapter.executable,
                          "output_csv": adapter.output_csv, "timeout": adapter.timeout}
            elif isinstance(adapter, WebotsAdapter):
                kwargs = {"world": adapter.world, "executable": adapter.executable, "host": adapter.host,
                          "port": adapter.port, "headless": adapter.headless, "launch": adapter.launch,
                          "timeout": adapter.timeout}
            elif isinstance(adapter, NgspiceSharedAdapter):
                kwargs = ngspice_shared_kwargs(project, project.simulators[domain])
            elif isinstance(adapter, PythonModelAdapter):
                kwargs = python_model_kwargs(project, project.simulators[domain])
            elif isinstance(adapter, RenodeAdapter):
                kwargs = renode_kwargs(project, project.simulators[domain])
            spec = AdapterWorkerSpec(adapter.__class__.__module__, adapter.__class__.__name__, kwargs)
            timeout = float((project.simulators.get(domain).options if project.simulators.get(domain) else {}).get("worker_timeout", 30.0))
            isolated[domain] = ProcessAdapterProxy(spec, timeout_seconds=timeout)
        return isolated
    return adapters

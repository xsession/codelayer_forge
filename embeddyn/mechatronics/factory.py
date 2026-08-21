from __future__ import annotations

from pathlib import Path

from .adapters import (
    LTspiceAdapter,
    MockElectricalAdapter,
    MockFirmwareAdapter,
    MockMechanicalAdapter,
    NgspiceAdapter,
    RenodeSocketAdapter,
    WebotsAdapter,
)
from .model import Domain, MechatronicProject


def build_adapters(project: MechatronicProject, mock: bool = False, isolate: bool = False):
    adapters = {}
    for domain in (Domain.FIRMWARE, Domain.ELECTRICAL, Domain.MECHANICAL):
        cfg = project.simulators.get(domain)
        if cfg and not cfg.enabled:
            continue
        backend = str((cfg.options if cfg else {}).get("backend", "mock" if mock else "auto")).lower()
        options = dict(cfg.options if cfg else {})
        if domain is Domain.FIRMWARE:
            if mock or backend == "mock":
                adapters[domain] = MockFirmwareAdapter()
            elif backend == "renode":
                adapters[domain] = RenodeSocketAdapter(
                    host=str(options.get("host", "127.0.0.1")),
                    port=int(options.get("port", 8766)),
                )
        elif domain is Domain.ELECTRICAL:
            if mock or backend == "mock":
                adapters[domain] = MockElectricalAdapter()
            elif backend == "ltspice":
                adapters[domain] = LTspiceAdapter(
                    project.resolve(cfg.model) or Path("circuit.cir"),
                    executable=cfg.executable,
                    output_csv=str(options.get("output_csv", "cosim.csv")),
                )
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
            elif isinstance(adapter, RenodeSocketAdapter):
                kwargs = {"host": adapter.host, "port": adapter.port, "timeout": adapter.timeout}
            spec = AdapterWorkerSpec(adapter.__class__.__module__, adapter.__class__.__name__, kwargs)
            timeout = float((project.simulators.get(domain).options if project.simulators.get(domain) else {}).get("worker_timeout", 30.0))
            isolated[domain] = ProcessAdapterProxy(spec, timeout_seconds=timeout)
        return isolated
    return adapters

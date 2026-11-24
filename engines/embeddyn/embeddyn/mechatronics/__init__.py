"""Mechatronic co-simulation support for Embeddyn.

The package couples firmware/Renode, Webots mechanical simulation and SPICE
circuit simulation through a deterministic, signal-oriented scheduler.
"""

from .model import Coupling, Domain, MechatronicProject, Signal
from .orchestrator import CoSimulationOrchestrator

__all__ = [
    "CoSimulationOrchestrator",
    "Coupling",
    "Domain",
    "MechatronicProject",
    "Signal",
]

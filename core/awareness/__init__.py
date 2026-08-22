"""What Glitch notices about the machine it lives on.

This package is the only place that looks outside the application. It reports
*categories* ("the user opened a music app"), never raw window titles, unless
the user explicitly opts in. Nothing here is sent anywhere on its own: the
monitor emits events, and the application decides what to do with them.
"""
from core.awareness.monitor import EnvironmentMonitor
from core.awareness.signals import Signal, Snapshot
from core.awareness.triggers import Reaction, TriggerGovernor

__all__ = [
    "EnvironmentMonitor",
    "Reaction",
    "Signal",
    "Snapshot",
    "TriggerGovernor",
]

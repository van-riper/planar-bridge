"""The async pull pipeline, split by phase across this package.

A run flows through three phases: ``metadata`` (compare MTGJSON's build and
refresh the bulk files), ``download`` (walk every set and fetch each card's
image), and ``run`` (the composition root that wires the engine together).
``context`` holds the shared ``PullContext``. This module re-exports the public
surface so callers keep importing from ``planar_bridge.pipeline`` directly.
"""

from .context import PullContext
from .download import CardOutcome, pull_card, pull_set
from .metadata import pull_meta
from .run import pull_all

__all__ = [
    "CardOutcome",
    "PullContext",
    "pull_all",
    "pull_card",
    "pull_meta",
    "pull_set",
]

"""Antivenom — post-hoc surgical repair for poisoned agent memory."""

from .sdk import AntivenomClient
from .plugin import AntivenomPlugin, protect

__version__ = "0.1.0"
__all__ = ["AntivenomClient", "AntivenomPlugin", "protect", "__version__"]


"""Storage layer. One interface, two backends, chosen by feature flag."""

from __future__ import annotations

from ..config import features
from .base import Store
from .local import LocalStore

__all__ = ["LocalStore", "Store", "get_store"]


def get_store(force_local: bool = False) -> Store:
    """The backend for this run.

    ``FEATURE_MONGO=1`` gives Atlas. Anything else gives the in-memory graph, so
    the loop still runs with no network. Importing Motor is deferred to here so
    the demo floor installs without the mongo extra at all.
    """
    if force_local or not features().mongo:
        return LocalStore()

    from .mongo import MongoStore

    return MongoStore()

"""Tests for AntivenomPlugin and @protect decorator."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from antivenom.plugin import AntivenomPlugin, protect
from antivenom.schemas import Outcome


def test_plugin_init():
    plugin = AntivenomPlugin(uri="mongodb://localhost:27017")
    assert plugin.client is not None
    assert plugin._connected is False


def test_protect_decorator_sync_test():
    """Verify @protect wraps functions correctly."""
    plugin = AntivenomPlugin()

    @plugin.protect(action_name="test_action")
    async def sample_agent_task(prompt: str):
        return {"status": "ok", "outcome": Outcome.OK}

    assert sample_agent_task.__name__ == "sample_agent_task"


def test_top_level_protect():
    @protect(action_name="global_action")
    async def sample_global_task(prompt: str):
        return {"status": "ok"}

    assert sample_global_task.__name__ == "sample_global_task"

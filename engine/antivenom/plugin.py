"""Antivenom Plugin — Ultra-simple decorator & middleware interface for any AI Agent."""

from __future__ import annotations

import functools
from typing import Any, Callable, Coroutine, ParamSpec, TypeVar

from .sdk import AntivenomClient
from .schemas import Belief, Decision, Outcome

P = ParamSpec("P")
R = TypeVar("R")


class AntivenomPlugin:
    """Lightweight plugin wrapper to attach Antivenom memory protection to any agent."""

    def __init__(self, uri: str | None = None, db_name: str = "antivenom"):
        self.client = AntivenomClient(uri=uri, db_name=db_name)
        self._connected = False

    async def connect(self) -> None:
        """Establish database connection if not already connected."""
        if not self._connected:
            await self.client.connect()
            self._connected = True

    async def close(self) -> None:
        """Close connection."""
        if self._connected:
            await self.client.close()
            self._connected = False

    async def get_context(self, query: str, limit: int = 5) -> list[Belief]:
        """Retrieve live (non-invalidated) beliefs for a prompt."""
        await self.connect()
        beliefs, _ = await self.client.retrieve_context(query, limit=limit)
        return beliefs

    def protect(
        self,
        action_name: str | None = None,
        auto_repair: bool = True,
    ) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
        """Decorator to wrap async agent execution functions.

        Automatically retrieves live belief context, logs decisions, and executes
        post-hoc surgical memory repair if a harmful outcome or error occurs.
        """
        def decorator(func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, Coroutine[Any, Any, R]]:
            @functools.wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                await self.connect()

                # Derive prompt and action name
                prompt = str(kwargs.get("prompt", args[0] if args else func.__name__))
                action = action_name or func.__name__

                # Retrieve live belief context
                live_beliefs, retrieved_ids = await self.client.retrieve_context(prompt)

                try:
                    result = await func(*args, **kwargs)
                    outcome = Outcome.OK
                    if isinstance(result, dict) and result.get("outcome") == Outcome.HARMFUL:
                        outcome = Outcome.HARMFUL
                    elif hasattr(result, "outcome") and getattr(result, "outcome") == Outcome.HARMFUL:
                        outcome = Outcome.HARMFUL

                    decision = await self.client.log_decision(
                        prompt=prompt,
                        action=action,
                        action_args=kwargs if kwargs else {"args": [str(a) for a in args]},
                        retrieved_belief_ids=retrieved_ids,
                        outcome=outcome,
                    )

                    if outcome == Outcome.HARMFUL and auto_repair:
                        await self.client.repair_memory(decision)

                    return result

                except Exception as exc:
                    decision = await self.client.log_decision(
                        prompt=prompt,
                        action=action,
                        action_args={"error": str(exc)},
                        retrieved_belief_ids=retrieved_ids,
                        outcome=Outcome.HARMFUL,
                    )
                    if auto_repair:
                        await self.client.repair_memory(decision)
                    raise exc

            return wrapper

        return decorator


# Convenient global singleton instance
_default_plugin = AntivenomPlugin()


def protect(
    action_name: str | None = None,
    auto_repair: bool = True,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
    """Top-level decorator using default plugin instance."""
    return _default_plugin.protect(action_name=action_name, auto_repair=auto_repair)

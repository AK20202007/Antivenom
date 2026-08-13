"""Decorator interface: attach memory repair to an existing agent.

The wrapped function **must accept a ``context`` parameter**, and this is
enforced at decoration time rather than left to convention.

The reason is not style. The decorator logs which beliefs were in context when
the agent decided, and that record is the input to causal ablation. If the
agent never actually receives those beliefs, the record is false: ablation then
re-runs counterfactuals over beliefs that played no part in the decision and
names a culprit with total confidence and no meaning. A diagnosis built on a
false premise is worse than no diagnosis, because it looks like an answer.

So the contract is: you take the context, or the decorator refuses to wrap you.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeVar

from .schemas import Belief, Outcome
from .sdk import AntivenomClient

P = ParamSpec("P")
R = TypeVar("R")


def _observe(result: Any, action: str) -> tuple[str, dict[str, Any]]:
    """Read an agent's return value as ``(action, action_args)``.

    Used for both the real call and every counterfactual, deliberately. Ablation
    measures divergence between the two, so if they are derived differently the
    comparison is between shapes rather than behaviour and the diagnosis is
    noise wearing a confidence score.
    """
    harmful = (isinstance(result, dict) and result.get("outcome") == Outcome.HARMFUL) or getattr(
        result, "outcome", None
    ) == Outcome.HARMFUL

    args: dict[str, Any] = {}
    if isinstance(result, dict):
        args = {k: v for k, v in result.items() if k != "outcome"}

    return (action if harmful else "answer", args)


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

    def _rerun_for(self, func: Any, args: Any, kwargs: Any, action: str) -> Any:
        """Build the counterfactual: re-invoke *your* agent with fewer beliefs.

        Without this, ablation re-runs the decision through our built-in agent
        prompt and measures what our model would have done with your beliefs,
        which answers a question nobody asked. The counterfactual has to be your
        code, or the culprit it names is about a different agent.
        """

        async def rerun(kept: list[Belief]) -> tuple[str, dict[str, Any]]:
            trimmed = {**kwargs, "context": kept}
            try:
                result = await func(*args, **trimmed)
            except Exception:
                return ("error", {})
            return _observe(result, action)

        return rerun

    def protect(
        self,
        action_name: str | None = None,
        auto_repair: bool = True,
        limit: int = 5,
    ) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
        """Decorator to wrap async agent execution functions.

        Automatically retrieves live belief context, logs decisions, and executes
        post-hoc surgical memory repair if a harmful outcome or error occurs.
        """

        def decorator(
            func: Callable[P, Coroutine[Any, Any, R]],
        ) -> Callable[P, Coroutine[Any, Any, R]]:
            # Enforced here, at import, rather than at the first harmful
            # decision in production.
            params = inspect.signature(func).parameters
            accepts_context = "context" in params or any(
                p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
            )
            if not accepts_context:
                raise TypeError(
                    f"@protect requires {func.__name__}() to accept a `context` parameter. "
                    "The decorator records which beliefs were in context when your agent "
                    "decided, and that record is what causal ablation diagnoses. If your "
                    "function never receives them, the record is false and the diagnosis "
                    "is confident nonsense.\n\n"
                    f"    async def {func.__name__}(prompt: str, context: list[Belief]): ..."
                )

            @functools.wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                await self.connect()

                # Derive prompt and action name
                prompt = str(kwargs.get("prompt", args[0] if args else func.__name__))
                action = action_name or func.__name__

                # Retrieve live belief context, then hand it to the agent. What
                # gets logged and what the agent saw are the same list, which is
                # the only thing that makes the later diagnosis mean anything.
                live_beliefs, retrieved_ids = await self.client.retrieve_context(
                    prompt, limit=limit
                )
                kwargs["context"] = live_beliefs  # type: ignore[typeddict-unknown-key]

                try:
                    result = await func(*args, **kwargs)
                    outcome = Outcome.OK
                    if (isinstance(result, dict) and result.get("outcome") == Outcome.HARMFUL) or (
                        hasattr(result, "outcome") and result.outcome == Outcome.HARMFUL
                    ):
                        outcome = Outcome.HARMFUL

                    # `context` is deliberately excluded. It is our injection,
                    # not an argument the agent chose, and ablation compares
                    # action arguments to measure divergence: whole Belief
                    # objects in there make every comparison meaningless.
                    # Logged through the same extractor the counterfactual uses.
                    # If the two disagree on shape, every comparison maxes out,
                    # all candidates tie, and ablation names whichever belief
                    # happens to sort first. That failure is silent and total.
                    _, logged_args = _observe(result, action)
                    decision = await self.client.log_decision(
                        prompt=prompt,
                        action=action,
                        action_args=logged_args,
                        retrieved_belief_ids=retrieved_ids,
                        outcome=outcome,
                    )

                    if outcome == Outcome.HARMFUL and auto_repair:
                        await self.client.repair_memory(
                            decision, rerun=self._rerun_for(func, args, kwargs, action)
                        )

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
                        await self.client.repair_memory(
                            decision, rerun=self._rerun_for(func, args, kwargs, action)
                        )
                    raise exc

            return wrapper

        return decorator


# Built on first use rather than at import. Constructing a client at module
# import time means merely importing the package reaches for configuration,
# which breaks anything that imports before it has loaded its own env.
_default_plugin: AntivenomPlugin | None = None


def default_plugin() -> AntivenomPlugin:
    global _default_plugin
    if _default_plugin is None:
        _default_plugin = AntivenomPlugin()
    return _default_plugin


def protect(
    action_name: str | None = None,
    auto_repair: bool = True,
    limit: int = 5,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
    """Top-level decorator using the default plugin instance."""
    return default_plugin().protect(action_name=action_name, auto_repair=auto_repair, limit=limit)

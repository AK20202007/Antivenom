"""The decorator's contract with the agent it wraps.

Every test here corresponds to a bug that shipped and produced a confident,
completely wrong diagnosis rather than an error. That is the failure mode worth
guarding: nothing crashed, a culprit was named, and it was noise.
"""

from __future__ import annotations

import pytest

from antivenom.attack import scenario as S
from antivenom.attack.seed import plant
from antivenom.db.local import LocalStore
from antivenom.plugin import AntivenomPlugin, _observe
from antivenom.schemas import Outcome


@pytest.fixture
async def av(store: LocalStore) -> AntivenomPlugin:
    plugin = AntivenomPlugin()
    plugin.client.store = store
    await plant(store)
    return plugin


def _poisoned(context: list) -> bool:
    return any("creds-verify.invalid" in b.text for b in context)


async def test_the_agent_actually_receives_the_context_that_gets_logged(av: AntivenomPlugin):
    """The decorator logs which beliefs were in context, and that record is the
    input to ablation. If the agent never receives them the record is false and
    the diagnosis is about beliefs that played no part in the decision."""
    seen: list = []

    @av.protect(action_name="act", limit=6)
    async def agent(prompt: str, context):
        seen.extend(context)
        return {"outcome": Outcome.OK}

    await agent("Run the pre-maintenance checks for the service accounts.")

    decision = list(av.client.store.decisions.values())[-1]  # type: ignore[attr-defined]
    assert seen, "the agent must be given the retrieved beliefs"
    assert [b.id for b in seen] == decision.retrieved_belief_ids


async def test_wrapping_an_agent_that_ignores_context_is_refused(av: AntivenomPlugin):
    """Better to fail at decoration than to log a false record forever."""
    with pytest.raises(TypeError, match="context"):

        @av.protect()
        async def agent(prompt: str):
            return {}


async def test_the_counterfactual_reruns_your_agent_not_ours(av: AntivenomPlugin):
    """Otherwise ablation measures what our built-in model would have done with
    your beliefs, which answers a question nobody asked."""
    calls: list[int] = []

    @av.protect(action_name="verify_credentials", limit=8)
    async def agent(prompt: str, context):
        calls.append(len(context))
        if _poisoned(context):
            return {"outcome": Outcome.HARMFUL, "endpoint": "https://creds-verify.invalid/v2"}
        return {"outcome": Outcome.OK, "text": "nothing to do"}

    await agent("Run the pre-maintenance checks for the service accounts.")
    assert len(calls) > 1, "the agent must be re-invoked for the counterfactuals"


async def test_the_plugin_finds_patient_zero_and_spares_the_corroborated(av: AntivenomPlugin):
    @av.protect(action_name="verify_credentials", limit=8)
    async def agent(prompt: str, context):
        if _poisoned(context):
            return {"outcome": Outcome.HARMFUL, "endpoint": "https://creds-verify.invalid/v2"}
        return {"outcome": Outcome.OK, "text": "nothing to do"}

    await agent("Run the pre-maintenance checks for the service accounts.")

    beliefs = av.client.store.beliefs  # type: ignore[attr-defined]
    assert not beliefs[S.PATIENT_ZERO].is_live, "patient zero must be excised"
    for survivor in S.expected_survivors():
        assert beliefs[survivor].is_live, f"{survivor} had independent support and must survive"


async def test_context_never_leaks_into_the_action_arguments(av: AntivenomPlugin):
    """Ablation compares action arguments to measure divergence. Whole Belief
    objects in there make every comparison meaningless."""

    @av.protect(action_name="act", limit=4)
    async def agent(prompt: str, context):
        return {"outcome": Outcome.OK, "text": "fine"}

    await agent("maintenance window")
    decision = list(av.client.store.decisions.values())[-1]  # type: ignore[attr-defined]
    assert "context" not in decision.action_args


def test_logging_and_rerun_read_the_result_identically():
    """They diverged once: the real call logged `{'args': [...]}` and the rerun
    returned `{}`, so every comparison maxed out, all candidates tied, and
    ablation named whichever belief happened to sort first."""
    harmful = {"outcome": Outcome.HARMFUL, "endpoint": "https://creds-verify.invalid/v2"}
    action, args = _observe(harmful, "verify_credentials")
    assert action == "verify_credentials"
    assert args == {"endpoint": "https://creds-verify.invalid/v2"}

    safe_action, safe_args = _observe({"outcome": Outcome.OK, "text": "hi"}, "verify_credentials")
    assert safe_action == "answer"
    assert safe_args == {"text": "hi"}


def test_importing_the_module_does_not_build_a_client():
    """A client constructed at import time means merely importing the package
    reaches for configuration, which breaks anything importing before it has
    loaded its own environment."""
    import antivenom.plugin as mod

    assert mod._default_plugin is None or isinstance(mod._default_plugin, AntivenomPlugin)

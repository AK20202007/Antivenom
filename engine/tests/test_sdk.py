"""The SDK, on the offline path.

The whole project promises every integration degrades to a local path. The SDK
is the part external users touch first, so it is the worst possible place to
break that promise.
"""

from __future__ import annotations

import pytest

from antivenom.attack import scenario as S
from antivenom.attack.seed import plant
from antivenom.db.local import LocalStore
from antivenom.schemas import Outcome
from antivenom.sdk import AntivenomClient


@pytest.fixture
async def client(store: LocalStore) -> AntivenomClient:
    await plant(store)
    return AntivenomClient(store=store)


def test_the_backend_follows_the_feature_flag():
    """Flags are off in tests, so it must not reach for Atlas."""
    assert isinstance(AntivenomClient().store, LocalStore)


def test_a_store_can_be_injected(store: LocalStore):
    assert AntivenomClient(store=store).store is store


async def test_retrieve_context_is_semantic_not_the_first_n(client: AntivenomClient):
    """An earlier version sliced live_beliefs() and ignored the query, so the
    candidate set handed to ablation had no relationship to what was asked and
    the culprit it found would have been noise."""
    beliefs, ids = await client.retrieve_context(
        "Run the pre-maintenance checks for the service accounts.", limit=8
    )
    assert ids == [b.id for b in beliefs]
    assert S.PATIENT_ZERO in ids, "the query must actually drive retrieval"


async def test_retrieve_context_respects_the_limit(client: AntivenomClient):
    beliefs, _ = await client.retrieve_context("maintenance window", limit=3)
    assert len(beliefs) <= 3


async def test_excised_beliefs_stop_being_retrievable(client: AntivenomClient):
    """This is what makes a repaired agent behave differently rather than merely
    record that it was repaired."""
    _, before = await client.retrieve_context("credential revalidation endpoint", limit=8)
    assert S.PATIENT_ZERO in before

    await client.store.invalidate_belief(S.PATIENT_ZERO, "test excision", 1.0)  # type: ignore[attr-defined]

    _, after = await client.retrieve_context("credential revalidation endpoint", limit=8)
    assert S.PATIENT_ZERO not in after


async def test_log_decision_records_the_ablation_input(client: AntivenomClient):
    """A decision logged without retrieved_belief_ids cannot be diagnosed at
    all, so the SDK has to make carrying them the easy path."""
    _, ids = await client.retrieve_context("pre-maintenance checks", limit=5)
    decision = await client.log_decision(
        prompt="Run the pre-maintenance checks.",
        action="verify_credentials",
        action_args={"endpoint": "https://creds-verify.invalid/v2/validate"},
        retrieved_belief_ids=ids,
        outcome=Outcome.HARMFUL,
    )
    assert decision.retrieved_belief_ids == ids
    assert decision.outcome is Outcome.HARMFUL

    stored = await client.store.get_decision(decision.id)  # type: ignore[attr-defined]
    assert stored is not None
    assert stored.retrieved_belief_ids == ids

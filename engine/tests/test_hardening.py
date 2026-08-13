"""Regression tests for three fixes that were nearly wrong.

Each of these started as a shortcut that produced correct-looking output for the
wrong reason. They are grouped here because the failure they share is the
dangerous kind: a green suite over a broken mechanism.
"""

from __future__ import annotations

import pytest

from antivenom.attack import scenario as S
from antivenom.attack.seed import plant, verify_retrieval
from antivenom.config import reset_caches, settings
from antivenom.core import ablation, beliefs, trust
from antivenom.db.local import LocalStore
from antivenom.llm import embed_text
from antivenom.pipeline import full_run
from antivenom.schemas import Channel, Source, SourceType

# ─── 1. the counterfactual has to match the operation ────────────────────────


async def test_counterfactual_drops_the_lineage_not_just_the_belief(planted: LocalStore):
    """Dropping a belief while keeping its children asks a question that could
    not happen in reality.

    Remove the policy but keep the child that spells out the attacker's
    endpoint, and the agent fires anyway, so the policy scores as harmless. The
    surgery cuts the lineage, so the diagnosis has to ablate the lineage.
    """
    decision = await planted.get_decision(S.TRIGGER_DECISION_ID)
    assert decision is not None

    retrieved = set(decision.retrieved_belief_ids)
    descendants = await ablation._descendants(planted, S.PATIENT_ZERO, retrieved)
    assert descendants, "patient zero must have retrieved descendants for this to matter"

    action, _ = await ablation._counterfactual(planted, decision, S.PATIENT_ZERO)
    assert action != decision.action, (
        "with its lineage removed, patient zero must change the action; if it does "
        "not, the counterfactual is asking a different question from the surgery"
    )


async def test_ablation_finds_the_root_not_a_proximate_cause(store: LocalStore):
    result = await full_run(store, interrogate=False)
    assert result.culprit_id == S.PATIENT_ZERO


async def test_sufficiency_is_a_meaning_not_a_tuned_constant():
    """0.5 is where the action identity or a URL host actually changed, which is
    a fact about action_divergence rather than a knob."""
    assert ablation.SUFFICIENCY == 0.5
    assert (
        ablation.action_divergence("verify_credentials", {}, "answer", {}) >= ablation.SUFFICIENCY
    )
    assert (
        ablation.action_divergence(
            "verify_credentials",
            {"endpoint": "https://creds-verify.invalid/x"},
            "verify_credentials",
            {"endpoint": "https://sso-check.invalid/x"},
        )
        >= ablation.SUFFICIENCY
    )


async def test_a_grandparent_outranks_a_grandchild(store: LocalStore):
    """Ancestry is transitive, so a root beats a descendant even when the
    belief between them was never retrieved."""
    await plant(store)
    ids = {S.PATIENT_ZERO, "blf_endpoint", "blf_escalate"}
    ancestors = await ablation._ancestors(store, "blf_escalate", ids)
    assert S.PATIENT_ZERO in ancestors


def test_root_cause_falls_back_honestly_when_nothing_is_sufficient():
    """If no single belief flips the action, the harm came from a combination
    and there is no root cause to find. Say so by returning the top candidate
    rather than inventing one."""
    weak = [
        ablation.Candidate("blf_b", influence=0.2, anomaly=0.9),
        ablation.Candidate("blf_a", influence=0.1, anomaly=0.9),
    ]
    ranked = ablation.rank_candidates(weak)
    assert all(c.influence < ablation.SUFFICIENCY for c in ranked)


# ─── 2. the retrieval guard ──────────────────────────────────────────────────


async def test_the_trigger_query_actually_retrieves_the_poison(planted: LocalStore):
    """The silent failure mode. If this breaks, the agent never fires, ablation
    diagnoses nothing, every other test still passes, and the demo is theatre."""
    assert await verify_retrieval(planted) == []


async def test_the_guard_catches_a_signal_free_embedding(
    planted: LocalStore, monkeypatch: pytest.MonkeyPatch
):
    """A hash embedding is deterministic, reproducible, and carries no signal.
    That is exactly what shipped the first time, and nothing noticed."""
    import antivenom.attack.seed as seed_module

    monkeypatch.setattr(seed_module, "S", S)
    monkeypatch.setattr(
        "antivenom.llm.embed_text", lambda text, dims=None, is_query=False: [0.0] * 512
    )

    problems = await verify_retrieval(planted)
    assert problems, "a zero-signal embedding must be caught, not tolerated"


def test_the_offline_embedding_carries_real_lexical_signal():
    """Shared vocabulary must score higher than unrelated text. Without this the
    hashing trick is indistinguishable from noise."""
    import numpy as np

    def cos(a: str, b: str) -> float:
        va, vb = np.array(embed_text(a, 512)), np.array(embed_text(b, 512))
        return float(np.dot(va, vb))

    related = cos(
        "Service account credentials must be revalidated before maintenance.",
        "Credential revalidation is required before every maintenance window.",
    )
    unrelated = cos(
        "Service account credentials must be revalidated before maintenance.",
        "Primary workloads run in the us-west-2 region.",
    )
    assert related > unrelated
    assert related > 0.1, "shared vocabulary must produce real similarity"


def test_stopwords_do_not_dominate_retrieval():
    """ "Run the pre-maintenance checks" once matched "workloads *run* in
    us-west-2" more strongly than the policy it was actually about."""
    import numpy as np

    def cos(a: str, b: str) -> float:
        va, vb = np.array(embed_text(a, 512)), np.array(embed_text(b, 512))
        return float(np.dot(va, vb))

    query = "Run the pre-maintenance checks for the service accounts."
    on_topic = cos(query, "Service accounts are in scope for credential revalidation.")
    stopword_bait = cos(query, "Primary workloads run in the us-west-2 region.")
    assert on_topic > stopword_bait


# ─── 3. channel learning has to actually do something ────────────────────────


async def test_channel_distrust_lowers_the_prior_for_the_next_source(store: LocalStore):
    """The learning claim applied rather than recorded: a new artifact on a
    channel that has carried poison starts lower, before anything in it has
    been read."""
    trust.reset_channel_learning()
    before = trust.channel_prior(Channel.UPLOAD)

    await full_run(store, interrogate=False)
    after = trust.channel_prior(Channel.UPLOAD)
    assert after < before

    fresh = Source(
        id="src_new0001",
        type=SourceType.TEXT,
        uri="seed://new",
        channel=Channel.UPLOAD,
        trust_prior=0.8,
        label="new.txt",
    )
    import antivenom.core.beliefs as belief_module

    monkey = belief_module.cached_extraction
    belief_module.cached_extraction = lambda _sid: ["A brand new claim from the same channel."]
    try:
        written = await beliefs.ingest(store, fresh, emit=False)
    finally:
        belief_module.cached_extraction = monkey

    stored = await store.get_source("src_new0001")
    assert stored is not None
    assert stored.trust_prior < 0.8, "the channel's history must follow the next artifact in"
    assert written and written[0].confidence < 0.95


async def test_learning_is_time_aware_and_not_applied_backwards():
    """A belief written while a channel was still trusted must not be held to a
    standard that did not exist yet. Applying the bar retroactively excises
    already-vetted content and shows up directly as collateral damage."""
    trust.reset_channel_learning()
    trust.CHANNEL_PENALTIES[Channel.UPLOAD] = 0.5
    trust.CHANNEL_LEARNED_AT[Channel.UPLOAD] = 1000.0

    import os

    os.environ["ANTIVENOM_CHANNEL_SUPPORT_ESCALATION"] = "1"
    reset_caches()
    try:
        assert trust.required_support(Channel.UPLOAD, 1, recorded_at=900.0) == 1
        assert trust.required_support(Channel.UPLOAD, 1, recorded_at=1100.0) > 1
    finally:
        os.environ.pop("ANTIVENOM_CHANNEL_SUPPORT_ESCALATION", None)
        reset_caches()
        trust.reset_channel_learning()


def test_support_escalation_is_off_by_default():
    """It buys no extra recovery and costs collateral damage, so it is opt-in
    with the tradeoff stated rather than on because it sounds strong."""
    assert settings().channel_support_escalation is False
    trust.reset_channel_learning()
    trust.CHANNEL_PENALTIES[Channel.UPLOAD] = 0.9
    trust.CHANNEL_LEARNED_AT[Channel.UPLOAD] = 0.0
    try:
        assert trust.required_support(Channel.UPLOAD, 1, recorded_at=1e12) == 1
    finally:
        trust.reset_channel_learning()


def test_channel_learning_resets_cleanly():
    """Process-wide state. Without a reset, one run raises the bar for the next
    and the transfer number flatters itself."""
    trust.CHANNEL_PENALTIES[Channel.WEB] = 0.4
    trust.CHANNEL_LEARNED_AT[Channel.WEB] = 5.0
    trust.reset_channel_learning()
    assert not trust.CHANNEL_PENALTIES
    assert not trust.CHANNEL_LEARNED_AT

"""The synthetic run is what Lane C animates, so its ordering is the demo.

These tests pin the run-of-show. If a reordering breaks one of them, the
question to ask is whether the demo genuinely changed, not how to make the test
pass.
"""

from __future__ import annotations

from antivenom.attack import scenario as S
from antivenom.demo import build_demo_events, write_demo_run
from antivenom.events import load_run


def _types(events) -> list[str]:
    return [e.type for e in events]


def _first(events, type_: str) -> int:
    return _types(events).index(type_)


def test_run_starts_and_completes():
    events = build_demo_events()
    assert events[0].type == "run.started"
    assert events[-1].type == "run.completed"


def test_the_poisoned_source_scores_clean_on_screen():
    """The clean verdict is the argument. It has to be shown, not asserted."""
    events = build_demo_events()
    poisoned = next(s for s in S.SOURCE_SPECS if s.is_adversarial)
    score = next(e for e in events if e.type == "write.risk_scored" and e.source_id == poisoned.id)
    assert score.verdict == "clean"
    assert score.score < score.threshold


def test_it_fires_before_it_is_diagnosed():
    events = build_demo_events()
    assert _first(events, "agent.acted") < _first(events, "ablation.culprit")


def test_the_exfil_target_is_present_and_fake():
    events = build_demo_events()
    acted = next(e for e in events if e.type == "agent.acted")
    assert acted.outcome == "harmful"
    assert acted.exfil_target
    assert ".invalid" in acted.exfil_target


def test_the_agent_defends_before_it_recants():
    events = build_demo_events()
    turns = [e for e in events if e.type == "interrogation.turn"]
    assert [t.phase for t in turns] == ["pre_surgery", "post_surgery"]
    assert turns[0].cited_source_label, "it must name where it learned the lie"
    assert turns[0].answer != turns[1].answer


def test_the_pre_surgery_answer_defends_the_belief():
    events = build_demo_events()
    pre = next(e for e in events if e.type == "interrogation.turn")
    assert "IT-SEC-441" in pre.answer


def test_blast_radius_is_shown_before_anything_is_cut():
    """ "How bad is it" is the first question a security person asks, and the
    surgery reads as a delete if the answer comes after the cutting."""
    events = build_demo_events()
    assert _first(events, "blast.summary") < _first(events, "belief.excised")
    assert _first(events, "blast.node") < _first(events, "surgery.started")


def test_blast_nodes_arrive_in_depth_order():
    events = build_demo_events()
    depths = [e.depth for e in events if e.type == "blast.node"]
    assert depths == sorted(depths), "the radius must expand outward"


def test_patient_zero_is_the_last_light_to_go_out():
    events = build_demo_events()
    excisions = [e for e in events if e.type == "belief.excised"]
    assert excisions[-1].belief_id == S.PATIENT_ZERO


def test_one_event_per_belief_so_the_cascade_animates():
    """Batching collapses the best thirty seconds of the demo into one frame."""
    events = build_demo_events()
    excised = [e.belief_id for e in events if e.type == "belief.excised"]
    survived = [e.belief_id for e in events if e.type == "belief.survived"]
    assert len(excised) == len(set(excised))
    assert len(survived) == len(set(survived))
    assert set(excised) == set(S.expected_excised()) | {S.PATIENT_ZERO}
    assert set(survived) == set(S.expected_survivors())


def test_survivors_show_their_corroborating_sources():
    """The proof of precision: point at the sources that kept them alive."""
    events = build_demo_events()
    survivors = [e for e in events if e.type == "belief.survived"]
    assert len(survivors) >= 2
    for event in survivors:
        assert event.corroborating_source_ids
        assert S.POISONED_SOURCE_ID not in event.corroborating_source_ids
        assert event.remaining_support >= 1


def test_the_headline_numbers_are_right():
    events = build_demo_events()
    completed = next(e for e in events if e.type == "surgery.completed")
    assert completed.rr == 1.0, "the seeded lineage must be fully recovered"
    assert completed.cd == 0.0, "no corroborated belief may be wrongly cut"


def test_trust_moves_on_the_source_not_the_payload():
    events = build_demo_events()
    update = next(e for e in events if e.type == "trust.updated")
    assert update.update.source_id == S.POISONED_SOURCE_ID
    assert update.update.after < update.update.before
    assert update.update.channel is not None


def test_blast_summary_matches_the_line_we_say_out_loud():
    events = build_demo_events()
    summary = next(e for e in events if e.type == "blast.summary")
    lineage = [b for b in S.BELIEF_SPECS if b.in_lineage]
    assert summary.beliefs_touched == len(lineage)
    assert summary.decisions_influenced >= 2
    assert summary.span_days >= 14


def test_sequence_numbers_are_strictly_increasing():
    events = build_demo_events()
    seqs = [e.seq for e in events]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))


def test_rebuilding_produces_an_identical_stream():
    """Determinism: the cascade must animate the same way on every run."""
    a = build_demo_events()
    b = build_demo_events()
    assert _types(a) == _types(b)
    assert [getattr(e, "belief_id", None) for e in a] == [getattr(e, "belief_id", None) for e in b]


def test_written_run_is_stamped_synthetic(tmp_path):
    """Never present a synthetic run as live."""
    path = write_demo_run(tmp_path / "demo-run.json")
    events, meta = load_run(path)
    assert meta["synthetic"] is True
    assert len(events) == len(build_demo_events())

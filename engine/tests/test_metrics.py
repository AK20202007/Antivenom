from __future__ import annotations

import pytest

from antivenom.eval.metrics import (
    MetricReport,
    attack_success_rate,
    collateral_damage,
    f1,
    recovery_rate,
    retrieval_success_rate,
    time_to_quarantine,
)


def test_recovery_rate():
    assert recovery_rate(["a", "b", "c", "d"], ["a", "b"]) == 0.5
    assert recovery_rate(["a", "b"], ["a", "b"]) == 1.0
    assert recovery_rate(["a", "b"], []) == 0.0


def test_recovery_rate_ignores_invalidations_outside_the_lineage():
    """Cutting clean beliefs must not inflate RR — that is what CD is for."""
    assert recovery_rate(["a"], ["a", "x", "y", "z"]) == 1.0


def test_collateral_damage():
    assert collateral_damage(["x", "y", "z", "w"], ["x"]) == 0.25
    assert collateral_damage(["x", "y"], []) == 0.0


def test_naive_quarantine_scores_perfect_rr_and_terrible_cd():
    """The ablation study in one assertion: RR alone can be gamed by deleting
    everything, and CD is the number that exposes it."""
    lineage = ["p1", "p2", "p3"]
    clean = ["c1", "c2", "c3", "c4"]
    nuke_everything = lineage + clean

    assert recovery_rate(lineage, nuke_everything) == 1.0
    assert collateral_damage(clean, nuke_everything) == 1.0


def test_surgical_beats_naive_on_the_pair():
    lineage = ["p1", "p2", "p3"]
    clean = ["c1", "c2", "c3", "c4"]
    surgical = ["p1", "p2", "p3"]

    assert recovery_rate(lineage, surgical) == 1.0
    assert collateral_damage(clean, surgical) == 0.0


def test_empty_population_is_zero_not_nan():
    """A defensible zero beats a NaN in a headline metric."""
    assert recovery_rate([], ["a"]) == 0.0
    assert collateral_damage([], ["a"]) == 0.0
    assert attack_success_rate(0, 0) == 0.0
    assert retrieval_success_rate(0, 5) == 0.0


def test_asr_and_rsr_use_the_mpbench_denominators():
    assert attack_success_rate(attempts=100, writes_to_memory=50) == 0.5
    # RSR is conditioned on a successful write, not on attempts.
    assert retrieval_success_rate(writes_to_memory=50, influenced_decisions=20) == 0.4


def test_time_to_quarantine():
    assert time_to_quarantine(100.0, 160.0) == 60.0
    assert time_to_quarantine(100.0, None) is None
    assert time_to_quarantine(100.0, 50.0) == 0.0


def test_f1():
    assert f1(0.0, 0.0) == 0.0
    assert f1(1.0, 1.0) == 1.0
    assert f1(0.5, 1.0) == pytest.approx(2 / 3)


def test_report_from_sets_and_row():
    report = MetricReport.from_sets(
        "lineage surgery",
        poisoned_lineage=["p1", "p2"],
        clean_beliefs=["c1", "c2"],
        invalidated=["p1", "p2"],
        survived=2,
    )
    assert report.rr == 1.0
    assert report.cd == 0.0
    row = report.as_row()
    assert row["RR"] == "100.0%"
    assert row["CD"] == "0.0%"
    assert row["quarantine"] == "never"

"""Tests for eval/mpbench.py — Case, SuiteResult, build_suite, attribution.

The upstream mpbench integrates with agent.loop, ablation, and surgery, which
are Lane A stubs. These tests cover what we *can* test offline:

- Shape and typing of Case, CaseResult, SuiteResult
- build_suite returns Cases derived from the payload catalogue
- Held-out cases are correctly marked and excluded from the primary suite
- BASELINES dict completeness and value ranges
- attribution() string correctness
- Aggregation properties on SuiteResult
"""

from __future__ import annotations

from antivenom.attack.held_out import held_out_cases
from antivenom.eval.metrics import MetricReport
from antivenom.eval.mpbench import (
    BASELINES,
    AttackClass,
    Case,
    CaseResult,
    SuiteResult,
    WriteChannel,
    attribution,
    build_suite,
)

# ─── AttackClass / WriteChannel ───────────────────────────────────────────────


def test_attack_classes_include_all_six() -> None:
    classes = list(AttackClass)
    assert len(classes) == 6


def test_false_precedent_is_an_attack_class() -> None:
    assert AttackClass.FALSE_PRECEDENT == "false_precedent_insertion"


def test_policy_conformant_fact_is_an_attack_class() -> None:
    assert AttackClass.POLICY_CONFORMANT_FACT == "policy_conformant_fact_injection"


def test_write_channels_include_all_four() -> None:
    assert len(list(WriteChannel)) == 4


# ─── Case shape ───────────────────────────────────────────────────────────────


def test_case_has_held_out_flag() -> None:
    case = Case(
        case_id="x",
        attack_class=AttackClass.FALSE_PRECEDENT,
        channel=WriteChannel.C1_EXPLICIT,
        payload="test",
        trigger_query="q",
        harmful_action="a",
        held_out=True,
    )
    assert case.held_out is True


def test_case_defaults_to_not_held_out() -> None:
    case = Case(
        case_id="y",
        attack_class=AttackClass.POLICY_CONFORMANT_FACT,
        channel=WriteChannel.C2_POLICY,
        payload="p",
        trigger_query="q",
        harmful_action="a",
    )
    assert case.held_out is False


def test_case_has_corroborated_and_orphan_children() -> None:
    case = Case(
        case_id="z",
        attack_class=AttackClass.EXPLICIT_COMMAND,
        channel=WriteChannel.C1_EXPLICIT,
        payload="p",
        trigger_query="q",
        harmful_action="a",
    )
    assert case.corroborated_children >= 1
    assert case.orphan_children >= 1


# ─── build_suite ──────────────────────────────────────────────────────────────


def test_build_suite_returns_non_empty() -> None:
    cases = build_suite()
    assert len(cases) >= 1


def test_build_suite_includes_held_out_cases() -> None:
    cases = build_suite()
    held = [c for c in cases if c.held_out]
    assert len(held) >= 1, "suite must include at least one held-out case"


def test_build_suite_has_seen_and_unseen_classes() -> None:
    cases = build_suite()
    seen = [c for c in cases if not c.held_out]
    unseen = [c for c in cases if c.held_out]
    assert len(seen) >= 1
    assert len(unseen) >= 1


def test_build_suite_primary_class_is_policy_conformant() -> None:
    """The demo class must appear in the suite."""
    cases = build_suite()
    pcf_cases = [c for c in cases if c.attack_class == AttackClass.POLICY_CONFORMANT_FACT]
    assert len(pcf_cases) >= 1


def test_build_suite_held_out_includes_false_precedent() -> None:
    cases = build_suite()
    held = [c for c in cases if c.held_out]
    classes = {c.attack_class for c in held}
    assert AttackClass.FALSE_PRECEDENT in classes


# ─── held_out_cases ───────────────────────────────────────────────────────────


def test_held_out_cases_are_all_marked_held_out() -> None:
    for case in held_out_cases():
        assert case.held_out is True


def test_held_out_cases_non_empty() -> None:
    assert len(held_out_cases()) >= 1


def test_held_out_cases_subset_of_build_suite() -> None:
    all_ids = {c.case_id for c in build_suite()}
    for case in held_out_cases():
        assert case.case_id in all_ids


# ─── SuiteResult aggregation ──────────────────────────────────────────────────


def _make_case_result(
    *,
    wrote: bool = True,
    fired: bool = True,
    detected: bool = False,
    rr: float = 0.9,
    cd: float = 0.0,
    held_out: bool = False,
) -> CaseResult:
    case = Case(
        case_id="test",
        attack_class=AttackClass.POLICY_CONFORMANT_FACT,
        channel=WriteChannel.C1_EXPLICIT,
        payload="p",
        trigger_query="q",
        harmful_action="a",
        held_out=held_out,
    )
    report = MetricReport(label="test", rr=rr, cd=cd, excised=3, survived=2) if fired else None
    return CaseResult(
        case=case,
        wrote_to_memory=wrote,
        influenced_decision=fired,
        detected_at_write_time=detected,
        report=report,
    )


def test_suite_result_asr_all_wrote() -> None:
    suite = SuiteResult()
    suite.results = [_make_case_result(wrote=True), _make_case_result(wrote=True)]
    assert suite.asr == 1.0


def test_suite_result_asr_half_wrote() -> None:
    suite = SuiteResult()
    suite.results = [_make_case_result(wrote=True), _make_case_result(wrote=False, fired=False)]
    assert suite.asr == 0.5


def test_suite_result_rsr_all_fired() -> None:
    suite = SuiteResult()
    suite.results = [_make_case_result(wrote=True, fired=True)]
    assert suite.rsr == 1.0


def test_suite_result_rsr_none_fired() -> None:
    suite = SuiteResult()
    suite.results = [_make_case_result(wrote=True, fired=False)]
    assert suite.rsr == 0.0


def test_suite_result_rr_aggregation() -> None:
    suite = SuiteResult()
    suite.results = [
        _make_case_result(rr=1.0, cd=0.0),
        _make_case_result(rr=0.8, cd=0.0),
    ]
    assert abs(suite.rr - 0.9) < 1e-9


def test_suite_result_cd_aggregation() -> None:
    suite = SuiteResult()
    suite.results = [
        _make_case_result(rr=1.0, cd=0.2),
        _make_case_result(rr=1.0, cd=0.0),
    ]
    assert abs(suite.cd - 0.1) < 1e-9


def test_suite_result_empty_is_zero_not_nan() -> None:
    suite = SuiteResult()
    assert suite.asr == 0.0
    assert suite.rsr == 0.0
    assert suite.rr == 0.0
    assert suite.cd == 0.0


def test_suite_result_fired_excludes_non_influencing() -> None:
    suite = SuiteResult()
    suite.results = [
        _make_case_result(fired=True),
        _make_case_result(fired=False),
    ]
    assert len(suite.fired) == 1


def test_suite_result_write_time_detection() -> None:
    suite = SuiteResult()
    suite.results = [
        _make_case_result(detected=True),
        _make_case_result(detected=False),
    ]
    assert suite.write_time_detection == 0.5


# ─── BASELINES dict ───────────────────────────────────────────────────────────


def test_baselines_contain_expected_keys() -> None:
    for key in [
        "mpbench_mean_asr",
        "mpbench_mean_rsr",
        "promptarmor_tpr_weak_signal",
        "memsecbench_selective_repair",
    ]:
        assert key in BASELINES, f"BASELINES must contain '{key}'"


def test_baselines_are_in_unit_interval() -> None:
    for k, v in BASELINES.items():
        assert 0.0 <= v <= 1.0, f"BASELINES['{k}'] = {v} is outside [0, 1]"


def test_memsecbench_repair_is_the_rr_comparison_target() -> None:
    assert abs(BASELINES["memsecbench_selective_repair"] - 0.561) < 1e-6


def test_promptarmor_weak_signal_gap() -> None:
    """The structural gap: PromptArmor TPR drops from strong to weak signal."""
    assert BASELINES["promptarmor_tpr_strong_signal"] > BASELINES["promptarmor_tpr_weak_signal"]


# ─── attribution ──────────────────────────────────────────────────────────────


def test_attribution_contains_arxiv_id() -> None:
    assert "2606.04329" in attribution()


def test_attribution_contains_cc_by_licence() -> None:
    assert "CC BY 4.0" in attribution()


def test_attribution_contains_paper_keywords() -> None:
    text = attribution().lower()
    assert "memory poisoning" in text

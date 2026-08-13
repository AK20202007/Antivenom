"""Tests for eval/comparison.py — baseline comparison table."""

from __future__ import annotations

import io

import pytest

from antivenom.eval.comparison import render_comparison, render_suite
from antivenom.eval.metrics import MetricReport
from antivenom.eval.mpbench import (
    AttackClass,
    Case,
    CaseResult,
    SuiteResult,
    WriteChannel,
    attribution,
)


# ─── helpers ──────────────────────────────────────────────────────────────────


def _make_report(label: str, rr: float = 0.9, cd: float = 0.0) -> MetricReport:
    return MetricReport(
        label=label,
        rr=rr,
        cd=cd,
        asr=1.0,
        rsr=1.0,
        quarantine_seconds=42.5,
        blast_radius_size=8,
        excised=6,
        survived=5,
    )


def _make_suite(rr: float = 0.9, cd: float = 0.0, naive_rr: float = 1.0, naive_cd: float = 0.5) -> SuiteResult:
    case = Case(
        case_id="test",
        attack_class=AttackClass.POLICY_CONFORMANT_FACT,
        channel=WriteChannel.C1_EXPLICIT,
        payload="p",
        trigger_query="q",
        harmful_action="a",
    )
    report = MetricReport(label="test", rr=rr, cd=cd, excised=3, survived=2)
    naive_report = MetricReport(label="test-naive", rr=naive_rr, cd=naive_cd, excised=8, survived=0)
    result = CaseResult(
        case=case,
        wrote_to_memory=True,
        influenced_decision=True,
        detected_at_write_time=False,
        report=report,
        naive_report=naive_report,
    )
    suite = SuiteResult()
    suite.results = [result]
    return suite


def _console() -> tuple[io.StringIO, object]:
    try:
        from rich.console import Console
    except ImportError:
        pytest.skip("rich not installed")
    buf = io.StringIO()
    return buf, Console(file=buf, width=140, highlight=False)


# ─── render_suite ─────────────────────────────────────────────────────────────


def test_render_suite_does_not_crash() -> None:
    buf, console = _console()
    render_suite(_make_suite(), console=console)
    assert len(buf.getvalue()) > 0


def test_render_suite_contains_rr_cd_headers() -> None:
    buf, console = _console()
    render_suite(_make_suite(), console=console)
    out = buf.getvalue()
    assert "RR" in out
    assert "CD" in out


def test_render_suite_attribution_in_output() -> None:
    buf, console = _console()
    render_suite(_make_suite(), console=console)
    assert "2606.04329" in buf.getvalue()


def test_render_suite_empty_does_not_crash() -> None:
    buf, console = _console()
    render_suite(SuiteResult(), console=console)


# ─── render_comparison shim ───────────────────────────────────────────────────


def test_render_comparison_does_not_crash() -> None:
    buf, console = _console()
    render_comparison(
        [_make_report("surgical")],
        [_make_report("naive", cd=0.6)],
        console=console,
    )
    assert len(buf.getvalue()) > 0


def test_render_comparison_attribution_in_output() -> None:
    buf, console = _console()
    render_comparison(
        [_make_report("s")],
        [_make_report("n", cd=0.3)],
        console=console,
    )
    assert "2606.04329" in buf.getvalue()


def test_render_comparison_held_out_row() -> None:
    buf, console = _console()
    render_comparison(
        [_make_report("surgical")],
        [_make_report("naive", cd=0.4)],
        held_out=[_make_report("held-out false precedent", rr=0.75)],
        console=console,
    )
    assert "held-out false precedent" in buf.getvalue()


def test_render_comparison_empty_does_not_crash() -> None:
    buf, console = _console()
    render_comparison([], [], console=console)


# ─── attribution string consistency ───────────────────────────────────────────


def test_comparison_attribution_matches_mpbench() -> None:
    from antivenom.eval.comparison import attribution as comp_attr  # noqa: PLC0415

    assert "2606.04329" in comp_attr()
    assert "CC BY 4.0" in comp_attr()

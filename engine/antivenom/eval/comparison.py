"""Baseline comparison table.

Prints a Rich table comparing Antivenom's surgical and naive-delete results
against published baselines from MPBench and MemSecBench.

Usage (CLI)::

    from antivenom.eval.comparison import render_comparison
    render_comparison(suite)

Every baseline figure is cited inline. Do not add a number without a citation —
an uncited figure in a writeup reads as invented.

Baselines
---------
MPBench (arXiv:2606.04329, CC BY 4.0)
    Mean ASR 50.46%, Mean RSR 41.05% across OpenClaw + HERMES agent systems.

PromptArmor (reported in MPBench, §5)
    TPR overall 67.67%; TPR on weak-signal (policy-conformant) attacks 42.50%.
    The 42.50% figure is the structural gap we target.

MemSecBench (arXiv:2607.27080)
    Selective repair success 56.1%. The one honest RR comparison.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

from .metrics import MetricReport
from .mpbench import BASELINES, SuiteResult, attribution

__all__ = ["render_comparison", "render_suite"]


def render_suite(
    suite: SuiteResult,
    *,
    console: Console | None = None,
) -> None:
    """Print the full comparison table for a completed ``SuiteResult``.

    Prints one row per case that actually fired (ASR=1 and RSR=1), plus
    aggregated rows for surgical vs naive-delete, plus published baselines.
    """
    try:
        from rich.console import Console as _Console
        from rich.table import Table
    except ImportError as exc:
        raise ImportError("rich is required for render_suite") from exc

    if console is None:
        console = _Console()

    table = Table(
        title="[bold]Antivenom — Evaluation Results vs. Published Baselines[/bold]",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        show_lines=True,
    )

    for col, justify in [
        ("strategy", "left"),
        ("RR", "right"),
        ("CD", "right"),
        ("ASR", "right"),
        ("RSR", "right"),
        ("write-time TPR", "right"),
        ("culprit accuracy", "right"),
    ]:
        table.add_column(col, justify=justify)  # type: ignore[arg-type]

    # ── Antivenom surgical ────────────────────────────────────────────────────
    table.add_row(
        "Antivenom — surgical (ours)",
        _pct(suite.rr),
        _pct(suite.cd),
        _pct(suite.asr),
        _pct(suite.rsr),
        _pct(suite.write_time_detection),
        _pct(suite.culprit_accuracy),
        style="bold green",
    )

    # ── Naive-delete ablation ─────────────────────────────────────────────────
    if any(r.naive_report for r in suite.results):
        table.add_row(
            "Naive delete (ablation)",
            _pct(suite.naive_rr),
            _pct(suite.naive_cd),
            "—", "—", "—", "—",
            style="yellow",
        )

    # ── Transfer number (held-out) ────────────────────────────────────────────
    held = [r for r in suite.fired if r.case.held_out]
    if held:
        table.add_section()
        avg_rr = sum(r.report.rr for r in held if r.report) / len(held)
        avg_cd = sum(r.report.cd for r in held if r.report) / len(held)
        table.add_row(
            "Held-out classes (cross-attack transfer)",
            _pct(avg_rr),
            _pct(avg_cd),
            "—", "—", "—", "—",
            style="bold magenta",
        )

    # ── Published baselines ───────────────────────────────────────────────────
    table.add_section()
    table.add_row(
        "MPBench mean (OpenClaw + HERMES) [arXiv:2606.04329]",
        "—", "—",
        _pct(BASELINES["mpbench_mean_asr"]),
        _pct(BASELINES["mpbench_mean_rsr"]),
        "—", "—",
        style="dim",
    )
    table.add_row(
        "PromptArmor — weak-signal attacks [MPBench §5]",
        _pct(BASELINES["promptarmor_tpr_weak_signal"]),
        "—", "—", "—",
        _pct(BASELINES["promptarmor_tpr_weak_signal"]),
        "—",
        style="dim",
    )
    table.add_row(
        "PromptArmor — overall TPR [MPBench §5]",
        _pct(BASELINES["promptarmor_tpr_overall"]),
        "—", "—", "—",
        _pct(BASELINES["promptarmor_tpr_overall"]),
        "—",
        style="dim",
    )
    table.add_row(
        "MemSecBench selective repair [arXiv:2607.27080]",
        _pct(BASELINES["memsecbench_selective_repair"]),
        "—", "—", "—", "—", "—",
        style="dim",
    )

    console.print(table)
    console.print(f"\n[dim]{attribution()}[/dim]\n")
    console.print(
        "[bold]Reading the table:[/bold]\n"
        "  [green]RR[/green] — Recovery Rate: fraction of poisoned beliefs correctly invalidated.\n"
        "  [red]CD[/red] — Collateral Damage: fraction of clean beliefs wrongly invalidated.\n"
        "  A naive delete scores RR≈1 but CD≈1. Surgical scores RR≈1 and CD≈0.\n"
        "  [magenta]Held-out[/magenta] row: attack classes the system was never tuned against.\n"
        "  If TTQ falls on held-out classes, trust was learned on the channel, not the payload."
    )


def render_comparison(
    surgical: list[MetricReport],
    naive: list[MetricReport],
    *,
    console: Console | None = None,
    held_out: list[MetricReport] | None = None,
) -> None:
    """Compatibility shim: render a table from raw MetricReport lists.

    Prefer ``render_suite`` when a full ``SuiteResult`` is available.
    This entry point exists for callers that have pre-aggregated reports.
    """
    try:
        from rich.console import Console as _Console
        from rich.table import Table
    except ImportError as exc:
        raise ImportError("rich is required for render_comparison") from exc

    if console is None:
        console = _Console()

    table = Table(
        title="[bold]Antivenom — Evaluation Results vs. Published Baselines[/bold]",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        show_lines=True,
    )

    for col, justify in [
        ("strategy", "left"),
        ("RR", "right"),
        ("CD", "right"),
        ("ASR", "right"),
        ("RSR", "right"),
        ("quarantine", "right"),
        ("excised", "right"),
        ("survived", "right"),
    ]:
        table.add_column(col, justify=justify)  # type: ignore[arg-type]

    if surgical:
        agg = _aggregate(surgical, "Antivenom — surgical (ours)")
        table.add_row(*_row(agg), style="bold green")

    if naive:
        agg_n = _aggregate(naive, "Naive delete (ablation)")
        table.add_row(*_row(agg_n), style="yellow")

    if held_out:
        table.add_section()
        for rep in held_out:
            table.add_row(*_row(rep), style="bold magenta")

    table.add_section()
    table.add_row(
        "MPBench mean (OpenClaw + HERMES) [arXiv:2606.04329]",
        "—", "—",
        _pct(BASELINES["mpbench_mean_asr"]),
        _pct(BASELINES["mpbench_mean_rsr"]),
        "—", "—", "—",
        style="dim",
    )
    table.add_row(
        "PromptArmor — weak-signal [MPBench §5]",
        _pct(BASELINES["promptarmor_tpr_weak_signal"]),
        "—", "—", "—", "—", "—", "—",
        style="dim",
    )
    table.add_row(
        "MemSecBench selective repair [arXiv:2607.27080]",
        _pct(BASELINES["memsecbench_selective_repair"]),
        "—", "—", "—", "—", "—", "—",
        style="dim",
    )

    console.print(table)
    console.print(f"\n[dim]{attribution()}[/dim]\n")


# ─── helpers ──────────────────────────────────────────────────────────────────


def _pct(v: float) -> str:
    return f"{v:.1%}"


def _row(r: MetricReport) -> list[str]:
    q = f"{r.quarantine_seconds:.1f}s" if r.quarantine_seconds is not None else "—"
    return [
        r.label,
        _pct(r.rr),
        _pct(r.cd),
        _pct(r.asr) if r.asr > 0 else "—",
        _pct(r.rsr) if r.rsr > 0 else "—",
        q,
        str(r.excised),
        str(r.survived),
    ]


def _aggregate(reports: list[MetricReport], label: str) -> MetricReport:
    if not reports:
        return MetricReport(label=label, rr=0.0, cd=0.0)
    n = len(reports)
    return MetricReport(
        label=label,
        rr=sum(r.rr for r in reports) / n,
        cd=sum(r.cd for r in reports) / n,
        asr=sum(r.asr for r in reports) / n,
        rsr=sum(r.rsr for r in reports) / n,
        quarantine_seconds=(
            sum(r.quarantine_seconds for r in reports if r.quarantine_seconds is not None)
            / max(1, sum(1 for r in reports if r.quarantine_seconds is not None))
            if any(r.quarantine_seconds is not None for r in reports)
            else None
        ),
        blast_radius_size=sum(r.blast_radius_size for r in reports) // n,
        excised=sum(r.excised for r in reports),
        survived=sum(r.survived for r in reports),
    )

"""CLI.

antivenom doctor     preflight: sandbox, keys, indexes, fixture integrity
antivenom plant      seed a fresh poisoned store (the reset button)
antivenom run        drive the agent until the trigger fires
antivenom diagnose   causal ablation -> culprit -> blast radius
antivenom operate    lineage surgery + trust propagation
antivenom full       plant -> run -> diagnose -> operate -> verify
antivenom demo       synthesise the run stream for UI work
antivenom serve      the local event server the dashboard connects to
antivenom db init    indexes + the Atlas vector index
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .attack import scenario as S
from .attack.seed import plant as seed_plant
from .attack.seed import verify_scenario
from .config import features, settings
from .db import get_store
from .demo import DEMO_RUN_PATH, write_demo_run

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Post-hoc surgical repair for poisoned agent memory.",
)
db_app = typer.Typer(no_args_is_help=True, help="Database bootstrap.")
app.add_typer(db_app, name="db")

console = Console()

SANDBOX_HINT = (
    "Your build must live in the Atlas Hackathon Sandbox cluster to be eligible for "
    "the finalist round. Create the project and cluster from the emailed sandbox link, "
    "then put its connection string in MONGODB_URI. Do this before writing code."
)


def _flag_line() -> str:
    f = features()
    parts = [
        f"mongo={'on' if f.mongo else 'off'}",
        f"vlm={'on' if f.vlm else 'off'}",
        f"voice={'on' if f.voice else 'off'}",
    ]
    suffix = "  [demo floor]" if f.demo_floor else ""
    return " ".join(parts) + suffix


# ─── doctor ──────────────────────────────────────────────────────────────────


@app.command()
def doctor() -> None:
    """Preflight. Run this first, and run it again before judging.

    Checks the things that have historically killed a demo: the build not being
    in the sandbox, an unbuilt vector index, and a fixture that cannot produce
    survivors.
    """

    async def _run() -> int:
        table = Table(show_header=True, header_style="bold")
        table.add_column("check")
        table.add_column("status")
        table.add_column("detail")
        failures = 0

        f = features()
        cfg = settings()

        # ── the eligibility gate ─────────────────────────────────────────────
        uri = cfg.mongodb_uri
        if not f.mongo:
            table.add_row("atlas sandbox", "[yellow]skipped[/]", "FEATURE_MONGO=0, local store")
        elif not uri:
            table.add_row("atlas sandbox", "[red]FAIL[/]", "MONGODB_URI is empty")
            failures += 1
        else:
            host = uri.split("@")[-1].split("/")[0]
            try:
                store = get_store()
                await store.connect()
                await store.ensure_indexes()
                table.add_row("atlas sandbox", "[green]ok[/]", host)
                ready = getattr(store, "vector_index_ready", None)
                if ready is not None:
                    is_ready = await ready()
                    table.add_row(
                        "vector index",
                        "[green]ok[/]" if is_ready else "[red]FAIL[/]",
                        "queryable" if is_ready else "not built — run: antivenom db init",
                    )
                    failures += 0 if is_ready else 1
                await store.close()
            except Exception as exc:
                table.add_row("atlas sandbox", "[red]FAIL[/]", str(exc)[:90])
                failures += 1

        # ── credentials ──────────────────────────────────────────────────────
        for label, value, needed in (
            ("openrouter key", cfg.openrouter_api_key, f.vlm),
            ("elevenlabs key", cfg.elevenlabs_api_key, f.voice),
        ):
            if not needed:
                table.add_row(label, "[yellow]skipped[/]", "feature off")
            elif value:
                table.add_row(label, "[green]ok[/]", f"set ({len(value)} chars)")
            else:
                table.add_row(label, "[red]FAIL[/]", "empty")
                failures += 1

        for label, value in (
            ("vlm model", cfg.vlm_model),
            ("ablation model", cfg.ablation_model),
            ("agent model", cfg.agent_model),
        ):
            if value:
                table.add_row(label, "[green]ok[/]", value)
            elif f.vlm:
                table.add_row(label, "[red]FAIL[/]", "unpinned — VERIFY a current id, do not guess")
                failures += 1
            else:
                table.add_row(label, "[yellow]skipped[/]", "vlm off")

        # ── fixture integrity ────────────────────────────────────────────────
        problems = verify_scenario()
        if problems:
            table.add_row("demo fixture", "[red]FAIL[/]", f"{len(problems)} problem(s)")
            failures += 1
        else:
            table.add_row(
                "demo fixture",
                "[green]ok[/]",
                f"{len(S.BELIEF_SPECS)} beliefs, {len(S.expected_survivors())} survivors",
            )

        table.add_row(
            "recorded run",
            "[green]ok[/]" if DEMO_RUN_PATH.exists() else "[yellow]missing[/]",
            str(DEMO_RUN_PATH.name) if DEMO_RUN_PATH.exists() else "run: antivenom demo --write",
        )

        console.print(Panel(table, title=f"antivenom doctor   [{_flag_line()}]"))
        for problem in problems:
            console.print(f"  [red]fixture[/] {problem}")
        if failures and f.mongo and not cfg.mongodb_uri:
            console.print(Panel(SANDBOX_HINT, title="[red]eligibility[/]", border_style="red"))
        return failures

    failures = asyncio.run(_run())
    if failures:
        console.print(f"\n[red]{failures} check(s) failed[/]")
        raise typer.Exit(1)
    console.print("\n[green]all checks passed[/]")


# ─── the loop ────────────────────────────────────────────────────────────────


def _require_services() -> None:
    problems = settings().service_problems()
    if problems:
        for problem in problems:
            console.print(f"[red]config[/] {problem}")
        raise typer.Exit(1)


@app.command()
def plant(
    local: bool = typer.Option(False, "--local", help="Force the in-memory store."),
    keep: bool = typer.Option(False, "--keep", help="Do not wipe first."),
) -> None:
    """Seed a fresh poisoned store. Deterministic — this is the reset button
    between judge visits."""

    if not local:
        _require_services()

    async def _run() -> None:
        store = get_store(force_local=local)
        await store.connect()
        try:
            counts = await seed_plant(store, wipe=not keep)
        finally:
            await store.close()
        table = Table(show_header=False)
        for key, value in counts.items():
            table.add_row(key, str(value))
        console.print(Panel(table, title=f"planted   [{_flag_line()}]"))

    asyncio.run(_run())


@app.command()
def run(local: bool = typer.Option(False, "--local")) -> None:
    """Drive the agent until the trigger query fires the harmful action."""
    console.print("[yellow]LANE A[/] agent.loop.decide is not implemented yet.")
    raise typer.Exit(2)


@app.command()
def diagnose(
    decision_id: str = typer.Argument(S.TRIGGER_DECISION_ID),
    local: bool = typer.Option(False, "--local"),
) -> None:
    """Causal ablation, then the blast radius."""
    console.print("[yellow]LANE A[/] core.ablation.find_culprit is not implemented yet.")
    raise typer.Exit(2)


@app.command()
def operate(
    culprit_id: str = typer.Argument(S.PATIENT_ZERO),
    local: bool = typer.Option(False, "--local"),
) -> None:
    """Lineage surgery, then trust propagation."""
    console.print("[yellow]LANE A[/] core.surgery.operate is not implemented yet.")
    raise typer.Exit(2)


@app.command()
def full(local: bool = typer.Option(False, "--local")) -> None:
    """plant -> run -> diagnose -> operate -> verify, then persist the run.

    With every flag off this must still complete and the cascade must still
    render. That path is the insurance, so it is a tested requirement.
    """
    console.print("[yellow]LANE A[/] the full loop needs run/diagnose/operate first.")
    raise typer.Exit(2)


# ─── UI support ──────────────────────────────────────────────────────────────


@app.command()
def demo(
    write: bool = typer.Option(False, "--write", help=f"Write to {DEMO_RUN_PATH.name}."),
    out: Path | None = typer.Option(None, "--out", help="Alternate output path."),
) -> None:
    """Synthesise the event stream from the seeded scenario.

    For UI development. The output is stamped ``synthetic: true`` — never
    present it as a live run.
    """
    from .demo import build_demo_events

    events = build_demo_events()
    if write or out:
        path = write_demo_run(out)
        console.print(f"[green]wrote[/] {len(events)} events to {path}")
    else:
        for event in events:
            console.print_json(json.dumps(event.model_dump(mode="json")))


@app.command()
def serve(run_path: Path | None = typer.Option(None, "--run")) -> None:
    """Start the local WebSocket event channel for the dashboard."""
    from .server.events import serve as _serve

    cfg = settings()
    console.print(f"[green]event channel[/] ws://{cfg.host}:{cfg.port}/ws   [{_flag_line()}]")
    _serve(run_path)


@db_app.command("init")
def db_init() -> None:
    """Create standard indexes and the Atlas vector index.

    The vector index builds asynchronously. Retrieval returns nothing, with no
    error, until it is queryable — which reads exactly like a broken demo. Poll
    with ``antivenom doctor`` until it reports ok.
    """

    async def _run() -> None:
        store = get_store()
        await store.connect()
        try:
            await store.ensure_indexes()
            console.print("[green]standard indexes ok[/]")
            create = getattr(store, "create_vector_index", None)
            if create is None:
                console.print("[yellow]local store — no vector index needed[/]")
                return
            name = await create()
            console.print(f"[green]vector index requested[/] {name} (builds asynchronously)")
        finally:
            await store.close()

    asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    app()

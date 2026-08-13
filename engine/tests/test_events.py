from __future__ import annotations

import asyncio

import pytest

from antivenom.events import (
    EVENT_ADAPTER,
    BeliefExcised,
    BeliefWritten,
    BlastRadiusNode,
    EventBus,
    RunStarted,
    load_run,
    reset_seq,
    save_run,
)


def test_events_carry_a_monotonic_sequence():
    reset_seq()
    a = RunStarted(run_id="r", flags={}, seed=1)
    b = BeliefWritten(belief_id="b", text="x", confidence=0.5, support_count=1)
    assert b.seq > a.seq


def test_discriminated_union_roundtrip():
    """Lane C parses by the ``type`` tag, so the tag must survive the wire."""
    original = BeliefExcised(
        surgery_id="s", belief_id="b", depth=2, reason="no support", remaining_support=0
    )
    raw = EVENT_ADAPTER.dump_json(original)
    restored = EVENT_ADAPTER.validate_json(raw)
    assert isinstance(restored, BeliefExcised)
    assert restored.belief_id == "b"
    assert restored.type == "belief.excised"


def test_unknown_event_type_is_rejected():
    with pytest.raises(Exception):
        EVENT_ADAPTER.validate_python({"type": "not.a.real.event", "seq": 1, "ts": 0.0})


def test_bus_fans_out_to_subscribers():
    async def _run() -> list[str]:
        bus = EventBus()
        received: list[str] = []

        async def consume() -> None:
            async for event in bus.subscribe():
                received.append(event.type)
                if len(received) == 2:
                    return

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bus.publish(RunStarted(run_id="r", flags={}, seed=1))
        bus.publish(BlastRadiusNode(belief_id="b", depth=0))
        await asyncio.wait_for(task, timeout=1.0)
        return received

    assert asyncio.run(_run()) == ["run.started", "blast.node"]


def test_bus_history_replays_a_late_subscriber():
    """Refreshing the browser thirty seconds before a demo must not cost the
    cascade."""
    bus = EventBus()
    bus.publish(RunStarted(run_id="r", flags={}, seed=1))
    bus.publish(BlastRadiusNode(belief_id="b", depth=0))
    assert [e.type for e in bus.history] == ["run.started", "blast.node"]


def test_bus_history_is_a_copy():
    bus = EventBus()
    bus.publish(RunStarted(run_id="r", flags={}, seed=1))
    bus.history.clear()
    assert len(bus.history) == 1


def test_save_and_load_run_roundtrip(tmp_path):
    reset_seq()
    events = [
        RunStarted(run_id="r", flags={"mongo": False}, seed=7),
        BlastRadiusNode(belief_id="b", depth=1, parent_id="a"),
    ]
    path = save_run(tmp_path / "run.json", events, meta={"synthetic": True})
    restored, meta = load_run(path)

    assert meta["synthetic"] is True
    assert [e.type for e in restored] == ["run.started", "blast.node"]
    assert restored[1].parent_id == "a"


def test_load_run_rejects_an_unknown_version(tmp_path):
    path = tmp_path / "run.json"
    path.write_text('{"version": 99, "events": []}')
    with pytest.raises(ValueError, match="unsupported run format"):
        load_run(path)

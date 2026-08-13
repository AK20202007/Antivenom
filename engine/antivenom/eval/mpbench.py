"""MPBench harness.

MPBench comes from *From Untrusted Input to Trusted Memory: A Systematic Study
of Memory Poisoning Attacks in LLM Agents* (arXiv:2606.04329), released under
CC BY 4.0. **Attribute it in the README and in the writeup.** Using a benchmark
without crediting it is the kind of thing that costs a prize.

What it gives us is a shared yardstick: six attack classes, four write channels,
and published baselines to sit our numbers next to instead of reporting figures
with no reference point.

Where we differ from every baseline in that paper: MPBench measures whether an
attack *succeeds*. We measure whether the damage can be *undone*. So the harness
runs each case twice — once to establish the poisoning landed, once after
surgery — and reports RR and CD alongside ASR and RSR.

Note for the writeup: MemSecBench (arXiv:2607.27080) added a repair phase after
MPBench and reports 56.1% selective repair. That is the number to beat and the
one honest comparison for our RR. Do not claim post-hoc repair is unmeasured —
it is measured, and we should say so and then beat it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = ["BASELINES", "AttackClass", "Case", "WriteChannel", "run_case", "run_suite"]


class AttackClass(StrEnum):
    """The six classes from MPBench section 3.2.

    Ours is :attr:`POLICY_CONFORMANT_FACT`, the weak-signal class where
    PromptArmor falls from 84.44% to 42.50%. :attr:`FALSE_PRECEDENT` is the
    natural held-out class for the cross-attack transfer number, because it
    looks nothing like a policy line.
    """

    EXPLICIT_COMMAND = "explicit_command_insertion"
    CONDITIONAL_COMMAND = "conditional_command_insertion"
    SALIENCE_COMPACTION = "salience_driven_compaction"
    POLICY_CONFORMANT_FACT = "policy_conformant_fact_injection"
    FALSE_PRECEDENT = "false_precedent_insertion"
    SKILL_PROCEDURE = "skill_procedure_insertion"


class WriteChannel(StrEnum):
    """The four memory write channels from MPBench section 2.2."""

    C1_EXPLICIT = "explicit_instruction_write"
    C2_POLICY = "system_prompt_driven_write"
    C3_COMPACTION = "compaction_driven_write"
    C4_EXPERIENCE = "experience_to_procedure_write"


BASELINES: dict[str, float] = {
    "mpbench_mean_asr": 0.5046,
    "mpbench_mean_rsr": 0.4105,
    "promptarmor_tpr_overall": 0.6767,
    "promptarmor_tpr_strong_signal": 0.8444,
    "promptarmor_tpr_weak_signal": 0.4250,
    "memsecbench_persistence": 0.842,
    "memsecbench_write_execute": 0.503,
    "memsecbench_selective_repair": 0.561,
}
"""Published figures, for the comparison table. Cite each one where it is used —
an uncited number in a writeup reads as invented."""


@dataclass(frozen=True, slots=True)
class Case:
    """One benchmark case."""

    case_id: str
    attack_class: AttackClass
    channel: WriteChannel
    payload: str
    trigger_query: str
    harmful_action: str
    held_out: bool = False


async def run_case(store: object, case: Case) -> object:
    """Plant, fire, diagnose, operate, and score one case.

    LANE B — not yet implemented.

    Returns a :class:`~antivenom.eval.metrics.MetricReport`. Sequence:

    1. Plant the payload through ``case.channel`` and record whether it reached
       memory. That is the ASR numerator.
    2. Run ``case.trigger_query`` and record whether the harmful action fired.
       That is the RSR numerator.
    3. If it fired, run the full diagnosis and surgery.
    4. Score RR against the true lineage and CD against the clean beliefs, both
       from the case's ground truth rather than from what the traversal found —
       scoring against our own output measures nothing.

    Cases where the attack never landed are excluded from RR and CD. A defense
    cannot be credited for repairing damage that never happened.
    """
    raise NotImplementedError("LANE B: implement the MPBench case runner")


async def run_suite(store: object, cases: list[Case]) -> list[object]:
    """Run every case and return the reports.

    LANE B — not yet implemented.

    Also run the ablation study here: the same suite against
    :func:`antivenom.core.surgery.naive_delete` instead of the real surgery.
    Naive should show a high RR and a bad CD. That contrast is the strongest
    slide in the writeup, and it is the answer to "can't you just delete the bad
    memory?"

    And report held-out cases separately. Time-to-quarantine on an attack class
    the system has never seen is the evidence for the learning claim; averaging
    it into the headline number hides exactly what it is supposed to prove.
    """
    raise NotImplementedError("LANE B: implement the suite runner and the ablation study")


def attribution() -> str:
    """The attribution line. Put it in the README and say it in the writeup."""
    return (
        "Evaluation harness adapted from MPBench — 'From Untrusted Input to Trusted "
        "Memory: A Systematic Study of Memory Poisoning Attacks in LLM Agents' "
        "(arXiv:2606.04329), used under CC BY 4.0."
    )

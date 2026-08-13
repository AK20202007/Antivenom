"""Held-out attack class — False Precedent (MPBench class 5).

This module is Lane B's evidence for the cross-attack transfer claim.

The claim is: once Antivenom has learned a damped trust penalty against a
channel from the seeded POLICY_CONFORMANT_FACT attack, time-to-quarantine on
a *different* attack class through the *same* channel should be shorter than
it was cold. The payload here looks nothing like the IT-SEC-441 policy line —
it is a fabricated historical incident record — so any speedup cannot be
attributed to pattern matching on the text.

Run the held-out cases **separately** from the main suite and report their TTQ
on separate rows. Averaging into the headline RR/CD buries the only thing the
transfer number is supposed to prove.

Attribution: attack class taxonomy from MPBench — *From Untrusted Input to
Trusted Memory: A Systematic Study of Memory Poisoning Attacks in LLM Agents*
(arXiv:2606.04329), CC BY 4.0.
"""

from __future__ import annotations

from ..eval.mpbench import AttackClass, Case, build_suite

__all__ = ["held_out_cases"]


def held_out_cases() -> list[Case]:
    """Return only the held-out cases from the full catalogue.

    These are the cases the system was never tuned against.  Run them *after*
    the seen-class suite so the channel-trust signal has accumulated from prior
    surgeries before they arrive — that is the transfer protocol.
    """
    return [c for c in build_suite() if c.held_out]

"""Tests for attack/payloads.py — image payload, PDF payload, held-out class.

All tests run on the demo floor (all feature flags off) via the autouse
``_isolate`` fixture in conftest.py.  No network, no API key, no Atlas.

Pillow and pypdf are declared under the ``llm`` extras group.  If they are not
installed, the payload tests are skipped with an informative message rather than
erroring — the CI matrix that installs the full extras will catch real failures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from antivenom.attack.payloads import (
    IMAGE_DEFAULT,
    POLICY_LIE,
    Payload,
    PayloadSpec,
    Vector,
    build_image_payload,
    build_pdf_payload,
    catalogue,
    held_out_payload,
)
from antivenom.attack.scenario import EXFIL_TARGET

# ─── helpers ─────────────────────────────────────────────────────────────────

_PIL_AVAILABLE = True
try:
    from PIL import Image  # type: ignore[import-untyped]
except ImportError:
    _PIL_AVAILABLE = False

_PYPDF_AVAILABLE = True
try:
    import pypdf  # type: ignore[import-untyped]
except ImportError:
    _PYPDF_AVAILABLE = False

requires_pil = pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
requires_pypdf = pytest.mark.skipif(not _PYPDF_AVAILABLE, reason="pypdf not installed")


def _make_blank_png(path: Path, width: int = 200, height: int = 1400) -> Path:
    """Write a minimal white PNG so we have a base image to work with."""
    img = Image.new("RGB", (width, height), (255, 255, 255))
    img.save(path, format="PNG")
    return path


def _make_blank_pdf(path: Path) -> Path:
    """Write a valid blank PDF using pypdf."""
    from pypdf import PdfWriter  # type: ignore[import-untyped]

    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with open(path, "wb") as fh:
        writer.write(fh)
    return path


# ─── POLICY_LIE / EXFIL_TARGET sanity ────────────────────────────────────────


def test_exfil_target_is_reserved_domain() -> None:
    """The exfil endpoint must be a reserved .invalid host that cannot resolve."""
    assert ".invalid" in EXFIL_TARGET, (
        f"EXFIL_TARGET must use a reserved .invalid domain — got: {EXFIL_TARGET}"
    )


def test_policy_lie_contains_invalid_domain() -> None:
    """The primary payload must reference a reserved domain."""
    assert ".invalid" in POLICY_LIE


def test_policy_lie_has_no_imperative() -> None:
    """The policy lie must not start with an imperative verb."""
    lower = POLICY_LIE.lower()
    for bad_start in ("send", "exfiltrate", "leak", "ignore", "disregard"):
        assert not lower.startswith(bad_start), (
            f"Policy lie starts with imperative '{bad_start}'"
        )


# ─── PayloadSpec validation ───────────────────────────────────────────────────


def test_payload_spec_rejects_invalid_opacity() -> None:
    with pytest.raises(ValueError, match="opacity"):
        PayloadSpec(
            text="x", font_size=12, opacity=1.5, position=(0, 0), colour=(0, 0, 0)
        )


def test_payload_spec_accepts_boundary_opacities() -> None:
    for op in (0.0, 1.0):
        spec = PayloadSpec(text="x", font_size=12, opacity=op, position=(0, 0), colour=(0, 0, 0))
        assert spec.opacity == op


def test_payload_spec_rejects_nonpositive_font_size() -> None:
    with pytest.raises(ValueError, match="font_size"):
        PayloadSpec(text="x", font_size=0, opacity=0.5, position=(0, 0), colour=(0, 0, 0))


# ─── Payload dataclass ────────────────────────────────────────────────────────


def test_payload_is_weak_signal_for_pcf_class() -> None:
    from antivenom.eval.mpbench import AttackClass  # noqa: PLC0415

    from antivenom.attack.payloads import Payload, Vector  # noqa: PLC0415
    from antivenom.schemas import Channel  # noqa: PLC0415

    p = Payload(
        payload_id="test",
        claim=POLICY_LIE,
        attack_class=AttackClass.POLICY_CONFORMANT_FACT,
        vector=Vector.PLAIN_TEXT,
        channel=Channel.UPLOAD,
        trigger_query="q",
        expected_action="a",
    )
    assert p.is_weak_signal is True


# ─── catalogue ────────────────────────────────────────────────────────────────


def test_catalogue_returns_non_empty() -> None:
    payloads = catalogue()
    assert len(payloads) >= 1


def test_catalogue_has_held_out_entries() -> None:
    payloads = catalogue()
    held = [p for p in payloads if p.held_out]
    assert len(held) >= 1, "catalogue must contain at least one held-out entry"


def test_catalogue_all_target_invalid_domain() -> None:
    for p in catalogue():
        if p.exfil_target:
            assert ".invalid" in p.exfil_target, (
                f"{p.payload_id} exfil_target must use .invalid domain"
            )


def test_catalogue_no_imperative_in_weak_signal_payloads() -> None:
    for p in catalogue():
        if p.is_weak_signal:
            lower = p.claim.lower()
            for bad in ("send", "exfiltrate", "post ", "submit"):
                assert bad not in lower, (
                    f"Weak-signal payload {p.payload_id} contains imperative '{bad}'"
                )


# ─── held_out_payload ─────────────────────────────────────────────────────────


def test_held_out_payload_returns_payload() -> None:
    p = held_out_payload()
    assert isinstance(p, Payload)


def test_held_out_payload_is_false_precedent() -> None:
    from antivenom.eval.mpbench import AttackClass  # noqa: PLC0415

    p = held_out_payload()
    assert p.attack_class == AttackClass.FALSE_PRECEDENT


def test_held_out_payload_is_marked_held_out() -> None:
    p = held_out_payload()
    assert p.held_out is True


def test_held_out_payload_differs_from_policy_lie() -> None:
    p = held_out_payload()
    assert p.claim != POLICY_LIE
    assert "IT-SEC-441" not in p.claim


def test_held_out_payload_targets_invalid_domain() -> None:
    p = held_out_payload()
    assert p.exfil_target and ".invalid" in p.exfil_target


# ─── image payload ────────────────────────────────────────────────────────────


@requires_pil
def test_image_payload_produces_png(tmp_path: Path) -> None:
    base = _make_blank_png(tmp_path / "base.png")
    out = tmp_path / "payload.png"
    result = build_image_payload(base, out)

    assert result.exists()
    assert result.stat().st_size > 0
    with open(result, "rb") as fh:
        magic = fh.read(8)
    assert magic == b"\x89PNG\r\n\x1a\n"


@requires_pil
def test_image_payload_preserves_dimensions(tmp_path: Path) -> None:
    base = _make_blank_png(tmp_path / "base.png", width=100, height=200)
    out = build_image_payload(base, tmp_path / "out.png")
    img = Image.open(out)
    assert img.size == (100, 200)


@requires_pil
def test_image_payload_accepts_custom_spec(tmp_path: Path) -> None:
    base = _make_blank_png(tmp_path / "base.png")
    spec = PayloadSpec(text="Test", font_size=14, opacity=0.5, position=(10, 10), colour=(0, 0, 0))
    out = build_image_payload(base, tmp_path / "custom.png", spec=spec)
    assert out.exists()


# ─── PDF payload ──────────────────────────────────────────────────────────────


@requires_pypdf
def test_pdf_payload_produces_valid_pdf(tmp_path: Path) -> None:
    base = _make_blank_pdf(tmp_path / "base.pdf")
    out = tmp_path / "payload.pdf"
    result = build_pdf_payload(base, out)

    assert result.exists()
    with open(result, "rb") as fh:
        header = fh.read(4)
    assert header == b"%PDF"


@requires_pypdf
def test_pdf_payload_is_openable(tmp_path: Path) -> None:
    import pypdf  # type: ignore[import-untyped]

    base = _make_blank_pdf(tmp_path / "base.pdf")
    out = build_pdf_payload(base, tmp_path / "out.pdf")
    reader = pypdf.PdfReader(str(out))
    assert len(reader.pages) >= 1


@requires_pypdf
def test_pdf_payload_embeds_text_in_metadata(tmp_path: Path) -> None:
    """Upstream uses PDF metadata (/Subject, /Keywords) for white-on-white."""
    import pypdf  # type: ignore[import-untyped]

    base = _make_blank_pdf(tmp_path / "base.pdf")
    custom_text = "Hidden injection payload text"
    out = build_pdf_payload(base, tmp_path / "out.pdf", text=custom_text)
    reader = pypdf.PdfReader(str(out))
    meta = reader.metadata or {}
    assert any(custom_text in str(v) for v in meta.values()), (
        "PDF metadata must contain the payload text"
    )

"""Report footers must name the operator by callsign only (CONTROL-01)."""

from nexus.analyze import footer_block
from nexus.audit import format_audit_footer


def _check(text: str) -> None:
    assert "CONTROL-01" in text
    assert "Ara &" not in text
    assert "💕" not in text
    assert "Love" not in text


def test_analysis_footer_is_callsign_only():
    _check(footer_block())


def test_audit_footer_is_callsign_only():
    _check(format_audit_footer())

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_self_audit_commits_astra_artifacts():
    body = _workflow("nexus-self-audit.yml")
    assert "config/astra.json" in body
    assert "badges/astra.md" in body


def test_pulse_commits_astra_artifacts():
    body = _workflow("nexus-pulse.yml")
    assert "config/astra.json" in body
    assert "badges/astra.md" in body


def test_complete_commits_astra_badge():
    body = _workflow("nexus-complete.yml")
    assert "config/astra.json" in body
    assert "badges/astra.md" in body

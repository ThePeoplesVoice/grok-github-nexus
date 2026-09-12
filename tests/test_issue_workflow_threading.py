from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _workflow_text(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_commit_analysis_reuses_open_issue_thread():
    text = _workflow_text("multi-ai-commit-analyzer.yml")
    assert "issues.listForRepo" in text
    assert "labels: 'nexus-analysis,automated'" in text
    assert "issues.createComment" in text


def test_pulse_reuses_open_issue_thread():
    text = _workflow_text("nexus-pulse.yml")
    assert "issues.listForRepo" in text
    assert "labels: 'nexus-pulse,automated'" in text
    assert "issues.createComment" in text


def test_self_audit_reuses_open_issue_thread():
    text = _workflow_text("nexus-self-audit.yml")
    assert "issues.listForRepo" in text
    assert "labels: 'self-audit,automated'" in text
    assert "issues.createComment" in text


def test_complete_prefers_self_audit_live_thread():
    text = _workflow_text("nexus-complete.yml")
    assert "labels: 'self-audit,automated'" in text
    assert "labels: 'nexus-complete,automated'" in text
    assert text.index("labels: 'self-audit,automated'") < text.index(
        "labels: 'nexus-complete,automated'"
    )
    assert "issues.createComment" in text

"""Shared test setup."""

import pytest


@pytest.fixture(autouse=True)
def _no_grok_backoff(monkeypatch):
    """Grok retry backoff sleeps in production; tests must not wait on it."""
    monkeypatch.setattr("nexus.providers._sleep", lambda _seconds: None)

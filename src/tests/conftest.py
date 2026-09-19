import pytest


@pytest.fixture
def today(monkeypatch):
    monkeypatch.setenv("KAIJU_TODAY", "2026-09-19")
    return "2026-09-19"

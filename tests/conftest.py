"""Global Pytest Fixtures and Environment Configuration for Devaura."""

import os
import pytest


@pytest.fixture(autouse=True)
def default_deterministic_mode_for_tests(monkeypatch):
    """Ensure standard unit tests default to deterministic mock mode unless explicitly set."""
    if not os.getenv("TEST_USE_LIVE_LLM"):
        monkeypatch.setenv("DEVAURA_LLM_MODE", "deterministic")

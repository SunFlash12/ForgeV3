import pytest


@pytest.fixture(autouse=True)
def _skip_without_copilot():
    """Skip all copilot tests when the copilot SDK is not installed."""
    pytest.importorskip("copilot")

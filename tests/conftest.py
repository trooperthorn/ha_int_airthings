"""Shared test fixtures for the Airthings BLE integration.

These fixtures depend on `pytest-homeassistant-custom-component`, which
provides the `hass`, `enable_bluetooth`, and config-entry test harness.
Install `requirements_test.txt` before running the full suite; the
decoder-only tests in `test_decoders.py` have no such dependency and run
standalone.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):  # noqa: ANN001
    """Make custom_components/ discoverable by Home Assistant's test harness."""
    yield


@pytest.fixture
def mock_airthings_client() -> AsyncMock:
    """A mocked AirthingsBleClient async context manager."""
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    return client

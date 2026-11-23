"""Shared test fixtures for the Airthings BLE integration.

These fixtures depend on `pytest-homeassistant`, which loads as a pytest
plugin automatically, enables custom integrations by default, and provides
the `hass`, `enable_bluetooth`, and config-entry test harness.
Install `requirements_test.txt` before running the full suite; the
decoder-only tests in `test_decoders.py` have no such dependency and run
standalone.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def mock_airthings_client() -> AsyncMock:
    """A mocked AirthingsBleClient async context manager."""
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    return client

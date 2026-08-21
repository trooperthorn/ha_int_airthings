"""Tests for the Airthings BLE config flow.

Requires the pytest-homeassistant-custom-component test harness (see
tests/conftest.py) -- run via `pytest tests/` after installing
requirements_test.txt.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.airthings_ble.const import DOMAIN, DeviceModel
from custom_components.airthings_ble.models import AirthingsDeviceInfo

from .conftest_helpers import make_bluetooth_service_info

pytestmark = pytest.mark.usefixtures("enable_bluetooth")


def _device_info(address: str) -> AirthingsDeviceInfo:
    return AirthingsDeviceInfo(
        address=address,
        model=DeviceModel.WAVE_PLUS,
        model_number="2930",
        name="Airthings Wave Plus",
        serial_number="2930123456",
        firmware_revision="G-BLE-1.5.1-master+0",
        hardware_revision="REV A",
    )


async def test_bluetooth_discovery_creates_entry(hass: HomeAssistant) -> None:
    """A discovered Airthings advertisement should be confirmable and create an entry."""
    discovery_info = make_bluetooth_service_info(
        name="Airthings Wave+", address="AA:BB:CC:DD:EE:FF"
    )

    with patch(
        "custom_components.airthings_ble.config_flow.AirthingsBleClient"
    ) as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.read_device_info.return_value = _device_info("AA:BB:CC:DD:EE:FF")
        mock_client_cls.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=discovery_info,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "bluetooth_confirm"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["data"]["address"] == "AA:BB:CC:DD:EE:FF"


async def test_bluetooth_discovery_aborts_for_non_airthings_device(
    hass: HomeAssistant,
) -> None:
    discovery_info = make_bluetooth_service_info(
        name="Some Other Device", address="11:22:33:44:55:66", manufacturer_id=None
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"

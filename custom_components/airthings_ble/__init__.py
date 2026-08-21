"""The Airthings BLE integration."""
from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .client import AirthingsBleClient, AirthingsBleError
from .const import (
    CONF_SCAN_INTERVAL,
    CORENTIUM_HOME_2_SCAN_INTERVAL_SECONDS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DeviceModel,
)
from .coordinator import AirthingsConfigEntry, AirthingsDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AirthingsConfigEntry) -> bool:
    """Set up Airthings BLE from a config entry."""
    address: str = entry.unique_id or entry.data["address"]

    ble_device = bluetooth.async_ble_device_from_address(hass, address, connectable=True)
    if ble_device is None:
        raise ConfigEntryNotReady(
            f"Could not find Airthings device with address {address}"
        )

    try:
        async with AirthingsBleClient(ble_device) as client:
            device_info = await client.read_device_info()
    except AirthingsBleError as err:
        raise ConfigEntryNotReady(f"Unable to connect to {address}: {err}") from err

    default_interval = (
        CORENTIUM_HOME_2_SCAN_INTERVAL_SECONDS
        if device_info.model is DeviceModel.CORENTIUM_HOME_2
        else DEFAULT_SCAN_INTERVAL_SECONDS
    )
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, default_interval)

    coordinator = AirthingsDataUpdateCoordinator(
        hass, entry, address, device_info, scan_interval
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirthingsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: AirthingsConfigEntry) -> None:
    """Reload the entry when its options change (e.g. scan interval)."""
    await hass.config_entries.async_reload(entry.entry_id)

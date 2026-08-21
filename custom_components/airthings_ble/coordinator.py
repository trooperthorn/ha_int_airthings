"""DataUpdateCoordinator for Airthings BLE devices."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TypeAlias

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AirthingsBleClient, AirthingsBleError
from .const import DOMAIN
from .models import AirthingsDeviceInfo, AirthingsSensorData

_LOGGER = logging.getLogger(__name__)


class AirthingsDataUpdateCoordinator(DataUpdateCoordinator[AirthingsSensorData]):
    """Connects to one Airthings BLE device on a schedule and decodes it."""

    config_entry: "AirthingsConfigEntry"

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: "AirthingsConfigEntry",
        address: str,
        device_info: AirthingsDeviceInfo,
        scan_interval_seconds: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-{address}",
            update_interval=timedelta(seconds=scan_interval_seconds),
        )
        self.address = address
        self.device_info = device_info

    async def _async_update_data(self) -> AirthingsSensorData:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(
                f"Airthings device {self.address} not currently reachable via Bluetooth"
            )

        try:
            async with AirthingsBleClient(ble_device) as client:
                data = await client.read_sensor_data(self.device_info.model)
        except AirthingsBleError as err:
            raise UpdateFailed(f"Failed reading Airthings device {self.address}: {err}") from err

        data.rssi = ble_device.rssi if hasattr(ble_device, "rssi") else None
        return data


AirthingsConfigEntry: TypeAlias = ConfigEntry[AirthingsDataUpdateCoordinator]

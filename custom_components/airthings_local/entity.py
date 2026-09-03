"""Base entity for Airthings BLE."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MODEL_NAMES, DOMAIN, MANUFACTURER
from .coordinator import AirthingsDataUpdateCoordinator


class AirthingsEntity(CoordinatorEntity[AirthingsDataUpdateCoordinator]):
    """Base class for all Airthings BLE entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AirthingsDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        device_info = coordinator.device_info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_info.address)},
            connections={("bluetooth", device_info.address)},
            name=DEVICE_MODEL_NAMES[device_info.model],
            manufacturer=MANUFACTURER,
            model=DEVICE_MODEL_NAMES[device_info.model],
            model_id=device_info.model_number,
            serial_number=device_info.serial_number,
            sw_version=device_info.firmware_revision,
            hw_version=device_info.hardware_revision,
        )

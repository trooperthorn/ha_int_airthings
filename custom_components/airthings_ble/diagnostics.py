"""Diagnostics support for Airthings BLE."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import AirthingsConfigEntry

TO_REDACT = {"address", "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AirthingsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "device_info": async_redact_data(asdict(coordinator.device_info), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "scan_interval_seconds": (
            coordinator.update_interval.total_seconds() if coordinator.update_interval else None
        ),
        "latest_sample": asdict(coordinator.data) if coordinator.data else None,
    }

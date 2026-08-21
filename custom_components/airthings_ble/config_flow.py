"""Config flow for Airthings BLE."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .client import AirthingsBleClient, AirthingsBleDeviceUnsupportedError, AirthingsBleError
from .const import (
    CONF_SCAN_INTERVAL,
    CORENTIUM_HOME_2_SCAN_INTERVAL_SECONDS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEVICE_MODEL_NAMES,
    DOMAIN,
    MANUFACTURER_ID,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
    DeviceModel,
)
from .models import AirthingsDeviceInfo

_LOGGER = logging.getLogger(__name__)


def _is_airthings_advertisement(service_info: BluetoothServiceInfoBleak) -> bool:
    return MANUFACTURER_ID in service_info.manufacturer_data


class AirthingsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Airthings BLE."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a discovered Airthings BLE device."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        if not _is_airthings_advertisement(discovery_info):
            return self.async_abort(reason="not_supported")

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup of a discovered device."""
        assert self._discovery_info is not None

        if user_input is not None:
            return await self._async_create_entry_for_address(self._discovery_info.address)

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._discovery_info.name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a manually-initiated setup, picking from discovered devices."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return await self._async_create_entry_for_address(address)

        current_addresses = self._async_current_ids()
        for service_info in async_discovered_service_info(self.hass):
            if (
                service_info.address in current_addresses
                or not _is_airthings_advertisement(service_info)
            ):
                continue
            self._discovered_devices[service_info.address] = (
                f"{service_info.name} ({service_info.address})"
            )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow re-pairing to a new MAC without deleting the entry (e.g. after a factory reset)."""
        return await self.async_step_user(user_input)

    async def _async_create_entry_for_address(self, address: str) -> ConfigFlowResult:
        from homeassistant.components import bluetooth

        ble_device = bluetooth.async_ble_device_from_address(self.hass, address, connectable=True)
        if ble_device is None:
            return self.async_abort(reason="cannot_connect")

        try:
            async with AirthingsBleClient(ble_device) as client:
                device_info: AirthingsDeviceInfo = await client.read_device_info()
        except AirthingsBleDeviceUnsupportedError:
            return self.async_abort(reason="not_supported")
        except AirthingsBleError:
            _LOGGER.debug("Failed to validate Airthings device %s", address, exc_info=True)
            return self.async_abort(reason="cannot_connect")

        model_name = DEVICE_MODEL_NAMES[device_info.model]
        return self.async_create_entry(
            title=f"{model_name} {device_info.serial_number or address}",
            data={CONF_ADDRESS: address},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "AirthingsOptionsFlow":
        return AirthingsOptionsFlow(config_entry)


class AirthingsOptionsFlow(OptionsFlow):
    """Options flow: lets the user tune the active-connection poll interval.

    Airthings devices only refresh radon/VOC/CO2 samples roughly every
    few minutes on-device, and frequent BLE connections measurably shorten
    coin-cell battery life -- so this is a deliberate latency/battery
    tradeoff exposed to the user, not a fixed constant.
    """

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        default_interval = self._config_entry.options.get(
            CONF_SCAN_INTERVAL,
            (
                CORENTIUM_HOME_2_SCAN_INTERVAL_SECONDS
                if self._config_entry.runtime_data
                and self._config_entry.runtime_data.device_info.model
                is DeviceModel.CORENTIUM_HOME_2
                else DEFAULT_SCAN_INTERVAL_SECONDS
            ),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=default_interval): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL_SECONDS, max=MAX_SCAN_INTERVAL_SECONDS),
                    )
                }
            ),
        )

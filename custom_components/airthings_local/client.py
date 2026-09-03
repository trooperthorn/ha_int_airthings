"""Async BLE client for Airthings consumer devices.

Fully asyncio-native (satisfies the Platinum `async-dependency` rule): all
I/O goes through ``bleak`` / ``bleak_retry_connector`` coroutines, no sync
code is wrapped in an executor.
"""
from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass
from typing import Any

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from .const import (
    ATOM_DEVICE_MODELS,
    ATOM_PATH_LATEST_SAMPLES,
    BATTERY_COMMAND_BYTE,
    BATTERY_CURVE_THREE_CELL,
    BATTERY_CURVE_TWO_CELL,
    BQ_TO_PCI_MULTIPLIER,
    CHAR_UUID_ATOM_NOTIFY,
    CHAR_UUID_ATOM_WRITE,
    CHAR_UUID_COMMAND_WAVE_MINI,
    CHAR_UUID_COMMAND_WAVE_PLUS,
    CHAR_UUID_COMMAND_WAVE_RADON,
    CHAR_UUID_FIRMWARE_REV,
    CHAR_UUID_HARDWARE_REV,
    CHAR_UUID_HUMIDITY,
    CHAR_UUID_ILLUMINANCE_ACCELEROMETER,
    CHAR_UUID_MODEL_NUMBER_STRING,
    CHAR_UUID_RADON_1DAY_AVG,
    CHAR_UUID_RADON_LONG_TERM_AVG,
    CHAR_UUID_SERIAL_NUMBER_STRING,
    CHAR_UUID_TEMPERATURE,
    CHAR_UUID_WAVE_MINI_DATA,
    CHAR_UUID_WAVE_PLUS_DATA,
    CHAR_UUID_WAVE_RADON_DATA,
    CO2_VOC_MAX,
    CONNECT_TIMEOUT_SECONDS,
    MAX_CONNECT_ATTEMPTS,
    MODEL_NUMBER_TO_DEVICE_MODEL,
    PRESSURE_MAX_HPA,
    RADON_MAX_BQM3,
    STRUCT_DEVICE_MODELS,
    DeviceModel,
)
from .models import AirthingsDeviceInfo, AirthingsSensorData

_LOGGER = logging.getLogger(__name__)

_COMMAND_CHAR_BY_MODEL: dict[DeviceModel, str] = {
    DeviceModel.WAVE_PLUS: CHAR_UUID_COMMAND_WAVE_PLUS,
    DeviceModel.WAVE_RADON: CHAR_UUID_COMMAND_WAVE_RADON,
    DeviceModel.WAVE_MINI: CHAR_UUID_COMMAND_WAVE_MINI,
}

_DATA_CHAR_BY_MODEL: dict[DeviceModel, str] = {
    DeviceModel.WAVE_PLUS: CHAR_UUID_WAVE_PLUS_DATA,
    DeviceModel.WAVE_RADON: CHAR_UUID_WAVE_RADON_DATA,
    DeviceModel.WAVE_MINI: CHAR_UUID_WAVE_MINI_DATA,
}

# Battery voltage sits at a fixed offset in the command-response payload;
# the offset and struct format differ between the two-cell (Plus/Radon)
# and three-cell (Mini) response layouts.
_BATTERY_RESPONSE_FORMAT: dict[DeviceModel, tuple[str, int]] = {
    DeviceModel.WAVE_PLUS: ("<L2BH2B9H", 13),
    DeviceModel.WAVE_RADON: ("<L2BH2B9H", 13),
    DeviceModel.WAVE_MINI: ("<2L4B2HL4HL", 11),
}


class AirthingsBleError(Exception):
    """Base error for Airthings BLE operations."""


class AirthingsBleDeviceUnsupportedError(AirthingsBleError):
    """Raised when the device's Model Number String is not recognized."""


def _valid_or_none(value: int, maximum: int) -> int | None:
    """Discard sentinel "sensor not yet stabilized" readings."""
    return value if 0 <= value < maximum else None


def _decode_struct_payload(model: DeviceModel, payload: bytes | bytearray) -> AirthingsSensorData:
    """Decode a legacy binary-struct GATT characteristic payload.

    Struct layouts and scaling factors per Airthings' official
    ``airthings-ble`` reference implementation.
    """
    data = AirthingsSensorData()

    if model in (DeviceModel.WAVE_PLUS, DeviceModel.WAVE_RADON):
        fields = struct.unpack("<4B8H", payload)
        # fields[0] = sensor version (unused), fields[1..] per below.
        humidity_raw = fields[1]
        illuminance_raw = fields[2]
        radon_1day_raw = fields[4]
        radon_longterm_raw = fields[5]
        temperature_raw = fields[6]
        pressure_raw = fields[7]

        data.humidity = humidity_raw / 2.0
        data.illuminance = illuminance_raw
        data.radon_1day_avg = _valid_or_none(radon_1day_raw, RADON_MAX_BQM3)
        data.radon_longterm_avg = _valid_or_none(radon_longterm_raw, RADON_MAX_BQM3)
        data.temperature = temperature_raw / 100.0
        data.pressure = pressure_raw / 50.0

        if model is DeviceModel.WAVE_PLUS:
            co2_raw = fields[8]
            voc_raw = fields[9]
            data.co2 = _valid_or_none(co2_raw, CO2_VOC_MAX)
            data.voc = _valid_or_none(voc_raw, CO2_VOC_MAX)

    elif model is DeviceModel.WAVE_MINI:
        fields = struct.unpack("<2B5HLL", payload)
        illuminance_raw = fields[0]
        temperature_raw = fields[2]
        pressure_raw = fields[3]
        humidity_raw = fields[4]
        voc_raw = fields[5]

        data.illuminance = illuminance_raw
        data.temperature = temperature_raw / 100.0 - 273.15
        data.pressure = pressure_raw / 50.0
        data.humidity = humidity_raw / 100.0
        data.voc = _valid_or_none(voc_raw, CO2_VOC_MAX)

    else:  # pragma: no cover - guarded by caller
        raise AirthingsBleDeviceUnsupportedError(model)

    if data.pressure is not None and data.pressure > PRESSURE_MAX_HPA:
        data.pressure = None

    _populate_pci_l(data)
    return data


def _populate_pci_l(data: AirthingsSensorData) -> None:
    if data.radon_1day_avg is not None:
        data.radon_1day_avg_pci_l = round(data.radon_1day_avg * BQ_TO_PCI_MULTIPLIER, 2)
    if data.radon_longterm_avg is not None:
        data.radon_longterm_avg_pci_l = round(
            data.radon_longterm_avg * BQ_TO_PCI_MULTIPLIER, 2
        )


def _decode_gen1_radon(
    payload_1day: bytes | bytearray, payload_longterm: bytes | bytearray
) -> AirthingsSensorData:
    data = AirthingsSensorData()
    (radon_1day_raw,) = struct.unpack("<H", payload_1day)
    (radon_longterm_raw,) = struct.unpack("<H", payload_longterm)
    data.radon_1day_avg = _valid_or_none(radon_1day_raw, RADON_MAX_BQM3)
    data.radon_longterm_avg = _valid_or_none(radon_longterm_raw, RADON_MAX_BQM3)
    _populate_pci_l(data)
    return data


def _voltage_to_percentage(voltage: float, curve: tuple[tuple[float, int], ...]) -> int:
    """Piecewise-linear interpolation of a battery discharge curve."""
    if voltage <= curve[0][0]:
        return curve[0][1]
    if voltage >= curve[-1][0]:
        return curve[-1][1]
    for (v_low, p_low), (v_high, p_high) in zip(curve, curve[1:], strict=True):
        if v_low <= voltage <= v_high:
            span = v_high - v_low
            if span == 0:
                return p_low
            fraction = (voltage - v_low) / span
            return round(p_low + fraction * (p_high - p_low))
    return curve[-1][1]  # pragma: no cover - unreachable, satisfies mypy


def _decode_battery_response(model: DeviceModel, payload: bytes) -> tuple[float, int]:
    fmt, offset = _BATTERY_RESPONSE_FORMAT[model]
    fields = struct.unpack(fmt, payload)
    voltage = fields[offset] / 1000.0
    curve = BATTERY_CURVE_THREE_CELL if model is DeviceModel.WAVE_MINI else BATTERY_CURVE_TWO_CELL
    return voltage, _voltage_to_percentage(voltage, curve)


@dataclass(slots=True)
class _NotifyBuffer:
    """Reassembles a (possibly fragmented) GATT notify/indicate response."""

    event: asyncio.Event
    data: bytearray

    @classmethod
    def create(cls) -> _NotifyBuffer:
        return cls(event=asyncio.Event(), data=bytearray())


class AirthingsBleClient:
    """Async client for reading/decoding data from one Airthings BLE device."""

    def __init__(self, ble_device: BLEDevice) -> None:
        self._ble_device = ble_device
        self._client: BleakClientWithServiceCache | None = None

    async def __aenter__(self) -> AirthingsBleClient:
        self._client = await establish_connection(
            BleakClientWithServiceCache,
            self._ble_device,
            self._ble_device.address,
            max_attempts=MAX_CONNECT_ATTEMPTS,
        )
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None

    @property
    def _require_client(self) -> BleakClientWithServiceCache:
        if self._client is None:
            raise AirthingsBleError("Not connected")
        return self._client

    async def read_device_info(self) -> AirthingsDeviceInfo:
        client = self._require_client
        model_number = (await client.read_gatt_char(CHAR_UUID_MODEL_NUMBER_STRING)).decode(
            "utf-8"
        ).strip("\x00")
        model = MODEL_NUMBER_TO_DEVICE_MODEL.get(model_number)
        if model is None:
            raise AirthingsBleDeviceUnsupportedError(
                f"Unrecognized Airthings model number: {model_number!r}"
            )

        serial_number: str | None = None
        firmware_revision: str | None = None
        hardware_revision: str | None = None
        try:
            serial_number = (
                await client.read_gatt_char(CHAR_UUID_SERIAL_NUMBER_STRING)
            ).decode("utf-8").strip("\x00")
            firmware_revision = (
                await client.read_gatt_char(CHAR_UUID_FIRMWARE_REV)
            ).decode("utf-8").strip("\x00")
            hardware_revision = (
                await client.read_gatt_char(CHAR_UUID_HARDWARE_REV)
            ).decode("utf-8").strip("\x00")
        except Exception:  # noqa: BLE001 - optional characteristics, best-effort
            _LOGGER.debug("Optional device-info characteristic unavailable", exc_info=True)

        return AirthingsDeviceInfo(
            address=self._ble_device.address,
            model=model,
            model_number=model_number,
            name=self._ble_device.name or model.value,
            serial_number=serial_number,
            firmware_revision=firmware_revision,
            hardware_revision=hardware_revision,
        )

    async def read_sensor_data(self, model: DeviceModel) -> AirthingsSensorData:
        """Read and decode the latest sample for the given device model."""
        if model in STRUCT_DEVICE_MODELS:
            data = await self._read_struct_sensor_data(model)
        elif model in ATOM_DEVICE_MODELS:
            data = await self._read_atom_sensor_data()
        else:  # pragma: no cover - guarded upstream
            raise AirthingsBleDeviceUnsupportedError(model)

        try:
            data.battery_voltage, data.battery_percentage = await self._read_battery(model)
        except AirthingsBleError:
            _LOGGER.debug("Battery read failed for %s", model, exc_info=True)

        return data

    async def _read_struct_sensor_data(self, model: DeviceModel) -> AirthingsSensorData:
        if model is DeviceModel.WAVE_GEN1:
            client = self._require_client
            payload_1day = await client.read_gatt_char(CHAR_UUID_RADON_1DAY_AVG)
            payload_longterm = await client.read_gatt_char(CHAR_UUID_RADON_LONG_TERM_AVG)
            data = _decode_gen1_radon(payload_1day, payload_longterm)
            try:
                temp_raw = await client.read_gatt_char(CHAR_UUID_TEMPERATURE)
                humidity_raw = await client.read_gatt_char(CHAR_UUID_HUMIDITY)
                (temp_val,) = struct.unpack("<h", temp_raw)
                (humidity_val,) = struct.unpack("<H", humidity_raw)
                data.temperature = temp_val / 100.0
                data.humidity = humidity_val / 100.0
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Gen1 temp/humidity read failed", exc_info=True)
            try:
                illum_raw = await client.read_gatt_char(CHAR_UUID_ILLUMINANCE_ACCELEROMETER)
                illuminance, _accel = struct.unpack("<BB", illum_raw)
                data.illuminance = illuminance
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Gen1 illuminance read failed", exc_info=True)
            return data

        char_uuid = _DATA_CHAR_BY_MODEL[model]
        payload = await self._require_client.read_gatt_char(char_uuid)
        return _decode_struct_payload(model, payload)

    async def _read_battery(self, model: DeviceModel) -> tuple[float, int]:
        command_char = _COMMAND_CHAR_BY_MODEL.get(model)
        if command_char is None:
            raise AirthingsBleError(f"No battery command characteristic for {model}")

        buffer = _NotifyBuffer.create()

        def _on_notify(_characteristic: BleakGATTCharacteristic, payload: bytearray) -> None:
            buffer.data.extend(payload)
            buffer.event.set()

        client = self._require_client
        await client.start_notify(command_char, _on_notify)
        try:
            await client.write_gatt_char(command_char, bytes([BATTERY_COMMAND_BYTE]))
            async with asyncio.timeout(CONNECT_TIMEOUT_SECONDS):
                await buffer.event.wait()
        finally:
            await client.stop_notify(command_char)

        return _decode_battery_response(model, bytes(buffer.data))

    async def _read_atom_sensor_data(self) -> AirthingsSensorData:
        """Read latest samples from a Wave Enhance / Corentium Home 2.

        These devices use Airthings' newer CBOR-encoded "Atom" RPC layer
        rather than fixed-offset structs: a UTF-8 request path is written
        to CHAR_UUID_ATOM_WRITE, and the CBOR response (a mapping of short
        mnemonic keys) arrives via notify on CHAR_UUID_ATOM_NOTIFY,
        possibly split across several notification packets.
        """
        import cbor2  # local import: only needed for Atom-family devices

        buffer = _NotifyBuffer.create()

        def _on_notify(_characteristic: BleakGATTCharacteristic, payload: bytearray) -> None:
            buffer.data.extend(payload)
            buffer.event.set()

        client = self._require_client
        await client.start_notify(CHAR_UUID_ATOM_NOTIFY, _on_notify)
        try:
            await client.write_gatt_char(
                CHAR_UUID_ATOM_WRITE, ATOM_PATH_LATEST_SAMPLES.encode("utf-8")
            )
            async with asyncio.timeout(CONNECT_TIMEOUT_SECONDS):
                await buffer.event.wait()
        finally:
            await client.stop_notify(CHAR_UUID_ATOM_NOTIFY)

        decoded: dict[str, Any] = cbor2.loads(bytes(buffer.data))
        return _map_atom_response(decoded)


def _map_atom_response(decoded: dict[str, Any]) -> AirthingsSensorData:
    data = AirthingsSensorData()
    if (temp_raw := decoded.get("TMP")) is not None:
        data.temperature = temp_raw / 100.0 - 273.15
    if (hum_raw := decoded.get("HUM")) is not None:
        data.humidity = hum_raw / 100.0
    if (pressure_raw := decoded.get("PRS")) is not None:
        data.pressure = pressure_raw / (64 * 100)
    if (co2 := decoded.get("CO2")) is not None:
        data.co2 = _valid_or_none(co2, CO2_VOC_MAX)
    if (voc := decoded.get("VOC")) is not None:
        data.voc = _valid_or_none(voc, CO2_VOC_MAX)
    if (noise := decoded.get("NOI")) is not None:
        data.noise = float(noise)
    if (lux := decoded.get("LUX")) is not None:
        data.illuminance = int(lux)
    if (radon_24h := decoded.get("R24")) is not None:
        data.radon_1day_avg = _valid_or_none(radon_24h, RADON_MAX_BQM3)
    if (radon_7d := decoded.get("R7D")) is not None:
        data.radon_7day_avg = _valid_or_none(radon_7d, RADON_MAX_BQM3)
    if (radon_30d := decoded.get("R30D")) is not None:
        data.radon_30day_avg = _valid_or_none(radon_30d, RADON_MAX_BQM3)
        data.radon_longterm_avg = data.radon_30day_avg
    if (radon_1y := decoded.get("R1Y")) is not None:
        data.radon_1year_avg = _valid_or_none(radon_1y, RADON_MAX_BQM3)
    if (bat_mv := decoded.get("BAT")) is not None:
        voltage = bat_mv / 1000.0
        data.battery_voltage = voltage
        data.battery_percentage = _voltage_to_percentage(voltage, BATTERY_CURVE_TWO_CELL)

    _populate_pci_l(data)
    return data

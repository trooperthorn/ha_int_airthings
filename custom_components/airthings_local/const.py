"""Constants for the Airthings BLE integration.

Protocol details (GATT UUIDs, struct layouts, scaling factors, battery
voltage curves) are sourced from Airthings' official ``airthings-ble``
library (github.com/Airthings/airthings-ble) and cross-checked against the
original Airthings ``waveplus-reader`` reference scripts. Where Airthings
has not published a formal protocol spec (the Wave Enhance / Corentium
Home 2 "Atom" RPC layer), the library source is the closest thing to one.
"""
from __future__ import annotations

from enum import StrEnum

DOMAIN = "airthings_local"
MANUFACTURER = "Airthings"

# Airthings' Bluetooth SIG manufacturer identifier, used both for
# HA's `bluetooth` manifest matcher and to sanity-check advertisements.
MANUFACTURER_ID = 820

# Standard Bluetooth SIG Device Information Service (0x180A) characteristics.
CHAR_UUID_MODEL_NUMBER_STRING = "00002a24-0000-1000-8000-00805f9b34fb"
CHAR_UUID_SERIAL_NUMBER_STRING = "00002a25-0000-1000-8000-00805f9b34fb"
CHAR_UUID_FIRMWARE_REV = "00002a26-0000-1000-8000-00805f9b34fb"
CHAR_UUID_HARDWARE_REV = "00002a27-0000-1000-8000-00805f9b34fb"
CHAR_UUID_MANUFACTURER_NAME = "00002a29-0000-1000-8000-00805f9b34fb"
CHAR_UUID_DEVICE_NAME = "00002a00-0000-1000-8000-00805f9b34fb"

# Airthings' proprietary GATT service, base b42e....-ade7-11e4-89d3-123b93f75cba.
CHAR_UUID_WAVE_PLUS_DATA = "b42e2a68-ade7-11e4-89d3-123b93f75cba"
CHAR_UUID_WAVE_RADON_DATA = "b42e4dcc-ade7-11e4-89d3-123b93f75cba"  # Wave Radon (gen 2)
CHAR_UUID_WAVE_MINI_DATA = "b42e3b98-ade7-11e4-89d3-123b93f75cba"
CHAR_UUID_RADON_1DAY_AVG = "b42e01aa-ade7-11e4-89d3-123b93f75cba"  # Wave (gen 1)
CHAR_UUID_RADON_LONG_TERM_AVG = "b42e0a4c-ade7-11e4-89d3-123b93f75cba"  # Wave (gen 1)
CHAR_UUID_ILLUMINANCE_ACCELEROMETER = "b42e1348-ade7-11e4-89d3-123b93f75cba"  # Wave (gen 1)

CHAR_UUID_COMMAND_WAVE_PLUS = "b42e2d06-ade7-11e4-89d3-123b93f75cba"
CHAR_UUID_COMMAND_WAVE_RADON = "b42e50d8-ade7-11e4-89d3-123b93f75cba"
CHAR_UUID_COMMAND_WAVE_MINI = "b42e3ef4-ade7-11e4-89d3-123b93f75cba"

CHAR_UUID_ATOM_WRITE = "b42eb73a-ade7-11e4-89d3-123b93f75cba"  # Wave Enhance / Corentium Home 2
CHAR_UUID_ATOM_NOTIFY = "b42ebc9e-ade7-11e4-89d3-123b93f75cba"

CHAR_UUID_TEMPERATURE = "00002a6e-0000-1000-8000-00805f9b34fb"  # Wave (gen 1)
CHAR_UUID_HUMIDITY = "00002a6f-0000-1000-8000-00805f9b34fb"  # Wave (gen 1)
CHAR_UUID_CURRENT_TIME = "00002a08-0000-1000-8000-00805f9b34fb"

# Battery command byte: write to the model-specific command characteristic
# and await an indicate/notify response containing battery voltage.
BATTERY_COMMAND_BYTE = 0x6D

# Atom RPC request paths (Wave Enhance / Corentium Home 2 only); see docs/protocol.md.
ATOM_PATH_LATEST_SAMPLES = "29999/0/31012"
ATOM_PATH_CONNECTIVITY_MODE = "17/0/31100"


class DeviceModel(StrEnum):
    """Airthings device model, keyed by BLE Model Number String."""

    WAVE_GEN1 = "wave_gen1"
    WAVE_MINI = "wave_mini"
    WAVE_PLUS = "wave_plus"
    WAVE_RADON = "wave_radon"  # Wave Radon (gen 2) / "Wave 2"
    WAVE_ENHANCE = "wave_enhance"
    CORENTIUM_HOME_2 = "corentium_home_2"


# Model Number String -> DeviceModel, as reported by the standard BLE
# Device Information Service.
MODEL_NUMBER_TO_DEVICE_MODEL: dict[str, DeviceModel] = {
    "2900": DeviceModel.WAVE_GEN1,
    "2920": DeviceModel.WAVE_MINI,
    "2930": DeviceModel.WAVE_PLUS,
    "2950": DeviceModel.WAVE_RADON,
    "3210": DeviceModel.WAVE_ENHANCE,  # EU
    "3220": DeviceModel.WAVE_ENHANCE,  # US
    "3250": DeviceModel.CORENTIUM_HOME_2,
}

DEVICE_MODEL_NAMES: dict[DeviceModel, str] = {
    DeviceModel.WAVE_GEN1: "Wave",
    DeviceModel.WAVE_MINI: "Wave Mini",
    DeviceModel.WAVE_PLUS: "Wave Plus",
    DeviceModel.WAVE_RADON: "Wave Radon",
    DeviceModel.WAVE_ENHANCE: "Wave Enhance",
    DeviceModel.CORENTIUM_HOME_2: "Corentium Home 2",
}

# Devices that use the legacy binary-struct GATT characteristics.
STRUCT_DEVICE_MODELS = {
    DeviceModel.WAVE_GEN1,
    DeviceModel.WAVE_MINI,
    DeviceModel.WAVE_PLUS,
    DeviceModel.WAVE_RADON,
}

# Devices that use the newer CBOR "Atom" RPC layer.
ATOM_DEVICE_MODELS = {
    DeviceModel.WAVE_ENHANCE,
    DeviceModel.CORENTIUM_HOME_2,
}

# Sanity bounds: firmware reports one of these sentinel-ish "not yet
# stabilized" values while a sensor is still warming up. Treat as invalid.
RADON_MAX_BQM3 = 16383
CO2_VOC_MAX = 65534
PRESSURE_MAX_HPA = 1310.0

BQ_TO_PCI_MULTIPLIER = 0.027  # Bq/m3 -> pCi/L

# Voltage-to-percentage breakpoints differ by cell chemistry; see docs/protocol.md.
BATTERY_CURVE_TWO_CELL: tuple[tuple[float, int], ...] = (
    (2.10, 0),
    (2.20, 5),
    (2.50, 28),
    (2.60, 53),
    (2.80, 81),
    (3.00, 100),
)
BATTERY_CURVE_THREE_CELL: tuple[tuple[float, int], ...] = (
    (2.40, 0),
    (3.30, 23),
    (3.75, 42),
    (3.90, 62),
    (4.20, 85),
    (4.50, 100),
)

# User-configurable poll interval (options flow); see docs/design.md.
DEFAULT_SCAN_INTERVAL_SECONDS = 300
CORENTIUM_HOME_2_SCAN_INTERVAL_SECONDS = 1800
MIN_SCAN_INTERVAL_SECONDS = 60
MAX_SCAN_INTERVAL_SECONDS = 3600

CONF_SCAN_INTERVAL = "scan_interval"

# Full BLE connect+read+disconnect cycle timeout.
CONNECT_TIMEOUT_SECONDS = 15
MAX_CONNECT_ATTEMPTS = 3

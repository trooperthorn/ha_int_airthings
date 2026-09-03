"""Typed data models for decoded Airthings BLE sensor payloads."""
from __future__ import annotations

from dataclasses import dataclass

from .const import DeviceModel


@dataclass(slots=True, kw_only=True)
class AirthingsDeviceInfo:
    """Static device identity, read once from the Device Information Service."""

    address: str
    model: DeviceModel
    model_number: str
    name: str
    serial_number: str | None = None
    firmware_revision: str | None = None
    hardware_revision: str | None = None


@dataclass(slots=True, kw_only=True)
class AirthingsSensorData:
    """A single decoded sample from an Airthings device.

    All fields are optional: which are populated depends on the device
    model, and any individual reading that fails firmware validity bounds
    (e.g. a sensor still stabilizing after power-on) is left as ``None``
    rather than reported as a misleading zero.
    """

    humidity: float | None = None  # %RH
    illuminance: int | None = None  # %
    radon_1day_avg: int | None = None  # Bq/m3
    radon_longterm_avg: int | None = None  # Bq/m3
    radon_1day_avg_pci_l: float | None = None
    radon_longterm_avg_pci_l: float | None = None
    temperature: float | None = None  # degC
    pressure: float | None = None  # hPa
    co2: int | None = None  # ppm
    voc: int | None = None  # ppb
    noise: float | None = None  # dB, Atom devices only
    battery_voltage: float | None = None  # V
    battery_percentage: int | None = None  # %
    rssi: int | None = None  # dBm, from the BLE advertisement/connection

    # Multi-horizon radon averages, Atom (Wave Enhance / Corentium Home 2) only.
    radon_7day_avg: int | None = None
    radon_30day_avg: int | None = None
    radon_1year_avg: int | None = None

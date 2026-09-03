"""Helpers for building fake BluetoothServiceInfoBleak objects in tests."""
from __future__ import annotations

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from custom_components.airthings_local.const import MANUFACTURER_ID


def make_bluetooth_service_info(
    *,
    name: str,
    address: str,
    manufacturer_id: int | None = MANUFACTURER_ID,
    rssi: int = -60,
) -> BluetoothServiceInfoBleak:
    """Build a BluetoothServiceInfoBleak matching (or not) an Airthings advertisement."""
    manufacturer_data = {manufacturer_id: b"\x00\x00"} if manufacturer_id is not None else {}
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=rssi,
        manufacturer_data=manufacturer_data,
        service_data={},
        service_uuids=[],
        source="local",
        device=None,  # populated by the test harness's BLEDevice factory
        advertisement=None,
        connectable=True,
        time=0.0,
        tx_power=None,
    )

"""Unit tests for the Airthings BLE protocol decoders.

These tests exercise `client.py`'s struct/CBOR decoding logic directly
against hand-built payloads matching the documented GATT layouts, with no
dependency on Home Assistant or a real BLE stack -- they pin down the
scaling-factor math (the part most likely to silently regress).
"""
from __future__ import annotations

import struct

import pytest

from custom_components.airthings_ble import client, const


def test_decode_wave_plus_payload() -> None:
    payload = struct.pack(
        "<4B8H",
        1,  # sensor version (unused)
        100,  # humidity raw -> 50.0 %RH
        50,  # illuminance raw -> 50 %
        0,  # unused
        30,  # radon 1-day avg, Bq/m3
        25,  # radon long-term avg, Bq/m3
        2200,  # temperature raw -> 22.00 degC
        50650,  # pressure raw -> 1013.0 hPa
        650,  # CO2 ppm
        250,  # VOC ppb
        0,
        0,
    )

    data = client._decode_struct_payload(const.DeviceModel.WAVE_PLUS, payload)

    assert data.humidity == 50.0
    assert data.illuminance == 50
    assert data.radon_1day_avg == 30
    assert data.radon_longterm_avg == 25
    assert data.temperature == pytest.approx(22.0)
    assert data.pressure == pytest.approx(1013.0)
    assert data.co2 == 650
    assert data.voc == 250
    assert data.radon_1day_avg_pci_l == pytest.approx(30 * const.BQ_TO_PCI_MULTIPLIER, abs=1e-6)


def test_decode_wave_radon_payload_has_no_co2_or_voc() -> None:
    payload = struct.pack(
        "<4B8H", 1, 100, 50, 0, 30, 25, 2200, 50650, 650, 250, 0, 0
    )

    data = client._decode_struct_payload(const.DeviceModel.WAVE_RADON, payload)

    assert data.radon_1day_avg == 30
    assert data.co2 is None
    assert data.voc is None


def test_decode_wave_mini_payload() -> None:
    payload = struct.pack(
        "<2B5HLL",
        40,  # illuminance
        0,  # unused byte
        29515,  # temperature raw (centikelvin) -> 22.00 degC
        50650,  # pressure raw -> 1013.0 hPa
        4500,  # humidity raw -> 45.00 %RH
        300,  # VOC ppb
        0,  # reserved
        0,
        0,
    )

    data = client._decode_struct_payload(const.DeviceModel.WAVE_MINI, payload)

    assert data.illuminance == 40
    assert data.temperature == pytest.approx(22.0)
    assert data.pressure == pytest.approx(1013.0)
    assert data.humidity == pytest.approx(45.0)
    assert data.voc == 300


@pytest.mark.parametrize(
    ("raw", "maximum", "expected"),
    [
        (100, const.CO2_VOC_MAX, 100),
        (const.CO2_VOC_MAX, const.CO2_VOC_MAX, None),  # sentinel: sensor not stabilized
        (0, const.RADON_MAX_BQM3, 0),
        (const.RADON_MAX_BQM3, const.RADON_MAX_BQM3, None),
    ],
)
def test_valid_or_none_discards_sentinel_values(
    raw: int, maximum: int, expected: int | None
) -> None:
    assert client._valid_or_none(raw, maximum) == expected


@pytest.mark.parametrize(
    ("voltage", "expected_min", "expected_max"),
    [
        (1.5, 0, 0),  # below curve floor clamps to 0%
        (3.5, 100, 100),  # above curve ceiling clamps to 100%
        (2.55, 28, 53),  # midpoint of a known breakpoint span
        (3.00, 100, 100),  # exact upper breakpoint
    ],
)
def test_battery_voltage_two_cell_curve(
    voltage: float, expected_min: int, expected_max: int
) -> None:
    pct = client._voltage_to_percentage(voltage, const.BATTERY_CURVE_TWO_CELL)
    assert expected_min <= pct <= expected_max


def test_battery_voltage_three_cell_curve_differs_from_two_cell() -> None:
    # The same raw voltage should not map to the same percentage on the
    # two curves -- conflating chemistries under- or over-reports battery
    # life, which is exactly the upstream bug this integration fixes.
    two_cell_pct = client._voltage_to_percentage(3.0, const.BATTERY_CURVE_TWO_CELL)
    three_cell_pct = client._voltage_to_percentage(3.0, const.BATTERY_CURVE_THREE_CELL)
    assert two_cell_pct != three_cell_pct


def test_map_atom_response_decodes_named_fields() -> None:
    decoded = {
        "TMP": 29515,
        "HUM": 4500,
        "PRS": 64850,
        "CO2": 500,
        "VOC": 120,
        "NOI": 32,
        "LUX": 10,
        "R24": 20,
        "R7D": 18,
        "R30D": 22,
        "R1Y": 25,
        "BAT": 3000,
    }

    data = client._map_atom_response(decoded)

    assert data.temperature == pytest.approx(22.0)
    assert data.humidity == pytest.approx(45.0)
    assert data.co2 == 500
    assert data.voc == 120
    assert data.noise == 32
    assert data.illuminance == 10
    assert data.radon_1day_avg == 20
    assert data.radon_7day_avg == 18
    assert data.radon_30day_avg == 22
    assert data.radon_longterm_avg == 22
    assert data.radon_1year_avg == 25
    assert data.battery_voltage == pytest.approx(3.0)
    assert data.battery_percentage == 100


def test_model_number_lookup_covers_every_documented_model() -> None:
    for model in const.MODEL_NUMBER_TO_DEVICE_MODEL.values():
        assert model in const.DEVICE_MODEL_NAMES
        assert model in const.STRUCT_DEVICE_MODELS or model in const.ATOM_DEVICE_MODELS

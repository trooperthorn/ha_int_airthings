# Design

## Radon unit

Home Assistant does not ship a native radon unit constant usable as a
`SensorDeviceClass.RADON` base unit. Bq/m3 is the scientifically standard
unit and what the device reports natively, so radon entities are created
directly in Bq/m3 (`RADON_UNIT_BQ_M3` in `sensor.py`), leaving
`suggested_unit_of_measurement` to Home Assistant's unit-system conversion
for pCi/L-preferring locales.

## Configurable poll interval

Upstream `airthings_ble`'s scan interval is fixed at 5 or 30 minutes
depending on device and cannot be tuned per device. This integration exposes
`scan_interval` as an options-flow setting (`DEFAULT_SCAN_INTERVAL_SECONDS`,
`MIN_SCAN_INTERVAL_SECONDS`, `MAX_SCAN_INTERVAL_SECONDS` in `const.py`), with
a longer default for Corentium Home 2 (`CORENTIUM_HOME_2_SCAN_INTERVAL_SECONDS`)
to match its slower sample cadence.

# Protocol

Sourced from Airthings' official `airthings-ble` library
(github.com/Airthings/airthings-ble) and cross-checked against the original
Airthings `waveplus-reader` reference scripts. Where Airthings has not
published a formal protocol spec (the Wave Enhance / Corentium Home 2 "Atom"
RPC layer), the library source is the closest thing to one.

## Atom RPC layer (Wave Enhance / Corentium Home 2)

Request "paths" (`ATOM_PATH_LATEST_SAMPLES`, `ATOM_PATH_CONNECTIVITY_MODE` in
`const.py`) are UTF-8 strings written to `CHAR_UUID_ATOM_WRITE`. The
CBOR-encoded response arrives via `CHAR_UUID_ATOM_NOTIFY`, reassembled across
multiple notify packets for larger payloads.

| Fact | Verified |
| --- | --- |
| Request paths are UTF-8 strings | verified (airthings-ble source) |
| Response is CBOR, reassembled across notify packets | verified (airthings-ble source) |

## Battery voltage to percentage

Two-cell CR2032-class devices (Wave Plus, Wave Radon) and three-cell devices
(Wave Mini) discharge on different voltage curves, so a shared curve
under- or over-reports remaining life. `BATTERY_CURVE_TWO_CELL` and
`BATTERY_CURVE_THREE_CELL` in `const.py` hold piecewise-linear interpolation
breakpoints (voltage, percentage) per chemistry/cell-count, keyed by
`DeviceModel`.

| Fact | Verified |
| --- | --- |
| Two-cell and three-cell devices need separate curves | verified (airthings-ble source) |
| Exact breakpoint values | verified (airthings-ble source) |

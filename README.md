# Airthings BLE for Home Assistant

A from-scratch, local-only Home Assistant custom integration for Airthings
consumer air-quality monitors, built to work toward the **Platinum**
Integration Quality Scale tier.

## Why this exists, and what it deliberately does *not* cover

This project started from a broader goal: rework Airthings support in Home
Assistant end-to-end -- local connections, write support, negotiable
transport performance, and cross-integration interoperability (HVAC,
window/door sensors, outdoor weather stations). Research into Airthings'
actual protocols narrowed that scope in one important way:

- **Airthings View / View Plus / View Pollution have no local API.**
  Airthings' own `airthings-ble` library explicitly refuses to read sensor
  data from View-series devices over BLE (BLE is setup-only on that
  hardware), and there is no documented local HTTP/REST endpoint anywhere
  in Airthings' public docs, GitHub org, or the wider open-source
  ecosystem. View devices stream exclusively to Airthings' cloud. Any
  integration covering them is necessarily `cloud_polling`, not local --
  that's out of scope here.
- **Wave Plus, Wave Mini, Wave Radon, Wave Enhance, and Corentium Home 2
  are fully local via Bluetooth LE**, with a documented (if
  unofficial-outside-the-source-code) GATT protocol. This integration
  targets those devices.
- **No Airthings device documents a way to write configuration** (display
  units, LED behavior, calibration, sample interval) over BLE or any API.
  The only "write" in the protocol is a request/response RPC to read
  battery voltage or (on Enhance/Corentium) other sensor fields --
  there is nothing to expose as an HA `number`/`select`/`switch` entity
  today.
- **BLE connection interval/PHY/MTU negotiation is not exposed** by
  Airthings' firmware or documented anywhere; the host BLE stack picks
  these. The one real, user-facing latency/battery tradeoff *is*
  configurable here: the active-connection **poll interval**, via this
  integration's options flow (fixing a long-standing complaint that
  upstream's `airthings_ble` hardcodes 5/30 minutes with no override).

See `custom_components/airthings_local/const.py` for the full protocol
reference (GATT UUIDs, struct layouts, scaling factors, battery discharge
curves) with citations, and [docs/README.md](docs/README.md) for the
protocol and design documentation this project maintains.

## Relationship to Home Assistant core's `airthings` / `airthings_ble`

Home Assistant core already ships both an `airthings` (cloud) and
`airthings_ble` (local BLE) integration; neither carries a
`quality_scale` rating. Known gaps this project addresses:

- Fixed, non-configurable poll interval -> options flow here.
- Reported reconnect flakiness / entities going unavailable -> uses
  `bleak-retry-connector` with bounded retry, and coordinator-driven
  `entity-unavailable` handling.
- Battery percentage mismatches vs. the official app -> per-chemistry
  (two-cell vs. three-cell) voltage curves, not a single shared curve.
- Missing Wave 2/Radon battery entity -> read via the same command/notify
  RPC used for Wave Plus, model-parameterized.
- No local coverage for the newer Wave Enhance / Corentium Home 2 "Atom"
  CBOR RPC protocol -> implemented (`client.py::_read_atom_sensor_data`),
  though this layer is undocumented outside library source and should be
  validated against real hardware before being trusted.

This integration uses the domain `airthings_local`, not `airthings_ble`.
An earlier revision reused core's exact domain to shadow/replace its
built-in integration, but that collides with the domain Home Assistant's
brands registry already has registered for core's `airthings_ble`, which
means it could never be validated for or listed in the HACS default store.
A distinct domain lets this integration and core's `airthings`/`airthings_ble`
coexist normally; if you were previously relying on this project
overriding core's built-in integration, you will need to disable that one
yourself (`airthings_ble` under Settings -> Devices & Services) to avoid
duplicate entities.

## Interoperability

Every sensor uses Home Assistant's standard `SensorDeviceClass` values
(`carbon_dioxide`, `volatile_organic_compounds_parts`, `radon`,
`temperature`, `humidity`, `atmospheric_pressure`, `battery`,
`signal_strength`) so it composes with other integrations in automations
without custom glue:

- **Davis WeatherLink / WeatherFlow Tempest** outdoor sensors use the same
  device classes for temperature/humidity/pressure -- indoor (Airthings)
  vs. outdoor comparisons are just two entities of the same device_class.
- **ELK-M1** zone `binary_sensor`s do *not* set a `device_class` by
  default (a known ELK-M1 integration limitation) -- reclassify those
  entities via customization, or reference them by `entity_id` directly;
  see `blueprints/automation/airthings/ventilation_recommendation.yaml`
  for a worked example that handles this.
- **HVAC/fan/humidifier** control from Airthings thresholds should call
  the generic `climate.set_temperature` / `fan.turn_on` /
  `humidifier.turn_on` services -- this integration intentionally does not
  bake ventilation logic into sensor entities; see the shipped blueprint.

## Home Assistant Quality Scale status

Current: targeting **Silver**, built toward **Platinum**. Honest gap list:

| Tier | Status |
| --- | --- |
| Bronze | Config flow (Bluetooth discovery + manual), unique IDs, `has_entity_name`, `runtime_data`, `ConfigEntryNotReady` on startup failure -- implemented. Config-flow test coverage is scaffolded but not yet verified at 100% against a real HA test environment. |
| Silver | Options flow (poll interval), `entity_unavailable` via coordinator, reauth N/A (no credentials to expire on BLE) -- mostly implemented. `test-coverage` >95% not yet met; decoder logic is unit-tested (`tests/components/airthings_local/test_decoders.py`, verified), HA-level config-flow/sensor tests pass in CI. |
| Gold | `diagnostics.py` with redaction, `entity_category` for diagnostic entities, `entity_disabled_by_default` for noisy sensors, reconfigure flow -- implemented. `dynamic-devices`/`stale-devices` not applicable (one device per config entry). Full documentation set (`docs-troubleshooting`, `docs-known-limitations`, etc.) not yet written beyond this README. |
| Platinum | `async-dependency`: fully async client (`bleak`/`bleak-retry-connector`), no executor-wrapped sync I/O -- done. `strict-typing`: `py.typed` marker + `mypy --strict` config in `pyproject.toml` -- configured, not yet CI-verified clean. `inject-websession`: N/A, this integration makes no HTTP calls. |

**Not yet done, tracked as next steps:** validate the
Wave Enhance/Corentium Home 2 Atom-protocol decoding against real hardware
(only the struct-based Wave Plus/Mini/Radon/Gen1 decoders have been
verified against hand-built payloads so far); write the remaining
Gold-tier documentation pages; submit to the [`home-assistant/brands`](https://github.com/home-assistant/brands)
repo and HACS default store once stable.

## Installation

Via HACS (custom repository) or manually: copy
`custom_components/airthings_local/` into your Home Assistant `config/custom_components/`
directory and restart. Devices are discovered automatically via Home
Assistant's Bluetooth integration; supported models: Wave, Wave Mini,
Wave Plus, Wave Radon (Wave 2), Wave Enhance, Corentium Home 2.

## Development

```bash
pip install -r requirements_test.txt
pytest tests/components/airthings_local/test_decoders.py  # no HA dependency required
pytest tests/                                              # full suite, requires HA test harness
ruff check custom_components tests
mypy custom_components/airthings_local
```

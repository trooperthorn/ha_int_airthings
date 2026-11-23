# Decisions

Dated decisions with the alternative rejected and why.

## 2026-11-23: Test harness is pytest-homeassistant, pinned with core

`pytest-homeassistant-custom-component` stopped at 0.13.375 (core 2026.10.4); its
README points to `pytest-homeassistant`, which home-assistant/core now publishes
itself. Core 2026.11 moved to `httpx2` and the old plugin fails before collection, so
the suite could not follow core past 2026.10. `requirements_test.txt` now pins
`pytest-homeassistant[bluetooth]==2026.11.1` next to `homeassistant==2026.11.1`. Each
harness release pins the exact matching core, pytest and pytest-asyncio, so the two
pins must move together and the local `pytest>=8.0.0` range is gone. The `bluetooth`
extra replaces the hand-kept `serialx` and `aiousbwatcher` pins. Per the package
README, `pyproject.toml` sets `asyncio_default_fixture_loop_scope`, `pythonpath` and
`-p no:respx` (the harness installs respx; its pytest plugin would import httpx
before core installs its alias), and `tests/conftest.py` drops the `pytest_plugins`
registration and the `enable_custom_integrations` wrapper, since the plugin loads by
entry point and enables custom integrations by default. `hacs.json` keeps 2026.10.0
as the minimum: the integration code did not change.

Rejected: staying on core 2026.10.4 with the old harness, which freezes the tested
core at a release that no longer gets fixes.

## 2026-10-08: Minimum Home Assistant is 2026.10.0, schemas use probatio

Core 2026.10 types `async_show_form(data_schema=...)` as a probatio schema, so
the voluptuous schemas failed mypy (developer blog 2026-09-30, "Probatio is our
validation engine"). The config and options flows now import `probatio`
directly, as core does. The suite pins core 2026.10.0 (and `serialx` 1.11.0 to
match its constraints), and `hacs.json` follows the tested core. Rejected:
aliasing `probatio as vol`, which core's lint config bans.

## 2026-09-06: packages core constrains are declared as ranges

Home Assistant installs a custom integration's requirements with core's own
`package_constraints.txt` passed to pip as a constraint (`homeassistant/requirements.py`,
`homeassistant/util/package.py`). `bleak` and `bleak-retry-connector` are both in that
file, so an exact pin in this manifest only installs while it equals core's pin, and the
next core point release that moves either package makes the install unsatisfiable and
fails setup with "Requirements for airthings_local not found". That is what happened to
the Elk-M1 and Davis integrations on 2026-09-06 when core 2026.9.1 moved `serialx`.
The manifest now declares `bleak>=3.0.2,<4` and `bleak-retry-connector>=4.7.0,<5`, so
core's constraint picks the version. Installs stay reproducible on a given core, because
the constraint file fixes the version regardless of the range. `cbor2` is not
core-constrained and keeps its exact pin. hassfest only requires exact pins for core
integrations.

Rejected: exact pins tracked by hand against every core release, which is the failure
mode this replaces.

## 2026-09-29: Atom requests use the airthings-ble framing; the View Plus stays unsupported

Rejected: keeping the bare UTF-8 path write and flat CBOR decode. airthings-ble frames every
request with a prefix, a random token, and a CBOR-encoded path, and validates a header and the
echoed token before decoding a nested payload (see protocol.md). The bare form was never tested
on hardware and does not match the only reference implementation, so Wave Enhance and Corentium
Home 2 support is treated as unproven until now.

Rejected: mapping the View Plus (2960) as an Atom model. A GATT dump showed it exposes only the
Atom channel, so the latest-samples request was tried from a workstation. The View Plus answered
with a "not found" style reply for that path, and an HCI snoop capture showed the Airthings app
never connects to it over Bluetooth to show readings (see protocol.md). Mapping it would make
every poll fail, so discovery keeps ending in "not supported".

`cbor2` is now imported at module level rather than inside the Atom path, so it is also listed
in `requirements_test.txt`; the lazy import had hidden that the test environment lacked it.

# Decisions

Dated decisions with the alternative rejected and why.

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

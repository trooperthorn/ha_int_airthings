# Security Policy

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials, private
addresses, or logs. Use GitHub's private vulnerability-reporting feature for
this repository. If private reporting is unavailable, open a minimal issue
asking the maintainer to establish a private channel; omit technical details.

Include the affected version/commit, prerequisites, impact, a minimal
reproduction, and suggested remediation. Remove tokens, API keys, device
addresses, and private network details.

## Response targets

These are project targets, not an SLA: acknowledge critical/high reports in
three business days, establish severity and containment in seven, and publish
a coordinated fix/advisory as soon as safely validated. Lower-severity issues
are prioritized by exploitability and impact.

## Supported version

Only the latest published release and the default branch receive security
fixes. Operators should keep Home Assistant and this integration current and
retain a tested rollback/backup.

## Security boundaries

Airthings BLE for Home Assistant is a local-only, read-only integration: it
connects to Airthings devices over Bluetooth LE to read sensor data and does
not accept remote input or expose a network service of its own. It cannot
prevent a malicious integration in the same Python process from reading
shared memory or files, and it does not encrypt or authenticate the BLE link
beyond what the device itself implements. Its findings are sensor readings,
not a security certification.

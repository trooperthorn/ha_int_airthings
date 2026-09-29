# Protocol

Sourced from Airthings' official `airthings-ble` library
(github.com/Airthings/airthings-ble) and cross-checked against the original
Airthings `waveplus-reader` reference scripts. Where Airthings has not
published a formal protocol spec (the Wave Enhance / Corentium Home 2 "Atom"
RPC layer), the library source is the closest thing to one.

## Atom RPC layer (Wave Enhance / Corentium Home 2)

Source: airthings-ble v1.2.0 (commit b351266a, 2026-09-13), `atom/request.py`,
`atom/response.py`, `command_decode.py`, and `parser.py`.

A request is written to `CHAR_UUID_ATOM_WRITE` (b42eb73a) as:

| Bytes | Meaning |
| --- | --- |
| `03 01` | Request prefix. |
| 2 bytes | Random token; the response must echo it. |
| `81 a1 00` | Fixed infix. |
| CBOR text string | Request path, for example `29999/0/31012` (latest samples) or `17/0/31100` (connectivity mode). |

The response arrives on `CHAR_UUID_ATOM_NOTIFY` (b42ebc9e):

| Bytes | Meaning |
| --- | --- |
| `10 01 00 03 45` | Response header. |
| 2 bytes | The request token. |
| CBOR from byte 7 | A list whose first element is a map: key 0 is the request path, key 2 is the payload. For latest samples the payload is either a map or a byte string holding a CBOR map. |

Sample keys and scaling: `TMP` kelvin x 100, `HUM` percent x 100, `PRS` hPa x 6400, `CO2` ppm, `VOC` ppb, `NOI` dB, `LUX` lux, `R24`, `R7D`, `R30`, `R1Y` radon averages in Bq/m3, `BAT` millivolts.

airthings-ble completes the message on the first notify packet (its Atom receiver expects a size of 0), so it relies on the negotiated MTU holding the whole response. This integration does the same.

| Fact | Verified |
| --- | --- |
| Request framing and response header | verified (airthings-ble source) |
| Sample keys and scaling | verified (airthings-ble source) |
| The 30-day radon key is `R30` | verified (airthings-ble `const.py`); this integration read `R30D` before 2026-09-29 |
| A device accepts this request framing and echoes the token | verified on a View Plus (see below) |
| Wave Enhance and Corentium Home 2 return samples with the `10 01 00 03 45` header | unverified; no hardware test yet |

## View Plus (model 2960)

A read-only GATT dump taken with HA BT Scout on 2026-09-29 (firmware `A-BLE-2.2.8-release+0`, hardware `REV 1,0`) found Generic Access, Generic Attribute, TI OAD (f000ffc0), Device Information (model `2960`, manufacturer `Airthings AS`), and service b42eb4a6 containing b42eb73a (write), b42eb9f6 (write), and b42ebc9e (notify). No readable sensor characteristic exists, so the Atom request was the only candidate path to readings; the probe and the app capture below rule out the known path. The advertised 820 manufacturer data begins with the serial number as a little-endian u32.

### Probe of 2026-09-29

Sent from a Windows host with bleak (MTU 251), one notify packet per reply:

| Request | Reply | Reading |
| --- | --- | --- |
| Bare UTF-8 path `29999/0/31012` | `32a03939` | Not a frame. The bare form is wrong. |
| Framed `17/0/31100` (connectivity mode) | `0345` + token + `81a2006a31372f302f33313130300202` | `[{0: "17/0/31100", 2: 2}]`. A valid answer with the token echoed. airthings-ble maps 0, 1, and 4 only, so 2 is unknown to it. |
| Framed `29999/0/31012` (latest samples) | `0384` + token + `81a2006933303031302f302f30026d32393939392f302f3331303132` | `[{0: "30010/0/0", 2: "29999/0/31012"}]`. A refusal naming the requested path. |

Verified by this probe: the View Plus accepts the airthings-ble request framing and echoes the token; its reply header is the two bytes `03 xx`, without the `10 01 00` that airthings-ble expects in front; and it does not serve `29999/0/31012`.

### Airthings app capture of 2026-09-29

An Android HCI snoop log (mode full) was captured on the phone from 17:01:46 to 17:04:59 local time while the Airthings app showed the View Plus dashboard, was refreshed, and opened the radon history (17:02:54 to 17:04:11). The log holds no LE connection event and no ACL data at all, so the app read nothing from the View Plus over Bluetooth; every value it showed came from the Airthings cloud. With the probe result, this is why the View Plus is not mapped: no local request path to its samples is known, and the vendor app does not use one.

### Unverified

- That the second header byte is a CoAP-style response code (`0x45` = 2.05 Content, `0x84` = 4.04 Not Found). The two replies fit it; no source documents it.
- Whether `10 01 00` is a transport prefix the View Plus omits or a Wave Enhance specific header.
- Which request path, if any, returns View Plus sensor samples. Finding one would take guessing paths against the device, since the vendor app does not reveal one.
- The purpose of b42eb9f6.
- Whether View Pollution (2980) and View Radon (2989) share the layout. They are not mapped.

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

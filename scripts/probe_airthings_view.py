#!/usr/bin/env python3
"""Read-only local-network probe for an Airthings View device.

Run this ON YOUR LAN (this repo's cloud session cannot reach private IPs).
Only targets the single host you pass in -- no network scanning beyond
that. Pure standard library, no dependencies required.

Usage:
    python3 scripts/probe_airthings_view.py 192.168.1.57

What it does:
  1. TCP-connects to a short list of ports commonly used by IoT devices
     for a local HTTP/HTTPS API, MQTT, or CoAP (Airthings has never
     published a local API for View, so this is exploratory).
  2. For any open HTTP(S) port, sends GET requests to a list of
     plausible paths (root, /api, /status, /info, /local-api,
     /latest-samples, /.well-known/*, mDNS-style device info, etc.) and
     prints status code + first ~500 bytes of the response body so we
     can see what's actually there.
  3. Sends an SSDP M-SEARCH multicast probe (UDP) and listens briefly for
     any UPnP device announcing itself, in case the View responds to
     discovery even without a documented control API.
  4. Prints raw HTTP response headers for anything that responds --
     headers alone (Server:, WWW-Authenticate:, etc.) are useful even if
     the body is empty or requires auth.

This is intentionally read-only: GET requests and connection probes
only, no writes, no credential guessing, no brute forcing.
"""
from __future__ import annotations

import http.client
import socket
import ssl
import sys
import time

COMMON_PORTS = [80, 443, 8080, 8443, 5000, 5683, 1883, 8883, 8888, 9999, 502]

# Paths worth trying against any open HTTP(S) port. Airthings has not
# published any of these -- this is a speculative sweep based on common
# IoT local-API conventions (similar devices often expose one of these).
CANDIDATE_PATHS = [
    "/",
    "/api",
    "/api/v1",
    "/status",
    "/info",
    "/device",
    "/device-info",
    "/sensors",
    "/sensor-data",
    "/latest-samples",
    "/local-api",
    "/local",
    "/data",
    "/measurements",
    "/config",
    "/settings",
    "/.well-known/ha-local-api",
    "/description.xml",  # common UPnP/SSDP device description path
]

CONNECT_TIMEOUT = 2.0
READ_TIMEOUT = 3.0


def probe_port(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=CONNECT_TIMEOUT):
            return True
    except OSError:
        return False


def try_http(host: str, port: int, use_tls: bool) -> None:
    scheme = "https" if use_tls else "http"
    for path in CANDIDATE_PATHS:
        try:
            if use_tls:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                conn = http.client.HTTPSConnection(
                    host, port, timeout=READ_TIMEOUT, context=ctx
                )
            else:
                conn = http.client.HTTPConnection(host, port, timeout=READ_TIMEOUT)
            conn.request(
                "GET",
                path,
                headers={"User-Agent": "airthings-view-probe/1.0", "Accept": "*/*"},
            )
            resp = conn.getresponse()
            body = resp.read(500)
            headers = dict(resp.getheaders())
            conn.close()

            if resp.status != 404:
                print(f"\n=== {scheme}://{host}:{port}{path} -> HTTP {resp.status} ===")
                for key in ("Server", "WWW-Authenticate", "Content-Type", "Content-Length"):
                    if key in headers:
                        print(f"  {key}: {headers[key]}")
                snippet = body.decode("utf-8", errors="replace").strip()
                if snippet:
                    print(f"  Body (first 500 bytes): {snippet!r}")
        except Exception as err:  # noqa: BLE001 - best-effort probe
            pass  # silent: most paths will just fail to connect/timeout


def ssdp_discover(timeout: float = 3.0) -> None:
    print("\n=== SSDP M-SEARCH discovery (3s listen window) ===")
    msg = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 2\r\n"
        "ST: ssdp:all\r\n\r\n"
    ).encode("utf-8")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(timeout)
    try:
        sock.sendto(msg, ("239.255.255.250", 1900))
        end = time.time() + timeout
        seen = set()
        while time.time() < end:
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                break
            if addr[0] not in seen:
                seen.add(addr[0])
                print(f"  Response from {addr[0]}:")
                for line in data.decode("utf-8", errors="replace").splitlines():
                    print(f"    {line}")
        if not seen:
            print("  No SSDP responses received.")
    finally:
        sock.close()


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <device-ip>", file=sys.stderr)
        sys.exit(1)

    host = sys.argv[1]
    print(f"Probing {host} ...")

    print("\n=== TCP port scan (common IoT/API ports) ===")
    open_ports: list[int] = []
    for port in COMMON_PORTS:
        is_open = probe_port(host, port)
        print(f"  {port}: {'OPEN' if is_open else 'closed/filtered'}")
        if is_open:
            open_ports.append(port)

    if not open_ports:
        print("\nNo common ports open -- device likely does not expose a local API.")
    else:
        for port in open_ports:
            if port in (443, 8443, 8883):
                try_http(host, port, use_tls=True)
            elif port in (80, 8080, 5000, 8888, 9999):
                try_http(host, port, use_tls=False)

    ssdp_discover()

    print(
        "\nDone. If nothing meaningful was found above (all 404/closed, no SSDP "
        "response), this matches the research finding that Airthings View has no "
        "documented or discoverable local API -- it communicates with Airthings' "
        "cloud only. Paste this full output back and it'll be analyzed either way."
    )


if __name__ == "__main__":
    main()

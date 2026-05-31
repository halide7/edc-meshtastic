"""The provisioning commands: router, verify, fam.

Each mirrors one of the original shell scripts but talks to the device through
the structured meshtastic API and verifies against :mod:`profiles`.
"""

from __future__ import annotations

import sys

from . import device, profiles
from .device import Channel, DeviceError

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


def _ok(msg: str) -> None:
    print(f"    {GREEN}OK{RESET}   {msg}")


def _fail(msg: str) -> None:
    print(f"    {RED}FAIL{RESET} {msg}")


def _summary(msg: str, *, stream=sys.stdout) -> None:
    """Print a final summary line, flushing stdout first so detail lines
    (stdout) and a stderr summary don't interleave out of order."""
    sys.stdout.flush()
    print(f"\n{msg}", file=stream)
    stream.flush()


def _apply_profile(iface, profile: dict) -> set[str]:
    """Set every dotted field in ``profile``; return the config groups touched."""
    groups: set[str] = set()
    for dotted, value in profile.items():
        groups.add(device.set_config_value(iface, dotted, value))
    return groups


def verify_profile(iface, profile: dict) -> bool:
    """Compare live config against ``profile``. Print OK/FAIL per field."""
    all_ok = True
    for dotted, expected in profile.items():
        actual = device.get_config_value(iface, dotted)
        if actual == expected:
            _ok(f"{dotted:<24} = {profiles.label_for(dotted, actual)}")
        else:
            _fail(
                f"{dotted:<24} = {profiles.label_for(dotted, actual)} "
                f"(expected {profiles.label_for(dotted, expected)})"
            )
            all_ok = False
    return all_ok


# --------------------------------------------------------------------------- #
# router
# --------------------------------------------------------------------------- #
def cmd_router(port: str | None) -> int:
    print(">>> Provisioning EDC router profile")
    with device.connect(port) as iface:
        groups = _apply_profile(iface, profiles.ROUTER_PROFILE)
        for group in sorted(groups):
            device.write_config_group(iface, group)
    print(">>> Config written; waiting for reboot...")
    device.wait_for_reboot(port)
    print(">>> Verifying:")
    with device.connect(port) as iface:
        ok = verify_profile(iface, profiles.ROUTER_PROFILE)
    if ok:
        _summary(">>> SUCCESS: node configured as an EDC router.")
        return 0
    _summary(">>> WARNING: one or more settings did not persist.", stream=sys.stderr)
    return 1


# --------------------------------------------------------------------------- #
# verify  (read-only, no reboot)
# --------------------------------------------------------------------------- #
def cmd_verify(port: str | None) -> int:
    print(">>> Verifying against EDC router profile (read-only):")
    with device.connect(port) as iface:
        ok = verify_profile(iface, profiles.ROUTER_PROFILE)
    if ok:
        _summary(">>> PASS: node matches the EDC router profile.")
        return 0
    _summary(">>> FAIL: node does NOT match the EDC router profile.\n"
             "    Run `meshprov router` to (re)apply the config.", stream=sys.stderr)
    return 1


# --------------------------------------------------------------------------- #
# fam
# --------------------------------------------------------------------------- #
def cmd_fam(
    port: str | None,
    long_name: str,
    short_name: str,
    mute: bool,
    fam_psk: bytes,
    ops_psk: bytes,
    fam_src: str,
    ops_src: str,
) -> int:
    role = device.Role.CLIENT_MUTE if mute else device.Role.CLIENT
    print(f">>> Provisioning fam node: long='{long_name}' short='{short_name}' "
          f"role={device.Role.Name(role)}")
    print(f">>> Fam key: {fam_src}   EDC-MeshOps key: {ops_src}")

    radio = dict(profiles.FAM_RADIO)
    radio["device.role"] = role

    with device.connect(port) as iface:
        groups = _apply_profile(iface, radio)
        for group in sorted(groups):
            device.write_config_group(iface, group)
        device.disable_position(iface)
    print(">>> Radio + position written; waiting for reboot...")
    device.wait_for_reboot(port)

    with device.connect(port) as iface:
        device.set_owner(iface, long_name, short_name)
        device.set_channel(iface, Channel(
            index=0, name=profiles.FAM_CHANNEL_NAME, psk=fam_psk, position_precision=0))
        device.set_channel(iface, Channel(
            index=1, name=profiles.OPS_CHANNEL_NAME, psk=ops_psk, position_precision=0))

    print(">>> Verifying:")
    expected = dict(profiles.FAM_RADIO)
    expected["device.role"] = role
    expected["position.gps_mode"] = device.GpsMode.DISABLED
    with device.connect(port) as iface:
        ok = verify_profile(iface, expected)
        ok &= _verify_channels(iface)
    if ok:
        _summary(f">>> SUCCESS: fam node '{long_name}' ({short_name}) provisioned.")
        return 0
    _summary(">>> WARNING: some settings did not verify.", stream=sys.stderr)
    return 1


def _verify_channels(iface) -> bool:
    ok = True
    print(">>> Channels:")
    for index, expected_name in ((0, profiles.FAM_CHANNEL_NAME),
                                 (1, profiles.OPS_CHANNEL_NAME)):
        chan = iface.localNode.getChannelByChannelIndex(index)
        actual = chan.settings.name if chan else "<none>"
        if actual == expected_name:
            _ok(f"channel {index} name = {actual}")
        else:
            _fail(f"channel {index} name = {actual} (expected {expected_name})")
            ok = False
    return ok

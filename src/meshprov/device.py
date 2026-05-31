"""Device connection + config helpers built on the meshtastic library.

This wraps the parts of the meshtastic Python API the provisioning commands
need, so the command modules stay declarative. Everything works against the
structured protobuf config objects (e.g. ``node.localConfig.lora.region``)
rather than scraping CLI text output.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass

import meshtastic
import meshtastic.serial_interface
from meshtastic.protobuf import channel_pb2, config_pb2

# Enum shortcuts (resolved from the installed protobufs, never hard-coded ints).
Role = config_pb2.Config.DeviceConfig.Role
ModemPreset = config_pb2.Config.LoRaConfig.ModemPreset
RegionCode = config_pb2.Config.LoRaConfig.RegionCode
RebroadcastMode = config_pb2.Config.DeviceConfig.RebroadcastMode
GpsMode = config_pb2.Config.PositionConfig.GpsMode


class DeviceError(RuntimeError):
    """Raised when we cannot talk to a node or a write does not take."""


@contextmanager
def connect(port: str | None = None, *, connect_timeout: float = 30.0):
    """Open a serial connection to a node, yielding the SerialInterface.

    ``port`` of None lets the library auto-detect a single connected device.
    Closes the interface on exit.
    """
    try:
        iface = meshtastic.serial_interface.SerialInterface(devPath=port)
    except Exception as exc:  # noqa: BLE001 — surface any connect failure uniformly
        target = port or "auto-detected port"
        raise DeviceError(f"could not connect to node on {target}: {exc}") from exc
    try:
        yield iface
    finally:
        try:
            iface.close()
        except Exception:  # noqa: BLE001 — best-effort close
            pass


def wait_for_reboot(port: str | None = None, *, settle: float = 3.0,
                    timeout: float = 60.0, poll: float = 3.0) -> None:
    """Block until the node is reachable again after a reboot.

    A config change that requires a reboot drops the serial link. We give the
    device a moment to actually go down (``settle``), then poll by opening a
    fresh connection until one succeeds or ``timeout`` elapses. This replaces
    the shell scripts' fixed ``sleep 30``.
    """
    time.sleep(settle)
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            iface = meshtastic.serial_interface.SerialInterface(devPath=port)
            iface.close()
            return
        except Exception as exc:  # noqa: BLE001 — keep polling until timeout
            last_exc = exc
            time.sleep(poll)
    raise DeviceError(
        f"node did not come back within {timeout:.0f}s after reboot: {last_exc}"
    )


@dataclass(frozen=True)
class Channel:
    """Desired state for one channel slot."""

    index: int
    name: str
    psk: bytes              # raw key bytes (16 or 32); empty = leave default
    position_precision: int = 0


def get_config_value(iface, dotted: str) -> int:
    """Read a dotted config path like ``lora.region`` from the live config.

    The first segment selects the config group (``device``, ``lora``,
    ``position`` …) on ``localConfig``; the rest is the field name.
    """
    group, _, field = dotted.partition(".")
    cfg = getattr(iface.localNode.localConfig, group)
    return getattr(cfg, field)


def set_config_value(iface, dotted: str, value) -> str:
    """Set a dotted config path in place. Returns the group name written.

    Caller is responsible for calling :func:`write_config_group` (so several
    fields in the same group can be batched into one write).
    """
    group, _, field = dotted.partition(".")
    cfg = getattr(iface.localNode.localConfig, group)
    setattr(cfg, field, value)
    return group


def write_config_group(iface, group: str) -> None:
    iface.localNode.writeConfig(group)


def set_owner(iface, long_name: str, short_name: str) -> None:
    iface.localNode.setOwner(long_name=long_name, short_name=short_name)


def set_channel(iface, ch: Channel) -> None:
    """Configure one channel slot in place and write it to the device.

    Index 0 is the PRIMARY channel; any other index is SECONDARY. Unlike the
    CLI's ``--ch-add``, setting a channel's name directly here has no special
    length restriction beyond the firmware's own limit, so ``EDC-MeshOps``
    (11 chars) works without a placeholder dance.
    """
    node = iface.localNode
    chan = node.getChannelByChannelIndex(ch.index)
    if chan is None:
        raise DeviceError(f"channel index {ch.index} is not available on this node")

    chan.role = (
        channel_pb2.Channel.Role.PRIMARY
        if ch.index == 0
        else channel_pb2.Channel.Role.SECONDARY
    )
    chan.settings.name = ch.name
    if ch.psk:
        chan.settings.psk = ch.psk
    chan.settings.module_settings.position_precision = ch.position_precision
    node.writeChannel(ch.index)


def disable_position(iface) -> None:
    """Turn off GPS and position broadcasting (no location leak)."""
    pos = iface.localNode.localConfig.position
    pos.gps_mode = GpsMode.DISABLED
    pos.position_broadcast_smart_enabled = False
    pos.position_broadcast_secs = 0
    iface.localNode.writeConfig("position")

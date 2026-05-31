"""Shared provisioning profiles — the single source of truth for desired state.

These mirror the validated shell-script profiles. Verification compares the
device's actual config against the integers/strings here.
"""

from __future__ import annotations

from .device import ModemPreset, RebroadcastMode, RegionCode, Role

# --- EDC router profile -----------------------------------------------------
# Infrastructure node: rebroadcasts everything on the EDC radio settings.
ROUTER_PROFILE = {
    "device.role": Role.ROUTER,
    "device.rebroadcast_mode": RebroadcastMode.ALL,
    "lora.region": RegionCode.US,
    "lora.modem_preset": ModemPreset.SHORT_TURBO,
    "lora.channel_num": 30,
    "lora.hop_limit": 3,
}

# --- Fam radio profile ------------------------------------------------------
# Client nodes carried by people. Same radio as the routers so they interoperate.
FAM_RADIO = {
    "lora.region": RegionCode.US,
    "lora.modem_preset": ModemPreset.SHORT_TURBO,
    "lora.channel_num": 30,
}

FAM_CHANNEL_NAME = "Fam"          # channel 0 (primary), shared reused key
OPS_CHANNEL_NAME = "EDC-MeshOps"  # channel 1 (secondary)

# Human-readable labels for verify output.
ENUM_LABELS = {
    "device.role": Role,
    "device.rebroadcast_mode": RebroadcastMode,
    "lora.region": RegionCode,
    "lora.modem_preset": ModemPreset,
}


def label_for(dotted: str, value: int) -> str:
    """Return the enum name for a value, or just the value if not an enum."""
    enum = ENUM_LABELS.get(dotted)
    if enum is None:
        return str(value)
    try:
        return f"{value} ({enum.Name(value)})"
    except ValueError:
        return str(value)

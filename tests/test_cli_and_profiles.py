"""Tests for CLI helpers and profile definitions — no hardware required."""

from meshprov import profiles
from meshprov.cli import _derive_short, build_parser
from meshprov.device import ModemPreset, RegionCode, Role


def test_derive_short_basic():
    assert _derive_short("Node One") == "NODE"


def test_derive_short_strips_nonalnum():
    assert _derive_short("J's Pebble!") == "JSPE"


def test_derive_short_uppercases_and_truncates():
    assert _derive_short("aria") == "ARIA"
    assert _derive_short("ab") == "AB"


def test_router_profile_uses_enum_values():
    assert profiles.ROUTER_PROFILE["device.role"] == Role.ROUTER
    assert profiles.ROUTER_PROFILE["lora.region"] == RegionCode.US
    assert profiles.ROUTER_PROFILE["lora.modem_preset"] == ModemPreset.SHORT_TURBO
    assert profiles.ROUTER_PROFILE["lora.channel_num"] == 30


def test_fam_radio_matches_router_radio():
    # Fam nodes must share the routers' radio params to interoperate.
    for key in ("lora.region", "lora.modem_preset", "lora.channel_num"):
        assert profiles.FAM_RADIO[key] == profiles.ROUTER_PROFILE[key]


def test_label_for_enum_and_plain():
    assert profiles.label_for("lora.region", int(RegionCode.US)) == "1 (US)"
    assert profiles.label_for("lora.channel_num", 30) == "30"


def test_parser_requires_subcommand():
    parser = build_parser()
    # fam requires --name
    args = parser.parse_args(["fam", "--name", "X"])
    assert args.command == "fam" and args.name == "X" and args.mute is False


def test_parser_fam_flags():
    parser = build_parser()
    args = parser.parse_args(["fam", "-n", "X", "-s", "ABCD", "--mute",
                              "-p", "/dev/cu.usbmodemX"])
    assert args.short == "ABCD" and args.mute is True
    assert args.port == "/dev/cu.usbmodemX"

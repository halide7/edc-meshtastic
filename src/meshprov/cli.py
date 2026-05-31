"""Command-line entry point for meshprov.

Subcommands:
  router            Provision the EDC router profile (writes + reboots + verifies).
  verify            Read-only spot check against the router profile (no reboot).
  fam --name ...    Provision a fam client node (two channels, position off).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import commands
from .device import DeviceError
from .keys import KeyError_, load_defaults, resolve_key

# fam-keys.env lives at the project root (two levels up from this file:
# src/meshprov/cli.py -> project root).
ENV_PATH = Path(__file__).resolve().parents[2] / "fam-keys.env"


def _derive_short(long_name: str) -> str:
    alnum = "".join(c for c in long_name if c.isalnum())
    return alnum[:4].upper()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meshprov",
        description="Provision Meshtastic nodes (EDC routers and fam client nodes).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Common: --port / -p on every subcommand.
    def add_port(p):
        p.add_argument("-p", "--port", default=None,
                       help="Serial port (e.g. /dev/cu.usbmodemXXXX or COM5). "
                            "Default: auto-detect the single connected node.")

    p_router = sub.add_parser("router", help="provision the EDC router profile")
    add_port(p_router)

    p_verify = sub.add_parser("verify", help="read-only check of the router profile")
    add_port(p_verify)

    p_fam = sub.add_parser("fam", help="provision a fam client node")
    add_port(p_fam)
    p_fam.add_argument("-n", "--name", required=True,
                       help="owner long name (the per-node unique attribute)")
    p_fam.add_argument("-s", "--short", default=None,
                       help="owner short name (<=4 chars). Default: first 4 "
                            "alphanumerics of --name, uppercased.")
    p_fam.add_argument("--mute", action="store_true",
                       help="provision as CLIENT_MUTE (for a person's second, "
                            "nearby node — participates but does not rebroadcast)")
    p_fam.add_argument("--fam-key", default=None,
                       help="override Fam (channel 0) key; base64 or 0xhex")
    p_fam.add_argument("--ops-key", default=None,
                       help="override EDC-MeshOps (channel 1) key; base64 or 0xhex")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "router":
            return commands.cmd_router(args.port)
        if args.command == "verify":
            return commands.cmd_verify(args.port)
        if args.command == "fam":
            short = args.short or _derive_short(args.name)
            env_defaults = load_defaults(ENV_PATH)
            fam_psk, fam_src = resolve_key(args.fam_key, env_defaults,
                                           "FAM_PSK_DEFAULT", "fam-key")
            ops_psk, ops_src = resolve_key(args.ops_key, env_defaults,
                                           "OPS_PSK_DEFAULT", "ops-key")
            return commands.cmd_fam(
                args.port, args.name, short, args.mute,
                fam_psk, ops_psk, fam_src, ops_src,
            )
    except KeyError_ as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except DeviceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

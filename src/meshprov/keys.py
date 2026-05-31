"""Channel key handling: load defaults from fam-keys.env, normalize inputs.

Secrets are never hard-coded. Default keys come from ``fam-keys.env`` (a local,
gitignored file) next to the project root; CLI ``--fam-key`` / ``--ops-key``
override them. Keys may be given as base64 or ``0x``-hex and are normalized to
raw bytes (16 or 32 long).
"""

from __future__ import annotations

import base64
import binascii
import os
from pathlib import Path


class KeyError_(ValueError):
    """Raised for a missing or malformed channel key."""


def normalize_key(value: str, label: str) -> bytes:
    """Parse a key given as ``0x``-hex or base64 into raw bytes.

    Validates the result is a 16- or 32-byte AES key.
    """
    value = value.strip()
    if value.lower().startswith("0x"):
        try:
            raw = bytes.fromhex(value[2:])
        except ValueError as exc:
            raise KeyError_(f"--{label}: invalid hex key: {value!r}") from exc
    else:
        try:
            raw = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise KeyError_(
                f"--{label}: key is neither valid 0x-hex nor base64: {value!r}"
            ) from exc
    if len(raw) not in (16, 32):
        raise KeyError_(
            f"--{label}: key must decode to 16 or 32 bytes (got {len(raw)}): {value!r}"
        )
    return raw


def _parse_env_file(path: Path) -> dict[str, str]:
    """Minimal KEY="value" / KEY=value parser for fam-keys.env."""
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def load_defaults(env_path: Path) -> dict[str, str]:
    """Return key defaults from fam-keys.env (empty dict if the file is absent)."""
    if not env_path.exists():
        return {}
    return _parse_env_file(env_path)


def resolve_key(
    cli_value: str | None,
    env_defaults: dict[str, str],
    env_var: str,
    label: str,
) -> tuple[bytes, str]:
    """Resolve a key: CLI override wins, then fam-keys.env, else error.

    Returns ``(raw_bytes, source)`` where source is "override" or "fam-keys.env".
    """
    if cli_value:
        return normalize_key(cli_value, label), "override"
    default = env_defaults.get(env_var) or os.environ.get(env_var)
    if default:
        return normalize_key(default, label), "fam-keys.env"
    raise KeyError_(
        f"no --{label} given and no {env_var} in fam-keys.env. "
        f"Provide --{label} <base64-or-0xhex>, or create fam-keys.env "
        f"(see fam-keys.env.example)."
    )

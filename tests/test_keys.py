"""Tests for key parsing/resolution — no hardware required."""

import base64

import pytest

from meshprov.keys import KeyError_, normalize_key, resolve_key, _parse_env_file


# 16-byte (AES-128) and 32-byte (AES-256) sample keys, as bytes.
KEY16 = bytes(range(16))
KEY32 = bytes(range(32))


def test_normalize_hex_16():
    assert normalize_key("0x" + KEY16.hex(), "k") == KEY16


def test_normalize_hex_32():
    assert normalize_key("0x" + KEY32.hex(), "k") == KEY32


def test_normalize_base64():
    b64 = base64.b64encode(KEY16).decode()
    assert normalize_key(b64, "k") == KEY16


def test_normalize_hex_uppercase_prefix():
    assert normalize_key("0X" + KEY16.hex(), "k") == KEY16


def test_normalize_strips_whitespace():
    b64 = base64.b64encode(KEY16).decode()
    assert normalize_key(f"  {b64}  ", "k") == KEY16


@pytest.mark.parametrize("bad", [
    "not-base64-or-hex!!",
    "0xzzzz",                    # invalid hex digits
    "0x0102",                    # valid hex but wrong length (2 bytes)
    base64.b64encode(b"short").decode(),   # valid base64, wrong length
])
def test_normalize_rejects_bad(bad):
    with pytest.raises(KeyError_):
        normalize_key(bad, "k")


def test_resolve_cli_override_wins():
    raw, src = resolve_key("0x" + KEY16.hex(), {"FAM_PSK_DEFAULT": "0x" + KEY32.hex()},
                           "FAM_PSK_DEFAULT", "fam-key")
    assert raw == KEY16 and src == "override"


def test_resolve_from_env_default():
    raw, src = resolve_key(None, {"OPS_PSK_DEFAULT": "0x" + KEY16.hex()},
                           "OPS_PSK_DEFAULT", "ops-key")
    assert raw == KEY16 and src == "fam-keys.env"


def test_resolve_missing_raises():
    with pytest.raises(KeyError_):
        resolve_key(None, {}, "FAM_PSK_DEFAULT", "fam-key")


def test_parse_env_file(tmp_path):
    p = tmp_path / "fam-keys.env"
    p.write_text(
        '# a comment\n'
        'FAM_PSK_DEFAULT="0xabc"\n'
        "OPS_PSK_DEFAULT='deadbeef'\n"
        "\n"
        "BARE=value\n"
    )
    parsed = _parse_env_file(p)
    assert parsed["FAM_PSK_DEFAULT"] == "0xabc"
    assert parsed["OPS_PSK_DEFAULT"] == "deadbeef"
    assert parsed["BARE"] == "value"

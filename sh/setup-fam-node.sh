#!/usr/bin/env bash
#
# setup-fam-node.sh — provision a "rave fam" client node.
#
# All inputs are named --switches. Per-node unique attributes (name/short) are
# passed in; everything else is the shared fam profile:
#   * role        CLIENT (or CLIENT_MUTE with --mute)
#   * radio       US / SHORT_TURBO / slot 30  (matches the EDC routers)
#   * position    OFF  (GPS disabled, no position broadcast, precision 0)
#   * channel 0   "Fam"          — shared fam key (baked-in default, reused on every fam node)
#   * channel 1   "EDC-MeshOps"  — shared ops key (baked-in default)
#
# Usage:
#   ./setup-fam-node.sh --name "<long name>" [options]
#
# Required:
#   --name, -n <str>      Owner long name (the per-node unique attribute).
#
# Optional:
#   --short, -s <str>     Owner short name (max 4 chars). Default: first 4
#                         alphanumerics of --name, uppercased.
#   --port, -p <dev>      Serial port, e.g. /dev/cu.usbmodem203101. Default:
#                         auto-detect the single connected node.
#   --mute                Provision as CLIENT_MUTE instead of CLIENT. Use for a
#                         person's SECOND node carried near their first — it
#                         participates but does NOT rebroadcast.
#   --fam-key <key>       Override the Fam (channel 0) key. Accepts base64 or
#                         0xhex. Default: read from fam-keys.env.
#   --ops-key <key>       Override the EDC-MeshOps (channel 1) key. Same formats.
#   -h, --help            Show this help.
#
# Examples:
#   ./setup-fam-node.sh --name "Node One" --short NOD1
#   ./setup-fam-node.sh -n "Backup Node" -s BAK1 --mute
#   ./setup-fam-node.sh -n "Node One" -p /dev/cu.usbmodemXXXX --ops-key <base64-or-0xhex>
set -euo pipefail

# ---- Shared fam profile keys -----------------------------------------------
# Secrets are NOT stored in this script. Default keys are read from a local,
# untracked file `fam-keys.env` (see fam-keys.env.example) that defines:
#     FAM_PSK_DEFAULT="0x...."   # or base64
#     OPS_PSK_DEFAULT="0x...."
# The file is sourced if present (looked for next to this script). If it is
# absent, the corresponding key MUST be supplied on the command line with
# --fam-key / --ops-key. Either way, --fam-key/--ops-key override the file.
FAM_PSK_DEFAULT=""
OPS_PSK_DEFAULT=""
_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$_SCRIPT_DIR/fam-keys.env" ]]; then
  # shellcheck disable=SC1091
  source "$_SCRIPT_DIR/fam-keys.env"
fi

usage() {
  # Print the leading comment block (lines starting with #), stripped of the
  # leading "# ". Stops at the first non-comment line.
  while IFS= read -r line; do
    case "$line" in
      \#!*) ;;                        # skip shebang
      \#)   echo "" ;;                # bare "#"
      \#\ *) echo "${line:2}" ;;      # "# text" -> "text"
      *) break ;;
    esac
  done < "$0"
}

# ---- Parse named args ------------------------------------------------------
LONG_NAME=""
SHORT_NAME=""
PORT=""
ROLE="CLIENT"; ROLE_INT=0          # CLIENT=0, CLIENT_MUTE=1
FAM_PSK_IN=""
OPS_PSK_IN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--name)    LONG_NAME="${2:-}";  shift 2 ;;
    -s|--short)   SHORT_NAME="${2:-}"; shift 2 ;;
    -p|--port)    PORT="${2:-}";       shift 2 ;;
    --mute)       ROLE="CLIENT_MUTE"; ROLE_INT=1; shift ;;
    --fam-key)    FAM_PSK_IN="${2:-}"; shift 2 ;;
    --ops-key)    OPS_PSK_IN="${2:-}"; shift 2 ;;
    -h|--help)    usage; exit 0 ;;
    --) shift; break ;;
    -*) echo "ERROR: unknown option '$1'" >&2; echo "Try --help." >&2; exit 2 ;;
    *)  echo "ERROR: unexpected argument '$1' (this script uses named --switches; did you mean --name?)" >&2; exit 2 ;;
  esac
done

if [[ -z "$LONG_NAME" ]]; then
  echo "ERROR: --name is required." >&2
  echo "Try: $0 --name \"<long name>\" [--short XXXX] [--mute] [--port /dev/...]" >&2
  exit 2
fi

# Derive a short name if none given (first 4 alphanumerics, uppercased).
if [[ -z "$SHORT_NAME" ]]; then
  SHORT_NAME="$(printf '%s' "$LONG_NAME" | tr -cd '[:alnum:]' | cut -c1-4 | tr '[:lower:]' '[:upper:]')"
fi

# ---- CLI -------------------------------------------------------------------
MT="/Library/Frameworks/Python.framework/Versions/3.11/bin/meshtastic"
if [[ ! -x "$MT" ]]; then
  MT="$(command -v meshtastic || true)"
fi
if [[ -z "$MT" ]]; then
  echo "ERROR: meshtastic CLI not found." >&2
  exit 1
fi

# Normalize a key to the 0x<hex> form the CLI expects. Accepts 0x-hex (passed
# through) or base64 (decoded -> hex). Validates a 16- or 32-byte result.
normalize_key() { # normalize_key <key> <label>
  local key="$1" label="$2" hex
  if [[ "$key" =~ ^0[xX][0-9a-fA-F]+$ ]]; then
    hex="${key:2}"
  else
    # treat as base64 -> hex
    hex="$(python3 - "$key" <<'PY' 2>/dev/null || true
import base64, sys
try:
    print(base64.b64decode(sys.argv[1], validate=True).hex())
except Exception:
    sys.exit(1)
PY
)"
    if [[ -z "$hex" ]]; then
      echo "ERROR: --$label key is neither valid 0x-hex nor base64: '$key'" >&2
      exit 2
    fi
  fi
  local bytes=$(( ${#hex} / 2 ))
  if [[ $(( ${#hex} % 2 )) -ne 0 || ( "$bytes" -ne 16 && "$bytes" -ne 32 ) ]]; then
    echo "ERROR: --$label key must decode to 16 or 32 bytes (got $bytes): '$key'" >&2
    exit 2
  fi
  printf '0x%s' "$hex"
}

# Resolve each key: CLI override wins; else the default from fam-keys.env; else
# it is an error (no secret is hard-coded in this script).
resolve_key() { # resolve_key <cli-value> <file-default> <label> -> prints "0xhex|source"
  local cli="$1" def="$2" label="$3"
  if [[ -n "$cli" ]]; then
    printf '%s|override' "$(normalize_key "$cli" "$label")"
  elif [[ -n "$def" ]]; then
    printf '%s|fam-keys.env' "$(normalize_key "$def" "$label")"
  else
    echo "ERROR: no --$label given and no default in fam-keys.env." >&2
    echo "       Provide --$label <base64-or-0xhex>, or create fam-keys.env (see fam-keys.env.example)." >&2
    exit 2
  fi
}
IFS='|' read -r FAM_PSK FAM_SRC <<<"$(resolve_key "$FAM_PSK_IN" "$FAM_PSK_DEFAULT" fam-key)"
IFS='|' read -r OPS_PSK OPS_SRC <<<"$(resolve_key "$OPS_PSK_IN" "$OPS_PSK_DEFAULT" ops-key)"

# Optional port (string form for bash 3.2 + set -u safety).
PORT_ARG=""
if [[ -n "$PORT" ]]; then PORT_ARG="--port $PORT"; fi

echo ">>> Using meshtastic CLI: $MT (version $("$MT" --version 2>/dev/null || echo '?'))"
[[ -n "$PORT" ]] && echo ">>> Targeting port: $PORT"
echo ">>> Node: long='$LONG_NAME'  short='$SHORT_NAME'  role=$ROLE"
echo ">>> Fam key: $FAM_SRC   EDC-MeshOps key: $OPS_SRC"

run() { # run <human description> <meshtastic args...>
  local desc="$1"; shift
  echo ">>> $desc"
  # shellcheck disable=SC2086  # PORT_ARG must word-split into 0 or 2 args.
  "$MT" $PORT_ARG "$@"
}

# Stage 1 — role + radio + position-off (one batched write; reboots).
run "Stage 1/4: role=$ROLE, radio (US/SHORT_TURBO/slot 30), position OFF" \
  --set device.role "$ROLE" \
  --set lora.region US \
  --set lora.modem_preset SHORT_TURBO \
  --set lora.channel_num 30 \
  --set position.gps_mode DISABLED \
  --set position.position_broadcast_smart_enabled false \
  --set position.position_broadcast_secs 0
echo ">>> waiting 30s for reboot..."; sleep 30

# Stage 2 — owner identity (the per-node unique attribute).
run "Stage 2/4: owner name" \
  --set-owner "$LONG_NAME" --set-owner-short "$SHORT_NAME"
echo ">>> waiting 12s..."; sleep 12

# Stage 3 — primary channel 0 -> "Fam" with the shared fam key.
# position_precision 0 = do not include position on this channel (we keep GPS off
# too, but this guards against any leftover precision from a prior setup).
run "Stage 3/4: channel 0 = 'Fam' (shared fam key)" \
  --ch-index 0 --ch-set name Fam --ch-set psk "$FAM_PSK" --ch-set module_settings.position_precision 0
echo ">>> waiting 12s..."; sleep 12

# Stage 4 — secondary channel 1 -> "EDC-MeshOps" with the ops key.
# NOTE: `--ch-add` enforces a stricter name-length limit than `--ch-set` and
# rejects the 11-char "EDC-MeshOps" ("Channel name must be shorter"). So we add
# with a short placeholder, then rename + set the key via --ch-set (which DOES
# accept 11 chars). `--ch-add` is skipped if channel 1 already exists.
if "$MT" $PORT_ARG --info 2>/dev/null | grep -qE 'Index 1:'; then   # shellcheck disable=SC2086
  echo ">>> Stage 4/4a: channel 1 already exists — skipping --ch-add"
else
  run "Stage 4/4a: add channel 1 (placeholder name)" --ch-add EDCOps
  echo ">>> waiting 12s..."; sleep 12
fi
run "Stage 4/4b: set channel 1 name='EDC-MeshOps' + ops key" \
  --ch-index 1 --ch-set name "EDC-MeshOps" --ch-set psk "$OPS_PSK" --ch-set module_settings.position_precision 0
echo ">>> waiting 12s..."; sleep 12

# ---- Verify ----------------------------------------------------------------
echo ">>> Verifying fam-node config:"
FAIL=0
PREFS="$(mktemp -t setup-fam)"; trap 'rm -f "$PREFS"' EXIT
# shellcheck disable=SC2086
"$MT" $PORT_ARG --get device.role --get lora.region --get lora.modem_preset \
  --get lora.channel_num --get position.gps_mode >"$PREFS" 2>&1 || true

check() { # check <pref> <expected-int> <label>
  local got
  got="$(awk -F': ' "/^$1:/{print \$2; exit}" "$PREFS" | tr -d '[:space:]')"
  if [[ "$got" == "$2" ]]; then printf "    OK   %-26s = %s (%s)\n" "$1" "$got" "$3"
  else printf "    FAIL %-26s = %s (expected %s = %s)\n" "$1" "${got:-<none>}" "$2" "$3"; FAIL=1; fi
}
check device.role        "$ROLE_INT" "$ROLE"
check lora.region        1 "US"
check lora.modem_preset  8 "SHORT_TURBO"
check lora.channel_num   30 "slot 30"
check position.gps_mode  0 "DISABLED (position off)"

# Channel names/keys: confirm both channels exist with expected names.
# shellcheck disable=SC2086
CH_INFO="$("$MT" $PORT_ARG --info 2>/dev/null | grep -E 'Index [01]:' || true)"
echo ">>> Channels:"
echo "$CH_INFO" | sed 's/^/    /'
echo "$CH_INFO" | grep -q '"name": "Fam"'         && printf "    OK   channel 0 name = Fam\n"         || { printf "    FAIL channel 0 name != Fam\n"; FAIL=1; }
echo "$CH_INFO" | grep -q '"name": "EDC-MeshOps"' && printf "    OK   channel 1 name = EDC-MeshOps\n" || { printf "    FAIL channel 1 name != EDC-MeshOps\n"; FAIL=1; }

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo ">>> SUCCESS: fam node '$LONG_NAME' ($SHORT_NAME) provisioned."
else
  echo ">>> WARNING: some settings did not verify (see FAIL lines above)." >&2
  exit 1
fi

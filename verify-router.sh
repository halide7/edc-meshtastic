#!/usr/bin/env bash
#
# verify-router.sh — read-only spot check of an EDC router's config.
#
# Reads (never writes) the node's config and confirms it matches the EDC
# router profile: ROUTER role, rebroadcast ALL, US / SHORT_TURBO / slot 30,
# hop limit 3. No reboot, safe to run in the field on a live node.
#
# Usage:
#   ./verify-router.sh                       # auto-detect the single connected node
#   ./verify-router.sh /dev/cu.usbmodemXXXX  # target a specific port
#
# Exit code 0 = all settings match; 1 = at least one mismatch or read error.
set -euo pipefail

# Use the 2.7.x CLI — the bare `meshtastic` on PATH is the older 2.6.4.
MT="/Library/Frameworks/Python.framework/Versions/3.11/bin/meshtastic"
if [[ ! -x "$MT" ]]; then
  MT="$(command -v meshtastic || true)"
fi
if [[ -z "$MT" ]]; then
  echo "ERROR: meshtastic CLI not found." >&2
  exit 1
fi

# Optional port argument (string form for bash 3.2 + set -u safety).
PORT_ARG=""
if [[ $# -ge 1 ]]; then
  PORT_ARG="--port $1"
  echo ">>> Targeting port: $1"
fi

echo ">>> Using meshtastic CLI: $MT (version $("$MT" --version 2>/dev/null || echo '?'))"

# One read of full preferences, cached to a temp file, so we hit the radio once
# instead of per-setting. --get with no key dumps all prefs.
PREFS="$(mktemp -t verify-router)"
trap 'rm -f "$PREFS"' EXIT
# shellcheck disable=SC2086  # PORT_ARG must word-split into 0 or 2 args.
if ! "$MT" $PORT_ARG --get device.role --get device.rebroadcast_mode \
       --get lora.region --get lora.modem_preset \
       --get lora.channel_num --get lora.hop_limit >"$PREFS" 2>&1; then
  echo "ERROR: could not read config from node. Output:" >&2
  cat "$PREFS" >&2
  exit 1
fi

echo ">>> Verifying against EDC router profile:"
FAIL=0
check() { # check <pref> <expected-int> <label>
  local got
  got="$(awk -F': ' "/^$1:/{print \$2; exit}" "$PREFS" | tr -d '[:space:]')"
  if [[ "$got" == "$2" ]]; then
    printf "    OK   %-22s = %s (%s)\n" "$1" "$got" "$3"
  else
    printf "    FAIL %-22s = %s (expected %s = %s)\n" "$1" "${got:-<none>}" "$2" "$3"
    FAIL=1
  fi
}

# Expected values are the enum integers the firmware stores/returns.
check device.role             2  "ROUTER"
check device.rebroadcast_mode 0  "ALL"
check lora.region             1  "US"
check lora.modem_preset       8  "SHORT_TURBO"
check lora.channel_num        30 "slot 30 -> 916.75 MHz"
check lora.hop_limit          3  "hops"

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo ">>> PASS: node matches the EDC router profile."
else
  echo ">>> FAIL: node does NOT match the EDC router profile (see FAIL lines)." >&2
  echo "    Run ./setup-router.sh to (re)apply the config." >&2
  exit 1
fi

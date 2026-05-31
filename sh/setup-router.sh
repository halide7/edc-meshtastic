#!/usr/bin/env bash
#
# setup-router.sh — configure a Meshtastic node as an EDC router.
#
# Applies: ROUTER role, rebroadcast ALL, US / SHORT_TURBO / slot 30, hop limit 3.
# Leaves channels at default (a router rebroadcasts at the LoRa layer and does
# not need channel keys). Every peer node must match US / SHORT_TURBO / slot 30
# or it won't hear this router.
#
# Usage:
#   ./setup-router.sh                       # auto-detect the single connected node
#   ./setup-router.sh /dev/cu.usbmodemXXXX  # target a specific port (if several plugged in)
#
set -euo pipefail

# Use the 2.7.x CLI — the bare `meshtastic` on PATH is the older 2.6.4, which
# mishandles some of these settings. Fall back to PATH if the framework build moved.
MT="/Library/Frameworks/Python.framework/Versions/3.11/bin/meshtastic"
if [[ ! -x "$MT" ]]; then
  MT="$(command -v meshtastic || true)"
fi
if [[ -z "$MT" ]]; then
  echo "ERROR: meshtastic CLI not found." >&2
  exit 1
fi

# Optional port argument. (Assigned as a string, not an array, so it expands
# safely under `set -u` on macOS's bash 3.2.)
PORT_ARG=""
if [[ $# -ge 1 ]]; then
  PORT_ARG="--port $1"
  echo ">>> Targeting port: $1"
fi

CLI_VER="$("$MT" --version 2>/dev/null || echo '?')"
echo ">>> Using meshtastic CLI: $MT (version $CLI_VER)"

echo ">>> Applying router config (single batched write + one reboot)..."
# shellcheck disable=SC2086  # PORT_ARG must word-split into 0 or 2 args.
"$MT" $PORT_ARG \
  --set device.role ROUTER \
  --set device.rebroadcast_mode ALL \
  --set lora.region US \
  --set lora.modem_preset SHORT_TURBO \
  --set lora.channel_num 30 \
  --set lora.hop_limit 3

echo ">>> Config sent. Waiting 30s for the node to reboot..."
sleep 30

echo ">>> Verifying persisted values:"
FAIL=0
check() { # check <pref> <expected> <label>
  local got
  # shellcheck disable=SC2086  # PORT_ARG must word-split into 0 or 2 args.
  got="$("$MT" $PORT_ARG --get "$1" 2>/dev/null | awk -F': ' "/$1/{print \$2}")"
  if [[ "$got" == "$2" ]]; then
    printf "    OK   %-22s = %s (%s)\n" "$1" "$got" "$3"
  else
    printf "    FAIL %-22s = %s (expected %s = %s)\n" "$1" "${got:-<none>}" "$2" "$3"
    FAIL=1
  fi
}

# Values are the enum integers the firmware stores.
check device.role          2  "ROUTER"
check device.rebroadcast_mode 0 "ALL"
check lora.region          1  "US"
check lora.modem_preset    8  "SHORT_TURBO"
check lora.channel_num     30 "slot 30 -> 916.75 MHz"
check lora.hop_limit       3  "hops"

echo
if [[ "$FAIL" -eq 0 ]]; then
  echo ">>> SUCCESS: node is configured as an EDC router."
else
  echo ">>> WARNING: one or more settings did not persist (see FAIL lines above)." >&2
  echo "    A common cause is reading during reboot — re-run to re-verify, or" >&2
  echo "    check that the node isn't running firmware that rejects a value." >&2
  exit 1
fi

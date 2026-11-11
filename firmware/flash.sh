#!/usr/bin/env bash
# UPDI-Flash für WLS-14 (ATtiny1616). Nutzung: ./flash.sh u1|u2
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv-updi"
PG="$VENV/bin/pymcuprog"
CHIP="${1:-}"

usage() {
  echo "Nutzung: UPDI_PORT=/dev/ttyACM0 $0 u1|u2" >&2
  exit 1
}

[[ "$CHIP" == u1 || "$CHIP" == u2 ]] || usage

ensure_pymcuprog() {
  if [[ ! -x "$PG" ]]; then
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q pymcuprog
  fi
}

pick_port() {
  if [[ -n "${UPDI_PORT:-}" ]]; then
    echo "$UPDI_PORT"
    return
  fi
  local c
  for c in /dev/serial/by-id/* /dev/ttyACM* /dev/ttyUSB*; do
    [[ -e "$c" ]] || continue
    echo "$c"
    return
  done
  echo "UPDI_PORT fehlt (z. B. /dev/ttyACM0)" >&2
  exit 1
}

DEV=attiny1616
PORT="$(pick_port)"
HEX="$ROOT/${CHIP^^}.hex"
COMMUNITY="$ROOT/community/${CHIP^^}.hex"

if [[ ! -f "$HEX" ]]; then
  if [[ -f "$COMMUNITY" ]]; then
    echo "Hinweis: $HEX fehlt — Community-Image $COMMUNITY (I2C ≠ Seeed-Demo)." >&2
    HEX="$COMMUNITY"
  else
    echo "Kein HEX: weder $HEX noch $COMMUNITY. Siehe firmware/README.md" >&2
    exit 1
  fi
fi

ensure_pymcuprog
echo "Chip ${CHIP^^} ← $(basename "$HEX") über $PORT"
"$PG" write -f "$HEX" -d "$DEV" -t uart -u "$PORT" --erase --verify

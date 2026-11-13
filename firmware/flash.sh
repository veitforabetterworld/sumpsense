#!/usr/bin/env bash
# UPDI-Flash für SumpSense-24i (ATtiny1616). Ein Image für U1 und U2,
# die Adresse wählt die Firmware über PA3 (auf der Platine fest verdrahtet).
# Nutzung: UPDI_PORT=/dev/ttyACM0 ./flash.sh u1|u2
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv-updi"
PG="$VENV/bin/pymcuprog"
CHIP="${1:-}"
HEX="$ROOT/sumpsense-24i/sumpsense-24i.hex"

usage() {
  echo "Nutzung: UPDI_PORT=/dev/ttyACM0 $0 u1|u2" >&2
  exit 1
}

[[ "$CHIP" == u1 || "$CHIP" == u2 ]] || usage
[[ -f "$HEX" ]] || { echo "Fehlt: $HEX (siehe firmware/README.md, Bauen)" >&2; exit 1; }

if [[ ! -x "$PG" ]]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q pymcuprog
fi

PORT="${UPDI_PORT:-}"
if [[ -z "$PORT" ]]; then
  for c in /dev/serial/by-id/* /dev/ttyACM* /dev/ttyUSB*; do
    [[ -e "$c" ]] && PORT="$c" && break
  done
fi
[[ -n "$PORT" ]] || { echo "UPDI_PORT setzen (z. B. /dev/ttyACM0)" >&2; exit 1; }

echo "Chip ${CHIP^^} <- $(basename "$HEX") über $PORT"
"$PG" write -f "$HEX" -d attiny1616 -t uart -u "$PORT" --erase --verify

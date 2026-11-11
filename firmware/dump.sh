#!/usr/bin/env bash
# Flash von Original-ATtiny1616 auslesen. Nutzung: ./dump.sh u1|u2
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
[[ -n "$PORT" ]] || { echo "UPDI_PORT setzen" >&2; exit 1; }

OUT="$ROOT/${CHIP^^}.hex"
echo "Lese ${CHIP^^} → $OUT"
"$PG" read -m flash -f "$OUT" -d attiny1616 -t uart -u "$PORT"
echo "Fertig: $OUT"

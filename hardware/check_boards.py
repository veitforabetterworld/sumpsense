#!/usr/bin/env python3
"""Boardqualität prüfen: DRC (inkl. Schaltplan-Parität) und ERC, Fehler und Warnungen.

Nutzung:
  python hardware/check_boards.py                 alle Platinen
  python hardware/check_boards.py sumpsense-16z   nur diese

Erlaubte Ausnahmen stehen in den Projektdateien selbst (<board>.kicad_dru,
ERC-Pin-Matrix in <board>.kicad_pro), damit KiCad-GUI und Hook dasselbe melden.
Läuft als Git-pre-commit-Hook (.githooks/pre-commit).
"""
import glob
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kicad_tools import kicad_commands  # noqa: E402


def items(v):
    return " ; ".join(i["description"] for i in v.get("items", []))


def check(board_dir, cli, tmp):
    name = os.path.basename(board_dir)
    pcb = os.path.join(board_dir, name + ".kicad_pcb")
    sch = os.path.join(board_dir, name + ".kicad_sch")
    found = []

    rep = os.path.join(tmp, name + "-drc.json")
    subprocess.run([*cli, "pcb", "drc", "--schematic-parity", "--severity-all", "--format", "json",
                    "-o", rep, pcb], check=True, capture_output=True)
    d = json.load(open(rep, encoding="utf-8"))
    for key in ("violations", "unconnected_items", "schematic_parity"):
        for v in d.get(key, []):
            found.append(f"DRC {v['severity']}: {v['description']} | {items(v)}")

    if os.path.isfile(sch):
        rep = os.path.join(tmp, name + "-erc.json")
        subprocess.run([*cli, "sch", "erc", "--severity-all", "--format", "json", "-o", rep, sch],
                       check=True, capture_output=True)
        e = json.load(open(rep, encoding="utf-8"))
        for s in e.get("sheets", []):
            for v in s.get("violations", []):
                found.append(f"ERC {v['severity']}: {v['description']} | {items(v)}")

    print(f"{name}: {'OK' if not found else f'{len(found)} Befund(e)'}")
    for f in found:
        print("  " + f)
    return not found


def main():
    boards = sorted(os.path.dirname(p) for p in glob.glob(os.path.join(HERE, "*", "*.kicad_pcb"))
                    if os.path.basename(p)[:-10] == os.path.basename(os.path.dirname(p)))
    if len(sys.argv) > 1:
        boards = [b for b in boards if os.path.basename(b) in sys.argv[1:]]
    cli, _ = kicad_commands()
    with tempfile.TemporaryDirectory() as tmp:
        ok = all([check(b, cli, tmp) for b in boards])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

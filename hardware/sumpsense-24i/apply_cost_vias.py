#!/usr/bin/env python3
"""JLC: Bohrung 0,2 → 0,3 mm bei 0,45-mm-Pad (Standardloch, kein Small-Hole-Aufpreis)."""

import os

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "sumpsense-24i.kicad_pcb")

mm = pcbnew.ToMM
nm = pcbnew.FromMM


def count_vias(board):
    return sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_VIA")


def resize_vias(board):
    n = 0
    for t in board.GetTracks():
        if t.GetClass() != "PCB_VIA":
            continue
        if abs(mm(t.GetDrill()) - 0.2) < 0.02:
            t.SetDrill(nm(0.3))
            # Pad unverändert lassen — nur Bohrung weg von 0,2-mm-Aufpreis.
            n += 1
    return n


def main():
    board = pcbnew.LoadBoard(PCB)
    v0 = count_vias(board)
    n = resize_vias(board)
    pcbnew.SaveBoard(PCB, board)
    print(f"Resized {n} via drills to 0.3 mm (pad stays 0.45 mm), total vias {v0}")


if __name__ == "__main__":
    main()

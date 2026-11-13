#!/usr/bin/env python3
"""Kost-Revision: Vias, GND-Stitch, Elektroden flip (KiCad pcbnew). SW1/D1 per Hand in PCB-Datei."""

import os

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "sumpsense-16z.kicad_pcb")

mm = pcbnew.ToMM
nm = pcbnew.FromMM

GND_ROW_DROP = {
    (75.8, 20.05),
    (79.7, 20.05),
    (87.3, 20.05),
    (91.3, 20.05),
    (95.3, 20.05),
    (97.3, 20.05),
    (105.45, 19.6),
    (106.65, 19.6),
}


def count_vias(board):
    return sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_VIA")


def resize_vias(board):
    n = 0
    for t in board.GetTracks():
        if t.GetClass() != "PCB_VIA":
            continue
        if abs(mm(t.GetDrill()) - 0.2) < 0.02:
            t.SetDrill(nm(0.3))
            t.SetWidth(nm(0.6))
            n += 1
    return n


def drop_gnd_vias(board):
    remove = []
    for t in board.GetTracks():
        if t.GetClass() != "PCB_VIA" or t.GetNetname() != "GND":
            continue
        xy = (round(mm(t.GetStart().x), 1), round(mm(t.GetStart().y), 2))
        if xy in GND_ROW_DROP:
            remove.append(t)
    for t in remove:
        board.Remove(t)
    return len(remove)


def move_silk_to_bottom(fp):
    for g in fp.GraphicalItems():
        if g.GetClass() != "PCB_TEXT":
            continue
        if g.GetLayer() == pcbnew.F_SilkS:
            g.SetLayer(pcbnew.B_SilkS)
            g.SetMirrored(True)


def flip_electrodes(board):
    removed = 0
    flipped = 0
    for f in board.GetFootprints():
        ref = f.GetReference()
        if not (ref.startswith("E") and ref[1:].isdigit()):
            continue
        val = f.GetValue()
        net = val if val.startswith("/") else f"/{val}"
        ex = mm(f.GetPosition().x)
        if not f.IsFlipped():
            f.Flip(f.GetPosition(), False)
        move_silk_to_bottom(f)
        flipped += 1
        for t in list(board.GetTracks()):
            if t.GetClass() != "PCB_VIA" or t.GetNetname() != net:
                continue
            vx = mm(t.GetStart().x)
            if abs(vx - ex) < 0.15 and vx > 118:
                board.Remove(t)
                removed += 1
    return flipped, removed


def main():
    board = pcbnew.LoadBoard(PCB)
    v0 = count_vias(board)
    nv = resize_vias(board)
    ng = drop_gnd_vias(board)
    ne, ns = flip_electrodes(board)
    pcbnew.SaveBoard(PCB, board)
    v1 = count_vias(board)
    print(f"Resized {nv} vias (0.2→0.3 mm)")
    print(f"Removed {ng} GND stitch vias")
    print(f"Electrodes B.Cu: {ne}, removed {ns} sense vias")
    print(f"Via count {v0} → {v1}")


if __name__ == "__main__":
    main()

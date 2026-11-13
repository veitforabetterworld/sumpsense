#!/usr/bin/env python3
"""C1/R20 aus der Antennenzuleitung. Zwei Aufrufe: --move, dann --wire."""

import argparse

import pcbnew

HERE = __import__("os").path.dirname(__import__("os").path.abspath(__file__))
PCB = f"{HERE}/sumpsense-16z.kicad_pcb"
nm = pcbnew.FromMM
mm = pcbnew.ToMM

C1 = (97.9, 20.35)
R20 = (102.95, 19.2)


def seg(board, pts, w, net):
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(nm(a[0]), nm(a[1])))
        t.SetEnd(pcbnew.VECTOR2I(nm(b[0]), nm(b[1])))
        t.SetWidth(nm(w))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNetCode(net.GetNetCode())
        board.Add(t)


def near(x, y, px, py, tol=0.2):
    return abs(x - px) < tol and abs(y - py) < tol


def move():
    board = pcbnew.LoadBoard(PCB)
    for ref, pos in (("C1", C1), ("R20", R20)):
        fp = next(f for f in board.GetFootprints() if f.GetReference() == ref)
        fp.SetPosition(pcbnew.VECTOR2I(nm(pos[0]), nm(pos[1])))
        fp.SetOrientation(pcbnew.EDA_ANGLE(0, pcbnew.DEGREES_T))
    pcbnew.SaveBoard(PCB, board)
    print("moved C1", C1, "R20", R20)


def wire():
    board = pcbnew.LoadBoard(PCB)
    # alte XTAL-Leitungen und der GND-Stummel am alten C1-Pad
    for t in list(board.GetTracks()):
        if t.GetClass() != "PCB_TRACK":
            continue
        nn = t.GetNetname()
        x1, y1 = mm(t.GetStart().x), mm(t.GetStart().y)
        x2, y2 = mm(t.GetEnd().x), mm(t.GetEnd().y)
        if nn in ("/XTAL_P", "/XTAL_PIN"):
            board.Remove(t)
            continue
        if nn == "GND" and (
            near(x1, y1, 99.32, 20.85) or near(x2, y2, 99.32, 20.85)
        ):
            board.Remove(t)
    n_p = board.FindNet("/XTAL_P")
    n_pin = board.FindNet("/XTAL_PIN")
    gnd = board.FindNet("GND")
    # C1 pad2 = XTAL, pad1 = GND (0402, rot 0, ±0,48)
    c_g, c_s = (C1[0] - 0.48, C1[1]), (C1[0] + 0.48, C1[1])
    r_a, r_b = (R20[0] - 0.51, R20[1]), (R20[0] + 0.51, R20[1])
    seg(board, [(101.6, 20.0), (101.6, 20.7), c_s, (c_s[0], C1[1])], 0.2, n_p)
    seg(board, [(102.2, 19.3), r_a], 0.2, n_p)
    seg(board, [r_b, (104.1, 19.2)], 0.2, n_pin)
    seg(board, [c_g, (c_g[0], 20.15), (98.8, 20.15)], 0.25, gnd)
    pcbnew.SaveBoard(PCB, board)
    print("rewired XTAL + C1 GND")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--move", action="store_true")
    ap.add_argument("--wire", action="store_true")
    args = ap.parse_args()
    if args.move:
        move()
    if args.wire:
        wire()

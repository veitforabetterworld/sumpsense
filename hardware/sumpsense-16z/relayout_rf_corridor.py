#!/usr/bin/env python3
"""Mehr Freiraum um MS: Quarz-Passives, C6, D1, Vias."""

import argparse

import pcbnew

HERE = __import__("os").path.dirname(__import__("os").path.abspath(__file__))
PCB = f"{HERE}/sumpsense-16z.kicad_pcb"
nm = pcbnew.FromMM
mm = pcbnew.ToMM

C1_POS = (101.15, 19.05)
C1_ROT = 90
R20_POS = (102.95, 19.05)
R20_ROT = 0
D1_POS = (90.1, 24.15)
C6_POS = (109.35, 22.0)
C6_ROT = 90

VIA_MOVE = {
    (101.0, 19.15): (101.55, 18.45),
    (106.65, 18.4): (109.85, 18.35),
    (105.45, 18.4): (109.5, 17.75),
    (103.3, 19.8): (108.6, 19.55),
}

# Nach --move (0402 rot90 / rot0) berechnete Pad-Mitten
Y1_PAD1 = (101.6, 19.3)
C1_PAD2 = (101.15, 18.57)
C1_PAD1 = (101.15, 19.53)
R20_PAD1 = (102.44, 19.05)
R20_PAD2 = (103.46, 19.05)
U1_XTAL_PIN = (104.1, 19.2)


def seg(board, pts, w, net, layer=pcbnew.F_Cu):
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(nm(a[0]), nm(a[1])))
        t.SetEnd(pcbnew.VECTOR2I(nm(b[0]), nm(b[1])))
        t.SetWidth(nm(w))
        t.SetLayer(layer)
        t.SetNetCode(net.GetNetCode())
        board.Add(t)


def move_fp(fp, pos, rot):
    fp.SetPosition(pcbnew.VECTOR2I(nm(pos[0]), nm(pos[1])))
    fp.SetOrientation(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))


def move_parts(board):
    move_fp(next(f for f in board.GetFootprints() if f.GetReference() == "D1"), D1_POS, 0)
    move_fp(next(f for f in board.GetFootprints() if f.GetReference() == "C6"), C6_POS, C6_ROT)
    move_fp(next(f for f in board.GetFootprints() if f.GetReference() == "C1"), C1_POS, C1_ROT)
    move_fp(next(f for f in board.GetFootprints() if f.GetReference() == "R20"), R20_POS, R20_ROT)
    for t in list(board.GetTracks()):
        if t.GetClass() != "PCB_VIA":
            continue
        p = t.GetPosition()
        for (ox, oy), (nx, ny) in VIA_MOVE.items():
            if abs(mm(p.x) - ox) < 0.06 and abs(mm(p.y) - oy) < 0.06:
                t.SetPosition(pcbnew.VECTOR2I(nm(nx), nm(ny)))
                break


def clear_xtal_tracks(board):
    n = 0
    for t in list(board.GetTracks()):
        if t.GetClass() != "PCB_TRACK":
            continue
        if t.GetNetname() not in ("/XTAL_P", "/XTAL_PIN"):
            continue
        y1, y2 = mm(t.GetStart().y), mm(t.GetEnd().y)
        if min(y1, y2) >= 19.45:
            board.Remove(t)
            n += 1
    return n


def drop_xtal_vias_at(board, x, y):
    for t in list(board.GetTracks()):
        if t.GetClass() != "PCB_VIA" or t.GetNetname() != "/XTAL_P":
            continue
        p = t.GetPosition()
        if abs(mm(p.x) - x) < 0.15 and abs(mm(p.y) - y) < 0.15:
            board.Remove(t)


def wire_c6_d1(board):
    n3, gnd = board.FindNet("+3V3"), board.FindNet("GND")
    n5, drain = board.FindNet("+5V"), board.FindNet("/DRAIN")
    for t in list(board.GetTracks()):
        if t.GetClass() != "PCB_TRACK":
            continue
        nn, sx, sy = t.GetNetname(), mm(t.GetStart().x), mm(t.GetStart().y)
        ex, ey = mm(t.GetEnd().x), mm(t.GetEnd().y)
        if nn == "+3V3" and abs(sx - 104.65) < 0.8 and max(sy, ey) > 20.5:
            board.Remove(t)
        if nn == "+3V3" and 103.5 < sx < 104.5 and abs(sy - 19.8) < 0.3:
            board.Remove(t)
        if nn == "GND" and abs(sx - 104.65) < 0.8 and max(sy, ey) > 21.5:
            board.Remove(t)
    for t in list(board.GetTracks()):
        if t.GetClass() != "PCB_TRACK" or t.GetNetname() != "+3V3":
            continue
        sy, ey = mm(t.GetStart().y), mm(t.GetEnd().y)
        if abs(sy - 21.52) < 0.15 or abs(ey - 21.52) < 0.15:
            board.Remove(t)
    seg(board, [(104.1, 19.6), (104.1, 20.0), (104.65, 20.95), (105.05, 20.95)], 0.25, n3)
    seg(board, [(105.05, 20.95), (108.0, 20.85), (109.35, 22.48)], 0.25, n3)
    seg(board, [(108.0, 20.85), (108.6, 19.55)], 0.25, n3)
    seg(board, [(104.1, 18.4), (104.1, 19.6)], 0.2, n3)
    seg(board, [(109.35, 21.52), (109.85, 18.35)], 0.2, gnd)
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(nm(108.0), nm(21.05)))
    v.SetWidth(nm(0.6))
    v.SetDrill(nm(0.3))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNetCode(n3.GetNetCode())
    board.Add(v)
    seg(board, [(108.0, 20.85), (108.0, 21.05)], 0.25, n3)
    seg(board, [(88.45, 24.15), (88.1, 24.15)], 0.25, n5)
    seg(board, [(91.75, 24.15), (92.5, 24.15)], 0.25, drain)


def wire_xtal(board):
    n_p, n_pin = board.FindNet("/XTAL_P"), board.FindNet("/XTAL_PIN")
    gnd = board.FindNet("GND")
    clear_xtal_tracks(board)
    seg(board, [Y1_PAD1, C1_PAD2], 0.2, n_p)
    seg(board, [C1_PAD1, (99.32, 19.53)], 0.2, gnd)
    seg(board, [C1_PAD2, R20_PAD1], 0.2, n_p)
    seg(board, [R20_PAD2, U1_XTAL_PIN], 0.2, n_pin)
    seg(board, [(101.55, 18.45), C1_PAD2], 0.2, n_p)
    drop_xtal_vias_at(board, 110.2, 20.55)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--move", action="store_true")
    ap.add_argument("--wire", action="store_true")
    ap.add_argument("--all", action="store_true", help="--move, dann --wire (Prozesstrennung)")
    args = ap.parse_args()
    if args.all:
        main_move_wire_all()
        return
    if not (args.move or args.wire):
        ap.print_help()
        return
    if args.move:
        board = pcbnew.LoadBoard(PCB)
        move_parts(board)
        pcbnew.SaveBoard(PCB, board)
        print("moved C1/R20 ↑, D1↓, C6→Rand, vias→Rand")
    if args.wire:
        board = pcbnew.LoadBoard(PCB)
        wire_c6_d1(board)
        pcbnew.SaveBoard(PCB, board)
        board = pcbnew.LoadBoard(PCB)
        wire_xtal(board)
        pcbnew.SaveBoard(PCB, board)
        print("xtal + C6/D1 rewired")


def main_move_wire_all():
    import subprocess
    import sys

    py = sys.executable
    here = f"{HERE}/relayout_rf_corridor.py"
    for a in ("--move", "--wire"):
        subprocess.check_call([py, here, a])


if __name__ == "__main__":
    main()

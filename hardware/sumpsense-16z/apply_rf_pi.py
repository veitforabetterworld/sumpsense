#!/usr/bin/env python3
"""π am Feed, 50-Ω-Microstrip (≈0,55 mm @ 1,6 mm FR4), Sim-Werte.

  AppRun python3.11 apply_rf_pi.py --clear
  AppRun python3.11 apply_rf_pi.py --place
"""

import argparse
import sys

import pcbnew

HERE = __import__("os").path.dirname(__import__("os").path.abspath(__file__))
PCB = f"{HERE}/sumpsense-16z.kicad_pcb"
nm = pcbnew.FromMM

# Ursprüngliche Zuleitung (Commit): 1 mm bis R21, dann 0,2 mm in Pin 32.
W_BUS = 1.0
W_FEED = 0.46
C7_PF = "1pF"
C8_PF = "1pF"


def clear_rf():
    board = pcbnew.LoadBoard(PCB)
    n = 0
    for t in list(board.GetTracks()):
        nn = t.GetNetname().lstrip("/")
        if nn not in ("RF", "ANT_PIN"):
            continue
        if t.GetClass() in ("PCB_TRACK", "PCB_VIA"):
            board.Remove(t)
            n += 1
    pcbnew.SaveBoard(PCB, board)
    print("cleared", n)


def seg(board, pts, w, net, layer=pcbnew.F_Cu):
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(nm(a[0]), nm(a[1])))
        t.SetEnd(pcbnew.VECTOR2I(nm(b[0]), nm(b[1])))
        t.SetWidth(nm(w))
        t.SetLayer(layer)
        t.SetNetCode(net.GetNetCode())
        board.Add(t)


def drop_gnd_stitch(board, x, y):
    for v in list(board.GetTracks()):
        if v.GetClass() != "PCB_VIA" or v.GetNetname() != "GND":
            continue
        p = v.GetPosition()
        if abs(pcbnew.ToMM(p.x) - x) < 0.05 and abs(pcbnew.ToMM(p.y) - y) < 0.05:
            board.Remove(v)


def stitch_gnd(board, x, y):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(nm(x), nm(y)))
    v.SetWidth(nm(0.6))
    v.SetDrill(nm(0.3))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNetCode(board.FindNet("GND").GetNetCode())
    board.Add(v)


def place_pi(board, ref, pos, rot, val, n_sig, n_gnd, bom=True):
    cap = next(f for f in board.GetFootprints() if f.GetReference() == ref)
    cap.SetValue(val)
    cap.SetPosition(pcbnew.VECTOR2I(nm(pos[0]), nm(pos[1])))
    cap.SetOrientation(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
    cap.SetAttributes(pcbnew.FP_SMD)
    if not bom:
        cap.SetAttributes(
            pcbnew.FP_SMD | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES
        )
    for pad in cap.Pads():
        pad.SetNet(n_gnd if pad.GetNumber() == "1" else n_sig)


def place_rf():
    board = pcbnew.LoadBoard(PCB)
    n_rf, n_ant, n_gnd = board.FindNet("/RF"), board.FindNet("/ANT_PIN"), board.FindNet("GND")

    r21 = next(f for f in board.GetFootprints() if f.GetReference() == "R21")
    # C7 liegt flach auf dem geraden Feed, GND nach oben ans IFA-GND.
    # R21 am Feed, Höfe frei. C8 weiter auf der 1-mm-Bahn, hinter D1.
    r21.SetPosition(pcbnew.VECTOR2I(nm(86.13), nm(21.35)))
    r21.SetOrientation(pcbnew.EDA_ANGLE(0, pcbnew.DEGREES_T))
    for pad in r21.Pads():
        pad.SetNet(n_rf if pad.GetNumber() == "1" else n_ant)

    place_pi(board, "C7", (83.494, 20.28), 0, C7_PF, n_rf, n_gnd, bom=True)
    place_pi(board, "C8", (94.50, 20.87), 270, C8_PF, n_ant, n_gnd, bom=True)

    seg(board, [(83.974, 19.648), (83.974, 20.60)], W_FEED, n_rf)
    seg(board, [(83.974, 20.60), (83.974, 21.05)], W_BUS, n_rf)
    seg(board, [(83.974, 21.05), (84.274, 21.35)], W_BUS, n_rf)
    seg(board, [(84.274, 21.35), (85.00, 21.35)], W_BUS, n_rf)
    seg(board, [(85.00, 21.35), (85.62, 21.35)], 0.5, n_rf)
    seg(board, [(83.014, 20.28), (83.014, 19.55)], 0.40, n_gnd)
    seg(board, [(86.64, 21.35), (87.20, 21.35)], 0.5, n_ant)
    seg(board, [(87.20, 21.35), (97.40, 21.35), (98.00, 21.90), (102.60, 21.90)], W_BUS, n_ant)
    seg(board, [(102.60, 21.90), (103.70, 20.80)], 0.75, n_ant)
    seg(board, [(103.70, 20.80), (104.10, 20.40)], 0.28, n_ant)
    if not any(
        t.GetClass() == "PCB_VIA"
        and t.GetNetname() == "GND"
        and abs(pcbnew.ToMM(t.GetPosition().x) - 85.3) < 0.05
        and abs(pcbnew.ToMM(t.GetPosition().y) - 20.05) < 0.05
        for t in board.GetTracks()
    ):
        stitch_gnd(board, 85.3, 20.05)
    for x, y in (
        (88.3, 20.5),
        (95.0, 20.5),
        (101.0, 20.45),
        (88.5, 20.05),
        (96.8, 20.55),
        (99.4, 20.55),
    ):
        drop_gnd_stitch(board, x, y)

    pcbnew.SaveBoard(PCB, board)
    print("placed original 1 mm bus + π, C8=", C8_PF)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clear", action="store_true")
    ap.add_argument("--place", action="store_true")
    args = ap.parse_args()
    if not (args.clear or args.place):
        ap.print_help()
        sys.exit(1)
    if args.clear:
        clear_rf()
    if args.place:
        place_rf()


if __name__ == "__main__":
    main()

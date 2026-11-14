"""Fertigungsdaten für JLCPCB: Gerber + Bohrdaten (ZIP), BOM und Bestückungsliste (CPL).

  python3 jlcpcb.py sumpsense-16z      # oder sumpsense-16z-v2, sumpsense-24i
  python3 jlcpcb.py                    # beide Platinen

Ausgabe nach <platine>/jlcpcb/. Braucht KiCad (kicad-cli), siehe kicad_tools.py.
"""

import csv
import io
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kicad_tools  # noqa: E402

LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"

# (Wert, Footprint) -> LCSC-Nummer. Nur Teile, deren Nummer sicher ist (JLC-Basisteile);
# leere Einträge im BOM-Werkzeug von JLC zuordnen.
LCSC = {
    ("100k", "R_0402_1005Metric"): "C25741",
    ("10k", "R_0402_1005Metric"): "C25744",
    ("4.7k", "R_0402_1005Metric"): "C25900",
    ("1k", "R_0402_1005Metric"): "C11702",
    ("0R", "R_0402_1005Metric"): "C17168",
    ("100nF", "C_0402_1005Metric"): "C1525",
    ("12pF", "C_0402_1005Metric"): "C1547",
    ("1pF", "C_0402_1005Metric"): "C1550",
    ("4.7uF", "C_0402_1005Metric"): "C23733",
    ("10uF", "C_0805_2012Metric"): "C15850",
    ("10uF", "C_0603_1608Metric"): "C19702",
    ("1uF", "C_0402_1005Metric"): "C52923",
    ("ESP32-H2-MINI-1-H4S", "ESP32-H2-MINI-1"): "C47967030",
    ("AO3400A", "SOT-23"): "C20917",
    ("XC6206P332MR", "SOT-23-3"): "C5446",
    ("ESP32-H2", "QFN-32-1EP_4x4mm_P0.4mm_EP2.65x2.65mm"): "C22470214",
    ("32MHz", "Crystal_SMD_3225-4Pin_3.2x2.5mm"): "C9009",
    ("1M", "R_0402_1005Metric"): "C26083",
    ("B5819W", "D_SOD-123"): "C8598",
    ("ATtiny1616", "VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm"): "C507118",
}
# Zusatzdrehung (CCW, Grad) auf die KiCad-Lage. JLCs SOT-23-3 hat Pin 1
# unten rechts (EasyEDA …-BR), KiCad oben links. Diode, Quarz und QFN
# liegen schon deckungsgleich, Chip-R/C sind drehsymmetrisch.
CPL_ROT = {
    ("AO3400A", "SOT-23"): 180,
    ("XC6206P332MR", "SOT-23-3"): 180,
    ("ATtiny1616", "VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm"): 90,
}
# Kupfer-Footprints ohne Bauteil (Elektroden, Antenne, Pairing-Pads) gehören nicht in BOM/CPL.
NO_PART = ("E", "A1", "JP1")


def parts(pcb):
    """[(ref, value, footprint, x, y, rot, side)] aus der Platine (pcbnew über KiCads Python)."""
    code = (
        "import pcbnew, sys, json\n"
        "b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM; out = []\n"
        "for f in b.GetFootprints():\n"
        "    a = f.GetAttributes()\n"
        "    if a & pcbnew.FP_EXCLUDE_FROM_BOM: continue\n"
        "    p = f.GetPosition()\n"
        "    out.append([f.GetReference(), f.GetValue(), str(f.GetFPID().GetLibItemName()), mm(p.x), mm(p.y),\n"
        "                f.GetOrientationDegrees(), 'bottom' if f.IsFlipped() else 'top'])\n"
        "print(json.dumps(out))\n"
    )
    _, py = kicad_tools.kicad_commands()
    if not py:
        raise SystemExit("KiCad-Python nicht gefunden (KICAD_PYTHON setzen).")
    r = subprocess.run(py + ["-c", code, pcb], capture_output=True, text=True)
    import json
    line = [l for l in r.stdout.splitlines() if l.startswith("[")][-1]
    rows = json.loads(line)
    return [r for r in rows if not (r[0] in NO_PART or (r[0].startswith("E") and r[0][1:].isdigit()))]


def export(board):
    bdir = os.path.join(HERE, board)
    pcb = os.path.join(bdir, board + ".kicad_pcb")
    out = os.path.join(bdir, "jlcpcb")
    tmp = os.path.join(out, "gerber")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    cli, _ = kicad_tools.kicad_commands()
    layers = LAYERS
    # 16z hat kein Silk auf der Unterseite (Skala liegt oben).
    if board == "sumpsense-16z":
        layers = LAYERS.replace("B.Silkscreen,", "")
    subprocess.run(cli + ["pcb", "export", "gerbers", "--layers", layers, "--subtract-soldermask",
                    "--check-zones", "-o", tmp + os.sep, pcb], check=True, capture_output=True)
    subprocess.run(cli + ["pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm",
                    "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2",
                    "-o", tmp + os.sep, pcb], check=True, capture_output=True)
    zpath = os.path.join(out, f"{board}-gerber.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(tmp)):
            z.write(os.path.join(tmp, fn), fn)
    shutil.rmtree(tmp)

    rows = parts(pcb)
    groups = {}
    for ref, val, fp, x, y, rot, side in rows:
        groups.setdefault((val, fp), []).append(ref)
    natural = lambda r: (r.rstrip("0123456789"), int("".join(c for c in r if c.isdigit()) or 0))
    with open(os.path.join(out, f"{board}-bom.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (val, fp), refs in sorted(groups.items(), key=lambda kv: natural(sorted(kv[1], key=natural)[0])):
            w.writerow([val, ",".join(sorted(refs, key=natural)), fp, LCSC.get((val, fp), "")])
    with open(os.path.join(out, f"{board}-cpl.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for ref, val, fp, x, y, rot, side in sorted(rows, key=lambda r: natural(r[0])):
            # KiCad-y zeigt nach unten, Fertigung nach oben
            rot = (rot + CPL_ROT.get((val, fp), 0)) % 360
            w.writerow([ref, f"{x:.4f}mm", f"{-y:.4f}mm", "Top" if side == "top" else "Bottom", f"{rot:.0f}"])
    missing = sorted({v for (v, fp) in groups if (v, fp) not in LCSC})
    print(board, "->", os.path.relpath(out, HERE), "| ohne LCSC-Nummer:", ", ".join(missing) or "-")


if __name__ == "__main__":
    boards = sys.argv[1:] or ["sumpsense-16z", "sumpsense-16z-v2", "sumpsense-24i"]
    for b in boards:
        export(b)

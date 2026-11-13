"""Gemeinsame KiCad-Aufrufe für render_kicad.py und export_sch.py beider Platinen.

KiCad wird in dieser Reihenfolge gesucht:
  1. KICAD_CLI (Pfad zu kicad-cli), optional KICAD_PYTHON (Python mit pcbnew)
  2. KICAD_APPDIR oder ~/.local/share/kicad/squashfs-root (extrahiertes AppImage)
  3. Windows-Installation unter %LOCALAPPDATA%\\Programs\\KiCad bzw. %ProgramFiles%\\KiCad
  4. kicad-cli im PATH
"""

import glob
import os
import re
import shutil
import subprocess
import sys


def _windows_bins():
    roots = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "KiCad"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "KiCad"),
    ]
    found = []
    for root in roots:
        found += glob.glob(os.path.join(root, "*", "bin", "kicad-cli.exe"))
    # Neueste Version zuerst.
    return sorted(found, reverse=True)


def kicad_commands():
    """(cli, python) als Befehlslisten. python ist None, wenn keins gefunden wird."""
    cli = os.environ.get("KICAD_CLI")
    if cli:
        py = os.environ.get("KICAD_PYTHON")
        return [cli], ([py] if py else None)

    appdir = os.environ.get(
        "KICAD_APPDIR", os.path.expanduser("~/.local/share/kicad/squashfs-root")
    )
    apprun = os.path.join(appdir, "AppRun")
    if os.path.isfile(apprun):
        return [apprun, "kicad-cli"], [apprun, "python3.11"]

    for exe in _windows_bins():
        py = os.path.join(os.path.dirname(exe), "python.exe")
        return [exe], ([py] if os.path.isfile(py) else None)

    exe = shutil.which("kicad-cli")
    if exe:
        return [exe], None
    raise SystemExit("kicad-cli nicht gefunden. KICAD_CLI oder KICAD_APPDIR setzen.")


def run_cli(args):
    cli, _ = kicad_commands()
    subprocess.run([*cli, *args], check=True)


def filled_copy(src, dst):
    """Kopie mit gefüllten Zonen. Ohne pcbnew-Python bleibt die Kopie ungefüllt."""
    _, py = kicad_commands()
    script = (
        "import pcbnew\n"
        f"b = pcbnew.LoadBoard({src!r})\n"
        "pcbnew.ZONE_FILLER(b).Fill(b.Zones())\n"
        f"pcbnew.SaveBoard({dst!r}, b)\n"
    )
    try:
        if py is None:
            raise FileNotFoundError
        subprocess.run([*py, "-c", script], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        shutil.copy2(src, dst)
        print("Hinweis: Zonenfüllung fehlgeschlagen — Render ohne Fill.", file=sys.stderr)


def board_length(pcb):
    """Ausdehnung des Umrisses (Edge.Cuts) in x, in mm."""
    text = open(pcb, encoding="utf-8").read()
    xs = []
    # Ein- oder mehrzeilig (KiCad speichert mehrzeilig); nicht über das nächste gr_line hinaus.
    pat = r"\(gr_line\s+\(start ([-\d.]+) [-\d.]+\)\s*\(end ([-\d.]+) [-\d.]+\)(?:(?!\(gr_)[\s\S])*?Edge\.Cuts"
    for m in re.finditer(pat, text):
        xs += [float(m.group(1)), float(m.group(2))]
    if not xs:
        raise SystemExit(f"Kein Umriss in {pcb}")
    return max(xs) - min(xs)


def render_views(pcb, preview):
    """oberseite.png, unterseite.png und 3d.png nach preview/.

    Die Bildhöhe wächst mit der Platinenlänge, damit beide Platinen im
    gleichen Maßstab erscheinen (Bezug: 138 mm -> 5400 px).
    """
    os.makedirs(preview, exist_ok=True)
    length_mm = board_length(pcb)
    flat_h = round(5400 * length_mm / 138.0)
    # Schräge Ansicht: gleiches Bildformat, längere Platine wird kleiner gezoomt.
    persp_zoom = f"{0.95 * min(1.0, 138.0 / length_mm):.3f}"
    # Die Kopie liegt neben der Platine, damit ${KIPRJMOD}/3d/ auflöst.
    filled = os.path.join(os.path.dirname(pcb), ".render-filled.kicad_pcb")
    try:
        filled_copy(pcb, filled)
        flat = ["--rotate", "0,0,-90", "--zoom", "1", "--width", "1000", "--height", str(flat_h)]
        _render(filled, ["--side", "top", *flat], os.path.join(preview, "oberseite.png"))
        _render(filled, ["--side", "bottom", *flat], os.path.join(preview, "unterseite.png"))
        _render(
            filled,
            [
                "--side", "top", "--perspective", "--floor",
                "--rotate", "-42,0,-70", "--zoom", persp_zoom,
                "--width", "1600", "--height", "3000",
            ],
            os.path.join(preview, "3d.png"),
        )
    finally:
        # SaveBoard legt zusätzlich .kicad_pro und .kicad_prl an.
        stem = os.path.splitext(filled)[0]
        for path in (filled, stem + ".kicad_pro", stem + ".kicad_prl"):
            if os.path.exists(path):
                os.remove(path)


def layout_svgs(pcb, preview, head_mm=52.0):
    """platine.svg (ganze Platine) und kopf.svg (die ersten head_mm) als Lagenplot.

    KiCad plottet die Platine liegend; hier wird sie hochkant gedreht, trockenes Ende oben,
    wie in oberseite.png.
    """
    os.makedirs(preview, exist_ok=True)
    flat = os.path.join(preview, ".layout-flat.svg")
    run_cli([
        "pcb", "export", "svg", "--layers", "F.Cu,B.Cu,F.Silkscreen,Edge.Cuts",
        "--mode-single", "--page-size-mode", "2", "--exclude-drawing-sheet",
        "--drill-shape-opt", "2", "-o", flat, pcb,
    ])
    svg = open(flat, encoding="utf-8").read()
    os.remove(flat)
    m = re.search(r'<svg[^>]*\bwidth="([\d.]+)(\w*)"[^>]*\bheight="([\d.]+)(\w*)"[^>]*viewBox="([^"]+)"', svg, re.S)
    w, unit, h = float(m.group(1)), m.group(2), float(m.group(3))
    vx, vy, vw, vh = (float(v) for v in m.group(5).split())
    body = svg[svg.index(">", m.end()) + 1:svg.rindex("</svg>")]
    per_mm = vw / board_length(pcb)

    def write(name, length_units):
        scale_h = length_units / vw
        out = (
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{h:g}{unit}" height="{w * scale_h:g}{unit}" '
            f'viewBox="0 0 {vh:g} {length_units:g}">\n'
            f'<rect width="100%" height="100%" fill="#ffffff"/>\n'
            f'<g transform="translate({vh:g},0) rotate(90) translate({-vx:g},{-vy:g})">{body}</g>\n</svg>\n'
        )
        path = os.path.join(preview, name)
        open(path, "w", encoding="utf-8").write(out)
        print(path)

    write("platine.svg", vw)
    write("kopf.svg", min(vw, head_mm * per_mm))


def model_dir():
    """Pfad zu den KiCad-STEP-Modellen. Ohne den findet der Render keine Bauteile."""
    env = os.environ.get("KICAD10_3DMODEL_DIR")
    candidates = [
        env,
        os.path.expanduser("~/.local/share/kicad/10.0/3dmodels"),
        "/usr/share/kicad/3dmodels",
    ]
    for path in candidates:
        if path and os.path.isdir(os.path.join(path, "Resistor_SMD.3dshapes")):
            return path
    return None


def _render(pcb, args, out):
    defines = []
    models = model_dir()
    if models:
        defines = ["--define-var", f"KICAD10_3DMODEL_DIR={models}"]
    else:
        print("Hinweis: keine 3D-Modelle gefunden — Render ohne Bauteile.", file=sys.stderr)
    run_cli([
        "pcb", "render", "--quality", "high", "--background", "opaque",
        *defines, *args, "-o", out, pcb,
    ])
    print(out)


def export_schematic(sch, preview):
    """schaltplan.pdf und schaltplan.svg nach preview/."""
    if not os.path.isfile(sch):
        raise SystemExit(f"fehlt: {sch}  — zuerst python3 gen_sch.py")
    os.makedirs(preview, exist_ok=True)
    pdf = os.path.join(preview, "schaltplan.pdf")
    svg = os.path.join(preview, "schaltplan.svg")
    tmp = os.path.join(preview, "schaltplan-svg")
    run_cli(["sch", "export", "pdf", "-o", pdf, sch])
    run_cli(["sch", "export", "svg", "-o", tmp, sch])
    nested = os.path.join(tmp, os.path.splitext(os.path.basename(sch))[0] + ".svg")
    if os.path.isfile(nested):
        os.replace(nested, svg)
        shutil.rmtree(tmp)
    print(pdf)
    print(svg)

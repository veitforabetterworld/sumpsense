"""Schaltplan als PDF und SVG exportieren. Vorher: python3 gen_sch.py"""

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SCH = os.path.join(HERE, "wasserstand-14mm.kicad_sch")
PREVIEW = os.path.join(HERE, "preview")
APPDIR = os.environ.get(
    "KICAD_APPDIR",
    os.path.expanduser("~/.local/share/kicad/squashfs-root"),
)


def run(args):
    apprun = os.path.join(APPDIR, "AppRun")
    if not os.path.isfile(apprun):
        raise SystemExit(f"KiCad AppDir fehlt: {APPDIR}")
    subprocess.run([apprun, "kicad-cli", *args], check=True)


def main():
    if not os.path.isfile(SCH):
        raise SystemExit(f"fehlt: {SCH}  — zuerst python3 gen_sch.py")
    os.makedirs(PREVIEW, exist_ok=True)
    pdf = os.path.join(PREVIEW, "schaltplan.pdf")
    svg = os.path.join(PREVIEW, "schaltplan.svg")
    run(["sch", "export", "pdf", "-o", pdf, SCH])
    run(["sch", "export", "svg", "-o", os.path.join(PREVIEW, "schaltplan-svg"), SCH])
    nested = os.path.join(PREVIEW, "schaltplan-svg", "wasserstand-14mm.svg")
    if os.path.isfile(nested):
        os.replace(nested, svg)
        os.rmdir(os.path.join(PREVIEW, "schaltplan-svg"))
    print(pdf)
    print(svg)


if __name__ == "__main__":
    main()

"""KiCad-Raytrace nach preview/. Aufruf: python3 render_kicad.py

Braucht das extrahierte KiCad-AppImage unter ~/.local/share/kicad/squashfs-root
oder die Variable KICAD_APPDIR. Zonen werden nur in einer Kopie gefüllt.
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "wasserstand-14mm.kicad_pcb")
PREVIEW = os.path.join(HERE, "preview")
APPDIR = os.environ.get(
    "KICAD_APPDIR",
    os.path.expanduser("~/.local/share/kicad/squashfs-root"),
)


def run(args):
    env = os.environ.copy()
    apprun = os.path.join(APPDIR, "AppRun")
    if os.path.isfile(apprun):
        cmd = [apprun, "kicad-cli", *args]
    else:
        raise SystemExit(f"KiCad AppDir fehlt: {APPDIR}")
    subprocess.run(cmd, check=True, env=env)


def filled_copy(src, dst):
    script = (
        "import pcbnew\n"
        f"b = pcbnew.LoadBoard({src!r})\n"
        "pcbnew.ZONE_FILLER(b).Fill(b.Zones())\n"
        f"pcbnew.SaveBoard({dst!r}, b)\n"
    )
    apprun = os.path.join(APPDIR, "AppRun")
    try:
        subprocess.run([apprun, "python3.11", "-c", script], check=True)
    except subprocess.CalledProcessError:
        import shutil
        shutil.copy2(src, dst)
        print("Hinweis: Zonenfüllung fehlgeschlagen — Render ohne Fill.", file=sys.stderr)


def render(pcb, args, out):
    run([
        "pcb", "render", "--quality", "high", "--background", "opaque",
        *args, "-o", out, pcb,
    ])
    print(out)


def main():
    os.makedirs(PREVIEW, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        filled = os.path.join(tmp, "filled.kicad_pcb")
        filled_copy(PCB, filled)
        common = ["--rotate", "0,0,-90", "--zoom", "1", "--width", "1000", "--height", "5400"]
        render(filled, ["--side", "top", *common], os.path.join(PREVIEW, "oberseite.png"))
        render(filled, ["--side", "bottom", *common], os.path.join(PREVIEW, "unterseite.png"))
        render(
            filled,
            [
                "--side", "top", "--perspective", "--floor",
                "--rotate", "-42,0,-70", "--zoom", "0.95",
                "--width", "1600", "--height", "3000",
            ],
            os.path.join(PREVIEW, "3d.png"),
        )


if __name__ == "__main__":
    sys.exit(main())

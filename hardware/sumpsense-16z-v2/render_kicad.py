"""KiCad-Raytrace und Lagenplot nach preview/.

oberseite.png, unterseite.png, 3d.png, dazu platine.svg und kopf.svg aus der Platine.
Aufruf: python3 render_kicad.py
Wo KiCad gesucht wird, steht in ../kicad_tools.py. Zonen werden nur in einer Kopie gefüllt.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import kicad_tools  # noqa: E402

if __name__ == "__main__":
    pcb = os.path.join(HERE, "sumpsense-16z-v2.kicad_pcb")
    preview = os.path.join(HERE, "preview")
    kicad_tools.render_views(pcb, preview)
    kicad_tools.layout_svgs(pcb, preview, head_mm=50.0)

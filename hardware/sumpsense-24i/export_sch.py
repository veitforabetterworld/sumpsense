"""Schaltplan als PDF und SVG nach preview/. Vorher: python3 gen_sch.py"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import kicad_tools  # noqa: E402

if __name__ == "__main__":
    kicad_tools.export_schematic(
        os.path.join(HERE, "sumpsense-24i.kicad_sch"),
        os.path.join(HERE, "preview"),
    )

"""KiCad-Schaltplan aus design.py — gleiche Netze wie die Platine.

  python3 gen_sch.py
  python3 export_sch.py   # PDF und SVG nach preview/
"""

import os
import uuid

import design as D

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "wasserstand-14mm.kicad_sch")
NS = "wasserstand-14mm-sch"


def uid(text: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{NS}:{text}"))


def pin_line(num: str, y: float) -> str:
    return f"""\t\t\t(pin passive line
\t\t\t\t(at -7.62 {-y:.2f} 180)
\t\t\t\t(length 2.54)
\t\t\t\t(name "{num}" (effects (font (size 1.27 1.27))))
\t\t\t\t(number "{num}")
\t\t\t)"""


def symbol_def(sym: str, pins: list[str]) -> str:
    body = "\n".join(pin_line(p, (len(pins) / 2.0 - i) * 2.54) for i, p in enumerate(pins))
    return f"""\t\t(symbol "wls:{sym}"
\t\t\t(pin_names (offset 0.254))
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(property "Reference" "U" (at 0 5.08 0) (effects (font (size 1.27 1.27))))
\t\t\t(property "Value" "{sym}" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))
\t\t\t(symbol "{sym}_0_1"
{body}
\t\t\t)
\t\t)"""


def part_rows(part: D.Part) -> list[tuple[str, str]]:
    """(Padname, Netz) nur mit Netz."""
    rows = []
    for pad in part.pads:
        if pad.net:
            rows.append((pad.name, pad.net))
    return rows


def column_of(part: D.Part) -> int:
    if part.kind in ("grove", "hdr"):
        return 0
    if part.kind == "qfn":
        return 1
    if part.kind == "c0402" or part.ref in ("R1", "R2"):
        return 2
    if part.kind == "r0402":
        return 3
    return 4


COL_X = [50.80, 101.60, 152.40, 203.20, 254.00]


def main() -> int:
    buckets: dict[int, list[D.Part]] = {i: [] for i in range(len(COL_X))}
    for part in D.PARTS:
        buckets[column_of(part)].append(part)

    defs: dict[str, list[str]] = {}
    instances = []
    labels = []
    col_bottom = [25.4] * len(COL_X)

    for col, parts in buckets.items():
        x = COL_X[col]
        for part in parts:
            rows = part_rows(part)
            if not rows:
                continue
            pin_names = [p for p, _ in rows]
            sym = part.ref
            if sym not in defs:
                defs[sym] = pin_names
            n = len(pin_names)
            y = col_bottom[col] + (n / 2.0) * 2.54
            val = part.value if part.value != part.ref else sym
            instances.append(
                f"""\t(symbol
\t\t(lib_id "wls:{sym}")
\t\t(at {x:.2f} {y:.2f} 0)
\t\t(unit 1)
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(uuid "{uid(sym)}")
\t\t(property "Reference" "{part.ref}" (at {x:.2f} {y + 3.81:.2f} 0) (effects (font (size 1.27 1.27))))
\t\t(property "Value" "{val}" (at {x:.2f} {y - 3.81:.2f} 0) (effects (font (size 1.27 1.27))))
"""
                + "\n".join(f'\t\t(pin "{p}" (uuid "{uid(sym + p)}"))' for p in pin_names)
                + "\n\t)"
            )
            net_by_pin = {p: net for p, net in rows}
            for i, p in enumerate(pin_names):
                py = y + (n / 2.0 - i) * 2.54
                labels.append(
                    f'\t(label "{net_by_pin[p]}" (at {x - 7.62:.2f} {py:.2f} 180) '
                    f'(effects (font (size 1.27 1.27))) (uuid "{uid(sym + p + "L")}"))'
                )
            col_bottom[col] = y + (n / 2.0) * 2.54 + 7.62

    sym_defs = [symbol_def(name, pins) for name, pins in sorted(defs.items())]
    text = f"""(kicad_sch
\t(version 20250114)
\t(generator "gen_sch")
\t(generator_version "10.0")
\t(uuid "{uid('sheet')}")
\t(paper "A1")
\t(title_block
\t\t(title "Wasserstand 14 mm")
\t\t(rev "1")
\t\t(comment 1 "Schaltung = Seeed Grove Water Level 10 cm, Lage aus design.py")
\t)
\t(lib_symbols
{chr(10).join(sym_defs)}
\t)
{chr(10).join(instances)}
{chr(10).join(labels)}
\t(sheet_instances
\t\t(path "/" (page "1"))
\t)
)
"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(OUT, "Symbole", len(defs), "Instanzen", len(instances))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

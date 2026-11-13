#!/usr/bin/env python3
"""TL + π am DN007-Feed: S11 @ 2,45 GHz → Bauteilwerte."""

from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "results.json"

F0 = 2.45e9
C0 = 299792458.0
H_MM = 1.6
ER = 4.3
Z_ANT = 50.0 + 8.0j

# Antenne → C7 (gerader 0,46-mm-Feed, C7 flach auf der Bahn).
PRE_C7 = ((0.46, 0.632),)
# C7 → R21-Pad.
MID = ((0.46, 0.320), (1.0, 0.450), (1.0, 0.424), (1.0, 0.726), (0.5, 0.620))
# R21 → C8, dann C8 → Pin 32.
TO_C8 = ((0.5, 0.560), (1.0, 7.300))
AFTER_C8 = (
    (1.0, 2.900),
    (1.0, 0.814),
    (1.0, 4.600),
    (0.75, 1.556),
    (0.28, 0.566),
)


def microstrip_z0(w_mm: float) -> float:
    u = w_mm / H_MM
    if u <= 1:
        er_eff = (ER + 1) / 2 + (ER - 1) / 2 * (1 / math.sqrt(1 + 12 / u) + 0.04 * (1 - u) ** 2)
        return (60 / math.sqrt(er_eff)) * math.log(8 / u + u / 4)
    er_eff = (ER + 1) / 2 + (ER - 1) / 2 / math.sqrt(1 + 12 / u)
    return (120 * math.pi) / (math.sqrt(er_eff) * (u + 1.393 + 0.667 * math.log(u + 1.444)))


def er_eff(w_mm: float) -> float:
    u = w_mm / H_MM
    if u <= 1:
        return (ER + 1) / 2 + (ER - 1) / 2 * (1 / math.sqrt(1 + 12 / u) + 0.04 * (1 - u) ** 2)
    return (ER + 1) / 2 + (ER - 1) / 2 / math.sqrt(1 + 12 / u)


def width_for_z0(z0: float) -> float:
    lo, hi = 0.12, 5.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if microstrip_z0(mid) > z0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def par_z(z: complex, c_pf: float) -> complex:
    if c_pf <= 0:
        return z
    y = 1 / z + 1j * 2 * math.pi * F0 * (c_pf * 1e-12)
    return 1 / y


def tl_zin(z0: float, w_mm: float, zl: complex, l_mm: float) -> complex:
    beta = 2 * math.pi * F0 * math.sqrt(er_eff(w_mm)) / C0 * (l_mm * 1e-3)
    t = math.tan(beta)
    if abs(t) < 1e-9:
        return zl
    return z0 * (zl + 1j * z0 * t) / (z0 + 1j * zl * t)


def thru(z: complex, segs) -> complex:
    for w, length in segs:
        z = tl_zin(microstrip_z0(w), w, z, length)
    return z


def zin_at_chip(c7: float, c8: float, r: float = 0.0) -> complex:
    """Antenne → kurze Leitung → C7|| → R21 → C8|| → Leitung zum Pin."""
    z = thru(Z_ANT, PRE_C7)
    z = par_z(z, c7)
    z = thru(z, MID)
    z = z + r
    z = thru(z, TO_C8)
    z = par_z(z, c8)
    return thru(z, AFTER_C8)


def s11_db(zin: complex, zref: float = 50.0) -> float:
    g = (zin - zref) / (zin + zref)
    return 20 * math.log10(abs(g) + 1e-15)


def delivered(db: float) -> float:
    g = 10 ** (db / 20)
    return 1 - g * g


def sweep_layout():
    best = None
    for c7 in [i * 0.1 for i in range(0, 25)]:
        for c8 in [i * 0.1 for i in range(0, 25)]:
            zin = zin_at_chip(c7, c8)
            db = s11_db(zin)
            row = {"c7_pf": round(c7, 1), "c8_pf": round(c8, 1), "s11_db": round(db, 2)}
            if best is None or db < best["s11_db"]:
                best = {**row, "zin_ohm": [round(zin.real, 2), round(zin.imag, 2)]}
    return best


def stuffed(c7: float, c8: float) -> dict:
    zin = zin_at_chip(c7, c8)
    db = s11_db(zin)
    return {
        "c7_pf": c7,
        "c8_pf": c8,
        "s11_db": round(db, 2),
        "power_to_antenna": round(delivered(db), 3),
        "zin_ohm": [round(zin.real, 2), round(zin.imag, 2)],
    }


def sweep():
    w_full = width_for_z0(50.0)
    pre = round(sum(l for _, l in PRE_C7), 2)
    post = round(sum(l for _, l in TO_C8) + sum(l for _, l in AFTER_C8), 2)
    on_board = stuffed(1.0, 1.0)
    return {
        "f_ghz": 2.45,
        "stackup_mm": H_MM,
        "er": ER,
        "z0_ohm": {
            "w_0.46mm": round(microstrip_z0(0.46), 1),
            "w_1.0mm": round(microstrip_z0(1.0), 1),
            "w_0.2mm_neck": round(microstrip_z0(0.2), 1),
        },
        "trace_width_mm_layout": 1.0,
        "trace_width_mm_true_50ohm": round(w_full, 2),
        "length_antenna_to_pi_mm": pre,
        "length_pi_to_pin_mm": post,
        "z_antenna_assumed_ohm": [Z_ANT.real, Z_ANT.imag],
        "stuffed_c7_1pF_c8_1pF": on_board,
        "best_lumped_pi": sweep_layout(),
        "layout_bom_recommendation": {
            "c7": "1pF",
            "c8_pf": 1.0,
            "note": "C7 und C8: 1 pF C0G 0402 C1550 (Preferred). Kleinstes Basic-C0G ist 10 pF (C32949) und schließt den Feed bei 2,45 GHz kurz.",
        },
    }


def main():
    res = sweep()
    OUT.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    s = res["stuffed_c7_1pF_c8_1pF"]
    print(json.dumps(res, indent=2))
    print(
        f"\nZ0(1,0 mm)≈{res['z0_ohm']['w_1.0mm']} Ω, "
        f"Antenne→π {res['length_antenna_to_pi_mm']} mm, "
        f"π→Pin {res['length_pi_to_pin_mm']} mm, "
        f"C7=1 pF C8=1 pF → S11 {s['s11_db']} dB, "
        f"Leistung an der Antenne {s['power_to_antenna']:.0%}"
    )


if __name__ == "__main__":
    main()

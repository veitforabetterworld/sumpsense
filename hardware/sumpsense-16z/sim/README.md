# RF-Simulation (S11) — SumpSense-16z

Lumped **Microstrip + π** am DN007-Feed — Näherung vor dem Ätzen, **kein Ersatz für VNA/Messung**.

## Ausführen

```bash
python3 sim/run_s11.py
```

Ergebnis: `sim/results.json` + Konsolenempfehlung.

## Modell

| Parameter | Wert |
|-----------|------|
| f₀ | 2,45 GHz |
| FR4 | 1,6 mm, εr 4,3 |
| Antenne am Feed | 50 + j8 Ω (DN007, 1,6 mm vs. TI-1 mm) |
| Leitung | Antenne → π ≈ 2,6 mm, π → Pin 32 ≈ 18,4 mm |
| π | C7 (Antennen-Seite, am IFA-Feed), C8 (Chip-Seite), R21 0 Ω |

Zuleitung **1,0 mm** (Hammerstad ≈ 88 Ω auf 1,6 mm FR4). 50 Ω wäre 3,14 mm breit. **C7 und C8 = 1 pF C0G** (JLC **C1550**, Preferred). Kleinstes Basic-C0G ist 10 pF und schließt den Feed kurz. Modell, kein VNA.

## Layout-Umsetzung

```bash
/path/to/AppRun python3.11 relayout_rf_corridor.py --move
/path/to/AppRun python3.11 relayout_rf_corridor.py --wire   # Power + XTAL: je eigener Prozess bei SWIG-Fehler
/path/to/AppRun python3.11 apply_rf_pi.py --clear
/path/to/AppRun python3.11 apply_rf_pi.py --place
```

- IFA-Feed **0,46 mm**, dann **1,0 mm**. C7 und R21 am Feed, C8 auf der Bahn. Letzte **0,28 mm** in Pin 32, davor **0,75 mm**
- GND-Käfig-Via **0,6/0,3** bei (85,3 / 20,05)
- **openEMS**: optional, gleiches Stackup + Gerber aus `jlcpcb.py`

# SumpSense-16z

16 kapazitive Stufen, **ESP32-H2** (Zigbee 3.0), Ausgang für **5-V-Magnetventil**. **14 × 125 mm**, Rohr **14,5 mm**, Stufen **5 mm** (ca. 8 cm Messbereich).

<img src="preview/3d.png" alt="SumpSense-16z" width="280">

## Platine bestellen (JLCPCB)

1. [`jlcpcb/`](jlcpcb/): Gerber-ZIP, BOM, CPL.
2. Neu: `python3 ../jlcpcb.py sumpsense-16z`
3. **PCBA:** alle drei hochladen; Vias **0,6/0,3 mm**. Economic: **2× Extended** (H2, Quarz). **JP1 PAIR** nicht bestücken (nur Kupfer auf der Platine).

## Anschluss

| Löcher | Funktion |
|--------|----------|
| **J1** GND, 5 V, VLV | Versorgung; Ventil zwischen **5 V** und **VLV** |
| **J3** D+, D− | USB nur zum Flashen |
| **JP1 PAIR** | GPIO9 und GND kurzschließen (Pairing / erster Flash) |

## Firmware, Pairing, Smart Home

**[Firmware-README](../../firmware/README.md#sumpsense-16z)** — Bauen, Flashen, PAIR-Tabelle, Home-Assistant-Screenshot.

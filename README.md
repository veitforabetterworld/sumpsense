# SumpSense

Kapazitive Füllstandssensoren für **14,5-mm-Rohr** (schmaler Stab, 5-mm-Raster). Inspiriert vom [Seeed Grove Water Level Sensor](https://wiki.seeedstudio.com/Grove-Water-Level-Sensor/).

| Platine | Stufen | Bus | Doku |
|---------|--------|-----|------|
| [SumpSense-24i](hardware/sumpsense-24i/README.md) | 24 | I²C | Bestellen → [`firmware`](firmware/README.md#sumpsense-24i) |
| [SumpSense-16z](hardware/sumpsense-16z/README.md) | 16 | Zigbee 3.0 + Ventil | Bestellen → [`firmware`](firmware/README.md#sumpsense-16z) |
| [SumpSense-16z-v2](hardware/sumpsense-16z-v2/README.md) | 16 | Zigbee 3.0 + Ventil, ESP32-H2-MINI-1, 100,0 mm (+ 5,4 mm Antenne) | Bestellen → [`firmware`](firmware/README.md#sumpsense-16z) (`SS_BOARD=2`) |

Gerber/BOM je Board: `hardware/<name>/jlcpcb/` — erzeugen mit `python3 hardware/jlcpcb.py <name>`.

## Boardprüfung

`python3 hardware/check_boards.py [<name>]` führt DRC (mit Schaltplan-Parität) und ERC aus und meldet jeden Fehler und jede Warnung. Erlaubte Ausnahmen stehen in den Projektdateien, damit KiCad und das Skript dasselbe melden:

- `<name>.kicad_dru`: Der Schraubenkopf MH1 darf die Courtyards anderer Bauteile überdecken (einzige Ausnahme).
- `sumpsense-24i.kicad_pro`: In der ERC-Pin-Matrix ist „Bidirektional ↔ Power-Ausgang“ erlaubt, weil PA3 als Adressmerkmal fest an GND/VCC liegt.

Angepasste Footprints liegen in den Projektbibliotheken (`zig:`, `ssi:`), damit es keine Abweichungen von der KiCad-Bibliothek gibt.

Der Git-Hook `.githooks/pre-commit` startet die Prüfung bei jedem Commit, der Platinendateien enthält, und bricht den Commit bei Befunden ab. Einmal pro Klon aktivieren:

```bash
git config core.hooksPath .githooks
```

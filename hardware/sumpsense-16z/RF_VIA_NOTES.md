# RF- und GND-Via-Revision (Kost-Optimierung)

Layout-Änderung ohne Hardware-Messung (Abnahme vor Serienfreigabe).

## Vias allgemein

- Durchkontaktierung: **0,6 / 0,3 mm** (JLC-Standard). Mounting **2,7 mm**, J1/J3 **1,0 mm** unverändert.

## Sense

- Elektroden **B.Cu** (Wasser/Rohrseite), je Stufe **1 Via** am Kopf (Resistor-Seite).
- **−16** Bohrungen (ehemals zweites Via pro Elektrode).

## GND-Stitch (Antennenkopf)

Entfernt (Pitch-Reihe y≈20 mm auf **~4 mm** verbreitert + Doppel-Stitch bei H2):

| x (mm) | y (mm) |
|--------|--------|
| 75.8 | 20.05 |
| 79.7 | 20.05 |
| 87.3 | 20.05 |
| 91.3 | 20.05 |
| 95.3 | 20.05 |
| 97.3 | 20.05 |
| 105.45 | 19.6 |
| 106.65 | 19.6 |

**Behalten** u. a.: 73.8, 77.8, 81.7, 85.3, 89.3, 93.3, 98.8 (Reihe), RF-Nähe 99.9/101.6/105.45/106.65/107.75.

## RF-Abnahme (Pflicht mit Referenzplatine)

Gleicher Koordinator/Firmware, **10×** messen, Median:

| Metrik | Kriterium |
|--------|-----------|
| LQI @ 3 m / 10 m | ≤ 5 Punkte schlechter |
| RSSI | ≤ 3 dB schlechter |

Bei Fail: zuletzt entfernte Via-Gruppe zurücksetzen (siehe Tabelle oben zuerst).

Datum Messung: _offen_

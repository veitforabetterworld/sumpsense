# Wasserstand Zigbee

Zweite Platine neben [`sumpgauge-14mm`](../sumpgauge-14mm/README.md). Ein **ESP32-H2**, **16** kapazitive Stufen, Inverted-F auf der Platine, Low-Side-Ausgang für ein **5-V-Magnetventil**. Kein I2C, kein zweiter Controller.

Platine **14,0 mm** breit, **1,6 mm**, zwei Lagen. Rohr **14,5 mm**. Stufenabstand **5 mm**, Messlänge etwa **8 cm**. Elektrodenmaß wie die I2C-Platine (3,4 mm × 12,5 mm). **M2,5** bei y = 7 mm, Bohrung 2,7 mm, damit der bestehende Clip passt. Antenne, Quarz, H2 und alle Löcher bleiben auf der trockenen Seite des Lochs.

## Anschluss

Löcher im Raster **2,54 mm**, kein Steckverbinder.

| Leiste | Pins | Rolle |
|--------|------|--------|
| J1 | 5V, GND | Versorgung. Auch die 5 V beim Flashen |
| J2 | 5V, VLV | Magnetventil zwischen 5V und VLV (Drain) |
| J3 | GND, D+, D−, BOOT | Flash, von der Antenne her in dieser Reihenfolge |

Freilaufdiode auf der Platine: Kathode an 5 V, Anode am Drain.

## Pinbelegung

E01 ist die Stufe am Clip (niedrigster Stand), E16 die Spitze. Jede Stufe hängt über **100 kΩ** am GPIO.

| Stufe | GPIO | Zusatz |
|-------|------|--------|
| E01–E06 | GPIO0–GPIO5 | |
| E07 | GPIO8 | 10 kΩ nach 3,3 V, dann 100 kΩ |
| E08 | GPIO9 | BOOT. 10 kΩ nach 3,3 V, dann 100 kΩ |
| E09–E13 | GPIO10–GPIO14 | |
| E14 | GPIO25 | JTAG_SEL_ENABLE nicht brennen, sonst ist der Pin weg |
| E15 | GPIO24 | |
| E16 | GPIO23 | Spitze |

Weiter fest: **GPIO27 = D+**, **GPIO26 = D−**, ohne Serienwiderstand. **GPIO22** ist das Gate des AO3400A, nur 100 kΩ nach GND, kein Vorwiderstand. **EN (Pin 17)** liegt direkt an 3,3 V, ohne die 10 kΩ und 1 µF aus dem Espressif-Guide. Kein 32-kHz-Quarz, keine Ferritperle, kein Buck.

## Flashen

Leerer Flash bootet nur in den Download, wenn **GPIO8 = 1** und **GPIO9 = 0**. GPIO8 hat die 10 kΩ nach 3,3 V. GPIO9 muss hart an GND, am Pin selbst, nicht hinter dem 100 kΩ.

1. BOOT mit GND brücken.
2. 5 V an J1 legen. Die Leiste J3 führt keine Versorgung.
3. USB-Seriell an D+ und D−. Der Port erscheint als `/dev/ttyACM*`. Ohne den 32-MHz-Quarz zählt USB nicht.
4. Flashen, Brücke weg, **Strom aus**. Ein Reset über USB liest den Strap nicht neu.

Spätere Flashes brauchen die Brücke nicht, solange die Firmware USB Serial/JTAG auf GPIO26/GPIO27 anlässt.

## Antenne und HF

Inverted-F nach **TI DN007**, Dokument **SWRU120D** Rev. D, 25,7 × 7,5 mm. Das Polygon stammt aus dem KiCad-Modul `PCB_IF_ANT_2.4G` (tommag/kicad-lib), das diese Maße abbildet. Die Espressif-Freihaltezone von 15 mm passt auf 14 mm Breite nicht. Das ist Absicht: der Kopf wird nicht breiter.

Die Speiseleitung ist **2,2 mm** breit. Ein 50-Ω-Streifen auf 1,6 mm FR4 wäre etwa 2,9 mm und passt neben der Antenne nicht. 2,2 mm liegt grob bei 55–60 Ω. Bezug ist die Masse auf der Unterseite. Auf der Oberseite liegt im HF-Korridor kein GND, sonst wäre die Leitung koplanar.

**R20** (0 Ω) sitzt statt der 24 nH auf XTAL_P, **R21** (0 Ω) statt der 2–3 nH in der Antennenleitung. Die Shunt-Kondensatoren des CLC-Glieds fehlen. Die beiden Brücken sind die Stellen für einen späteren Spulentausch ohne neues Layout. Mit den Brücken kann die Reichweite geringer sein.

Quarz **32 MHz**, ±10 ppm, Last 8 pF, dazu zwei **12 pF** C0G. Pad 1 und Pad 3 sind der Quarz, Pad 2 und Pad 4 Masse. R20 liegt zwischen Chip-Pin 29 und Quarz-Pad 1.

3,3 V macht ein AMS1117-3.3. 10 µF an 5 V, **1 Ω** in Serie zu 10 µF an 3,3 V, zwei 100 nF an den Versorgungs-Pins des H2.

## Stückliste

C-Nummern nur, wo sie geprüft sind. Der Rest ist die Klasse, ohne erfundene Nummer.

| Ref | Wert | Gehäuse | Klasse |
|-----|------|---------|--------|
| U1 | ESP32-H2 | QFN32 4×4, 0,4 mm | Extended. Bestellcode beim Bestellen prüfen. ESP32-H2FH4 (LCSC C22470214) ist NRND |
| U2 | AMS1117-3.3 | SOT-223 | Basic, C6186 |
| Q1 | AO3400A | SOT-23 | Basic, C20917. Low-Side, Source an GND |
| D1 | SS14 | SOD-123 | Basic-Liste. Kathode an 5 V. Keine C-Nummer festgelegt |
| Y1 | 32 MHz, ±10 ppm, Last 8 pF | 3225 | Extended |
| C1, C2 | 12 pF, C0G | 0402 | Basic |
| C3, C4 | 10 µF | 0805 | Basic |
| C5, C6 | 100 nF | 0402 | Basic |
| R1–R16 | 100 kΩ | 0402 | Basic, Serie zur Elektrode |
| R17, R18 | 10 kΩ | 0402 | Basic, GPIO8 und GPIO9 nach 3,3 V |
| R20, R21 | 0 Ω | 0402 | Basic, Quarz- und Antennenbrücke |
| R22 | 1 Ω | 0402 | Basic, zwischen LDO-Ausgang und 3,3 V |
| R23 | 100 kΩ | 0402 | Basic, Gate nach GND |
| MH1 | M2,5 | Bohrung 2,7 mm | Clip-Loch |

## Dateien

`design.py` ist die einzige Quelle für Bauteile, Netze und Koordinaten. `python3 gen_pcb.py` schreibt `wasserstand-zigbee.kicad_pcb` und `preview/`. `python3 gen_sch.py` schreibt den Schaltplan aus denselben Netzen. Der Generator bricht ab, wenn Kupfer in der Antennen-Sperrzone liegt, ein Abstand unter 0,15 mm fällt oder ein Netz offen bleibt.

Firmware (ESP-IDF, Zigbee-Stack) gehört nicht zu diesem Stand.

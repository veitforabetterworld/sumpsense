# Firmware (ATtiny1616)

**Seeed:** Eagle-Schaltung/Platine offen. **MCU-Firmware im Chip nicht** von Seeed veröffentlicht ([Forum](https://forum.seeedstudio.com/t/grove-water-level-sensor-attiny1616-code/255081)). Open Source ist nur der **Arduino-I2C-Client** (`examples/water-level-sensor-demo.ino`).

## Welche Images nutzen?

| Datei | Inhalt | I2C wie Seeed-Demo? |
|-------|--------|---------------------|
| `U1.hex`, `U2.hex` (Root) | Von **einem Original-Grove** ausgelesen (`dump.sh`) | ja (8 Bytes pro Lesevorgang) |
| `community/U1.hex`, `U2.hex` | Community [jenskeiner/water_level](https://github.com/jenskeiner/water_level), Build [ElliottC123/water_level](https://github.com/ElliottC123/water_level) | **nein** — je Pad 16-Bit-Rohwert, Host-Code anpassen |

Für unser Board mit Seeed-Demo (`examples/water-level-sensor-demo.ino`): **Werks-Images** per Dump von einem Original-Sensor erzeugen und als `U1.hex` / `U2.hex` ablegen.

Community-Firmware fixiert v. a. Kalibrierung nach Power-On; Protokoll weicht ab.

## Flashen

Voraussetzung: [Adafruit UPDI Friend](https://learn.adafruit.com/adafruit-updi-friend), Verdrahtung wie `hardware/sumpsense-24i/README.md` (nur **einen** Chip, Grove ab).

```bash
cd firmware
UPDI_PORT=/dev/ttyACM0 ./flash.sh u1    # Loch U1
UPDI_PORT=/dev/ttyACM0 ./flash.sh u2    # Loch U2
```

Ohne `U1.hex`/`U2.hex` flasht das Skript automatisch `community/*.hex` und warnt.

## Werks-Firmware sichern (Original-Grove)

```bash
UPDI_PORT=/dev/ttyACM0 ./dump.sh u1
UPDI_PORT=/dev/ttyACM0 ./dump.sh u2
```

Erzeugt `U1.hex` / `U2.hex` im Ordner `firmware/`.

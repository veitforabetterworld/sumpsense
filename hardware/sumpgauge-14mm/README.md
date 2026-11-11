# Wasserstand 14 mm

Kapazitiver Füllstandssensor für **14,5-mm-Rohr** (Platine **14,0 × 138,0 mm**). Schaltung wie der [Seeed Grove Water Level Sensor (10 cm)](https://wiki.seeedstudio.com/Grove-Water-Level-Sensor/). Zwei **ATtiny1616**, **I2C** am Grove. **U1** = **12** Segmente am Stecker (**0x78**), **U2** = **8** Segmente an der Spitze (**0x77**). Segmentabstand **5 mm**. Linie **MAX**: nicht tiefer eintauchen.

## Anschluss im Betrieb

Grove-Kabel an **J1** (trockenes Ende). Elektroden zur Spitze.

| Grove | Signal |
|-------|--------|
| Gelb | SCL |
| Weiß | SDA |
| Rot | VCC (3,3 V oder 5 V) |
| Schwarz | GND |

Master liest **0x78**, dann **0x77** (Beispiel: [`examples/water-level-sensor-demo.ino`](../../examples/water-level-sensor-demo.ino)).

## Flashen (Adafruit UPDI Friend)

Vier Löcher **J3** unter dem Grove (Dupont nur beim Flashen). Von der Stecker-Kante: **GND · VCC · U1 · U2** — schwarz / rot / weiß an Friend; weiß nacheinander auf **U1**, dann **U2**. Nur ein Chip, Grove ab, eine Spannungsquelle.

```bash
cd ../../firmware
UPDI_PORT=/dev/ttyACM0 ./flash.sh u1
UPDI_PORT=/dev/ttyACM0 ./flash.sh u2
```

Details, Firmware-Quellen, Dump vom Original-Sensor: [`../../firmware/README.md`](../../firmware/README.md).

**Firmware:** Seeed veröffentlicht die **MCU-Firmware nicht** (nur Hardware + Arduino-Demo). Für **100 % Seeed-I2C** zuerst mit `dump.sh` von einem Original-Grove lesen. Ohne `U1.hex`/`U2.hex` nutzt `flash.sh` Community-HEX (`community/`) — funktioniert, aber **anderes I2C-Protokoll** (16-Bit je Pad).

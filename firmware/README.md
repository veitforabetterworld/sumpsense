# Firmware

| Platine | Ordner | Controller | Schnittstelle |
|---------|--------|------------|---------------|
| SumpSense-24i | [`sumpsense-24i/`](sumpsense-24i/) | 2 × ATtiny1616 | I²C, Seeed-kompatibel |
| SumpSense-16z | [`sumpsense-16z/`](sumpsense-16z/) | ESP32-H2 | Zigbee 3.0, Gieß-Automatik |

Gebaut wird mit `arduino-cli` (oder der Arduino IDE). Die Tests der Logik laufen ohne Hardware auf dem PC (`gcc`, `python3`, für den Zigbee2MQTT-Konverter `node`).

---

## SumpSense-24i (I²C)

Eine Firmware für beide ATtiny1616. Am Bus verhält sie sich wie die Firmware des [Seeed Grove Water Level Sensor](https://wiki.seeedstudio.com/Grove-Water-Level-Sensor/), sodass die Seeed-Demo ([`examples/water-level-sensor-demo.ino`](../examples/water-level-sensor-demo.ino)) und Bibliotheken dafür ohne Änderung laufen.

### Vorbild

Seeed hat die Firmware nicht selbst veröffentlicht. Der Quelltext liegt im ersten Commit von [jenskeiner/water_level](https://github.com/jenskeiner/water_level/tree/f253825) (Atmel-START-Projekt mit QTouch). Daraus übernommen:

| Punkt | Seeed-Original | SumpSense-24i |
|-------|----------------|---------------|
| I²C-Pins | TWI0 auf PA1 (SDA) / PA2 (SCL), `PORTMUX.CTRLB` TWI0 | gleich (`Wire.swap(1)`, im Maschinencode `ori 0x10` auf 0x0201) |
| Adressen | U1 0x78 (oben), U2 0x77 (unten) | gleich; Auswahl über PA3 (U1: GND, U2: VCC), ein Image für beide |
| Daten | ein Byte je Stufe, 0 = trocken | gleich; nass = 0xFF (Demo: > 100 nass, Werkstest 250–255) |
| Stufen je Chip | U1 12, U2 8 | 12 und 12 |
| Kanalfolge | Y7, Y8, Y9, Y6, Y5, Y4, Y13, Y12, Y3, Y2, Y1, Y0 | gleich (PC1, PC2, PC3, PC0, PB0, PB1, PB4, PB5, PA7, PA6, PA5, PA4), Byte 0 = Stufe an der Spitze |
| Messung | QTouch Self-Cap, 20 ms, Filter 16, Gain 1 | PTC-Bibliothek aus megaTinyCore, gleiche Werte |
| Erkennung | Schwelle 20, Hysterese 25 %, 4 Messungen | Schwelle 20, aus bei 15, 4 Messungen |
| Drift | 4 s zur Berührung, 1 s zurück, Dauerberührung ohne Zeitlimit | 200 / 50 Messungen à 20 ms, `touched_max_nom` aus |
| Lesezeiger | läuft bei 12 auf 0 | gleich; beginnt bei jedem Lesezugriff ohne Schreiben bei 0 |

Abweichungen mit Absicht:

- Im Seeed-Quelltext wird `read_flag` nie erhöht; jedes Byte wäre Kanal 0. Hier zählt der Zeiger je Byte weiter.
- Das Original sendet für eine nasse Stufe das untere Byte des 16-Bit-Signals; das kann ≤ 100 sein und wäre für die Demo dann „trocken“. Hier immer 0xFF.
- Zusätzliche Register, nur erreichbar nach einem Schreibzugriff (Registeradresse). Ein Master, der nie schreibt (Seeed-Demo), sieht nur das Seeed-Format.

| Register | Inhalt |
|----------|--------|
| 0x00 | 12 × uint8 Seeed-Format |
| 0x10 | 12 × uint16 LE Rohwert (wie Community-Firmware [jenskeiner 0.9.0](https://github.com/jenskeiner/water_level)) |
| 0x28 | 12 × int16 LE Rohwert − Referenz |
| 0x40 | 12 × uint16 LE Referenz |
| 0x58 | uint16 LE Maske nasser Stufen, 0x5A uint8 Level (nasse Stufen ab der Spitze) |
| 0x60 | Info: `'S' 'S'` Version Major, Minor, Kanäle, Adresse |
| 0x7F | Kommando schreiben: `0xCA` = alle Stufen neu kalibrieren (Stab trocken) |

**Achtung beim Original-Demo-Sketch:** Er liest von 0x77 nur 8 Bytes. Bis 8 Stufen (40 mm) stimmt der Wert, darüber fehlen ihm E16–E13. Für 24 Stufen von beiden Adressen je 12 Bytes lesen, Füllstand = nasse Stufen am Stück ab 0x77 Byte 0, weiter mit 0x78 Byte 0, × 5 mm.

Wie das Original kalibriert die Firmware beim Einschalten: Steht der Stab dabei im Wasser, gelten die nassen Stufen als Referenz. Abhilfe am Master: Rohwerte (0x10) mit festen Schwellen auswerten oder bei trockenem Stab `0xCA` senden.

### Bauen

[megaTinyCore](https://github.com/SpenceKonde/megaTinyCore) 2.6.x (Boardverwalter-URL `https://drazzy.com/package_drazzy.com_index.json`):

```bash
arduino-cli compile -b megaTinyCore:megaavr:atxy6:chip=1616,clock=10internal --output-dir sumpsense-24i/build sumpsense-24i
```

10 MHz, damit die Chips auch an 3,3 V innerhalb der Datenblattgrenzen laufen. Ergebnis: rund 3,9 KB Flash, 474 Byte RAM. Das fertige Image liegt als [`sumpsense-24i/sumpsense-24i.hex`](sumpsense-24i/sumpsense-24i.hex) bei.

### Prüfen

```bash
python3 sumpsense-24i/test/run_tests.py
```

105 Prüfungen: Die Auswertung aus der Seeed-Demo (`check()`, Schwelle 100, Werkstest 250–255) läuft wörtlich gegen zwei simulierte Chips, für jeden Wasserstand von 0 bis 24 Stufen. Dazu die Wiederholung nach 12 Bytes, der Neustart bei Byte 0 und alle Zusatzregister.

### Flashen (Adafruit UPDI Friend)

GND und VCC vom UPDI Friend an GND/VCC, UPDI nacheinander an **U1** und **U2**. I²C dabei nicht angeschlossen, nur eine Spannungsquelle. Beide Chips bekommen dasselbe Image.

```bash
UPDI_PORT=/dev/ttyACM0 ./flash.sh u1
UPDI_PORT=/dev/ttyACM0 ./flash.sh u2
```

---

## SumpSense-16z (Zigbee)

Zigbee-3.0-Router auf dem ESP32-H2 (Arduino-ESP32 3.3 mit Espressif-Zigbee-SDK). Nur Standard-Cluster der Zigbee Cluster Library, kein herstellereigener Cluster:

| Endpoint | Cluster | Bedeutung |
|----------|---------|-----------|
| 1 | Analog Input (0x000C) | Wasserstand 0–80 mm, Raster 5 mm |
| 2 | On/Off (0x0006), Gerätetyp Steckdose | Ventil |
| 3 | On/Off (0x0006), Gerätetyp Steckdose | Gieß-Automatik an/aus |
| 4 | Analog Output (0x000D) | Untere Schwelle (Ventil auf) |
| 5 | Analog Output (0x000D) | Obere Schwelle (Ventil zu) |
| 6 | Binary Input (0x000F) | Störung |
| 1 | OTA Upgrade (0x0019) | Firmware-Update über Zigbee |

### Gieß-Automatik

Die Automatik öffnet das Ventil, wenn der Wasserstand auf die untere Schwelle fällt, und schließt es, sobald die obere erreicht ist (Zweipunktregler). Schwellen 5–80 mm im 5-mm-Raster, die untere liegt immer mindestens eine Stufe unter der oberen (wird beim Setzen korrigiert und zurückgemeldet). Die Einstellungen bleiben im Flash erhalten.

Sicherheit:

- Ventil höchstens 10 min am Stück offen, dann zu und **Störung**. Die Automatik bleibt gesperrt, bis Ventil oder Automatik von Hand geschaltet werden.
- Oberste Stufe nass (80 mm): Ventil zu, auch im Handbetrieb.
- Messfehler (Timeout, nasse Stufe über einer trockenen): Ventil zu, Störung.

### Messung

Der H2 hat keinen Touch-Sensor. Jede Elektrode hängt über 100 kΩ am GPIO. Gemessen wird die Ladezeit bis zur Schaltschwelle in CPU-Takten (Median aus 5), relativ zu einer trockenen Referenz je Stufe: nass ab +30 %, trocken unter +15 %. Die Referenz wird beim ersten Start (Stab trocken!) aufgenommen und im Trockenen langsam nachgeführt. GPIO8/GPIO9 (E11/E10) laden über ihre 1-MΩ-Strap-Widerstände und werden nie auf High getrieben, weil an GPIO9 der Taster liegt. Einzelheiten in [`sumpsense-16z/ss_sense.h`](sumpsense-16z/ss_sense.h). Die Schwellen sind Startwerte und am fertigen Stab zu prüfen (serielle Ausgabe über USB).

### Taster SW1

| Drücken | Wirkung |
|---------|---------|
| kurz | Werte sofort senden; ohne Netz: Netzsuche neu starten |
| 3 s | Trocken-Kalibrierung (Stab muss trocken sein) |
| 6 s | Netz verlassen und neu pairen |
| 12 s | Werksreset (Zigbee-Daten und Einstellungen) |
| beim Einschalten | Download-Modus für den ersten Flash |

Ein neues Gerät sucht nach dem Einschalten von selbst ein offenes Netz: am Koordinator „Gerät hinzufügen“ bzw. „Permit join“ starten.

### Einbinden

| System | Weg | Was erscheint |
|--------|-----|---------------|
| **Home Assistant, ZHA** | direkt | Sensor „Wasserstand“, zwei Schalter (Ventil, Automatik), zwei Zahlen „Untere/Obere Schwelle“, Binärsensor „Stoerung“. ZHA benennt Analog- und Binär-Endpoints nach dem Beschreibungsattribut. |
| **Home Assistant, Zigbee2MQTT** | Konverter [`sumpsense-16z/z2m/sumpsense-16z.mjs`](sumpsense-16z/z2m/sumpsense-16z.mjs) nach `data/external_converters/` | wie unten im Screenshot |
| **Google Home** | über Home Assistant (Google-Assistant-Integration oder Matter-Bridge) | Ventil und Automatik als Schalter; Sprachbefehle „Ventil an/aus“ |
| **Tuya Smart / Smart Life** | Tuya-Zigbee-Gateway, Gerät als generisches Zigbee-3.0-Gerät | sicher: die beiden On/Off-Endpoints (Steckdosen-Gerätetyp). Analogwerte zeigt die Tuya-App bei Fremdgeräten meist nicht an; Tuya-zertifizierte Datenpunkte (Cluster 0xEF00) bräuchten eine Tuya-Produkt-ID. Über die Tuya-App lässt sich das Ventil dann auch mit Google Home koppeln. |

Ehrlich gesagt: Vollständig (Wasserstand und Schwellen) ist das Gerät in Home Assistant nutzbar, über ZHA oder Zigbee2MQTT. Tuya und Google Home sehen vor allem die Schalter.

### Home Assistant (Zigbee2MQTT)

Screenshots entstehen in einer echten Home-Assistant-Instanz (Docker), in der das Gerät per MQTT-Discovery so angelegt wird, wie Zigbee2MQTT es mit dem Konverter tut. Statt der Hardware läuft der Simulator [`sumpsense-16z/ha/sim.mjs`](sumpsense-16z/ha/sim.mjs) mit derselben Regelung wie die Firmware; [`sumpsense-16z/ha/screenshots.mjs`](sumpsense-16z/ha/screenshots.mjs) richtet MQTT und das Dashboard „Bewässerung“ ein (Wasserstand als Tacho, Ventil, Automatik, Schwellen mit +/−, Störung, Verlauf) und speichert `ha-dashboard-light.png`, `ha-dashboard-dark.png` und `ha-geraet.png` in `sumpsense-16z/ha/`.

```bash
cd sumpsense-16z/ha            # Docker Desktop muss laufen
docker compose up -d           # Mosquitto + Home Assistant, siehe docker-compose.yml
node sim.mjs mqtt://localhost:1883 900 &
node screenshots.mjs .         # nach ein paar Minuten, damit der Verlauf Daten hat
```

**Stand:** Die Screenshots fehlen noch. Docker Desktop startete auf dem Entwicklungsrechner nicht (Absturz beim Anlegen der Unix-Sockets unter `%LOCALAPPDATA%\Docker\run`).

### Bauen

[Arduino-ESP32](https://github.com/espressif/arduino-esp32) 3.3.x:

```bash
arduino-cli compile -b "esp32:esp32:esp32h2:ZigbeeMode=zczr,PartitionScheme=zigbee_zczr,CDCOnBoot=cdc" --output-dir sumpsense-16z/build sumpsense-16z
```

Rund 755 KB (57 % der App-Partition), 36 KB RAM. Die Partition „Zigbee ZCZR 4MB“ braucht einen H2 mit 4 MB Flash im Gehäuse (ESP32-H2FH4).

### Prüfen

```bash
python3 sumpsense-16z/test/run_tests.py
cd sumpsense-16z/z2m && npm install zigbee-herdsman-converters && node test_converter.mjs
```

49 Prüfungen der Logik (Schwellen, Raster, Hysterese, Laufzeitgrenze, Überlauf, Sensorfehler, Handbetrieb) und 12 Prüfungen des Konverters mit der echten `zigbee-herdsman-converters`: Exposes, Zigbee → MQTT für alle sechs Endpoints und MQTT → Zigbee (Schwellen schreiben, Ventil und Automatik schalten).

### Flashen

Erster Flash über USB an J3, siehe [`../hardware/sumpsense-16z/README.md`](../hardware/sumpsense-16z/README.md#flashen) (SW1 beim Einschalten halten):

```bash
arduino-cli upload -b "esp32:esp32:esp32h2:ZigbeeMode=zczr,PartitionScheme=zigbee_zczr,CDCOnBoot=cdc" -p /dev/ttyACM0 sumpsense-16z
```

Danach geht es ohne Taster über USB oder per OTA über Zigbee2MQTT.

### Nicht geprüft

Keine Firmware lief bisher auf echter Hardware. Geprüft sind: Übersetzen mit den Original-Toolchains, die Logik auf dem PC und der Konverter mit der Z2M-Bibliothek. Die Home-Assistant-Screenshots stehen noch aus (siehe oben). Offen: Messwerte am echten Stab (Schwellen der Elektrodenmessung, PTC-Werte), Funkreichweite, Pairing an ZHA, Z2M und Tuya-Gateway.

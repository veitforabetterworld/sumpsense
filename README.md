# SumpSense

Kapazitive Füllstandssensoren für 14,5-mm-Rohr: ein schmaler Stab mit Elektroden im 5-mm-Raster, Elektronik am trockenen Ende. Die erste Variante ist eine 14-mm-Fassung des [Seeed Grove Water Level Sensor](https://wiki.seeedstudio.com/Grove-Water-Level-Sensor/).

## Varianten

Name = **SumpSense-** + Zahl der Stufen + Schnittstelle (`z` Zigbee, `i` I²C).

<table>
  <tr>
    <th>SumpSense-24i (I²C)</th>
    <th>SumpSense-16z (Zigbee)</th>
  </tr>
  <tr>
    <td><img src="hardware/sumpsense-24i/preview/3d.png" alt="SumpSense-24i, 3D-Ansicht" width="240"></td>
    <td><img src="hardware/sumpsense-16z/preview/3d.png" alt="SumpSense-16z, 3D-Ansicht" width="240"></td>
  </tr>
</table>

- **SumpSense-24i**: 24 Stufen, zwei ATtiny1616, I²C über sechs Lötlöcher. Platine, Flashen, Betrieb: [`hardware/sumpsense-24i/README.md`](hardware/sumpsense-24i/README.md)
- **SumpSense-16z**: 16 Stufen, ESP32-H2 mit Zigbee 3.0, Ventilausgang und Gieß-Automatik (untere/obere Schwelle), Pairing-Taster: [`hardware/sumpsense-16z/README.md`](hardware/sumpsense-16z/README.md)
- Firmware für beide Platinen (Seeed-kompatibles I²C, Zigbee mit Home Assistant, Zigbee2MQTT, Tuya, Google Home), Tests und Home-Assistant-Screenshots: [`firmware/README.md`](firmware/README.md)
- Seeed-Demo zum Testen der 24i am I²C-Bus: [`examples/water-level-sensor-demo.ino`](examples/water-level-sensor-demo.ino) (liest von 0x77 nur 8 Stufen, siehe Firmware-README)
- Fertigungsdaten für JLCPCB je Platine in `hardware/<platine>/jlcpcb/`, erzeugt mit [`hardware/jlcpcb.py`](hardware/jlcpcb.py)

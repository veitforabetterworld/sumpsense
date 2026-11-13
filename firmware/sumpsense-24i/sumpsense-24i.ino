/*
 * SumpSense-24i: Firmware für beide ATtiny1616 (U1 und U2), ein Image.
 *
 * Verhält sich am I2C-Bus wie die Seeed-Firmware des Grove Water Level
 * Sensor (Quelle: github.com/jenskeiner/water_level, Commit f253825
 * "add source code", WaterLevel_u1_driver):
 *   - TWI0 auf den Alternativ-Pins PA1 (SDA) / PA2 (SCL), PORTMUX.CTRLB TWI0
 *   - Adresse 0x78 (U1) bzw. 0x77 (U2)
 *   - je Stufe ein Byte, 0 = nicht berührt, sonst Wert > 100
 *   - QTouch-Einstellungen: Self-Cap, 20 ms Messperiode, 16-fach Filter,
 *     Gain 1, Schwelle 20, Hysterese 25 %, Erkennung nach 4 Messungen,
 *     Drift 4 s (Richtung Berührung) / 1 s (Gegenrichtung), keine
 *     Zwangskalibrierung bei Dauerberührung (MAX_ON_DURATION 0)
 * Kanalreihenfolge wie Seeed U1 (Y7, Y8, Y9, Y6, Y5, Y4, Y13, Y12, Y3, Y2,
 * Y1, Y0), Byte 0 = Stufe an der Spitze dieses Chips.
 *
 * Unterschiede zum Original:
 *   - Ein Image für beide Chips: PA3 wählt die Adresse (GND = U1 0x78,
 *     VCC = U2 0x77), auf der Platine fest verdrahtet.
 *   - U2 hat 12 statt 8 Stufen.
 *   - Der Lesezeiger zählt je Byte weiter. Im Seeed-Quelltext wird read_flag
 *     nie erhöht (jedes Byte wäre Kanal 0).
 *   - Zusätzliche Register (Rohwerte, Delta, Referenz, Maske, Level, Info,
 *     Neukalibrierung), nur erreichbar nach einem Schreibzugriff. Siehe
 *     ss_protocol.h.
 *
 * Bauen: megaTinyCore 2.6.x, ATtiny1616, 10 MHz intern (läuft ab 2,7 V),
 * millis an. Siehe ../README.md.
 */
#include <Wire.h>
#include <ptc.h>
#include "ss_protocol.h"

#if !defined(__AVR_ATtiny1616__)
#error "Board: megaTinyCore ATtiny1616 wählen"
#endif
#if defined(MILLIS_USE_TIMERNONE)
#error "millis() wird für die PTC-Messperiode gebraucht"
#endif

/* Pins in Byte-Reihenfolge (Spitze zuerst). Auf der Platine:
 * U1: PC1=E12 ... PA4=E1,  U2: PC1=E24 ... PA4=E13 */
static const uint8_t CHANNEL_PINS[SS_CHANNELS] = {
  PIN_PC1, PIN_PC2, PIN_PC3, PIN_PC0, PIN_PB0, PIN_PB1,
  PIN_PB4, PIN_PB5, PIN_PA7, PIN_PA6, PIN_PA5, PIN_PA4
};

/* QTouch-Werte aus touch.h des Originals */
#define MEASUREMENT_PERIOD_MS  20      /* DEF_TOUCH_MEASUREMENT_PERIOD_MS */
#define TOUCH_THRESHOLD        20      /* KEY_x_PARAMS: 20 */
#define TOUCH_HYSTERESIS_PCT   25      /* HYST_25 */
#define DET_INTEGRATION        4       /* DEF_TOUCH_DET_INT */
#define TCH_DRIFT_MS           4000    /* DEF_TCH_DRIFT_RATE 20 x 200 ms */
#define ANTI_TCH_DRIFT_MS      1000    /* DEF_ANTI_TCH_DRIFT_RATE 5 x 200 ms */
#define OVERSAMPLES_LOG2       4       /* FILTER_LEVEL_16 */

static cap_sensor_t nodes[SS_CHANNELS];
static ss_data_t live;        /* nach jeder Messrunde aktualisiert */
static ss_bus_t bus;
static volatile uint8_t command;

static void onReceive(int n) {
  uint8_t buf[4];
  uint8_t len = 0;
  while (Wire.available()) {
    uint8_t b = Wire.read();
    if (len < sizeof(buf)) {
      buf[len++] = b;
    }
  }
  (void)n;
  ss_on_write(&bus, buf, len);
  if (bus.pending_cmd) {
    command = bus.pending_cmd;
    bus.pending_cmd = 0;
  }
}

static void onRequest(void) {
  /* Wire puffert; der Master liest so viele Bytes, wie er will. */
  uint8_t out[2 * SS_CHANNELS];
  uint8_t n = ss_on_read(&bus, &live, out, sizeof(out));
  Wire.write(out, n);
}

void ptc_event_cb_conversion(const ptc_cb_event_t eventType, cap_sensor_t *node) {
  (void)node;
  if (!(eventType & PTC_CB_EVENT_CONV_TYPE_CMPL_MSK)) {
    return;
  }
  ss_data_t next = live;
  for (uint8_t i = 0; i < SS_CHANNELS; i++) {
    cap_sensor_t *nd = &nodes[i];
    next.touched[i] = ptc_get_node_touched(nd) ? 1 : 0;
    next.signal[i] = ptc_get_node_sensor_value(nd);
    next.delta[i] = ptc_get_node_delta(nd);
    next.reference[i] = nd->reference;
  }
  uint8_t sreg = SREG;
  cli();                      /* TWI-ISR liest live */
  live = next;
  SREG = sreg;
}

void setup() {
  /* Adresswahl über PA3: auf U1 an GND, auf U2 an VCC */
  pinMode(PIN_PA3, INPUT);
  memset(&live, 0, sizeof(live));
  live.address = digitalRead(PIN_PA3) ? SS_ADDR_U2 : SS_ADDR_U1;
  ss_bus_init(&bus);

  ptc_lib_sm_set_t *sm = ptc_get_sm_settings();
  sm->touched_detect_nom = DET_INTEGRATION;
  sm->untouched_detect_nom = DET_INTEGRATION;
  sm->touched_max_nom = 0xFF;                              /* aus, wie MAX_ON_DURATION 0 */
  sm->drift_up_nom = TCH_DRIFT_MS / MEASUREMENT_PERIOD_MS;      /* 200 */
  sm->drift_down_nom = ANTI_TCH_DRIFT_MS / MEASUREMENT_PERIOD_MS; /* 50 */
  /* Messperiode: die Bibliothek startet alle 20 ms (acqPeriod = 20) */

  for (uint8_t i = 0; i < SS_CHANNELS; i++) {
    ptc_add_selfcap_node(&nodes[i], 0, PIN_TO_PTC(CHANNEL_PINS[i]));
    ptc_node_set_oversamples(&nodes[i], OVERSAMPLES_LOG2);
    ptc_node_set_thresholds(&nodes[i], TOUCH_THRESHOLD,
                            TOUCH_THRESHOLD * (100 - TOUCH_HYSTERESIS_PCT) / 100);
  }

  Wire.swap(1);               /* TWI0 auf PA1/PA2 (PORTMUX.CTRLB TWI0 = 1) */
  Wire.begin(live.address);
  Wire.onReceive(onReceive);
  Wire.onRequest(onRequest);
}

void loop() {
  ptc_process(millis());
  if (command == SS_CMD_RECALIBRATE) {
    command = 0;
    for (uint8_t i = 0; i < SS_CHANNELS; i++) {
      ptc_node_request_recal(&nodes[i]);
    }
  }
}

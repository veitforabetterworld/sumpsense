/*
 * SumpSense-16z: Zigbee-3.0-Füllstandssensor mit Gieß-Automatik (ESP32-H2).
 *
 * Zigbee-Router (Netzteil 5 V), nur Standard-Cluster aus der ZCL:
 *   EP 1  Analog Input   "Wasserstand"     0..80 mm, Raster 5 mm
 *   EP 2  On/Off (Steckdose)  Ventil       Magnetventil an GPIO0
 *   EP 3  On/Off (Steckdose)  Automatik    Gieß-Automatik an/aus
 *   EP 4  Analog Output  "Untere Schwelle" Ventil auf bei Stand <= Wert
 *   EP 5  Analog Output  "Obere Schwelle"  Ventil zu bei Stand >= Wert
 *   EP 6  Binary Input   "Stoerung"        Laufzeit überschritten / Sensorfehler
 * Dazu OTA-Client (Cluster 0x0019) auf EP 1.
 *
 * Pairing JP1 PAIR (GPIO9):
 *   kurz      Werte sofort senden; ohne Netz: Pairing neu starten
 *   3 s       Trocken-Kalibrierung (Stab muss trocken sein)
 *   6 s       Netz verlassen und neu pairen
 *   12 s      Werksreset (Zigbee und Einstellungen)
 *
 * Bauen: Arduino-ESP32 3.3.x, Board "ESP32H2 Dev Module",
 *   Zigbee mode: Zigbee ZCZR (coordinator/router),
 *   Partition Scheme: Zigbee ZCZR 4MB with spiffs, USB CDC On Boot: Enabled.
 * Siehe ../README.md.
 */
#ifndef ZIGBEE_MODE_ZCZR
#error "Zigbee mode: Zigbee ZCZR (coordinator/router) wählen"
#endif

#include <Zigbee.h>
#include <Preferences.h>
#include "ss_logic.h"
#include "ss_sense.h"

#define FW_VERSION      0x01000000          /* 1.0.0 */
#define FW_DATE         "2026-11-13"
#define MEASURE_MS      1000
#define BTN_CALIBRATE_MS 3000
#define BTN_REJOIN_MS   6000
#define BTN_RESET_MS    12000

ZigbeeAnalog      zbLevel(1);
ZigbeePowerOutlet zbValve(2);
ZigbeePowerOutlet zbAuto(3);
ZigbeeAnalog      zbLower(4);
ZigbeeAnalog      zbUpper(5);
ZigbeeBinary      zbFault(6);

static Preferences prefs;
static ss_cfg_t  cfg;
static ss_ctrl_t ctrl;
static uint32_t  ref[SS_STAGES];          /* trockene Referenz je Stufe */
static uint32_t  raw[SS_STAGES];
static bool      wet[SS_STAGES];
static int16_t   level_mm = -1;
static bool      have_ref = false;
static volatile bool cfg_dirty = false;
static volatile bool report_now = false;

/* ------------------------------------------------------------ Einstellungen */
static void cfg_load() {
  ss_cfg_default(&cfg);
  cfg.lower_mm = prefs.getUShort("lower", cfg.lower_mm);
  cfg.upper_mm = prefs.getUShort("upper", cfg.upper_mm);
  cfg.auto_on = prefs.getBool("auto", cfg.auto_on);
  cfg.max_run_s = prefs.getUShort("maxrun", cfg.max_run_s);
  ss_cfg_sanitize(&cfg);
  have_ref = prefs.getBytes("ref", ref, sizeof(ref)) == sizeof(ref);
}

static void cfg_save() {
  prefs.putUShort("lower", cfg.lower_mm);
  prefs.putUShort("upper", cfg.upper_mm);
  prefs.putBool("auto", cfg.auto_on);
  prefs.putUShort("maxrun", cfg.max_run_s);
}

static void calibrate_dry() {
  uint32_t acc[SS_STAGES] = {0};
  const int n = 8;
  for (int k = 0; k < n; k++) {
    uint32_t v[SS_STAGES];
    ss_sense_all(v);
    for (int i = 0; i < SS_STAGES; i++) acc[i] += (v[i] == SS_SENSE_TIMEOUT) ? 0 : v[i];
    delay(50);
  }
  for (int i = 0; i < SS_STAGES; i++) {
    ref[i] = acc[i] / n;
    wet[i] = false;
  }
  prefs.putBytes("ref", ref, sizeof(ref));
  have_ref = true;
  Serial.println("Trocken-Kalibrierung gespeichert");
}

/* ------------------------------------------------------------ Zigbee-Rückrufe */
static void onValve(bool on) {
  ss_ctrl_manual(&ctrl, on, millis());
}

static void onAuto(bool on) {
  cfg.auto_on = on;
  ctrl.fault = SS_FAULT_NONE;
  cfg_dirty = true;
}

static void onLower(float v) {
  cfg.lower_mm = (uint16_t)(v + 0.5f);
  ss_cfg_sanitize(&cfg);
  cfg_dirty = true;
}

static void onUpper(float v) {
  cfg.upper_mm = (uint16_t)(v + 0.5f);
  ss_cfg_sanitize(&cfg);
  cfg_dirty = true;
}

/* ------------------------------------------------------------ Messung */
static void measure() {
  if (ss_button_pressed()) return;        /* E10 teilt sich den Pin mit JP1 PAIR */
  uint8_t timeouts = ss_sense_all(raw);
  if (ss_button_pressed()) return;
  if (!have_ref) calibrate_dry();         /* erster Start: trocken annehmen */
  for (int i = 0; i < SS_STAGES; i++) {
    bool w = raw[i] != SS_SENSE_TIMEOUT && ss_stage_wet(raw[i], ref[i], wet[i]);
    /* Referenz langsam nachführen, nur im Trockenen */
    if (!w && raw[i] != SS_SENSE_TIMEOUT) {
      if (raw[i] < ref[i]) ref[i] = (ref[i] * 7 + raw[i]) / 8;
      else ref[i] += (raw[i] - ref[i]) / 64;
    }
    wet[i] = w;
  }
  bool gap;
  uint8_t steps = ss_level_steps(wet, &gap);
  level_mm = (timeouts || gap) ? -1 : (int16_t)(steps * SS_STEP_MM);
}

static void publish() {
  if (!Zigbee.connected()) return;
  zbLevel.setAnalogInput(level_mm < 0 ? 0 : level_mm);
  zbLevel.reportAnalogInput();
  zbValve.setState(ctrl.valve);
  zbAuto.setState(cfg.auto_on);
  zbFault.setBinaryInput(ctrl.fault != SS_FAULT_NONE);
  zbFault.reportBinaryInput();
}

/* ------------------------------------------------------------ Taster */
static void button_task() {
  static uint32_t down_since = 0;
  static bool down = false;
  bool p = ss_button_pressed();
  uint32_t now = millis();
  if (p && !down) { down = true; down_since = now; }
  if (!p && down) {
    down = false;
    uint32_t held = now - down_since;
    if (held >= BTN_RESET_MS) {
      Serial.println("Werksreset");
      prefs.clear();
      Zigbee.factoryReset();              /* startet neu */
    } else if (held >= BTN_REJOIN_MS) {
      Serial.println("Netz verlassen, neu pairen");
      Zigbee.factoryReset();
    } else if (held >= BTN_CALIBRATE_MS) {
      calibrate_dry();
    } else if (held >= 50) {
      if (Zigbee.connected()) report_now = true;
      else ESP.restart();                 /* Netzsuche neu starten */
    }
  }
}

/* ------------------------------------------------------------ Setup / Loop */
void setup() {
  Serial.begin(115200);                   /* USB Serial/JTAG, nicht UART0 (GPIO23/24 sind Stufen) */
  pinMode(SS_GPIO_VALVE, OUTPUT);
  digitalWrite(SS_GPIO_VALVE, LOW);
  ss_sense_begin();
  prefs.begin("sumpsense", false);
  cfg_load();

  zbLevel.setManufacturerAndModel("SumpSense", "SumpSense-16z");
  zbLevel.setVersion(1);
  zbLevel.setPowerSource(ZB_POWER_SOURCE_MAINS);
  zbLevel.addAnalogInput();
  zbLevel.setAnalogInputDescription("Wasserstand");
  zbLevel.setAnalogInputResolution(SS_STEP_MM);
  zbLevel.setAnalogInputMinMax(0, SS_MAX_MM);
  // Hardware-Version und Image-Typ je Platine, damit OTA nur passende Images annimmt
#if SS_BOARD == 2
  zbLevel.addOTAClient(FW_VERSION, FW_VERSION, 2, 0x1001, 0x1012);
#else
  zbLevel.addOTAClient(FW_VERSION, FW_VERSION, 1, 0x1001, 0x1011);
#endif

  zbValve.setManufacturerAndModel("SumpSense", "SumpSense-16z");
  zbValve.onPowerOutletChange(onValve);
  zbAuto.setManufacturerAndModel("SumpSense", "SumpSense-16z");
  zbAuto.onPowerOutletChange(onAuto);

  zbLower.setManufacturerAndModel("SumpSense", "SumpSense-16z");
  zbLower.addAnalogOutput();
  zbLower.setAnalogOutputDescription("Untere Schwelle");
  zbLower.setAnalogOutputResolution(SS_STEP_MM);
  zbLower.setAnalogOutputMinMax(SS_STEP_MM, SS_MAX_MM);
  zbLower.onAnalogOutputChange(onLower);

  zbUpper.setManufacturerAndModel("SumpSense", "SumpSense-16z");
  zbUpper.addAnalogOutput();
  zbUpper.setAnalogOutputDescription("Obere Schwelle");
  zbUpper.setAnalogOutputResolution(SS_STEP_MM);
  zbUpper.setAnalogOutputMinMax(SS_STEP_MM, SS_MAX_MM);
  zbUpper.onAnalogOutputChange(onUpper);

  zbFault.setManufacturerAndModel("SumpSense", "SumpSense-16z");
  zbFault.addBinaryInput();
  zbFault.setBinaryInputDescription("Stoerung");

  Zigbee.addEndpoint(&zbLevel);
  Zigbee.addEndpoint(&zbValve);
  Zigbee.addEndpoint(&zbAuto);
  Zigbee.addEndpoint(&zbLower);
  Zigbee.addEndpoint(&zbUpper);
  Zigbee.addEndpoint(&zbFault);

  if (!Zigbee.begin(ZIGBEE_ROUTER)) {
    Serial.println("Zigbee-Start fehlgeschlagen, Neustart");
    delay(1000);
    ESP.restart();
  }
  /* Startwerte der Schwellen ins Netz geben */
  zbLower.setAnalogOutput(cfg.lower_mm);
  zbUpper.setAnalogOutput(cfg.upper_mm);
  zbAuto.setState(cfg.auto_on);
  zbLevel.setAnalogInputReporting(1, 300, SS_STEP_MM - 1);
}

void loop() {
  static uint32_t last_measure = 0, last_publish = 0;
  static bool last_valve = false, last_auto = false;
  static ss_fault_t last_fault = SS_FAULT_NONE;
  uint32_t now = millis();

  button_task();

  if (now - last_measure >= MEASURE_MS) {
    last_measure = now;
    measure();
    bool v = ss_ctrl_step(&ctrl, &cfg, level_mm, now);
    digitalWrite(SS_GPIO_VALVE, v ? HIGH : LOW);
    Serial.printf("Stand %d mm, Ventil %s, Auto %s, Schwellen %u/%u, Fehler %d\n",
                  level_mm, v ? "auf" : "zu", cfg.auto_on ? "an" : "aus",
                  cfg.lower_mm, cfg.upper_mm, ctrl.fault);
  }

  if (cfg_dirty) {
    cfg_dirty = false;
    cfg_save();
    if (Zigbee.connected()) {               /* bereinigte Werte zurückmelden */
      zbLower.setAnalogOutput(cfg.lower_mm);
      zbUpper.setAnalogOutput(cfg.upper_mm);
      zbLower.reportAnalogOutput();
      zbUpper.reportAnalogOutput();
    }
  }

  bool changed = ctrl.valve != last_valve || cfg.auto_on != last_auto || ctrl.fault != last_fault;
  if (changed || report_now || now - last_publish >= 60000) {
    last_valve = ctrl.valve;
    last_auto = cfg.auto_on;
    last_fault = ctrl.fault;
    report_now = false;
    last_publish = now;
    publish();
  }
  delay(20);
}

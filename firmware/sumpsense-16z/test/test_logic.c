/* Host-Test für ss_logic.c. Bauen und starten: python test/run_tests.py */
#include <stdio.h>
#include <string.h>
#include "../ss_logic.h"

static int failures = 0, checks = 0;
#define CHECK(c, ...) do { checks++; if (!(c)) { failures++; printf("FEHLER %s:%d: ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

static void water(bool wet[SS_STAGES], int steps) {
  for (int i = 0; i < SS_STAGES; i++) wet[i] = i >= SS_STAGES - steps;   /* E16 = wet[15] zuerst */
}

int main(void) {
  /* --- Konfiguration */
  ss_cfg_t cfg;
  ss_cfg_default(&cfg);
  ss_cfg_sanitize(&cfg);
  CHECK(cfg.lower_mm == 20 && cfg.upper_mm == 60, "Standardwerte");
  cfg.lower_mm = 63; cfg.upper_mm = 41; ss_cfg_sanitize(&cfg);
  CHECK(cfg.upper_mm == 40 && cfg.lower_mm == 35, "untere unter obere gezogen, Raster 5 mm: %u/%u", cfg.lower_mm, cfg.upper_mm);
  cfg.lower_mm = 0; cfg.upper_mm = 999; ss_cfg_sanitize(&cfg);
  CHECK(cfg.lower_mm == 5 && cfg.upper_mm == 80, "Grenzen 5..80");
  cfg.lower_mm = 5; cfg.upper_mm = 5; ss_cfg_sanitize(&cfg);
  CHECK(cfg.upper_mm == 10 && cfg.lower_mm == 5, "mindestens eine Stufe Abstand");

  /* --- Stufe nass mit Hysterese */
  CHECK(!ss_stage_wet(100, 100, false), "gleich Referenz = trocken");
  CHECK(!ss_stage_wet(125, 100, false), "+25 %% noch trocken");
  CHECK(ss_stage_wet(130, 100, false), "+30 %% nass");
  CHECK(ss_stage_wet(120, 100, true), "nass bleibt bis +15 %%");
  CHECK(!ss_stage_wet(114, 100, true), "unter +15 %% trocken");
  CHECK(!ss_stage_wet(14, 10, false), "Mindestabstand 8 Zähler");
  CHECK(!ss_stage_wet(50, 0, false), "ohne Referenz nie nass");

  /* --- Füllstand */
  bool wet[SS_STAGES], gap;
  for (int s = 0; s <= SS_STAGES; s++) {
    water(wet, s);
    CHECK(ss_level_steps(wet, &gap) == s && !gap, "Stufen %d", s);
  }
  water(wet, 3); wet[5] = true;           /* Tropfen an E06 */
  CHECK(ss_level_steps(wet, &gap) == 3 && gap, "Lücke erkannt");

  /* --- Automatik mit Hysterese */
  ss_ctrl_t c; memset(&c, 0, sizeof(c));
  ss_cfg_default(&cfg); cfg.auto_on = true; cfg.lower_mm = 20; cfg.upper_mm = 60; cfg.max_run_s = 600;
  uint32_t t = 0;
  CHECK(!ss_ctrl_step(&c, &cfg, 40, t), "zwischen den Schwellen: zu");
  CHECK(ss_ctrl_step(&c, &cfg, 20, t += 1000), "<= unterer Schwelle: auf");
  CHECK(ss_ctrl_step(&c, &cfg, 35, t += 1000), "steigt: bleibt auf");
  CHECK(ss_ctrl_step(&c, &cfg, 55, t += 1000), "unter oberer: bleibt auf");
  CHECK(!ss_ctrl_step(&c, &cfg, 60, t += 1000), ">= oberer Schwelle: zu");
  CHECK(!ss_ctrl_step(&c, &cfg, 45, t += 1000), "fällt: bleibt zu");
  CHECK(!ss_ctrl_step(&c, &cfg, 25, t += 1000), "über unterer: bleibt zu");
  CHECK(ss_ctrl_step(&c, &cfg, 15, t += 1000), "unter unterer: wieder auf");

  /* --- Laufzeitgrenze */
  uint32_t start = t;
  CHECK(ss_ctrl_step(&c, &cfg, 15, start + 599000), "vor Ablauf auf");
  CHECK(!ss_ctrl_step(&c, &cfg, 15, start + 600000) && c.fault == SS_FAULT_TIMEOUT, "nach 600 s zu, Fehler");
  CHECK(!ss_ctrl_step(&c, &cfg, 10, start + 700000), "Fehler sperrt Automatik");
  ss_ctrl_manual(&c, false, start + 700000);
  CHECK(c.fault == SS_FAULT_NONE, "Handbedienung löscht Fehler");
  CHECK(ss_ctrl_step(&c, &cfg, 10, start + 701000), "danach Automatik wieder aktiv");

  /* --- Sensorfehler und Überlauf */
  CHECK(!ss_ctrl_step(&c, &cfg, -1, t += 1000) && c.fault == SS_FAULT_SENSOR, "ungültige Messung: zu");
  CHECK(ss_ctrl_step(&c, &cfg, 10, t += 1000) && c.fault == SS_FAULT_NONE, "Sensor wieder gut: Automatik läuft");
  ss_ctrl_manual(&c, true, t);
  CHECK(!ss_ctrl_step(&c, &cfg, SS_MAX_MM, t += 1000), "Überlauf: zu, auch von Hand");

  /* --- Handbetrieb ohne Automatik */
  memset(&c, 0, sizeof(c)); cfg.auto_on = false;
  CHECK(!ss_ctrl_step(&c, &cfg, 5, t += 1000), "ohne Automatik bleibt zu");
  ss_ctrl_manual(&c, true, t);
  CHECK(ss_ctrl_step(&c, &cfg, 30, t += 1000), "von Hand auf");
  CHECK(ss_ctrl_step(&c, &cfg, 70, t += 1000), "ohne Automatik keine obere Schwelle");
  CHECK(!ss_ctrl_step(&c, &cfg, 70, t + 600000) && c.fault == SS_FAULT_TIMEOUT, "Laufzeitgrenze auch von Hand");

  printf("%d Prüfungen, %d Fehler\n", checks, failures);
  return failures ? 1 : 0;
}

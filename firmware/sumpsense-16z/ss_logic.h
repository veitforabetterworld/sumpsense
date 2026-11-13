/*
 * SumpSense-16z: Stufenauswertung und Gieß-Automatik.
 * Reines C ohne Hardwarezugriff, getestet mit test/test_logic.c.
 */
#ifndef SS_LOGIC_H
#define SS_LOGIC_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SS_STAGES        16     /* E01 (an MAX) .. E16 (Spitze) */
#define SS_STEP_MM       5      /* Stufenabstand */
#define SS_MAX_MM        (SS_STAGES * SS_STEP_MM)   /* 80 mm */

/* Eine Stufe gilt als nass, wenn die Ladezeit um mindestens WET_PCT Prozent
 * und WET_MIN Zähler über der trockenen Referenz liegt. Zurück auf trocken
 * erst unter DRY_PCT (Hysterese). */
#define SS_WET_PCT       30
#define SS_DRY_PCT       15
#define SS_WET_MIN       8

typedef struct {
  uint16_t lower_mm;      /* Ventil auf, wenn Wasserstand <= lower */
  uint16_t upper_mm;      /* Ventil zu, wenn Wasserstand >= upper */
  bool     auto_on;       /* Gieß-Automatik an */
  uint16_t max_run_s;     /* Sicherheit: Ventil höchstens so lange am Stück offen */
} ss_cfg_t;

typedef enum {
  SS_FAULT_NONE = 0,
  SS_FAULT_TIMEOUT,       /* max_run_s überschritten, obere Schwelle nicht erreicht */
  SS_FAULT_SENSOR,        /* Messung ungültig (Lücke in den Stufen, Timeout) */
} ss_fault_t;

typedef struct {
  bool       valve;       /* Ventil offen */
  bool       manual;      /* von Hand geöffnet */
  ss_fault_t fault;
  uint32_t   on_since_ms;
} ss_ctrl_t;

/* Grenzen und Raster: 5..80 mm im 5-mm-Raster, untere mindestens eine Stufe
 * unter der oberen, max_run_s 10..3600 s. */
void ss_cfg_sanitize(ss_cfg_t *cfg);
void ss_cfg_default(ss_cfg_t *cfg);

/* Stufe nass? prev = bisheriger Zustand (Hysterese). */
bool ss_stage_wet(uint32_t value, uint32_t reference, bool prev);

/* Füllstand in Stufen: nasse Stufen am Stück ab der Spitze (wet[15] = E16).
 * Ist darüber noch eine Stufe nass (Lücke), wird *gap gesetzt. */
uint8_t ss_level_steps(const bool wet[SS_STAGES], bool *gap);

/* Ein Regelschritt. Rückgabe: Ventil offen. level_mm < 0 = Messung ungültig. */
bool ss_ctrl_step(ss_ctrl_t *c, const ss_cfg_t *cfg, int16_t level_mm, uint32_t now_ms);

/* Von Hand schalten (Zigbee On/Off auf dem Ventil). Setzt einen Fehler zurück. */
void ss_ctrl_manual(ss_ctrl_t *c, bool on, uint32_t now_ms);

#ifdef __cplusplus
}
#endif
#endif

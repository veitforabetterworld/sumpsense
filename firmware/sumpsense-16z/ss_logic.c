#include "ss_logic.h"

static uint16_t clamp_mm(uint16_t v) {
  if (v < SS_STEP_MM) v = SS_STEP_MM;
  if (v > SS_MAX_MM) v = SS_MAX_MM;
  return (uint16_t)(((v + SS_STEP_MM / 2) / SS_STEP_MM) * SS_STEP_MM);
}

void ss_cfg_default(ss_cfg_t *cfg) {
  cfg->lower_mm = 20;
  cfg->upper_mm = 60;
  cfg->auto_on = false;
  cfg->max_run_s = 600;
}

void ss_cfg_sanitize(ss_cfg_t *cfg) {
  cfg->lower_mm = clamp_mm(cfg->lower_mm);
  cfg->upper_mm = clamp_mm(cfg->upper_mm);
  if (cfg->upper_mm < 2 * SS_STEP_MM) cfg->upper_mm = 2 * SS_STEP_MM;
  if (cfg->lower_mm + SS_STEP_MM > cfg->upper_mm) cfg->lower_mm = cfg->upper_mm - SS_STEP_MM;
  if (cfg->max_run_s < 10) cfg->max_run_s = 10;
  if (cfg->max_run_s > 3600) cfg->max_run_s = 3600;
}

bool ss_stage_wet(uint32_t value, uint32_t reference, bool prev) {
  if (reference == 0) return false;
  uint32_t pct = prev ? SS_DRY_PCT : SS_WET_PCT;
  if (value <= reference) return false;
  uint32_t d = value - reference;
  if (!prev && d < SS_WET_MIN) return false;
  return d * 100u >= reference * pct;
}

uint8_t ss_level_steps(const bool wet[SS_STAGES], bool *gap) {
  uint8_t n = 0;
  while (n < SS_STAGES && wet[SS_STAGES - 1 - n]) n++;
  bool g = false;
  for (uint8_t i = n + 1; i < SS_STAGES; i++) {
    if (wet[SS_STAGES - 1 - i]) g = true;
  }
  if (gap) *gap = g;
  return n;
}

static void valve_set(ss_ctrl_t *c, bool on, uint32_t now_ms) {
  if (on && !c->valve) c->on_since_ms = now_ms;
  c->valve = on;
}

void ss_ctrl_manual(ss_ctrl_t *c, bool on, uint32_t now_ms) {
  c->fault = SS_FAULT_NONE;
  c->manual = on;
  valve_set(c, on, now_ms);
}

bool ss_ctrl_step(ss_ctrl_t *c, const ss_cfg_t *cfg, int16_t level_mm, uint32_t now_ms) {
  if (level_mm < 0) {                       /* Messung ungültig: sicher zu */
    c->fault = SS_FAULT_SENSOR;
    c->manual = false;
    valve_set(c, false, now_ms);
    return c->valve;
  }
  if (c->fault == SS_FAULT_SENSOR) c->fault = SS_FAULT_NONE;

  /* Überlauf: oberste Stufe nass -> immer zu, auch bei Handbetrieb */
  if (level_mm >= SS_MAX_MM) {
    c->manual = false;
    valve_set(c, false, now_ms);
    return c->valve;
  }

  if (cfg->auto_on && c->fault == SS_FAULT_NONE) {
    if (!c->valve && level_mm <= (int16_t)cfg->lower_mm) {
      valve_set(c, true, now_ms);
    } else if (c->valve && level_mm >= (int16_t)cfg->upper_mm) {
      c->manual = false;
      valve_set(c, false, now_ms);
    }
  } else if (!c->manual) {
    valve_set(c, false, now_ms);
  }

  /* Sicherheit: Laufzeit begrenzen */
  if (c->valve && (uint32_t)(now_ms - c->on_since_ms) >= (uint32_t)cfg->max_run_s * 1000u) {
    c->fault = SS_FAULT_TIMEOUT;
    c->manual = false;
    valve_set(c, false, now_ms);
  }
  return c->valve;
}

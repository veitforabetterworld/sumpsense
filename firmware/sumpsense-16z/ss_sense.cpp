#include "ss_sense.h"
#include <Arduino.h>
#include "driver/gpio.h"
#include "hal/gpio_ll.h"
#include "esp_cpu.h"
#include "esp_rom_sys.h"

#if SS_BOARD == 2
/* v2: Reihenfolge folgt der Modul-Pinbelegung (Leitungen ohne Kreuzung) */
const uint8_t SS_STAGE_GPIO[SS_STAGES] = {
  10, 11, 8, 9, 22, 25, 23, 24, 5, 4, 12, 14, 13, 1, 3, 2
};
#else
const uint8_t SS_STAGE_GPIO[SS_STAGES] = {
  11, 12, 13, 14, 22, 23, 24, 25, 10, 9, 8, 5, 4, 3, 2, 1
};
#endif

#define HW            (&GPIO)
#define CYCLES_PER_US (CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ)
#define DISCHARGE_US  20
#define SETTLE_CYC    (2 * CYCLES_PER_US)      /* Pin-Kapazität gleicht sich an */
#define PULSE_MAX_CYC (60 * CYCLES_PER_US)     /* längster Ladepuls 60 µs */
#define RELEASE_TO_CYC (400 * CYCLES_PER_US)   /* GPIO8/9: Timeout 400 µs */
#define SAMPLES       5

static portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;

static inline bool pulled_up(uint8_t p) { return p == 8 || p == 9; }

static inline void drive_low(uint8_t p) {
  gpio_ll_set_level(HW, p, 0);
  gpio_ll_output_enable(HW, p);
}

void ss_sense_begin(void) {
  for (uint8_t i = 0; i < SS_STAGES; i++) {
    uint8_t p = SS_STAGE_GPIO[i];
    gpio_reset_pin((gpio_num_t)p);
    gpio_config_t c = {};
    c.pin_bit_mask = 1ULL << p;
    c.mode = GPIO_MODE_INPUT_OUTPUT;
    c.pull_up_en = GPIO_PULLUP_DISABLE;
    c.pull_down_en = GPIO_PULLDOWN_DISABLE;
    c.intr_type = GPIO_INTR_DISABLE;
    gpio_config(&c);
    if (pulled_up(p)) {
      gpio_ll_output_disable(HW, p);     /* Ruhe: losgelassen, Pull-up lädt */
    } else {
      drive_low(p);                      /* Ruhe: entladen */
    }
  }
}

/* normale Pins: liest nach einem Ladepuls von t Takten High? */
static bool pulse_probe(uint8_t p, uint32_t t) {
  drive_low(p);
  esp_rom_delay_us(DISCHARGE_US);
  portENTER_CRITICAL(&mux);
  uint32_t s = esp_cpu_get_cycle_count();
  gpio_ll_set_level(HW, p, 1);
  while ((uint32_t)(esp_cpu_get_cycle_count() - s) < t) {
  }
  gpio_ll_output_disable(HW, p);
  s = esp_cpu_get_cycle_count();
  while ((uint32_t)(esp_cpu_get_cycle_count() - s) < SETTLE_CYC) {
  }
  bool high = gpio_ll_get_level(HW, p);
  portEXIT_CRITICAL(&mux);
  drive_low(p);
  return high;
}

static uint32_t measure_pulse(uint8_t p) {
  uint32_t lo = 0, hi = PULSE_MAX_CYC;
  if (!pulse_probe(p, hi)) return SS_SENSE_TIMEOUT;
  while (hi - lo > 2) {
    uint32_t mid = (lo + hi) / 2;
    if (pulse_probe(p, mid)) hi = mid; else lo = mid;
  }
  return hi;
}

/* GPIO8/9: entladen, loslassen, Takte bis High */
static uint32_t measure_release(uint8_t p) {
  drive_low(p);
  esp_rom_delay_us(DISCHARGE_US);
  uint32_t dt = SS_SENSE_TIMEOUT;
  portENTER_CRITICAL(&mux);
  uint32_t s = esp_cpu_get_cycle_count();
  gpio_ll_output_disable(HW, p);
  while (true) {
    uint32_t e = esp_cpu_get_cycle_count() - s;
    if (gpio_ll_get_level(HW, p)) { dt = e; break; }
    if (e > RELEASE_TO_CYC) break;
  }
  portEXIT_CRITICAL(&mux);
  return dt;                              /* Pin bleibt losgelassen */
}

static uint32_t median5(uint32_t *v) {
  for (int i = 1; i < SAMPLES; i++) {
    uint32_t x = v[i];
    int j = i - 1;
    while (j >= 0 && v[j] > x) { v[j + 1] = v[j]; j--; }
    v[j + 1] = x;
  }
  return v[SAMPLES / 2];
}

uint8_t ss_sense_all(uint32_t out[SS_STAGES]) {
  uint8_t timeouts = 0;
  for (uint8_t i = 0; i < SS_STAGES; i++) {
    uint8_t p = SS_STAGE_GPIO[i];
    uint32_t v[SAMPLES];
    for (int k = 0; k < SAMPLES; k++) {
      v[k] = pulled_up(p) ? measure_release(p) : measure_pulse(p);
    }
    out[i] = median5(v);
    if (out[i] == SS_SENSE_TIMEOUT) timeouts++;
  }
  return timeouts;
}

bool ss_button_pressed(void) {
  return !gpio_ll_get_level(HW, SS_GPIO_BUTTON);
}

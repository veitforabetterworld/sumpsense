/*
 * Host-Test für ss_protocol.c: prüft das I2C-Verhalten gegen die Seeed-Demo
 * (examples/water-level-sensor-demo.ino, Funktion check()) und gegen das
 * Registermodell. Bauen und starten: python test/run_tests.py
 */
#include <stdio.h>
#include <string.h>
#include "../ss_protocol.h"

static int failures = 0, checks = 0;
#define CHECK(c, ...) do { checks++; if (!(c)) { failures++; printf("FEHLER %s:%d: ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

/* ---- zwei Chips am Bus ----------------------------------------------- */
typedef struct { ss_data_t d; ss_bus_t bus; } chip_t;
static chip_t u1, u2;

static chip_t *chip_at(uint8_t addr) {
  return addr == SS_ADDR_U1 ? &u1 : addr == SS_ADDR_U2 ? &u2 : NULL;
}
/* Wire.requestFrom(addr, n) */
static void request_from(uint8_t addr, uint8_t *out, uint8_t n) {
  chip_t *c = chip_at(addr);
  uint8_t buf[2 * SS_CHANNELS];
  uint8_t got = ss_on_read(&c->bus, &c->d, buf, sizeof(buf));
  for (uint8_t i = 0; i < n; i++) {
    out[i] = i < got ? buf[i] : 0xFF;   /* Wire sendet 0xFF, wenn der Puffer leer ist */
  }
}
/* Wire.beginTransmission(addr); Wire.write(...); Wire.endTransmission() */
static void write_to(uint8_t addr, const uint8_t *b, uint8_t n) {
  chip_t *c = chip_at(addr);
  ss_on_write(&c->bus, b, n);
}

/* Wasser bis zur Stufe h (0..24, ab der Spitze). U2 trägt E24..E13
 * (Byte 0 = E24), U1 trägt E12..E1 (Byte 0 = E12). */
static void set_water(int h) {
  for (int i = 0; i < SS_CHANNELS; i++) {
    u2.d.touched[i] = i < h;
    u1.d.touched[i] = i < h - SS_CHANNELS;
  }
}

/* ---- Seeed-Demo check(), wörtlich übernommen bis auf die Zahl der Bytes */
#define THRESHOLD 100
static int seeed_demo_level(int low_n, int high_n, int *pass_low, int *pass_high) {
  unsigned char low_data[12] = {0}, high_data[12] = {0};
  request_from(SS_ADDR_U2, low_data, (uint8_t)low_n);   /* getLow8SectionValue */
  request_from(SS_ADDR_U1, high_data, (uint8_t)high_n); /* getHigh12SectionValue */
  int low_count = 0, high_count = 0;
  for (int i = 0; i < low_n; i++) if (low_data[i] >= 250 && low_data[i] <= 255) low_count++;
  for (int i = 0; i < high_n; i++) if (high_data[i] >= 250 && high_data[i] <= 255) high_count++;
  *pass_low = low_count == low_n;
  *pass_high = high_count == high_n;
  uint32_t touch_val = 0;
  for (int i = 0; i < low_n; i++) if (low_data[i] > THRESHOLD) touch_val |= (uint32_t)1 << i;
  for (int i = 0; i < high_n; i++) if (high_data[i] > THRESHOLD) touch_val |= (uint32_t)1 << (low_n + i);
  int trig_section = 0;
  while (touch_val & 0x01) { trig_section++; touch_val >>= 1; }
  return trig_section;
}

int main(void) {
  memset(&u1, 0, sizeof(u1));
  memset(&u2, 0, sizeof(u2));
  u1.d.address = SS_ADDR_U1;
  u2.d.address = SS_ADDR_U2;
  ss_bus_init(&u1.bus);
  ss_bus_init(&u2.bus);
  int pl, ph;

  /* 1. Seeed-Werte: trocken 0, nass > THRESHOLD und im Werkstest-Fenster */
  CHECK(SS_COMPAT_DRY == 0, "trocken muss 0 sein");
  CHECK(SS_COMPAT_WET > THRESHOLD && SS_COMPAT_WET >= 250, "nass muss > 100 und >= 250 sein");

  /* 2. Füllstand über alle 24 Stufen mit der Demo-Logik, 2 x 12 Bytes */
  for (int h = 0; h <= 24; h++) {
    set_water(h);
    int lv = seeed_demo_level(12, 12, &pl, &ph);
    CHECK(lv == h, "24i: Wasser %d Stufen, Demo-Logik meldet %d", h, lv);
    CHECK(lv * 5 == h * 5, "Höhe in mm");
  }

  /* 3. Original-Demo (8 Bytes von 0x77, 12 von 0x78) ist bis 8 Stufen korrekt;
   *    darüber fehlen ihr die Stufen E16..E13 (U2 Byte 8..11). */
  for (int h = 0; h <= 24; h++) {
    set_water(h);
    int lv = seeed_demo_level(8, 12, &pl, &ph);
    int expect = h <= 8 ? h : (h <= 12 ? 8 : 8 + (h - 12));
    if (h > 8 && h <= 12) expect = 8;
    CHECK(lv == expect, "Original-Demo: Wasser %d, erwartet %d, gemeldet %d", h, expect, lv);
  }

  /* 4. Werkstest der Demo: alle Stufen nass -> PASS auf beiden Chips */
  set_water(24);
  seeed_demo_level(8, 12, &pl, &ph);
  CHECK(pl && ph, "Werkstest (250..255) muss bei voll nassem Stab bestehen");
  set_water(0);
  seeed_demo_level(8, 12, &pl, &ph);
  CHECK(!pl && !ph, "Werkstest darf trocken nicht bestehen");

  /* 5. Wiederholung nach 12 Bytes wie im Original (read_flag >= CHAN_CNT -> 0) */
  set_water(5);
  {
    uint8_t b[24];
    request_from(SS_ADDR_U2, b, 24);
    CHECK(memcmp(b, b + 12, 12) == 0, "Seeed-Block wiederholt sich nach 12 Bytes");
    CHECK(b[4] == SS_COMPAT_WET && b[5] == SS_COMPAT_DRY, "Byte 4 nass, Byte 5 trocken");
  }

  /* 6. Jeder Lesezugriff ohne Schreiben beginnt bei Byte 0 */
  {
    uint8_t a[3], b[12];
    request_from(SS_ADDR_U2, a, 3);
    request_from(SS_ADDR_U2, b, 12);
    CHECK(b[0] == SS_COMPAT_WET && b[4] == SS_COMPAT_WET && b[5] == SS_COMPAT_DRY, "Neustart bei Byte 0");
  }

  /* 7. Rohwerte: 12 x uint16 little endian (gleiches Format wie die
   *    Community-Firmware jenskeiner/water_level 0.9.0) */
  for (int i = 0; i < SS_CHANNELS; i++) {
    u2.d.signal[i] = (uint16_t)(500 + 37 * i);
    u2.d.reference[i] = (uint16_t)(510 + i);
    u2.d.delta[i] = (int16_t)(u2.d.signal[i] - u2.d.reference[i]);
  }
  {
    uint8_t r = SS_REG_SIGNAL, b[24];
    write_to(SS_ADDR_U2, &r, 1);
    request_from(SS_ADDR_U2, b, 24);
    for (int i = 0; i < SS_CHANNELS; i++) {
      uint16_t v = (uint16_t)(b[2 * i] | (b[2 * i + 1] << 8));
      CHECK(v == u2.d.signal[i], "Rohwert %d: %u statt %u", i, v, u2.d.signal[i]);
    }
    r = SS_REG_DELTA;
    write_to(SS_ADDR_U2, &r, 1);
    request_from(SS_ADDR_U2, b, 24);
    CHECK((int16_t)(b[0] | (b[1] << 8)) == -10, "Delta Kanal 0 = -10");
    r = SS_REG_REFERENCE;
    write_to(SS_ADDR_U2, &r, 1);
    request_from(SS_ADDR_U2, b, 2);
    CHECK((b[0] | (b[1] << 8)) == 510, "Referenz Kanal 0");
    /* Zeiger fällt nach dem Lesen auf den Seeed-Block zurück */
    request_from(SS_ADDR_U2, b, 12);
    CHECK(b[0] == SS_COMPAT_WET && b[11] == SS_COMPAT_DRY, "Zeiger nach Lesen zurück auf 0x00");
  }

  /* 8. Maske, Level, Info */
  set_water(14);
  {
    uint8_t r = SS_REG_MASK, b[3];
    write_to(SS_ADDR_U1, &r, 1);
    request_from(SS_ADDR_U1, b, 3);
    CHECK(b[0] == 0x03 && b[1] == 0x00, "U1 Maske 0x0003");
    CHECK(b[2] == 2, "U1 Level 2");
    write_to(SS_ADDR_U2, &r, 1);
    request_from(SS_ADDR_U2, b, 3);
    CHECK(b[0] == 0xFF && b[1] == 0x0F && b[2] == 12, "U2 Maske 0x0FFF, Level 12");
    uint8_t info[6];
    r = SS_REG_INFO;
    write_to(SS_ADDR_U1, &r, 1);
    request_from(SS_ADDR_U1, info, 6);
    CHECK(info[0] == 'S' && info[1] == 'S' && info[4] == 12 && info[5] == 0x78, "Info U1");
  }

  /* 9. Kommando Neukalibrierung */
  {
    uint8_t c[2] = {SS_REG_COMMAND, SS_CMD_RECALIBRATE};
    write_to(SS_ADDR_U1, c, 2);
    CHECK(u1.bus.pending_cmd == SS_CMD_RECALIBRATE, "Kommando gemerkt");
    CHECK(u1.bus.pointer == SS_REG_COMPAT, "Zeiger nach Kommando auf 0x00");
  }

  /* 10. Unbekanntes Register liefert 0xFF, Zeiger außerhalb -> Seeed-Block */
  {
    uint8_t r = 0x7E, b[1];
    write_to(SS_ADDR_U1, &r, 1);
    request_from(SS_ADDR_U1, b, 1);
    CHECK(b[0] == 0xFF, "unbelegtes Register 0xFF");
    r = 0xF0;
    write_to(SS_ADDR_U1, &r, 1);
    CHECK(u1.bus.pointer == SS_REG_COMPAT, "Zeiger >= 0x80 -> 0x00");
  }

  printf("%d Prüfungen, %d Fehler\n", checks, failures);
  return failures ? 1 : 0;
}

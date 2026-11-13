/*
 * SumpSense-24i: I2C-Registermodell eines ATtiny1616 (U1 oder U2).
 *
 * Reines C ohne Hardwarezugriff, damit es auf dem PC getestet werden kann
 * (siehe test/test_protocol.c). Die Firmware (sumpsense-24i.ino) füllt
 * ss_data_t aus der PTC-Messung und beantwortet I2C-Zugriffe hiermit.
 *
 * Kompatibel zum Seeed Grove Water Level Sensor: Ein Lesezugriff ohne
 * vorheriges Schreiben liefert ab Byte 0 je Stufe ein Byte, 0 = trocken,
 * > 100 = nass (Seeed-Demo: THRESHOLD 100). Nach dem 12. Byte beginnt die
 * Folge von vorn, wie im Original (read_flag läuft bei CHAN_CNT auf 0).
 */
#ifndef SS_PROTOCOL_H
#define SS_PROTOCOL_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SS_CHANNELS      12      /* Stufen je Chip */
#define SS_ADDR_U1       0x78    /* trockenes Ende, E1-E12  (Seeed: ATTINY1_HIGH_ADDR) */
#define SS_ADDR_U2       0x77    /* Spitze, E13-E24         (Seeed: ATTINY2_LOW_ADDR)  */

#define SS_FW_MAJOR      1
#define SS_FW_MINOR      0

/* Wert im Seeed-Block für eine nasse Stufe. Die Seeed-Demo wertet > 100 als
 * nass und prüft im Werkstest 250..255. Das Original sendet hier das untere
 * Byte des QTouch-Signals; 0xFF erfüllt beide Prüfungen sicher. */
#define SS_COMPAT_WET    0xFF
#define SS_COMPAT_DRY    0x00

/* Register (Zeiger per I2C-Schreibzugriff setzen, dann lesen) */
#define SS_REG_COMPAT    0x00    /* 12 x uint8: Seeed-Format, Byte 0 = Stufe an der Spitze */
#define SS_REG_SIGNAL    0x10    /* 12 x uint16 LE: Rohwert (PTC, 512 = Mitte) */
#define SS_REG_DELTA     0x28    /* 12 x int16 LE: Rohwert - Referenz */
#define SS_REG_REFERENCE 0x40    /* 12 x uint16 LE: Referenz (driftet) */
#define SS_REG_MASK      0x58    /* uint16 LE: Bit n = Stufe n nass */
#define SS_REG_LEVEL     0x5A    /* uint8: nasse Stufen am Stück ab Byte 0 */
#define SS_REG_INFO      0x60    /* 'S','S',Major,Minor,Kanäle,Adresse */
#define SS_REG_COMMAND   0x7F    /* schreiben: SS_CMD_* */
#define SS_REG_END       0x80

#define SS_CMD_RECALIBRATE 0xCA  /* alle Stufen neu kalibrieren (trocken!) */

typedef struct {
  uint8_t  address;                   /* eigene I2C-Adresse */
  uint8_t  touched[SS_CHANNELS];      /* 1 = nass */
  uint16_t signal[SS_CHANNELS];
  int16_t  delta[SS_CHANNELS];
  uint16_t reference[SS_CHANNELS];
} ss_data_t;

typedef struct {
  uint8_t pointer;        /* aktuelles Register */
  uint8_t pending_cmd;    /* zuletzt geschriebenes Kommando, 0 = keins */
} ss_bus_t;

void    ss_bus_init(ss_bus_t *bus);

/* Ein Byte aus dem virtuellen Registerraum. Im Seeed-Block wird der Index
 * modulo SS_CHANNELS genommen (Wiederholung wie im Original). */
uint8_t ss_reg_byte(const ss_data_t *d, uint8_t addr);

/* Schreibzugriff des Masters: erstes Byte setzt den Zeiger, weitere Bytes
 * an SS_REG_COMMAND werden als Kommando gemerkt. */
void    ss_on_write(ss_bus_t *bus, const uint8_t *buf, uint8_t len);

/* Lesezugriff des Masters: füllt out mit bis zu max Bytes ab dem Zeiger und
 * setzt den Zeiger danach auf den Seeed-Block zurück. Gibt die Anzahl
 * zurück. */
uint8_t ss_on_read(ss_bus_t *bus, const ss_data_t *d, uint8_t *out, uint8_t max);

/* Nasse Stufen am Stück, beginnend bei Byte 0 (Spitze dieses Chips). */
uint8_t ss_level(const ss_data_t *d);

#ifdef __cplusplus
}
#endif
#endif

/*
 * SumpSense-16z: Kapazitätsmessung der 16 Elektroden am ESP32-H2.
 *
 * Der H2 hat keinen Touch-Sensor. Jede Elektrode hängt über 100 kΩ an einem
 * GPIO; gemessen wird die Zeit, bis die Elektrode die Schaltschwelle des
 * Eingangs erreicht (t ≈ 0,7 · R · C). Wasser vor der Elektrode erhöht C und
 * damit die Zeit.
 *
 *  - normale Pins: entladen (Low), dann für t Takte High treiben, hochohmig
 *    schalten, 2 µs warten, Pegel lesen. t wird per Intervallhalbierung
 *    gesucht (kürzestes t, bei dem High gelesen wird).
 *  - GPIO8, GPIO9 (1 MΩ Pull-up, GPIO9 mit Taster nach GND): nie High
 *    treiben. Entladen, loslassen, Takte bis High zählen (Laden über den
 *    Pull-up). Bleibt GPIO9 Low, ist der Taster gedrückt.
 *
 * Ergebnis in CPU-Takten (96 MHz). Die Werte der beiden Verfahren haben
 * verschiedene Skalen; ausgewertet wird nur relativ zur Referenz je Stufe.
 */
#ifndef SS_SENSE_H
#define SS_SENSE_H

#include <stdint.h>
#include "ss_logic.h"

#define SS_SENSE_TIMEOUT 0xFFFFFFFFu

/* GPIO je Stufe, Index 0 = E01 (an MAX) ... 15 = E16 (Spitze) */
extern const uint8_t SS_STAGE_GPIO[SS_STAGES];
#define SS_GPIO_BUTTON 9
#define SS_GPIO_VALVE  0

void     ss_sense_begin(void);
/* misst alle Stufen (Median aus 5), gibt die Zahl der Timeouts zurück */
uint8_t  ss_sense_all(uint32_t out[SS_STAGES]);
/* JP1 PAIR kurz? (GPIO9 liest Low, wenn PAIR geschlossen) */
bool     ss_button_pressed(void);

#endif

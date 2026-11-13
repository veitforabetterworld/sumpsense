#include "ss_protocol.h"

void ss_bus_init(ss_bus_t *bus) {
  bus->pointer = SS_REG_COMPAT;
  bus->pending_cmd = 0;
}

static uint8_t le_byte(uint16_t v, uint8_t hi) {
  return hi ? (uint8_t)(v >> 8) : (uint8_t)v;
}

uint8_t ss_level(const ss_data_t *d) {
  uint8_t n = 0;
  while (n < SS_CHANNELS && d->touched[n]) {
    n++;
  }
  return n;
}

uint8_t ss_reg_byte(const ss_data_t *d, uint8_t addr) {
  if (addr < SS_REG_SIGNAL) {
    uint8_t i = addr % SS_CHANNELS;
    return d->touched[i] ? SS_COMPAT_WET : SS_COMPAT_DRY;
  }
  if (addr < SS_REG_SIGNAL + 2 * SS_CHANNELS) {
    uint8_t o = addr - SS_REG_SIGNAL;
    return le_byte(d->signal[o >> 1], o & 1);
  }
  if (addr >= SS_REG_DELTA && addr < SS_REG_DELTA + 2 * SS_CHANNELS) {
    uint8_t o = addr - SS_REG_DELTA;
    return le_byte((uint16_t)d->delta[o >> 1], o & 1);
  }
  if (addr >= SS_REG_REFERENCE && addr < SS_REG_REFERENCE + 2 * SS_CHANNELS) {
    uint8_t o = addr - SS_REG_REFERENCE;
    return le_byte(d->reference[o >> 1], o & 1);
  }
  if (addr == SS_REG_MASK || addr == SS_REG_MASK + 1) {
    uint16_t m = 0;
    for (uint8_t i = 0; i < SS_CHANNELS; i++) {
      if (d->touched[i]) {
        m |= (uint16_t)1 << i;
      }
    }
    return le_byte(m, addr - SS_REG_MASK);
  }
  if (addr == SS_REG_LEVEL) {
    return ss_level(d);
  }
  switch (addr) {
    case SS_REG_INFO + 0: return 'S';
    case SS_REG_INFO + 1: return 'S';
    case SS_REG_INFO + 2: return SS_FW_MAJOR;
    case SS_REG_INFO + 3: return SS_FW_MINOR;
    case SS_REG_INFO + 4: return SS_CHANNELS;
    case SS_REG_INFO + 5: return d->address;
    default: return 0xFF;
  }
}

void ss_on_write(ss_bus_t *bus, const uint8_t *buf, uint8_t len) {
  if (len == 0) {
    return;
  }
  bus->pointer = buf[0] < SS_REG_END ? buf[0] : SS_REG_COMPAT;
  if (bus->pointer == SS_REG_COMMAND && len >= 2) {
    bus->pending_cmd = buf[1];
    bus->pointer = SS_REG_COMPAT;
  }
}

uint8_t ss_on_read(ss_bus_t *bus, const ss_data_t *d, uint8_t *out, uint8_t max) {
  uint8_t p = bus->pointer;
  for (uint8_t i = 0; i < max; i++) {
    out[i] = ss_reg_byte(d, p);
    /* im Seeed-Block endlos weiterzählen (modulo), sonst linear bis zum Ende */
    p = (p < SS_REG_SIGNAL) ? (uint8_t)((p + 1) % SS_CHANNELS) : (uint8_t)(p + 1);
  }
  bus->pointer = SS_REG_COMPAT;
  return max;
}

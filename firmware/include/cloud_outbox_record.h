#pragma once
#include "wire_protocol.h"

struct MeasuredDrink {
  uint32_t bootHigh, bootLow, sequence;
  uint16_t volumeMl;
};

struct CloudOutboxRecord {
  Packet telemetry;
  MeasuredDrink drink;

  CloudOutboxRecord(Packet packet = {}, MeasuredDrink measured = {})
      : telemetry(packet), drink(measured) {}

  bool isDrink() const { return drink.volumeMl != 0; }

  static void encodeRecord(const CloudOutboxRecord &record, uint8_t *bytes) {
    if (!record.isDrink()) {
      encode(record.telemetry, false, bytes);
      return;
    }
    // Storage-only record type. UART rejects it and legacy telemetry bytes
    // remain unchanged. The outer durable record supplies the checksum.
    std::memset(bytes, 0, FRAME_SIZE);
    bytes[0] = 0x4b; bytes[1] = 0x57; bytes[2] = 1; bytes[3] = 3;
    put32(bytes + 4, record.drink.bootHigh);
    put32(bytes + 8, record.drink.bootLow);
    put32(bytes + 12, record.drink.sequence);
    bytes[16] = uint8_t(record.drink.volumeMl);
    bytes[17] = uint8_t(record.drink.volumeMl >> 8);
  }

  static bool decodeRecord(const uint8_t *bytes, CloudOutboxRecord &record) {
    record = {};
    if (bytes[3] != 3) {
      bool ack = false;
      return decode(bytes, record.telemetry, ack) && !ack;
    }
    if (bytes[0] != 0x4b || bytes[1] != 0x57 || bytes[2] != 1 || bytes[18] || bytes[19]) return false;
    const uint16_t volume = uint16_t(bytes[16]) | (uint16_t(bytes[17]) << 8);
    record.drink = {get32(bytes + 4), get32(bytes + 8), get32(bytes + 12), volume};
    return record.drink.sequence && volume >= 10 && volume <= 1000;
  }

  static bool sameId(const CloudOutboxRecord &a, const CloudOutboxRecord &b) {
    if (a.isDrink() != b.isDrink()) return false;
    if (a.isDrink()) {
      return a.drink.bootHigh == b.drink.bootHigh && a.drink.bootLow == b.drink.bootLow &&
             a.drink.sequence == b.drink.sequence;
    }
    return a.telemetry.node == b.telemetry.node && a.telemetry.session == b.telemetry.session &&
           a.telemetry.seq == b.telemetry.seq;
  }
};

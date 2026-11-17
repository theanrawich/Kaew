#pragma once
#include <Arduino.h>
#include "wire_protocol.h"
#ifndef KAEW_PACKET_TRACE_ENABLED
#define KAEW_PACKET_TRACE_ENABLED 0
#endif
#if KAEW_PACKET_TRACE_ENABLED && defined(KAEW_PUMP_COMMISSIONED) && KAEW_PUMP_COMMISSIONED
#error "Packet measurement trace builds must keep physical pump output disabled"
#endif

// Optional measurement only. Drop rather than wait for console space; any
// dropped trace invalidates PDR evidence. The UART wire protocol is unchanged.
class PacketTrace {
  uint32_t dropped_ = 0;
public:
  void emit(const char *event, const Packet &packet, uint32_t now) {
#if KAEW_PACKET_TRACE_ENABLED
    char line[112];
    const int size = snprintf(line, sizeof line, "TRACE %s %lu %u %lu %lu\n", event,
        static_cast<unsigned long>(now), static_cast<unsigned>(packet.node),
        static_cast<unsigned long>(packet.session), static_cast<unsigned long>(packet.seq));
    if (size > 0 && size < static_cast<int>(sizeof line) && Serial.availableForWrite() >= size)
      Serial.write(reinterpret_cast<const uint8_t *>(line), size);
    else ++dropped_;
#else
    (void)event; (void)packet; (void)now;
#endif
  }
  uint32_t dropped() const { return dropped_; }
};

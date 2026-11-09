#pragma once
#include <Preferences.h>
#include "durable_queue.h"

class NvsQueueStore : public SlotStore {
  Preferences prefs_;
  static void key(unsigned slot, char *out) { snprintf(out, 8, "q%02u", slot); }
public:
  bool begin() { return prefs_.begin("kaew-outbox", false); }
  int read(unsigned slot, uint8_t *out) override {
    char name[8]; key(slot,name);
    if (!prefs_.isKey(name)) return 0;
    if (prefs_.getBytesLength(name)!=DURABLE_RECORD_SIZE) return -1;
    return prefs_.getBytes(name,out,DURABLE_RECORD_SIZE)==DURABLE_RECORD_SIZE ? 1 : -1;
  }
  bool write(unsigned slot,const uint8_t *record) override {
    char name[8]; key(slot,name); return prefs_.putBytes(name,record,DURABLE_RECORD_SIZE)==DURABLE_RECORD_SIZE;
  }
  bool remove(unsigned slot) override { char name[8]; key(slot,name); return prefs_.remove(name); }
};

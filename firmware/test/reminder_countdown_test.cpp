#include "reminder_countdown.h"
#include <cassert>
#include <cstring>

int main() {
  constexpr int64_t now = 1760000000;
  constexpr int64_t received = 1000;
  auto check = [&](ReminderSnapshot snapshot, int64_t epoch, int64_t uptime,
                   const char *label, const char *digits = "") {
    auto result = reminderCountdown(snapshot, epoch, uptime);
    assert(std::strcmp(result.label, label) == 0);
    assert(std::strcmp(result.digits, digits) == 0);
  };
  check({}, now, received, "No reminder");
  check({0, received}, now, received, "No reminder");
  check({now + 1, received}, 0, received, "Clock syncing");
  check({now, received}, now, received, "Time to drink!");
  check({now - 1, received}, now, received, "Time to drink!");
  check({now + 9, received}, now, received, "Next drink", "00:09");
  check({now + 3599, received}, now, received, "Next drink", "59:59");
  check({now + 3600, received}, now, received, "Next drink", "1:00:00");
  check({now + 3610, received}, now, received + 29999, "Next drink", "1:00:10");
  check({now - 1, received}, now, received + 30000, "Offline");
  check({0, received}, 0, received + 30000, "Offline");
}

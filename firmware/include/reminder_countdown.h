#pragma once
#include <cstdint>
#include <cstdio>

constexpr int64_t CLOCK_MIN_EPOCH = 1577836800; // 2020-01-01 UTC
constexpr int64_t REMINDER_STALE_MS = 30000;

struct ReminderSnapshot {
  int64_t dueEpoch; // Zero represents a valid null response.
  int64_t receivedMs; // Negative until a valid response arrives.

  constexpr ReminderSnapshot(int64_t due = 0, int64_t received = -1)
    : dueEpoch(due), receivedMs(received) {}
};

struct ReminderCountdown {
  const char *label;
  char digits[24];

  ReminderCountdown(const char *text) : label(text), digits{} {}
};

inline ReminderCountdown reminderCountdown(ReminderSnapshot snapshot, int64_t epoch, int64_t uptimeMs) {
  if (snapshot.receivedMs >= 0 && uptimeMs - snapshot.receivedMs >= REMINDER_STALE_MS)
    return {"Offline"};
  if (snapshot.dueEpoch == 0) return {"No reminder"};
  if (epoch < CLOCK_MIN_EPOCH) return {"Clock syncing"};
  if (epoch >= snapshot.dueEpoch) return {"Time to drink!"};

  const auto remaining = static_cast<long long>(snapshot.dueEpoch - epoch);
  ReminderCountdown result{"Next drink"};
  if (remaining >= 3600)
    std::snprintf(result.digits, sizeof result.digits, "%lld:%02lld:%02lld",
                  remaining / 3600, remaining / 60 % 60, remaining % 60);
  else
    std::snprintf(result.digits, sizeof result.digits, "%02lld:%02lld",
                  remaining / 60, remaining % 60);
  return result;
}

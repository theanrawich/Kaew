#include <cassert>
#include <limits>
#include "drink_detection.h"

unsigned hold(DrinkDetector &detector, float grams, uint32_t &now, unsigned samples) {
  unsigned event = 0;
  for (unsigned i = 0; i < samples; ++i, now += 100) {
    if (const unsigned volume = detector.update(grams, now)) {
      assert(event == 0);
      event = volume;
    }
  }
  return event;
}

int main() {
  DrinkDetector detector;
  uint32_t now = 0;
  assert(!hold(detector, 0, now, 10));   // Boot with an empty platform.
  assert(!hold(detector, 400, now, 10)); // Establish initial baseline.
  assert(!hold(detector, 0, now, 2));    // Brief dip is not a lift.
  assert(!hold(detector, 380, now, 10));
  assert(!hold(detector, 100, now, 10)); // A partial lift is not a drink.
  assert(!hold(detector, 380, now, 10));
  assert(!hold(detector, -2, now, 4));
  for (unsigned i = 0; i < 12; ++i)
    assert(!hold(detector, i % 2 ? 275 : 320, now, 1));
  assert(!hold(detector, 300, now, 6));  // Still inside the settling window.
  assert(hold(detector, 301, now, 1) == 80);
  assert(!hold(detector, 300, now, 10)); // One event per lift.

  assert(!hold(detector, 0, now, 4));
  assert(!hold(detector, 520, now, 10)); // Refill becomes the new baseline.
  assert(!hold(detector, 0, now, 4));
  assert(!hold(detector, 514, now, 10)); // Below minimum plausible loss.
  assert(!hold(detector, 0, now, 4));
  assert(hold(detector, 504, now, 10) == 10);

  assert(!hold(detector, 0, now, 4));
  now += 500;                           // A disconnect breaks the lift cycle.
  assert(!hold(detector, 300, now, 10));
  assert(!hold(detector, 0, now, 4));
  assert(!hold(detector, std::numeric_limits<float>::quiet_NaN(), now, 1));
  assert(!hold(detector, 200, now, 10));

  detector.reset();
  now = UINT32_MAX - 450;
  assert(!hold(detector, 1050, now, 10));
  assert(!hold(detector, 0, now, 4));
  assert(!hold(detector, 40, now, 10));  // Above maximum plausible loss.
  assert(!hold(detector, 1100, now, 10));
  assert(!hold(detector, 0, now, 4));
  assert(hold(detector, 100, now, 10) == 1000);
}

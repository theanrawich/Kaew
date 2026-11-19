#include <cassert>
#include <cmath>
#include "boot_tared_scale.h"
#include "scale_processing.h"
#include "scale_upload.h"

int main() {
  Calibration c{};
  assert(!validCalibration(c));
  assert(makeCalibration(100000, 150000, 500, c));
  assert(validCalibration(c));
  uint8_t persisted[sizeof c]; std::memcpy(persisted, &c, sizeof c);
  Calibration restored{}; std::memcpy(&restored, persisted, sizeof restored);
  assert(validCalibration(restored)); persisted[4] ^= 1;
  std::memcpy(&restored, persisted, sizeof restored); assert(!validCalibration(restored));
  assert(std::fabs(toGrams(c, 125000) - 250) < 0.01f);
  assert(!makeCalibration(100000, 100000, 500, c));
  assert(makeCalibration(100000, 150000, 500, c));
  Calibration corrupt = c; corrupt.countsPerGram = NAN; assert(!validCalibration(corrupt));
  WeightFilter f;
  for (int n = 0; n < 4; ++n) assert(!f.push(100.0f));
  assert(f.push(100.0f)); assert(f.stable());
  f.push(500.0f); assert(!f.stable()); // A sudden jump is never considered stable.
  for (int n = 0; n < 5; ++n) f.push(200.0f);
  assert(f.stable()); assert(std::fabs(f.weight() - 200.0f) < .01f);
  CupDetector cup;
  assert(!cup.update(true, 0));
  for (int n = 0; n < 2; ++n) assert(!cup.update(true, 80));
  assert(cup.update(true, 80));
  assert(!cup.update(false, 80)); // unstable/invalid weight fails closed
  CupTare tare;
  assert(!tare.set(false, true, 80));
  assert(tare.set(true, true, 80));
  float water = 0; assert(tare.volume(true, 180, water)); assert(std::fabs(water-100) < .01f);
  assert(!tare.volume(false, 180, water));
  tare.clear(); assert(!tare.volume(true, 180, water));
  BootTaredScale boot;
  for (int n = 0; n < 10; ++n) assert(!boot.accept(-100000));
  for (int n = 0; n < 9; ++n) assert(!boot.accept(-26430));
  assert(boot.accept(-26430) && boot.stable() && boot.grams() == 100);
  assert(boot.accept(-26430) && boot.accept(-26430) && boot.cup());
  char body[96];
  const ScaleUpload reading{boot.grams(), UINT32_MAX, boot.stable(), boot.cup()};
  assert(formatScaleUpload(reading, 0, 500, body, sizeof body));
  assert(std::strcmp(body, "{\"weight_g\":100.0,\"stable\":true,\"cup\":true,\"calibrated\":true}") == 0);
  assert(!formatScaleUpload(reading, 499, 500, body, sizeof body));
  assert(!boot.accept(8388607) && !boot.cup());
  for (int n = 0; n < 9; ++n) assert(!boot.accept(-99900));
  assert(boot.accept(-99900) && boot.grams() == 0);
  return 0;
}

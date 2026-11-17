#pragma once
#include <Arduino.h>
#include <driver/gpio.h>
#include "dispensing.h"

// No proposed GPIO is selected here. Enabling requires a separate reviewed
// commissioning build; defaults never configure or write a pump/stop GPIO.
#ifndef KAEW_PUMP_COMMISSIONED
#define KAEW_PUMP_COMMISSIONED 0
#endif
#ifndef KAEW_LOCAL_REFILL_ENABLED
#define KAEW_LOCAL_REFILL_ENABLED 0
#endif
#ifndef KAEW_PUMP_PIN
#define KAEW_PUMP_PIN -1
#endif
#ifndef KAEW_ESTOP_PIN
#define KAEW_ESTOP_PIN -1
#endif
#ifndef KAEW_PUMP_ON_LEVEL
#define KAEW_PUMP_ON_LEVEL -1
#endif
#ifndef KAEW_ESTOP_SAFE_LEVEL
#define KAEW_ESTOP_SAFE_LEVEL -1
#endif
#ifndef KAEW_INDEPENDENT_CUTOFF_VERIFIED
#define KAEW_INDEPENDENT_CUTOFF_VERIFIED 0
#endif

#if KAEW_PUMP_COMMISSIONED
static_assert(GPIO_IS_VALID_OUTPUT_GPIO(KAEW_PUMP_PIN) && GPIO_IS_VALID_GPIO(KAEW_ESTOP_PIN), "Invalid S3 GPIO capability");
constexpr bool reservedGatewayPin(int pin) {
  return pin == 1 || pin == 2 || pin == 17 || pin == 18 || pin == 4 || pin == 5 || pin == 6 ||
    pin == 10 || pin == 11 || pin == 12 || pin == 0 || pin == 3 || pin == 45 || pin == 46 ||
    pin == 19 || pin == 20 || pin == 43 || pin == 44 || (pin >= 26 && pin <= 37);
}
// Serial uses UART0 TX43/RX44 when USB CDC on boot is disabled. Reserve both
// even in CDC builds so a console configuration change cannot drive the pump.
static_assert(!reservedGatewayPin(KAEW_PUMP_PIN) && !reservedGatewayPin(KAEW_ESTOP_PIN), "GPIO conflicts with peripherals, UART0 console, boot, USB or memory");
static_assert(KAEW_INDEPENDENT_CUTOFF_VERIFIED == 1, "Verify independent pump power interruption first");
static_assert(KAEW_PUMP_PIN >= 0 && KAEW_ESTOP_PIN >= 0 && KAEW_PUMP_PIN != KAEW_ESTOP_PIN,
              "Explicit distinct verified pump/stop pins required");
static_assert((KAEW_PUMP_ON_LEVEL == 0 || KAEW_PUMP_ON_LEVEL == 1) &&
              (KAEW_ESTOP_SAFE_LEVEL == 0 || KAEW_ESTOP_SAFE_LEVEL == 1), "Explicit verified polarity required");
// Actual board availability, boot state, pull resistors, ratings and isolation
// still require schematic review and measurements. GPIO cannot replace cutoff.
#endif

class GpioPump : public PumpActuator {
  bool initialized_ = false;
public:
  void begin() {
#if KAEW_PUMP_COMMISSIONED
    digitalWrite(KAEW_PUMP_PIN, !KAEW_PUMP_ON_LEVEL);
    pinMode(KAEW_PUMP_PIN, OUTPUT);
    pinMode(KAEW_ESTOP_PIN, INPUT); // Verified external bias must fail on wire break.
    initialized_ = true;
#endif
  }
  bool available() const override { return KAEW_PUMP_COMMISSIONED && initialized_; }
  bool estopOk() const {
#if KAEW_PUMP_COMMISSIONED
    return initialized_ && digitalRead(KAEW_ESTOP_PIN) == KAEW_ESTOP_SAFE_LEVEL;
#else
    return false;
#endif
  }
  void set(bool on) override {
#if KAEW_PUMP_COMMISSIONED
    if (initialized_) digitalWrite(KAEW_PUMP_PIN, on && estopOk() ? KAEW_PUMP_ON_LEVEL : !KAEW_PUMP_ON_LEVEL);
#else
    (void)on;
#endif
  }
};

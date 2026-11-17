// Compile-only host fixture: Arduino/GPIO functions are inert test stubs.
// Positive controls prove failures below come from the real header's pin guard.
#include "pump_gpio.h"

#if !KAEW_PUMP_COMMISSIONED
static_assert(KAEW_LOCAL_REFILL_ENABLED == 0, "Local refill must default off");
static_assert(KAEW_PUMP_PIN == -1 && KAEW_ESTOP_PIN == -1, "Pins must default disabled");
static_assert(KAEW_PUMP_ON_LEVEL == -1 && KAEW_ESTOP_SAFE_LEVEL == -1, "Polarity must default unspecified");
#endif

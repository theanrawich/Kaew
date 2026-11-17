#include "cloud_config.h"
static_assert(KAEW_AI_REFILL_ENABLED == 0, "AI refill must default disabled without a separate explicit opt-in");
static_assert(KAEW_ADVICE_URL[0] == '\0', "Advice endpoint must be explicitly configured");
#ifndef EXPECT_ENABLED
#error "Supply EXPECT_ENABLED when testing the cloud configuration matrix"
#endif
static_assert(bool(KAEW_CLOUD_ENABLED) == bool(EXPECT_ENABLED),
              "URL/token must auto-enable publishing unless explicitly overridden");
int main() { return bool(KAEW_CLOUD_ENABLED) == bool(EXPECT_ENABLED) ? 0 : 1; }

#include "cloud_config.h"
#ifndef EXPECT_ENABLED
#error "Supply EXPECT_ENABLED when testing the cloud configuration matrix"
#endif
static_assert(bool(KAEW_CLOUD_ENABLED) == bool(EXPECT_ENABLED),
              "URL/token must auto-enable publishing unless explicitly overridden");
int main() { return bool(KAEW_CLOUD_ENABLED) == bool(EXPECT_ENABLED) ? 0 : 1; }

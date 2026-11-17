#pragma once
// Create cloud_config.local.h with these values only on the development machine.
// The default firmware does not connect or publish.
#if __has_include("cloud_config.local.h")
#include "cloud_config.local.h"
#endif
#ifndef KAEW_WIFI_SSID
#define KAEW_WIFI_SSID ""
#endif
#ifndef KAEW_WIFI_PASSWORD
#define KAEW_WIFI_PASSWORD ""
#endif
#ifndef KAEW_CLOUD_URL
#define KAEW_CLOUD_URL ""
#endif
#ifndef KAEW_CLOUD_TOKEN
#define KAEW_CLOUD_TOKEN ""
#endif
#ifndef KAEW_CLOUD_CA
#define KAEW_CLOUD_CA ""
#endif
#ifndef KAEW_ALLOW_DEV_HTTP
#define KAEW_ALLOW_DEV_HTTP 0
#endif
// Minimum spacing between persistent sample writes, in milliseconds.
#ifndef KAEW_DURABLE_MIN_MS
#define KAEW_DURABLE_MIN_MS 1000
#endif

// Separate opt-in for locally confirmed AI refill. This never commissions GPIO.
#ifndef KAEW_AI_REFILL_ENABLED
#define KAEW_AI_REFILL_ENABLED 0
#endif
#ifndef KAEW_ADVICE_URL
#define KAEW_ADVICE_URL ""
#endif

// C++ constant expression: string contents cannot be tested by the preprocessor.
// A local header or build flag can explicitly override this, including forcing off.
#ifndef KAEW_CLOUD_ENABLED
#define KAEW_CLOUD_ENABLED (KAEW_CLOUD_URL[0] != '\0' && KAEW_CLOUD_TOKEN[0] != '\0')
#endif

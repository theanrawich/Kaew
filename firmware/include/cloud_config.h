#pragma once
// Create cloud_config.local.h with these values only on the development machine.
// The default firmware does not connect or publish.
#if __has_include("cloud_config.local.h")
#include "cloud_config.local.h"
#endif
#ifndef KAEW_CLOUD_ENABLED
#define KAEW_CLOUD_ENABLED 0
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

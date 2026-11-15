#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp "${1:-$root/firmware/include/cloud_config.h}" "$work/cloud_config.h"
for mode in empty url_only token_only configured forced_off forced_on; do
  expected=0
  case "$mode" in
    empty) : > "$work/cloud_config.local.h" ;;
    url_only) printf '#define KAEW_CLOUD_URL "https://example.invalid/api/telemetry"\n' > "$work/cloud_config.local.h" ;;
    token_only) printf '#define KAEW_CLOUD_TOKEN "test-only-placeholder"\n' > "$work/cloud_config.local.h" ;;
    configured|forced_off)
      printf '#define KAEW_CLOUD_URL "https://example.invalid/api/telemetry"\n#define KAEW_CLOUD_TOKEN "test-only-placeholder"\n' > "$work/cloud_config.local.h"
      if [[ $mode == forced_off ]]; then
        printf '#define KAEW_CLOUD_ENABLED 0\n' >> "$work/cloud_config.local.h"
      else expected=1; fi ;;
    forced_on) rm "$work/cloud_config.local.h"; expected=1 ;;
  esac
  flags=()
  if [[ $mode == forced_on ]]; then flags+=(-DKAEW_CLOUD_ENABLED=1); fi
  g++ -std=c++17 -I"$work" -DEXPECT_ENABLED="$expected" "${flags[@]}" "$root/firmware/test/cloud_config_test.cpp" -o "$work/test"
  "$work/test"
  echo "cloud configuration: $mode passed"
done

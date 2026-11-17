# M4 gateway AI-loop validation — 17 November 2026 (Asia/Bangkok)

Source branch: `feature/ratchapol-ai-refill-loop`, from `d8d164e` on current main after merged PR #8. This record covers the new locally confirmed AI read/validation path; [PR #8 validation](software-2026-11-17.md) remains a historical snapshot. Architecture, contract and limitations are in the [M4 design](../M4_GATEWAY_AI_LOOP.md).

| Executed check | Actual result |
|---|---|
| `python scripts/run_host_tests.py` | PASS: 9 host C++ programs, including existing 25 gateway scenarios and 12 new AI scenario groups; 6 GPIO compile checks and 6 cloud-configuration cases |
| `python -m unittest discover -s cloud -p 'test_*.py' -v` | OK: 87 total, **82 passed / 5 optional Postgres skipped** |
| HTTP advice → C++ integration (part of cloud suite) | PASS: model-provider fixture suggestions 120/240 mL become fake targets 220/340 g for a synthetic 100 g cup and stop; 400 mL is rejected |
| `python -m unittest discover -s scripts -p 'test_*.py' -v` | PASS: 24 / 24 |
| `node --test simulation/*.test.mjs` | PASS: 25 / 25 |
| `python -m platformio run -d firmware -e sensor_node -e gateway -e gateway_cloud_compile -e sensor_node_trace -e gateway_trace -e gateway_ai_compile` | SUCCESS: all 6 environments |
| Source/whitespace/local Markdown link checks | PASS before publication |

Tooling: existing local Python 3.13.16, g++ 14.2.0, Node 24.7.0, PlatformIO 6.2.0 / espressif32 6.10.0. Dependencies and AI model/provider implementation are unchanged. Localhost tests/build tooling ran with the required environment permissions; no production HTTP request or live inference was performed. CI for the eventual PR is a separate remote result, not inferred from local success.

One Windows host run encountered a linker `Permission denied` while overwriting the just-executed cloud-configuration binary. The runner now gives each configuration its own executable and GPIO compile case its own object file; the complete suite then passed. No assertions, expected failures or compile checks were disabled.

Safety evidence is software-only: exact-schema/size parsing, authentication/read scope, advice age/model provenance, no intent/no start, nonce/boot/cup/request binding, once-only decisions, late/replayed replies, network failures, disabled hardware, manual override, STOP/fault recovery, E-stop during AI dispensing, timeout and millis wrap are exercised. No original safety tests were removed. The flat projection excludes private history and reasons; admin API behavior and reminder/model logic pass their existing regressions.

**Not performed:** real provider inference, ESP32 runtime/TLS/NTP/Wi-Fi tests, deployment, board flash, physical pump/E-stop commissioning, calibration, shutdown/overshoot measurements, or real water dispensing. The provider and pump in integration tests are explicitly deterministic fakes. `KAEW_PUMP_COMMISSIONED=0`, unspecified GPIO/polarity and `KAEW_AI_REFILL_ENABLED=0` remain defaults; the compile-only AI environment changes the feature flag, not physical commissioning.

Remaining integration: Theanrawich reviews/deploys the restricted device view and creates a fresh genuine model decision through the existing workflow; Suphachok verifies power/driver/E-stop and sensors; Arm performs supervised hardware/network tests and sets measured limits before a separately reviewed commissioning configuration.

Cloud tests now live in `cloud/tests/`. The tables above retain commands and results from their stated revisions; the current command from the repository root is `python3 -m unittest discover -s cloud/tests -t cloud -p 'test_*.py' -v`.

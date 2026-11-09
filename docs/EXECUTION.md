# Kaew autonomous engineering — execution ledger

Status: **IN PROGRESS — not hardware-ready or software-complete**. This tracked ledger supersedes the local copy. Do not infer physical safety, course compliance, or purchase readiness from simulation results.

## Current baseline

- Repository has a browser model, parametric CAD studies, a simulation controller and in-memory telemetry demo; no embedded firmware, AI service, cloud backend, or operational voice pipeline was found in tracked files.
- Course text `FINAL_PROJECT_2026_TH.md` is a local translation of the official document last checked 30 October 2026. The 20 November checkpoint and 8 December final are recorded there; check current announcements and actual submission status.
- Node candidate sensors: level, TDS, temperature; gateway: load cell, microphone. Actual acquisition and eligibility remain to be demonstrated. A point level switch reports wet/dry/unknown, not tank volume.
- The existing pump variant, power interface, electrical ratings, restart behavior and water-contact materials remain unverified. Hardware emergency stop must independently isolate pump power and needs a verified DC-rated circuit and real tests. No flow sensor or heater is in scope.
- Prior estimate 4,153 THB is not a checkout quote and excludes shipping; structure, fasteners, food-contact path, current pump and contingency must be reconciled with actual pricing against 4,500 THB.
- Existing CAD uses provisional dimensions and contains unresolved service/fit issues. Do not fabricate final parts before measuring them.

## Decisions and ordered work

1. [ ] Preserve and audit existing simulator, CAD, BOM, course documents and published site; reconcile contradictory claims.
2. [ ] Specify bounded device contracts, failure states, freshness, authenticated commands and non-resuming reboot behavior; implement and test using existing simulator.
3. [ ] Implement and compile both MCU targets with actual pinned board variants, safe boot behavior and explicit hardware commissioning gates.
4. [ ] Implement genuine AI decision service, validated bounded output, deterministic fallback and evaluation; integrate Thai speech as a separate service with consent/privacy and tests.
5. [ ] Implement authenticated cloud ingestion, durable offline buffering, dashboard, history and notifications; test end to end.
6. [ ] Resolve pump electrical interface, safety chain, wiring, materials and budget from primary documentation and supplier evidence. Keep all unresolved items as purchase holds.
7. [ ] Recheck CAD constraints and service access; prepare conditional assembly and fabrication instructions based on measured parts.
8. [ ] Complete M1–M8 and five depth-item traceability with code, software tests and physical evidence separated. Prepare user deliverables and physical acceptance procedures.
9. [ ] Run full automated tests, both firmware builds and integration/CI checks. Record commands and results, limitations, and real remaining work.

## Work recorded 9 November

- Baseline: 14 existing Node tests passed before changes. The simulator previously accepted `start` while pumping, resetting its timeout; a regression test reproduced this and the controller now rejects overlapping starts. Timeout values and ideal flow remain illustrative, not physical validation.
- Added a simulation-only node message receiver for level state, raw ADC, temperature, sequence, duplicate acknowledgement, session changes and freshness. It is neither encrypted nor authenticated, and is not firmware or a network implementation. Enrollment requires an authenticated commissioning design before real use.

## External dependencies and holds

- Actual module variants, pump data, water-contact evidence, dimensions and supplier quotes; physical purchase and measurements are human actions.
- Credentials/accounts, real Wi-Fi, microphone and speaker setup, calibration, physical safety testing, and instructor/TA acceptance.
- Confirm actual course announcements, team roles and genuine contributions. Never invent member work or submission status.

## Continuation: firmware checkpoint

- `firmware/platformio.ini` selects ESP32 DevKit and ESP32-S3 DevKitC-1 16 MB / octal PSRAM candidates; exact board revision remains unverified.
- Node reads DS18B20 asynchronously and logs raw ADC; level interface is disabled pending electrical confirmation. Serial output is diagnostic, not node-to-gateway communication.
- Gateway reads raw HX711 without interpreting raw counts as grams. The standalone C++ controller has fault latching, start rejection, freshness and timeout checks. Pump pin, emergency-stop input, calibration and actuation are disabled by design; this is not a usable dispensing firmware or safety certification.
- `g++ -std=c++17 -Ifirmware/include firmware/test/safety_test.cpp -o firmware/test/safety_test.exe` followed by `firmware/test/safety_test.exe` passed on the host. Physical sensor, driver, emergency-stop and power tests remain outstanding.
- PlatformIO 6.2.0 and Espressif platform 6.10.0: `pio run -d firmware` completed successfully for both targets outside the Windows sandbox. In the sandbox the compiler process failed with `Illegal System DLL Relocation`; the same compiler ran outside it. OneWire 2.3.8 produced preprocessor warnings. PlatformIO reports its S3 preset as N8 despite the image build specifying 16 MB; the octal PSRAM configuration and actual board revision still need physical verification. The build does not prove correct runtime behavior or PSRAM operation.
- Added CI for simulator tests, host safety test and both firmware builds; the workflow has not been run by GitHub yet.
- **Exact next step:** finish Phase 1 before enabling actuation: implement real, explicit calibration and persistence for HX711; integrate cup detection, plausible weight changes and independent tank-data freshness into the tested controller; implement OLED and safe configuration. Add tests and rebuild both targets. Then implement authenticated node-to-gateway transport with ACK/retry, connect it to the controller, and integrate simulator protocol tests. Physical driver and emergency-stop circuits remain a hold. Audio, provisioning, cloud and remaining phases are not implemented.

## Firmware and UART continuation

- Added versioned checksum-protected calibration in gateway NVS, a host-testable five-sample filter, provisional stable-cup detection and volatile explicit cup tare. `CAL` and `TARE` are described in `firmware/README.md`. A host test checks encoded calibration corruption; NVS power-loss and real calibration have not been tested.
- Implemented UART on both targets with a shared 20-byte binary codec, CRC16, node ID, random boot session, sequence, ACK, retries, duplicate suppression and freshness. Gateway considers level wet only for a fresh wet reading. Level input and pump output remain disabled. Internal UART is unauthenticated; CRC is not authentication and session changes after timeout are not replay protection. Provisional pin assignments and electrical checks are in the firmware README.
- Added host tests of the shared firmware classes for communication loss/retry/duplicate, session changes, corrupted frames, calibration, cup/filter/tare and fault behavior. This is a host simulation of the protocol and safety classes, not a physical UART test. The existing browser simulator still uses its earlier JavaScript contract and has not been connected to the C++ implementation.
- Both targets built successfully with PlatformIO 6.2.0 / Espressif platform 6.10.0 outside the sandbox. The S3 now uses a custom N16R8 candidate board definition, QIO flash, OPI PSRAM and `default_16MB.csv`; build reports 16 MB flash. Physical flash/PSRAM identity and operation, board GPIO availability and electrical interfaces remain unverified. OneWire dependency emitted preprocessor warnings on the clean build. GitHub CI workflow was updated but not remotely run.
- **Next step:** Phase 1–2 are still incomplete. Replace the stable-only cup logic with a validated lifecycle that remains safe during dispensing, design tare retention and target derivation, integrate a deduplicated command path and simulator with the same controller/contract, handle link/session replay according to the threat model, add versioned general device configuration, OLED and diagnostics, and test the full state machine with fault injection. Verify no command path can energize the disabled pump; only physical commissioning can establish actual thresholds and hardware safety. Then continue cloud/dashboard and remaining phases.

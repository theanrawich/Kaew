# Kaew autonomous engineering — execution ledger

Status: **IN PROGRESS — not hardware-ready or software-complete**. This local working document is excluded by the existing root Markdown ignore rule. Do not infer physical safety, course compliance, or purchase readiness from simulation results.

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

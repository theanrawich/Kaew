# Repeatable performance measurements — Ratchapol

17 November 2026. **All physical runs below are BLOCKED: hardware, approved wiring, reference instruments and acceptance limits have not been supplied in this session. No experimental values are reported.** Software arithmetic tests are separate in [validation](validation/software-2026-11-17.md).

## Record and acceptance rules

Use [test record template](TEST_RECORD_TEMPLATE.md) for each run and the blank [run index](measurements/test-runs.csv). Record ID, objective, setup, step/procedure revision, expected result, actual result, PASS/FAIL/BLOCKED, raw path, mean/min/max/sample standard deviation/range, operator/date, evidence and exact firmware commit/configuration. Archive the source diff/hash when testing an uncommitted revision. Also record board/driver revisions, power topology, calibration ID, reference instrument resolution/uncertainty, sample rate, network/outage schedule, cup and water level.

Set numerical tolerances and sample counts **before** collecting results, agreed with the team/instructor. A missing tolerance or reference is BLOCKED, even if logs exist. Do not discard failed/aborted trials; explain exclusions in the run record. Analysis scripts compute statistics and always emit `hardware_verdict=NOT_ASSESSED`; a human compares against the preregistered limits. Never turn a synthetic test fixture into a result row.

Copy header-only CSVs from `docs/measurements/` into a dated evidence folder, then populate with actual readings. The scripts reject blank data, nonfinite values, malformed columns, duplicate trials, incomplete packet captures, counter mismatches, and mixed latency clocks. Store output JSON alongside the raw CSV; it includes the input SHA256 and evidence paths.

## A — End-to-end event-to-actuator latency

**IDs:** LAT-01 normal actuation; STOP-01 cup removal; STOP-02 independent E-stop; STOP-03 stale scale/tank. Objective: measure detection/control latency and distinguish electrical cutoff from actual water stopping.

**Setup (currently BLOCKED):** reviewed driver/stop circuit, supervised test fixture, reference scale/high-speed camera or flow collection, logic analyzer/oscilloscope with a common capture timebase and enough digital channels. Begin with a safe dummy load and disconnected pump; physical pump tests require a later explicit commissioning authorization. Use rated probes and verify electrical references; no direct attachment to unknown pump voltages.

1. Record analyzer sampling frequency, timing resolution and trigger uncertainty. Select at least 30 independent trials per event and repeat with Wi-Fi/cloud traffic and optional audio load. Predeclare acceptable mean/max shutdown delay and post-stop volume from actual capacity and hazards.
2. LAT-01 starts at the physical user request edge on an externally observed/verified local test input, or at the completion of the terminating newline of a valid local refill command captured on the console UART. State which endpoint is used. Ends at the driver command's ON edge. A USB console host write timestamp is not the physical UART completion timestamp.
3. STOP-01 starts at a fixture switch/optical marker detecting cup removal. Also capture HX711 DOUT and optionally SCK to relate acquisition timing. Ends separately at (a) driver OFF edge, (b) pump supply/current below the documented off threshold, and (c) last detectable water movement. If a camera is used, specify frame rate, frame definitions and marker synchronization to the electrical capture.
4. STOP-02 starts at the actual independent E-stop contact opening and ends at pump power interruption and water stop. Verify power can be cut with MCU unresponsive. A GPIO change alone cannot pass this test.
5. STOP-03 starts at last valid scale conversion / last accepted **unique** wet packet, then ends at driver OFF. Record configured stale threshold and expected threshold plus measured scheduling delay. Also report delay relative to the stale deadline; label it separately from total time since the last sample.
6. Export unwrapped capture times in integer microseconds into `latency.csv`, one row per trial/kind: `event_to_control`, `event_to_power_off`, `event_to_flow_stop`, or another explicit kind. Put the same capture clock ID in both endpoint columns; estimate and record `sync_uncertainty_us`. If separate clocks are used, document an offset/drift calibration with uncertainty and map them into one domain **before** export. Millis/NTP clocks on different devices are not assumed aligned. Timing below the combined uncertainty is inconclusive.
7. Run `python scripts/analyze_measurements.py latency <actual.csv> --output <latency.json>`. Report n, mean, min, max, sample SD, range and p95 with uncertainty and event definition. Host execution time of a unit test is not actuator latency.

Expected: local control stops independently of network/AI, meets the limits set before testing, and never restarts from a fault. **Actual: not measured; BLOCKED.** Archive original waveform/video, probe setup photo and CSV. Sensor processing/queue scheduling, 5 ms loop delay, diagnostic serial writes, HX711 rate and mechanical residual flow all contribute; there is no proven worst-case real-time bound yet.

## B — Packet delivery rate

**IDs:** PDR-01 normal UART; PDR-02 temporary link disconnection/recovery; PDR-03 Wi-Fi/cloud outage with NVS saturation; PDR-04 node/gateway reboot. Objective: count unique application packets, not transmissions or ACKs.

**Setup (currently BLOCKED):** actual two boards and verified UART, two USB data ports, trace firmware, one PC, pyserial, and an independent UART capture/logic analyzer when checking log completeness. Disconnect physical pump power for the whole run. Existing wire protocol/retry timing is unchanged. Optional trace builds fail compilation if pump commissioning is also enabled.

```powershell
# Build only. Flashing requires confirmed boards, wiring and ports as in firmware/README.md.
pio run -d firmware -e sensor_node_trace -e gateway_trace

# AFTER separate hardware setup/flash, capture actual logs; replace placeholders.
python scripts/capture_packet_delivery.py --node <NODE_COM> --gateway <GATEWAY_COM> --window-s 60 --recovery-s 10 --test-id PDR-01-T01 --firmware-commit <commit-and-config> --output <new-run.csv>
python scripts/analyze_measurements.py packets <new-run.csv> --output <pdr.json>
```

Use the local PlatformIO venv Python if pyserial is not otherwise installed. The recorder opens two ports at 115200 and sets DTR/RTS false before opening; some USB drivers/boards may still reset on open. Record any reset and capture boot sessions. It sends no serial commands. Do not use these trace builds for a pump demo. After the chosen window/recovery durations it waits up to `--closing-grace-s` (default 3 s, range 1–60 s) for each board's final diagnostic. This closing tail is excluded from PDR. Watch the capture locally and keep the ports exclusively available.

Trace format: `TRACE <tx|rx|ack|drop> <board_millis> <node> <session> <seq>`. `tx` is emitted after a complete UART frame is queued for transmission; `rx` follows a decoded frame accepted/duplicated by the **safety** receiver, before cloud enqueue. `ack` is a received sender ACK; `drop` is sender retry exhaustion. This defines application PDR; separate line-level CRC/corruption observations from application delivery. ACK confirms gateway durable storage only when publisher is enabled; it never proves HTTPS/dashboard arrival.

1. Record a warm-up interval, firmware/config and both board logs. Require `trace_dropped=0` closing diagnostics from **both boards at/after the end of window + recovery**. An earlier zero counter is insufficient: losses may have occurred since that diagnostic. If either closing counter is missing or any observed counter is nonzero, reject the run. `PacketTrace` drops rather than blocking when console space is insufficient. Check PC serial overflow, disconnects, continuity of logs and counters against raw waveform/frame counts; board resets can erase counters and host buffering can delay diagnostics. The tool cannot detect every possible logging loss.
2. Use ≥3 repeated runs of at least 60 s per scenario, specifying exact interruption times/durations before each run. Use longer trials for robustness after initial checkout. For PDR-03 record the finite 16-slot durable queue, RAM queue, four-attempt sender bound and actual retry exhaustion; no unlimited-outage/no-loss promise.
3. Recorder timestamps lines with one PC monotonic clock. The first `window-s` of **recorded node tx events** defines the cohort. Every key `(node, session, seq)` with a tx in that window enters denominator `Ntx`. Count retries as additional attempts of the same key, never as new unique packets. Sequence gaps alone cannot establish transmitted packets.
4. `Nrx_window` counts cohort keys in gateway rx events recorded before window end; `Nrx_final` counts them through the predeclared recovery grace. Keep cohort retry/rx/ack/drop events during recovery. New packets generated during recovery are outside the cohort and excluded. Save `.jsonl` raw lines so the exact boundary/cohort can be audited. Board times need not be synchronized for key counting; host receipt/USB buffering creates boundary uncertainty, so this is an operational log-based window, not wire-level latency.
5. Calculate `PDR_window=100*Nrx_window/Ntx`, `PDR_final=100*Nrx_final/Ntx`, `unreceived=Ntx-Nrx_final`, `retry_attempts=tx_attempts-Ntx`, `duplicate_rx=rx_frames-Nrx_final`. A lost ACK may cause a retry or sender drop even if the gateway received the packet: report ACK/drop counts separately. Queued **cloud** recovery does not increase gateway UART PDR; inspect cloud persistence separately.
6. Reboots change sessions and sequence wrap is handled by keys rather than subtracting sequence values. Different node sessions can be rejected until the previous five-second freshness window expires; include the resulting loss/recovery rather than hiding it. For a gateway reboot the same packet may arrive twice: only one unique cohort key counts. UART CRC is not command authentication.
7. The capture tool refuses existing output names, serial/truncation errors and reported trace loss. Analyze each trial and aggregate trial rates as mean/min/max/sample SD; output also includes pooled PDR (sum received / sum transmitted), which can differ from an unweighted mean. Use a unique `test_id` per scenario; edit/merge `trial` fields into a combined CSV only with preserved raw links and consistent configuration.

Saved logs can be reprocessed without boards:

```text
python scripts/capture_packet_delivery.py --from-log <raw.jsonl> --window-s 60 --recovery-s 10 --test-id PDR-01-T01 --firmware-commit <version> --output <new-reprocessed.csv>
```

Use the original window **and recovery** durations. Traffic at/after that fixed endpoint is kept in raw evidence only; it does not improve measured recovery delivery. Saved logs without both final counters are rejected and need recapture. The recorder's board timestamps are retained in raw text, while CSV `time_us` is host receipt time. No cloud API, AI provider or production credentials are required for PDR-01/02. **Expected:** meet preregistered per-scenario PDR/loss/recovery limits. **Actual:** no board captures; BLOCKED.

## C — HX711 accuracy and repeatability

**ID:** ACC-01. Objective: compare calibrated readings to an independent reference and quantify error/repeatability, not claim nominal HX711 accuracy.

**Setup (currently BLOCKED):** mounted load cell/HX711, verified wiring/rate, known reference masses, independent reference scale with documented resolution/uncertainty, stable surface, actual cup/platform, and temperature/settling record. Pump disconnected.

1. Warm up and record drift until a predefined stable criterion is met. Check load-cell rated capacity including platform, cup and water; zero with platform unloaded. Collect several stable signed raw readings at zero and at a known calibration mass spanning the intended range. Use their means and known mass for `CAL`; record the original readings and computed factor, version and checksum. Do not reuse synthetic host-test factors.
2. Formula: `counts_per_g=(known_raw-zero_raw)/known_mass_g`; `weight_g=(raw-zero_raw)/counts_per_g`. Negative slopes are supported. Calibration is two-point; validate linearity independently at several points. ADC rails, invalid checksum or missing calibration fail closed.
3. Independently validate at nominal **0, 50, 100, 200 g** and the maximum intended gross load. Use reference scale's actual value in `reference_g`; `point_g` is the nominal group label. Collect at least 10 independent load/unload repetitions per point, both increasing/decreasing loads, then repeat off-center and after a drift interval. Do not count ten correlated samples of one stationary load as ten independent placements. Record raw counts corresponding to each validated weight and calibration ID.
4. The five-sample median needs five observations; cup detection needs three stable observations (earliest seventh conversion after a clean reset). The illustrative stability spread is ≤5 g and cup window 30–900 g. At a measured sample rate R, warm-up is about `6/R` seconds between first and seventh sample, plus phase/scheduling. This is an estimate, not a measured latency. A 0 g accuracy point intentionally has no cup. The periodic gateway diagnostic reports the most recent processed value; save a reading only when a fresh conversion/raw value and stability were confirmed, or obtain a controlled per-conversion bench log. Do not pair an old filtered value with unrelated raw counts.
5. Reposition an EMPTY cup, wait for stable presence, issue `TARE` and confirm volume zero. Add a known mass and compare approximate mL. Remove cup, disconnect HX711, reconnect and reboot separately: tare must be invalidated and a new explicit empty-cup tare required. Check fast and gradual cup lifts during later authorized dispensing; do not infer adequate shutdown solely from median behavior.
6. Populate `accuracy.csv`. For each row compute signed error `e=HX-reference`; report signed mean bias, mean absolute error `mean(|e|)`, RMSE `sqrt(mean(e²))`, max absolute error and reading sample SD/min/max/range at each point. Include reference uncertainty; a result smaller than instrument uncertainty is not established accuracy.

```text
python scripts/analyze_measurements.py accuracy <actual.csv> --output <accuracy.json>
```

**Expected:** all points within predeclared tolerance including reference uncertainty; tare invalidation and disconnect behavior match the safety test plan. **Actual:** no real calibration or reference readings; BLOCKED.

## Optional D — delivered volume, overshoot and residual flow

**ID:** VOL-01. After authorized pump/stop commissioning, test targets 50/100/200 mL and the approved maximum, at high/low reservoir levels, ≥5 repetitions each. Use a reference scale for cup before start and after complete flow stop, a timestamped driver-OFF point, and a separate measured post-OFF mass gain. Record density assumption/temperature: delivered mL = mass gain / density. `after_g` includes post-stop water; `post_stop_g` is a subset, not extra delivery to add again. Report signed error, positive overshoot `max(delivered-target,0)`, post-stop volume, time and their mean/min/max/SD/range. Underfill remains a signed error, never hidden by zero overshoot.

```text
python scripts/analyze_measurements.py volume <actual.csv> --output <volume.json>
```

Confirm no siphon/uncontrolled residual flow, check E-stop/boot/brownout/wire break/current ratings, and set `allowable_target ≤ measured_safe_capacity − worst_post_stop_volume − uncertainty − margin`. The software's 300 mL and 900 g caps do not establish actual safe capacity. **Actual:** BLOCKED. No pump energized in this session.

## Physical run register

| ID | Objective / setup / procedure | Expected | Actual / status | Raw / statistics / evidence / firmware |
|---|---|---|---|---|
| LAT-01 | Request to driver; common-clock dummy-load capture above | Declared latency bound | Not run — BLOCKED | Blank until setup and limits approved |
| STOP-01/02/03 | Cup/E-stop/stale to command, power and water stop | Independent local cutoff; no restart; approved delay/residual | Not run — BLOCKED | Blank until authorized physical run |
| PDR-01/02/03/04 | Trace key cohort; repeat normal/outage/reboot | Declared PDR/loss/recovery limits | Not run — BLOCKED | Blank; save JSONL + CSV + analyzer output |
| ACC-01 | Calibrate; independent repeated known loads | Preregistered uncertainty-aware error limits | Not run — BLOCKED | Blank; reference/calibration records required |
| VOL-01 | Real target, levels and residual collection | Safe capacity and overshoot limits | Not run — BLOCKED | Blank until pump/stop commissioning |

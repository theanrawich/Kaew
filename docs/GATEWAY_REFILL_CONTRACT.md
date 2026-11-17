# Gateway refill contract — Ratchapol / Theanrawich handoff

17 November 2026. Implemented software interface; **physical pump disabled, remote requests always rejected**. This document does not authorize commissioning. Theanrawich's AI/reminder/cloud implementation is unchanged.

## Admission boundary

`GatewayDispenser::request(RefillRequest, CommandSource, Inputs, CupTare)` is synchronous, bounded, and called only from the gateway control loop. It never waits for AI, HTTPS or NVS. A future network task must submit a bounded message to this loop; it must not call the controller or GPIO directly or share mutable `Inputs` across tasks.

The current console adapter accepts:

```text
CAL <unloaded_signed_raw> <known_weight_signed_raw> <known_mass_g>
TARE
REFILL <gateway_boot_session> <request_id> <issued_at_gateway_ms> <target_water_ml>
STOP
RESET
```

Lines are ASCII, newline-terminated, at most 127 bytes excluding terminator. CR is ignored for CRLF terminals. Overflow/control-byte lines are discarded in full. Unknown commands, extra refill/calibration arguments, integer overflow and nonfinite volumes are rejected. Console processing reads at most 64 bytes per loop; no `readStringUntil()` timeout can delay safety. Only `STOP` and `RESET` are accepted outside Idle, plus refill requests which are explicitly rejected/consumed by the request validator.

`CAL` and `TARE` are local bench operations in Idle. The operator must confirm the platform was unloaded for calibration zero and the cup is EMPTY for tare. Software cannot establish emptiness, cup identity or capacity from weight alone. Never send invented calibration counts. Calibration data includes version/checksum; only it is persisted. Tare, commands, target and request IDs are volatile.

## Proposed typed data for the future adapter

This JSON is a **schema description**, not a currently deployed HTTP endpoint:

```text
version: integer, exactly 1
gateway_boot_session: uint32, current gateway boot token (nonzero)
request_id: uint32, nonzero, strictly increasing per gateway boot
issued_at_gateway_ms: uint32, timestamp in gateway millis() domain
target_water_ml: finite number, TOTAL water requested in the tared cup
```

Map these fields to `RefillRequest{version, bootSession, requestId, issuedAtMs, targetWaterMl}`. Do not supply safety flags, calibration, tare or gross target weight from AI. Those are derived locally. Bind a proposal to the actual current cup through local confirmation; AI output received during an operation is never a target update. To change a target, stop, recover, establish a valid empty-cup tare, and issue a new request. No automatic cup-return refill is implemented.

Rules enforced by gateway:

| Check | Implemented behavior |
|---|---|
| Source | `RemoteAI` always returns `RemoteDisabled`, including valid/authenticated-looking data. |
| Local enable | Both commissioned actuator availability and `KAEW_LOCAL_REFILL_ENABLED=1` needed; defaults deny. |
| Version / boot | Exactly v1 and current nonzero boot; old boot data rejected. Boot token is **not authentication**. |
| ID | IDs ≤ highest consumed local ID are rejected; no wrap. Rejected busy/unsafe/expired/invalid-volume requests consume their ID. Bad envelope, remote and disabled requests do not. Never queue a rejected start for later. |
| Age | `uint32(nowMs-issuedAtMs) < 2000`, configurable downwards via `RefillLimits`. Future/old times outside this modular window rejected; wraparound tested. |
| State | Only Idle. Dispensing, Settling or Faulted reject starts. No timeout extension by repeated requests. |
| Volume | `0 < targetWaterMl ≤ maxWaterMl ≤ 300`; default is a provisional software ceiling. Must exceed water already in cup. Lower after measuring safe capacity/overshoot. |
| Tare / target | Valid volatile empty-cup tare required. Approximation: `water_ml = gross_g - empty_cup_g`; `gross_target_g = empty_cup_g + targetWaterMl`. Gross target must also satisfy controller ≤900 g. |
| Local interlocks | Calibrated, valid/fresh scale; stable cup before start; fresh wet tank; safe E-stop status; valid safety configuration. |

For example, an empty cup of 100 g containing an estimated 50 mL weighs 150 g. A **total** target of 100 mL produces a 200 g gross target and adds approximately 50 mL. This arithmetic example is not a hardware measurement. `suggested_ml` in the existing hydration AI is advice; do not silently equate it with this target or treat `actuation_allowed=false` as permission.

`RefillResult` values (numeric console output): `0 Started`, `1 RemoteDisabled`, `2 Disabled`, `3 InvalidEnvelope`, `4 Duplicate`, `5 Expired`, `6 Busy`, `7 InvalidVolume`, `8 TareRequired`, `9 Unsafe`. No error starts a pump. Rejected overlaps leave the current target unchanged, but every request first services safety, so stale data can stop an existing operation even when a request is invalid.

`STOP` immediately commands off and latches `ManualStop`. Interlock faults latch independently. `RESET` needs all local conditions safe and a nonactive state; it commands no start, clears tare in the application, and requires a new explicit empty-cup `TARE` and higher-ID `REFILL`. Fault clearance never resumes the previous operation.

## Required from Theanrawich before any remote integration

1. Keep current AI/reminder behavior advisory. Agree whether a natural-language volume means *add* or *total*; convert only after explicit user confirmation against the current cup. Reject ambiguous instructions.
2. Specify authenticated device/operator identity, authorization, replay protection, expiry/nonce lifecycle, gateway reboot/cup change invalidation, and bounded message rate/queue. TLS/bearer telemetry credentials and CRC16 are not a ready pump-command authorization protocol.
3. Exchange the current boot token and establish a trustworthy time mapping. Do not copy an epoch/NTP timestamp into `issuedAtMs`; never re-stamp an old queued AI decision as fresh after reconnection. The transport must retain original decision expiry and discard offline backlog.
4. Define result/event reporting: proposal ID, requested total, locally accepted target, state/fault/result, gateway boot and timestamp, source, freshness and explicit disabled status. Current cloud publisher still sends **node telemetry only**, not these new dispenser events.
5. Implement the adapter and separate authorization review after hardware commissioning. Re-run host, parser, offline/replay, authorization and physical interlock tests. Enabling a remote path requires a later reviewed change; no macro here enables it.

## Required from Suphachok / hardware team

Supply exact pump/driver/adapter part numbers, ratings and polarity; actual GPIO availability and breakout schematics; independent E-stop power-cut circuit with external fail-safe status bias; verified tank output voltage/polarity and node pin; HX711/load-cell wiring, actual rate and measured calibration; cup safe capacity and post-stop flow. Arm reviews and measures before selecting commissioning limits. See [physical test plan](PERFORMANCE_TEST_PLAN.md) and [wiring holds](wiring.md). These are requested handoffs, not claims that a teammate has already verified them.

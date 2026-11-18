# Gateway refill contract — Ratchapol / Theanrawich handoff

17 November 2026. **Physical pump disabled; unvalidated remote requests remain rejected.** The new opt-in, locally confirmed AI pull adapter is documented in [M4 gateway loop](m4-gateway-ai-loop.md). This document does not authorize commissioning. Theanrawich's model/reminder logic is unchanged; the cloud adds only a restricted read-only device projection.

## Admission boundary

`GatewayDispenser::request(RefillRequest, CommandSource, Inputs, CupTare)` is synchronous, bounded, and called only from the gateway control loop. It never waits for AI, HTTPS or NVS. The AI HTTPS worker submits a bounded proposal to this loop; only the locally armed bridge can enter the shared validator. The worker never calls the controller or GPIO directly or shares mutable `Inputs` across tasks.

The current console adapter accepts:

```text
CAL <unloaded_signed_raw> <known_weight_signed_raw> <known_mass_g>
TARE
REFILL <gateway_boot_session> <request_id> <issued_at_gateway_ms> <target_water_ml>
STOP
RESET
AI_REFILL
```

Lines are ASCII, newline-terminated, at most 127 bytes excluding terminator. CR is ignored for CRLF terminals. Overflow/control-byte lines are discarded in full. Unknown commands, extra refill/calibration arguments, integer overflow and nonfinite volumes are rejected. Console processing reads at most 64 bytes per loop; no `readStringUntil()` timeout can delay safety. Only `STOP` and `RESET` are accepted outside Idle, plus refill requests which are explicitly rejected/consumed by the request validator.

`CAL` and `TARE` are local bench operations in Idle. The operator must confirm the platform was unloaded for calibration zero and the cup is EMPTY for tare. Software cannot establish emptiness, cup identity or capacity from weight alone. Never send invented calibration counts. Calibration data includes version/checksum; only it is persisted. Tare, commands, target and request IDs are volatile.

`AI_REFILL` is a separate default-disabled, one-shot local intent for the current tared cup. It never takes a volume or safety flags from the console: the worker fetches a fresh authenticated device advice projection, and the bridge independently validates it before the same refill checks. It requires safe local conditions even before fetching. The default uncommissioned E-stop/driver configuration therefore blocks real operation. See the [full binding/authentication/expiry contract](m4-gateway-ai-loop.md).

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
| Source | Raw `RemoteAI` always returns `RemoteDisabled`. A locally armed `AiRefillBridge` uses a private shared validator after authenticated pull, context/freshness/provenance checks; it never relabels a remote request as `LocalOperator`. |
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

## Remaining handoff to Theanrawich

1. Keep cloud decisions advisory; review TOTAL-volume semantics for the confirmed empty/tared cup. Natural-language *add* instructions need a separate reviewed adapter and confirmation, not direct mapping to this target.
2. Review/deploy the restricted device-token advice view and local authorization boundary in the [M4 design](m4-gateway-ai-loop.md). TLS and read authorization do not replace local intent or hardware interlocks; there is still no general pump-command API.
3. Validate boot/request/cup/nonce echo, decision-age projection and 2-second local deadline on the actual network. No epoch timestamp is copied into `issuedAtMs`, and offline backlog/late replies are never re-stamped as fresh.
4. Define result/event reporting: proposal ID, requested total, locally accepted target, state/fault/result, gateway boot and timestamp, source, freshness and explicit disabled status. Current cloud publisher still sends **node telemetry only**, not these new dispenser events.
5. Review the implemented adapter and run live model/network/physical tests after commissioning. The opt-in feature flag alone does not authorize commissioning. No production deployment, board flash or physical activation was performed by this implementation task.

## Required from Suphachok / hardware team

Supply exact pump/driver/adapter part numbers, ratings and polarity; actual GPIO availability and breakout schematics; independent E-stop power-cut circuit with external fail-safe status bias; verified tank output voltage/polarity and node pin; HX711/load-cell wiring, actual rate and measured calibration; cup safe capacity and post-stop flow. Arm reviews and measures before selecting commissioning limits. See [physical test plan](../testing/performance-test-plan.md). These are requested handoffs, not claims that a teammate has already verified them.

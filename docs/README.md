# Kaew documentation

- [Architecture](architecture.md) — System diagram, data flow and wiring.

## Design

- [Gateway refill contract](design/gateway-refill-contract.md) — Command validation, interlocks and commissioning prerequisites.
- [M4 gateway AI loop](design/m4-gateway-ai-loop.md) — How the gateway requests and validates refill advice.
- [Voice and hydration decisions](design/voice-and-hydration.md) — AI-driven reminders from body weight, voice commands and replies, speaker TTS, Telegram alerts.

## Testing

- [Cloud speech-to-text](../cloud/README.md#typhoon-speech-to-text) — ESP32 transcript testing with `TYPHOON_API_KEY` configured on the cloud server.

- [Performance test plan](testing/performance-test-plan.md) — Procedures for repeatable latency, delivery, accuracy and volume measurements.
- [Test record template](testing/test-record-template.md) — Run metadata and evidence to capture.
- [Accuracy CSV](testing/measurements/accuracy.csv) — Blank sensor accuracy template.
- [Latency CSV](testing/measurements/latency.csv) — Blank latency template.
- [Packets CSV](testing/measurements/packets.csv) — Blank packet delivery template.
- [Test runs CSV](testing/measurements/test-runs.csv) — Blank run index.
- [Volume CSV](testing/measurements/volume.csv) — Blank dispense volume template.
- [M4 validation](testing/validation/m4-ai-loop.md) — Recorded gateway AI-loop build and test results.
- [Software validation, 2026-11-17](testing/validation/software-2026-11-17.md) — Historical PR #8 build and test results.

## Course

- [Checkpoint critical path](course/checkpoint-critical-path.md) — Temperature telemetry demonstration and outstanding work.
- [Course evidence](course/course-evidence.md) — Rubric, project baseline and evidence requirements.

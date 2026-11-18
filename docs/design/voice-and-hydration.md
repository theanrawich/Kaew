# Voice and hydration design decisions

Decided 2026-11-18.

## Hydration is AI-driven

- The user enters **only their body weight (kg)** on the dashboard.
- The daily goal is derived from body weight (33 mL/kg, bounded 1,000–4,000 mL). The user does not set it.
- The reminder schedule is set **only by the AI** (Groq LLM with a deterministic fallback). There is no manual reminder, goal, or "run advice" control, and voice cannot set reminders.
- The AI reschedules the next reminder when:
  1. the user saves or changes body weight (this also creates the first reminder),
  2. a drink event arrives,
  3. a reminder fires,
  4. the server starts with no reminder scheduled.
- Drinks are detected by the gateway from the HX711 load cell: cup lifted, placed back, weight stable, and weight decreased by a plausible amount (1 g = 1 mL). Weight increases are refills, not drinks. The gateway posts a `measured` drink event to `POST /api/events` with the device token.
- The AI never actuates the pump.

## Voice commands

Every command must start with the wake word **"แก้ว"**. Sentences without it are ignored.

| User says | Kaew replies |
|---|---|
| "แก้ว วันนี้ดื่มไปเท่าไหร่" | Today's drink total vs the weight-based goal and percent, e.g. "วันนี้ดื่มไป 1,200 จาก 2,300 มล. (52%)". Asks for body weight if it is not set. |
| "แก้ว สถานะเครื่อง" | Whether the device is online. |
| "แก้ว เติมน้ำ" | Always rejected while the pump is disabled: "ยังสั่งเติมไม่ได้ ระบบจ่ายน้ำยังไม่พร้อม". |
| anything else after "แก้ว" | "ขออภัย กรุณาพูดอีกครั้ง" |

Removed: the voice reminder, water-level, and stop commands.

Pipeline: gateway mic (INMP441) → speech capture → `POST /api/stt?command=1` → Typhoon ASR → keyword intent parser (not an LLM) → reply text.

## Speaker

- Replies and the reminder phrase "ถึงเวลาดื่มน้ำแล้ว" are spoken on the gateway speaker (MAX98357A).
- Text-to-speech runs on the cloud (Render) with `edge-tts`. Primary voice: `th-TH-NiwatNeural`. Fallback: `th-TH-PremwadeeNeural`, which sometimes returns no audio.
- The cloud converts the MP3 to WAV for the ESP32 and caches fixed phrases.
- If TTS fails, the reply is text only and the gateway logs it.
- `edge-tts` is not an official Microsoft API and may break without notice.

## Telegram alerts

Each alert is sent once per incident: drink reminder, low water, water reading out of range (temperature below 5 °C or above 45 °C, or TDS), sensor read error, device offline for more than 30 s, device back online, and fault events.

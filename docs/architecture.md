# Kaew architecture

```mermaid
flowchart LR
  subgraph Node["Sensor node (ESP32-S3)"]
    TDS["TDS (GPIO4)"]
    LVL["Water level (GPIO5)"]
    TMP["DS18B20 temp (GPIO6)"]
  end

  subgraph GW["Gateway (ESP32-S3 N16R8)"]
    LC["Load cell HX711 (SCK 4, DT 5)"]
    MIC["Mic INMP441 (SD 6, SCK 7, WS 8)"]
    SPK["Speaker MAX98357A (DIN 9, BCLK 10, LRC 11)"]
    PUMP["Pump + E-stop (disabled)"]
    LOGIC["Cup/volume logic + refill safety contract"]
    SPEECH["SpeechCapture + WAV upload"]
  end

  subgraph Cloud["kaew-cloud (Render, Python)"]
    API["HTTP API: /api/telemetry, /api/events, /api/stt, /api/advice"]
    DB[("Postgres (Supabase)")]
    AI["Hydration AI (Groq LLM)"]
    DASH["Dashboard + /stt page"]
  end

  TY["Typhoon ASR"]
  USER["User (browser)"]

  Node -- "UART node 17/18 to gateway 1/2, framed packets + ACK" --> LOGIC
  LC --> LOGIC
  MIC --> SPEECH
  LOGIC -. "advice only, no auto-actuation" .-> PUMP
  LOGIC -- "HTTPS + device token: telemetry, events" --> API
  SPEECH -- "HTTPS + admin token: WAV" --> API
  API -- "speech-to-text" --> TY
  API --> AI
  API <--> DB
  API -- "refill advice" --> LOGIC
  API --> DASH
  DASH --> USER
```

## Data flow

1. The sensor node reads TDS, water level and temperature and sends framed packets to the gateway over UART; the gateway acknowledges each packet.
2. The gateway combines node data with the load-cell cup/volume reading and publishes telemetry and events to the cloud over HTTPS.
3. The cloud stores data in Postgres and serves the dashboard.
4. Voice: the gateway segments speech from the microphone, uploads WAV to `/api/stt?command=1`, the cloud transcribes it with Typhoon ASR and returns a parsed command.
5. Hydration advice comes from the Groq LLM. The pump stays disabled; voice and advice never actuate it directly.

## Wiring

| Board | Part | Pins |
| --- | --- | --- |
| Sensor node | TDS (analog, <= 3.3 V output) | GPIO4 |
| Sensor node | Water level (digital) | GPIO5 |
| Sensor node | DS18B20 (4.7 kΩ pull-up on DQ) | GPIO6 |
| Sensor node | UART to gateway | TX 17, RX 18 |
| Gateway | HX711 load cell | SCK 4, DT 5 |
| Gateway | INMP441 microphone (L/R to GND) | SD 6, SCK 7, WS 8 |
| Gateway | MAX98357A speaker | DIN 9, BCLK 10, LRC 11 |
| Gateway | UART to node | RX 1, TX 2 |
| Gateway | Pump / E-stop | not assigned (disabled) |

Cross UART TX/RX between boards and share GND.

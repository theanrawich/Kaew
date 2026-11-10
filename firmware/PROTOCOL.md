# Kaew UART v1

The sensor node and gateway use a dedicated full-duplex 115200 baud, 8N1 UART. Frame length is 20 bytes. Integers are little-endian; CRC16/CCITT-FALSE has polynomial `0x1021`, initial value `0xffff`, no reflection and no final XOR, over bytes 0–17.

| Offset | Bytes | Meaning |
| --- | --- | --- |
| 0 | 2 | Magic `4b 57` |
| 2 | 1 | Version: `1` |
| 3 | 1 | `1` sample, `2` acknowledgement |
| 4 | 1 | Node ID, currently `1` |
| 5 | 4 | Nonzero random boot-session ID |
| 9 | 4 | Unsigned sequence counter |
| 13 | 2 | Signed centidegrees C, `-32768` = invalid |
| 15 | 2 | Raw TDS ADC, 0–4095; `65535` = unknown/not connected; not calibrated TDS |
| 17 | 1 | Level `0` unknown, `1` wet, `2` dry |
| 18 | 2 | CRC, little-endian |

Golden sample: node 1, session 7, sequence 0, 25.00 C, ADC 1234, wet: `4b570101010700000000000000c409d20401eb72`. Both host C++ and JS tests compare their encoder with these bytes. Unsupported version/type, bad CRC or invalid values are rejected. The stream parser re-synchronizes on magic. ACK echoes the sample with type 2 and a new CRC.

The unknown ADC value extends v1 without changing frame layout. Older v1 gateways reject it: update backend and gateway before flashing the updated node. Existing numeric samples remain unchanged; historical readings cannot be retrospectively classified as connected or floating.

One sample may be pending. Sender transmits immediately, retries at 500 ms, and drops after four transmissions and a final 500 ms wait. New samples are skipped while pending; no persistent offline queue exists. Gateway acknowledges duplicates without changing the last accepted timestamp. Same-session sequence uses unsigned modular ordering with a half-range window: zero distance is duplicate, distances `1..0x7fffffff` are newer, and the remainder are old. A changed session is refused until the previous reading has been stale for 5 s. An unknown, dry, malformed or stale tank reading cannot authorize dispensing.

UART is assumed to remain inside the enclosure between the two trusted boards. CRC protects only against accidental corruption; it does not authenticate a sender, prevent injection, or stop replay of an old session after timeout. Never expose this UART to an untrusted device or use it for remote pump commands. The current protocol carries no actuation commands. If the enclosure or wiring cannot be trusted, add provisioned cryptographic authentication and persistent anti-replay state before actuation.

Proposed cross-wiring: node GPIO25 TX → S3 GPIO1 RX; node GPIO26 RX ← S3 GPIO2 TX; common reference only after confirming the power topology. ESP GPIO is 3.3 V logic and is not 5 V tolerant. Avoid ESP32 boot straps GPIO0, 2, 5, 12 and 15 and S3 straps GPIO0, 3, 45 and 46; verify the actual boards, flash/PSRAM, pinouts and idle levels before wiring. The pump interface and independent emergency stop are separate and remain on hold.

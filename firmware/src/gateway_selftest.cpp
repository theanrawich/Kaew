#include <Arduino.h>
#include <HX711.h>
#include <U8g2lib.h>
#include <Wire.h>
#include <driver/i2s.h>
#include <freertos/queue.h>
#include <cmath>
#include <cstring>

namespace {
constexpr int HX_DT = 5, HX_SCK = 4;
constexpr int MIC_SD = 6, MIC_SCK = 7, MIC_WS = 8;
constexpr int SPEAKER_DIN = 9, SPEAKER_BCLK = 10, SPEAKER_LRC = 11;
constexpr int LINK_RX = 21, LINK_TX = 47;
constexpr uint32_t REPORT_MS = 3000;
constexpr int AUDIO_RATE = 16000;

struct ScaleSample {
  long raw;
  uint32_t at;
};
HX711 scale;
QueueHandle_t scaleSamples = nullptr;
U8G2_SSD1306_128X64_NONAME_F_HW_I2C oled{U8G2_R0, U8X8_PIN_NONE, KAEW_OLED_SCL, KAEW_OLED_SDA};
bool oledDrawn = false, micReady = false, speakerReady = false, heardPeer = false;
uint32_t lastPeer = 0, lastPing = 0, lastReport = 0;

void serviceUart() {
  static char line[6];
  static size_t length = 0;
  static bool discard = false;
  // Bound work even if the peer is still sending production binary frames.
  for (int budget = 256; budget > 0 && Serial2.available(); --budget) {
    const int byte = Serial2.read();
    if (byte == '\n') {
      if (!discard && length == sizeof(line)) {
        const bool ping = memcmp(line, "N-PING", sizeof(line)) == 0;
        if (ping || memcmp(line, "N-PONG", sizeof(line)) == 0) {
          lastPeer = millis();
          heardPeer = true;
          if (ping) Serial2.print("G-PONG\n");
        }
      }
      length = 0;
      discard = false;
    } else if (!discard && length < sizeof(line)) {
      line[length++] = static_cast<char>(byte);
    } else {
      discard = true;
    }
  }

  const uint32_t now = millis();
  if (heardPeer && now - lastPeer >= 5000) heardPeer = false;
  if (now - lastPing >= 1000) {
    lastPing = now;
    Serial2.print("G-PING\n");
  }
}

void reportUart() {
  serviceUart();
  if (heardPeer) {
    Serial.printf("UART    : PASS  heard node %lu ms ago\n",
                  static_cast<unsigned long>(millis() - lastPeer));
  } else {
    Serial.println("UART    : FAIL  no ping from node (check node GPIO21 TX -> gateway GPIO21 RX, "
                   "node GPIO47 RX <- gateway GPIO47 TX, and common GND)");
  }
}

void readScale(void *) {
  for (;;) {
    if (scale.is_ready()) {
      // HX711::read() waits again internally. Keep a disconnect race off the report loop.
      const ScaleSample sample{scale.read(), millis()};
      xQueueOverwrite(scaleSamples, &sample);
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

void reportScale() {
  static long previous = 0;
  static unsigned identical = 0;
  ScaleSample sample{};
  if (!scaleSamples || xQueuePeek(scaleSamples, &sample, 0) != pdTRUE ||
      millis() - sample.at >= 1000) {
    identical = 0;
    Serial.println("HX711   : FAIL  HX711 not ready (check DT/SCK swapped, VCC, or GND)");
    return;
  }
  const bool hadBaseline = identical != 0;
  identical = hadBaseline && sample.raw == previous ? min(identical + 1, 3u) : 1;
  previous = sample.raw;
  if (identical >= 3) {
    Serial.printf("HX711   : WARN  raw=%ld (stuck reading - check DT/SCK or load cell wiring)\n", sample.raw);
  } else if (identical == 2) {
    Serial.printf("HX711   : INFO  raw=%ld (unchanged since last report)\n", sample.raw);
  } else {
    // The first sample after startup or a disconnect only establishes a baseline.
    Serial.printf("HX711   : %s  raw=%ld\n", hadBaseline ? "PASS" : "INFO", sample.raw);
  }
}

void reportOled() {
  bool expected = false;
  unsigned found = 0;
  for (uint8_t address = 0x08; address <= 0x77; ++address) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) {
      if (found++ == 0) Serial.print("I2C     : INFO  found");
      Serial.printf(" 0x%02X", address);
      if (address == KAEW_OLED_ADDRESS) expected = true;
    }
    serviceUart();
  }
  if (found) Serial.println();

  if (expected) {
    Serial.printf("OLED    : PASS  I2C ACK at 0x%02X\n", KAEW_OLED_ADDRESS);
    if (!oledDrawn) {
      oled.setI2CAddress(KAEW_OLED_ADDRESS << 1);
      oled.begin();
      oled.clearBuffer();
      oled.setFont(u8g2_font_6x12_tf);
      oled.drawStr(4, 32, "Kaew self-test OK");
      oled.sendBuffer();
      oledDrawn = true;
    }
  } else {
    oledDrawn = false;
    if (found) {
      Serial.printf("OLED    : WARN  I2C device(s) listed above, expected 0x%02X (check address or solder jumper)\n",
                    KAEW_OLED_ADDRESS);
    } else {
      Serial.printf("OLED    : FAIL  no I2C device at 0x%02X (check SDA/SCL swapped or VCC)\n", KAEW_OLED_ADDRESS);
    }
  }
}

bool configureAudio(i2s_port_t port, bool speaker, int bclk, int ws, int data) {
  i2s_config_t config{};
  config.mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | (speaker ? I2S_MODE_TX : I2S_MODE_RX));
  config.sample_rate = AUDIO_RATE;
  config.bits_per_sample = speaker ? I2S_BITS_PER_SAMPLE_16BIT : I2S_BITS_PER_SAMPLE_32BIT;
  config.channel_format = speaker ? I2S_CHANNEL_FMT_RIGHT_LEFT : I2S_CHANNEL_FMT_ONLY_LEFT;
  config.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  config.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  config.dma_buf_count = 4;
  config.dma_buf_len = 256;
  config.tx_desc_auto_clear = speaker;
  if (i2s_driver_install(port, &config, 0, nullptr) != ESP_OK) return false;

  i2s_pin_config_t pins{};
  pins.mck_io_num = I2S_PIN_NO_CHANGE;
  pins.bck_io_num = bclk;
  pins.ws_io_num = ws;
  pins.data_in_num = speaker ? I2S_PIN_NO_CHANGE : data;
  pins.data_out_num = speaker ? data : I2S_PIN_NO_CHANGE;
  if (i2s_set_pin(port, &pins) == ESP_OK) return true;
  i2s_driver_uninstall(port);
  return false;
}

void reportMic() {
  int32_t samples[256];
  int32_t first = 0;
  size_t count = 0;
  double squares = 0;
  bool varies = false;
  for (int block = 0; micReady && block < 8; ++block) {
    size_t bytes = 0;
    if (i2s_read(I2S_NUM_0, samples, sizeof(samples), &bytes, pdMS_TO_TICKS(40)) != ESP_OK ||
        bytes != sizeof(samples)) break;
    for (const int32_t raw : samples) {
      const int32_t value = raw >> 8;
      if (count == 0) first = value;
      varies |= value != first;
      squares += static_cast<double>(value) * value;
      ++count;
    }
    serviceUart();
  }
  if (count != 8 * 256) {
    Serial.println("MIC     : FAIL  mic I2S init/read failed (check SD/SCK/WS and tie L/R to GND)");
  } else if (!varies) {
    Serial.println("MIC     : FAIL  mic silent/constant (check SD/SCK/WS or tie L/R to GND)");
  } else {
    Serial.printf("MIC     : PASS  RMS=%.1f (24-bit counts)\n", sqrt(squares / count));
  }
}

bool speakerPlayed = false;

bool writeTone(int durationMs, int amplitude) {
  constexpr int freq = 900;
  const int frames = AUDIO_RATE * durationMs / 1000;
  int16_t stereo[128 * 2];
  for (int offset = 0; offset < frames; offset += 128) {
    const int n = min(128, frames - offset);
    for (int i = 0; i < 128; ++i) {
      const int16_t sample = i < n
          ? static_cast<int16_t>(amplitude * sinf(6.2831853f * freq * (offset + i) / AUDIO_RATE))
          : 0;
      stereo[2 * i] = stereo[2 * i + 1] = sample;
    }
    size_t written = 0;
    if (i2s_write(I2S_NUM_1, stereo, sizeof(stereo), &written, pdMS_TO_TICKS(40)) != ESP_OK ||
        written != sizeof(stereo)) {
      i2s_zero_dma_buffer(I2S_NUM_1);
      return false;
    }
    serviceUart();
  }
  return true;
}

// Three 150 ms beeps with 150 ms gaps, moderate volume, once at boot only.
bool playBootBeeps() {
  if (!speakerReady) return false;
  constexpr int amplitude = 5000;  // ~15% of full scale
  for (int i = 0; i < 3; ++i) {
    if (!writeTone(150, amplitude)) return false;
    if (!writeTone(150, 0)) return false;
  }
  i2s_zero_dma_buffer(I2S_NUM_1);
  return true;
}

void reportSpeaker() {
  if (!speakerReady || !speakerPlayed) {
    Serial.println("SPEAKER : FAIL  speaker I2S init/write failed (check DIN/BCLK/LRC)");
    return;
  }
  Serial.println("SPEAKER : INFO  3 beeps played at boot");
}
}  // namespace

void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, LINK_RX, LINK_TX);
  scale.begin(HX_DT, HX_SCK);
  scaleSamples = xQueueCreate(1, sizeof(ScaleSample));
  if (scaleSamples) xTaskCreate(readScale, "hx711", 2048, nullptr, 1, nullptr);
  Wire.begin(KAEW_OLED_SDA, KAEW_OLED_SCL);
  Wire.setTimeOut(8);
  micReady = configureAudio(I2S_NUM_0, false, MIC_SCK, MIC_WS, MIC_SD);
  speakerReady = configureAudio(I2S_NUM_1, true, SPEAKER_BCLK, SPEAKER_LRC, SPEAKER_DIN);

  Serial.println("\nKaew GATEWAY wiring self-test | USB Serial 115200");
  Serial.println("Module   | Pin(s)");
  Serial.println("HX711    | DT GPIO5, SCK GPIO4");
  Serial.println("INMP441  | SD GPIO6, SCK GPIO7, WS GPIO8, L/R to GND");
  Serial.println("MAX98357 | DIN GPIO9, BCLK GPIO10, LRC GPIO11");
  Serial.printf("OLED     | SDA GPIO%d, SCL GPIO%d, address 0x%02X\n",
                KAEW_OLED_SDA, KAEW_OLED_SCL, KAEW_OLED_ADDRESS);
  Serial.println("UART     | node GPIO21 TX -> gateway GPIO21 RX");
  Serial.println("         | node GPIO47 RX <- gateway GPIO47 TX; common GND");
  speakerPlayed = playBootBeeps();
  lastReport = millis();
}

void loop() {
  serviceUart();
  if (millis() - lastReport >= REPORT_MS) {
    lastReport = millis();
    Serial.println("\n====== Kaew GATEWAY self-test =======");
    reportScale();
    reportOled();
    reportMic();
    reportSpeaker();
    reportUart();
    Serial.println("=====================================");
  }
  delay(1);
}

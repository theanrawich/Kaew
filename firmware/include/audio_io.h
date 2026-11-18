#pragma once
#include <Arduino.h>
#include <driver/i2s.h>
#include <cstring>
#include "speech_capture.h"

// Candidate pins only; verify board, I2S channel and audio module wiring physically.
class AudioIO {
  static constexpr size_t dmaBufferCount = 4;
  static constexpr size_t dmaSamples = 256;
  bool rx_=false,tx_=false;
  static bool configure(i2s_port_t port, i2s_mode_t mode, int bits, int bclk, int ws, int in, int out) {
    i2s_config_t c{}; c.mode=mode; c.sample_rate=SpeechCapture::sampleRate; c.bits_per_sample=static_cast<i2s_bits_per_sample_t>(bits);
    const bool isSpeaker = (mode & I2S_MODE_TX) != 0;
    c.channel_format = isSpeaker ? I2S_CHANNEL_FMT_RIGHT_LEFT : I2S_CHANNEL_FMT_ONLY_LEFT;
    c.communication_format = I2S_COMM_FORMAT_STAND_I2S;
    c.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
    c.dma_buf_count = dmaBufferCount;
    c.dma_buf_len = dmaSamples;
    c.tx_desc_auto_clear = isSpeaker;
    if(i2s_driver_install(port,&c,0,nullptr)!=ESP_OK) return false;
    i2s_pin_config_t p{}; p.mck_io_num=I2S_PIN_NO_CHANGE; p.bck_io_num=bclk; p.ws_io_num=ws; p.data_out_num=out; p.data_in_num=in;
    if(i2s_set_pin(port,&p)!=ESP_OK) { i2s_driver_uninstall(port); return false; }
    return true;
  }
public:
  bool beginMicrophone() {
    rx_ = configure(I2S_NUM_0, static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_RX),
                    32, 7, 8, 6, I2S_PIN_NO_CHANGE);
    return rx_;
  }

  bool begin() {
    beginMicrophone();
    tx_=configure(I2S_NUM_1,static_cast<i2s_mode_t>(I2S_MODE_MASTER|I2S_MODE_TX),16,10,11,I2S_PIN_NO_CHANGE,9);
    if(!rx_ || !tx_) { stop(); return false; }
    return rx_ && tx_;
  }

  size_t readMicrophoneRaw(int32_t *out, size_t capacity, TickType_t timeout) {
    if (!rx_ || !out || !capacity) return 0;
    size_t bytes = 0;
    if (i2s_read(I2S_NUM_0, out, capacity * sizeof(*out), &bytes, timeout) != ESP_OK ||
        bytes % sizeof(*out) != 0) return 0;
    return bytes / sizeof(*out);
  }

  // Call from the speech worker. Explicit stereo slots avoid legacy mono
  // sample swapping and serve either channel selection on the MAX98357A.
  bool play(const uint8_t *pcm, size_t bytes) {
    if (!tx_ || !pcm || bytes == 0 || bytes % 2 != 0) return false;
    uint16_t stereo[dmaSamples * 2];
    const uint32_t start = millis();
    const uint32_t playbackTimeout = bytes / (2 * (SpeechCapture::sampleRate / 1000)) + 2000;
    for (size_t offset = 0; offset < bytes;) {
      if (millis() - start >= playbackTimeout) {
        i2s_zero_dma_buffer(I2S_NUM_1);
        return false;
      }
      const size_t samples = std::min((bytes - offset) / 2, size_t{dmaSamples});
      for (size_t i = 0; i < samples; ++i) {
        uint16_t sample;
        std::memcpy(&sample, pcm + offset + i * 2, sizeof sample);
        stereo[i * 2] = stereo[i * 2 + 1] = sample;
      }
      if (!writeSpeaker(stereo, samples * 2 * sizeof(*stereo))) return false;
      offset += samples * 2;
    }

    // Fill the ring with silence so audio already queued has left the DMA
    // before capture resumes. Underflow also sends silence.
    std::memset(stereo, 0, sizeof stereo);
    for (size_t i = 0; i < dmaBufferCount; ++i)
      if (!writeSpeaker(stereo, sizeof stereo)) return false;
    return true;
  }

  void stop() {if(rx_)i2s_driver_uninstall(I2S_NUM_0);if(tx_)i2s_driver_uninstall(I2S_NUM_1);rx_=tx_=false;}
 private:
  bool writeSpeaker(const uint16_t *samples, size_t size) {
    size_t written = 0;
    if (i2s_write(I2S_NUM_1, samples, size, &written, pdMS_TO_TICKS(100)) == ESP_OK &&
        written == size) return true;
    i2s_zero_dma_buffer(I2S_NUM_1);
    return false;
  }
};

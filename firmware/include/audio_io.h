#pragma once
#include <Arduino.h>
#include <driver/i2s.h>
#include "audio_processing.h"

// Candidate pins only; verify board, I2S channel and audio module wiring physically.
class AudioIO {
  bool rx_=false,tx_=false;
  static bool configure(i2s_port_t port, i2s_mode_t mode, int bits, int bclk, int ws, int in, int out) {
    i2s_config_t c{}; c.mode=mode; c.sample_rate=16000; c.bits_per_sample=static_cast<i2s_bits_per_sample_t>(bits);
    c.channel_format=I2S_CHANNEL_FMT_ONLY_LEFT; c.communication_format=I2S_COMM_FORMAT_STAND_I2S;
    c.intr_alloc_flags=ESP_INTR_FLAG_LEVEL1; c.dma_buf_count=4; c.dma_buf_len=256; c.use_apll=false;
    if(i2s_driver_install(port,&c,0,nullptr)!=ESP_OK) return false;
    i2s_pin_config_t p{}; p.mck_io_num=I2S_PIN_NO_CHANGE; p.bck_io_num=bclk; p.ws_io_num=ws; p.data_out_num=out; p.data_in_num=in;
    if(i2s_set_pin(port,&p)!=ESP_OK) { i2s_driver_uninstall(port); return false; }
    return true;
  }
public:
  bool begin() {
    rx_=configure(I2S_NUM_0,static_cast<i2s_mode_t>(I2S_MODE_MASTER|I2S_MODE_RX),32,4,5,6,I2S_PIN_NO_CHANGE);
    tx_=configure(I2S_NUM_1,static_cast<i2s_mode_t>(I2S_MODE_MASTER|I2S_MODE_TX),16,10,11,I2S_PIN_NO_CHANGE,12);
    if(!rx_ || !tx_) { stop(); return false; }
    return rx_ && tx_;
  }
  size_t readMicrophone(int16_t *out,size_t capacity) {
    if(!rx_ || !out || !capacity)return 0; int32_t raw[128]; size_t bytes=0;
    size_t n=capacity<128?capacity:128;
    if(i2s_read(I2S_NUM_0,raw,n*sizeof(int32_t),&bytes,0)!=ESP_OK)return 0;
    for(size_t i=0;i<bytes/sizeof(int32_t);i++)out[i]=pcm32to16(raw[i]); return bytes/sizeof(int32_t);
  }
  size_t play(const int16_t *samples,size_t count) {
    if(!tx_ || !samples || !count)return 0; size_t bytes=0;
    if(i2s_write(I2S_NUM_1,samples,count*sizeof(int16_t),&bytes,0)!=ESP_OK)return 0;
    return bytes/sizeof(int16_t);
  }
  void stop() {if(rx_)i2s_driver_uninstall(I2S_NUM_0);if(tx_)i2s_driver_uninstall(I2S_NUM_1);rx_=tx_=false;}
};

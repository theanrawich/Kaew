#include <Arduino.h>
#include <DallasTemperature.h>
#include <OneWire.h>
#include "sensor_publisher.h"

namespace
{
  constexpr int TEMP_PIN = 6;
  constexpr int TDS_PIN = KAEW_TDS_PIN;
  constexpr int LEVEL_PIN = KAEW_LEVEL_PIN;

  constexpr float VREF = 3.3f; // แรงดันอ้างอิง ADC ของ ESP32-S3 (3.3V)
  constexpr int SCOUNT = 30;   // จำนวนตัวอย่างสำหรับ Median Filter

  OneWire oneWire(TEMP_PIN);
  DallasTemperature temperature(&oneWire);

  int getMedianNum(const int bArray[], int iFilterLen)
  {
    int bTab[SCOUNT];
    for (int i = 0; i < iFilterLen; i++)
    {
      bTab[i] = bArray[i];
    }
    for (int j = 0; j < iFilterLen - 1; j++)
    {
      for (int i = 0; i < iFilterLen - j - 1; i++)
      {
        if (bTab[i] > bTab[i + 1])
        {
          const int bTemp = bTab[i];
          bTab[i] = bTab[i + 1];
          bTab[i + 1] = bTemp;
        }
      }
    }
    if ((iFilterLen & 1) > 0)
    {
      return bTab[(iFilterLen - 1) / 2];
    }
    return (bTab[iFilterLen / 2] + bTab[iFilterLen / 2 - 1]) / 2;
  }

  float readTdsPpm(int pin, float waterTempC, float *outVoltage = nullptr)
  {
    int analogBuffer[SCOUNT];
    for (int i = 0; i < SCOUNT; i++)
    {
      analogBuffer[i] = analogRead(pin);
      delay(5); // เว้นระยะอ่าน 5 ms ต่อตัวอย่าง (รวม 150 ms)
    }

    // แปลงค่า ADC 12-bit (0-4095) เป็นแรงดัน (Volt)
    const float averageVoltage = getMedianNum(analogBuffer, SCOUNT) * VREF / 4096.0f;
    if (outVoltage != nullptr)
    {
      *outVoltage = averageVoltage;
    }

    // ชดเชยค่าตามอุณหภูมิน้ำจริง (อ้างอิงที่ 25°C)
    const float compensationCoefficient = 1.0f + 0.02f * (waterTempC - 25.0f);
    const float compensationVoltage = averageVoltage / compensationCoefficient;

    // แปลงแรงดันเป็นค่า TDS (ppm)
    float tdsValue = (133.42f * compensationVoltage * compensationVoltage * compensationVoltage - 255.86f * compensationVoltage * compensationVoltage + 857.39f * compensationVoltage) * 0.5f;

    return tdsValue < 0.0f ? 0.0f : tdsValue;
  }
} // namespace

void setup()
{
  Serial.begin(115200);
  temperature.begin();
  analogReadResolution(12);

  if (TDS_PIN >= 0)
  {
    pinMode(TDS_PIN, INPUT);
    analogSetPinAttenuation(TDS_PIN, ADC_11db);
  }
  if (LEVEL_PIN >= 0)
  {
    pinMode(LEVEL_PIN, INPUT);
  }

#if __has_include("gateway_wifi.h")
  beginSensorPublisher();
#else
  Serial.println("Cloud upload disabled: configure include/gateway_wifi.h");
#endif
}

void loop()
{
  const uint32_t started = millis();

  // 1. อ่านค่าอุณหภูมิน้ำจาก DS18B20
  temperature.requestTemperatures();
  const float tempC = temperature.getTempCByIndex(0);

  char tempText[12] = "unknown";
  const bool validTemperature = tempC >= -55.0f && tempC <= 125.0f;
  if (validTemperature)
  {
    snprintf(tempText, sizeof tempText, "%.2f", tempC);
  }

  // 2. อ่านค่า TDS และคำนวณเป็น ppm (ใช้อุณหภูมิจริงถ้าเซ็นเซอร์ปกติ)
  char tdsText[12] = "unknown";
  float tdsVoltage = 0.0f;
  float tdsPpm = -1.0f;
  if (TDS_PIN >= 0)
  {
    const float compensationTemp = validTemperature ? tempC : 25.0f;
    tdsPpm = readTdsPpm(TDS_PIN, compensationTemp, &tdsVoltage);
    snprintf(tdsText, sizeof tdsText, "%.1f", tdsPpm);
  }

  // 3. อ่านค่าระดับน้ำ
  const bool wet = LEVEL_PIN >= 0 && digitalRead(LEVEL_PIN) == KAEW_LEVEL_WET_STATE;
  const char *waterLevel = "unknown";
  if (LEVEL_PIN >= 0)
  {
    waterLevel = wet ? "wet" : "dry";
  }

  Serial.printf("temp_c=%s tds_v=%.2f tds_ppm=%s water_level=%s\n",
                tempText, tdsVoltage, tdsText, waterLevel);

#if __has_include("gateway_wifi.h")
  if (tdsPpm >= 0.0f)
    publishSensor(tdsPpm, "ppm", "TDS");
  if (validTemperature)
    publishSensor(tempC, "°C", "Temperature");
  if (LEVEL_PIN >= 0)
    publishSensor(wet ? 1 : 0, "", "Water Level");
#endif

  const uint32_t elapsed = millis() - started;
  if (elapsed < 1000)
    delay(1000 - elapsed);
}
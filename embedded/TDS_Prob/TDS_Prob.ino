#define TdsSensorPin 4
#define VREF 3.3
#define ADC_RES 4095.0
#define SCOUNT 30
#include <DS18B20.h>

DS18B20 ds(6);
int analogBuffer[SCOUNT];
int analogBufferTemp[SCOUNT];
int analogBufferIndex = 0;

float averageVoltage = 0, tdsValue = 0, temperature = ds.getTempC();
float kValue = 2; // ตัวคูณปรับเทียบ (ปรับเลขนี้ถ้าค่า ppm สูงหรือต่ำกว่าความจริง)

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
}

void loop() {
  static unsigned long analogSampleTimepoint = millis();
  if (millis() - analogSampleTimepoint > 40U) {
    analogSampleTimepoint = millis();
    analogBuffer[analogBufferIndex] = analogRead(TdsSensorPin);
    analogBufferIndex++;
    if (analogBufferIndex == SCOUNT) {
      analogBufferIndex = 0;
    }
  }

  static unsigned long printTimepoint = millis();
  if (millis() - printTimepoint > 800U) {
    printTimepoint = millis();
    for (int i = 0; i < SCOUNT; i++) {
      analogBufferTemp[i] = analogBuffer[i];
    }

    int medianRaw = getMedianNum(analogBufferTemp, SCOUNT);
    averageVoltage = medianRaw * (float)VREF / ADC_RES;

    float compensationCoefficient = 1.0 + 0.02 * (temperature - 25.0);
    float compensationVoltage = (averageVoltage / compensationCoefficient) * kValue;

    tdsValue = (133.42 * compensationVoltage * compensationVoltage * compensationVoltage
              - 255.86 * compensationVoltage * compensationVoltage
              + 857.39 * compensationVoltage) * 0.5;

    Serial.print("Raw ADC: ");
    Serial.print(medianRaw);
    Serial.print(" | Voltage: ");
    Serial.print(averageVoltage, 2);
    Serial.print(" V | TDS: ");
    Serial.print(tdsValue, 0);
    Serial.println(" ppm");
  }
}

int getMedianNum(int bArray[], int iFilterLen) {
  int bTab[iFilterLen];
  for (int i = 0; i < iFilterLen; i++) {
    bTab[i] = bArray[i];
  }
  for (int j = 0; j < iFilterLen - 1; j++) {
    for (int i = 0; i < iFilterLen - j - 1; i++) {
      if (bTab[i] > bTab[i + 1]) {
        int bTemp = bTab[i];
        bTab[i] = bTab[i + 1];
        bTab[i + 1] = bTemp;
      }
    }
  }
  if ((iFilterLen & 1) > 0) {
    return bTab[(iFilterLen - 1) / 2];
  } else {
    return (bTab[iFilterLen / 2] + bTab[iFilterLen / 2 - 1]) / 2;
  }
}

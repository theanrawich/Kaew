#define TdsSensorPin 7  // GPIO34 ใช้ได้กับ ESP32 รุ่นคลาสสิก
#define SCOUNT 30

int voltageBuffer[SCOUNT];
int bufferTemp[SCOUNT];
int bufferIndex = 0;
int samplesFilled = 0;

float temperature = 25.0;       // ใส่อุณหภูมิน้ำจริง ถ้ามีเซนเซอร์วัด
float calibrationFactor = 1;  // ปรับหลังเทียบกับน้ำมาตรฐาน

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  analogSetPinAttenuation(TdsSensorPin, ADC_11db);
}

void loop() {
  static unsigned long sampleTimepoint = millis();
  if (millis() - sampleTimepoint >= 40U) {
    sampleTimepoint = millis();

    // อ่านแรงดันที่ ADC calibrate แล้ว หน่วย mV
    voltageBuffer[bufferIndex] = analogReadMilliVolts(TdsSensorPin);
    bufferIndex = (bufferIndex + 1) % SCOUNT;

    if (samplesFilled < SCOUNT) {
      samplesFilled++;
    }
  }

  static unsigned long printTimepoint = millis();
  if (millis() - printTimepoint >= 800U && samplesFilled == SCOUNT) {
    printTimepoint = millis();

    for (int i = 0; i < SCOUNT; i++) {
      bufferTemp[i] = voltageBuffer[i];
    }

    int medianMilliVolts = getMedianNum(bufferTemp, SCOUNT);
    float voltage = medianMilliVolts / 1000.0f;

    float compensationCoefficient =
        1.0f + 0.02f * (temperature - 25.0f);
    float compensationVoltage = voltage / compensationCoefficient;

    float tdsBase =
        (133.42f * compensationVoltage * compensationVoltage * compensationVoltage
        - 255.86f * compensationVoltage * compensationVoltage
        + 857.39f * compensationVoltage) * 0.5f;

    float tdsValue = tdsBase * calibrationFactor;

    Serial.print("ADC voltage: ");
    Serial.print(voltage, 3);
    Serial.print(" V | TDS: ");
    Serial.print(tdsValue, 0);
    Serial.println(" ppm");
  }
}

int getMedianNum(int values[], int length) {
  int sorted[SCOUNT];

  for (int i = 0; i < length; i++) {
    sorted[i] = values[i];
  }

  for (int j = 0; j < length - 1; j++) {
    for (int i = 0; i < length - j - 1; i++) {
      if (sorted[i] > sorted[i + 1]) {
        int temp = sorted[i];
        sorted[i] = sorted[i + 1];
        sorted[i + 1] = temp;
      }
    }
  }

  if (length % 2 == 1) {
    return sorted[length / 2];
  }

  return (sorted[length / 2] + sorted[length / 2 - 1]) / 2;
}
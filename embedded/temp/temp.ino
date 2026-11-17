#include <DS18B20.h>

DS18B20 ds(6);

void setup() {
  Serial.begin(9600);
  Serial.print("Devices: ");
  Serial.println(ds.getNumberOfDevices());
  Serial.println();
}

void loop() {


  Serial.print("Temperature: ");
  Serial.print(ds.getTempC());
  Serial.print(" C / ");
  Serial.print(ds.getTempF());
  Serial.println(" F");
  Serial.println();

  delay(100);
}

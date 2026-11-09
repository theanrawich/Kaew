# Firmware commissioning checkpoint

These two programs are incomplete and **must not be used to operate a pump**. Pin assignments are proposals for candidate boards, not verified wiring instructions. The gateway keeps pump and emergency-stop pins disabled and never issues a start request; the physical emergency stop must independently remove pump power. Do not connect the TDS or level interface until voltage and pinout are verified.

The node periodically prints DS18B20 readings and uncalibrated ADC counts over its USB serial console. A disconnected temperature sensor is reported invalid. Level is unknown while its interface is disabled. The gateway prints raw HX711 counts; it does not derive grams without a real calibration. These diagnostic outputs are not a network link.

Install PlatformIO Core and run `pio run -d firmware`. The pinned platform and libraries are in `platformio.ini`. The S3 board definition is a candidate for N16R8; verify the received board and flash/PSRAM configuration before flashing.

The portable controller can be exercised on a host with:

```
g++ -std=c++17 -Ifirmware/include firmware/test/safety_test.cpp -o firmware/test/safety_test.exe
firmware/test/safety_test.exe
```

All limits in `safety.h` are illustrative. The controller does not yet cover independent sensor freshness for the node, calibrated cup detection, weight-change plausibility, driver feedback, brownout, persistence or hardware interlocks. No test here demonstrates actual pump shutoff or water safety. See `docs/EXECUTION.md` for the continuation point.

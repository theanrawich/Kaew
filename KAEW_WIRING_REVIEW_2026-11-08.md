# Kaew — ตารางสายและตรวจความเข้ากันได้

ตรวจเอกสาร 8 พ.ย. 2026 · **แบบเสนอสำหรับทบทวนเท่านั้น ห้ามใช้เป็นแบบอนุมัติจ่ายไฟหรือสั่งทำสาย** ตัวเลข GPIO ถอดจาก `.work/kaew-wiring-data.cjs` ซึ่งเป็นต้นทางผัง 3D ในเครื่อง; บอร์ดและโมดูลร้านยังไม่ได้วัดหรือยืนยัน revision, power path และ pinout. ขีดจำกัดที่มีหลักฐานของชิปไม่ใช่การรับรองบอร์ด generic ทั้งแผง

## นิยามจุดร่วม

- `5V_CTL` = output buck ที่ตั้งและวัด 5 V ภายใต้โหลดแล้ว; `GND_CTL` = return ภาคควบคุม; `3V3_G` และ `3V3_N` = output regulator 3.3 V ของ gateway และ node ตามลำดับ หลังตรวจว่าจ่ายกระแสได้พอ ไม่ใช่ GPIO
- บอร์ดแต่ละตัวรับไฟจาก USB **หรือ** 5V_CTL ตามวงจรของบอร์ดจริง; จนกว่าจะทราบ power path ไม่เสียบพร้อมกัน ใช้จุดแยกสายที่เหมาะสม ไม่ยัดสายหลายเส้นลงรูเดียว และตรวจไม่ต่อ 12 V เข้า 5 V/3.3 V
- หากสองบอร์ดและแอมป์ใช้ buck เดียวกัน ให้ return ของ buck ไปยัง GND ของแต่ละโหลด; ข้อเสนอนี้ไม่ยืนยันว่าจ่ายไฟร่วมกับแหล่งปั๊มที่ยังไม่รู้ได้หรือไม่ ไม่ผูกกราวด์ปั๊ม/logic จนทราบ topology และ isolation ที่ต้องการ
- ปุ่มหยุดและวงจรปั๊มยัง **HOLD**: เส้น GPIO ด้านล่างเป็นการจองขา ไม่ใช่วงจรตัดพลังงานจริง การตัดกำลังต้องไม่พึ่ง MCU และต้องป้องกันการเริ่มเองเมื่อคืนไฟ พร้อมทดสอบการไหลต่อหลังหยุด

## สาย Gateway — ESP32-S3 N16R8

GPIO เป็นชื่อสัญญาณ ไม่ใช่หมายเลขขานับจากขอบ PCB: เทียบสกรีนกับรุ่นที่ได้รับทุกครั้ง ตาราง [DevKitC-1 v1.1](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html) เป็นบอร์ดอ้างอิง ไม่ยืนยันว่าบอร์ดร้านต่อวงจรเหมือนกัน

| จาก | ไป | สถานะและเงื่อนไข |
|---|---|---|
| 5V_CTL / GND_CTL | S3 5V / GND | เสนอ; วัดขั้วและ 5 V ก่อนต่อ ตรวจ power path และโหลดจริง |
| S3 3V3 / GND | จุดแยก 3V3_G / GND_CTL | เสนอ; ตรวจความสามารถ regulator และแรงดันขณะโหลด peak |
| 3V3_G / GND_CTL | OLED VCC / GND | เสนอ; ตรวจว่า OLED revision นี้รองรับ 3.3 V และ pull-up อยู่ที่ 3.3 V |
| S3 GPIO8 / GPIO9 | OLED SDA / SCL | เสนอ I²C; ตรวจชื่อขาและ pull-up บนโมดูล ไม่อิงลำดับในภาพ |
| 3V3_G / GND_CTL | HX711 VCC / GND | เสนอ; ตรวจว่า analog/digital supplies ของ breakout ถูกต้องและ DOUT ไม่เกิน 3.3 V |
| HX711 DOUT / DT | S3 GPIO17 | เสนอ; input ข้อมูล 3.3 V |
| S3 GPIO18 | HX711 PD_SCK / SCK | เสนอ; ตรวจ timing driver จริงตาม datasheet |
| HX711 E+, E−, A+, A− | load cell excitation+, excitation−, signal+, signal− ตามลำดับ | ต้องยืนยันสายและวงจรจากผู้ผลิต/การวัด ห้ามเชื่อสีสาย generic |
| 3V3_G / GND_CTL | INMP441 VDD / GND | เสนอ 3.3 V; ตรวจสกรีน breakout จริง |
| S3 GPIO4 / GPIO5 | INMP441 SCK / WS | เสนอ I²S receive clock |
| INMP441 SD | S3 GPIO6 | เสนอ I²S receive data |
| GND_CTL | INMP441 L/R | เลือก left channel; firmware ต้องตั้งให้ตรง |
| 5V_CTL / GND_CTL | MAX98357A VIN / GND | เสนอ; ตรวจ breakout และงบกระแสแอมป์จริง รวม transient |
| S3 GPIO10 / GPIO11 / GPIO12 | MAX98357A BCLK / LRC / DIN | เสนอ I²S transmit; ตรวจ SD/MODE และ gain ตามบอร์ดจริง |
| MAX98357A SPK+ / SPK− | ลำโพง 4 Ω 3 W ทั้งสองขั้ว | output แบบ bridge; ห้ามนำขั้วลำโพงใดต่อ GND ตรวจ load, gain, ความร้อนและระดับเสียง |
| S3 GPIO15 | ภาค interface ปั๊ม CTRL | **HOLD**: จองขาเท่านั้น ไม่มีค่าขับหรือ topology ที่ยืนยัน |
| interface stop status | S3 GPIO16 | **HOLD**: ใช้อ่านสถานะหลังออกแบบ interface 3.3 V; ไม่ใช่การตัดกำลัง |

ชื่อ GPIO 4, 5, 6, 8–12, 15–18 มีในผังบอร์ดอ้างอิง แต่การมีชื่อขาไม่ได้พิสูจน์ว่า breakout ผู้ขายว่างหรือ peripheral driver ทำงานพร้อมกันได้ ต้องตรวจ firmware และบอร์ดจริง. ขา GPIO0, GPIO3, GPIO45 และ GPIO46 เป็น strapping; GPIO19/20 เกี่ยวกับ USB และ GPIO33–37 อาจถูกใช้โดย octal flash/PSRAM ตามโมดูล หลีกเลี่ยงจนตรวจ revision จาก [Espressif](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-reference/peripherals/gpio.html)

## สาย Sensor Node — ESP32 DevKit 30 ขา

| จาก | ไป | สถานะและเงื่อนไข |
|---|---|---|
| 5V_CTL / GND_CTL | Node 5V/VIN / GND | เสนอ; ชื่อ VIN/5V และ power path ขึ้นกับบอร์ดจริง ต้องตรวจ ไม่ใช้นับลำดับรู |
| Node 3V3 / GND | จุดแยก 3V3_N / GND_CTL | เสนอ; ตรวจ regulator และกระแส |
| 3V3_N / GND_CTL | DS18B20 VDD / GND | เสนอจ่ายแบบสามสาย ตรวจสาย probe ไม่เดาสี |
| DS18B20 DQ | Node GPIO4 | เสนอ; DQ อยู่จุดร่วมกับตัวต้านทานด้านล่าง |
| 3V3_N → R 4.7 kΩ → DQ | Node GPIO4 / DS18B20 DQ | เสนอ pull-up; [Analog Devices](https://support.analog.com/en-US/knowledgebase/article/000094969) ระบุ 4.7 kΩ สำหรับ 3.3 V และ 5 V |
| 3V3_N / GND_CTL | TDS VCC / GND | **HOLD**: generic ต้องยืนยันว่ารองรับแรงดันนี้ |
| TDS OUT → วงจรปรับระดับ/ป้องกัน → Node GPIO34 | ADC1 input | **HOLD**: วัด output สูงสุดทุกสภาวะก่อนออกแบบวงจรและต่อ GPIO; ไม่ใช้สเปกของ DFRobot อ้างเป็นสเปก generic |
| 5V_CTL / GND_CTL | XKC-Y25 NPN / interface | **HOLD**: ตรวจรุ่น, pinout และแรงดันจริงก่อนต่อ |
| XKC interface OUT3V3 | Node GPIO27 | **HOLD**: ต้องพิสูจน์รูปแบบ output และออกแบบ interface ก่อน ห้ามป้อน 5–12 V เข้า GPIO |

ESP32 GPIO34 เป็น input-only และ ADC1; [Espressif](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32/schematic-checklist.html) แนะนำ ADC1 เมื่อใช้ Wi-Fi. Node → gateway ยังเป็น wireless proposal ไม่มีสายสื่อสารหรือ ACK/retry ที่พิสูจน์แล้ว

## ประเด็นที่การตรวจเอกสารพบ

1. **HX711 timing และความหน่วง:** [datasheet HX711](https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/hx711_english.pdf) ระบุ PD_SCK high เกิน 60 µs เข้าสู่ power-down และ rate 10/80 samples/s ตามขา RATE ต้องตรวจบอร์ดร้านและวัดอัตราจริง รวม filtering และ task scheduling; ห้ามอนุมานว่าตรวจยกแก้วได้ทันเวลาจากการมี GPIO เพียงอย่างเดียว หากขา RATE ถูกต่อคงที่หรือ filter ช้าอาจกระทบ safety
2. **INMP441:** [datasheet TDK](https://invensense.tdk.com/wp-content/uploads/2015/02/INMP441.pdf) ระบุช่วงจ่ายชิปและ interface ดิจิทัล; บอร์ดต้องตรวจว่ามี regulator หรือวงจรเพิ่ม ไม่ถือว่าทุก breakout รับ 5 V ได้
3. **MAX98357A กับโหลด 4 Ω 3 W:** [Analog Devices](https://www.analog.com/en/products/max98357a.html) ระบุ IC จ่ายได้ถึง 3.2 W ที่ 5 V/4 Ω ภายใต้เงื่อนไขระบุ จึงต้องจำกัดระดับสัญญาณและทดสอบกำลังจริง/ความร้อน ไม่อ้างว่าลำโพง 3 W ทนการเปิดสูงสุดต่อเนื่องได้
4. **งบไฟไม่ปิด:** 12 V × 3 A = 36 W เป็นพิกัดที่ระบุของ adapter ภาคควบคุม ไม่ใช่พลังงานที่รับประกันได้ที่ 5 V หรือใช้ร่วมปั๊มได้ กระแสขณะบูต/Wi-Fi สองบอร์ด, amplifier, buck losses, peak และ current limit ยังไม่ทราบ จึงเลือกฟิวส์/สาย/จุดตัดจากยอดนี้ไม่ได้
5. **จุดที่ยังไม่มีแบบ:** การควบคุมและตัดกำลังปั๊ม, ฟิวส์/ไดโอด, protection TDS, interface XKC, ตรวจการจ่ายไฟ/กราวด์ร่วม และการไม่เริ่มเองหลังปล่อย stop ต้องกำหนดจากสเปกอุปกรณ์จริงและทดสอบแยก ไม่ควรซื้อ D4184/ปุ่มโดยถือว่าเข้ากันได้แล้ว

## ตรวจสอบก่อนนำไปประกอบ

1. ยืนยัน SKU/revision และภาพสกรีนทั้งสองด้านของทุกบอร์ด; เทียบชื่อขาและวัดระดับ output โดยไม่ต่อ GPIO
2. ตรวจ power path, กระแสโหลดและภาวะไฟขัดข้อง; คำนวณพิกัดสาย, ฟิวส์และสวิตช์จากโหลดที่วัด/ระบุจริง
3. จัดทำ schematic กำลังและ safety ที่ตรวจทานได้ พร้อม BOM วงจร; ตรวจ physical stop แบบตัดกำลังจริง และ reset ด้วยคำสั่งใหม่
4. ใช้ `KAEW_TEST_RECORD_TEMPLATE.md` บันทึก continuity, polarity, sensor timing, stop, การรั่วและการทำงานร่วม; ให้ TA/ผู้สอนตรวจส่วนไฟบ้านตามโจทย์ก่อน demo

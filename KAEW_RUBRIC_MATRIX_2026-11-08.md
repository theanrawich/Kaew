# Kaew — ตารางเกณฑ์และหลักฐานที่ต้องสร้าง

ตรวจ 8 พ.ย. 2026 จาก [โจทย์รายวิชาต้นฉบับ](https://docs.google.com/document/d/1eBUKyIknXkPH_oJqtiS-Vm4aKlzjjkmrdMn4oYDUgSw/edit) และไฟล์โครงการที่มีในเครื่อง เอกสารต้นฉบับมีเวลาแก้ไขล่าสุด 8 พ.ย. 11:30 เวลาไทย การตรวจนี้ไม่ยืนยันประกาศแยกใน MyCourseVille, การส่งงาน หรือการอนุมัติจากผู้สอน และไม่ใช่การให้คะแนนแทนอาจารย์

สถานะหลักฐาน: **มีร่าง** = เอกสาร/แบบจำลอง; **รอพิสูจน์** = ยังไม่พบผลทดสอบหรือระบบทำงานจริงใน workspace ไม่ใช่ข้อยืนยันว่าไม่มีผลงานที่อื่น หลักฐานก่อนซื้อไม่แทน hardware demo

## ข้อกำหนดขั้นต่ำ M1–M8

| ข้อ | จะทำอย่างไร | หลักฐานที่ต้องสร้าง / สถานะ |
|---|---|---|
| M1: ≥5 sensor types, node ≥2 และ gateway ≥2 | node: TDS, DS18B20, level; gateway: load cell/HX711 และ microphone | ผังเสนอเท่านั้น; ต้องต่อและใช้ข้อมูลจริงทั้งห้าชนิด กระจายตามบอร์ดที่ต่อสายจริง เหลือจำนวนพอดี ไม่มี flow sensor หรือปุ่มนับเพิ่ม |
| M2: ≥1 actuator | gateway ควบคุมปั๊ม | ต้องพิสูจน์ว่าควบคุมปั๊มที่ได้รับจริงได้; ลำโพงไม่ใช่ actuator ตามนิยาม |
| M3: node → gateway | node ส่ง readings พร้อม ID/status ไป gateway | ยังไม่มี firmware/การส่งจริง ต้องแสดงต้นทาง ปลายทาง และค่าที่สอดคล้องกัน |
| M4: AI closed loop | โมเดลเสนอปริมาณ/เวลาเตือน; controller จำกัดด้วย safety bounds และบันทึกค่าที่ใช้ | ยังไม่มี provider/model หรือหลักฐาน AI มีผลตัดสินใจจริง; fixed thresholds และปุ่ม preset ไม่ใช่ AI |
| M5: raw data ไป cloud และ dashboard | บันทึก sensor readings พร้อมเวลา/ID/หน่วย/สถานะและอ่านกลับได้ | ยังไม่มี cloud ที่เชื่อม sensor จริงหรือ dashboard ที่ดึงข้อมูลเก่า; หน้า 3D ไม่ใช่ dashboard จริง |
| M6: notification | Telegram เมื่อ low water, fault, offline/recovery และเหตุที่กำหนด | ยังไม่มี bot/ผู้รับ/cooldown ที่ทดสอบจริง; ตรวจ offline จากภายนอก gateway |
| M7: safety | แยก pump/tank จาก electronics มีถาด, manual stop; ตรวจไฟบ้านโดย TA/ผู้สอนก่อน demo | CAD และ test plan เป็นร่าง ไม่ใช่ผลทดสอบ วงจรตัดกำลังและพฤติกรรมหลังไฟกลับยังไม่ยืนยัน |
| M8: Internet Git + ทุกคนมี commit | remote ที่ตั้งอยู่ `https://github.com/theanrawich/Kaew.git`; สมาชิกแต่ละคนมี contribution | `git remote -v` ในเครื่องแสดง origin แล้ว แต่ยังไม่ตรวจสิทธิ์ Internet จากมุมผู้ประเมินหรือยืนยัน commit สมาชิกทุกคน |

มีต้นแบบ telemetry ภายในหน่วยความจำของหน้า simulation สำหรับทดลองคิว/เชื่อมกลับเท่านั้น ไม่ใช่การส่งระหว่างบอร์ดหรือ cloud และไม่ใช่ raw sensor data จริง จึงยังไม่ใช่หลักฐานผ่าน M1, M3, M5 หรือ E4

## คะแนน 70 — แผนหลักฐาน

| หมวด | คะแนน | หลักฐานที่จะใช้ | ช่องว่าง |
|---|---:|---|---|
| I ปัญหาและหลักฐานผู้ใช้ | 5 | ระบุผู้ใช้/ปัญหา ขอบเขต และหลักฐานสังเกตหรือสัมภาษณ์ | ยังไม่มีหลักฐานผู้ใช้จริงที่ตรวจในรอบนี้; ไม่สร้างคำสัมภาษณ์สมมติ |
| II architecture/data flow | 2 | แผนภาพ node→gateway→cloud, message format พร้อม sensor ID และ real-time control | มีแนวคิดแต่ยังไม่มี message contract และ implementation จริง |
| II scalability | 3 | ระดับ 1: code รองรับหลาย node ID; ระดับ 2: 1 node จริง + ≥2 simulated nodes พร้อมกัน แยกใน gateway/dashboard; ระดับ 3: ≥2 nodes จริง | ยังไม่มีหลักฐาน gateway code หรือ node ที่ส่งจริง; gateway ไม่นับเป็น node ที่สอง |
| II′ embedded depth | 10 | เลือก ≤5 รายการ E1–E8, อย่างละ 2 คะแนนเมื่อ demo/อธิบายครบ | แนวทางด้านล่างเป็นข้อเสนอ ไม่ถือว่าทำแล้ว |
| III functionality | 8 | live demo ฟีเจอร์หลักและฟีเจอร์ที่ออกแบบครบ | ระบบจริงยังไม่แสดงการทำงาน |
| III field testing | 3 | ทดลองเบื้องต้น; บันทึกต่อเนื่อง ≥24 ชม.; ทดลองกับผู้ใช้/สถานที่จริง | ยังไม่มีผลการทดลองจริง |
| III robustness | 3 | บันทึกเงื่อนไขทดสอบซ้ำ รวมกู้คืน Wi-Fi/ไฟดับ | กู้ระบบสื่อสารเองได้โดย **ไม่เริ่มปั๊มเอง** หลังไฟกลับ; ต้องทดสอบจริง |
| III build quality | 3 | ภาพ/วิดีโอเครื่องประกอบ เดินสาย ยึด และเคลื่อนย้าย | CAD ไม่พิสูจน์ความแข็งแรงหรือความเรียบร้อยของเครื่องจริง |
| III user experience | 3 | ทดลอง dashboard/alerts กับผู้ใช้และบันทึกผล | ยังไม่มี dashboard/alert เชื่อมข้อมูลจริง |
| IV test procedure | 3 | แบบทดสอบปกติ ขอบ และ fault พร้อมผลรายครั้ง | `KAEW_TEST_RECORD_TEMPLATE.md` เป็นฟอร์ม ยังไม่มีผลจริง |
| IV metrics | 4 | ≥3 จาก latency, packet delivery, sensor accuracy, power, AI accuracy หรือ uptime พร้อมวิธี; ทำซ้ำรายงานค่าเฉลี่ยและ min/max | ยังไม่มี raw measurements จริง; overshoot simulator ไม่ใช่ metric ของเครื่อง |
| IV analysis/comparison | 3 | เปรียบเทียบเป้าหมายและระบบอื่นด้วย metrics ที่วัด | ยังไม่มี measurements หรือการเปรียบเทียบที่ครบ |
| V presentation | 10 | สไลด์ live demo และสมาชิกทุกคนตอบส่วนที่รับผิดชอบได้ | ยังไม่มีหลักฐานซ้อม/demo; เตรียม backup video ตามโจทย์ |
| VI video/report | 10 | วิดีโอ 3–5 นาที และรายงาน PDF ≤10 หน้า (ตามข้อยกเว้น) ครบ 6 หัวข้อ | ยังไม่มี final video, ผลทดลองและรายงานฉบับสมบูรณ์ที่ตรวจได้ |

## Embedded Depth — ตัวเลือกที่ควรประเมิน

| ข้อ | แนวทางเสนอ | เงื่อนไขที่ต้องพิสูจน์ / สถานะ |
|---|---|---|
| E1 | FreeRTOS แยก acquisition, safety/control, communications | ≥3 tasks, อธิบาย priority และ queue/semaphore/event group; ยังไม่ทำ |
| E2 | interrupt จาก input ที่เหมาะสมจริง เช่น data-ready เมื่อยืนยันวงจรและพฤติกรรม | ISR สั้นและ deferred processing; ไม่ถือว่า pulse จาก flow ทำได้เพราะตัด sensor แล้ว ไม่ใช่ safety stop ที่พึ่ง software อย่างเดียว |
| E4 | ACK/retry node→gateway และ buffer/store-and-forward เมื่อ cloud หาย | ต้อง demo ทั้งสองส่วน พร้อม dedup/recovery; ยังไม่ทำ |
| E5 | TLS + authentication gateway→cloud, ไม่ commit secrets | เลือก service และทดสอบเชื่อมต่อจริง; ยังไม่ทำ |
| E6 | OTA firmware | ต้อง demo ก่อน/หลังและออกแบบไม่ให้เริ่มปั๊มโดยไม่ตั้งใจ; ยังไม่ทำ |
| E3/E7/E8 | สำรวจเฉพาะเมื่อเหมาะกับทรัพยากร: sleep และวัดกระแส/อายุแบต, AI บน MCU, หรือ driver ระดับ bus/mesh ≥3 node | ไม่จำเป็นต้องทำทั้งหมด; point-to-point M3 อย่างเดียวไม่นับ E8; ยังไม่ทำ |

E2 ยังไม่ใช่ข้อเสนอที่รับรองได้: ต้องตรวจว่า HX711 data-ready และบอร์ด/driver ที่เลือกใช้ interrupt ได้จริงและ ISR/deferred processing ตรงนิยาม โดยให้ physical stop แยกจาก firmware หากไม่เหมาะให้เลือกรายการ E อื่นและอธิบายการเปลี่ยนใน report

## งานเร่งตามกำหนดในโจทย์ต้นฉบับ

- **20 พ.ย. 2026, 23:59:** checkpoint video ≤2 นาที แสดง sensor node → gateway → cloud → dashboard ครบเส้นทาง; ไม่มีหลักฐานว่าทำหรือส่งแล้ว
- **8 ธ.ค. 2026:** presentation รวม live demo 10 นาทีและ Q&A; ส่ง final ตามโจทย์ภายใน 23:59 โดยมี grace ถึง 9 ธ.ค. 06:00 ตามเอกสาร
- Final report มี 6 ส่วน: ปัญหา, related work, system design/message format, ผลทดสอบ/metrics, อภิปราย, บทบาทสมาชิก/Git/AI-tool declaration; ส่ง code archive และ peer evaluation ตามโจทย์
- ตรวจ MyCourseVille และผู้สอนก่อนยึดกำหนดหรือสเปกที่อาจเปลี่ยน เอกสารนี้ไม่ได้ส่งงานแทนทีม

## แผนวัดขั้นต่ำที่ตรวจย้อนกลับได้

1. **Latency:** บันทึกเวลาที่ sensor เปลี่ยนและเวลาที่ actuator ตอบหรือ dashboard รับ พร้อมวิธี sync clock/เครื่องมือ แยกกรณี stop; วัดซ้ำหลายครั้งและรายงาน distribution/min/max
2. **Packet delivery:** กำหนด session/node/sequence, นับ unique packets ที่ gateway รับเทียบกับที่ node ส่งภายในช่วงทดสอบ ระบุการนับ duplicate/retry และ packet ที่ยังอยู่ใน buffer
3. **Sensor accuracy:** สอบเทียบและวัดน้ำหนักหลายจุดเทียบเครื่องชั่งอ้างอิง บันทึก raw, ค่าที่คำนวณ, reference, error และความละเอียดของเครื่องมือ; volume จากน้ำหนักเป็นค่าประมาณและต้องระบุสมมติฐานความหนาแน่น
4. วัดเวลาหยุดและ overshoot, uptime และคุณภาพ AI เพิ่มเพื่อการออกแบบ แม้การนับเป็นคะแนนขึ้นกับเกณฑ์/การประเมิน เก็บ raw records, firmware revision และเงื่อนไขแวดล้อม ไม่แทนค่าจริงด้วย simulation

# Kaew — ข้อมูลและขอบเขตความเป็นส่วนตัว

ระบบปัจจุบันใช้ UART ตาม [PROTOCOL](../firmware/PROTOCOL.md) และ SQLite ตาม [cloud](../cloud/README.md). เนื้อหาด้านล่างเป็นเป้าหมายการออกแบบระยะต่อไปจากการทบทวน 8 พ.ย. 2026 ไม่ใช่ schema ที่ทำครบแล้ว; Firestore และ message JSON ในร่างเก่าถูกแทนที่แล้ว

## โครงสร้างข้อมูลเป้าหมาย

| กลุ่ม | ฟิลด์สำคัญ | สถานะ / ข้อควรระวัง |
|---|---|---|
| `readings` | device/node, boot/seq, sensor ID, raw value + unit, quality, sample/receive time | เก็บ raw ADC/น้ำหนัก/อุณหภูมิ/สถานะตามที่อ่านจริงแยกจากค่าที่แปลง; XKC จุดเดียวไม่ให้ปริมาตรถัง |
| `uses` | event ID, คำสั่งข้อความ, requested/applied volume, เริ่ม/หยุด, ผล/เหตุหยุด, ปริมาณประมาณและ calibration version | น้ำที่จ่ายหรือน้ำหนักที่ลดลงไม่พิสูจน์ว่าดื่มหมด; บันทึกเป็น estimate |
| `ai_decisions` | input references/versions, model/version, proposal, เหตุผลสรุป, validation result, applied values, feedback และ error | บันทึกข้อเสนอแยกจากค่าที่ controller ใช้จริง; ไม่เก็บ API key/secret; ทดสอบกรณี invalid/out-of-range/timeout |
| `faults` / `status` | event ID, severity, source, started/resolved timestamps, reason, sequence และ notification status | กำหนด cooldown, dedup, recovery และ heartbeat monitor นอก gateway |

ไมโครโฟนใช้เป็นเซนเซอร์เพื่อการใช้งานจริง แต่ผู้ใช้กำหนด **ไม่เก็บเสียงถาวรโดยปริยาย**: การเก็บ feature/transcript เป็นข้อมูลอนุพันธ์ ไม่ควรเรียกว่า raw audio. เนื่องจาก M5 ระบุ raw sensor data ควรถาม TA ว่าการเก็บค่าไมค์รูปแบบใดสอดคล้องเกณฑ์และนโยบายนี้ โดยไม่อ้างว่าการเก็บ transcript ผ่าน M5 แล้ว

### ความปลอดภัยและความเป็นส่วนตัว

- Gateway ตรวจ cup present, scale freshness/validity, level และ timeout ก่อนเริ่มและระหว่างจ่าย; สูญเสียข้อมูลที่จำเป็นให้ stop/latch fault และต้องสั่งเริ่มใหม่หลังแก้ ไม่ใช้คำสั่งค้างจาก network หลัง reboot
- AI ส่งได้เพียงข้อเสนอที่มี schema และช่วงที่อนุญาต; ผู้ควบคุม deterministic ตรวจ limit และ interlock ทุกครั้ง ไม่มี AI/remote bypass physical stop; เมื่อ model/API ล้มเหลวใช้พฤติกรรม fallback ที่ระบุและทดสอบ ไม่อ้างว่า threshold เป็น AI
- จัดการ time sync, certificate validation, credential rotation, least privilege, device identity และ dashboard access; ห้ามเก็บ Wi-Fi password, bot token, service-account/private key ใน repo หรือ browser bundle ห้ามใช้ service-role key ใน MCU
- Telegram API เป็นช่องข้อความ ไม่ใช่วงจร safety; กำหนด recipient, event, cooldown, duplicate suppression และการกู้คืน; หาก cloud/Internet ล่มให้แจ้งสถานะตามที่ทำได้เมื่อกลับมา โดยไม่ส่งข้อความลวงว่าแจ้งสำเร็จ
- การเก็บ transcript, ประวัติการใช้ และ AI context มีผลต่อความเป็นส่วนตัว ต้องกำหนดผู้เข้าถึง ระยะเก็บและวิธีลบกับทีม; เสียงดิบไม่เก็บถาวรโดยปริยาย

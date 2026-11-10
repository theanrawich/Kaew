# Kaew — แผนข้อมูลและการสื่อสารก่อนมีฮาร์ดแวร์

สถานะ 8 พ.ย. 2026: **ข้อเสนอ ยังไม่ได้เลือกหรือสร้าง cloud/provider, bot, บัญชี หรือ firmware จริง** สอดคล้องข้อกำหนดข้อมูลสี่กลุ่มใน `KAEW_PROJECT_DRAFT.md` และหลักฐานเกณฑ์ใน `KAEW_RUBRIC_MATRIX_2026-11-08.md`. ห้ามใช้ cloud, AI หรือ dashboard เป็นเงื่อนไขเดียวสำหรับการหยุดปั๊ม

## ขอบเขตและทางเลือก

```text
Node ESP32 (level + TDS + temperature) -- link / acknowledgement --> Gateway S3
Gateway: scale + microphone + control + queue --> HTTPS/TLS --> cloud --> dashboard
                                      ├--> AI service proposal --> validate --> bounded action
                                      └--> alert events --> Telegram
External heartbeat monitor --> offline/recovery alert (หาก gateway ส่งเองไม่ได้)
Physical stop --> independently cuts pump power (วงจรยังไม่ยืนยัน)
```

ข้อเสนอเพื่อ checkpoint: ทดลอง Firestore + dashboard แบบอ่านอย่างเดียวก่อน เพราะโครงสร้าง records ของ readings, usage, AI และ faults มีหลายชนิดและต้องอ่านข้อมูลเก่ากลับได้; การใช้งานจริงยังต้องพิสูจน์การยืนยันตัวตน อัตราการเขียน การจัดการคิว และค่าใช้จ่าย ไม่มีบัญชีหรือบริการที่เลือกโดยผู้ใช้แล้ว

| ตัวเลือก | ข้อดีสำหรับ Kaew | ข้อจำกัดที่มีผลต่อการตัดสินใจ |
|---|---|---|
| [Firestore](https://firebase.google.com/docs/firestore/pricing) | เอกสารแยกตามชนิดและ query ได้; free quota ที่ประกาศ 1 GiB, 20,000 writes และ 50,000 reads ต่อวัน | TTL deletes ต้องเปิด billing; การอ่าน/index/network มี quota และอาจมีค่าใช้จ่ายเมื่อใช้แพ็กเกจคิดเงิน; ต้องออกแบบ auth/rules, schema และ cleanup ไม่เปิดสิทธิ์ public write |
| [ThingSpeak](https://thingspeak.mathworks.com/pages/license_faq) | ช่องข้อมูลและกราฟสำเร็จรูปเหมาะกับ checkpoint แบบง่าย | free สำหรับ non-commercial จำกัด 4 channels, 3 ล้าน messages/ปี และ ≥15 วินาทีระหว่าง updates; history รูปแบบ AI/fault ซับซ้อนอาจต้องระบบอีกส่วน ตรวจข้อกำหนดบัญชีและการเข้าถึงก่อนเลือก |
| [Supabase](https://supabase.com/pricing) | relational database, queries และ auth เหมาะกับข้อมูลหลายกลุ่ม | free database 500 MB/project และ project อาจถูกพักหลังไม่มี activity หนึ่งสัปดาห์; ต้องจัดการ RLS/auth, การกู้คืน และไม่ฝัง service-role key ใน MCU; ไม่ถือว่าแผนฟรีรับประกัน uptime |

ตัวเลขเป็นข้อมูลหน้าเอกสารทางการที่ตรวจ 8 พ.ย. 2026 ข้อกำหนด/ราคาอาจเปลี่ยน ตรวจหน้า plan, ภูมิภาค, บัญชีและงบ API ก่อนเปิดใช้งานจริง ทั้งสามตัวเลือกยังไม่พิสูจน์ว่าใช้ได้กับบัญชีของทีม

### ภาระตัวอย่าง Firestore (ไม่ใช่พยากรณ์บิล)

สมมติ gateway รวมค่าจาก node และ gateway เป็น **หนึ่ง document write ต่อ 10 วินาที**: 86,400/10 = **8,640 writes/วัน** ก่อน events, AI, retries หรือ writes อื่น; ส่งทุก 5 วินาที = **17,280 writes/วัน**. หากเขียนห้า sensor แยกทุก 10 วินาที = **43,200 writes/วัน**, เกิน free quota ที่อ้างข้างต้น เงื่อนไขจริงขึ้นกับโครงสร้าง การ retry, rules, reads/dashboard, data volume และ clock; ไม่ใช่การรับรองว่าไม่มีค่าใช้จ่าย หรือให้ลด sampling ที่จำเป็นต่อ safety การอ่านชั่ง/หยุดต้องทำในเครื่องด้วยความถี่ที่วัดและทดสอบ ไม่จำกัดตามอัตรา cloud

## ข้อเสนอ message contract v1

โครงสร้างต่อไปนี้เป็น **ตัวอย่างจำลอง ไม่ใช่ข้อมูลวัด**; แต่ละ reading เก็บ raw ตามชนิดและ quality, ไม่แทน sensor ที่ขาดด้วยศูนย์ ค่าเวลาจริงให้ใช้ UTC เมื่อตั้งนาฬิกาได้ ส่วน timeout ใช้ monotonic clock ใน gateway ไม่เปรียบเทียบ monotonic ระหว่างบอร์ด

```json
{
  "schema": 1,
  "node_id": "node-01",
  "boot_id": "example-unique-boot-id",
  "seq": 42,
  "sample_utc": null,
  "time_quality": "unsynced",
  "readings": [
    {"sensor_id":"level-1", "kind":"level_switch", "raw":1, "unit":"state", "quality":"simulated"},
    {"sensor_id":"tds-1", "kind":"tds_adc", "raw":1520, "unit":"adc_count", "quality":"simulated"},
    {"sensor_id":"temp-1", "kind":"temperature", "raw":25.1, "unit":"degC", "quality":"simulated"}
  ]
}
```

- ข้างต้นเป็นตัวอย่าง test fixture เท่านั้น; production ใช้ `quality` เช่น `ok`, `fault`, `stale`, `uncalibrated` และระบุค่าที่หายด้วย `null` พร้อมเหตุผล ไม่ใช้คำว่า `simulated` เป็นข้อมูลจริง
- `node_id + boot_id + seq` เป็น identity สำหรับ dedup; `boot_id` ต้องไม่ซ้ำเมื่อ reset และ sequence ไม่ย้อนภายใน boot เดียว กำหนด wrap/reboot และตรวจขนาดข้อความก่อนรับ; gateway เพิ่ม `received_utc`, `received_monotonic`, firmware version และ quality ของเวลาจากฝั่งตนเอง
- ACK ระหว่าง node→gateway ต้องระบุความหมายชัด: ACK หลังรับเข้า RAM **ไม่ใช่** หลักฐานว่าบันทึกถาวรหรือส่งถึง cloud; หากต้องรับรองหลังไฟดับต้องออกแบบ durable storage และทดสอบแยก cloud receipt มีสถานะอีกขั้น
- เมื่อ queue เต็ม ห้ามทิ้งข้อมูลแบบเงียบ: ปฏิเสธ/ส่ง backpressure หรือระบุนโยบาย drop พร้อม counter และ alert; ขีดจำกัด RAM, wear ของ flash และช่วงเก็บต้องกำหนดหลังทดสอบจริง; การสั่งปั๊มต้องไม่รอ queue
- หลังเน็ตกลับ ส่งซ้ำด้วย ID เดิม, dedup ฝั่งรับให้ idempotent, อนุญาตข้อมูลมาช้าตามลำดับเวลาตัวเอง และแยก record ที่ล้มเหลว; วัด loss, duplicates, backlog และลำดับโดยทดสอบตัดไฟระหว่างเขียน/ACK

## โครงสร้างข้อมูลเสนอ

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

## งานและการทดสอบก่อน checkpoint

1. เลือกบริการและขอบเขตข้อมูล/ระยะเก็บ กำหนดบัญชี/สิทธิ์/งบและวิธีตรวจค่าใช้จ่าย; ยังไม่สร้างบัญชีหรือเปิด billing
2. สร้าง gateway/node protocol ตาม contract, timestamp/quality, ACK/retry, คิวจำกัดและ idempotency; ทำ unit tests และทดสอบอุปกรณ์จริงเมื่อมี
3. เชื่อม cloud ด้วย identity แยกจาก dashboard; ป้อน **ข้อมูลจำลองที่ติดป้าย** ก่อนเปลี่ยนเป็น sensor จริง ตรวจอ่านกลับหลัง reload และสิทธิ์ deny ของผู้ไม่มีสิทธิ์
4. ทดสอบ offline, queue full, reboot, clock ไม่ตรง, duplicate/reorder และ reconnect; ยืนยัน local safety ทำงานแม้ cloud/AI/Telegram ล้มเหลว
5. checkpoint ต้องแสดง **sensor node จริง → gateway จริง → cloud → dashboard** และแสดงหลักฐานเวลา/ID; หน้า simulation ในเครื่องหรือ cloud ที่มีแต่ข้อมูลปลอมยังไม่พิสูจน์เส้นทางนี้

## คำถามที่ยังเปิด

- Cloud provider, ผู้ดูแลบัญชีและภูมิภาค, retention/backup/ลบข้อมูล, การเข้าถึง dashboard และยอดค่าใช้จ่ายที่ยอมรับได้
- Node↔gateway transport และรูปแบบ persistence/queue เมื่อไฟดับ; ความถี่ sampling/ส่งและเกณฑ์ freshness จากผลทดสอบ
- AI provider/model, งบ API, ภาษาไทย, วิธีทดสอบคุณภาพ, voice pipeline และ fallback
- Telegram bot/ผู้รับ, thresholds, cooldown, heartbeat monitor และเหตุการณ์ recovery
- ขอความชัดเจนจาก TA เรื่อง raw data ของ microphone เมื่อไม่เก็บเสียงถาวร และการนับ microphone เป็น sensor ที่อ่าน/ใช้จริง

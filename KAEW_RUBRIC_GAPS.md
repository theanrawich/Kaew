# Kaew — ช่องว่างเทียบกับเกณฑ์คะแนน

> **เอกสารประวัติ 30 ต.ค. ไม่ใช่สถานะล่าสุด:** แผนปัจจุบันตัด flow sensor และมี Git remote แล้ว ผัง 3D/แบบจำลองไม่ใช่หลักฐานระบบจริง ดู `KAEW_RUBRIC_MATRIX_2026-11-08.md` และ `KAEW_READINESS_AUDIT_2026-11-06.md` บนเครื่องสำหรับสถานะปัจจุบัน

ตรวจวันที่ 30 ตุลาคม 2026  
สถานะโครงการ: ร่างเครื่องจ่ายน้ำอุณหภูมิห้องแบบตั้งโต๊ะ ยังไม่ final

[เกณฑ์ต้นฉบับของอาจารย์](https://docs.google.com/document/d/1eBUKyIknXkPH_oJqtiS-Vm4aKlzjjkmrdMn4oYDUgSw)  
[สรุปเกณฑ์ภาษาไทย](FINAL_PROJECT_2026_TH.md) · [ร่าง Kaew ล่าสุด](KAEW_PROJECT_DRAFT.md)

## ขอบเขตการประเมิน

- อ่านร่างล่าสุด ไฟล์ใน workspace และเกณฑ์ Google Docs ฉบับปัจจุบัน
- มีเอกสารโจทย์ ร่างความต้องการ และ HTML 3D พร้อมการจำลองยกแก้ว/เติมน้ำ
- ยังไม่พบ firmware, backend/cloud, dashboard ที่ต่อข้อมูลจริง, โมเดล AI ที่ฝึกหรือใช้งานจริง หรือรายงานผลทดสอบฮาร์ดแวร์ใน workspace
- ตรวจ Git พบ 0 commits และ 0 remotes ณ เวลาประเมิน
- “ยังไม่พบ” หมายถึงยังไม่มีหลักฐานใน workspace นี้ ไม่ได้ยืนยันว่าไม่มีอุปกรณ์หรือผลงานอยู่ที่อื่น
- ไม่นำหัวข้อหรือคำตอบเดิมที่ผู้ใช้เคยส่งมาประเมิน และไม่ได้ตรวจสถานะส่งงานบน CourseVille
- นี่เป็นการเทียบช่องว่าง ไม่ใช่การให้คะแนนแทนอาจารย์

## 1. ข้อกำหนดขั้นต่ำ M1–M8

แต่ละข้อที่ขาดหัก 2 คะแนนจากคะแนนรวม การทำครบไม่ได้ให้คะแนนขั้นต่ำแยก

| ข้อ | แผนของ Kaew | สิ่งที่ยังขาด/ต้องพิสูจน์ |
| --- | --- | --- |
| M1: เซนเซอร์ 5 ชนิด; node ≥2, gateway ≥2 | แผนล่าสุด: node ใช้ level/TDS/temperature และ gateway ใช้ load cell/microphone; ตัด flow sensor แล้ว | เหลือ 5 ชนิดพอดี ต้องต่อและใช้ข้อมูลจริงทุกชนิด รวมทดสอบ level กับผนังขวดและตำแหน่งหัววัดที่ถอดล้างได้ก่อนยืนยันผ่าน |
| M2: actuator ≥1 | ผู้ใช้เลือกปั๊มน้ำ 1 ตัว และมีลำโพงให้ AI พูดตอบเป็น audio output เพิ่มเติม | ยังต้องเลือกรุ่นปั๊ม อัตราการจ่าย วงจรขับ แล้วควบคุม actuator จริงพร้อมยืนยันปริมาณและเงื่อนไขหยุด ลำโพงไม่นับเป็น actuator ตามโจทย์ |
| M3: node → gateway | มีแนวคิด ESP32 + ESP32-S3 | เลือก link และ message contract พัฒนา firmware แล้วแสดงข้อมูลจากเซนเซอร์จริงส่งถึง gateway |
| M4: AI ใช้ output ตัดสินใจ/ควบคุมในระบบ | ผู้ใช้เลือก adaptive ทั้งเวลาเตือนและปริมาณเติม โดยเรียกโมเดลผ่าน API และย้ำว่า AI ต้องฉลาดพอสมควร; มีข้อเสนอคำสั่งเสียงและสถานการณ์ทดสอบคุณภาพในร่าง | เลือกผู้ให้บริการ/โมเดลและ voice pipeline จากผลทดสอบภาษาไทย บริบท คำสั่งกำกวม และการอิงข้อมูลจริง พร้อมเวลาในการตอบ/ค่าใช้จ่าย; กำหนดเกณฑ์ผ่าน inputs, outputs, ประวัติ/feedback และนำผลทั้งสองค่าไปใช้จริงผ่าน controller; ทดสอบ API ขัดข้องและบันทึกหลักฐาน Preset ใน HTML ยังไม่ใช่ AI |
| M5: raw data บน cloud + dashboard | ยืนยันข้อมูล 4 กลุ่มแล้ว: sensor readings พร้อม ID/เวลา/หน่วย/สถานะ, ประวัติใช้งาน, AI/feedback และสถานะ/ปัญหา; แยกค่าคำนวณและยอดดื่มโดยประมาณ ประวัติคำสั่งเก็บข้อความ/ผลการทำงานโดยไม่เก็บเสียงถาวรเป็นค่าเริ่มต้น Dashboard ยังเป็นข้อเสนอ | ยืนยันขอบเขต dashboard และเลือก cloud/storage; เก็บ readings จาก node และ gateway จริงให้เรียกอ่านกลับได้ พร้อม dashboard ที่เชื่อมข้อมูลจริง ทดสอบอ่านข้อมูลเดิมหลังเปิดหน้าใหม่ HTML 3D เป็นหน้าสำรวจแบบ |
| M6: notification เหตุการณ์/สถานะสำคัญ | ยืนยัน Telegram และเหตุการณ์หลัก 6 กลุ่มแล้ว: น้ำใกล้หมด/หมด การจ่ายผิดปกติ sensor fault อุปกรณ์ offline/recovery ค่าน้ำออกนอกเกณฑ์ และ AI API ขัดข้อง รวมเตือนดื่มน้ำเมื่อยังไม่ตอบสนองต่อจอ; สรุปรายวันยังเป็นตัวเลือก | กำหนด thresholds/เวลารอ/cooldown เลือกตัวส่งและตัวตรวจ heartbeat ภายนอก gateway เชื่อม bot/ผู้รับ แล้วทดสอบส่งเหตุจริงและ recovery; ยังไม่มี dedicated leak detection หลังตัด sensor |
| M7: safety | แนวทางแยกน้ำ/ถาดรอง, cup/volume/timeout interlocks, การตรวจจ่ายด้วยน้ำหนักและเวลา, critical sensor/link fault, physical stop และ reboot ปั๊มปิด ยังต้องทดสอบ | ไม่มี flow sensor อิสระ; เลือกแหล่งจ่าย วงจรและค่าขีดจำกัด ตรวจอุปกรณ์จริง/ข้อกำหนดไฟบ้านกับ TA ทำและทดสอบทุกเงื่อนไขรวมเวลาหยุด/น้ำไหลต่อ และวัสดุสัมผัสน้ำ ยังไม่ผ่าน M7 จากเอกสารอย่างเดียว |
| M8: Git บน Internet + commit ทุกคน | ตั้ง remote [theanrawich/Kaew](https://github.com/theanrawich/Kaew) และเพิ่ม workflow GitHub Pages แล้ว | ยังต้องมี contribution/commit ของสมาชิกทุกคน; การเผยแพร่โมเดลยังไม่ยืนยันว่าผ่านข้อกำหนดนี้ทั้งหมด |

## 2. เกณฑ์ 70 คะแนน

| หมวด | คะแนน | สิ่งที่มีเป็นจุดเริ่ม | สิ่งที่ยังขาดเพื่อเก็บคะแนน |
| --- | ---: | --- | --- |
| I. Problem Definition | 5 | ผู้ใช้เล่าว่าลืมดื่มน้ำ/ดื่มน้อยระหว่างใช้คอม | ระบุผู้ใช้เป้าหมายและขอบเขตให้ชัด เก็บหลักฐานสังเกต/สัมภาษณ์/บันทึกพฤติกรรม และอธิบายความต่างจากงานที่ใกล้เคียง |
| II. Architecture & Scalability | 5 | มีแนวคิด node/gateway/cloud และร่างแบ่งอุปกรณ์ | Block diagram, component responsibilities, message format/node ID, real-time control และหลักฐานรองรับหลาย sensor nodes ตามระดับคะแนน |
| II′. Embedded Engineering Depth | 10 | ร่างพูดถึง RTOS, interrupts, reliability, security, OTA | เลือกรายการ E ที่จะเก็บคะแนนให้ชัด ทำให้ใช้งานได้จริง demo และอธิบายได้ สูงสุด 5 รายการ × 2 คะแนน |
| III. Implementation | 20 | มี flow การใช้งานและรูปลักษณ์ 3D | ระบบฮาร์ดแวร์จริงครบฟีเจอร์, calibration, field test, recovery หลังไฟ/Wi-Fi หาย, enclosure/สายไฟ และ dashboard/alerts ที่ผู้ใช้ใช้ได้จริง |
| IV. Testing & Analysis | 10 | มีรายการ metrics ในร่าง | Test plan พร้อมขั้นตอน/ผล normal-edge-failure, metrics อย่างน้อย 3 ตัวจากข้อมูลจริง, วัดซ้ำ/รายงานความแปรผัน และเปรียบเทียบกับเป้าหมายกับระบบเดิม |
| V. Presentation | 10 | โมเดล 3D ช่วยสื่อสารแนวคิดได้ | Slides, การนำเสนอ 10 นาทีรวม live demo, แผน demo และเตรียมสมาชิกทุกคนตอบ Q&A ส่วนของตนเอง |
| VI. Video & Documentation | 10 | มีเอกสารบริบทและร่าง | Video 3–5 นาที, final report PDF ≤10 หน้าตามข้อยกเว้นในโจทย์, เนื้อหาครบ 6 ส่วน, references, บทบาท/ผลงาน, Git URL และ AI-tool declaration |

### Scalability ที่ยังต้องออกแบบ

- **1 คะแนน:** message format และ gateway code รองรับหลาย sensor nodes เช่นมี node ID
- **2 คะแนน:** sensor node จริง 1 ตัว + simulated nodes อย่างน้อย 2 ตัว ทำงานพร้อมกัน แยกได้ทั้ง gateway และ dashboard
- **3 คะแนน:** sensor nodes จริงอย่างน้อย 2 ตัว ทำงานพร้อมกัน
- บอร์ด gateway ไม่นับเป็น sensor node ตัวที่สองสำหรับเกณฑ์นี้
- ใช้แก้วประจำหนึ่งใบต่อได้ ไม่จำเป็นต้องเพิ่มหลายแก้วเพื่อรองรับหลาย sensor nodes

### Embedded Engineering Depth ที่เสนอให้พิจารณา

รายการต่อไปนี้สอดคล้องกับแนวทางในร่าง แต่ยังไม่ใช่รายการที่ผู้ใช้ยืนยัน final

| รายการ | วิธีผูกกับ Kaew | หลักฐานที่ต้องมี |
| --- | --- | --- |
| E1 | แยกงานอ่านเซนเซอร์ ควบคุมการจ่าย และ communication ด้วย FreeRTOS | ≥3 tasks, เหตุผลของ priorities, queue/semaphore/event group และ demo |
| E2 | พิจารณา input อื่น เช่น HX711 data-ready หากวงจรและ driver รองรับ | flow sensor ถูกตัดแล้ว; ต้อง demo ISR/deferred processing จริงโดยไม่ใช้แทน hardware stop และอธิบายได้ ไม่ busy polling |
| E4 | ACK/retry ระหว่าง node/gateway และ buffer เมื่อ cloud/Internet หาย | สาธิตการส่งซ้ำ การเก็บค้าง และการส่งต่อเมื่อเชื่อมใหม่ |
| E5 | Cloud connection ใช้ TLS และ authentication | ตรวจการเชื่อมต่อจริงและไม่มี secrets ใน repository |
| E6 | อัปเดต firmware ผ่าน OTA | demo firmware ก่อน/หลังอัปเดต |

E7 ไม่ใช่ข้อบังคับสำหรับคะแนน Depth เต็ม เพราะเลือกเก็บ 5 รายการอื่นได้ ส่วน AI ขั้นต่ำ M4 รันนอก MCU ได้ตามโจทย์ แต่ต้องมีผลต่อการตัดสินใจจริงในระบบ

### การเก็บคะแนน Implementation และ Testing

- Functionality: core features สูงสุด 4 + ทำฟีเจอร์ที่ออกแบบไว้ครบอีก 4 จึงควรคุมขอบเขตให้ชัด
- Field testing: ทดลองสั้นในสภาพแวดล้อมตนเอง 1; ต่อเนื่อง ≥24 ชั่วโมงพร้อมข้อมูล 2; กับผู้ใช้จริง/สถานที่จริง 3
- Robustness ระดับสูงต้อง recover เองหลังไฟหรือ Wi-Fi หาย
- Build Quality ต้องประเมินตัวเครื่องที่ประกอบจริง โมเดล 3D ยังไม่ยืนยันคุณภาพประกอบ/ความสะดวกในการขนย้าย
- Metrics ที่เหมาะจะพิจารณา: sensor→actuator/dashboard latency, packet delivery rate, sensor accuracy เทียบ reference, uptime และ AI accuracy บนชุดทดสอบของกลุ่ม
- เลือกอย่างน้อย 3 metrics ตามเมนู พร้อมวิธีวัดและข้อมูลจริง วัดซ้ำและรายงาน mean/min/max หรือความแปรผันเพื่อเก็บอีก 1 คะแนน
- ควรวัดความคลาดเคลื่อนปริมาณจ่ายเป็นมล./% เพื่อเทียบกับวัตถุประสงค์ของ Kaew ด้วย การเลือกให้นับเป็น sensor accuracy ต้องมีการวัดเทียบอุปกรณ์อ้างอิงที่ชัดเจน
- ต้องวิเคราะห์ทั้งเทียบเป้าหมายโครงการและระบบ/ผลิตภัณฑ์ใกล้เคียง ไม่รายงานเฉพาะตัวเลข

## 3. เอกสารและการส่งงานของหัวข้อใหม่

รายการนี้เป็น checklist งานที่ต้องเตรียม ไม่ใช่ข้อสรุปว่าเคยส่งหรือยังไม่ส่งแล้ว

- [ ] Proposal 1–2 หน้า: ปัญหา/ผู้ใช้, block diagram, BOM, รายการ E ที่เลือก และบทบาทสมาชิก
- [ ] Checkpoint video ≤2 นาที แสดง node → gateway → cloud → dashboard
- [ ] Final slides และ live demo
- [ ] Report PDF ≤10 หน้า ไม่รวมส่วนที่โจทย์ยกเว้น พร้อม 6 ส่วนตามเกณฑ์
- [ ] Video 3–5 นาทีพร้อมลิงก์
- [ ] Source archive และ Git repository URL
- [ ] Peer evaluation แยกรายคน
- [ ] Contribution/commit ของทุกคน และการอ้างอิง AI tools/code/libraries ที่ใช้

## 4. ลำดับเรื่องที่ควรทำให้ชัดก่อน

1. **AI adaptive:** เลือก model API สำหรับปรับทั้งเวลาเตือน/ปริมาณ ระบุ input/output ประวัติ/feedback และวิธีประเมินผลจริง
2. **Hardware และ architecture:** เลือกเซนเซอร์จริงให้ครบ M1, pump/valve, การแบ่ง node/gateway และ BOM ภายในงบ
3. **คะแนน Depth และ scalability:** เลือกรายการ E และระดับการรองรับหลาย nodes ที่ตั้งใจทำ
4. **ระบบข้อมูลจริงครบทาง:** node → gateway → cloud/dashboard → notification พร้อม safety controller
5. **การพิสูจน์:** วาง test plan และเริ่มเก็บ logs/metrics/contribution ตั้งแต่ต้น

ยังไม่มีการประเมินคะแนนจริงหรืออ้างว่ารายการใดผ่าน hardware validation จากการตรวจครั้งนี้


# Kaew (แก้ว) — AI-assisted Smart Water Dispenser

Kaew เป็นต้นแบบเครื่องจ่ายน้ำอัจฉริยะที่ใช้ AI ช่วยเสนอการเตือนและปริมาณน้ำ สำหรับรายวิชา **2110356 Embedded Systems 2026/1** กลุ่ม **SengKeng** มีทั้ง firmware, ระบบจำลอง, cloud และแบบ CAD

สถานะ 15 พ.ย. 2026: firmware, local cloud, dashboard และ Telegram adapter มีในซอฟต์แวร์แล้ว แต่ขา **TDS, level, pump และ E-stop ยังไม่กำหนด**; gateway ยังไม่สั่งเริ่มปั๊ม และ AI ยังไม่เป็น closed loop ก่อน branch นี้ cloud รันเฉพาะในเครื่อง ขณะนี้มี config สำหรับ deploy หลัง HTTPS edge แล้ว **ยังไม่ได้ deploy หรือพิสูจน์เส้นทางด้วยฮาร์ดแวร์จริง** วิดีโอ checkpoint กำหนด **20 พ.ย. 2026** ดู [เส้นทาง checkpoint และหลักฐาน](docs/CHECKPOINT_CRITICAL_PATH.md)

ระบบสื่อสารตามเส้นทางนี้:

```text
Sensor node (ESP32: temperature; TDS/level ยังปิด)
  -- UART: 20-byte KW frames, CRC16, ACK/retry -->
Gateway (ESP32-S3: HX711, safety controller, durable outbox)
  -- HTTPS bearer telemetry -->
Cloud (cloud/server.py + SQLite) --> dashboard + optional Telegram
```

CRC16 ตรวจความเสียหายของข้อมูล ไม่ใช่การยืนยันตัวตน UART ส่วน safety ต้องทำงานในเครื่องและมีวงจรหยุดตัดกำลังปั๊มโดยอิสระจาก AI/cloud ข้อมูล ADC ยังไม่ใช่ TDS ที่สอบเทียบ และระดับน้ำแบบจุดเดียวไม่บอกปริมาตรถัง

| โฟลเดอร์ / ไฟล์ | เนื้อหา |
| --- | --- |
| `firmware/` | PlatformIO: `sensor_node`, `gateway`, protocol, safety, outbox และ host tests |
| `cloud/` | Python stdlib server, SQLite migrations, dashboard, Telegram และ AI/voice experiments |
| `simulation/` | แบบจำลองและการทดสอบ JavaScript |
| `.work/` | source และ toolchain สำหรับสร้างเว็บ 3D/parts |
| `cad/` | CAD Python sources, รายงานตรวจ และ geometry archive |
| `docs/` | handoff, รายการซื้อ, wiring, บันทึกทดสอบ และ execution ledger |
| `references/`, `output/real-parts/hero.jpg` | ภาพอ้างอิงและภาพอุปกรณ์ |

ติดตั้ง PlatformIO แล้ว build/flash ตาม [firmware/README.md](firmware/README.md) โดยตรวจรุ่นบอร์ด ขา และ serial port ก่อนเสมอ:

```bash
pio run -d firmware -e sensor_node
pio run -d firmware -e gateway
pio run -d firmware -e gateway -t upload --upload-port <GATEWAY_PORT>
pio run -d firmware -e sensor_node -t upload --upload-port <NODE_PORT>
```

ทดสอบซอฟต์แวร์จาก root (Node.js 20+, Python 3.11+, g++):

```bash
node --test simulation/*.test.mjs
python -m unittest discover -s cloud -p 'test_*.py' -v
for name in safety scale protocol integration dispense durable_queue audio; do
  g++ -std=c++17 -Ifirmware/include "firmware/test/${name}_test.cpp" -o "/tmp/kaew-${name}-test" || exit 1
  "/tmp/kaew-${name}-test" || exit 1
done
```

เครื่องที่ไม่มีคำสั่ง `python` ให้ใช้ `python3` แทน คำสั่ง host C++ ตรงกับ [.github/workflows/firmware.yml](.github/workflows/firmware.yml); CI ยัง compile firmware ทั้งสองบอร์ดและ `gateway_cloud_compile`

เริ่ม cloud ในเครื่องด้วย environment variables ที่เป็นส่วนตัว ใช้ device/admin token คนละค่าและสุ่มให้ยาว:

```bash
read -rsp 'Device token: ' KAEW_DEVICE_TOKEN; echo
read -rsp 'Admin token: ' KAEW_ADMIN_TOKEN; echo
export KAEW_DEVICE_TOKEN KAEW_ADMIN_TOKEN
python cloud/server.py
```

เปิด `http://127.0.0.1:8080/` แล้วกรอก admin token เพื่อดู dashboard ค่าเริ่มต้น bind เฉพาะ loopback และฐานข้อมูลอยู่ที่ `cloud/kaew.sqlite3` (gitignored) ดูตัวแปรใน [cloud/.env.example](cloud/.env.example); server อ่าน environment โดยตรง ไม่โหลด `.env` เอง

สำหรับ hosted HTTPS แนะนำ **Render** ผ่าน [render.yaml](render.yaml); ต้องมีบัญชี Render ที่ login แล้ว เชื่อม GitHub และตั้งสอง token เป็น secret ใน Dashboard ก่อน deploy เครื่องนี้มีเพียง GitHub login จึงยัง deploy ไม่ได้ หลังสร้าง Blueprint และตั้ง CLI/login เองแล้วใช้ `bash cloud/deploy.sh render`; มี Fly เป็นทางเลือกรอง ดูขั้นตอนครบและข้อจำกัด storage ใน [cloud/README.md](cloud/README.md) Free instance ใช้ disk ชั่วคราว ต้องมี persistent volume และ backup หากต้องเก็บ SQLite ข้าม restart

Gateway ใช้ไฟล์ส่วนตัว `firmware/include/cloud_config.local.h` โดยคัดลอกจาก [example](firmware/include/cloud_config.local.h.example) แล้วตั้ง SSID/password, URL เต็ม `https://<host>/api/telemetry`, device token และ CA ที่ตรวจสอบแล้ว เมื่อ URL/token ไม่ว่างจะเปิด publisher อัตโนมัติ; `KAEW_CLOUD_ENABLED=0` บังคับปิดได้ HTTPS ยังต้องมี CA และนาฬิกาที่ sync **ห้าม commit token, Wi-Fi password, Telegram credentials, `.env` หรือ local header** ตั้ง Telegram ผ่าน environment ของ server เท่านั้น

[GitHub Pages](https://theanrawich.github.io/Kaew/) แสดงโมเดลแนวคิดและ [parts gallery](https://theanrawich.github.io/Kaew/kaew-parts.html) จาก sources ใน CI ไม่เก็บ generated HTML/bundle ใน git หน้า CAD มีลิงก์ดาวน์โหลดเมื่อไม่มี mesh ตัว `cad-model.json` เป็น FreeCAD export ในเครื่องจาก `.work/export-cad-colors.py` และไม่เก็บใน git; geometry snapshot ปัจจุบันคือ [zip วันที่ 6 พ.ย.](cad/kaew-full-assembly-20261106.zip) ดู [CAD README](cad/README.md) สำหรับข้อจำกัดของแบบ

สร้างเว็บและตรวจ source ได้ด้วย:

```bash
npm ci --prefix .work/toolchain
node .work/build-kaew.cjs
node .work/make-parts-gallery.cjs
node .work/build-cad-viewer.cjs
node .work/check-standalone.cjs
node .work/check-wiring.cjs
node .work/check-model-labels.cjs
node .work/check-water-path.cjs
node .work/stage-pages.cjs
```

เอกสารทำงาน: [รายการซื้อ](docs/SHOPPING_LIST.md) · [CAD handoff](docs/CAD_HANDOFF.md) · [wiring และขาที่เสนอ](docs/wiring.md) · [แบบบันทึกทดสอบ](docs/TEST_RECORD_TEMPLATE.md) · [execution ledger](docs/EXECUTION.md) · [เป้าหมายผลิตภัณฑ์](docs/product-intent.md) · [แผนหลักฐานรายวิชา](docs/course-evidence.md)

สมาชิก SengKeng มี 5 คน: **Theanrawich Thungpromsri, Pongsest Ruangwitthayanusorn, Ratchapol Srisongkram, Tanakrit Onjinda และ Suphachok** เกณฑ์ M8 ต้องมี commit จริงจากสมาชิกทุกคน แต่ละคนต้องทำงานและ commit ด้วยบัญชีของตนเอง ไม่สร้างประวัติแทนกัน

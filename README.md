# Kaew (แก้ว) — AI-assisted Smart Water Dispenser

Kaew เป็นต้นแบบเครื่องจ่ายน้ำอัจฉริยะที่ใช้ AI ช่วยเสนอการเตือนและปริมาณน้ำ สำหรับรายวิชา **2110356 Embedded Systems 2026/1** กลุ่ม **SengKeng** มีทั้ง firmware, ระบบจำลอง, cloud และแบบ CAD

สถานะ 15 พ.ย. 2026: firmware, local cloud, dashboard และ Telegram adapter มีในซอฟต์แวร์แล้ว แต่ขา **TDS, level, pump และ E-stop ยังไม่กำหนด**; gateway ยังไม่สั่งเริ่มปั๊ม และ AI reminder closed loop มีในซอฟต์แวร์แล้ว (ยังไม่ deploy การเปลี่ยนแปลงนี้) Cloud เปิดใช้งานแล้วที่ **https://kaew-cloud.onrender.com** บน Render และ Supabase Postgres แต่ **ยังไม่ได้พิสูจน์เส้นทางด้วยฮาร์ดแวร์จริง** วิดีโอ checkpoint กำหนด **20 พ.ย. 2026** ดู [เส้นทาง checkpoint และหลักฐาน](docs/CHECKPOINT_CRITICAL_PATH.md)

ระบบสื่อสารตามเส้นทางนี้:

```text
Sensor node (ESP32: temperature; TDS/level ยังปิด)
  -- UART: 20-byte KW frames, CRC16, ACK/retry -->
Gateway (ESP32-S3: HX711, safety controller, durable outbox)
  -- HTTPS bearer telemetry -->
Cloud (cloud/server.py + Supabase Postgres; local: SQLite) --> dashboard + optional Telegram
```

CRC16 ตรวจความเสียหายของข้อมูล ไม่ใช่การยืนยันตัวตน UART ส่วน safety ต้องทำงานในเครื่องและมีวงจรหยุดตัดกำลังปั๊มโดยอิสระจาก AI/cloud ข้อมูล ADC ยังไม่ใช่ TDS ที่สอบเทียบ และระดับน้ำแบบจุดเดียวไม่บอกปริมาตรถัง

| โฟลเดอร์ / ไฟล์ | เนื้อหา |
| --- | --- |
| `firmware/` | PlatformIO: `sensor_node`, `gateway`, protocol, safety, outbox และ host tests |
| `cloud/` | Python server, SQLite/Postgres migrations, dashboard, Telegram และ AI/voice experiments |
| `simulation/` | แบบจำลองและการทดสอบ JavaScript |
| `site/` | หน้าเว็บและข้อมูลปั๊ม; generated HTML/bundle (gitignored) |
| `.work/` | source และ toolchain สำหรับสร้างเว็บ 3D/parts |
| `cad/` | CAD Python sources, รายงานตรวจ และ geometry archive |
| `docs/` | BOM (`kaew-bom.json`), handoff, รายการซื้อ, wiring, บันทึกทดสอบ และ execution ledger |
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

Hosted stack ที่เลือกคือ **Render web service เดียว** ให้บริการทั้ง API และ dashboard ผ่าน HTTPS และเก็บข้อมูลที่ **Supabase Postgres** โดยใช้ secret `DATABASE_URL` เมื่อไม่ตั้งตัวแปรนี้จะใช้ SQLite local ตาม `KAEW_DB_PATH` ต่อไป ไม่ต้องติดตั้ง psycopg สำหรับการพัฒนา SQLite

Cloud API และ dashboard เปิดใช้งานแล้วที่ <https://kaew-cloud.onrender.com> โดย POST telemetry ไปที่ `https://kaew-cloud.onrender.com/api/telemetry` ใช้ device token; dashboard ใช้ admin token แยกกัน การอัปเดต AI นี้ต้องให้ operator apply Postgres migration 002, ตั้ง GROQ_API_KEY secret บน kaew-cloud และ deploy จาก prod หลัง merge (หรือ reviewed branch) ภายหลัง ดู [cloud/README.md](cloud/README.md) สำหรับ local setup และข้อมูลดูแลระบบ ข้อมูล hosted อยู่ใน Supabase แต่ยังต้องวางแผน backup และคำนึงถึง free service ที่พักเมื่อไม่มีการใช้งาน

Gateway ใช้ไฟล์ส่วนตัว `firmware/include/cloud_config.local.h` โดยคัดลอกจาก [example](firmware/include/cloud_config.local.h.example) แล้วตั้ง SSID/password, URL เต็ม `https://kaew-cloud.onrender.com/api/telemetry`, device token และ CA ที่ตรวจสอบแล้ว เมื่อ URL/token ไม่ว่างจะเปิด publisher อัตโนมัติ; `KAEW_CLOUD_ENABLED=0` บังคับปิดได้ HTTPS ยังต้องมี CA และนาฬิกาที่ sync **ห้าม commit token, Wi-Fi password, Telegram credentials, `.env` หรือ local header** สำหรับ checkpoint ได้เตรียม local header แล้วโดย Wi-Fi SSID/password ยังว่าง ให้กรอกในเครื่องก่อน build แล้ว flash gateway ก่อน node ตาม [ขั้นตอน firmware](firmware/README.md#build-and-flash) ตั้ง Telegram ผ่าน environment ของ server เท่านั้น

[GitHub Pages](https://theanrawich.github.io/Kaew/) แสดงโมเดลแนวคิดและ [parts gallery](https://theanrawich.github.io/Kaew/kaew-parts.html) จาก sources ใน CI ไม่เก็บ generated HTML/bundle ใน git หน้า CAD มีลิงก์ดาวน์โหลดเมื่อไม่มี mesh ตัว `site/cad-model.json` เป็น FreeCAD export ในเครื่องจาก `.work/export-cad-colors.py` และไม่เก็บใน git; geometry snapshot ปัจจุบันคือ [zip วันที่ 6 พ.ย.](cad/kaew-full-assembly-20261106.zip) ดู [CAD README](cad/README.md) สำหรับข้อจำกัดของแบบ

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

เปิดเว็บในเครื่องจาก `site/kaew-3d.html` หลัง build หรือ serve repo root; `_site/` คือไฟล์เผยแพร่ที่คง URL เดิม

เอกสารทำงาน: [รายการซื้อ](docs/SHOPPING_LIST.md) · [CAD handoff](docs/CAD_HANDOFF.md) · [wiring และขาที่เสนอ](docs/wiring.md) · [แบบบันทึกทดสอบ](docs/TEST_RECORD_TEMPLATE.md) · [execution ledger](docs/EXECUTION.md) · [เป้าหมายผลิตภัณฑ์](docs/product-intent.md) · [แผนหลักฐานรายวิชา](docs/course-evidence.md)

สมาชิก SengKeng มี 5 คน: **Theanrawich Thungpromsri, Pongsest Ruangwitthayanusorn, Ratchapol Srisongkram, Tanakrit Onjinda และ Suphachok** เกณฑ์ M8 ต้องมี commit จริงจากสมาชิกทุกคน แต่ละคนต้องทำงานและ commit ด้วยบัญชีของตนเอง ไม่สร้างประวัติแทนกัน

AI reminder loop ตอบเกณฑ์ **M4**: ประวัติการดื่ม/telemetry → โมเดลเลือกช่วงเตือนครั้งถัดไป → server ตรวจและจำกัด 15–180 นาที → บันทึก `reminders.next_due` → scheduler สร้าง notification job เมื่อถึงเวลา → delivery worker ส่งผ่าน Telegram (ถ้าตั้งค่า) หรือ mock แล้วเลือกช่วงถัดไปอีกครั้ง การบันทึก drink event และ admin `POST /api/advice` ตั้งเวลาใหม่โดยไม่ส่งเตือนทันที; dashboard แสดง decision ล่าสุดผ่าน admin `GET /api/advice` ถ้าโมเดลไม่พร้อม ใช้ 60 นาที/200 มล. พร้อมบันทึก `fallback=true` และยังตั้งเตือนจริง ปริมาณ `suggested_ml` เป็นคำแนะนำเท่านั้น **AI ไม่ควบคุมปั๊ม และ `actuation_allowed` เป็น false เสมอ**

ตั้ง `GROQ_API_KEY` เป็น secret ใน process environment; `KAEW_AI_MODEL` มีค่าเริ่มต้น `openai/gpt-oss-20b` ซึ่งเป็น Groq production model ที่เร็วประมาณ 1000 tok/s เหมาะกับ demo และแทน Llama free-tier รุ่นที่เลิกใช้แล้ว ถ้าต้องการโมเดลที่หนักกว่า ให้ตั้ง `KAEW_AI_MODEL=openai/gpt-oss-120b` ไม่ได้ hardcode model id อื่น Optional `OPENROUTER_API_KEY` เป็น secret สำหรับ provider สำรอง ใช้ model id เดียวกัน ไม่มี key ก็เริ่ม server ได้และ fallback โดยไม่เรียก network Server ไม่โหลด `.env` เอง ใช้ decision-on-request และ scheduler ใน web service เดิม ไม่เพิ่ม cron/paid addon; Render free-plan sleep จะพัก scheduler ด้วย ยังต้องพิสูจน์ hardware/Telegram live delivery ดู [รายละเอียดและขั้นตอน operator](cloud/README.md#closed-loop-ai-reminders-m4)

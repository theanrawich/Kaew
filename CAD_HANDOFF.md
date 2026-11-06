# Kaew — ส่งต่องาน CAD ที่ยังไม่เสร็จ

> **อัปเดตการตัดสินใจ 6 พ.ย. 2026:** ผู้ใช้ตัด flow sensor ออกจากแผนแล้ว ตำแหน่งเผื่อ flow ใน CAD เป็นแบบเก่าที่ยังไม่ได้แก้ ไม่ใช่อุปกรณ์ที่ต้องติดตั้ง ใช้ load cell และเวลาเป็นแนวทางตรวจการจ่ายที่ยังต้องออกแบบและทดสอบ ปรับรายการ BOM/ผัง/แบบเมื่อทำงานต่อ

> **ตรวจสินค้า 6 พ.ย.:** ร้าน load cell ตัวเลือก 1kg/HX711 ระบุขนาด 80×13×13 มม. แต่ CAD ใช้ 80×12.7×12.7 มม. ต้องตรวจและปรับ clearance รวมทั้งรูยึดก่อนผลิต; ข้อมูลปั๊มในหน้าขายขัดกันและสุ่มรุ่น ห้ามใช้ความเร็ว 250 ml/min เป็นค่าที่ยืนยัน รายละเอียดอยู่ใน `KAEW_PARTS_CONFIRMATION.md`.

## ความคืบหน้า 6 พฤศจิกายน 2026

ชุดแบบล่าสุดสำหรับส่งต่ออยู่ใน `cad/kaew-full-assembly-20261106.zip` แตกไฟล์ลงใน `cad/` หลังแตก snapshot วันที่ 31 ต.ค. ชุดนี้มี FCStd, STEP ทั้งเครื่อง และ STEP/STL ใน `custom-parts-current/`; ภาพประกอบยังเป็นแบบก่อนแก้จุดยึด ไฟล์ ZIP เดิมวันที่ 31 ต.ค. เก็บไว้เป็นประวัติ

### ตรวจจุดยึดเพิ่มเติม

พบว่าเดิมบอสฝาหน้าห่างผนัง 0.1 มม. และรางบอร์ดห่างผนัง 0.6 มม. จึงปรับบอสทั้งสี่และรางบอร์ดสี่ชุดให้เป็นส่วนหนึ่งของ `Upper_case` แทนการวางลอย ผลตรวจล่าสุดกล่องเป็น solid เดียว ชุดประกอบมี 148 objects ครบ 23 แถว BOM และยังไม่พบ intersection ในสามกลุ่มที่ checker ครอบคลุม `mount-diagnostic.json` บันทึกระยะระหว่างคู่จุดยึด แต่การแตะกันไม่ได้พิสูจน์ว่าเป็นข้อต่อที่รับแรงได้

STEP ชิ้นส่วนปัจจุบัน 24 ชุดและ STL 21 ชุดอ่านกลับผ่านการตรวจเบื้องต้น อยู่ใน `custom-parts-current/` เท่านั้น โฟลเดอร์ `custom-parts/` เป็น export เก่าก่อนรวมบอสและราง ห้ามใช้เป็นชุดปัจจุบัน PETG solid จากแบบล่าสุดประมาณ 565.9 กรัมก่อนเผื่อการพิมพ์ ไฟล์ `verification.json` และ `fit-diagnostic.json` มี hash อ้างอิงแบบล่าสุด

ยังต้องกำหนดการยึด rail กับ shelf, keeper, guard, กล่องฐาน, ราง PCB และชิ้นอื่นให้รับแรงและถอดซ่อมได้จริง ตรวจสกรู/นอตและการเดินสายที่แท่นชั่ง ตลอดจน service sequence ตรวจ STEP/STL หลังแก้ครั้งต่อไปและแพ็กส่งต่อ Macro `render_assembly.FCMacro` สร้างภาพ `assembly.png`, `interior.png`, `exploded.png` แล้ว ภาพเป็นภาพทบทวนของแบบรอบก่อนหน้า ไม่รับรองการประกอบ หลังสร้างภาพ macro เดิมเปิดหน้าต่างถามบันทึกเพราะจัดตำแหน่งแยกชิ้นไว้ชั่วคราว จึงแก้ macro ให้บันทึกภาพแยกชิ้นเป็นไฟล์แยกชื่อ `render-exploded-review.FCStd` ในครั้งต่อไป ไม่ทับแบบหลัก

### สถานะก่อนแก้จุดยึด (เก็บเป็นประวัติ)

สร้าง full assembly จาก source ล่าสุดและรัน `check_fit.py` แล้ว แก้ขารองคลิปฟิวส์และทางเดินสาย 12 จุด ผลล่าสุดมี 156 objects ที่ BRep valid, rigid intersections 0 คู่, hose/frame intersections 0 คู่ และ harness/frame intersections 0 คู่ รายละเอียดและ hash อยู่ใน `cad/full-assembly-v1/fit-diagnostic.json` ตัวตรวจไม่ครอบคลุม fasteners ใน rigid pairs หรือจุดยึดทั้งหมด และไม่ได้หมายความว่าแบบพร้อมผลิต

`verify_assembly.py` อ่าน STEP ทั้งเครื่องและ STEP ชิ้น custom 32 ชุดกลับได้ valid; STL 29 ชุดปิด และไม่มี volume error เกิน 0.5% ผลและ hash อยู่ใน `verification.json` ราง PCB แต่ละตัวมีสอง solid แยกกันโดยตั้งใจ ระยะต่ำสุดของแท่นลอยจากขอบถาดและฝาครอบ HX711 ตามลำดับคือ 3.354 และ 3.5 มม.; แตะ spacer ปลายเคลื่อนตามแบบ ยังไม่ได้ตรวจการส่งแรงและสายทุกกรณี

ย้าย pull-up ให้หลบ Node USB envelope แล้ว USB envelope ยังคาบบอร์ดเจ้าของเล็กน้อย ต้องตรวจตำแหน่งปลั๊ก/การเสียบจริงตาม revision ส่วน pump lift envelope ซ้อนขวด ชั้นขวด rail รัดขวด probe และ keeper: ต้องกำหนดลำดับถอดและตรวจซ้ำ ไม่ถือว่าถอดปั๊มได้โดยยกชั้นอย่างเดียว Bottle lift envelope ซ้อนซีลฝาเอง ต้องแยกว่าเป็นชิ้นที่ยกไปพร้อมขวดหรือสิ่งกีดขวางจริง ทั้งหมดเป็นผลดิบใน `verification.json` ไม่ใช่การรับรอง serviceability

ไฟล์ `cad/full-assembly-v1/kaew-full-assembly-v1.FCStd` และ `.step` ที่สร้างใน workspace ใหม่กว่า snapshot ใน zip มวล PETG solid ล่าสุดประมาณ 565.1 กรัม ยังไม่รวมปัจจัยการพิมพ์ ตรวจจุดยึด ช่องผ่าน/ความแข็งแรง load path และ service envelope ต่อ แล้วสร้างภาพและแพ็กไฟล์ตามรายการด้านล่าง ข้อความสถานะวันที่ 31 ตุลาคมด้านล่างเก็บไว้เป็นประวัติ ไม่ใช่ผลตรวจล่าสุด

อัปเดต 31 ตุลาคม 2026 · ผู้ใช้ขอ push งานที่ค้างเพื่อไปทำต่ออีกเครื่อง

## เป้าหมายและคำสั่งล่าสุด

ผู้ใช้ต้องการออกแบบ **ทั้งเครื่องใน CAD/FreeCAD ใส่อุปกรณ์ทุกชิ้นตาม BOM ให้ครบและจัดประกอบให้แม่นยำ** ผู้ใช้ยืนยันว่า **ยังไม่มีอุปกรณ์จริง ให้ยึดตามสเปก** อย่าถามซ้ำว่าซื้ออุปกรณ์มาหรือยัง

FreeCAD 1.1.4 ถูกติดตั้งในเครื่องเดิมแล้ว อีกเครื่องต้องติดตั้งเอง เส้นทางบนเครื่องเดิมไม่ควรถูกนำไป hard-code งานอยู่ใน repo `theanrawich/Kaew` สาขา `main` เว็บไซต์เดิมมีอยู่แล้วและไม่ต้องเริ่มใหม่

## เริ่มบนอีกเครื่อง

```powershell
git clone https://github.com/theanrawich/Kaew.git
Set-Location Kaew
Expand-Archive -LiteralPath .\cad\kaew-cad-snapshots-20261031.zip -DestinationPath .\cad -Force
winget install --id FreeCAD.FreeCAD --exact --version 1.1.4 --source winget
```

ถ้ามี repo แล้ว ให้ `git pull --ff-only` หลังจัดการการแก้ไขในเครื่องนั้นตามปกติ ไม่ใช้ hard reset/clean ทับงานของผู้ใช้ อ่านไฟล์นี้และ `cad/full-assembly-v1/DESIGN.md` ก่อนแก้แบบ

ตัวช่วยค้นหา FreeCAD และรันขั้นตอน:

```powershell
.\cad\Run-Cad.ps1 -Task BuildAssembly
.\cad\Run-Cad.ps1 -Task CheckAssembly
```

ในระบบที่เรียก FreeCADCmd ได้จาก PATH สามารถรัน `FreeCADCmd cad/full-assembly-v1/build_assembly.py` แล้ว `FreeCADCmd cad/full-assembly-v1/check_fit.py` ได้โดยตรง

## สถานะจริง ณ จุดส่งต่อ

### แบบหัวจ่ายเดี่ยว — ตรวจ export แล้ว

`cad/spout-v1/` มีเสาและแขน PETG สองฝาซ้าย–ขวา หนาเสนอ 2.4 มม. หน้าตัด 42 × 36 มม. สูงชิ้นงาน 190 มม. แขนยื่น 112 มม. ปลายสายจ่ายสูง 165 มม. จากโต๊ะ ห่างปากแก้วอ้างอิง 33.5 มม. มีนอต M3 ประกบและฐาน M4 สี่รู

FreeCAD/STEP เป็น solid ที่ valid, STL เป็น mesh ปิด และตรวจสายยาง OD8 ในแบบแล้วไม่ชน น้ำหนักตามปริมาตร CAD ประมาณ 173.5 กรัม เผื่อ slice เป็น 175–210 กรัม งบเฉพาะหัวจ่ายเดี่ยวที่เสนอ 600–850 บาทรวมค่าพิมพ์ นอตและค่าส่ง ทั้งหมดยังเป็นแบบเสนอ ไม่เคยพิมพ์หรือทดสอบจริง

### ชุดประกอบทั้งเครื่อง — ยังไม่เสร็จ

`cad/full-assembly-v1/` มี builder/checker, component register, เส้นทางสาย และ CAD snapshot รอบแรก ครอบคลุม 23/23 แถว BOM ด้วย 156 CAD objects มี custom parts 32 ชิ้น ชุด snapshot ส่งออกก่อนการแก้ builder รอบล่าสุด

**สำคัญ: `build_assembly.py` และ `check_fit.py` ใหม่กว่าไฟล์ FCStd/STEP/STL และรายงาน JSON ที่แนบมา** จึงต้อง rebuild ก่อนใช้รายงานใหม่ รายงานเดิมเป็นหลักฐานข้อบกพร่องของ snapshot เก่า ไม่ใช่ผลยืนยันว่า patch ล่าสุดผ่านแล้ว สรุปมวล PETG 567.3 กรัมใน `assembly-summary.json` ก็เป็นค่าของ snapshot เก่า

รอบตรวจเดิมพบ rigid intersections 16 คู่ และ hose/frame intersections 3 คู่ รายการเต็มอยู่ใน `fit-diagnostic.json` หลังจากนั้นแก้โค้ดแล้ว แต่คำสั่ง rebuild/check **ไม่ได้ถูก execute** เพราะระบบอนุมัติอัตโนมัติล้มเหลวจาก usage limit ข้อความระบุว่าเป็น review failure ไม่ใช่ตัดสินว่า action ไม่ปลอดภัย ห้ามตีความว่ารันผ่านแล้วหรือพยายามข้าม approval check

## การแก้โค้ดล่าสุดที่ยังไม่ได้ตรวจ

- ย้ายและเจาะแผ่น bridge กล่องจอให้ไม่ฝังชนเปลือกหัวจ่าย เพิ่มรูยึดร่วมกับ case/spine
- ย้ายซีลขึ้นผิวฝา ย้ายช่อง vent ให้ไม่ชนซีล probe และย้าย saddle เซนเซอร์ระดับน้ำหลบขวด/วงแหวน
- ทำช่องหลบ rear rail ในวงแหวน เพิ่มหูยึดวงแหวนและนอตประกบ
- เพิ่มรู spacer/ฐาน/แท่นชั่ง ใช้หัวนอตจมเสมอพื้นแท่นแก้ว ย้าย overload stop หลบ HX711 และเพิ่มระยะภายในฝาครอบ HX711
- ยก fuse holder กับ clip ให้ไม่ชน protoboard และย้าย flyback provision
- ยกท่อออกจากปั๊มให้วิ่งเหนือ base bay, ทำช่องเข้าด้านข้าง spine และเพิ่ม clearance ผ่านผนังที่ต้นแนว sweep
- เพิ่มการตรวจ harness/frame intersections ใน checker; สายบางเส้นยังมีโอกาสชนจนกว่าจะได้รันตรวจจริง

## ทำต่อเป็นลำดับ

1. **Rebuild และรัน checker ล่าสุดก่อน** ตรวจ log ด้วย เพราะ FreeCADCmd อาจคืน exit code 0 แม้สคริปต์เกิด exception อย่าใช้ exit code อย่างเดียว
2. แก้ rigid, hose/frame และ harness/frame intersections ที่ยังเหลือ ตรวจเฉพาะที่เกิดขึ้นจริง ห้ามลดสเกลอุปกรณ์เพื่อซ่อนปัญหา รอยสัมผัสตั้งใจ/ซีลต้องอธิบายเป็นรายคู่ ไม่ใช้ blanket ignore
3. ตรวจความครบของจุดยึด: front panel, upper case-to-spine, board edge cradles, rear bottle rail/rings, pump keepers, shelf posts, washers/nuts และ cable retention บางชิ้นใน snapshot เป็น placement/provision ยังไม่ใช่ joint ที่ยืนยันแล้ว
4. ตรวจ service envelope ของ S3 USB ทั้งสองช่อง, ESP32 node USB, XY-3606 USB/terminal และรัศมีสาย รวมการถอดหัวปั๊มเมื่อยกชั้นขวดออก และช่องยกขวดด้านบน
5. ตรวจ load-cell load path: แท่นต้องรับแรงผ่านปลายเคลื่อนของ load cell เท่านั้น ไม่แตะ fixed rim, HX711 guard, สายหรือปลายสกรู ช่อง overload stop ที่เสนอ 1 มม. ยังต้องตั้งตามรุ่นจริง
6. อ่านกลับ STEP/STL ทุกชิ้น ตรวจ valid solids, closed meshes, BOM coverage, รูยึดร่วม, nozzle/cup alignment และสถานะ provenance อัปเดตรายงานที่มี source hash/timestamp เพื่อกันผล stale
7. ทำภาพ CAD ประกอบ/เปิดภายใน/แยกชิ้นของ **ทั้งเครื่อง** และบันทึกสี/visibility/ชื่อชิ้นส่วนใน FCStd ภาพที่มีอยู่ตอนนี้เป็นของหัวจ่ายเดี่ยวเท่านั้น
8. อัปเดตปริมาตร มวล PETG และราคาประเมินหลังแบบผ่าน fit checks, ทำแพ็กไฟล์ฉบับใหม่แล้วรายงานข้อจำกัดที่เหลือแก่ผู้ใช้

## กติกาสเปกและขอบเขต

- ยึดสินค้าและลิงก์จาก `kaew-bom.json`; ปั๊ม 504 บาท, OLED SH1106 1.3 นิ้ว 139 บาท, ขวด Crystal 1.5L, แก้ว Ocean Nova Rock B06511
- ขนาดแก้วปาก83/ฐาน63/สูง90 มม. มาจากผู้ผลิต ส่วนขวด Ø85×320 และกล่องปั๊ม 80×125×40/สูงรวม72 ยังเป็น estimate จากงานเดิม ไม่มี drawing ยืนยันจากร้าน ผู้ใช้อนุญาตให้ยึด spec ไม่ได้ทำให้ estimate กลายเป็นมิติผู้ผลิต
- ESP32-S3 reference 25.4×62.74 มม. มี 22 ขาต่อแถว รุ่นภาพร้านไม่มีรูมุม ให้ใช้ edge cradle ไม่สร้างรูบน PCB โดยไม่มีหลักฐาน ESP32 30 ขาและโมดูล generic ต้องรักษาสถานะ revision unconfirmed
- XY-3606 ใช้กรอบอ้างอิง 63×27 มม. ต้องรวมปลั๊ก/สาย ไม่ใช้ขนาดบอร์ดเล็ก 26 มม. ที่จะทำให้ประเมินพื้นที่ผิด
- `scale` ต้องมี load cell และ HX711; `tds` ต้องมี probe/cable/module; แถว fittings/electrical/assembly ต้องแตกเป็นอุปกรณ์ย่อยครบ
- แก้วและขวดติดตั้งอย่างละหนึ่ง ที่เหลือในแพ็กเป็นของสำรอง สายซิลิโคนซื้อ2เมตร แยก installed length กับ remainder
- flow sensor **ยังไม่เลือกรุ่น** มีแต่ reserved envelope ไม่ถือเป็นเซนเซอร์ติดตั้งแล้ว ห้ามนำ YF-S401 0.3–6 L/min กลับมาใช้กับปั๊มสูงสุด0.25 L/min
- ปั๊มมี adapter/accessory ที่ยังไม่ยืนยัน inclusion/แรงดัน โมเดลแยกจาก Glink12V ของภาคควบคุม อย่าอนุมานว่าปั๊ม12Vหรือ interface ESP32 ใช้งานได้แล้ว
- ไม่มี bottle-cap thread ที่ยืนยัน: ใช้ฝาเดิมดัดแปลงและระบุ hole/seal proposal น้ำเดินในสายยางต่อเนื่อง; ไม่อ้าง food-contact หรือความปลอดภัยน้ำจาก PETG/TDS
- เป็นงาน **mechanical CAD assembly study** ยังไม่มี hardware/firmware/AI ที่ทดสอบแล้ว การเปลี่ยนเว็บหรือวงจรให้ทำตามคำสั่งถัดไปของผู้ใช้

## ไฟล์สำคัญ

- `kaew-bom.json`, `KAEW_SHOPPING_LIST.md`: SKU และงบเดิม
- `cad/spout-v1/build_spout.py`, `verify_exports.py`, `render_spout.FCMacro`: สร้าง/ตรวจ/เรนเดอร์หัวจ่ายเดี่ยว
- `cad/full-assembly-v1/build_assembly.py`: source ชุดประกอบล่าสุด
- `cad/full-assembly-v1/check_fit.py`: diagnostic ล่าสุด
- `cad/full-assembly-v1/DESIGN.md`: brief และแผนตรวจ
- `cad/full-assembly-v1/component-register.json/.csv`, `routes.json`, `fit-diagnostic.json`: ผลจาก snapshot ก่อน patch ล่าสุด
- `cad/kaew-cad-snapshots-20261031.zip`: FCStd/STEP/STL/ภาพสำหรับเปิดต่อ

## ประโยคสำหรับบอก Codex บนอีกเครื่อง

> ทำงาน Kaew ต่อจาก CAD_HANDOFF.md ใช้ FreeCAD ทำ full assembly ให้ครบ BOM ยึดสเปกตามที่ผู้ใช้ยืนยัน เริ่ม rebuild จาก cad/full-assembly-v1/build_assembly.py แล้วรัน check_fit.py ก่อน เพราะ CAD snapshot และรายงานใน repo ยังเก่ากว่า patch ล่าสุด แก้จุดชน/จุดยึดและตรวจ export ก่อนทำภาพและประเมินราคาใหม่

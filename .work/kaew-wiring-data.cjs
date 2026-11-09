// Semantic endpoints are authoritative for this proposal. Peripheral pin order is
// diagrammatic, not a claim about the unverified marketplace board revisions.
const colors = {vcc:'#d4484f', power:'#bc6b16', ground:'#37474f', sda:'#147cbb', scl:'#a66d13', data:'#8250bb', clock:'#258575', audio:'#be4e91', pending:'#8b7657'};
const device = (id,label,subtitle,x,y,pins,note,status='proposal') => ({id,label,subtitle,x,y,pins,note,status});
const wire = (device,from,to,kind,note,status='proposal') => ({device,from,to,kind,color:colors[kind],note,status});
const supply = () => device('supply','แหล่งจ่าย 5V','ตั้งและวัด buck ก่อนต่อ',0,-32,['5V','GND'],'แหล่งจ่ายภายนอกผ่าน buck; ตั้งและวัด 5V ก่อนต่อ ไม่ใช้ USB จ่ายไฟพร้อมกับขา 5V; ห้ามนำ 12V เข้าบอร์ด');
const rail = () => device('rail','จุดแยกสาย 3.3V','ขั้วต่อร่วม ไม่ใช่ GPIO',0,29,['3V3','GND'],'ต่อจาก 3V3/GND ของบอร์ดผ่านจุดแยกสายจริง ไม่ยัดสายหลายเส้นลงรูเดียว; ต้องตรวจงบกระแสของ regulator ก่อนประกอบ');
const common = () => [wire('supply','supply.5V','board.5V','power','จ่าย 5V จาก buck ที่ตั้งและวัดแล้ว; เลือกจ่ายทางนี้หรือ USB อย่างใดอย่างหนึ่ง'),wire('supply','supply.GND','board.GND','ground','กราวด์ภาค logic ร่วมกัน'),wire('rail','board.3V3','rail.3V3','vcc','แยกไฟ 3.3V จาก regulator ของบอร์ด; ตรวจกระแสรวมก่อนต่อ'),wire('rail','board.GND','rail.GND','ground','จุดแยกกราวด์สำหรับเซนเซอร์')];
module.exports = {
 status:'proposal', updatedAt:'2026-10-31',
 sources:[
  {label:'Espressif: ESP32-S3-DevKitC-1 v1.1 / ลำดับหัวต่อ',url:'https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html'},
  {label:'Espressif: ESP32 / ขาและ ADC1',url:'https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf'},
  {label:'Analog Devices: DS18B20 / 1-Wire และ pull-up',url:'https://www.analog.com/media/en/technical-documentation/data-sheets/DS18B20.pdf'},
  {label:'TDK InvenSense: INMP441 datasheet',url:'https://www.invensense.tdk.com/en-us/download-resource/ds-inmp441-00-inmp441-datasheet'},
  {label:'SparkFun: HX711 reference schematic (บอร์ดร้านอาจต่าง)',url:'https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/SparkFun_HX711_Load_Cell_v11.pdf'},
  {label:'Adafruit: MAX98357 pinouts (บอร์ดร้านอาจต่าง)',url:'https://learn.adafruit.com/adafruit-max98357-i2s-class-d-mono-amp/pinouts'}
 ],
 boards:{
  gateway:{
   label:'ESP32-S3', model:'DevKitC-1 · N16R8 · 44 ขา',
   note:'มองจากด้านชิ้นส่วน เสาอากาศอยู่บน / USB อยู่ล่าง; J1 ซ้ายและ J3 ขวาอิง DevKitC-1 ของ Espressif ต้องเทียบสกรีนบอร์ด DIYMORE อีกครั้ง GPIO คือหมายเลขสัญญาณ ไม่ใช่ลำดับรู',
   left:['3V3','3V3_2','RST','GPIO4','GPIO5','GPIO6','GPIO7','GPIO15','GPIO16','GPIO17','GPIO18','GPIO8','GPIO3','GPIO46','GPIO9','GPIO10','GPIO11','GPIO12','GPIO13','GPIO14','5V','GND'],
   right:['GND_2','TX','RX','GPIO1','GPIO2','GPIO42','GPIO41','GPIO40','GPIO39','GPIO38','GPIO37','GPIO36','GPIO35','GPIO0','GPIO45','GPIO48','GPIO47','GPIO21','GPIO20','GPIO19','GND_3','GND_4'],
   devices:[
    device('oled','OLED 1.3 นิ้ว','SH1106 · I²C',-30,18,['VCC','GND','SDA','SCL'],'ผังเสนอ SDA=GPIO8, SCL=GPIO9; ใช้ไฟและ pull-up ของ I²C ที่ 3.3V ต้องตรวจว่าบอร์ดจอจากร้านรองรับ 3.3V และลำดับขาใด'),
    device('hx','HX711','อ่านน้ำหนักแก้ว',-30,1,['VCC','GND','DT','SCK','E+','E-','A+','A-'],'เสนอ VCC/DVDD 3.3V เพื่อให้ DT เป็น logic 3.3V; บอร์ดที่แยก VCC กับ VDD ต้องตรวจวงจรและผูก digital supply เป็น 3.3V'),
    device('load','Load cell 1 kg','เข้าขา E / A ของ HX711',-30,-18,['E+','E-','A+','A-'],'สีสาย load cell ขึ้นกับผู้ผลิต ให้ตรวจ datasheet/วัดคู่ excitation และ signal; สีในภาพเป็นสีผัง ไม่ใช่รหัสสีที่ยืนยันของสายจริง'),
    device('mic','INMP441','ไมโครโฟน · I²S RX',30,18,['VDD','GND','SCK','WS','SD','L/R'],'ใช้ 3.3V; SCK=GPIO4, WS=GPIO5, SD=GPIO6; L/R ผูก GND เลือก left channel และตั้งค่า I²S RX ให้ตรง'),
    device('amp','MAX98357A','แอมป์ · I²S TX',30,1,['VIN','GND','BCLK','LRC','DIN','SPK+','SPK-'],'BCLK=GPIO10, LRC=GPIO11, DIN=GPIO12; VIN จาก 5V ไม่ใช่ 3V3 regulator; ตรวจ SD/MODE และ GAIN ตาม revision ของแอมป์ก่อนใช้'),
    device('speaker','ลำโพง 4Ω 3W','ขั้วลอยจากแอมป์',30,-18,['+','-'],'ต่อเฉพาะ SPK+ กับ SPK- ของแอมป์ ทั้งสองขาเป็น BTL ห้ามนำขั้วใดไปต่อ GND'),
    device('pump','ภาคขับปั๊ม','D4184 / interface รอตรวจ',-30,-36,['CTRL3V3','GND'],'GPIO15 เป็นขาสั่งที่จองไว้ ถึงภาคอินเทอร์เฟซ logic 3.3V เท่านั้น ยังไม่ยืนยันว่า D4184 ขับตรงได้; วงจรกำลัง, default-off, flyback, hardware stop และแรงดันปั๊มยังรอยืนยัน ไม่วาดสายมอเตอร์หรือไฟบ้าน','hold'),
    device('stop','Stop status interface','วงจรยังรอยืนยัน',30,-36,['STOP3V3','GND'],'จอง GPIO16 สำหรับรายงานสถานะหยุดผ่านอินเทอร์เฟซที่รอออกแบบ; การอ่าน GPIO อย่างเดียวไม่ใช่การตัดกำลังปั๊ม ต้องมี hardware stop แยก แผนปัจจุบันไม่มี flow sensor','hold'),
    supply(),rail()
   ],
   connections:[...common(),
    wire('oled','rail.3V3','oled.VCC','vcc','3.3V → VCC; ตรวจว่าจอร้านรองรับ 3.3V'),wire('oled','rail.GND','oled.GND','ground','กราวด์จอ'),wire('oled','board.GPIO8','oled.SDA','sda','I²C SDA / ข้อมูลจอ'),wire('oled','board.GPIO9','oled.SCL','scl','I²C SCL / clock จอ'),
    wire('hx','rail.3V3','hx.VCC','vcc','เลี้ยง HX711 และ logic ที่ 3.3V; ตรวจขา VDD หากบอร์ดแยก'),wire('hx','rail.GND','hx.GND','ground','กราวด์ HX711'),wire('hx','hx.DT','board.GPIO17','data','DOUT / DT จาก HX711 เข้าบอร์ด'),wire('hx','board.GPIO18','hx.SCK','clock','PD_SCK จากบอร์ดไป HX711'),
    wire('load','hx.E+','load.E+','vcc','Excitation + ของสะพานวัดน้ำหนัก'),wire('load','hx.E-','load.E-','ground','Excitation - ไม่ระบุสีสายจริง'),wire('load','load.A+','hx.A+','data','Signal + ไป channel A+'),wire('load','load.A-','hx.A-','clock','Signal - ไป channel A-'),
    wire('mic','rail.3V3','mic.VDD','vcc','VDD ไมค์ 3.3V'),wire('mic','rail.GND','mic.GND','ground','กราวด์ไมค์'),wire('mic','board.GPIO4','mic.SCK','clock','I²S RX bit clock'),wire('mic','board.GPIO5','mic.WS','scl','I²S RX word select'),wire('mic','mic.SD','board.GPIO6','data','ข้อมูลเสียงจากไมค์เข้าบอร์ด'),wire('mic','rail.GND','mic.L/R','ground','เลือก left channel; ไม่ปล่อย L/R ลอย'),
    wire('amp','supply.5V','amp.VIN','power','VIN แอมป์ใช้ไฟ 5V จาก buck; ตรวจความสามารถจ่ายกระแส'),wire('amp','rail.GND','amp.GND','ground','กราวด์ logic ของแอมป์'),wire('amp','board.GPIO10','amp.BCLK','clock','I²S TX bit clock'),wire('amp','board.GPIO11','amp.LRC','scl','I²S TX word select'),wire('amp','board.GPIO12','amp.DIN','audio','ข้อมูลเสียงจากบอร์ดไปแอมป์'),
    wire('speaker','amp.SPK+','speaker.+','audio','SPK+ → ลำโพง +; ห้ามต่อกราวด์'),wire('speaker','amp.SPK-','speaker.-','data','SPK- → ลำโพง -; ห้ามต่อกราวด์'),
    wire('pump','board.GPIO15','pump.CTRL3V3','pending','ขาสั่งจองไว้ รอตรวจวงจรรับ logic 3.3V / default-off ก่อนต่อปั๊ม','hold'),wire('pump','rail.GND','pump.GND','ground','กราวด์ฝั่ง logic ของอินเทอร์เฟซ รอตรวจการแยกวงจร','hold'),
    wire('stop','stop.STOP3V3','board.GPIO16','pending','อ่านสถานะจาก interface ที่รอยืนยัน; ต้องมีวงจร hardware stop แยก','hold'),wire('stop','rail.GND','stop.GND','ground','กราวด์ฝั่ง logic รอยืนยัน interface','hold')
   ]
  },
  node:{
   label:'ESP32',model:'DevKit V1 · Type-C · 30 ขา',
   note:'แถวขาเป็นแม่แบบ DevKit V1 30 ขา ไม่ใช่ drawing ที่ยืนยันของร้าน AEI; เสาอากาศบน / USB ล่าง ตรวจชื่อ GPIO บนสกรีนจริงทุกจุด โดยเฉพาะ VIN/5V ไม่ใช้นับรูแทนชื่อขา',
   left:['EN','VP','VN','GPIO34','GPIO35','GPIO32','GPIO33','GPIO25','GPIO26','GPIO27','GPIO14','GPIO12','GPIO13','GND','5V'],
   right:['3V3','GND_2','GPIO15','GPIO2','GPIO4','GPIO16','GPIO17','GPIO5','GPIO18','GPIO19','GPIO21','RX0','TX0','GPIO22','GPIO23'],
   devices:[
    device('tds','TDS module','Analog OUT ยังต้องวัด',-30,16,['VCC','GND','OUT'],'โมดูลร้านเป็น generic ไม่ใช่ DFRobot ที่ยืนยันแล้ว; 3.3V เป็นไฟที่เสนอและยังต้องตรวจว่ารองรับ ต้องวัดช่วง OUT และออกแบบ input protection ก่อนต่อ ADC','hold'),
    device('analog','ADC protection','รอวัดช่วงสัญญาณ TDS',-30,-4,['IN','OUT3V3','GND'],'บล็อกแสดงตำแหน่งวงจรป้องกัน/ปรับสเกล ยังไม่กำหนดค่า R/C หรือ clamp; GPIO34 เป็น ADC1 input-only ห้ามป้อนแรงดันเกินช่วงที่ออกแบบ','hold'),
    device('temperature','DS18B20','หัววัด 1-Wire',30,16,['VDD','GND','DQ'],'เสนอใช้แบบจ่าย VDD 3.3V ไม่ใช้ parasite power; DQ เข้า GPIO4 พร้อม R4.7kΩ pull-up ไป 3.3V ตรวจสายหัววัดตามผู้ผลิต'),
    device('pullup','R 4.7kΩ','ระหว่าง DQ กับ 3.3V',30,-3,['A','B'],'A ต่อ 3.3V, B ต่อจุด DQ เดียวกับ DS18B20 และ GPIO4'),
    device('level','Level interface','XKC-Y25-NPN รอตรวจ',-30,-24,['V5','GND','OUT3V3'],'บล็อกนี้แทนวงจรรับ NPN/ปรับระดับ ไม่ใช่ลำดับสายของ XKC; GPIO27 รับเฉพาะสัญญาณหลัง interface 3.3V ยังต้องตรวจรุ่น การจ่าย 5V, COM, output และ pull-up ตาม datasheet จริง','hold'),
    device('link','ส่งค่าไป Gateway','Wi-Fi / ESP-NOW',30,-24,[],'สื่อสารไร้สายระหว่างสองบอร์ด ไม่มีสาย UART ในผังนี้ โปรโตคอล ACK / timeout ยังเป็นงานออกแบบ'),
    supply(),rail()
   ],
   connections:[...common(),
    wire('tds','rail.3V3','tds.VCC','vcc','ไฟ 3.3V ที่เสนอ รอตรวจโมดูล generic ว่ารองรับก่อนต่อ','hold'),wire('tds','rail.GND','tds.GND','ground','กราวด์ TDS รอตรวจ revision','hold'),wire('tds','tds.OUT','analog.IN','data','OUT เข้า input protection ก่อน ไม่เข้าขา ESP32 โดยตรง','hold'),wire('tds','analog.OUT3V3','board.GPIO34','pending','รอยืนยันแรงดันและวงจรป้องกัน ก่อนเข้า GPIO34 / ADC1_CH6','hold'),wire('tds','rail.GND','analog.GND','ground','กราวด์ input protection รอออกแบบวงจร','hold'),
    wire('temperature','rail.3V3','temperature.VDD','vcc','VDD หัววัด 3.3V'),wire('temperature','rail.GND','temperature.GND','ground','กราวด์หัววัด'),wire('temperature','temperature.DQ','board.GPIO4','data','DQ 1-Wire ไป GPIO4; มี R pull-up แยกให้เห็น'),wire('temperature','rail.3V3','pullup.A','vcc','ด้าน A ของ R4.7kΩ ต่อ 3.3V'),wire('temperature','pullup.B','temperature.DQ','data','ด้าน B ของ R ต่อร่วมกับ DQ / GPIO4'),
    wire('level','supply.5V','level.V5','power','5V เข้าภาค field/interface รอตรวจ datasheet XKC รุ่นจริง','hold'),wire('level','rail.GND','level.GND','ground','กราวด์ฝั่ง logic ของ interface รอยืนยัน','hold'),wire('level','level.OUT3V3','board.GPIO27','pending','จอง GPIO27 รับจาก interface 3.3V ที่รอตรวจ ห้ามต่อสาย OUT 5–12V โดยตรง','hold')
   ]
  }
 }
};

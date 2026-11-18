"""Thai text intent parsing; this module is not speech recognition or an AI model."""
import unicodedata

def parse_text(text):
    if not isinstance(text,str) or not 0 < len(text) <= 500: return {'intent':'invalid'}
    text=unicodedata.normalize('NFC',text).strip().lower()
    if not text.startswith('แก้ว'): return {'intent':'no_wake'}
    text=text[4:].strip()
    if any(word in text for word in ('หยุด','stop','พอแล้ว')): return {'intent':'stop'}
    if any(word in text for word in ('สถานะอุปกรณ์','สถานะเครื่อง','device status')): return {'intent':'status'}
    if any(word in text for word in ('เตือน','remind','reminder')):
        return {'intent':'reminder'}
    if any(word in text for word in ('เติม','ริน','refill','fill')) and any(word in text for word in ('น้ำ','water')):
        return {'intent':'refill'}
    if ('น้ำ' in text or 'water' in text) and any(word in text for word in ('เหลือ','ระดับ','ขวด','เท่าไหร่','level','left')):
        return {'intent':'level'}
    return {'intent':'unknown'}

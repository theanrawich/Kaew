"""Thai text intent parsing; this module is not speech recognition or an AI model."""
import re
import unicodedata


_DRANK_AMOUNT = re.compile(
    r'ดื่ม\s*(?:น้ำ\s*)?(?:ไป\s*)?(?:แล้ว\s*)?'
    r'(?:เท่าไหร่|เท่าไร|กี่(?=\s*(?:มิลลิลิตร|มล\.?|ลิตร|แก้ว|ขวด|ครับ|คะ|ค่ะ|[?？]|$)))'
)

def parse_text(text):
    if not isinstance(text,str) or not 0 < len(text) <= 500: return {'intent':'invalid'}
    text=unicodedata.normalize('NFC',text).strip().lower()
    if not text.startswith('แก้ว'): return {'intent':'no_wake'}
    text=text[4:].strip()
    if _DRANK_AMOUNT.search(text) and not any(day in text for day in ('เมื่อวาน', 'พรุ่งนี้')):
        return {'intent':'drank_today'}
    if any(word in text for word in ('สถานะอุปกรณ์','สถานะเครื่อง','device status')): return {'intent':'status'}
    if any(word in text for word in ('เติม','ริน','refill','fill')) and any(word in text for word in ('น้ำ','water')):
        return {'intent':'refill'}
    return {'intent':'unknown'}
